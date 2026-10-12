from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from backend.services.institution_repository import now
from scripts.institution_v2c_migration import plan, apply
from scripts.institution_v2c_operations import reconcile, rollback
from test_reservations_fees import cmd, call, get, issue, reserve, receive, fee_fixture, setup


def test_migration_dryrun_quarantine_order_idempotency(client, register, create, database):
    lib = register(); book = create(lib, copies=0, global_work_id='OL-Systems')['library_book_id']
    call(client, lib, 'staff/lending/activate', body=cmd())
    stamp = now()
    records = [{'reservation_id': i, 'library_id': 'OLD-A', 'user_id': i + 1, 'work_id': 'OL-Systems', 'status': 'ACTIVE', 'reserved_at': stamp + timedelta(seconds=i)} for i in [2, 1]]
    records += [{'reservation_id': 99, 'user_id': 2, 'work_id': 'OL-Systems', 'status': 'ACTIVE', 'reserved_at': stamp}]
    database.reservations.insert_many(records)
    assert len(plan(lib, 'OLD-A', 'reservations')['quarantine']) == 3
    database.institution_library_aliases.insert_one({'canonical_library_id': lib, 'legacy_library_id': 'OLD-A'})
    before = list(database.reservations.find({})); dry = plan(lib, 'OLD-A', 'reservations')
    assert dry['read_only'] and [r['legacy_reservation_id'] for r in dry['rows']] == [1, 2] and len(dry['quarantine']) == 1
    assert database.institution_reservations.count_documents({}) == 0
    key = str(uuid4()); result = apply(lib, 'OLD-A', 'reservations', writers_stopped=True, idempotency_key=key)
    assert apply(lib, 'OLD-A', 'reservations', writers_stopped=True, idempotency_key=key) == result
    assert len(plan(lib, 'OLD-A', 'reservations')['already_migrated']) == 2
    assert list(database.reservations.find({})) == before
    call(client, lib, 'staff/reservations-fees/activate', body=cmd())
    assert reconcile(lib)['ok']


def test_paid_fine_migration_preserves_history_missing_loan_quarantine(client, setup, database):
    lib, book = setup; loan = issue(client, lib, book)
    database.institution_loans.update_one({'loan_id': loan['loan_id']}, {'$set': {'legacy_issue_id': 42}})
    database.institution_library_aliases.insert_one({'canonical_library_id': lib, 'legacy_library_id': 'OLD-A'})
    database.fines.insert_many([{'fine_id': 7, 'user_id': 2, 'issue_id': 42, 'amount': 15, 'status': 'PAID', 'created_at': now(), 'paid_at': now()},
                               {'fine_id': 8, 'library_id': 'OLD-A', 'user_id': 2, 'issue_id': 999, 'amount': 5, 'status': 'UNPAID', 'created_at': now()}])
    before = list(database.fines.find({})); dry = plan(lib, 'OLD-A', 'fees')
    assert len(dry['rows']) == len(dry['quarantine']) == 1
    result = apply(lib, 'OLD-A', 'fees', writers_stopped=True, idempotency_key=str(uuid4()))
    fee = get(client, lib, 'me/fees', 2)['results'][0]
    assert fee['status'] == 'PAID' and fee['paid_amount_minor'] == 1500
    assert len(get(client, lib, f'me/fees/{fee["fee_id"]}', 2)['ledger']) == 2
    assert list(database.fines.find({})) == before and reconcile(lib)['ok']
    assert len(plan(lib, 'OLD-A', 'fees')['already_migrated']) == 1


def test_migration_quarantines_active_canonical_allocation(client, setup, database):
    lib, book = setup
    issue(client, lib, book)
    database.institution_library_books.update_one({'library_book_id': book}, {'$set': {'global_work_id': 'OL-Systems'}})
    database.institution_library_aliases.insert_one({'canonical_library_id': lib, 'legacy_library_id': 'OLD-A'})
    database.reservations.insert_one({'reservation_id': 20, 'library_id': 'OLD-A', 'user_id': 2,
        'work_id': 'OL-Systems', 'status': 'ACTIVE', 'reserved_at': now()})
    dry = plan(lib, 'OLD-A', 'reservations')
    assert not dry['rows'] and 'Active canonical loan/borrow hold' in dry['quarantine'][0]['reason']
    assert database.institution_reservations.count_documents({}) == 0


