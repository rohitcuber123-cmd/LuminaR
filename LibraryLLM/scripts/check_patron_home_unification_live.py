"""Normal development login; exact phase-owned disposable library only."""
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
from uuid import uuid4
import httpx
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
TEST = 'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
MANIFEST = ROOT / 'reports/patron_home_unification_disposable.json'
CORE = 'http://127.0.0.1:8088'


def main():
    mode = sys.argv[1]
    load_dotenv(ROOT / '.env')
    mongo = MongoClient(os.getenv('MONGO_URI'))
    database = mongo['luminar_library']
    if mode == 'cleanup':
        fixture = json.loads(MANIFEST.read_text())
        lid = fixture['library_id']
        assert lid != TEST and fixture['name'] == 'Disposable Shared Home QA'
        library = database.institution_libraries.find_one({'library_id': lid})
        assert library and library['slug'] == fixture['slug'] and library['owner_user_id'] == 4
        assert library['access_mode'] == 'PRIVATE_CODE'
        assert {m['user_id'] for m in database.institution_memberships.find({'library_id': lid})} == {4, 6}
        assert not database.institution_locks.find_one({'_id': lid})
        assert database.institution_library_books.count_documents({'library_id': lid}) == 1
        assert database.institution_library_books.find_one({'library_id': lid, 'library_book_id': fixture['added_book_id'], 'title': 'Shared Home QA Local Handbook'})
        for name in ('loans', 'lending_requests', 'reservations', 'fees'):
            assert database['institution_' + name].count_documents({'library_id': lid}) == 0
        deleted = {}
        for name in database.list_collection_names():
            if name.startswith('institution_'):
                count = database[name].delete_many({'library_id': lid}).deleted_count
                if count: deleted[name] = count
        assert database.institution_library_books.count_documents({'library_id': TEST, 'status': 'ACTIVE'}) == 150
        (ROOT / 'reports/patron_home_unification_cleanup.json').write_text(json.dumps({
            'disposable_library_removed': True, 'library_id': lid, 'deleted_scoped_counts': deleted,
            'test_preserved': True, 'test_active_books': 150}, indent=2))
        print('Exact disposable QA library removed; TEST preserved.')
        return

    password = getpass.getpass('Development password (runtime only): ')
    with httpx.Client(timeout=120) as client:
        def login(email):
            response = client.post(CORE + '/auth/login', json={'email': email, 'password': password})
            response.raise_for_status()
            return {'Authorization': 'Bearer ' + response.json()['access_token']}
        owner = login('rohitcuber123@gmail.com')
        patron = login('loh234123@gmail.com')
        def read(path):
            response = client.get(CORE + path, headers=patron)
            response.raise_for_status()
            return response.json()
        if mode == 'create':
            assert not MANIFEST.exists(), 'Never reuse a completed disposable fixture.'
            code = secrets.token_urlsafe(24)
            response = client.post(CORE + '/libraries/register', headers=owner, json={
                'name': 'Disposable Shared Home QA', 'slug': 'shared-home-qa-' + uuid4().hex[:12],
                'library_type': 'PRIVATE_INSTITUTION', 'access_mode': 'PRIVATE_CODE', 'access_code': code})
            response.raise_for_status()
            fixture = response.json()['library']
            # Save exact identity before any subsequent operation; no secrets in the manifest.
            MANIFEST.write_text(json.dumps(fixture, indent=2))
            response = client.post(CORE + '/libraries/' + fixture['library_id'] + '/join', headers=patron, json={'access_code': code})
            response.raise_for_status()
            fixture['source_before'] = read('/libraries/' + fixture['library_id'] + '/catalogue/source')
            assert fixture['source_before']['catalogue_source'] == 'GLOBAL_FALLBACK'
            MANIFEST.write_text(json.dumps(fixture, indent=2))
            print('Disposable empty library:', fixture['library_id'])
        elif mode == 'add':
            fixture = json.loads(MANIFEST.read_text())
            assert not fixture.get('added_book_id')
            base = '/libraries/' + fixture['library_id']
            response = client.post(CORE + base + '/inventory/books', headers=owner, json={
                'title': 'Shared Home QA Local Handbook', 'authors': ['Shared Home QA'], 'subjects': ['Shared Discovery'],
                'copies': 1, 'shelf_location': 'QA-01', 'idempotency_key': str(uuid4())})
            response.raise_for_status()
            fixture['added_book_id'] = response.json()['library_book_id']
            fixture['source_after'] = read(base + '/catalogue/source')
            assert fixture['source_after']['catalogue_source'] == 'LIBRARY_LOCAL'
            assert fixture['source_after']['local_book_count'] == 1
            MANIFEST.write_text(json.dumps(fixture, indent=2))
            print('First canonical local book added; source switched automatically.')
        elif mode == 'verify':
            report = {'verified_at': datetime.now(timezone.utc).isoformat(), 'normal_login': True, 'library_id': TEST}
            base = '/libraries/' + TEST
            report['home'] = read(base + '/catalogue/home')
            assert report['home']['source']['local_book_count'] == 150
            response = client.get('http://127.0.0.1:5182/recommendation-api/recommendations?limit=50&offset=0', headers=patron)
            global_candidates = response.json().get('recommendations', []) if response.is_success else []
            report['global_candidate_status'] = response.status_code
            response = client.post(CORE + base + '/catalogue/recommendations', headers=patron,
                json={'work_ids': [b['work_id'] for b in global_candidates], 'limit': 10})
            response.raise_for_status()
            report['recommendations'] = response.json()
            for key, path in [('browse', '/catalogue/books?limit=50'), ('search', '/catalogue/books?search=Physics'),
                ('arrivals', '/catalogue/books?sort=new_arrivals'), ('popular', '/catalogue/books?sort=popular'),
                ('genres', '/catalogue/genres?limit=50'), ('no_results', '/catalogue/books?search=NO_SUCH_QA_TITLE_2026')]:
                report[key] = read(base + path)
            primary = [*report['home']['featured'], *report['home']['new_arrivals'], *report['recommendations']['results'],
                       *report['home']['popular'], *[s['preview_book'] for s in report['home']['subjects'] if s.get('preview_book')]]
            assert primary and all(b['library_book_id'] and b['source'] == 'LIBRARY' and b['library_id'] == TEST for b in primary)
            report['primary_local_percent'] = 100
            report['global_filler_count'] = 0
            report['local_only_recommendations'] = sum(b['global_work_id'] is None for b in report['recommendations']['results'])
            assert report['local_only_recommendations'] > 0
            assert report['no_results']['results'] == []
            report['canonical_nonowned'] = read(base + '/catalogue/global-books/OL19545719W')
            assert report['canonical_nonowned']['book'] is None
            report['authority'] = {}
            for label, headers, path in [('staff_personal_denied', owner, '/catalogue/home'), ('patron_staff_denied', patron, '/staff/loans')]:
                response = client.get(CORE + base + path, headers=headers)
                assert response.status_code == 403
                report['authority'][label] = response.status_code
            fixture = json.loads(MANIFEST.read_text())
            report['disposable_home_after'] = read('/libraries/' + fixture['library_id'] + '/catalogue/home')
            assert report['disposable_home_after']['source']['local_book_count'] == 1
            report['global_count'] = database.books.estimated_document_count()
            assert report['global_count'] == 5000000
            report['global_linked_document_sha256'] = {}
            for row in database.institution_library_books.find({'library_id': TEST, 'global_work_id': {'$ne': None}}):
                work = row['global_work_id']
                document = database.books.find_one({'work_id': work}, {'_id': 0})
                report['global_linked_document_sha256'][work] = hashlib.sha256(json.dumps(document, sort_keys=True, default=str).encode()).hexdigest()
            (ROOT / 'reports/patron_home_unification_live.json').write_text(json.dumps(report, indent=2, default=str))
            print('TEST: 150 books; all primary candidates local; local-only recommendations eligible; global catalogue 5000000.')
        else:
            raise ValueError(mode)
    mongo.close()


if __name__ == '__main__':
    main()
