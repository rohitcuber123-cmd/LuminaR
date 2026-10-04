"""Batch 5C/5D: real Core and standalone worker processes, isolated Mongo DB.

No FAISS/Search process is started. The fixture owns and removes its database,
queue and lexical files. Credentials are generated in memory for normal login.
"""
import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')


def ensure(condition, message):
    if not condition:
        raise AssertionError(message)


def port_number():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def request(port, method, path, data=None, token=None):
    body = None if data is None else json.dumps(data).encode()
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request('http://127.0.0.1:' + str(port) + path,
                                 data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, None


def wait_for(predicate, description, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.15)
    raise AssertionError('Timed out: ' + description)


def stop(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=8)


def main():
    name = 'luminar_batch5cd_' + uuid.uuid4().hex
    ensure(name.startswith('luminar_batch5cd_'), 'Unsafe test database name')
    work_id = 'TESTLEX' + uuid.uuid4().hex.upper()
    email = 'batch5cd-' + uuid.uuid4().hex + '@example.com'
    password = 'Random test credential ' + uuid.uuid4().hex
    signing_key = 'isolated-signing-key-' + uuid.uuid4().hex
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
    core = worker = None
    with tempfile.TemporaryDirectory(prefix='luminar-batch5cd-') as temporary:
        fixture = Path(temporary)
        lexical_root = fixture / 'lexical'
        lexical_root.mkdir()
        queue_root = fixture / 'queue'
        environment = os.environ.copy()
        environment.update(MONGO_DB_NAME=name,
                           LUMINAR_SEARCH_INDEX_DIR=str(queue_root),
                           LUMINAR_LEXICAL_PATH=str(lexical_root),
                           JWT_SECRET_KEY=signing_key,
                           LEXICAL_SEARCH_ENABLED='false',
                           LUMINAR_LEXICAL_SYNC_ENABLED='false')
        # Parent imports bind to the same isolated source before any Core module.
        os.environ.update(environment)
        from backend.services.auth_service import hash_password
        from search.lexical_build import build_snapshot
        from search.lexical_delta import initialize_delta, LexicalOverlayStore
        from search.sync_queue import SyncQueue

        with MongoClient(mongo_uri, serverSelectionTimeoutMS=3000) as mongo:
            mongo.admin.command('ping')
            database = mongo[name]
            queue = SyncQueue(queue_root)
            manifest = build_snapshot([{'work_id': 'BASE_FIXTURE',
                                        'title': 'Base fixture',
                                        'authors': ['Fixture author']}],
                                       lexical_root, source_db=name)
            initialize_delta(lexical_root, manifest, 0, queue)
            database.users.insert_one({'user_id': 1, 'name': 'Isolated admin',
                                       'email': email, 'password_hash': hash_password(password),
                                       'role': 'ADMIN', 'is_email_verified': True,
                                       'is_active': True})
            port = port_number()

            def start_core():
                nonlocal core
                core = subprocess.Popen([sys.executable, '-m', 'uvicorn',
                                         'backend.main:app', '--host', '127.0.0.1',
                                         '--port', str(port), '--no-access-log'],
                                        cwd=ROOT, env=environment, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
                def healthy():
                    ensure(core.poll() is None, 'Core exited during startup')
                    try:
                        return request(port, 'GET', '/health')[0] == 200
                    except (OSError, ValueError):
                        return False
                wait_for(healthy, 'Core healthy', 30)

            def start_worker():
                nonlocal worker
                worker_env = environment.copy()
                worker_env['LUMINAR_LEXICAL_SYNC_ENABLED'] = 'true'
                worker = subprocess.Popen([sys.executable,
                                           str(ROOT / 'scripts' / 'lexical_worker.py'),
                                           '--apply', '--poll-seconds', '.2',
                                           '--root', str(lexical_root)],
                                          cwd=ROOT, env=worker_env,
                                          stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL)
                time.sleep(.5)
                ensure(worker.poll() is None, 'Standalone lexical worker exited')

            def state():
                reader = LexicalOverlayStore(lexical_root, expected_source_db=name,
                                             event_queue=queue)
                try:
                    return reader.health()
                finally:
                    reader.close()

            def exact(kind, value):
                reader = LexicalOverlayStore(lexical_root, expected_source_db=name,
                                             event_queue=queue)
                try:
                    return [wid for _, wid in reader.exact(kind, value)]
                finally:
                    reader.close()

            def tombstones():
                with closing(sqlite3.connect(lexical_root / 'lexical_delta.sqlite3')) as db:
                    return db.execute('SELECT count(*) FROM overrides WHERE deleted=1').fetchone()[0]

            def settled(sequence):
                wait_for(lambda: state()['lexical_source_event_checkpoint'] == sequence,
                         'lexical checkpoint ' + str(sequence))
                ensure(not state()['lexical_pending'], 'Lexical event remained pending')

            def call(method, path, data=None):
                status, result = request(port, method, path, data, token)
                ensure(status == 200, method + ' ' + path + ' returned ' + str(status))
                return result

            try:
                start_core()
                start_worker()
                ensure(request(port, 'POST', '/books/', {'work_id': work_id,
                       'title': 'Unauthorized'})[0] in (401, 403),
                       'Unauthenticated mutation was allowed')
                status, login = request(port, 'POST', '/auth/staff-login',
                                        {'email': email, 'password': password})
                ensure(status == 200 and login and login.get('access_token'),
                       'Normal staff login failed')
                token = login['access_token']

                # 5C: one synthetic book, normal authenticated Core routes.
                call('POST', '/books/', {'work_id': work_id,
                     'title': 'Synthetic First Title',
                     'authors': 'Synthetic First Author',
                     'description': 'Synthetic description',
                     'total_copies': 1, 'available_copies': 1})
                settled(1)
                ensure(exact('TITLE', 'Synthetic First Title') == [work_id], 'Create title missing')
                ensure(exact('AUTHOR', 'Synthetic First Author') == [work_id], 'Create author missing')
                generation = state()['lexical_generation']
                call('PUT', '/books/' + work_id, {'available_copies': 0})
                ensure(queue.latest() == 1 and state()['lexical_generation'] == generation,
                       'Inventory-only update emitted lexical event')
                call('PUT', '/books/' + work_id, {'title': 'Synthetic Revised Title'})
                settled(2)
                ensure(exact('TITLE', 'Synthetic First Title') == [] and
                       exact('TITLE', 'Synthetic Revised Title') == [work_id],
                       'Old title not suppressed')
                call('PUT', '/books/' + work_id, {'authors': 'Synthetic Revised Author'})
                settled(3)
                ensure(exact('AUTHOR', 'Synthetic First Author') == [] and
                       exact('AUTHOR', 'Synthetic Revised Author') == [work_id],
                       'Old author not suppressed')
                generation = state()['lexical_generation']
                call('PUT', '/books/' + work_id, {'description': 'Description only changed'})
                settled(4)
                ensure(state()['lexical_generation'] == generation,
                       'Description-only update changed lexical generation')
                call('DELETE', '/books/' + work_id)
                settled(5)
                ensure(exact('TITLE', 'Synthetic Revised Title') == [] and
                       exact('AUTHOR', 'Synthetic Revised Author') == [],
                       'Deleted values remained visible')
                ensure(state()['lexical_available'], 'Lexical overlay unavailable')
                ensure(database.books.count_documents({'work_id': work_id}) == 0,
                       '5C book remained in Mongo')
                ensure(tombstones() == 1, '5C delete tombstone missing')
                batch5c = {'status': 'PASS', 'queue_latest': 5,
                           'checkpoint': state()['lexical_source_event_checkpoint'],
                           'generation': state()['lexical_generation'],
                           'tombstones': tombstones()}

                # 5D: same disposable ID, outage and restart sequence.
                call('POST', '/books/', {'work_id': work_id,
                     'title': 'Outage Initial Title', 'authors': 'Outage Initial Author'})
                settled(6)
                stop(worker)
                worker = None
                call('PUT', '/books/' + work_id, {'title': 'Outage Intermediate Title'})
                call('PUT', '/books/' + work_id, {'title': 'Outage Latest Title'})
                ensure(queue.latest() == 8 and
                       state()['lexical_source_event_checkpoint'] == 6 and
                       state()['lexical_pending'], 'Worker outage did not leave event pending')
                start_worker()
                settled(8)
                ensure(exact('TITLE', 'Outage Initial Title') == [] and
                       exact('TITLE', 'Outage Intermediate Title') == [] and
                       exact('TITLE', 'Outage Latest Title') == [work_id],
                       'Replay did not use latest Mongo title')
                stop(core)
                core = None
                start_core()
                call('PUT', '/books/' + work_id, {'authors': 'After Core Restart Author'})
                settled(9)
                ensure(exact('AUTHOR', 'Outage Initial Author') == [] and
                       exact('AUTHOR', 'After Core Restart Author') == [work_id],
                       'Core restart update was not replayed')
                stop(worker)
                worker = None
                start_worker()
                call('DELETE', '/books/' + work_id)
                settled(10)
                ensure(exact('TITLE', 'Outage Latest Title') == [] and
                       exact('AUTHOR', 'After Core Restart Author') == [],
                       'Delete tombstone not effective after worker restart')
                ensure(database.books.count_documents({'work_id': work_id}) == 0,
                       '5D book remained in Mongo')
                ensure(tombstones() == 1, '5D delete tombstone missing')
                batch5d = {'status': 'PASS', 'queue_latest': 10,
                           'checkpoint': state()['lexical_source_event_checkpoint'],
                           'pending': state()['lexical_pending'],
                           'tombstones': tombstones()}
                return {'database': 'isolated', 'core_process': True,
                        'standalone_worker_process': True, 'faiss_loaded': False,
                        'batch_5c': batch5c, 'batch_5d': batch5d,
                        'cleanup': 'PASS'}
            finally:
                stop(worker)
                stop(core)
                ensure(name.startswith('luminar_batch5cd_'), 'Unsafe drop target')
                mongo.drop_database(name)


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