@pytest.mark.parametrize('damage', ['counter', 'policy', 'terminal_link', 'legacy_charge'])
def test_reconciliation_detects_corrupt_history_without_writes(client, setup, database, damage):
    lib, book = setup
    if damage == 'counter':
        issue(client, lib, book); reserve(client, lib, book)
        database.institution_reservation_counters.delete_many({'library_id': lib})
        expected = 'no persistent counter'
    elif damage == 'terminal_link':
        loan = issue(client, lib, book); row = reserve(client, lib, book)
        receive(client, lib, loan)
        converted = database.institution_reservations.find_one({'reservation_id': row['reservation_id']})
        call(client, lib, f'lending/borrow-requests/{converted["lending_request_id"]}/cancel', 3, cmd())
        database.institution_reservations.update_one({'reservation_id': row['reservation_id']}, {'$set': {'lending_request_id': str(uuid4())}})
        expected = 'exactly one matching borrow request'
    else:
        _, fee = fee_fixture(client, setup, database)
        if damage == 'policy':
            database.institution_fees.update_one({'fee_id': fee['fee_id']}, {'$set': {'policy_snapshot.rate_minor_per_day': 999}})
            expected = 'Fee policy snapshot'
        else:
            database.institution_loans.update_one({'loan_id': fee['loan_id']}, {'$set': {'legacy_issue_id': 77}})
            database.fines.insert_one({'fine_id': 77, 'issue_id': 77, 'user_id': 2, 'amount': 15, 'status': 'UNPAID'})
            expected = 'Legacy/canonical overdue charge mapping'
    before = {name: list(database[name].find({})) for name in database.list_collection_names()}
    report = reconcile(lib)
    assert not report['ok'] and any(expected in problem for problem in report['problems'])
    assert before == {name: list(database[name].find({})) for name in database.list_collection_names()}


def test_client_tenant_borrower_amount_policy_spoofing_rejected(client, setup, database):
    lib, book = setup
    for field in ['library_id', 'user_id', 'policy_version', 'amount_minor']:
        call(client, lib, 'reservations', 3, cmd(library_book_id=book, **{field: 99}), expected=422)
    _, fee = fee_fixture(client, setup, database)
    call(client, lib, f'staff/fees/{fee["fee_id"]}/payments', body=cmd(amount_minor=500, method='CASH', paid_amount_minor=1500), expected=422)
    call(client, lib, 'settings/fee-policy', body=cmd(version=99), expected=422)
    assert get(client, lib, f'staff/fees/{fee["fee_id"]}')['balance_minor'] == 1500


@pytest.mark.parametrize('loss', ['REMOVED', 'DEMOTED', 'DISABLED'])
def test_stale_staff_credentials_cannot_mutate_finances(client, setup, database, loss):
    lib, fee = fee_fixture(client, setup, database)
    database.institution_memberships.update_one({'library_id': lib, 'user_id': 3}, {'$set': {'role': 'LIBRARIAN'}})
    assert get(client, lib, 'staff/fees', 3)['total'] == 1
    if loss == 'DISABLED':
        database.users.update_one({'user_id': 3}, {'$set': {'is_active': False}})
        expected = 401
    else:
        database.institution_memberships.update_one({'library_id': lib, 'user_id': 3}, {'$set': {'status': 'REMOVED'} if loss == 'REMOVED' else {'role': 'GENERAL_USER'}})
        expected = 404 if loss == 'REMOVED' else 403
    call(client, lib, f'staff/fees/{fee["fee_id"]}/payments', 3, cmd(amount_minor=500, method='CASH'), expected=expected)
    assert database.institution_fee_ledger.count_documents({'fee_id': fee['fee_id']}) == 1


def test_active_canonical_cross_library_idor_and_unaffiliated_global_admin(client, setup, register, create, database):
    lib, book = setup; loan = issue(client, lib, book); row = reserve(client, lib, book)
    other = register(owner=30, private=True, name='Orion Private')
    call(client, other, 'staff/lending/activate', 30, cmd())
    call(client, other, 'staff/reservations-fees/activate', 30, cmd())
    call(client, other, 'reservations', 30, cmd(library_book_id=book), expected=403)
    joined = client.post(f'/libraries/{other}/join', headers={'x-test-user': '29'}, json={'access_code': 'Private V2C Passphrase'})
    assert joined.status_code == 200, joined.text
    call(client, other, 'reservations', 29, cmd(library_book_id=book), expected=404)
    call(client, other, f'reservations/{row["reservation_id"]}/cancel', 29, cmd(), expected=404)
    database.institution_loans.update_one({'loan_id': loan['loan_id']}, {'$set': {'due_at': now() - timedelta(days=2)}})
    receive(client, lib, loan)
    fee = get(client, lib, 'staff/fees')['results'][0]
    call(client, other, f'staff/fees/{fee["fee_id"]}', 30, method='GET', expected=404)
    call(client, other, f'staff/fees/{fee["fee_id"]}/payments', 30, cmd(amount_minor=1, method='CASH'), expected=404)
    database.users.insert_one({'user_id': 31, 'email': 'global-admin@example.com', 'name': 'Global Admin', 'role': 'ADMIN', 'is_active': True, 'is_email_verified': True})
    for path in ['me/reservations', 'me/fees', 'staff/reservations', 'staff/fees']:
        call(client, lib, path, 31, method='GET', expected=404)


def test_canonical_legacy_reservation_and_payment_bypass_denied(client, setup, database):
    lib, book = setup
    response = client.post('/reservations/', headers={'x-test-user': '2'}, json={'work_id': 'OL-Systems'})
    assert response.status_code == 410, response.text
    lib, fee = fee_fixture(client, setup, database)
    database.fines.insert_one({'fine_id': 55, 'user_id': 2, 'issue_id': 55, 'amount': 15, 'status': 'UNPAID'})
    database.institution_fees.update_one({'fee_id': fee['fee_id']}, {'$set': {'legacy_fine_id': 55}})
    response = client.post('/fines/pay/55', headers={'x-test-user': '2'})
    assert response.status_code == 410
    assert database.fines.find_one({'fine_id': 55})['status'] == 'UNPAID'


