from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4
import pytest
from backend.services.institution_repository import now
from backend.services import library_lending_journal as journal


def cmd(**fields):
    return {'idempotency_key': str(uuid4()), **fields}


@pytest.fixture
def setup(client, register, create, database, h):
    lib = register(); book = create(lib, copies=5, shelf_location='B-12')
    for user in range(2, 31):
        response = client.post(f'/libraries/{lib}/join', json={}, headers=h(user))
        assert response.status_code == 200, response.text
    response = client.post(f'/libraries/{lib}/staff/lending/activate', json=cmd())
    assert response.status_code == 200, response.text
    return lib, book['library_book_id']


def request(client, lib, book, user=2, body=None):
    return client.post(f'/libraries/{lib}/lending/borrow-requests', json=body or cmd(library_book_id=book), headers={'x-test-user': str(user)})


def review(client, lib, rid, action='approve', body=None, kind='borrow', user=1):
    return client.post(f'/libraries/{lib}/staff/lending/{kind}-requests/{rid}/{action}', json=body or cmd(), headers={'x-test-user': str(user)})


def avail(client, lib, book):
    r = client.get(f'/libraries/{lib}/inventory/{book}/availability'); assert r.status_code == 200, r.text
    return r.json()


def issued(client, lib, book):
    r = request(client, lib, book); assert r.status_code == 201, r.text
    a = review(client, lib, r.json()['lending_request_id']); assert a.status_code == 200, a.text
    return a.json()['loan']


def test_pending_hold_then_issue_does_not_decrement_twice(client, setup, database):
    lib, book = setup; body = cmd(library_book_id=book)
    pending = request(client, lib, book, body=body).json()
    assert pending['status'] == 'PENDING' and pending['loan_id'] is None and 'due_at' not in pending
    assert database.institution_loans.count_documents({}) == 0
    assert avail(client, lib, book)['requestable'] == 4
    assert request(client, lib, book, body=body).json()['lending_request_id'] == pending['lending_request_id']
    assert request(client, lib, book).status_code == 409
    key = cmd(); approved = review(client, lib, pending['lending_request_id'], body=key).json()
    assert approved['loan']['status'] == 'ACTIVE'
    assert avail(client, lib, book)['requestable'] == 4
    assert review(client, lib, pending['lending_request_id'], body=key).json()['loan_id'] == approved['loan_id']
    assert request(client, lib, book).status_code == 409
    assert database.institution_loans.count_documents({}) == 1


def test_lending_receipts_and_lists_keep_explicit_utc_timezone(client, setup):
    from datetime import datetime, timezone
    lib, book = setup
    pending = request(client, lib, book).json()
    assert datetime.fromisoformat(pending['requested_at']).utcoffset() == timedelta(0)
    assert datetime.fromisoformat(pending['expires_at']).utcoffset() == timedelta(0)
    key = cmd()
    result = review(client, lib, pending['lending_request_id'], body=key).json()
    assert review(client, lib, pending['lending_request_id'], body=key).json() == result
    loan = result['loan']
    listed = client.get(f'/libraries/{lib}/me/loans', headers={'x-test-user': '2'}).json()['results'][0]
    assert listed['due_at'] == loan['due_at']
    assert datetime.fromisoformat(loan['borrowed_at']).tzinfo == timezone.utc
    assert datetime.fromisoformat(loan['due_at']) - datetime.fromisoformat(loan['borrowed_at']) == timedelta(days=14)


@pytest.mark.parametrize('action', ['cancel', 'reject', 'expire'])
def test_releases_once(client, setup, database, action):
    lib, book = setup; pending = request(client, lib, book).json(); rid = pending['lending_request_id']; key = cmd(reason='Changed plans') if action == 'reject' else cmd()
    if action == 'cancel':
        path = f'/libraries/{lib}/lending/borrow-requests/{rid}/cancel'; r = client.post(path, json=key, headers={'x-test-user': '2'})
        assert r.status_code == 200; assert client.post(path, json=key, headers={'x-test-user': '2'}).status_code == 200
    elif action == 'reject':
        assert review(client, lib, rid, action, key).json()['rejection_reason'] == 'Changed plans'
        assert review(client, lib, rid, action, key).status_code == 200
    else:
        database.institution_lending_requests.update_one({'lending_request_id': rid}, {'$set': {'expires_at': now() - timedelta(seconds=1)}})
    assert avail(client, lib, book)['requestable'] == 5
    assert avail(client, lib, book)['requestable'] == 5
    assert review(client, lib, rid).status_code == 409


