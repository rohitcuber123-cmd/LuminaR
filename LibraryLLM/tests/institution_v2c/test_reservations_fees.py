from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4
import pytest
from backend.services.institution_repository import now
from backend.services import library_lending_journal as journal


def cmd(**fields):
    return {'idempotency_key': str(uuid4()), **fields}


def call(client, lib, path, user=1, body=None, method='POST', expected=200):
    r = client.request(method, f'/libraries/{lib}/{path}', headers={'x-test-user': str(user)}, json=body)
    assert r.status_code == expected, r.text
    return r.json()


@pytest.fixture
def setup(client, register, create, h):
    lib = register(); book = create(lib, copies=1)['library_book_id']
    for user in range(2, 31):
        call(client, lib, 'join', user, {})
    call(client, lib, 'staff/lending/activate', body=cmd())
    call(client, lib, 'staff/reservations-fees/activate', body=cmd())
    return lib, book


def borrow(client, lib, book, user=2):
    return call(client, lib, 'lending/borrow-requests', user, cmd(library_book_id=book), expected=201)


def issue(client, lib, book, user=2):
    request = borrow(client, lib, book, user)
    return call(client, lib, f'staff/lending/borrow-requests/{request["lending_request_id"]}/approve', body=cmd())['loan']


def reserve(client, lib, book, user=3, body=None):
    return call(client, lib, 'reservations', user, body or cmd(library_book_id=book), expected=201)


def receive(client, lib, loan, user=2):
    request = call(client, lib, f'loans/{loan["loan_id"]}/return-request', user, cmd(), expected=201)
    return call(client, lib, f'staff/lending/return-requests/{request["lending_request_id"]}/confirm', body=cmd())


def get(client, lib, path, user=1):
    return call(client, lib, path, user, method='GET')


def fee_fixture(client, setup, database):
    lib, book = setup; loan = issue(client, lib, book)
    database.institution_loans.update_one({'loan_id': loan['loan_id']}, {'$set': {'due_at': now() - timedelta(days=3)}})
    receive(client, lib, loan)
    return lib, get(client, lib, 'staff/fees')['results'][0]


def test_fifo_waiting_no_hold_conversion_return_atomic(client, setup, database):
    lib, book = setup; loan = issue(client, lib, book)
    a = reserve(client, lib, book); b = reserve(client, lib, book, 4)
    assert (a['queue_sequence'], b['queue_sequence']) == (1, 2)
    assert get(client, lib, 'me/reservations', 3)['results'][0]['queue_position'] == 1
    assert get(client, lib, 'me/reservations', 4)['results'][0]['queue_position'] == 2
    assert get(client, lib, f'inventory/{book}/availability')['pending_holds'] == 0
    result = receive(client, lib, loan)
    a = get(client, lib, 'me/reservations', 3)['results'][0]
    assert a['status'] == 'CONVERTED' and a['lending_request_id']
    assert get(client, lib, 'me/reservations', 4)['results'][0]['status'] == 'WAITING'
    assert get(client, lib, f'inventory/{book}/availability')['pending_holds'] == 1
    plan = database.institution_lending_operations.find_one({'operation_id': result['operation_id']})
    assert {'loans', 'reservations', 'lending_requests'}.issubset({e['collection'] for e in plan['effects']})
    call(client, lib, f'staff/lending/borrow-requests/{a["lending_request_id"]}/approve', body=cmd())
    assert get(client, lib, 'me/reservations', 3)['results'][0]['status'] == 'FULFILLED'


