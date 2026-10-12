from datetime import timedelta
from uuid import uuid4
import pytest
from backend.services import library_lending_journal as journal
from backend.services.library_lending_service import now
from tests.institution_v2b.test_lending import setup, cmd, request, review, avail, issued
from scripts.lending_v2b_operations import reconcile, recover, rollback


@pytest.mark.parametrize('action', ['approve', 'reject', 'cancel', 'return-create', 'return-confirm', 'return-reject', 'renew', 'stock', 'shelf'])
@pytest.mark.parametrize('partial', [False, True])
def test_each_transition_recovers_absolute_effects(client, setup, database, monkeypatch, action, partial):
    lib, book = setup; base = f'/libraries/{lib}'; request_id = None; loan = None
    if action in ['approve', 'reject', 'cancel']:
        # Use genuine copy allocations to exercise every copy hold conversion/release.
        for n in range(5):
            assert client.post(base + f'/inventory/books/{book}/copies', json=cmd(barcode=f'Copy {n}')).status_code == 201
        assert client.put(base + f'/staff/lending/books/{book}/stock', json=cmd(total_copies=5, allocation_mode='COPY')).status_code == 200
        request_id = request(client, lib, book).json()['lending_request_id']
    elif action.startswith('return') or action == 'renew':
        loan = issued(client, lib, book)
        if action in ['return-confirm', 'return-reject']:
            request_id = client.post(base + f'/loans/{loan["loan_id"]}/return-request', json=cmd(), headers={'x-test-user': '2'}).json()['lending_request_id']
    old = journal.replay; key = cmd()
    def fail(plan):
        if partial:
            step = plan['effects'][0]
            journal.durable(step['collection']).update_one(step['query'], {'$setOnInsert' if step['insert_only'] else '$set': step['values']}, upsert=step['insert_only'])
        raise OSError('Injected interruption')
    monkeypatch.setattr(journal, 'replay', fail)
    if action in ['approve', 'reject']:
        run = lambda: review(client, lib, request_id, action, key)
    elif action == 'cancel':
        run = lambda: client.post(base + f'/lending/borrow-requests/{request_id}/cancel', json=key, headers={'x-test-user': '2'})
    elif action == 'return-create':
        run = lambda: client.post(base + f'/loans/{loan["loan_id"]}/return-request', json=key, headers={'x-test-user': '2'})
    elif action in ['return-confirm', 'return-reject']:
        run = lambda: review(client, lib, request_id, 'confirm' if action.endswith('confirm') else 'reject', key, 'return')
    elif action == 'renew':
        key['expected_due_at'] = loan['due_at']
        run = lambda: client.post(base + f'/loans/{loan["loan_id"]}/renew', json=key, headers={'x-test-user': '2'})
    elif action == 'stock':
        key['total_copies'] = 8
        run = lambda: client.put(base + f'/staff/lending/books/{book}/stock', json=key)
    else:
        key['shelf_location'] = 'Recovered Shelf'
        run = lambda: client.put(base + f'/staff/lending/books/{book}/shelf', json=key)
    response = run(); assert response.status_code == 503, response.text
    assert database.institution_locks.find_one({'_id': lib})
    monkeypatch.setattr(journal, 'replay', old)
    assert recover(lib, apply=True, writers_stopped=True)['ok']
    assert run().is_success and reconcile(lib)['ok']
    unfinished = database.institution_lending_operations.count_documents({'library_id': lib, 'state': {'$ne': 'COMMITTED'}})
    assert unfinished == 0
    count = avail(client, lib, book)
    assert count['pending_holds'] + count['active_loans'] + count['physical_available'] + count['unavailable_stock'] == count['total']


def test_recovery_and_rollback_require_stopped_writers(client, setup):
    lib, book = setup
    with pytest.raises(ValueError): recover(lib, apply=True, writers_stopped=False)
    with pytest.raises(ValueError): rollback(lib, apply=True, writers_stopped=False)
    assert rollback(lib)['safe']
    assert rollback(lib, apply=True, writers_stopped=True)['applied']
    assert rollback(lib, apply=True, writers_stopped=True)['applied']
    result = client.post(f'/libraries/{lib}/staff/lending/activate', json=cmd()); assert result.status_code == 200, result.text
    assert request(client, lib, book).status_code == 201
    assert not rollback(lib)['safe']


def test_invalid_migration_preflight_does_not_block_a_healthy_library(client, setup, database):
    from scripts.migrate_lending_v2b import apply
    from fastapi import HTTPException
    lib, book = setup
    with pytest.raises(HTTPException) as error:
        apply(lib, 'unproven', writers_stopped=True, idempotency_key=str(uuid4()))
    assert error.value.status_code == 409
    assert not database.institution_locks.find_one({'_id': lib})
    assert avail(client, lib, book)['requestable'] == 5


