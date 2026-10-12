import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi import HTTPException

from backend.institution_dependencies import require_library_membership
from backend.services.institution_repository import now, library_mutation
from backend.services.institution_security import verify_code
from scripts.migrate_institution_v1 import plan, apply_plan


@pytest.mark.parametrize('private', [False, True])
def test_registration_models_owner_and_global_identity(register, database, private):
    result = register(private=private)
    library, member = result['library'], result['membership']
    assert member['role'] == 'ADMIN' and member['is_owner'] and member['status'] == 'ACTIVE'
    assert database.users.find_one({'user_id': 1})['role'] == 'GENERAL_USER'
    row = database.institution_libraries.find_one({'library_id': library['library_id']})
    assert row['owner_user_id'] == 1 and row['status'] == 'ACTIVE'
    security = database.institution_security.find_one({'library_id': library['library_id']})
    if private:
        assert security['access_code_hash'].startswith('$argon2id$')
        assert security['access_code_hash'] != 'Institution Test Passphrase'
        assert verify_code(security['access_code_hash'], 'Institution Test Passphrase')
    else:
        assert security['access_code_hash'] is None
    assert 'owner_user_id' not in library and 'access_code_hash' not in json.dumps(result)
    assert database.institution_audit.count_documents({'event': 'LIBRARY_REGISTERED'}) == 1


@pytest.mark.parametrize('extra', ['owner_user_id', 'owner_role', 'created_by', 'admin_user_id', 'is_owner', 'is_admin', 'user_id', 'membership_status'])
def test_registration_mass_assignment(client, extra):
    response = client.post('/libraries/register', json={'name': 'Example', 'slug': 'example-library', 'access_mode': 'PUBLIC', 'library_type': 'PUBLIC_LIBRARY', extra: 'ADMIN'})
    assert response.status_code == 422


@pytest.mark.parametrize('body', [
    {'access_mode': 'PRIVATE_CODE', 'library_type': 'PRIVATE_INSTITUTION'},
    {'access_mode': 'PUBLIC', 'library_type': 'PUBLIC_LIBRARY', 'access_code': 'SensitivePassword'},
    {'access_mode': 'PUBLIC', 'library_type': 'PRIVATE_INSTITUTION'},
    {'access_mode': 'PRIVATE_CODE', 'library_type': 'PRIVATE_INSTITUTION', 'access_code': 'short'},
])
def test_registration_invalid_access_and_secret_safe_errors(client, body):
    result = client.post('/libraries/register', json={'name': 'Example', 'slug': 'example-library', **body})
    assert result.status_code == 422
    assert 'SensitivePassword' not in result.text and 'short' not in result.text
    assert 'input' not in result.text


def test_duplicate_normalized_slug_and_duplicate_names(client, register, database):
    register(slug='Central-Library')
    response = client.post('/libraries/register', json={'name': 'Other', 'slug': 'central-library', 'access_mode': 'PUBLIC', 'library_type': 'PUBLIC_LIBRARY'})
    assert response.status_code == 409
    register(slug='second-library')
    assert database.institution_libraries.count_documents({}) == 2
    assert database.institution_memberships.count_documents({}) == 2
    assert database.institution_locks.count_documents({}) == 0


def test_discovery_search_filter_pagination_and_safe_metadata(client, register, h):
    a = register()['library']['library_id']; register(private=True)
    for search in ['Aurora', 'Hyderabad', 'Telangana']:
        result = client.get('/libraries', params={'search': search}, headers=h(2))
        assert result.status_code == 200 and result.json()['total'] >= 1
        assert not any(secret in result.text for secret in ['access_code_hash', 'owner_user_id', 'token_hash'])
    assert client.get('/libraries?kind=public').json()['total'] == 1
    assert client.get('/libraries?kind=private').json()['total'] == 1
    assert client.get('/libraries?limit=1').json()['has_more']
    assert len(client.get('/libraries?offset=1&limit=1').json()['results']) == 1
    assert client.get('/libraries?kind=mine', headers=h(2)).json()['total'] == 0
    client.post(f'/libraries/{a}/join', headers=h(2), json={})
    assert client.get('/libraries?kind=mine', headers=h(2)).json()['total'] == 1
    assert client.get('/libraries?search=%5B').json()['total'] == 0


