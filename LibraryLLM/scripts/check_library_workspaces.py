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
SCRATCH = ROOT / '.scratch/library-workspaces'
CORE = 'http://127.0.0.1:8084'
FRONTEND = 'http://127.0.0.1:5184'
PASSWORD = 'LuminaR-Workspace-Fixture-123!'


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--serve', action='store_true'); args = parser.parse_args()
    name = 'luminar_workspace_live_' + uuid4().hex
    mongo = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=5000)
    database = mongo[name]; processes = []; logs = []
    SCRATCH.mkdir(parents=True, exist_ok=True); (SCRATCH / 'stop').unlink(missing_ok=True)
    try:
        password_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
        database.users.insert_many([{'user_id': i, 'email': f'workspace-{i}@example.com', 'name': f'Workspace Account {i}', 'password_hash': password_hash,
            'role': 'ADMIN' if i == 1 else 'GENERAL_USER', 'is_active': True, 'is_email_verified': True} for i in [1, 2]])
        env = {**os.environ, 'MONGO_URI': 'mongodb://127.0.0.1:27017', 'MONGO_DB_NAME': name,
            'JWT_SECRET_KEY': secrets.token_urlsafe(48), 'LUMINAR_CORE_API_TARGET': CORE,
            'ISBN_LOOKUP_DB': str(SCRATCH / 'no-isbn.duckdb')}
        for title, command, cwd in [('core', [sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8084'], ROOT),
            ('frontend', ['node', str(ROOT / 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5184', '--strictPort'], ROOT / 'frontend')]:
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
            for i in [1, 2]:
                response = client.post(CORE + '/auth/login', json={'email': f'workspace-{i}@example.com', 'password': PASSWORD})
                response.raise_for_status(); headers[i] = {'Authorization': 'Bearer ' + response.json()['access_token']}
            def call(user, method, path, body=None, expected=200):
                response = client.request(method, CORE + path, headers=headers[user], json=body)
                assert response.status_code == expected, (path, response.status_code, response.text[:400])
                return response.json()
            def command(**body): return {'idempotency_key': str(uuid4()), **body}
            libraries = []
            for title, owner in [('Library A', 1), ('Library B', 2), ('Library C', 2)]:
                row = call(owner, 'POST', '/libraries/register', {'name': title, 'slug': 'workspace-' + uuid4().hex[:12],
                    'library_type': 'PUBLIC_LIBRARY', 'access_mode': 'PUBLIC'}, 201)['library']
                library_id = row['library_id']
                if owner != 1:
                    member = call(1, 'POST', f'/libraries/{library_id}/join', {})['membership']
                    if title == 'Library B': call(2, 'PATCH', f'/libraries/{library_id}/memberships/{member["membership_id"]}', {'role': 'LIBRARIAN'})
                call(owner, 'POST', f'/libraries/{library_id}/staff/lending/activate', command())
                call(owner, 'POST', f'/libraries/{library_id}/staff/reservations-fees/activate', command())
                call(owner, 'POST', f'/libraries/{library_id}/inventory/books', command(title=title + ' Manual', subjects=['Workspace'], copies=1), 201)
                context = call(1, 'GET', f'/libraries/{library_id}/context')
                role = context['membership']['role']
                call(1, 'GET', f'/libraries/{library_id}/staff/fees', expected=403 if role == 'GENERAL_USER' else 200)
                libraries.append({'library_id': library_id, 'name': title, 'role': role})
            assert [row['role'] for row in libraries] == ['ADMIN', 'LIBRARIAN', 'GENERAL_USER']
            report = {'status': 'PASS', 'verified_at': datetime.now(timezone.utc).isoformat(), 'database': name,
                'account_user_id': 1, 'account_global_role': 'ADMIN', 'libraries': libraries,
                'existing_tenant_api_authority_verified': True, 'production_mutations': 0,
                'workspace_policy': 'Frontend workspace navigation and routes; accepted patron API role rules unchanged.'}
            (ROOT / 'reports/library_workspace_live_api.json').write_text(json.dumps(report, indent=2), encoding='utf8')
            (SCRATCH / 'fixture.json').write_text(json.dumps({**report, 'frontend': FRONTEND, 'core': CORE,
                'email': 'workspace-1@example.com', 'password': PASSWORD}), encoding='utf8')
            print('Workspace fixture ready: one global ADMIN account; Library A ADMIN, B LIBRARIAN, C GENERAL_USER.', flush=True)
            if args.serve:
                while not (SCRATCH / 'stop').exists(): sleep(.25)
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
                try: p.wait(timeout=10)
                except subprocess.TimeoutExpired: p.kill(); p.wait(timeout=10)
        for log in logs: log.close()
        assert name.startswith('luminar_workspace_live_')
        mongo.drop_database(name)
        cleanup = {'fixture_database': name, 'fixture_database_dropped': name not in mongo.list_database_names(),
            'own_services_stopped': all(p.poll() is not None for p in processes), 'production_modified': False}
        (ROOT / 'reports/library_workspace_cleanup.json').write_text(json.dumps(cleanup, indent=2), encoding='utf8')
        mongo.close(); (SCRATCH / 'stop').unlink(missing_ok=True)


if __name__ == '__main__': main()