def test_expiry_backlog_releases_bounded_batches_without_abandoning_gate(client, setup, database):
    lib, book = setup
    holding = database.institution_holdings.find_one({'library_id': lib})
    database.institution_holdings.update_one({'holding_id': holding['holding_id']}, {'$set': {'total_copies': 100}})
    database.institution_lending_requests.insert_many([{
        'lending_request_id': str(uuid4()), 'library_id': lib, 'library_book_id': book,
        'holding_id': holding['holding_id'], 'copy_id': None, 'user_id': user,
        'request_type': 'BORROW', 'status': 'PENDING', 'allocation_mode': 'AGGREGATE',
        'expires_at': now() - timedelta(seconds=1), 'requested_at': now(),
    } for user in range(40, 91)])
    path = f'/libraries/{lib}/inventory/{book}/availability'
    first = client.get(path)
    assert first.status_code == 503 and first.headers['Retry-After'] == '3'
    assert database.institution_lending_requests.count_documents({'status': 'EXPIRED'}) == 50
    assert not database.institution_locks.find_one({'_id': lib})
    assert client.get(path).json()['requestable'] == 100
    assert database.institution_lending_requests.count_documents({'status': 'EXPIRED'}) == 51
    assert reconcile(lib)['ok']


def test_pending_request_policy_is_bounded_and_enforced(client, setup, create, monkeypatch):
    lib, book = setup
    monkeypatch.setenv('LIBRARY_MAX_PENDING_REQUESTS', '1')
    monkeypatch.setenv('LIBRARY_BORROW_HOLD_HOURS', '2')
    pending = request(client, lib, book).json()
    from datetime import datetime
    assert datetime.fromisoformat(pending['expires_at']) - datetime.fromisoformat(pending['requested_at']) == timedelta(hours=2)
    other = create(lib, title='Second local title', idempotency_key=str(uuid4()))['library_book_id']
    assert request(client, lib, other).status_code == 409
    monkeypatch.setenv('LIBRARY_BORROW_HOLD_HOURS', '169')
    assert client.get(f'/libraries/{lib}/lending/config').status_code == 503
    monkeypatch.setenv('LIBRARY_BORROW_HOLD_HOURS', '24')
    monkeypatch.setenv('LIBRARY_MAX_PENDING_REQUESTS', '0')
    assert client.get(f'/libraries/{lib}/lending/config').status_code == 503


@pytest.mark.parametrize('status', ['SUSPENDED', 'REMOVED', 'DISABLED'])
def test_current_staff_authority_rechecked(client, setup, database, status):
    lib, book = setup; pending = request(client, lib, book).json()
    if status == 'DISABLED': database.users.update_one({'user_id': 1}, {'$set': {'is_active': False}})
    else: database.institution_memberships.update_one({'library_id': lib, 'user_id': 1}, {'$set': {'status': status}})
    assert review(client, lib, pending['lending_request_id']).status_code in [401, 404]
    assert database.institution_loans.count_documents({}) == 0


def test_librarian_can_issue_and_confirm_without_global_role(client, setup, database):
    lib, book = setup; database.institution_memberships.update_one({'library_id': lib, 'user_id': 10}, {'$set': {'role': 'LIBRARIAN'}})
    pending = request(client, lib, book).json(); loan = review(client, lib, pending['lending_request_id'], user=10).json()['loan']
    ret = client.post(f'/libraries/{lib}/loans/{loan["loan_id"]}/return-request', json=cmd(), headers={'x-test-user': '2'}).json()
    assert review(client, lib, ret['lending_request_id'], 'confirm', kind='return', user=10).status_code == 200


def test_member_privacy_and_queue_bounded_filters(client, setup):
    lib, book = setup; request(client, lib, book)
    row = client.get(f'/libraries/{lib}/inventory/{book}/availability', headers={'x-test-user': '3'}).json()
    assert not any(k in row for k in ['borrower', 'user_id', 'email', 'requests'])
    assert client.get(f'/libraries/{lib}/me/borrow-requests', headers={'x-test-user': '3'}).json()['results'] == []
    queue = client.get(f'/libraries/{lib}/staff/lending/borrow-requests?status=PENDING&user_id=2&search=AUR&limit=1').json()
    assert queue['total'] == 1 and len(queue['results']) == 1
    assert client.get(f'/libraries/{lib}/staff/lending/borrow-requests?limit=1000').status_code == 422


def test_known_copy_conditions_and_stock_floor(client, setup, database):
    lib, book = setup; base = f'/libraries/{lib}'
    copy = client.post(base + f'/inventory/books/{book}/copies', json=cmd(barcode='Known genuine copy')).json()
    assert client.put(base + f'/staff/lending/books/{book}/copies/{copy["copy_id"]}/condition', json=cmd(status='DAMAGED')).status_code == 200
    assert avail(client, lib, book)['requestable'] == 4
    assert client.put(base + f'/staff/lending/books/{book}/stock', json=cmd(total_copies=0)).status_code == 409
    assert client.put(base + f'/staff/lending/books/{book}/copies/{copy["copy_id"]}/condition', json=cmd(status='AVAILABLE')).status_code == 200
    assert avail(client, lib, book)['requestable'] == 5
    assert client.put(base + f'/staff/lending/books/{book}/stock', json=cmd(total_copies=5, allocation_mode='COPY')).status_code == 409


def test_snapshot_cannot_masquerade_as_copy_circulation(client, register, create, database):
    lib = register(); row = create(lib, copies=1)
    database.institution_copies.insert_one({'library_id': lib, 'library_book_id': row['library_book_id'], 'holding_id': row['holding']['holding_id'], 'copy_id': str(uuid4()), 'copy_number': 1, 'status': 'BORROWED'})
    assert client.post(f'/libraries/{lib}/staff/lending/activate', json=cmd()).status_code == 409