def test_public_join_idempotent_general_and_multi_library(client, register, h, database):
    a = register()['library']['library_id']; b = register(owner=3)['library']['library_id']
    for library_id in [a, a, b]:
        result = client.post(f'/libraries/{library_id}/join', headers=h(2, 'ADMIN'), json={})
        assert result.status_code == 200
        assert result.json()['membership']['role'] == 'GENERAL_USER'
    assert database.institution_memberships.count_documents({'user_id': 2}) == 2
    assert len(client.get('/me/libraries', headers=h(2)).json()['results']) == 2
    assert database.institution_audit.count_documents({'actor_user_id': 2, 'event': 'PUBLIC_LIBRARY_JOINED'}) == 2


@pytest.mark.parametrize('field', ['role', 'is_admin', 'is_owner', 'user_id', 'membership_status'])
def test_join_role_spoof_rejected(client, register, h, field):
    library_id = register()['library']['library_id']
    assert client.post(f'/libraries/{library_id}/join', headers=h(2), json={field: 'ADMIN'}).status_code == 422


@pytest.mark.parametrize('status', ['SUSPENDED', 'REMOVED'])
@pytest.mark.parametrize('private', [True, False])
def test_no_self_reactivation(client, register, h, database, status, private):
    library_id = register(private=private)['library']['library_id']
    body = {'access_code': 'Institution Test Passphrase'} if private else {}
    assert client.post(f'/libraries/{library_id}/join', headers=h(2), json=body).status_code == 200
    database.institution_memberships.update_one({'library_id': library_id, 'user_id': 2}, {'$set': {'status': status}})
    assert client.post(f'/libraries/{library_id}/join', headers=h(2), json=body).status_code == 403
    assert client.get(f'/libraries/{library_id}/context', headers=h(2)).status_code == 404


def test_private_code_case_sensitive_and_brute_force(client, register, h, database, caplog):
    library_id = register(private=True)['library']['library_id']
    for i in range(5):
        code = 'institution test passphrase' if i == 0 else 'wrong private secret'
        assert client.post(f'/libraries/{library_id}/join', headers=h(2), json={'access_code': code}).status_code == 403
    result = client.post(f'/libraries/{library_id}/join', headers=h(2), json={'access_code': 'Institution Test Passphrase'})
    assert result.status_code == 429 and result.headers.get('Retry-After')
    assert client.post(f'/libraries/{library_id}/join', headers=h(3), json={'access_code': 'Institution Test Passphrase'}).status_code == 200
    assert 'wrong private secret' not in caplog.text
    assert database.institution_audit.count_documents({'event': 'PRIVATE_LIBRARY_JOIN_FAILED'}) == 5


@pytest.mark.parametrize('role', ['ADMIN', 'LIBRARIAN'])
def test_staff_rotation_preserves_members_invalidates_old_code(client, register, invite, accept, h, database, role):
    library_id = register(private=True)['library']['library_id']
    accepted = accept(invite(library_id, role=role))
    result = client.put(f'/libraries/{library_id}/access-code', headers=h(2), json={'access_code': 'New Institution Passphrase'})
    assert result.status_code == 200 and result.json()['access_code_set']
    assert 'New Institution' not in result.text and 'argon2' not in result.text
    assert client.get(f'/libraries/{library_id}/context', headers=h(2)).status_code == 200
    assert client.post(f'/libraries/{library_id}/join', headers=h(3), json={'access_code': 'Institution Test Passphrase'}).status_code == 403
    assert client.post(f'/libraries/{library_id}/join', headers=h(3), json={'access_code': 'New Institution Passphrase'}).status_code == 200
    assert database.institution_audit.count_documents({'event': 'ACCESS_CODE_CHANGED'}) == 1
    assert accepted['membership']['role'] == role


