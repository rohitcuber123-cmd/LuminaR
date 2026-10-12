"""One global account, three tenant roles; isolated HTTP and browser fixture."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from time import sleep
from uuid import uuid4
import bcrypt
import httpx
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / '.scratch/dashboard-convergence'
CORE = 'http://127.0.0.1:8086'
FRONTEND = 'http://127.0.0.1:5186'
PASSWORD = 'LuminaR-Workspace-Fixture-123!'


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--serve', action='store_true'); args = parser.parse_args()
    name = 'luminar_dc_live_' + uuid4().hex
    mongo = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=5000)
    database = mongo[name]; processes = []; logs = []
    SCRATCH.mkdir(parents=True, exist_ok=True); (SCRATCH / 'stop').unlink(missing_ok=True)
    try:
        password_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
        database.users.insert_many([{'user_id': i, 'email': f'workspace-{i}@example.com', 'name': f'Workspace Account {i}', 'password_hash': password_hash,
            'role': 'ADMIN' if i == 1 else 'LIBRARIAN' if i == 4 else 'GENERAL_USER', 'is_active': True, 'is_email_verified': True} for i in [1, 2, 3, 4, 5, 6]])
        database.platform_role_assignments.insert_one({'user_id':5,'role':'PLATFORM_ADMIN','status':'ACTIVE','approval_ref':'ISOLATED-TEST','approved_by':'fixture-operator','approved_at':datetime.now(timezone.utc)})
        database.books.insert_many([{'book_id':i,'work_id':f'TEST-WORK-{i}','title':f'Global Reference {i}','authors':'Fixture Author','subjects':'Systems','total_copies':0,'available_copies':0} for i in range(1,4)])
        env = {**os.environ, 'MONGO_URI': 'mongodb://127.0.0.1:27017', 'MONGO_DB_NAME': name,
            'JWT_SECRET_KEY': secrets.token_urlsafe(48), 'LUMINAR_CORE_API_TARGET': CORE,
            'ISBN_LOOKUP_DB': str(SCRATCH / 'no-isbn.duckdb')}
        for title, command, cwd in [('core', [sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8086'], ROOT),
            ('frontend', ['node', str(ROOT / 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5186', '--strictPort'], ROOT / 'frontend')]:
            log = (SCRATCH / f'{title}.log').open('w', encoding='utf8'); logs.append(log)
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0))
        with httpx.Client(timeout=60) as client:
            for _ in range(120):
                if any(p.poll() is not None for p in processes): raise RuntimeError('Fixture service failed; inspect its .scratch logs.')
                try:
                    if client.get(CORE + '/health').is_success and client.get(FRONTEND).is_success: break
                except httpx.HTTPError: pass
                sleep(.25)
            else: raise RuntimeError('Fixture startup timed out.')
            headers = {}
            for i in [1, 2, 3, 4, 5, 6]:
                response = client.post(CORE + '/auth/login', json={'email': f'workspace-{i}@example.com', 'password': PASSWORD})
                response.raise_for_status(); headers[i] = {'Authorization': 'Bearer ' + response.json()['access_token']}
            def call(user, method, path, body=None, expected=200):
                response = client.request(method, CORE + path, headers=headers[user], json=body)
                assert response.status_code == expected, (path, response.status_code, response.text[:400])
                return response.json()
            def command(**body): return {'idempotency_key': str(uuid4()), **body}
            libraries = []
            for title, owner in [('Library A', 1), ('Library B', 2), ('Library C', 2), ('Library D', 2), ('Library E', 2)]:
                row = call(owner, 'POST', '/libraries/register', {'name': title, 'slug': 'workspace-' + uuid4().hex[:12],
                    'library_type': 'PUBLIC_LIBRARY', 'access_mode': 'PUBLIC'}, 201)['library']
                library_id = row['library_id']
                if owner != 1:
                    member = call(1, 'POST', f'/libraries/{library_id}/join', {})['membership']
                    if title in ['Library C', 'Library E']: call(2, 'PATCH', f'/libraries/{library_id}/memberships/{member["membership_id"]}', {'role': 'LIBRARIAN'})
                call(owner, 'POST', f'/libraries/{library_id}/staff/lending/activate', command())
                call(owner, 'POST', f'/libraries/{library_id}/staff/reservations-fees/activate', command())
                call(owner, 'POST', f'/libraries/{library_id}/inventory/books', command(title=title + ' Manual', subjects=['Systems'], copies=3, shelf_location='Room 2 / Shelf A'), 201)
                context = call(1, 'GET', f'/libraries/{library_id}/context')
                role = context['membership']['role']
                call(1, 'GET', f'/libraries/{library_id}/staff/fees', expected=403 if role == 'GENERAL_USER' else 200)
                libraries.append({'library_id': library_id, 'name': title, 'role': role})
            library_b = libraries[1]['library_id']
            call(3, 'POST', f'/libraries/{library_b}/join', {})
            book_b = call(3, 'GET', f'/libraries/{library_b}/inventory/books')['results'][0]
            req = call(3, 'POST', f'/libraries/{library_b}/lending/borrow-requests', command(library_book_id=book_b['library_book_id']), expected=201)
            loan = call(2, 'POST', f"/libraries/{library_b}/staff/lending/borrow-requests/{req['lending_request_id']}/approve", command())
            call(3, 'POST', f"/libraries/{library_b}/loans/{loan['loan_id']}/return-request", command(), expected=201)
            call(1, 'POST', f'/libraries/{library_b}/lending/borrow-requests', command(library_book_id=book_b['library_book_id']), expected=201)
            for row in [libraries[0], libraries[2]]:
                lid = row['library_id']; book = call(1, 'GET', f'/libraries/{lid}/inventory/books')['results'][0]
                call(1, 'POST', f'/libraries/{lid}/lending/borrow-requests', command(library_book_id=book['library_book_id']), expected=403)
                call(1, 'GET', f'/libraries/{lid}/me/loans', expected=403)
                call(1, 'GET', f'/libraries/{lid}/staff/loans')
            assert [row['role'] for row in libraries] == ['ADMIN', 'GENERAL_USER', 'LIBRARIAN', 'GENERAL_USER', 'LIBRARIAN']
            single=call(6,'POST','/libraries/register',{'name':'Library F','slug':'single-'+uuid4().hex[:12],'library_type':'PUBLIC_LIBRARY','access_mode':'PUBLIC'},201)['library']
            library_a=libraries[0]['library_id']
            call(3,'POST',f'/libraries/{library_a}/join',{})
            book_a=call(3,'GET',f'/libraries/{library_a}/inventory/books')['results'][0]
            pending_a=call(3,'POST',f'/libraries/{library_a}/lending/borrow-requests',command(library_book_id=book_a['library_book_id']),expected=201)
            active_a=call(1,'POST',f'/libraries/{library_a}/staff/lending/borrow-requests/{pending_a["lending_request_id"]}/approve',command())
            event=call(5,'POST','/platform/events',{'title':'Global Systems Workshop','category':'OTHER','summary':'Installation announcement','description':'A global platform event.'},201)
            call(5,'POST',f'/platform/events/{event["event_id"]}/publish',None)
            assert call(4,'GET','/me/platform-access')['roles']==[]
            call(4,'GET','/platform/accounts',expected=403)
            call(5,'GET',f'/libraries/{library_a}/staff/loans',expected=404)
            report = {'single_staff_library':single['library_id'],'staff_assisted_loan':active_a['loan_id'],'status': 'PASS', 'verified_at': datetime.now(timezone.utc).isoformat(), 'database': name,
                'account_user_id': 1, 'account_global_role': 'ADMIN', 'libraries': libraries,
                'existing_tenant_api_authority_verified': True, 'production_mutations': 0,
                'workspace_policy': 'Active GENERAL_USER patron endpoints; ADMIN/LIBRARIAN operational endpoints. Separate route contexts.'}
            (ROOT / 'reports/dashboard_convergence_live_api.json').write_text(json.dumps(report, indent=2), encoding='utf8')
            (SCRATCH / 'fixture.json').write_text(json.dumps({**report, 'frontend': FRONTEND, 'core': CORE,
                'email': 'workspace-1@example.com', 'password': PASSWORD, 'owned_pids': [p.pid for p in processes]}), encoding='utf8')
            print('Workspace fixture ready: one global ADMIN account; Library A ADMIN, B GENERAL_USER, C LIBRARIAN, D GENERAL_USER, E LIBRARIAN.', flush=True)
            if args.serve:
                while not (SCRATCH / 'stop').exists(): sleep(.25)
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
                try: p.wait(timeout=10)
                except subprocess.TimeoutExpired: p.kill(); p.wait(timeout=10)
        for log in logs: log.close()
        assert name.startswith('luminar_dc_live_')
        mongo.drop_database(name)
        cleanup = {'fixture_database': name, 'fixture_database_dropped': name not in mongo.list_database_names(),
            'own_services_stopped': all(p.poll() is not None for p in processes), 'production_modified': False}
        (ROOT / 'reports/dashboard_convergence_cleanup.json').write_text(json.dumps(cleanup, indent=2), encoding='utf8')
        mongo.close(); (SCRATCH / 'stop').unlink(missing_ok=True)


if __name__ == '__main__': main()