@pytest.mark.parametrize('action', ['cancel', 'reject', 'expiry'])
def test_converted_terminal_releases_to_next_once(client, setup, database, action):
    lib, book = setup; loan = issue(client, lib, book)
    a = reserve(client, lib, book); b = reserve(client, lib, book, 4); receive(client, lib, loan)
    a = get(client, lib, 'me/reservations', 3)['results'][0]; rid = a['lending_request_id']
    call(client, lib, f'reservations/{a["reservation_id"]}/cancel', 3, cmd(), expected=409)
    if action == 'expiry':
        database.institution_lending_requests.update_one({'lending_request_id': rid}, {'$set': {'expires_at': now() - timedelta(seconds=1)}})
        get(client, lib, f'inventory/{book}/availability')
    else:
        path = f'lending/borrow-requests/{rid}/cancel' if action == 'cancel' else f'staff/lending/borrow-requests/{rid}/reject'
        call(client, lib, path, 3 if action == 'cancel' else 1, cmd())
    assert get(client, lib, 'me/reservations', 4)['results'][0]['status'] == 'CONVERTED'
    assert database.institution_lending_requests.count_documents({'reservation_id': b['reservation_id']}) == 1
    assert get(client, lib, f'inventory/{book}/availability')['pending_holds'] == 1


def test_concurrent_sequence_duplicate_and_cancel_head(client, setup, database):
    lib, book = setup; issue(client, lib, book)
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda u: reserve(client, lib, book, u), range(3, 15)))
    assert sorted(r['queue_sequence'] for r in results) == list(range(1, 13))
    first = next(r for r in results if r['queue_sequence'] == 1)
    key = cmd(); path = f'reservations/{first["reservation_id"]}/cancel'
    assert call(client, lib, path, first['user_id'], key) == call(client, lib, path, first['user_id'], key)
    assert get(client, lib, 'staff/reservations')['results'][1]['queue_position'] == 1
    reserve(client, lib, book, first['user_id'])
    call(client, lib, 'reservations', first['user_id'], cmd(library_book_id=book), expected=409)


@pytest.mark.parametrize('change', ['REMOVED', 'SUSPENDED', 'DISABLED', 'UNVERIFIED'])
def test_head_ineligible_advance(client, setup, database, change):
    lib, book = setup; loan = issue(client, lib, book); a = reserve(client, lib, book); reserve(client, lib, book, 4)
    if change in ['DISABLED', 'UNVERIFIED']:
        database.users.update_one({'user_id': 3}, {'$set': {'is_active' if change == 'DISABLED' else 'is_email_verified': False}})
    else:
        database.institution_memberships.update_one({'library_id': lib, 'user_id': 3}, {'$set': {'status': change}})
    receive(client, lib, loan)
    assert database.institution_reservations.find_one({'reservation_id': a['reservation_id']})['status'] == 'CANCELLED'
    assert get(client, lib, 'me/reservations', 4)['results'][0]['status'] == 'CONVERTED'


def test_return_race_direct_cannot_steal(client, setup, database):
    lib, book = setup; loan = issue(client, lib, book); a = reserve(client, lib, book)
    request = call(client, lib, f'loans/{loan["loan_id"]}/return-request', 2, cmd(), expected=201)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(lambda: call(client, lib, f'staff/lending/return-requests/{request["lending_request_id"]}/confirm', body=cmd())),
                   pool.submit(lambda: client.post(f'/libraries/{lib}/lending/borrow-requests', headers={'x-test-user': '4'}, json=cmd(library_book_id=book)))]
        assert futures[1].result().status_code == 409
        futures[0].result()
    assert database.institution_lending_requests.find_one({'reservation_id': a['reservation_id']})['user_id'] == 3


def test_stock_increase_allocates_before_exposure_and_cancel_race(client, setup, database):
    lib, book = setup; issue(client, lib, book); a = reserve(client, lib, book); b = reserve(client, lib, book, 4)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(lambda: client.post(f'/libraries/{lib}/reservations/{a["reservation_id"]}/cancel', headers={'x-test-user': '3'}, json=cmd())),
                   pool.submit(lambda: client.put(f'/libraries/{lib}/staff/lending/books/{book}/stock', json=cmd(total_copies=2)))]
        assert futures[0].result().status_code in [200, 409]
        assert futures[1].result().status_code == 200
    assert database.institution_lending_requests.count_documents({'status': 'PENDING', 'request_type': 'BORROW'}) == 1
    assert get(client, lib, f'inventory/{book}/availability')['requestable'] == 0