def test_twenty_requests_last_five_units(client, setup, database):
    lib, book = setup
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda u: request(client, lib, book, u), range(2, 22)))
    assert sum(r.status_code == 201 for r in results) == 5
    assert sum(r.status_code == 409 for r in results) == 15
    assert avail(client, lib, book)['requestable'] == 0
    assert database.institution_lending_requests.count_documents({'status': 'PENDING'}) == 5


def test_return_request_remains_active_reject_re_request_confirm(client, setup, database):
    lib, book = setup; loan = issued(client, lib, book); path = f'/libraries/{lib}/loans/{loan["loan_id"]}/return-request'
    body = cmd(); pending = client.post(path, json=body, headers={'x-test-user': '2'}).json()
    assert client.post(path, json=body, headers={'x-test-user': '2'}).json()['lending_request_id'] == pending['lending_request_id']
    assert client.post(path, json=cmd(), headers={'x-test-user': '2'}).status_code == 409
    current = client.get(f'/libraries/{lib}/me/loans', headers={'x-test-user': '2'}).json()['results'][0]
    assert current['status'] == 'ACTIVE' and current['return_requested_at'] and current['returned_at'] is None
    assert avail(client, lib, book)['requestable'] == 4
    assert client.post(f'/libraries/{lib}/loans/{loan["loan_id"]}/renew', json=cmd(expected_due_at=loan['due_at']), headers={'x-test-user': '2'}).status_code == 409
    assert review(client, lib, pending['lending_request_id'], 'reject', kind='return').status_code == 200
    assert avail(client, lib, book)['requestable'] == 4
    pending = client.post(path, json=cmd(), headers={'x-test-user': '2'}).json()
    # Removed borrowers must still be able to have physical returns confirmed by staff.
    database.institution_memberships.update_one({'library_id': lib, 'user_id': 2}, {'$set': {'status': 'REMOVED'}})
    key = cmd(); result = review(client, lib, pending['lending_request_id'], 'confirm', key, 'return')
    assert result.status_code == 200, result.text
    assert result.json()['loan']['status'] == 'RETURNED'
    assert review(client, lib, pending['lending_request_id'], 'confirm', key, 'return').status_code == 200
    assert avail(client, lib, book)['requestable'] == 5


@pytest.mark.parametrize('change', ['REMOVED', 'SUSPENDED', 'ACCOUNT_DISABLED'])
def test_borrower_revalidated_and_hold_released(client, setup, database, change):
    lib, book = setup; pending = request(client, lib, book).json()
    if change == 'ACCOUNT_DISABLED':
        database.users.update_one({'user_id': 2}, {'$set': {'is_active': False}})
    else:
        database.institution_memberships.update_one({'library_id': lib, 'user_id': 2}, {'$set': {'status': change}})
    result = review(client, lib, pending['lending_request_id']); assert result.status_code == 200, result.text
    assert result.json()['status'] == 'CANCELLED' and database.institution_loans.count_documents({}) == 0
    assert avail(client, lib, book)['requestable'] == 5


