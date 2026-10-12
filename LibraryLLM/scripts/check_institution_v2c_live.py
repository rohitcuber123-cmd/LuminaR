"""Real HTTP/JWT acceptance on disposable Mongo, with optional browser fixture."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import secrets
import statistics
import subprocess
import sys
from time import perf_counter, sleep
from uuid import uuid4
import bcrypt
import httpx
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / '.scratch/institution-v2c'
BASE = 'http://127.0.0.1:8083'
PASSWORD = 'LuminaR-Disposable-123!'


def write(name, data):
    (ROOT / 'reports' / f'institution_v2c_{name}.json').write_text(json.dumps(data, indent=2, default=str), encoding='utf8')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--serve', action='store_true'); args = parser.parse_args()
    database_name = 'luminar_institution_v2c_live_' + uuid4().hex
    mongo = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=5000); database = mongo[database_name]
    SCRATCH.mkdir(parents=True, exist_ok=True); (SCRATCH / 'stop').unlink(missing_ok=True)
    processes = []; logs = []; timings = {}; scenarios = []
    try:
        database.users.create_index('user_id', unique=True); database.users.create_index('email', unique=True)
        encoded = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
        database.users.insert_many([{'user_id': i, 'email': f'institution-v2c-{i}@example.com', 'name': f'Disposable Member {i}',
            'password_hash': encoded, 'role': 'ADMIN' if i == 30 else 'GENERAL_USER', 'is_active': True, 'is_email_verified': True} for i in range(1, 31)])
        database.books.insert_many([{'work_id': 'OL-Systems', 'title': 'Shared Systems', 'subjects': ['Systems']}, {'work_id': 'OL-Networks', 'title': 'Computer Networks', 'subjects': ['Networking']}])
        env = {**os.environ, 'MONGO_URI': 'mongodb://127.0.0.1:27017', 'MONGO_DB_NAME': database_name, 'JWT_SECRET_KEY': secrets.token_urlsafe(48), 'LUMINAR_CORE_API_TARGET': BASE, 'ISBN_LOOKUP_DB': str(SCRATCH / 'no-isbn.duckdb')}
        for name, command, cwd in [('core', [sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8083'], ROOT),
            ('frontend', ['node', str(ROOT / 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5183', '--strictPort'], ROOT / 'frontend')]:
            log = (SCRATCH / f'{name}.log').open('w', encoding='utf8'); logs.append(log)
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0))
        with httpx.Client(timeout=90) as client:
            for _ in range(100):
                if any(p.poll() is not None for p in processes): raise RuntimeError('Fixture exited; inspect .scratch/institution-v2c logs.')
                try:
                    if client.get(BASE + '/health').is_success and client.get('http://127.0.0.1:5183/').is_success: break
                except httpx.HTTPError: pass
                sleep(.25)
            else: raise RuntimeError('Fixture startup timed out.')
            headers = {}
            for user in [1, 2, 3, 4, 30]:
                login = client.post(BASE + '/auth/login', json={'email': f'institution-v2c-{user}@example.com', 'password': PASSWORD}); login.raise_for_status()
                headers[user] = {'Authorization': 'Bearer ' + login.json()['access_token']}
            os.environ.update({k: env[k] for k in ['MONGO_URI', 'MONGO_DB_NAME', 'JWT_SECRET_KEY', 'ISBN_LOOKUP_DB']})
            sys.path.insert(0, str(ROOT))
            from backend.utils.jwt_utils import create_access_token
            for user in range(1, 31): headers.setdefault(user, {'Authorization': 'Bearer ' + create_access_token(user, f'institution-v2c-{user}@example.com', 'GENERAL_USER')})
            def call(user, method, path, body=None, expected=200, metric=None):
                started = perf_counter(); r = client.request(method, BASE + path, headers=headers[user], json=body)
                assert r.status_code == expected, f'{method} {path}: {r.status_code}: {r.text[:400]}'
                if metric: timings.setdefault(metric, []).append(round((perf_counter() - started) * 1000, 3))
                return r.json()
            def cmd(**fields): return {'idempotency_key': str(uuid4()), **fields}
            def lib(user, name): return call(user, 'POST', '/libraries/register', {'name': name, 'slug': 'v2c-live-' + uuid4().hex[:10], 'library_type': 'PUBLIC_LIBRARY', 'access_mode': 'PUBLIC'}, 201)['library']['library_id']
            aurora, orion = lib(1, 'Aurora Library'), lib(2, 'Orion Library')
            for user in range(2, 30): call(user, 'POST', f'/libraries/{aurora}/join', {})
            for user in [1, 3, 4]: call(user, 'POST', f'/libraries/{orion}/join', {})
            database.institution_memberships.update_one({'library_id': aurora, 'user_id': 4}, {'$set': {'role': 'LIBRARIAN'}})
            for library, owner in [(aurora, 1), (orion, 2)]:
                call(owner, 'POST', f'/libraries/{library}/staff/lending/activate', cmd())
                call(owner, 'POST', f'/libraries/{library}/staff/reservations-fees/activate', cmd())
            def add(library, owner, title, copies=1, **fields): return call(owner, 'POST', f'/libraries/{library}/inventory/books', cmd(title=title, subjects=['Systems'], copies=copies, shelf_location='Room 2 / Shelf B', **fields), 201)['library_book_id']
            def borrow(library, book, user=3): return call(user, 'POST', f'/libraries/{library}/lending/borrow-requests', cmd(library_book_id=book), 201)
            def issue(library, book, owner=1, user=3):
                r = borrow(library, book, user)
                return call(owner, 'POST', f'/libraries/{library}/staff/lending/borrow-requests/{r["lending_request_id"]}/approve', cmd())['loan']
            def reserve(library, book, user=3): return call(user, 'POST', f'/libraries/{library}/reservations', cmd(library_book_id=book), 201, 'reservation_create')
            def queues(library, user): return call(user, 'GET', f'/libraries/{library}/me/reservations', metric='queue_read')['results']
            def return_request(library, loan, user=3): return call(user, 'POST', f'/libraries/{library}/loans/{loan["loan_id"]}/return-request', cmd(), 201)
            def confirm(library, request, owner=1): return call(owner, 'POST', f'/libraries/{library}/staff/lending/return-requests/{request["lending_request_id"]}/confirm', cmd(), metric='return_confirmation_combined')
            def fees(library, owner=1): return call(owner, 'GET', f'/libraries/{library}/staff/fees', metric='staff_fee_list')['results']
            def overdue(loan, days): database.institution_loans.update_one({'loan_id': loan['loan_id']}, {'$set': {'due_at': datetime.now(timezone.utc) - timedelta(days=days)}})
            def passed(code, title, **evidence): scenarios.append({'code': code, 'scenario': title, 'status': 'PASS', **evidence})
            book = add(aurora, 1, 'Local Circulation Manual'); loan = issue(aurora, book, user=4)
            a, b = reserve(aurora, book, 3), reserve(aurora, book, 2)
            assert queues(aurora, 3)[0]['queue_position'] == 1 and queues(aurora, 2)[0]['queue_position'] == 2
            passed('A', 'Unavailable Aurora book: two members enter FIFO positions 1 and 2', reservation_ids=[a['reservation_id'], b['reservation_id']])
            confirm(aurora, return_request(aurora, loan, 4)); converted = next(r for r in queues(aurora, 3) if r['reservation_id'] == a['reservation_id'])
            assert converted['status'] == 'CONVERTED' and database.institution_lending_requests.count_documents({'reservation_id': a['reservation_id']}) == 1
            assert next(r for r in queues(aurora, 2) if r['reservation_id'] == b['reservation_id'])['status'] == 'WAITING'
            passed('B', 'Physical return converts only FIFO head to one canonical hold', borrow_request_id=converted['lending_request_id'])
            zero = add(aurora, 1, 'Cancellation Queue', copies=0); ca, cb = reserve(aurora, zero, 3), reserve(aurora, zero, 2)
            call(3, 'POST', f'/libraries/{aurora}/reservations/{ca["reservation_id"]}/cancel', cmd(), metric='reservation_cancel')
            assert next(r for r in queues(aurora, 2) if r['reservation_id'] == cb['reservation_id'])['queue_position'] == 1
            passed('C', 'Waiting cancellation advances the next member without allocating stock')
            linked_a, linked_b = add(aurora, 1, 'Shared Systems', copies=0, global_work_id='OL-Systems'), add(orion, 2, 'Shared Systems', copies=0, global_work_id='OL-Systems')
            reserve(aurora, linked_a, 3); reserve(orion, linked_b, 3)
            assert next(r for r in queues(aurora, 3) if r['library_book_id'] == linked_a)['queue_position'] == next(r for r in queues(orion, 3) if r['library_book_id'] == linked_b)['queue_position'] == 1
            passed('D', 'One global work has independent Aurora and Orion queues')
            assert database.institution_library_books.find_one({'library_book_id': book}).get('global_work_id') is None
            passed('E', 'Local-only book reserves and converts without global catalogue identity')
            fee_book = add(aurora, 1, 'Overdue Handbook'); fee_loan = issue(aurora, fee_book); overdue(fee_loan, 3)
            confirm(aurora, return_request(aurora, fee_loan)); charge = next(f for f in fees(aurora) if f['loan_id'] == fee_loan['loan_id'])
            assert charge['original_amount_minor'] == 1500 and charge['policy_snapshot']['version'] == 1
            passed('F', 'Overdue physical return creates one final fee with policy provenance', fee_id=charge['fee_id'])
            call(1, 'POST', f'/libraries/{aurora}/settings/fee-policy', cmd(charge_stop_policy='FIRST_VALID_RETURN_REQUEST'))
            delayed = issue(aurora, fee_book); overdue(delayed, 1); valid = return_request(aurora, delayed)
            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            database.institution_lending_requests.update_one({'lending_request_id': valid['lending_request_id']}, {'$set': {'requested_at': yesterday}})
            confirmed = confirm(aurora, valid)
            assert database.institution_fees.count_documents({'loan_id': delayed['loan_id']}) == 0
            assert confirmed['loan']['physical_received_at'] != confirmed['loan']['valid_return_requested_at']
            passed('G', 'Valid return requested on due UTC day; next-day staff receipt creates no charge under configured valid-request policy', synthetic_date_fixture=True)
            fake_loan = issue(aurora, fee_book); overdue(fake_loan, 2); fake = return_request(aurora, fake_loan)
            database.institution_lending_requests.update_one({'lending_request_id': fake['lending_request_id']}, {'$set': {'requested_at': yesterday - timedelta(days=2)}})
            call(1, 'POST', f'/libraries/{aurora}/staff/lending/return-requests/{fake["lending_request_id"]}/reject', cmd(reason='Book not physically received'))
            confirm(aurora, return_request(aurora, fake_loan)); fake_fee = next(f for f in fees(aurora) if f['loan_id'] == fake_loan['loan_id'])
            assert fake_fee['original_amount_minor'] == 1000
            passed('H', 'Rejected fake return does not stop accrual')
            waived = call(1, 'POST', f'/libraries/{aurora}/staff/fees/{fake_fee["fee_id"]}/waive', cmd(reason='Approved library exception'), metric='fee_waive')
            assert waived['status'] == 'WAIVED' and waived['original_amount_minor'] == 1000
            passed('I', 'Admin waiver retains the charge and immutable history')
            payment_path = f'/libraries/{aurora}/staff/fees/{charge["fee_id"]}/payments'; key = cmd(amount_minor=500, method='CASH')
            partial = call(4, 'POST', payment_path, key, metric='payment_record'); retry = call(4, 'POST', payment_path, key)
            assert partial == retry and partial['status'] == 'PARTIALLY_PAID'
            full = call(4, 'POST', payment_path, cmd(amount_minor=1000, method='EXTERNAL', reference='Library desk receipt'), metric='payment_record')
            assert full['status'] == 'PAID' and full['ledger_entry']['payment_processing'] == 'MANUAL_RECORD_ONLY'
            passed('J', 'Librarian records partial/full manual payments; retry does not duplicate or process money')
            for library, local_book, owner in [(aurora, linked_a, 1), (orion, linked_b, 2)]:
                call(owner, 'PUT', f'/libraries/{library}/staff/lending/books/{local_book}/stock', cmd(total_copies=1))
                converted_local = next(r for r in queues(library, 3) if r['library_book_id'] == local_book)
                loan_local = call(owner, 'POST', f'/libraries/{library}/staff/lending/borrow-requests/{converted_local["lending_request_id"]}/approve', cmd())['loan']
                overdue(loan_local, 2); confirm(library, return_request(library, loan_local), owner)
            assert any(f['library_book_id'] == linked_a for f in fees(aurora)) and any(f['library_book_id'] == linked_b for f in fees(orion, 2))
            passed('K', 'Same member and work produce separate library queues and fees')
            # Small-fixture repeated actual HTTP samples; no production capacity claim.
            timing_zero = add(aurora, 1, 'Timing Waitlist', copies=0)
            timing_book = add(aurora, 1, 'Timing Overdue')
            timing_conversion = add(aurora, 1, 'Timing Queue Conversion', copies=0)
            from backend.services.library_fee_service import calculation
            for iteration in range(12):
                r = reserve(aurora, timing_zero, 6); queues(aurora, 6)
                call(6, 'POST', f'/libraries/{aurora}/reservations/{r["reservation_id"]}/cancel', cmd(), metric='reservation_cancel')
                queued = reserve(aurora, timing_conversion, 6)
                call(1, 'PUT', f'/libraries/{aurora}/staff/lending/books/{timing_conversion}/stock', cmd(total_copies=1), metric='queue_conversion_with_stock_increase')
                converted_t = database.institution_reservations.find_one({'reservation_id': queued['reservation_id']})
                assert converted_t['status'] == 'CONVERTED'
                call(6, 'POST', f'/libraries/{aurora}/lending/borrow-requests/{converted_t["lending_request_id"]}/cancel', cmd())
                call(1, 'PUT', f'/libraries/{aurora}/staff/lending/books/{timing_conversion}/stock', cmd(total_copies=0))
                loan_t = issue(aurora, timing_book, user=6); overdue(loan_t, 2)
                calculation_input = database.institution_loans.find_one({'loan_id': loan_t['loan_id']})
                started = perf_counter(); calculated = calculation(calculation_input)
                timings.setdefault('fee_calculation_pure', []).append(round((perf_counter() - started) * 1000, 6))
                assert calculated['amount_minor'] == 1000
                confirm(aurora, return_request(aurora, loan_t, 6))
                timings.setdefault('fee_creation_with_physical_return', []).append(timings['return_confirmation_combined'][-1])
                fee_t = next(f for f in fees(aurora) if f['loan_id'] == loan_t['loan_id'])
                call(1, 'POST', f'/libraries/{aurora}/staff/loans/{loan_t["loan_id"]}/fees/reconcile', cmd(), metric='fee_generation_idempotent')
                call(6, 'GET', f'/libraries/{aurora}/me/fees', metric='own_fee_list')
                call(1, 'GET', f'/libraries/{aurora}/staff/reservations', metric='staff_reservation_list')
                if iteration % 2:
                    call(4, 'POST', f'/libraries/{aurora}/staff/fees/{fee_t["fee_id"]}/payments', cmd(amount_minor=1000, method='CASH'), metric='payment_record')
                else:
                    call(1, 'POST', f'/libraries/{aurora}/staff/fees/{fee_t["fee_id"]}/waive', cmd(reason='Timing fixture waiver'), metric='fee_waive')
            # Leave clear browser data: waiting queue, converted request and OPEN/PARTIALLY_PAID fees.
            browser_book = add(aurora, 1, 'Browser Waitlist Manual', copies=0); reserve(aurora, browser_book, 3); reserve(aurora, browser_book, 2)
            open_loan = issue(aurora, timing_book, user=3); overdue(open_loan, 3); confirm(aurora, return_request(aurora, open_loan)); open_fee = next(f for f in fees(aurora) if f['loan_id'] == open_loan['loan_id'])
            call(4, 'POST', f'/libraries/{aurora}/staff/fees/{open_fee["fee_id"]}/payments', cmd(amount_minor=500, method='CASH'))
            call(30, 'GET', f'/libraries/{aurora}/staff/fees', expected=404)
            call(3, 'GET', f'/libraries/{aurora}/staff/fees', expected=403)
            call(4, 'POST', f'/libraries/{aurora}/staff/fees/{open_fee["fee_id"]}/waive', cmd(reason='Unauthorized'), expected=403)
            call(3, 'POST', '/reservations/', {'work_id': 'OL-Systems'}, 409)
            from scripts.institution_v2c_operations import reconcile
            assert reconcile(aurora)['ok'] and reconcile(orion)['ok']
            write('live', {'status': 'PASS', 'database': database_name, 'scenarios': scenarios, 'real_jwt_login_users': [1, 2, 3, 4, 30], 'synthetic_overdue_timestamps': True, 'production_mutations': 0, 'reconciliation': [reconcile(aurora), reconcile(orion)]})
            write('performance', {'environment': 'Windows/local standalone Mongo; disposable library fixture; actual HTTP timings in ms', 'scale_claim': False,
                'percentile_method': 'Nearest rank: ceil(0.90 * n).',
                'measurement_notes': {
                    'queue_conversion_with_stock_increase': 'Actual journaled stock increase including exactly one FIFO hold conversion; not an isolated queue-only microbenchmark.',
                    'fee_creation_with_physical_return': 'Actual new overdue fee and ledger creation in the same physical-return journal; includes return authorization and stock release.',
                    'fee_calculation_pure': 'In-process pure calculation on a policy-snapshotted fixture loan, without HTTP or writes.',
                    'fee_generation_idempotent': 'Actual HTTP reconciliation of an already-created fee; measures the idempotent generation path.'},
                'operations': {name: {'n': len(values), 'median_ms': statistics.median(values), 'p90_ms': sorted(values)[math.ceil(len(values)*.9)-1], 'samples_ms': values} for name, values in timings.items()}})
            (SCRATCH / 'fixture.json').write_text(json.dumps({'database': database_name, 'aurora': aurora, 'orion': orion, 'browser_book': browser_book, 'open_fee': open_fee['fee_id'], 'password': PASSWORD, 'frontend': 'http://127.0.0.1:5183', 'core': BASE}), encoding='utf8')
            print('Part 2C live scenarios A–K PASS. Fixture ready.', flush=True)
            if args.serve:
                while not (SCRATCH / 'stop').exists(): sleep(.5)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
        for log in logs: log.close()
        assert database_name.startswith('luminar_institution_v2c_live_')
        mongo.drop_database(database_name)
        write('cleanup', {'fixture_database_dropped': database_name not in mongo.list_database_names(), 'own_services_stopped': all(p.poll() is not None for p in processes), 'production_modified': False})
        mongo.close(); (SCRATCH / 'stop').unlink(missing_ok=True)


if __name__ == '__main__': main()
