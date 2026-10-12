"""Disposable UI QA with real login and read-only access to global metadata.

The supplied development password is runtime input only. Platform authority
exists only in this uniquely named fixture database, never in production.
"""
from datetime import datetime, timezone
import getpass
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
SCRATCH = ROOT / '.scratch/product-ui-fixture'
CORE = 'http://127.0.0.1:8089'
FRONTEND = 'http://127.0.0.1:5189'


def main():
    password = getpass.getpass('Development password for disposable QA accounts (runtime only): ')
    name = 'luminar_product_ui_' + uuid4().hex
    mongo = MongoClient('mongodb://127.0.0.1:27017')
    database = mongo[name]
    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / 'stop').unlink(missing_ok=True)
    processes, logs = [], []
    try:
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
        database.users.insert_many([{'user_id': i, 'email': f'product-qa-{i}@example.com',
            'name': f'Product QA {i}', 'password_hash': hashed, 'role': 'GENERAL_USER',
            'is_active': True, 'is_email_verified': True} for i in (1, 2, 5)])
        database.platform_role_assignments.insert_one({'user_id': 5, 'role': 'PLATFORM_ADMIN',
            'status': 'ACTIVE', 'approval_ref': 'ISOLATED-UI-QA', 'approved_by': 'fixture-operator',
            'approved_at': datetime.now(timezone.utc)})
        wrapper = SCRATCH / 'live_core.py'
        wrapper.write_text('import sys\nsys.path.insert(0, ' + repr(str(ROOT)) + ')\n' + '''
from backend.main import app
from backend.services import book_service
from backend.database.mongodb import client
class ReadOnly:
    def __init__(self, collection): self.collection = collection
    def __getattr__(self, name):
        if name not in {'find', 'find_one', 'aggregate', 'estimated_document_count', 'count_documents'}:
            raise RuntimeError('Fixture prohibits global metadata writes')
        return getattr(self.collection, name)
book_service.books_collection = ReadOnly(client['luminar_library']['books'])
book_service.book_categories_collection = ReadOnly(client['luminar_library']['book_categories'])
''', encoding='utf8')
        env = {**os.environ, 'MONGO_URI': 'mongodb://127.0.0.1:27017', 'MONGO_DB_NAME': name,
            'JWT_SECRET_KEY': secrets.token_urlsafe(48), 'LUMINAR_CORE_API_TARGET': CORE,
            'ISBN_LOOKUP_DB': str(SCRATCH / 'no-isbn.duckdb')}
        for title, command, cwd in [
            ('core', [sys.executable, '-m', 'uvicorn', 'live_core:app', '--app-dir', str(SCRATCH),
                '--host', '127.0.0.1', '--port', '8089'], ROOT),
            ('frontend', ['node', str(ROOT / 'frontend/node_modules/vite/bin/vite.js'),
                '--host', '127.0.0.1', '--port', '5189', '--strictPort'], ROOT / 'frontend')]:
            log = (SCRATCH / (title + '.log')).open('w', encoding='utf8'); logs.append(log)
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0))
        with httpx.Client(timeout=90) as client:
            for _ in range(120):
                if any(p.poll() is not None for p in processes): raise RuntimeError('Fixture startup failed.')
                try:
                    if client.get(CORE + '/health').is_success and client.get(FRONTEND).is_success: break
                except httpx.HTTPError: pass
                sleep(.25)
            else: raise RuntimeError('Fixture startup timed out.')
            headers = {}
            for i in (1, 2, 5):
                response = client.post(CORE + '/auth/login', json={'email': f'product-qa-{i}@example.com', 'password': password})
                response.raise_for_status(); headers[i] = {'Authorization': 'Bearer ' + response.json()['access_token']}
            libraries = []
            for label in ('Add', 'Import'):
                response = client.post(CORE + '/libraries/register', headers=headers[1], json={
                    'name': 'QA ' + label, 'slug': 'product-' + label.lower() + '-' + uuid4().hex[:12],
                    'library_type': 'PUBLIC_LIBRARY', 'access_mode': 'PUBLIC'})
                response.raise_for_status(); library = response.json()['library']; lid = library['library_id']
                client.post(CORE + '/libraries/' + lid + '/join', headers=headers[2], json={}).raise_for_status()
                source = client.get(CORE + '/libraries/' + lid + '/catalogue/source', headers=headers[2])
                source.raise_for_status(); assert source.json()['catalogue_source'] == 'GLOBAL_FALLBACK'
                assert source.json()['circulation_state'] == 'CANONICAL'
                libraries.append({**library, 'source_before': source.json()})
            report = {'status': 'READY', 'database': name, 'core': CORE, 'frontend': FRONTEND,
                'libraries': libraries, 'production_platform_assignments_created': 0,
                'normal_login': True, 'owned_pids': [p.pid for p in processes]}
            (ROOT / 'reports/product_consistency_live_fixture.json').write_text(json.dumps(report, indent=2), encoding='utf8')
            (SCRATCH / 'sample.csv').write_text('title,subjects,copies,shelf_location\nQA Import Networks Manual,Networks,2,QA-02\n', encoding='utf8')
            print('Disposable fixture ready: Add and Import libraries plus an isolated Platform account.', flush=True)
            while not (SCRATCH / 'stop').exists(): sleep(.25)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
        for log in logs: log.close()
        assert name.startswith('luminar_product_ui_')
        mongo.drop_database(name)
        cleanup = {'fixture_database': name, 'database_dropped': name not in mongo.list_database_names(),
            'owned_services_stopped': all(p.poll() is not None for p in processes), 'test_library_removed': False,
            'production_platform_authority_changed': False}
        (ROOT / 'reports/product_consistency_fixture_cleanup.json').write_text(json.dumps(cleanup, indent=2), encoding='utf8')
        mongo.close()


if __name__ == '__main__': main()