def test_staff_membership_recheck_global_role_spoof_and_idor(client, setup, register, h, database):
    lib, book = setup; other = register(owner=30, name='Orion Library'); pending = request(client, lib, book).json(); rid = pending['lending_request_id']
    for user in [2, 29, 30]:
        assert review(client, lib, rid, user=user).status_code in [403, 404]
    assert client.post(f'/libraries/{lib}/staff/lending/borrow-requests/{rid}/approve', json=cmd(), headers=h(2, 'ADMIN')).status_code == 403
    assert client.post(f'/libraries/{lib}/lending/borrow-requests/{rid}/cancel', json=cmd(), headers=h(3)).status_code == 404
    assert review(client, other, rid).status_code == 404
    assert client.get(f'/libraries/{lib}/staff/lending/borrow-requests', headers=h(2)).status_code == 403
    loan = review(client, lib, rid).json()['loan']
    assert client.post(f'/libraries/{lib}/loans/{loan["loan_id"]}/return-request', json=cmd(), headers=h(3)).status_code == 404
    ret = client.post(f'/libraries/{lib}/loans/{loan["loan_id"]}/return-request', json=cmd(), headers=h(2)).json()
    assert review(client, lib, ret['lending_request_id'], 'confirm', kind='return', user=2).status_code == 403


def test_stock_shelf_status_and_copy_mode(client, setup, database):
    lib, book = setup; path = f'/libraries/{lib}/staff/lending/books/{book}'
    assert client.put(path + '/stock', json=cmd(total_copies=6)).status_code == 200
    assert avail(client, lib, book)['requestable'] == 6
    pending = request(client, lib, book).json()
    assert client.put(path + '/stock', json=cmd(total_copies=0)).status_code == 409
    assert client.put(f'/libraries/{lib}/inventory/books/{book}/holding', json={'total_copies': 999, 'available_copies': 999}).status_code == 409
    assert client.put(path + '/stock', json=cmd(total_copies=6, circulation_status='REFERENCE_ONLY')).status_code == 200
    assert request(client, lib, book, 3).status_code == 409
    assert review(client, lib, pending['lending_request_id']).json()['status'] == 'REJECTED'
    assert client.put(path + '/shelf', json=cmd(shelf_location='Room 7 / Shelf C', call_number='004.5')).status_code == 200
    assert avail(client, lib, book)['shelf_location'] == 'Room 7 / Shelf C'
    for n in range(6):
        assert client.post(f'/libraries/{lib}/inventory/books/{book}/copies', json=cmd(barcode=f'C{n}')).status_code == 201
    assert client.put(path + '/stock', json=cmd(total_copies=6, allocation_mode='COPY')).status_code == 200
    pending = request(client, lib, book).json(); copy_id = pending['copy_id']; assert copy_id
    assert database.institution_copies.find_one({'copy_id': copy_id})['status'] == 'HELD_FOR_REQUEST'
    assert client.put(path + f'/copies/{copy_id}/condition', json=cmd(status='AVAILABLE')).status_code == 409
    loan = review(client, lib, pending['lending_request_id']).json()['loan']
    assert loan['copy_id'] == copy_id and database.institution_copies.find_one({'copy_id': copy_id})['status'] == 'BORROWED'
    ret = client.post(f'/libraries/{lib}/loans/{loan["loan_id"]}/return-request', json=cmd(), headers={'x-test-user': '2'}).json()
    assert database.institution_copies.find_one({'copy_id': copy_id})['status'] == 'BORROWED'
    assert review(client, lib, ret['lending_request_id'], 'confirm', kind='return').status_code == 200
    assert database.institution_copies.find_one({'copy_id': copy_id})['status'] == 'AVAILABLE'


@pytest.mark.parametrize('stage', ['after_plan', 'after_effect', 'after_commit'])
def test_unknown_commit_recovery_replays_exactly_once(client, setup, database, monkeypatch, stage):
    lib, book = setup; original = journal.replay
    def fault(plan):
        if stage == 'after_effect':
            first = plan['effects'][0]; database['institution_' + first['collection']].update_one(first['query'], {'$setOnInsert': first['values']}, upsert=True)
        if stage == 'after_commit':
            original(plan)
        raise OSError('Injected lost acknowledgement')
    monkeypatch.setattr(journal, 'replay', fault)
    body = cmd(library_book_id=book); r = request(client, lib, book, body=body)
    assert r.status_code == 503 and 'RECOVERY_REQUIRED' in r.text
    assert database.institution_locks.count_documents({'_id': lib}) == 1
    assert database.institution_lending_config.find_one({'library_id': lib})['state'] == 'RECOVERY_REQUIRED'
    monkeypatch.setattr(journal, 'replay', original)
    from scripts.lending_v2b_operations import recover
    report = recover(lib, apply=True, writers_stopped=True)
    assert report['ok'], report
    assert request(client, lib, book, body=body).status_code == 201
    assert avail(client, lib, book)['requestable'] == 4
    assert database.institution_lending_requests.count_documents({}) == 1
    assert database.institution_audit.count_documents({'library_id': lib, 'event': 'BORROW_REQUEST_CREATED'}) == 1


