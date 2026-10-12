"""Real HTTP validation on disposable Mongo. --serve keeps the browser fixture alive.

No production accounts, mail delivery, model loading, or domain migrations.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from time import perf_counter, sleep
from uuid import uuid4

import bcrypt
import httpx
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
SCRATCH = ROOT / '.scratch/institution-v1'
BASE = 'http://127.0.0.1:8082'
PASSWORD = 'LuminaR-Disposable-123!'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve', action='store_true')
    args = parser.parse_args()
    database_name = 'luminar_institution_live_' + uuid4().hex
    mongo = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=3000)
    database = mongo[database_name]
    database.users.create_index('user_id', unique=True); database.users.create_index('email', unique=True)
    encoded = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
    database.users.insert_many([{'user_id': i, 'email': f'institution-test-{i}@example.com', 'name': f'Disposable User {i}',
        'password_hash': encoded, 'role': 'GENERAL_USER', 'is_email_verified': True, 'is_active': True} for i in range(1, 61)])
    env = {**os.environ, 'MONGO_URI': 'mongodb://127.0.0.1:27017', 'MONGO_DB_NAME': database_name,
           'JWT_SECRET_KEY': secrets.token_urlsafe(48), 'LUMINAR_CORE_API_TARGET': BASE}
    logs = []; processes = []
    SCRATCH.mkdir(parents=True, exist_ok=True)
    try:
        for name, command, cwd in [
            ('core', [sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8082'], ROOT),
            ('frontend', ['node', str(ROOT / 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5182', '--strictPort'], ROOT / 'frontend'),
        ]:
            log = (SCRATCH / (name + '.log')).open('w', encoding='utf8'); logs.append(log)
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0))
        client = httpx.Client(timeout=20)
        for _ in range(80):
            if any(p.poll() is not None for p in processes):
                raise RuntimeError('A validation service exited. Inspect .scratch/institution-v1 logs.')
            try:
                if client.get(BASE + '/health').is_success and client.get('http://127.0.0.1:5182/').is_success:
                    break
            except httpx.HTTPError:
                pass
            sleep(.25)
        else:
            raise RuntimeError('Validation services did not become ready.')
        headers = {}
        for i in range(1, 61):
            result = client.post(BASE + '/auth/login', json={'email': f'institution-test-{i}@example.com', 'password': PASSWORD})
            # Login's existing IP limiter permits only 20/min. Build later JWTs with
            # the actual auth helper; at least the initial accounts use real login.
            if result.status_code == 429:
                break
            result.raise_for_status(); headers[i] = {'Authorization': 'Bearer ' + result.json()['access_token']}
        os.environ.update({k: env[k] for k in ('MONGO_URI', 'MONGO_DB_NAME', 'JWT_SECRET_KEY')})
        sys.path.insert(0, str(ROOT))
        from backend.utils.jwt_utils import create_access_token
        for i in range(1, 61):
            headers.setdefault(i, {'Authorization': 'Bearer ' + create_access_token(i, f'institution-test-{i}@example.com', 'GENERAL_USER')})
        records = []
        metrics = {}
        def call(user, method, path, body=None, expected=200, metric=None):
            start = perf_counter()
            response = client.request(method, BASE + path, headers=headers[user], json=body)
            elapsed = (perf_counter() - start) * 1000
            if response.status_code != expected:
                raise AssertionError(f'{method} {path}: expected {expected}, got {response.status_code}')
            if metric:
                metrics.setdefault(metric, []).append(round(elapsed, 3))
            return response.json()
        def passed(scenario): records.append({'scenario': scenario, 'status': 'PASS'})
        def register(user, private, name, slug):
            return call(user, 'POST', '/libraries/register', {'name': name, 'slug': slug, 'access_mode': 'PRIVATE_CODE' if private else 'PUBLIC',
                'library_type': 'PRIVATE_INSTITUTION' if private else 'PUBLIC_LIBRARY', 'address': {'city': 'Hyderabad', 'region': 'Telangana'},
                **({'access_code': 'Orion Private Institution Code'} if private else {})}, 201, 'registration')['library']['library_id']
        aurora = register(1, False, 'Aurora Public Library', 'aurora-disposable')
        call(2, 'GET', '/libraries?search=Aurora'); call(2, 'POST', f'/libraries/{aurora}/join', {}, metric='public_join')
        passed('A: public registration/discovery/join')
        orion = register(3, True, 'Orion Research Institute', 'orion-disposable')
        call(4, 'GET', f'/libraries/{orion}/context', expected=404)
        call(4, 'POST', f'/libraries/{orion}/join', {'access_code': 'Wrong access code'}, 403)
        call(4, 'POST', f'/libraries/{orion}/join', {'access_code': 'Orion Private Institution Code'}, metric='private_join')
        passed('B: private outsider guard, wrong/correct code')
        call(4, 'POST', f'/libraries/{aurora}/join', {})
        assert len(call(4, 'GET', '/me/libraries')['results']) == 2
        passed('C: same global user belongs to two libraries')
        invitation = call(3, 'POST', f'/libraries/{orion}/invitations', {'email': 'institution-test-4@example.com', 'role': 'LIBRARIAN'}, 201, 'invitation_create')
        accepted = call(4, 'POST', f'/invitations/{invitation["invitation"]["invitation_id"]}/accept', {'token': invitation['invite_token']}, metric='invitation_accept')
        assert accepted['membership']['role'] == 'LIBRARIAN'
        passed('D: per-library role differs')
        call(4, 'PUT', f'/libraries/{orion}/access-code', {'access_code': 'Rotated Orion Institution Code'}, metric='code_rotation')
        call(5, 'POST', f'/libraries/{orion}/join', {'access_code': 'Orion Private Institution Code'}, 403)
        call(5, 'POST', f'/libraries/{orion}/join', {'access_code': 'Rotated Orion Institution Code'}, metric='private_join')
        call(4, 'GET', f'/libraries/{orion}/context')
        passed('E: librarian rotates, old fails, new works, members remain')
        for path in ('access-code', 'access'):
            body = {'access_code': 'Cross library attempt'} if path == 'access-code' else {'access_mode': 'PUBLIC'}
            call(1, 'PUT', f'/libraries/{orion}/{path}', body, 404)
        call(1, 'GET', f'/libraries/{orion}/memberships', expected=404)
        passed('F: cross-library mutations denied')
        call(2, 'GET', f'/libraries/{orion}/context', expected=404); call(4, 'GET', f'/libraries/{orion}/context')
        passed('G: private-resource guard')
        call(1, 'PUT', f'/libraries/{aurora}/access', {'access_mode': 'PRIVATE_CODE', 'access_code': 'Aurora Private Access Code'})
        call(2, 'GET', f'/libraries/{aurora}/context'); call(6, 'POST', f'/libraries/{aurora}/join', {}, 403)
        passed('H: public to private preserves members')
        call(1, 'PUT', f'/libraries/{aurora}/access', {'access_mode': 'PUBLIC'}); call(6, 'POST', f'/libraries/{aurora}/join', {})
        assert database.institution_security.find_one({'library_id': aurora})['access_code_hash'] is None
        passed('I: private to public clears hash')
        admin_invite = call(3, 'POST', f'/libraries/{orion}/invitations', {'email': 'institution-test-7@example.com', 'role': 'ADMIN'}, 201)
        call(7, 'POST', f'/invitations/{admin_invite["invitation"]["invitation_id"]}/accept', {})
        lib_invite = call(7, 'POST', f'/libraries/{orion}/invitations', {'email': 'institution-test-8@example.com', 'role': 'LIBRARIAN'}, 201)
        call(8, 'POST', f'/invitations/{lib_invite["invitation"]["invitation_id"]}/accept', {})
        call(7, 'POST', f'/libraries/{orion}/invitations', {'email': 'institution-test-9@example.com', 'role': 'ADMIN'}, 403)
        call(8, 'POST', f'/libraries/{orion}/invitations', {'email': 'institution-test-9@example.com', 'role': 'LIBRARIAN'}, 403)
        passed('J: owner/admin/librarian invitation matrix')
        for _ in range(10):
            for label, user, path in [('me_libraries', 4, '/me/libraries'), ('discovery', 2, '/libraries'), ('library_search', 2, '/libraries?search=Hyderabad'),
                                      ('staff_list', 3, f'/libraries/{orion}/memberships'), ('membership_guard', 4, f'/libraries/{orion}/context')]:
                call(user, 'GET', path, metric=label)
        for user in range(30, 35): call(user, 'POST', f'/libraries/{aurora}/join', {}, metric='public_join')
        for user in range(35, 38): call(user, 'POST', f'/libraries/{orion}/join', {'access_code': 'Rotated Orion Institution Code'}, metric='private_join')
        staff = call(3, 'GET', f'/libraries/{orion}/memberships')['results']
        target = next(r for r in staff if r['user_id'] == 8)
        for role in ('GENERAL_USER', 'LIBRARIAN'):
            call(3, 'PATCH', f'/libraries/{orion}/memberships/{target["membership_id"]}', {'role': role}, metric='role_change')
        from backend.services.institution_security import verify_code
        encoded = database.institution_security.find_one({'library_id': orion})['access_code_hash']
        for _ in range(5):
            start = perf_counter(); assert verify_code(encoded, 'Rotated Orion Institution Code')
            metrics.setdefault('code_verify_kdf', []).append(round((perf_counter() - start) * 1000, 3))
        def concurrent(user):
            with httpx.Client(timeout=20) as other:
                results = [other.get(BASE + path, headers=headers[user]) for path in ('/libraries', '/me/libraries', f'/libraries/{orion}/context')]
                return {'user_id': user, 'statuses': [r.status_code for r in results], 'membership_user_ids': [l['membership']['user_id'] for l in results[1].json()['results']]}
        with ThreadPoolExecutor(max_workers=20) as pool: concurrency = list(pool.map(concurrent, range(1, 21)))
        assert all(r['statuses'][:2] == [200, 200] and all(uid == r['user_id'] for uid in r['membership_user_ids']) for r in concurrency)
        with ThreadPoolExecutor(max_workers=20) as pool:
            failed = list(pool.map(lambda _: client.post(BASE + f'/libraries/{orion}/join', headers=headers[45], json={'access_code': 'Wrong concurrent code'}).status_code, range(20)))
        assert failed.count(403) == 5 and failed.count(429) == 15
        # No raw secret may appear in persisted institution records or service logs.
        safe = str(list(database.institution_audit.find({}))) + str(list(database.institution_invitations.find({})))
        assert all(s not in safe for s in ['Orion Private Institution Code', 'Rotated Orion Institution Code', invitation['invite_token']])
        for log in logs: log.flush()
        log_text = (SCRATCH / 'core.log').read_text(encoding='utf8')
        assert invitation['invite_token'] not in log_text and 'Wrong concurrent code' not in log_text
        live = {'status': 'PASS', 'transport': 'real uvicorn + HTTP + MongoDB', 'database': database_name,
                'production_database_modified': False, 'scenarios': records,
                'concurrency': {'workers': 20, 'reads': concurrency, 'private_join_statuses': {str(k): failed.count(k) for k in set(failed)}}}
        (REPORTS / 'institution_v1_live.json').write_text(json.dumps(live, indent=2), encoding='utf8')
        perf = {k: {'samples': len(v), 'mean_ms': round(sum(v) / len(v), 3), 'max_ms': max(v), 'raw_ms': v} for k, v in metrics.items()}
        (REPORTS / 'institution_v1_performance.json').write_text(json.dumps({'local_only': True, 'transport': 'HTTP', 'metrics': perf}, indent=2), encoding='utf8')
        # Browser fixture descriptor deliberately excludes passwords, JWTs, and invitation tokens.
        (SCRATCH / 'fixture.json').write_text(json.dumps({'database': database_name, 'aurora': aurora, 'orion': orion, 'core': BASE, 'frontend': 'http://127.0.0.1:5182'}), encoding='utf8')
        print('Live scenarios A–J and 20-worker isolation: PASS', flush=True)
        if args.serve:
            print('Disposable preview: http://127.0.0.1:5182 . Create .scratch/institution-v1/stop to finish and clean up.', flush=True)
            while not (SCRATCH / 'stop').exists(): sleep(.5)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
        for log in logs: log.close()
        assert database_name.startswith('luminar_institution_live_')
        mongo.drop_database(database_name); mongo.close()
        if (SCRATCH / 'stop').exists(): (SCRATCH / 'stop').unlink()
        print('Disposable database and preview processes cleaned up.', flush=True)


if __name__ == '__main__': main()