def test_access_mode_conversion_preserves_existing_members(client, register, h, database):
    library_id = register()['library']['library_id']
    client.post(f'/libraries/{library_id}/join', headers=h(2), json={})
    assert client.put(f'/libraries/{library_id}/access', json={'access_mode': 'PRIVATE_CODE'}).status_code == 422
    assert client.put(f'/libraries/{library_id}/access', json={'access_mode': 'PRIVATE_CODE', 'access_code': 'New Private Code'}).status_code == 200
    assert client.get(f'/libraries/{library_id}/context', headers=h(2)).status_code == 200
    assert client.post(f'/libraries/{library_id}/join', headers=h(3), json={}).status_code == 403
    assert client.put(f'/libraries/{library_id}/access', json={'access_mode': 'PUBLIC'}).status_code == 200
    assert database.institution_security.find_one({'library_id': library_id})['access_code_hash'] is None
    assert client.post(f'/libraries/{library_id}/join', headers=h(3), json={}).status_code == 200


def test_cross_library_global_admin_and_private_resource_guards(client, register, h):
    a = register()['library']['library_id']; b = register(owner=3, private=True)['library']['library_id']
    for url in [f'/libraries/{b}/context', f'/libraries/{b}/access', f'/libraries/{b}/memberships', f'/libraries/{b}/invitations', f'/libraries/{b}/audit']:
        assert client.get(url, headers=h(1, 'ADMIN')).status_code == 404
    assert client.put(f'/libraries/{b}/access-code', headers=h(1, 'ADMIN'), json={'access_code': 'spoofed access code'}).status_code == 404
    require_library_membership(a, {'sub': '1'})
    with pytest.raises(HTTPException) as denied:
        require_library_membership(b, {'sub': '1', 'role': 'ADMIN', 'active_library_id': b})
    assert denied.value.status_code == 404


def test_general_user_denied_staff_operations(client, register, h):
    library_id = register(private=True)['library']['library_id']
    client.post(f'/libraries/{library_id}/join', headers=h(2), json={'access_code': 'Institution Test Passphrase'})
    for url in [f'/libraries/{library_id}/access', f'/libraries/{library_id}/memberships', f'/libraries/{library_id}/invitations', f'/libraries/{library_id}/audit']:
        assert client.get(url, headers=h(2)).status_code == 403
    assert client.put(f'/libraries/{library_id}/access-code', headers=h(2), json={'access_code': 'another secret'}).status_code == 403


def test_roles_differ_by_library_and_librarian_limits(client, register, invite, accept, h):
    a = register()['library']['library_id']; b = register(owner=3, private=True)['library']['library_id']
    client.post(f'/libraries/{a}/join', headers=h(2), json={})
    accept(invite(b, actor=3), 2)
    roles = {r['library_id']: r['membership']['role'] for r in client.get('/me/libraries', headers=h(2)).json()['results']}
    assert roles == {a: 'GENERAL_USER', b: 'LIBRARIAN'}
    assert client.post(f'/libraries/{b}/invitations', headers=h(2), json={'email': 'user4@example.com', 'role': 'LIBRARIAN'}).status_code == 403
    assert client.put(f'/libraries/{b}/access', headers=h(2), json={'access_mode': 'PUBLIC'}).status_code == 403
    assert client.put(f'/libraries/{a}/access-code', headers=h(2), json={'access_code': 'new secret code'}).status_code == 403


def test_admin_chaining_and_owner_protection(client, register, invite, accept, h, database):
    created = register(); library_id = created['library']['library_id']
    admin = accept(invite(library_id, role='ADMIN'))['membership']
    librarian = accept(invite(library_id, target=3, actor=2), 3)['membership']
    assert client.post(f'/libraries/{library_id}/invitations', headers=h(2), json={'email': 'user4@example.com', 'role': 'ADMIN'}).status_code == 403
    assert client.patch(f'/libraries/{library_id}/memberships/{librarian["membership_id"]}', headers=h(2), json={'role': 'ADMIN'}).status_code == 403
    for actor in [1, 2, 3]:
        for change in [{'role': 'GENERAL_USER'}, {'status': 'SUSPENDED'}, {'status': 'REMOVED'}]:
            assert client.patch(f'/libraries/{library_id}/memberships/{created["membership"]["membership_id"]}', headers=h(actor), json=change).status_code == 403
    assert client.patch(f'/libraries/{library_id}/memberships/{admin["membership_id"]}', headers=h(2), json={'role': 'LIBRARIAN'}).status_code == 403
    assert client.patch(f'/libraries/{library_id}/memberships/{admin["membership_id"]}', json={'role': 'LIBRARIAN'}).status_code == 200
    assert database.institution_memberships.count_documents({'library_id': library_id, 'role': 'ADMIN', 'status': 'ACTIVE'}) == 1