def test_renewal_proven_tenant_reservations_only(client, setup, database):
    lib, book = setup; database.institution_library_books.update_one({'library_book_id': book}, {'$set': {'global_work_id': 'OL-Networks'}})
    loan = issued(client, lib, book)
    for tenant in [None, str(uuid4())]:
        database.reservations.insert_one({'work_id': 'OL-Networks', 'library_id': tenant, 'user_id': 3, 'status': 'ACTIVE'})
    path = f'/libraries/{lib}/loans/{loan["loan_id"]}/renew'; body = cmd(expected_due_at=loan['due_at'])
    r = client.post(path, json=body, headers={'x-test-user': '2'}); assert r.status_code == 200, r.text
    assert client.post(path, json=body, headers={'x-test-user': '2'}).json()['renewal_count'] == 1
    assert client.post(path, json=cmd(expected_due_at=r.json()['due_at']), headers={'x-test-user': '2'}).status_code == 409


def test_same_library_reservation_blocks_renewal(client, setup, database):
    lib, book = setup; database.institution_library_books.update_one({'library_book_id': book}, {'$set': {'global_work_id': 'OL-Networks'}})
    loan = issued(client, lib, book); database.reservations.insert_one({'library_id': lib, 'work_id': 'OL-Networks', 'user_id': 3, 'status': 'ACTIVE'})
    assert client.post(f'/libraries/{lib}/loans/{loan["loan_id"]}/renew', json=cmd(expected_due_at=loan['due_at']), headers={'x-test-user': '2'}).status_code == 409


@pytest.mark.parametrize('action', ['approve', 'reject', 'cancel', 'expiry'])
def test_terminal_request_races(client, setup, database, action):
    lib, book = setup; pending = request(client, lib, book).json(); rid = pending['lending_request_id']
    def contender(n):
        if action == 'cancel' and n % 2:
            return client.post(f'/libraries/{lib}/lending/borrow-requests/{rid}/cancel', json=cmd(), headers={'x-test-user': '2'})
        if action == 'expiry' and n % 2:
            return client.get(f'/libraries/{lib}/inventory/{book}/availability')
        return review(client, lib, rid, 'reject' if action == 'reject' and n % 2 else 'approve')
    if action == 'expiry':
        database.institution_lending_requests.update_one({'lending_request_id': rid}, {'$set': {'expires_at': now() - timedelta(seconds=1)}})
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(contender, range(5)))
    assert all(r.status_code in [200, 409] for r in results)
    state = database.institution_lending_requests.find_one({'lending_request_id': rid})['status']
    assert state in ['APPROVED', 'REJECTED', 'CANCELLED', 'EXPIRED']
    loans = database.institution_loans.count_documents({'status': 'ACTIVE'})
    assert loans == int(state == 'APPROVED') and avail(client, lib, book)['requestable'] == 5 - loans


def test_idempotency_payload_conflict_and_strict_fields(client, setup):
    lib, book = setup; body = cmd(library_book_id=book); assert request(client, lib, book, body=body).status_code == 201
    assert request(client, lib, str(uuid4()), body={**body, 'library_book_id': str(uuid4())}).status_code == 409
    for field in ['user_id', 'library_id', 'role', 'loan_id']:
        assert request(client, lib, book, body=cmd(library_book_id=book, **{field: 'spoof'})).status_code == 422
    assert request(client, lib, book, body={'library_book_id': book}).status_code == 422