@pytest.mark.parametrize('action', ['waive', 'adjust'])
def test_payment_race_with_waive_adjust_balances_valid(client, setup, database, action):
    lib, fee = fee_fixture(client, setup, database); path = f'staff/fees/{fee["fee_id"]}'
    body = cmd(reason='Policy exception', **({'direction': 'CREDIT', 'amount_minor': 1500} if action == 'adjust' else {}))
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(lambda: client.post(f'/libraries/{lib}/{path}/{action}', json=body))
        b = pool.submit(lambda: client.post(f'/libraries/{lib}/{path}/payments', json=cmd(amount_minor=500, method='CASH')))
        assert a.result().status_code in [200, 409] and b.result().status_code in [200, 409]
    assert reconcile(lib)['ok']
    row = get(client, lib, path)
    assert row['balance_minor'] >= 0 and row['paid_amount_minor'] <= row['current_amount_minor']


def test_same_library_renewal_waiting_blocks_cross_library_does_not(client, setup, register, create):
    lib, book = setup; loan = issue(client, lib, book); a = reserve(client, lib, book)
    call(client, lib, f'loans/{loan["loan_id"]}/renew', 2, cmd(expected_due_at=loan['due_at']), expected=409)
    call(client, lib, f'reservations/{a["reservation_id"]}/cancel', 3, cmd())
    other = register(owner=3, name='Orion'); other_book = create(other, actor=3, copies=0)['library_book_id']
    call(client, other, 'staff/lending/activate', 3, cmd()); call(client, other, 'staff/reservations-fees/activate', 3, cmd())
    joined = client.post(f'/libraries/{other}/join', headers={'x-test-user': '4'}, json={})
    assert joined.status_code == 200, joined.text
    reserve(client, other, other_book, 4)
    assert call(client, lib, f'loans/{loan["loan_id"]}/renew', 2, cmd(expected_due_at=loan['due_at']))['renewal_count'] == 1


def test_grace_disabled_estimate_and_waiting_expiry(client, setup, database):
    lib, book = setup; call(client, lib, 'settings/fee-policy', body=cmd(grace_days=2))
    loan = issue(client, lib, book); a = reserve(client, lib, book); b = reserve(client, lib, book, 4)
    database.institution_reservations.update_one({'reservation_id': a['reservation_id']}, {'$set': {'expires_at': now() - timedelta(days=1)}})
    assert get(client, lib, 'me/reservations', 4)['results'][0]['queue_position'] == 1
    database.institution_loans.update_one({'loan_id': loan['loan_id']}, {'$set': {'due_at': now() - timedelta(days=3)}})
    estimate = get(client, lib, 'me/fees', 2)['estimates'][0]
    assert estimate['kind'] == 'ESTIMATED' and estimate['amount_minor'] == 500
    assert database.institution_fees.count_documents({}) == 0
    receive(client, lib, loan)
    assert get(client, lib, 'me/fees', 2)['results'][0]['original_amount_minor'] == 500
    assert rollback(lib)['safe'] is False


def test_reservation_limit_per_library_and_idempotency_key_conflict(client, setup, create):
    lib, book = setup
    for i in range(5):
        identity = book if i == 0 else create(lib, copies=0, title=f'Unavailable {i}', idempotency_key=str(uuid4()))['library_book_id']
        if i == 0: issue(client, lib, book)
        reserve(client, lib, identity)
    sixth = create(lib, copies=0, idempotency_key=str(uuid4()))['library_book_id']
    call(client, lib, 'reservations', 3, cmd(library_book_id=sixth), expected=409)


def test_copy_mode_restoration_converts_real_copy(client, register, create, database):
    lib = register(); book = create(lib, copies=1)['library_book_id']; call(client, lib, 'join', 2, {})
    # Register the physical identity before canonical activation.
    response = call(client, lib, f'inventory/books/{book}/copies', body={'barcode': '2C-COPY-1'}, expected=201)
    copy = response['copy_id']
    call(client, lib, 'staff/lending/activate', body=cmd()); call(client, lib, 'staff/reservations-fees/activate', body=cmd())
    call(client, lib, f'staff/lending/books/{book}/stock', body=cmd(total_copies=1, allocation_mode='COPY'), method='PUT')
    call(client, lib, f'staff/lending/books/{book}/copies/{copy}/condition', body=cmd(status='DAMAGED'), method='PUT')
    reserve(client, lib, book, 2)
    call(client, lib, f'staff/lending/books/{book}/copies/{copy}/condition', body=cmd(status='AVAILABLE'), method='PUT')
    row = get(client, lib, 'me/reservations', 2)['results'][0]
    request = database.institution_lending_requests.find_one({'lending_request_id': row['lending_request_id']})
    assert request['copy_id'] == copy
    assert database.institution_copies.find_one({'copy_id': copy})['status'] == 'HELD_FOR_REQUEST'