@pytest.mark.parametrize('role', ['ADMIN', 'LIBRARIAN'])
def test_invitation_secrets_identity_replay_and_pending(client, register, invite, accept, h, database, role):
    library_id = register()['library']['library_id']
    invitation = invite(library_id, role=role)
    row = database.institution_invitations.find_one({'invitation_id': invitation['invitation']['invitation_id']})
    assert row['token_hash'] != invitation['invite_token'] and len(row['token_hash']) == 64
    assert invitation['invite_token'] not in str(row)
    pending = client.get('/me/invitations', headers=h(2)); assert len(pending.json()['results']) == 1
    assert invitation['invite_token'] not in pending.text and 'token_hash' not in pending.text
    path = '/invitations/' + row['invitation_id'] + '/accept'
    assert client.post(path, headers=h(3), json={'token': invitation['invite_token']}).status_code == 404
    assert client.post(path, headers=h(2), json={'token': 'x' * 43}).status_code == 404
    accept(invitation)
    assert client.post(path, headers=h(2), json={}).status_code == 409
    assert 'token_hash' not in str(database.institution_invitations.find_one({'invitation_id': row['invitation_id']}))


def test_unknown_email_verified_new_account_and_normalization(client, register, invite, h, database):
    library_id = register()['library']['library_id']
    invitation = invite(library_id, email=' NewAccount@Example.com ')
    row = invitation['invitation']; assert row['email_normalized'] == 'newaccount@example.com'
    database.users.insert_one({'user_id': 50, 'email': 'newaccount@example.com', 'role': 'GENERAL_USER', 'is_email_verified': False, 'is_active': True})
    path = f'/invitations/{row["invitation_id"]}/accept'
    assert client.post(path, headers=h(50), json={'token': invitation['invite_token']}).status_code == 404
    database.users.update_one({'user_id': 50}, {'$set': {'is_email_verified': True}})
    assert client.post(path, headers=h(50), json={}).status_code == 403
    assert client.post(path, headers=h(50), json={'token': invitation['invite_token']}).status_code == 200


def test_invite_expiry_revocation_decline_reissue_and_cross_library(client, register, invite, accept, h, database):
    library_id = register()['library']['library_id']; other = register(owner=3)['library']['library_id']
    invitation = invite(library_id); invitation_id = invitation['invitation']['invitation_id']
    assert client.post(f'/libraries/{library_id}/invitations', json={'email': 'user2@example.com', 'role': 'ADMIN'}).status_code == 409
    assert client.post(f'/libraries/{other}/invitations/{invitation_id}/revoke', headers=h(3)).status_code == 404
    database.institution_invitations.update_one({'invitation_id': invitation_id}, {'$set': {'expires_at': now() - timedelta(seconds=1)}})
    assert client.post(f'/invitations/{invitation_id}/accept', headers=h(2), json={'token': invitation['invite_token']}).status_code == 410
    second = invite(library_id)
    second_id = second['invitation']['invitation_id']
    assert client.post(f'/libraries/{library_id}/invitations/{second_id}/revoke').status_code == 200
    assert client.post(f'/invitations/{second_id}/accept', headers=h(2), json={}).status_code == 409
    third = invite(library_id)
    assert client.post(f'/invitations/{third["invitation"]["invitation_id"]}/decline', headers=h(2), json={}).status_code == 200
    assert database.institution_memberships.count_documents({'library_id': library_id, 'user_id': 2}) == 0