def test_fee_final_policy_snapshot_and_duplicate_generation(client, setup, database):
    lib, book = setup; loan = issue(client, lib, book); original = loan['fee_policy_id']
    call(client, lib, 'settings/fee-policy', body=cmd(rate_minor_per_day=900, grace_days=1))
    database.institution_loans.update_one({'loan_id': loan['loan_id']}, {'$set': {'due_at': now() - timedelta(days=3)}})
    result = receive(client, lib, loan)
    fee = get(client, lib, 'me/fees', 2)['results'][0]
    assert fee['original_amount_minor'] == 1500 and fee['policy_id'] == original
    plan = database.institution_lending_operations.find_one({'operation_id': result['operation_id']})
    assert {'fees', 'fee_ledger', 'loans'}.issubset({s['collection'] for s in plan['effects']})
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: call(client, lib, f'staff/loans/{loan["loan_id"]}/fees/reconcile', body=cmd()), range(2)))
    assert database.institution_fees.count_documents({}) == 1
    assert database.institution_fee_ledger.count_documents({'entry_type': 'CHARGE'}) == 1
    newer = issue(client, lib, book)
    assert newer['fee_policy_snapshot']['rate_minor_per_day'] == 900


@pytest.mark.parametrize('policy,expected', [('PHYSICAL_RECEIPT', 1000), ('FIRST_VALID_RETURN_REQUEST', 500)])
def test_valid_return_staff_delay_and_rejected_fake(client, setup, database, policy, expected):
    lib, book = setup
    call(client, lib, 'settings/fee-policy', body=cmd(charge_stop_policy=policy))
    loan = issue(client, lib, book)
    due = now() - timedelta(days=2)
    database.institution_loans.update_one({'loan_id': loan['loan_id']}, {'$set': {'due_at': due}})
    fake = call(client, lib, f'loans/{loan["loan_id"]}/return-request', 2, cmd(), expected=201)
    database.institution_lending_requests.update_one({'lending_request_id': fake['lending_request_id']}, {'$set': {'requested_at': due - timedelta(days=1)}})
    call(client, lib, f'staff/lending/return-requests/{fake["lending_request_id"]}/reject', body=cmd(reason='Book not received'))
    valid = call(client, lib, f'loans/{loan["loan_id"]}/return-request', 2, cmd(), expected=201)
    database.institution_lending_requests.update_one({'lending_request_id': valid['lending_request_id']}, {'$set': {'requested_at': due + timedelta(days=1)}})
    call(client, lib, f'staff/lending/return-requests/{valid["lending_request_id"]}/confirm', body=cmd())
    fee = get(client, lib, 'staff/fees')['results'][0]
    assert fee['original_amount_minor'] == expected
    assert fee['calculation']['valid_return_requested_at'] != fake['requested_at']


def test_ledger_partial_full_payment_retry_overpay_and_waive(client, setup, database):
    lib, fee = fee_fixture(client, setup, database); path = f'staff/fees/{fee["fee_id"]}'
    key = cmd(amount_minor=500, method='CASH')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: call(client, lib, path + '/payments', body=key), range(2)))
    assert results[0] == results[1] and results[0]['status'] == 'PARTIALLY_PAID'
    assert results[0]['balance_minor'] == 1000
    call(client, lib, path + '/payments', body=cmd(amount_minor=1001, method='OTHER'), expected=409)
    call(client, lib, path + '/adjust', body=cmd(amount_minor=100, direction='CREDIT', reason='Approved credit'))
    full = call(client, lib, path + '/payments', body=cmd(amount_minor=900, method='EXTERNAL', reference='Desk reference'))
    assert full['status'] == 'PAID' and full['balance_minor'] == 0
    details = get(client, lib, path)
    assert len(details['ledger']) == 4 and details['original_amount_minor'] == 1500
    assert database.institution_fee_ledger.count_documents({'entry_type': 'PAYMENT_RECORD'}) == 2


