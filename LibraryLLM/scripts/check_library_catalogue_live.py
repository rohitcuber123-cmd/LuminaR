"""Disposable tenant HTTP/browser fixture; existing 5M metadata is strictly read-only."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from time import sleep, perf_counter
from uuid import uuid4
import bcrypt
import httpx
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / '.scratch/library-catalogue'
CORE = 'http://127.0.0.1:8087'
FRONTEND = 'http://127.0.0.1:5187'
PASSWORD = 'LuminaR-Catalogue-Fixture-123!'


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--serve', action='store_true'); args = parser.parse_args()
    name = 'luminar_catalogue_live_' + uuid4().hex
    mongo = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=5000)
    database = mongo[name]; processes = []; logs = []
    SCRATCH.mkdir(parents=True, exist_ok=True); (SCRATCH / 'stop').unlink(missing_ok=True)
    try:
        password_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
        database.users.insert_many([{'user_id': i, 'email': f'catalogue-{i}@example.com', 'name': f'Catalogue Account {i}', 'password_hash': password_hash,
            'role': 'ADMIN' if i == 2 else 'GENERAL_USER', 'is_active': True, 'is_email_verified': True} for i in [1, 2, 3, 5]])
        database.platform_role_assignments.insert_one({'user_id':5,'role':'PLATFORM_ADMIN','status':'ACTIVE','approval_ref':'ISOLATED-TEST','approved_by':'fixture-operator','approved_at':datetime.now(timezone.utc)})
        global_book = mongo.luminar_library.books.find_one({'work_id': {'$regex': '^OL[0-9]+W$'}}, {'_id':0}, sort=[('book_id',1)])
        assert global_book and mongo.luminar_library.books.estimated_document_count() == 5000000
        database.books.insert_one(global_book)  # One immutable copy for existing trusted link validation.
        wrapper = SCRATCH / 'live_core.py'
        wrapper.write_text('''import sys
sys.path.insert(0, r"''' + str(ROOT) + '''")
from backend.main import app
from backend.services import book_service
from backend.database.mongodb import client
class ReadOnly:
    def __init__(self, collection): self.collection = collection
    def __getattr__(self, name):
        if name not in {"find", "find_one", "aggregate", "estimated_document_count", "count_documents"}:
            raise RuntimeError("Live fixture forbids production metadata mutations")
        return getattr(self.collection, name)
book_service.books_collection = ReadOnly(client["luminar_library"]["books"])
book_service.book_categories_collection = ReadOnly(client["luminar_library"]["book_categories"])
''', encoding='utf8')
        env = {**os.environ, 'MONGO_URI': 'mongodb://127.0.0.1:27017', 'MONGO_DB_NAME': name,
            'JWT_SECRET_KEY': secrets.token_urlsafe(48), 'LUMINAR_CORE_API_TARGET': CORE,
            'ISBN_LOOKUP_DB': str(SCRATCH / 'no-isbn.duckdb')}
        for title, command, cwd in [('core', [sys.executable, '-m', 'uvicorn', 'live_core:app', '--app-dir', str(SCRATCH), '--host', '127.0.0.1', '--port', '8087'], ROOT),
            ('frontend', ['node', str(ROOT / 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5187', '--strictPort'], ROOT / 'frontend')]:
            log = (SCRATCH / f'{title}.log').open('w', encoding='utf8'); logs.append(log)
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0))
        with httpx.Client(timeout=90) as client:
            for _ in range(120):
                if any(p.poll() is not None for p in processes): raise RuntimeError('Fixture service failed; inspect .scratch logs.')
                try:
                    if client.get(CORE + '/health').is_success and client.get(FRONTEND).is_success: break
                except httpx.HTTPError: pass
                sleep(.25)
            else: raise RuntimeError('Fixture startup timed out.')
            headers = {}
            for i in [1, 2, 3, 5]:
                response = client.post(CORE + '/auth/login', json={'email': f'catalogue-{i}@example.com', 'password': PASSWORD})
                response.raise_for_status(); headers[i] = {'Authorization': 'Bearer ' + response.json()['access_token']}
            timings = []
            def call(user, method, path, body=None, expected=200):
                started = perf_counter(); response = client.request(method, CORE + path, headers=headers[user], json=body)
                assert response.status_code == expected, (path, response.status_code, response.text[:500])
                if '/catalogue/' in path: timings.append({'path':path, 'elapsed_ms':round((perf_counter()-started)*1000,2), 'bytes':len(response.content)})
                return response.json()
            def command(**body): return {'idempotency_key': str(uuid4()), **body}
            libraries = []
            for title, count in [('Catalogue Library A',10), ('Catalogue Library B',0), ('Catalogue Library C',4)]:
                row = call(2, 'POST', '/libraries/register', {'name': title, 'slug': 'catalogue-' + uuid4().hex[:12],
                    'library_type': 'PUBLIC_LIBRARY', 'access_mode': 'PUBLIC'}, 201)['library']; lid=row['library_id']; base='/libraries/'+lid
                for user in [1,3]: call(user,'POST',base+'/join',{})
                call(2,'POST',base+'/staff/lending/activate',command()); call(2,'POST',base+'/staff/reservations-fees/activate',command())
                rows = []
                for n in range(count):
                    book_title = global_book['title'][:500] if title.endswith(' A') and n == 0 else ('A' if title.endswith(' A') else 'C') + f' Local Collection Book {n+1}'
                    rows.append(call(2,'POST',base+'/inventory/books',command(title=book_title,
                        authors=['Ada Catalogue' if n%2 == 0 else 'Grace Catalogue'], subjects=['Networking' if n < 4 else 'Mathematics'],
                        global_work_id=global_book['work_id'] if title.endswith(' A') and n==0 else None,
                        copies=0 if n==4 else 2, shelf_location=f'{title[-1]} / Reading Room / Shelf {n+1}',
                        circulation_status='REFERENCE_ONLY' if n==2 else 'TEMPORARILY_UNAVAILABLE' if n==3 else 'CIRCULATING'),201)['library_book_id'])
                libraries.append({'library_id':lid,'name':title,'book_ids':rows})
            a,b,c=libraries; base='/libraries/'+a['library_id']
            request=call(3,'POST',base+'/lending/borrow-requests',command(library_book_id=a['book_ids'][0]),201)
            call(2,'POST',base+'/staff/lending/borrow-requests/'+request['lending_request_id']+'/approve',command())
            call(1,'POST',base+'/lending/borrow-requests',command(library_book_id=a['book_ids'][5]),201)
            loan_request=call(1,'POST',base+'/lending/borrow-requests',command(library_book_id=a['book_ids'][6]),201)
            call(2,'POST',base+'/staff/lending/borrow-requests/'+loan_request['lending_request_id']+'/approve',command())
            for user in [3,1]: call(user,'POST',base+'/reservations',command(library_book_id=a['book_ids'][4]),201)
            homes=[call(1,'GET','/libraries/'+r['library_id']+'/catalogue/home') for r in libraries]
            assert [h['source']['local_book_count'] for h in homes] == [10,0,4]
            assert homes[1]['source']['catalogue_source'] == 'GLOBAL_FALLBACK'
            assert homes[0]['popular'] and homes[2]['popular'] == [] and len(homes[2]['featured']) == 4
            owned=call(1,'GET',base+'/catalogue/global-books/'+global_book['work_id'])['book']
            assert owned['owned_by_current_library'] and owned['shelf_location'] and owned['actions']['request']
            assert call(1,'GET','/libraries/'+b['library_id']+'/catalogue/global-books/'+global_book['work_id'])['book'] is None
            global_page=client.get(CORE+'/books/?limit=12').json(); assert global_page['count']==5000000 and len(global_page['results'])==12
            for row in libraries:
                route='/libraries/'+row['library_id']
                for suffix in ['/catalogue/books','/catalogue/books?sort=new_arrivals','/catalogue/books?sort=popular','/catalogue/genres']:
                    call(1,'GET',route+suffix)
            assert call(1,'GET',base+'/catalogue/books?search=unmatched-catalogue-phrase')['results']==[]
            call(2,'GET',base+'/catalogue/home',expected=403)
            call(5,'GET',base+'/catalogue/home',expected=404)
            call(5,'POST',base+'/lending/borrow-requests',command(library_book_id=a['book_ids'][0]),404)
            staff=[call(2,'GET','/libraries/'+r['library_id']+'/catalogue/source') for r in [a,b]]
            report={'status':'PASS','verified_at':datetime.now(timezone.utc).isoformat(),'database':name,'libraries':libraries,
                'global_work_id':global_book['work_id'],'global_title':global_book['title'],'global_catalogue_count':5000000,
                'scenarios':{'A':'10 real local books','B':'zero books; existing 5M read-only fallback','C':'local-only records without ISBN/work ID',
                    'D':'non-owned global context returns no physical holding','E':'same global work owned A / non-owned B','G':'real borrowing/reservation activity',
                    'H':'four-book collection with no popularity'},'home_counts':[h['source']['local_book_count'] for h in homes],
                'own_state_summary':homes[0]['my_library'],'staff_sources':staff,'api_timings':timings,'production_mutations':0,
                'isolation':'Only fixture DB writes; production books/categories wrapped in method-whitelisted ReadOnly collections.',
                'global_search_live_limit':'Existing Search service port 8003 is not running; adapter/routing covered by frontend and frozen Search regression, no fake engine or index build.'}
            (ROOT/'reports/library_catalogue_live_api.json').write_text(json.dumps(report,indent=2),encoding='utf8')
            (SCRATCH/'fixture.json').write_text(json.dumps({**report,'frontend':FRONTEND,'core':CORE,'email':'catalogue-1@example.com','staff_email':'catalogue-2@example.com','password':PASSWORD,'owned_pids':[p.pid for p in processes]}),encoding='utf8')
            print('Catalogue fixture ready: A10, B0 with existing 5M metadata, C4 no popularity.',flush=True)
            if args.serve:
                while not (SCRATCH/'stop').exists(): sleep(.25)
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
                try: p.wait(timeout=10)
                except subprocess.TimeoutExpired: p.kill(); p.wait(timeout=10)
        for log in logs: log.close()
        assert name.startswith('luminar_catalogue_live_')
        mongo.drop_database(name)
        cleanup={'fixture_database':name,'fixture_database_dropped':name not in mongo.list_database_names(),'own_services_stopped':all(p.poll() is not None for p in processes),'production_modified':False}
        (ROOT/'reports/library_catalogue_cleanup.json').write_text(json.dumps(cleanup,indent=2),encoding='utf8')
        mongo.close(); (SCRATCH/'stop').unlink(missing_ok=True)


if __name__ == '__main__': main()