@pytest.mark.parametrize('status', ['SUSPENDED', 'REMOVED'])
def test_staff_loses_authority_and_can_be_reactivated(client, register, invite, accept, h, status):
    library_id = register(private=True)['library']['library_id']
    member = accept(invite(library_id))['membership']
    endpoint = f'/libraries/{library_id}/memberships/{member["membership_id"]}'
    assert client.patch(endpoint, json={'status': status}).status_code == 200
    assert client.get(f'/libraries/{library_id}/access', headers=h(2)).status_code == 404
    assert client.put(f'/libraries/{library_id}/access-code', headers=h(2), json={'access_code': 'New Secret Code'}).status_code == 404
    assert client.patch(endpoint, json={'status': 'ACTIVE'}).status_code == 200
    assert client.get(f'/libraries/{library_id}/access', headers=h(2)).status_code == 200


def test_stale_inviter_cannot_grant_admin_or_manage_existing_admin(client, register, invite, accept, h):
    library_id = register()['library']['library_id']
    admin = accept(invite(library_id, role='ADMIN'))['membership']
    pending = invite(library_id, actor=2, target=3)
    client.patch(f'/libraries/{library_id}/memberships/{admin["membership_id"]}', json={'status': 'SUSPENDED'})
    assert client.post(f'/invitations/{pending["invitation"]["invitation_id"]}/accept', headers=h(3), json={}).status_code == 404
    owner_inv = invite(library_id, target=4, role='ADMIN'); accept(owner_inv, 4)
    client.patch(f'/libraries/{library_id}/memberships/{admin["membership_id"]}', json={'status': 'ACTIVE'})
    assert client.post(f'/libraries/{library_id}/invitations', headers=h(2), json={'email': 'user4@example.com', 'role': 'LIBRARIAN'}).status_code == 403


def test_concurrent_double_accept_and_duplicate_joins(client, register, invite, h, database):
    library_id = register()['library']['library_id']
    invitation = invite(library_id)
    path = f'/invitations/{invitation["invitation"]["invitation_id"]}/accept'
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda _: client.post(path, headers=h(2), json={}).status_code, range(20)))
    assert results.count(200) == 1 and set(results) <= {200, 409}
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda _: client.post(f'/libraries/{library_id}/join', headers=h(3), json={}).status_code, range(20)))
    assert 200 in results and set(results) <= {200, 503}
    assert client.post(f'/libraries/{library_id}/join', headers=h(3), json={}).status_code == 200
    assert database.institution_memberships.count_documents({'library_id': library_id, 'user_id': 3}) == 1


def test_concurrent_private_attempt_budget_and_20_user_context_isolation(client, register, h):
    library_id = register(private=True)['library']['library_id']
    with ThreadPoolExecutor(max_workers=20) as pool:
        responses = list(pool.map(lambda _: client.post(f'/libraries/{library_id}/join', headers=h(2), json={'access_code': 'wrong secret'}).status_code, range(20)))
    assert responses.count(403) == 5 and responses.count(429) == 15
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda i: (client.get('/libraries', headers=h(i)).status_code,
                                          client.get('/me/libraries', headers=h(i)).json()['results'],
                                          client.get(f'/libraries/{library_id}/context', headers=h(i)).status_code), range(1, 21)))
    assert all(r[0] == 200 for r in results)
    assert results[0][2] == 200 and all(r[2] == 404 for r in results[1:])
    assert all(not r[1] for r in results[1:])


def test_owner_last_admin_concurrent_protection(client, register, invite, accept, h, database):
    created = register(); library_id = created['library']['library_id']
    admin = accept(invite(library_id, role='ADMIN'))['membership']
    librarian = accept(invite(library_id, target=3), 3)['membership']
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda i: client.patch(f'/libraries/{library_id}/memberships/{created["membership"]["membership_id"]}', headers=h(2), json={'status': 'REMOVED'}).status_code, range(20)))
    assert set(results) == {403}
    database.institution_memberships.update_one({'library_id': library_id, 'user_id': 1}, {'$set': {'status': 'SUSPENDED'}})
    assert client.patch(f'/libraries/{library_id}/memberships/{librarian["membership_id"]}', headers=h(2), json={'role': 'GENERAL_USER'}).status_code == 409