def test_waiver_retains_charge_history_authority_reason(client, setup, database):
    lib, fee = fee_fixture(client, setup, database); path = f'staff/fees/{fee["fee_id"]}'
    database.institution_memberships.update_one({'library_id': lib, 'user_id': 3}, {'$set': {'role': 'LIBRARIAN'}})
    call(client, lib, path + '/waive', 3, cmd(reason='Requested'), expected=403)
    call(client, lib, path + '/adjust', 3, cmd(amount_minor=1, direction='CREDIT', reason='Requested'), expected=403)
    call(client, lib, path + '/waive', body=cmd(reason='   '), expected=422)
    call(client, lib, path + '/payments', 3, cmd(amount_minor=500, method='CASH'))
    waived = call(client, lib, path + '/waive', body=cmd(reason='Staff delay exception'))
    assert waived['status'] == 'WAIVED' and waived['original_amount_minor'] == 1500 and waived['paid_amount_minor'] == 500
    assert len(get(client, lib, path)['ledger']) == 3
    call(client, lib, path + '/payments', body=cmd(amount_minor=1, method='CASH'), expected=409)


def test_cross_library_private_and_global_admin_denied(client, setup, register, create, database):
    lib, book = setup; loan = issue(client, lib, book); a = reserve(client, lib, book)
    other = register(owner=30, private=True, name='Orion Private')
    for path in ['me/reservations', 'me/fees', 'staff/reservations', 'staff/fees', 'settings/fee-policy']:
        call(client, other, path, user=1, method='GET', expected=404)
    call(client, lib, 'staff/fees', user=30, method='GET', expected=403)
    call(client, other, 'reservations', user=30, body=cmd(library_book_id=book), expected=403)
    call(client, lib, f'reservations/{a["reservation_id"]}/cancel', user=4, body=cmd(), expected=404)
    database.institution_loans.update_one({'loan_id': loan['loan_id']}, {'$set': {'due_at': now() - timedelta(days=2)}})
    receive(client, lib, loan)
    fee = get(client, lib, 'staff/fees')['results'][0]
    call(client, lib, f'me/fees/{fee["fee_id"]}', user=4, method='GET', expected=404)
    call(client, other, f'staff/fees/{fee["fee_id"]}', user=30, method='GET', expected=409)


@pytest.mark.parametrize('value', [1.5, True, -1, 0, 1000000000001])
def test_money_strict_integer(client, setup, database, value):
    lib, fee = fee_fixture(client, setup, database)
    call(client, lib, f'staff/fees/{fee["fee_id"]}/payments', body=cmd(amount_minor=value, method='CASH'), expected=422)


@pytest.mark.parametrize('cut', [0, 1, 2, 3, 4, 5, 8, 12])
def test_partial_plan_replay_restores_compound_fee_queue(client, setup, database, monkeypatch, cut):
    lib, book = setup; loan = issue(client, lib, book); reserve(client, lib, book)
    database.institution_loans.update_one({'loan_id': loan['loan_id']}, {'$set': {'due_at': now() - timedelta(days=2)}})
    request = call(client, lib, f'loans/{loan["loan_id"]}/return-request', 2, cmd(), expected=201)
    replay = journal.replay
    def fail(plan):
        partial = {**plan, 'effects': plan['effects'][:cut]}
        for step in partial['effects']:
            journal.durable(step['collection']).update_one(step['query'], {'$setOnInsert' if step['insert_only'] else '$set': step['values']}, upsert=step['insert_only'])
        raise RuntimeError('Injected lost acknowledgement mid-plan')
    monkeypatch.setattr(journal, 'replay', fail)
    key = cmd(); path = f'staff/lending/return-requests/{request["lending_request_id"]}/confirm'
    call(client, lib, path, body=key, expected=503)
    assert database.institution_locks.find_one({'_id': lib})
    monkeypatch.setattr(journal, 'replay', replay)
    from scripts.institution_v2c_operations import recover
    assert recover(lib, apply=True, writers_stopped=True)['ok']
    assert call(client, lib, path, body=key)['status'] == 'COMPLETED'
    assert database.institution_fees.count_documents({}) == 1
    assert database.institution_lending_requests.count_documents({'request_type': 'BORROW', 'status': 'PENDING'}) == 1
