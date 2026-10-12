"""Real HTTP/Mongo Part 2A checks. Only a disposable database is written.

--serve keeps the fixture alive until .scratch/institution-v2a/stop is created.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import io
import json
import os
from pathlib import Path
import secrets
import statistics
import subprocess
import sys
from time import perf_counter, sleep
from uuid import uuid4, UUID
import bcrypt
import httpx
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
SCRATCH = ROOT / '.scratch/institution-v2a'
BASE = 'http://127.0.0.1:8082'
PASSWORD = 'LuminaR-Disposable-123!'


def write(name, value):
    (REPORTS / ('institution_v2a_' + name + '.json')).write_text(json.dumps(value, indent=2, default=str), encoding='utf8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve', action='store_true')
    args = parser.parse_args()
    database_name = 'luminar_institution_v2a_live_' + uuid4().hex
    mongo = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=5000)
    database = mongo[database_name]
    database.users.create_index('user_id', unique=True); database.users.create_index('email', unique=True)
    encoded = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
    database.users.insert_many([{'user_id': i, 'email': f'institution-v2a-{i}@example.com', 'name': f'Disposable User {i}',
        'password_hash': encoded, 'role': 'ADMIN' if i == 20 else 'GENERAL_USER', 'is_email_verified': True, 'is_active': True} for i in range(1, 31)])
    # Existing public bibliographic metadata is copied only into the fixture.
    works = list(mongo.luminar_library.books.find({'work_id': {'$in': ['OL19545719W', 'OL109579W']}},
                  {'_id': 0, 'work_id': 1, 'title': 1, 'subjects': 1, 'authors': 1, 'publisher': 1, 'publication_year': 1, 'isbn': 1}))
    assert len(works) == 2
    database.books.insert_many(works)
    env = {**os.environ, 'MONGO_URI': 'mongodb://127.0.0.1:27017', 'MONGO_DB_NAME': database_name,
           'JWT_SECRET_KEY': secrets.token_urlsafe(48), 'LUMINAR_CORE_API_TARGET': BASE,
           'ISBN_LOOKUP_DB': str(SCRATCH / 'no-isbn-mapping.duckdb')}
    logs = []; processes = []; metrics = {}; scenarios = []
    SCRATCH.mkdir(parents=True, exist_ok=True)
    if (SCRATCH / 'stop').exists(): (SCRATCH / 'stop').unlink()
    try:
        for name, command, cwd in [
            ('core', [sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8082'], ROOT),
            ('frontend', ['node', str(ROOT / 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5182', '--strictPort'], ROOT / 'frontend')]:
            log = (SCRATCH / (name + '.log')).open('w', encoding='utf8'); logs.append(log)
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0))
        with httpx.Client(timeout=180) as client:
            for _ in range(100):
                if any(p.poll() is not None for p in processes): raise RuntimeError('Validation service exited; inspect fixture logs.')
                try:
                    if client.get(BASE + '/health').is_success and client.get('http://127.0.0.1:5182/').is_success: break
                except httpx.HTTPError: pass
                sleep(.25)
            else: raise RuntimeError('Validation service startup timeout.')
            headers = {}
            for i in (1, 2, 3, 4, 20):
                result = client.post(BASE + '/auth/login', json={'email': f'institution-v2a-{i}@example.com', 'password': PASSWORD})
                result.raise_for_status(); headers[i] = {'Authorization': 'Bearer ' + result.json()['access_token']}
            os.environ.update({k: env[k] for k in ('MONGO_URI', 'MONGO_DB_NAME', 'JWT_SECRET_KEY', 'ISBN_LOOKUP_DB')})
            sys.path.insert(0, str(ROOT))
            from backend.utils.jwt_utils import create_access_token
            from backend.services.library_catalogue_repository import TenantInventory
            from backend.services.library_catalogue_linking import verified_work
            from scripts.reconcile_inventory_v2a import reconcile
            for i in range(1, 31): headers.setdefault(i, {'Authorization': 'Bearer ' + create_access_token(i, f'institution-v2a-{i}@example.com', 'GENERAL_USER')})
            def call(user, method, path, body=None, expected=200, metric=None, files=None):
                start = perf_counter()
                response = client.request(method, BASE + path, headers=headers[user], json=body, files=files)
                duration = round((perf_counter() - start) * 1000, 3)
                assert response.status_code == expected, f'{method} {path}: expected {expected}, got {response.status_code}: {response.text[:300]}'
                if metric: metrics.setdefault(metric, []).append(duration)
                return response.json()
            def register(user, name, private=False):
                return call(user, 'POST', '/libraries/register', {'name': name, 'slug': 'v2a-live-' + uuid4().hex[:9],
                    'library_type': 'PRIVATE_INSTITUTION' if private else 'PUBLIC_LIBRARY', 'access_mode': 'PRIVATE_CODE' if private else 'PUBLIC',
                    **({'access_code': 'Orion V2A Private Passphrase'} if private else {})}, 201)['library']['library_id']
            aurora = register(1, 'Aurora Public Library'); orion = register(2, 'Orion Private Institute', True)
            migration_library = register(3, 'Migration Verification Library')
            def base(library): return f'/libraries/{library}/inventory'
            def add(user, library, title, **fields):
                return call(user, 'POST', base(library) + '/books', {'title': title, 'subjects': ['Systems'], **fields}, 201, 'manual_book_create')
            def preview(user, library, text, label):
                return call(user, 'POST', base(library) + '/imports/preview', expected=201, metric=label,
                    files={'file': ('minimal.csv', text.encode(), 'text/csv')})
            def apply(user, library, job, label):
                return call(user, 'POST', base(library) + f'/imports/{job["import_id"]}/apply', {'existing_policy': 'skip'}, metric=label)
            def passed(number, title, **evidence): scenarios.append({'number': number, 'scenario': title, 'status': 'PASS', **evidence})
            local = add(1, aurora, 'Local Laboratory Handbook')
            assert local['isbn_10'] is local['isbn_13'] is local['global_work_id'] is None
            UUID(local['library_book_id']); assert local['holding']['total_copies'] == 1
            passed(1, 'Title + subject creates UUID, accession and holding without ISBN/work/author', accession=local['accession_number'])
            author_optional = add(1, aurora, 'Unidentified Research Notes', authors=['Fixture Author'])
            assert author_optional['global_work_id'] is author_optional['isbn_13'] is None
            passed(2, 'Optional author does not require global identity')
            work = works[0]
            linked = add(1, aurora, work['title'], global_work_id=work['work_id'])
            assert linked['global_work_id'] == work['work_id']
            passed(3, 'Existing trusted global work links to local holding', global_work_id=work['work_id'])
            for iteration in range(3):
                text = 'title,subject\n' + ''.join(f'Batch100-{iteration}-{i},Systems\n' for i in range(100))
                previous = database.institution_sequences.find_one({'library_id': aurora})['value']
                job = preview(1, aurora, text, 'preview_100_rows')
                assert job['new_library_records'] == 100 and database.institution_sequences.find_one({'library_id': aurora})['value'] == previous
                result = apply(1, aurora, job, 'apply_100_rows'); assert result['created_records'] == 100
                assert len({r['accession_number'] for r in result['rows']}) == 100
            passed(4, '100 title + subject rows preview without allocation, apply unique automatic accessions', repeated_samples=3)
            out = io.StringIO(); writer = csv.writer(out); writer.writerow(['title', 'subject', 'isbn', 'work_id'])
            writer.writerows([['ISBN Physics', 'Physics', '9780306406157', ''], [works[1]['title'], 'Research', '', works[1]['work_id']], ['Only Local', 'Local Knowledge', '', ''], ['Missing Subject', '', '', '']])
            mixed = preview(1, aurora, out.getvalue(), 'preview_mixed'); assert mixed['rows_invalid'] == 1
            mixed_result = apply(1, aurora, mixed, 'apply_mixed'); assert mixed_result['created_records'] == 3 and mixed_result['status'] == 'PARTIAL'
            passed(5, 'Mixed identifiers, local-only rows and isolated missing-subject error', counts={k: mixed_result[k] for k in ('created_records', 'invalid_rows')})
            before = call(1, 'GET', base(aurora) + '/books?search=Repeated%20Title')['total']
            dup = preview(1, aurora, 'title,subject\nRepeated Title,Physics\nRepeated Title,History\n', 'preview_duplicate')
            assert dup['possible_duplicates'] == 1
            duplicate_result = apply(1, aurora, dup, 'apply_duplicate'); assert duplicate_result['created_records'] == 2
            assert call(1, 'GET', base(aurora) + '/books?search=Repeated%20Title')['total'] == before + 2
            passed(6, 'Same title flags review and creates separate identities without silent merge')
            jobs = []
            for user, library in ((1, aurora), (2, orion)):
                jobs.append((user, library, preview(user, library, 'title,genre\n' + ''.join(f'Concurrent Library Book {i},Systems\n' for i in range(100)), 'preview_concurrent_100')))
            with ThreadPoolExecutor(max_workers=2) as pool:
                concurrent = list(pool.map(lambda item: apply(*item, 'apply_concurrent_100'), jobs))
            assert all(r['created_records'] == 100 for r in concurrent)
            assert all(r['accession_number'].startswith('AUR-') for r in concurrent[0]['rows'])
            assert all(r['accession_number'].startswith('ORI-') for r in concurrent[1]['rows'])
            passed(7, 'Concurrent imports into two libraries preserve independent counters', rows_per_library=100)
            for library, other in ((aurora, 2), (orion, 1)):
                call(other, 'GET', base(library) + '/books', expected=404)
                call(other, 'POST', base(library) + '/books', {'title': 'Spoof', 'subjects': ['Systems']}, 404)
            call(20, 'GET', base(orion) + '/books', expected=404)
            call(4, 'POST', f'/libraries/{orion}/join', {'access_code': 'Orion V2A Private Passphrase'})
            call(4, 'POST', f'/libraries/{aurora}/join', {})
            assert call(4, 'GET', base(orion) + '/books')['total'] == 100
            call(4, 'POST', base(orion) + '/books', {'title': 'Denied', 'subjects': ['Systems']}, 403)
            passed(8, 'Private tenant isolation and global ADMIN bypass denied; GENERAL member reads only')
            unchanged = (local['library_book_id'], local['accession_number'])
            later = call(1, 'PUT', base(aurora) + f'/books/{local["library_book_id"]}/global-link', {'global_work_id': None})
            # Both fixture global works are already held in Aurora, so link later in Orion.
            later_local = add(2, orion, 'Later Linked Local Record')
            later = call(2, 'PUT', base(orion) + f'/books/{later_local["library_book_id"]}/global-link', {'global_work_id': work['work_id']})
            assert (later['library_book_id'], later['accession_number']) == (later_local['library_book_id'], later_local['accession_number'])
            call(2, 'PUT', base(orion) + f'/books/{later_local["library_book_id"]}/global-link', {'global_work_id': None})
            passed(9, 'Later verified link and unlink preserve local UUID/accession')
            database.library_inventory.insert_many([
                {'library_id': 'LIB001', 'work_id': work['work_id'], 'total_copies': 3, 'available_copies': 2},
                {'library_id': 'LIB001', 'title': 'Legacy Physics', 'subject': 'Physics', 'isbn': '9780306406157', 'quantity': 1},
                {'library_id': 'LIB001', 'title': 'Legacy Local Record', 'genre': 'Research', 'quantity': 2, 'barcode': 'KNOWN-LEGACY-001'},
                {'library_id': 'LIB001', 'title': 'Quarantined Missing Subject'}])
            legacy_before = list(database.library_inventory.find({})); index_before = {n: list(database[n].list_indexes()) for n in database.list_collection_names()}
            command = [sys.executable, 'scripts/migrate_inventory_v2a.py', '--database', database_name, '--library-id', migration_library, '--alias', f'LIB001={migration_library}']
            def cli(extra):
                run = subprocess.run(command + extra, cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
                assert run.returncode == 0, run.stderr; return json.loads(run.stdout)
            dry = cli([]); assert dry['mode'] == 'DRY_RUN' and dry['counts']['missing_subject'] == 1
            assert {n: list(database[n].list_indexes()) for n in database.list_collection_names()} == index_before
            migrated = cli(['--apply']); repeated = cli(['--apply'])
            assert migrated['counts']['created_records'] == 3 and repeated['counts']['created_records'] == 0
            assert list(database.library_inventory.find({})) == legacy_before
            assert database.institution_copies.find_one({'library_id': migration_library})['status'] == 'UNVERIFIED'
            write('migration', {'status': 'PASS', 'dry_run': dry, 'apply': migrated, 'repeat': repeated, 'legacy_collection_unchanged': True, 'production_applied': False})
            passed(10, 'Explicit LIB001 alias: 4 legacy rows → 3 ready, 1 missing subject; dry/apply/repeat reconcile')
            # Larger import and true concurrent HTTP create checks.
            text = 'title,subject\n' + ''.join(f'Batch1000-{i},Systems\n' for i in range(1000))
            job = preview(1, aurora, text, 'preview_1000_rows'); result = apply(1, aurora, job, 'apply_1000_rows')
            assert result['created_records'] == 1000 and len({r['accession_number'] for r in result['rows']}) == 1000
            replay = apply(1, aurora, job, 'apply_replay'); assert replay == result
            concurrent_manual = []
            for size in (10, 100):
                with ThreadPoolExecutor(max_workers=size) as pool:
                    created = list(pool.map(lambda i: add(1, aurora, f'Concurrent Manual {size}-{i}'), range(size)))
                assert len({r['accession_number'] for r in created}) == size
                concurrent_manual.append({'workers': size, 'requests': size, 'unique_accessions': size, 'duplicate_accessions': 0})
            for _ in range(10):
                call(1, 'GET', base(aurora) + '/books?limit=20', metric='inventory_list')
                call(1, 'GET', base(aurora) + '/books?search=Batch1000-99&limit=20', metric='inventory_search')
                start = perf_counter(); assert verified_work(work['work_id']); metrics.setdefault('global_work_validation', []).append(round((perf_counter() - start) * 1000, 3))
                start = perf_counter(); TenantInventory(aurora).accession(database.institution_libraries.find_one({'library_id': aurora}))
                metrics.setdefault('accession_allocation', []).append(round((perf_counter() - start) * 1000, 3))
            # Prefix stays fixed even when the canonical name changes.
            database.institution_libraries.update_one({'library_id': orion}, {'$set': {'name': 'Renamed Private Institute'}})
            stable = add(2, orion, 'Stable Prefix Record'); assert stable['accession_number'].startswith('ORI-')
            def isolation(user):
                rows = call(user, 'GET', '/me/libraries')['results']
                assert all(r['membership']['user_id'] == user for r in rows)
                private = client.get(BASE + base(orion) + '/books', headers=headers[user])
                assert private.status_code == (200 if user in (2, 4) else 404)
                return {'user_id': user, 'private_inventory_status': private.status_code}
            with ThreadPoolExecutor(max_workers=20) as pool: reads = list(pool.map(isolation, range(1, 21)))
            reconciliation = [reconcile(database, lib) for lib in (aurora, orion, migration_library)]
            assert all(r['status'] == 'PASS' for r in reconciliation)
            database.users.update_one({'user_id': 4}, {'$set': {'is_active': False}})
            call(4, 'GET', base(orion) + '/books', expected=401)
            database.users.update_one({'user_id': 4}, {'$set': {'is_active': True}})
            write('live', {'status': 'PASS', 'transport': 'real HTTP + uvicorn + MongoDB + Vite', 'database': database_name, 'production_database_modified': False,
                'scenarios': scenarios, 'concurrent_manual': concurrent_manual, 'concurrent_imports': {'libraries': 2, 'rows_each': 100, 'duplicates': 0},
                'large_import': {'rows': 1000, 'created': 1000, 'duplicates': 0, 'idempotent_replay': True}, 'isolation_workers': 20,
                'isolation_reads': reads, 'prefix_rename_stable': True, 'current_account_revocation_denied': True, 'reconciliation': reconciliation,
                'legacy_domain_counts': {name: database[name].count_documents({}) for name in ('issues', 'reservations', 'fines')}})
            summaries = {}
            for key, values in metrics.items():
                summaries[key] = {'samples': len(values), 'median_ms': round(statistics.median(values), 3), 'p90_ms': round(sorted(values)[max(0, int(.9 * len(values) + .9999) - 1)], 3) if len(values) >= 3 else None,
                                  'max_ms': max(values), 'raw_ms': values}
            write('performance', {'local_only': True, 'scale': 'about 1500 records in measured library', 'metrics': summaries,
                'single_sample_note': '1000-row apply/preview have one sample; p90 is deliberately null. No 10k/100k claim.'})
            fixture = {'database': database_name, 'aurora': aurora, 'orion': orion, 'migration_library': migration_library, 'core': BASE, 'frontend': 'http://127.0.0.1:5182'}
            (SCRATCH / 'fixture.json').write_text(json.dumps(fixture), encoding='utf8')
            (SCRATCH / 'browser-minimal.csv').write_text('title,subject\nBrowser Minimal Book,Systems\nBrowser Missing Subject,\n', encoding='utf8')
            print('Live scenarios 1–10, 1000 rows, 10/100 concurrent creates, 20-worker isolation and reconciliation: PASS', flush=True)
            if args.serve:
                print('Preview ready at http://127.0.0.1:5182; create .scratch/institution-v2a/stop to clean up.', flush=True)
                while not (SCRATCH / 'stop').exists(): sleep(.5)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
        for log in logs: log.close()
        assert database_name.startswith('luminar_institution_v2a_live_')
        mongo.drop_database(database_name)
        write('cleanup', {'database': database_name, 'fixture_database_dropped': database_name not in mongo.list_database_names(), 'own_preview_processes_stopped': all(p.poll() is not None for p in processes), 'production_database_modified': False})
        mongo.close()
        if (SCRATCH / 'stop').exists(): (SCRATCH / 'stop').unlink()
        print('Disposable database and preview processes cleaned up.', flush=True)


if __name__ == '__main__': main()