def test_partial_grants_and_crashed_mutations_fail_closed(client, register, h, database):
    library_id = register()['library']['library_id']
    database.institution_memberships.insert_one({'membership_id': 'partial', 'library_id': library_id, 'user_id': 2, 'role': 'ADMIN', 'status': 'ACTIVE', 'grant_invitation_id': 'not-committed'})
    assert client.get(f'/libraries/{library_id}/context', headers=h(2)).status_code == 404
    with pytest.raises(RuntimeError):
        with library_mutation(library_id):
            raise RuntimeError('simulated worker failure')
    assert client.get(f'/libraries/{library_id}/context').status_code == 503
    assert database.institution_locks.count_documents({'_id': library_id}) == 1


def test_audit_whitelist_profile_and_no_secrets(client, register, invite, accept, database):
    library_id = register(private=True)['library']['library_id']; secret = invite(library_id); accept(secret)
    assert client.patch(f'/libraries/{library_id}', json={'name': 'Updated library', 'description': 'A description'}).status_code == 200
    assert client.put(f'/libraries/{library_id}/access-code', json={'access_code': 'CodeRotationSecret'}).status_code == 200
    text = client.get(f'/libraries/{library_id}/audit').text
    assert all(s not in text for s in ['Institution Test Passphrase', secret['invite_token'], 'CodeRotationSecret', 'token_hash', 'access_code_hash'])
    assert {'LIBRARY_REGISTERED', 'STAFF_INVITED', 'STAFF_INVITE_ACCEPTED', 'ACCESS_CODE_CHANGED', 'LIBRARY_PROFILE_UPDATED'} <= {r['event'] for r in database.institution_audit.find({})}
    assert client.delete(f'/libraries/{library_id}/audit').status_code == 405


def test_migration_dry_run_apply_idempotence_and_domain_preservation(database):
    database.users.update_one({'user_id': 1}, {'$set': {'role': 'ADMIN'}})
    database.users.update_one({'user_id': 2}, {'$set': {'role': 'LIBRARIAN'}})
    database.issues.insert_one({'issue_id': 1, 'user_id': 2})
    before = database.list_collection_names()
    proposed = plan(database, name='Legacy Library', slug='legacy-library', access_mode='public')
    assert database.institution_libraries.count_documents({}) == 0
    assert before == database.list_collection_names()
    assert proposed['owner_user_id'] == 1
    first = apply_plan(database, proposed)
    second = apply_plan(database, plan(database, name='Legacy Library', slug='legacy-library', access_mode='public'))
    assert first['memberships_created'] == 30 and second['memberships_created'] == 0
    assert database.institution_libraries.count_documents({}) == 1
    assert database.institution_memberships.count_documents({}) == 30
    assert database.institution_audit.count_documents({'event_id': 'migration:legacy-v1'}) == 1
    assert 'library_id' not in database.issues.find_one({'issue_id': 1})
    assert database.users.find_one({'user_id': 2})['role'] == 'LIBRARIAN'


def test_migration_safe_owner_selection_and_private_hash(database):
    with pytest.raises(ValueError): plan(database, name='Legacy', slug='legacy', access_mode='public')
    database.users.update_many({'user_id': {'$in': [1, 2]}}, {'$set': {'role': 'ADMIN'}})
    with pytest.raises(ValueError): plan(database, name='Legacy', slug='legacy', access_mode='public')
    proposed = plan(database, name='Legacy', slug='legacy', access_mode='private', owner_email=' USER2@EXAMPLE.COM ')
    apply_plan(database, proposed, 'Legacy Private Passphrase')
    encoded = database.institution_security.find_one({})['access_code_hash']
    assert encoded.startswith('$argon2id$') and verify_code(encoded, 'Legacy Private Passphrase')
    with pytest.raises(ValueError): plan(database, name='Legacy', slug='legacy', access_mode='public', owner_user_id=2)


