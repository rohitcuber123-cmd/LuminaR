from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import HTTPException
from backend.services import library_activity_identity as identities
from backend.services.institution_repository import now


@pytest.fixture
def activity(library, client, database):
    library_id = library()
    assert client.post(f'/libraries/{library_id}/join', headers={'x-test-user': '2'}, json={}).status_code == 200
    database.institution_memberships.insert_one({'membership_id': str(uuid4()), 'library_id': library_id,
        'user_id': 3, 'role': 'LIBRARIAN', 'status': 'ACTIVE', 'is_owner': False})
    event = {'event_id': str(uuid4()), 'library_id': library_id, 'event': 'BORROW_REQUEST_APPROVED',
        'actor_user_id': 3, 'target_user_id': 2, 'created_at': now(), 'metadata': {'loan_id': str(uuid4())}}
    database.institution_audit.insert_one(deepcopy(event))
    return library_id, event


def read(client, activity, audit=False, user=1):
    path = 'audit' if audit else 'staff/activity'
    result = client.get(f'/libraries/{activity[0]}/{path}', headers={'x-test-user': str(user)})
    assert result.status_code == 200, result.text
    return next(row for row in result.json()['results'] if row['event_id'] == activity[1]['event_id'])


def test_operational_activity_actor_email(client, activity):
    row = read(client, activity, user=3)
    assert row['actor']['email'] == 'v2f-3@example.com'
    assert row['actor']['identity_source'] == 'CURRENT_ACCOUNT'


def test_operational_activity_member_email(client, activity):
    assert read(client, activity)['member']['email'] == 'v2f-2@example.com'


def test_audit_actor_email(client, activity):
    assert read(client, activity, audit=True)['actor']['email'] == 'v2f-3@example.com'


def test_actor_member_remain_distinct(client, activity):
    row = read(client, activity)
    assert row['actor']['user_id'] == row['actor_user_id'] == 3
    assert row['member']['user_id'] == row['target_user_id'] == 2
    assert row['actor'] != row['member']


def test_system_actor_label(client, activity, database):
    database.institution_audit.update_one({'event_id': activity[1]['event_id']}, {'$set': {'actor_user_id': None}})
    row = read(client, activity)
    assert row['actor_user_id'] is None and row['actor'] is None


def test_missing_actor_fallback(client, activity, database):
    database.institution_audit.update_one({'event_id': activity[1]['event_id']}, {'$set': {'actor_user_id': 50000}})
    row = read(client, activity)
    assert row['actor_user_id'] == 50000 and row['actor'] is None


def test_deleted_actor_history_still_renders(client, activity, database):
    database.users.delete_one({'user_id': 3})
    row = read(client, activity, audit=True)
    assert row['actor_user_id'] == 3 and row['actor'] is None


def test_activity_identity_batch_lookup(client, activity, monkeypatch):
    calls = []
    original = identities.users_collection.find
    def find(query, projection=None, *args, **kwargs):
        if isinstance(query.get('user_id'), dict) and '$in' in query['user_id']:
            calls.append((query, projection))
        return original(query, projection, *args, **kwargs)
    monkeypatch.setattr(identities.users_collection, 'find', find)
    read(client, activity)
    assert len(calls) == 1 and calls[0][0] == {'user_id': {'$in': [2, 3]}}
    assert calls[0][1] == {'_id': 0, 'user_id': 1, 'name': 1, 'email': 1}


def test_activity_no_n_plus_one_identity_queries(client, activity, database, monkeypatch):
    for _ in range(49):
        row = {**activity[1], 'event_id': str(uuid4())}
        database.institution_audit.insert_one(row)
    calls = []
    original = identities.users_collection.find
    def find(query, *args, **kwargs):
        if isinstance(query.get('user_id'), dict): calls.append(query)
        return original(query, *args, **kwargs)
    monkeypatch.setattr(identities.users_collection, 'find', find)
    result = client.get(f'/libraries/{activity[0]}/staff/activity?limit=50')
    assert result.status_code == 200 and len(result.json()['results']) == 50
    assert calls == [{'user_id': {'$in': [2, 3]}}]


def test_activity_cross_library_identity_denied(client, activity, library, monkeypatch):
    other = library(owner=4)
    result = client.get(f'/libraries/{other}/staff/activity')
    assert result.status_code == 404 and 'v2f-4@example.com' not in result.text
    with pytest.raises(HTTPException):
        identities.hydrate_activity_identities(other, [activity[1]])


def test_general_user_cannot_view_activity_emails(client, activity):
    for path in ['staff/activity', 'audit']:
        result = client.get(f'/libraries/{activity[0]}/{path}', headers={'x-test-user': '2'})
        assert result.status_code == 403 and 'v2f-3@example.com' not in result.text


def test_platform_role_alone_cannot_view_tenant_activity_emails(client, activity, database):
    database.platform_role_assignments.insert_one({'assignment_id': str(uuid4()), 'user_id': 9,
        'role': 'PLATFORM_ADMIN', 'status': 'ACTIVE', 'approved_by': 'isolated-test-review',
        'approval_ref': 'PART2F-ACTIVITY-ISOLATED-FIXTURE', 'approved_at': now()})
    from backend.platform_dependencies import has_platform_admin
    assert has_platform_admin({'sub': '9'})
    for path in ['staff/activity', 'audit']:
        result = client.get(f'/libraries/{activity[0]}/{path}', headers={'x-test-user': '9', 'x-test-role': 'ADMIN'})
        assert result.status_code == 404 and 'v2f-3@example.com' not in result.text


def test_activity_reference_full_value_preserved(client, activity, database):
    before = list(database.institution_audit.find({'library_id': activity[0]}))
    row = read(client, activity)
    read(client, activity, audit=True)
    assert row['metadata']['loan_id'] == activity[1]['metadata']['loan_id']
    assert list(database.institution_audit.find({'library_id': activity[0]})) == before


def test_activity_current_email_not_historical_snapshot(client, activity, database):
    database.users.update_one({'user_id': 3}, {'$set': {'email': 'changed@example.com', 'is_active': False}})
    row = read(client, activity, audit=True)
    assert row['actor']['email'] == 'changed@example.com'
    assert row['actor']['identity_source'] == 'CURRENT_ACCOUNT'
    assert row['actor_user_id'] == 3


def test_activity_existing_event_email_snapshot_fallback(client, activity, database):
    database.users.delete_one({'user_id': 2})
    database.institution_audit.update_one({'event_id': activity[1]['event_id']}, {'$set': {'target_email_normalized': 'event-member@example.com'}})
    row = read(client, activity)
    assert row['member']['email'] == 'event-member@example.com'
    assert row['member']['identity_source'] == 'EVENT_SNAPSHOT'


def test_activity_identity_rechecks_authority_before_output(client, activity, database, monkeypatch):
    original = identities.hydrate_activity_identities
    def revoke(library_id, rows):
        result = original(library_id, rows)
        database.institution_memberships.update_one({'library_id': library_id, 'user_id': 1}, {'$set': {'status': 'REMOVED'}})
        return result
    monkeypatch.setattr(identities, 'hydrate_activity_identities', revoke)
    result = client.get(f'/libraries/{activity[0]}/audit')
    assert result.status_code == 404 and 'v2f-3@example.com' not in result.text
