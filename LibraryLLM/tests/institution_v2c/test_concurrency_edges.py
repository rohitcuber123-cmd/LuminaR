from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4
import pytest
from backend.services.institution_repository import now
from scripts.institution_v2c_operations import reconcile
from test_reservations_fees import setup, cmd, call, get, issue, reserve, receive, fee_fixture


def test_reservation_renewal_race_has_serialized_result(client, setup):
    lib, book = setup; loan = issue(client, lib, book)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(lambda: client.post(f'/libraries/{lib}/loans/{loan["loan_id"]}/renew', json=cmd(expected_due_at=loan['due_at']), headers={'x-test-user': '2'}))
        b = pool.submit(lambda: reserve(client, lib, book, 3))
        assert a.result().status_code in [200, 409]; b.result()
    row = get(client, lib, 'me/loans', 2)['results'][0]
    call(client, lib, f'loans/{loan["loan_id"]}/renew', 2, cmd(expected_due_at=row['due_at']), expected=409)
    assert reconcile(lib)['ok']


def test_return_confirmation_fee_generation_race_one_charge(client, setup, database):
    lib, book = setup; loan = issue(client, lib, book)
    database.institution_loans.update_one({'loan_id': loan['loan_id']}, {'$set': {'due_at': now() - timedelta(days=2)}})
    request = call(client, lib, f'loans/{loan["loan_id"]}/return-request', 2, cmd(), expected=201)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(lambda: call(client, lib, f'staff/lending/return-requests/{request["lending_request_id"]}/confirm', body=cmd()))
        b = pool.submit(lambda: client.post(f'/libraries/{lib}/staff/loans/{loan["loan_id"]}/fees/reconcile', json=cmd()))
        a.result(); assert b.result().status_code in [200, 409]
    assert database.institution_fees.count_documents({'loan_id': loan['loan_id']}) == 1
    assert reconcile(lib)['ok']


def test_adjustment_waiver_race_keeps_immutable_valid_balance(client, setup, database):
    lib, fee = fee_fixture(client, setup, database); base = f'/libraries/{lib}/staff/fees/{fee["fee_id"]}'
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(lambda: client.post(base + '/adjust', json=cmd(direction='CHARGE', amount_minor=100, reason='Approved adjustment')))
        b = pool.submit(lambda: client.post(base + '/waive', json=cmd(reason='Approved waiver')))
        assert a.result().status_code in [200, 409]; assert b.result().status_code == 200
    assert reconcile(lib)['ok'] and get(client, lib, f'staff/fees/{fee["fee_id"]}')['status'] == 'WAIVED'


def test_queue_head_request_limit_blocks_direct_bypass(client, setup, create, database):
    lib, book = setup; loan = issue(client, lib, book)
    for i in range(5):
        other = create(lib, copies=1, title=f'Pending {i}', idempotency_key=str(uuid4()))['library_book_id']
        call(client, lib, 'lending/borrow-requests', 3, cmd(library_book_id=other), expected=201)
    reserve(client, lib, book, 3); reserve(client, lib, book, 4); receive(client, lib, loan)
    counts = get(client, lib, f'inventory/{book}/availability')
    assert counts['physical_available'] == 1 and counts['requestable'] == 0 and counts['waiting_queue_has_priority']
    call(client, lib, 'lending/borrow-requests', 5, cmd(library_book_id=book), expected=409)
    pending = database.institution_lending_requests.find_one({'user_id': 3, 'status': 'PENDING'})
    call(client, lib, f'lending/borrow-requests/{pending["lending_request_id"]}/cancel', 3, cmd())
    assert get(client, lib, 'me/reservations', 3)['results'][0]['status'] == 'CONVERTED'


def test_overdue_disabled_future_policy_no_charge(client, setup, database):
    lib, book = setup; call(client, lib, 'settings/fee-policy', body=cmd(overdue_enabled=False))
    loan = issue(client, lib, book); database.institution_loans.update_one({'loan_id': loan['loan_id']}, {'$set': {'due_at': now() - timedelta(days=20)}})
    receive(client, lib, loan)
    assert database.institution_fees.count_documents({}) == 0


def test_reservation_receipt_retry_and_key_conflict(client, setup):
    lib, book = setup; issue(client, lib, book); key = cmd(library_book_id=book)
    assert reserve(client, lib, book, body=key) == reserve(client, lib, book, body=key)
    call(client, lib, 'reservations', 3, {**key, 'library_book_id': str(uuid4())}, expected=409)


def test_membership_removal_conversion_race_never_issues_removed_user(client, setup, database):
    lib, book = setup; issue(client, lib, book); a = reserve(client, lib, book, 3); reserve(client, lib, book, 4)
    member = database.institution_memberships.find_one({'library_id': lib, 'user_id': 3})
    with ThreadPoolExecutor(max_workers=2) as pool:
        x = pool.submit(lambda: client.patch(f'/libraries/{lib}/memberships/{member["membership_id"]}', json={'status': 'REMOVED'}))
        y = pool.submit(lambda: client.put(f'/libraries/{lib}/staff/lending/books/{book}/stock', json=cmd(total_copies=2)))
        assert x.result().status_code == 200; assert y.result().status_code == 200
    row = database.institution_reservations.find_one({'reservation_id': a['reservation_id']})
    if row['status'] == 'CONVERTED':
        assert call(client, lib, f'staff/lending/borrow-requests/{row["lending_request_id"]}/approve', body=cmd())['status'] == 'CANCELLED'
    assert database.institution_loans.count_documents({'user_id': 3}) == 0
    assert get(client, lib, 'me/reservations', 4)['results'][0]['status'] == 'CONVERTED'
    assert reconcile(lib)['ok']