def test_indexes_are_unique_and_idempotent(database):
    from backend.services.institution_repository import ensure_indexes
    before = {name: list(database[name].list_indexes()) for name in database.list_collection_names()}
    ensure_indexes()
    assert all(before[name] == list(database[name].list_indexes()) for name in before)
    assert any(i.get('unique') and dict(i['key']) == {'library_id': 1, 'user_id': 1} for i in database.institution_memberships.list_indexes())


@pytest.mark.parametrize('status', ['SUSPENDED', 'ARCHIVED'])
def test_inactive_library_denies_members_and_discovery(client, register, database, status):
    library_id = register()['library']['library_id']
    database.institution_libraries.update_one({'library_id': library_id}, {'$set': {'status': status}})
    assert client.get(f'/libraries/{library_id}/context').status_code == 404
    assert client.get('/libraries').json()['total'] == 0
    assert client.post(f'/libraries/{library_id}/join', json={}).status_code == 404


def test_real_jwt_identity_ignores_global_role_and_stale_library_role(client, register, database, invite, accept):
    from backend.main import app
    from backend.dependencies import get_current_user
    from backend.utils.jwt_utils import create_access_token
    library_id = register(owner=2)['library']['library_id']
    database.users.update_one({'user_id': 1}, {'$set': {'role': 'ADMIN'}})
    app.dependency_overrides.pop(get_current_user)
    outsider = {'Authorization': 'Bearer ' + create_access_token(1, 'user1@example.com', 'ADMIN')}
    owner = {'Authorization': 'Bearer ' + create_access_token(2, 'user2@example.com', 'GENERAL_USER')}
    assert client.get(f'/libraries/{library_id}/access', headers=outsider).status_code == 404
    assert client.get(f'/libraries/{library_id}/access', headers=owner).status_code == 200
    database.institution_memberships.update_one({'library_id': library_id, 'user_id': 2}, {'$set': {'status': 'SUSPENDED'}})
    assert client.get(f'/libraries/{library_id}/access', headers=owner).status_code == 404
    database.users.update_one({'user_id': 2}, {'$set': {'is_active': False}})
    assert client.get('/me/libraries', headers=owner).status_code == 401


def test_pagination_bounds_and_uuid_authorization(client):
    for path in ['/libraries?limit=1000', '/me/libraries?offset=-1', '/libraries/not-a-uuid/context']:
        assert client.get(path).status_code == 422


def test_access_code_long_unicode_is_not_bcrypt_truncated(client, database):
    phrase = '研究' * 64
    result = client.post('/libraries/register', json={'name': 'Research library', 'slug': 'unicode-library', 'library_type': 'PRIVATE_INSTITUTION', 'access_mode': 'PRIVATE_CODE', 'access_code': phrase})
    assert result.status_code == 201
    encoded = database.institution_security.find_one({})['access_code_hash']
    assert verify_code(encoded, phrase) and not verify_code(encoded, phrase[:-1] + '語')


def test_cross_library_membership_uuid_and_invitation_mass_assignment(client, register, h):
    a = register(); b = register(owner=2)
    assert client.patch(f'/libraries/{a["library"]["library_id"]}/memberships/{b["membership"]["membership_id"]}', json={'status': 'REMOVED'}).status_code == 404
    for extra in [{'is_owner': True}, {'invited_by_user_id': 2}, {'password': 'SuppliedPassword'}]:
        response = client.post(f'/libraries/{a["library"]["library_id"]}/invitations', json={'email': 'user3@example.com', 'role': 'LIBRARIAN', **extra})
        assert response.status_code == 422 and 'SuppliedPassword' not in response.text


def test_email_change_invalidates_existing_account_invitation(client, register, invite, h, database):
    library_id = register()['library']['library_id']; invitation = invite(library_id)
    database.users.update_one({'user_id': 2}, {'$set': {'email': 'changed@example.com'}})
    assert client.post(f'/invitations/{invitation["invitation"]["invitation_id"]}/accept', headers=h(2), json={}).status_code == 404
