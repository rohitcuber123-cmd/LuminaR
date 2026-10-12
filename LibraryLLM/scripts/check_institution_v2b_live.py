"""Real HTTP acceptance scenarios A-M and timing samples, isolated Mongo only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
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
SCRATCH = ROOT / '.scratch/institution-v2b'
BASE = 'http://127.0.0.1:8082'
PASSWORD = 'LuminaR-Disposable-123!'


def write(name, data):
    (ROOT / 'reports' / f'institution_v2b_{name}.json').write_text(json.dumps(data, indent=2, default=str), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--serve', action='store_true'); args = parser.parse_args()
    database_name = 'luminar_institution_v2b_live_' + uuid4().hex
    mongo = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=5000); database = mongo[database_name]
    SCRATCH.mkdir(parents=True, exist_ok=True); (SCRATCH / 'stop').unlink(missing_ok=True)
    processes = []; logs = []; timings = {}; scenarios = []
    try:
        database.users.create_index('user_id', unique=True); database.users.create_index('email', unique=True)
        encoded = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
        database.users.insert_many([{'user_id': i, 'email': f'institution-v2b-{i}@example.com', 'name': f'Disposable Member {i}',
            'password_hash': encoded, 'role': 'ADMIN' if i == 30 else 'GENERAL_USER', 'is_active': True, 'is_email_verified': True} for i in range(1, 31)])
        works = list(mongo.luminar_library.books.find({'work_id': {'$in': ['OL19545719W', 'OL109579W']}}, {'_id': 0, 'work_id': 1, 'title': 1, 'subjects': 1, 'authors': 1}))
        database.books.insert_many(works)
        env = {**os.environ, 'MONGO_URI': 'mongodb://127.0.0.1:27017', 'MONGO_DB_NAME': database_name, 'JWT_SECRET_KEY': secrets.token_urlsafe(48),
            'LUMINAR_CORE_API_TARGET': BASE, 'ISBN_LOOKUP_DB': str(SCRATCH / 'no-isbn-mapping.duckdb')}
        for name, command, cwd in [('core', [sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8082'], ROOT),
            ('frontend', ['node', str(ROOT / 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5182', '--strictPort'], ROOT / 'frontend')]:
            log = (SCRATCH / f'{name}.log').open('w', encoding='utf-8'); logs.append(log)
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0))
        with httpx.Client(timeout=90) as client:
            for _ in range(100):
                if any(p.poll() is not None for p in processes):
                    raise RuntimeError('Fixture service exited. Inspect .scratch/institution-v2b logs.')
                try:
                    if client.get(BASE + '/health').is_success and client.get('http://127.0.0.1:5182/').is_success:
                        break
                except httpx.HTTPError:
                    pass
                sleep(.25)
            else:
                raise RuntimeError('Fixture startup timed out.')
            headers = {}
            for user in [1, 2, 3, 4, 30]:
                login = client.post(BASE + '/auth/login', json={'email': f'institution-v2b-{user}@example.com', 'password': PASSWORD}); login.raise_for_status()
                headers[user] = {'Authorization': 'Bearer ' + login.json()['access_token']}
            os.environ.update({k: env[k] for k in ['MONGO_URI', 'MONGO_DB_NAME', 'JWT_SECRET_KEY', 'ISBN_LOOKUP_DB']})
            sys.path.insert(0, str(ROOT))
            from backend.utils.jwt_utils import create_access_token
            for user in range(1, 31):
                headers.setdefault(user, {'Authorization': 'Bearer ' + create_access_token(user, f'institution-v2b-{user}@example.com', 'GENERAL_USER')})
            def call(user, method, path, body=None, expected=200, metric=None):
                start = perf_counter(); response = client.request(method, BASE + path, headers=headers[user], json=body)
                assert response.status_code == expected, f'{method} {path}: {response.status_code}: {response.text[:300]}'
                if metric:
                    timings.setdefault(metric, []).append(round((perf_counter() - start) * 1000, 3))
                return response.json()
            def cmd(**fields): return {'idempotency_key': str(uuid4()), **fields}
            def library(user, name):
                return call(user, 'POST', '/libraries/register', {'name': name, 'slug': 'v2b-live-' + uuid4().hex[:10], 'library_type': 'PUBLIC_LIBRARY', 'access_mode': 'PUBLIC'}, 201)['library']['library_id']
            aurora = library(1, 'Aurora Approval Library'); orion = library(2, 'Orion Approval Library')
            for user in range(2, 30): call(user, 'POST', f'/libraries/{aurora}/join', {})
            for user in [1, 3, 4]: call(user, 'POST', f'/libraries/{orion}/join', {})
            for lib, owner in [(aurora, 1), (orion, 2)]: call(owner, 'POST', f'/libraries/{lib}/staff/lending/activate', cmd())
            def add(lib, user, title, copies=1, **fields):
                return call(user, 'POST', f'/libraries/{lib}/inventory/books', cmd(title=title, subjects=['Systems'], copies=copies, shelf_location='Room 2 / Shelf B', **fields), 201)['library_book_id']
            def request(lib, book, user=3, body=None):
                return call(user, 'POST', f'/libraries/{lib}/lending/borrow-requests', body or cmd(library_book_id=book), 201, 'borrow_request')
            def review(lib, request_id, action, user=1, kind='borrow', body=None):
                return call(user, 'POST', f'/libraries/{lib}/staff/lending/{kind}-requests/{request_id}/{action}', body or cmd(), metric={'approve': 'approval', 'reject': 'rejection', 'confirm': 'return_confirmation'}[action])
            def avail(lib, book, user=1):
                return call(user, 'GET', f'/libraries/{lib}/inventory/{book}/availability', metric='availability_read')
            def passed(code, title, **evidence): scenarios.append({'code': code, 'scenario': title, 'status': 'PASS', **evidence})
            book = add(aurora, 1, 'Local Practical Handbook')
            pending = request(aurora, book); assert avail(aurora, book)['requestable'] == 0 and database.institution_loans.count_documents({}) == 0
            loan = review(aurora, pending['lending_request_id'], 'approve')['loan']; assert avail(aurora, book)['requestable'] == 0
            passed('A', 'Aggregate request holds without a loan; approval converts the same allocation', loan_id=loan['loan_id'])
            race = add(aurora, 1, 'The Last Unit')
            def contender(user):
                response = client.post(BASE + f'/libraries/{aurora}/lending/borrow-requests', json=cmd(library_book_id=race), headers=headers[user])
                return {'user': user, 'status': response.status_code, 'request': response.json()}
            with ThreadPoolExecutor(max_workers=2) as pool: racers = list(pool.map(contender, [4, 5]))
            assert sorted(r['status'] for r in racers) == [201, 409]; passed('B', 'Concurrent last unit requests have one winner', results=racers)
            winner = next(r['request'] for r in racers if r['status'] == 201)
            review(aurora, winner['lending_request_id'], 'reject', body=cmd(reason='Condition check')); assert avail(aurora, race)['requestable'] == 1
            passed('C', 'Rejection releases the held unit')
            pending = request(aurora, race); key = cmd(); path = f'/libraries/{aurora}/lending/borrow-requests/{pending["lending_request_id"]}/cancel'
            call(3, 'POST', path, key, metric='cancellation'); call(3, 'POST', path, key); assert avail(aurora, race)['requestable'] == 1
            passed('D', 'Cancellation and replay release once')
            pending = request(aurora, race); database.institution_lending_requests.update_one({'lending_request_id': pending['lending_request_id']}, {'$set': {'expires_at': datetime.now(timezone.utc) - timedelta(seconds=1)}})
            assert avail(aurora, race)['requestable'] == 1; passed('E', 'Lazy expiry releases the hold')
            ret = call(3, 'POST', f'/libraries/{aurora}/loans/{loan["loan_id"]}/return-request', cmd(), 201, 'return_request')
            current = call(3, 'GET', f'/libraries/{aurora}/me/loans')['results']; assert current[0]['status'] == 'ACTIVE' and avail(aurora, book)['requestable'] == 0
            key = cmd(); confirmed = review(aurora, ret['lending_request_id'], 'confirm', kind='return', body=key); review(aurora, ret['lending_request_id'], 'confirm', kind='return', body=key)
            assert confirmed['loan']['status'] == 'RETURNED' and avail(aurora, book)['requestable'] == 1
            passed('F', 'Return request stays active; physical confirmation moves it to history and releases once')
            pending = request(aurora, book); loan = review(aurora, pending['lending_request_id'], 'approve')['loan']
            ret = call(3, 'POST', f'/libraries/{aurora}/loans/{loan["loan_id"]}/return-request', cmd(), 201)
            review(aurora, ret['lending_request_id'], 'reject', kind='return', body=cmd(reason='Book not physically received'))
            assert avail(aurora, book)['requestable'] == 0; passed('G', 'Rejected return remains active and allocated')
            linked_a = add(aurora, 1, 'Shared Global Work', global_work_id=works[0]['work_id'])
            linked_b = add(orion, 2, 'Shared Global Work', global_work_id=works[0]['work_id'])
            request(aurora, linked_a); assert avail(aurora, linked_a)['requestable'] == 0 and avail(orion, linked_b, 2)['requestable'] == 1
            passed('H', 'Same global work uses independent library holdings')
            ret = call(3, 'POST', f'/libraries/{aurora}/loans/{loan["loan_id"]}/return-request', cmd(), 201)
            review(aurora, ret['lending_request_id'], 'confirm', kind='return'); passed('I', 'Local-only record completes the full request/issue/physical-return cycle')
            reference = add(aurora, 1, 'Reference Handbook', circulation_status='REFERENCE_ONLY')
            call(3, 'POST', f'/libraries/{aurora}/lending/borrow-requests', cmd(library_book_id=reference), 409); passed('J', 'Reference-only record remains visible but cannot be requested')
            call(1, 'PUT', f'/libraries/{aurora}/staff/lending/books/{linked_a}/shelf', cmd(shelf_location='North Wing / A-4', call_number='004.9'))
            assert avail(aurora, linked_a)['shelf_location'] == 'North Wing / A-4'; queue = call(1, 'GET', f'/libraries/{aurora}/staff/lending/borrow-requests')['results']
            assert next(r for r in queue if r['library_book_id'] == linked_a)['shelf_location'] == 'North Wing / A-4'; passed('K', 'Shelf change is visible to member availability and staff queue')
            call(1, 'PUT', f'/libraries/{aurora}/staff/lending/books/{linked_a}/stock', cmd(total_copies=2)); assert avail(aurora, linked_a)['requestable'] == 1; passed('L', 'Stock increase safely creates requestable capacity')
            call(1, 'PUT', f'/libraries/{aurora}/staff/lending/books/{linked_a}/stock', cmd(total_copies=0), 409); passed('M', 'Stock decrease below pending/active allocation is denied')
            # Multiple actual HTTP samples per requested operation, no extrapolated capacity claim.
            perf_book = add(aurora, 1, 'Timing Fixture', copies=3)
            for iteration in range(12):
                pending = request(aurora, perf_book, 6)
                if iteration % 3 == 0:
                    review(aurora, pending['lending_request_id'], 'reject')
                elif iteration % 3 == 1:
                    call(6, 'POST', f'/libraries/{aurora}/lending/borrow-requests/{pending["lending_request_id"]}/cancel', cmd(), metric='cancellation')
                else:
                    loan = review(aurora, pending['lending_request_id'], 'approve')['loan']
                    call(6, 'POST', f'/libraries/{aurora}/loans/{loan["loan_id"]}/renew', cmd(expected_due_at=loan['due_at']), metric='renewal')
                    ret = call(6, 'POST', f'/libraries/{aurora}/loans/{loan["loan_id"]}/return-request', cmd(), 201, 'return_request')
                    review(aurora, ret['lending_request_id'], 'confirm', kind='return')
                avail(aurora, perf_book); call(1, 'GET', f'/libraries/{aurora}/staff/lending/borrow-requests', metric='staff_list')
            call(30, 'GET', f'/libraries/{aurora}/staff/lending/borrow-requests', expected=404)
            call(3, 'GET', f'/libraries/{aurora}/staff/lending/borrow-requests', expected=403)
            call(3, 'POST', '/issues/issue', {'work_id': works[0]['work_id']}, 409)
            database.users.update_one({'user_id': 6}, {'$set': {'is_active': False}})
            call(6, 'GET', f'/libraries/{aurora}/me/loans', expected=401); database.users.update_one({'user_id': 6}, {'$set': {'is_active': True}})
            # Leave one pending borrow and one pending return for browser confirmation testing.
            pending = request(aurora, book, 4); loan = review(aurora, pending['lending_request_id'], 'approve')['loan']
            call(4, 'POST', f'/libraries/{aurora}/loans/{loan["loan_id"]}/return-request', cmd(), 201)
            fixture = {'database': database_name, 'aurora': aurora, 'orion': orion, 'book': book, 'linked_a': linked_a, 'core': BASE, 'frontend': 'http://127.0.0.1:5182', 'synthetic_password': PASSWORD}
            (SCRATCH / 'fixture.json').write_text(json.dumps(fixture), encoding='utf-8')
            write('live', {'status': 'PASS', 'transport': 'real HTTP / uvicorn / Mongo / Vite', 'production_modified': False, 'scenarios': scenarios, 'security': {'outsider_global_admin_denied': True, 'member_staff_denied': True, 'legacy_bypass_denied': True, 'disabled_account_denied': True}})
            metrics = {key: {'samples': len(values), 'median_ms': round(statistics.median(values), 3), 'p90_ms': sorted(values)[max(0, int(len(values) * .9 + .9999) - 1)], 'raw_ms': values} for key, values in timings.items()}
            write('performance', {'environment': 'Local standalone Mongo with acknowledged journal writes; disposable small library', 'metrics': metrics,
                'p90_note': 'Descriptive nearest-rank percentile. Fewer than ten samples gives weak tail precision; no production-tail or service-level claim.',
                'limitations': 'No production-scale throughput, multi-host or replica-set claim.'})
            print('Live A-M and circulation performance/security checks: PASS', flush=True)
            if args.serve:
                print('Fixture ready. Create .scratch/institution-v2b/stop to stop services and drop only this disposable database.', flush=True)
                while not (SCRATCH / 'stop').exists(): sleep(.5)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
        for log in logs: log.close()
        assert database_name.startswith('luminar_institution_v2b_live_')
        mongo.drop_database(database_name)
        write('cleanup', {'fixture_database_dropped': database_name not in mongo.list_database_names(), 'own_services_stopped': all(p.poll() is not None for p in processes), 'production_modified': False})
        mongo.close(); (SCRATCH / 'stop').unlink(missing_ok=True)


if __name__ == '__main__': main()
