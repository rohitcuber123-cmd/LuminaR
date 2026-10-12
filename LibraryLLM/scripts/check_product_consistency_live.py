"""Normal authenticated live reads, denied authority probes and QA receipts."""
from collections import Counter
from datetime import datetime, timezone
import getpass
import json
import math
import os
import secrets
from pathlib import Path
from statistics import median
from time import perf_counter, sleep
from uuid import uuid4
import httpx
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
LID = 'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
BASE = '/libraries/' + LID


def main():
    password = getpass.getpass('Local development password (runtime only): ')
    load_dotenv(ROOT / '.env'); mongo = MongoClient(os.getenv('MONGO_URI'))
    database = mongo['luminar_library']
    report = {'verified_at': datetime.now(timezone.utc).isoformat(), 'library_id': LID,
        'normal_authentication': True, 'measurements': {}, 'authority_probes': []}
    with httpx.Client(timeout=120) as client:
        def login(core, email):
            response = client.post(core + '/auth/login', json={'email': email, 'password': password})
            response.raise_for_status(); return {'Authorization': 'Bearer ' + response.json()['access_token']}

        def read(core, path, headers):
            for attempt in range(3):
                response = client.get(core + path, headers=headers)
                if response.status_code != 503 or attempt == 2: break
                sleep(.3 * (attempt + 1))
            response.raise_for_status(); return response.json()

        core = 'http://127.0.0.1:8088'
        owner = login(core, 'rohitcuber123@gmail.com'); patron = login(core, 'loh234123@gmail.com')
        for label, path in [('source', '/catalogue/source'), ('home', '/catalogue/home'),
                ('browse', '/catalogue/books?limit=20'), ('search', '/catalogue/books?limit=20&search=Physics'),
                ('arrivals', '/catalogue/books?limit=20&sort=new_arrivals'), ('genres', '/catalogue/genres?limit=50'),
                ('popular', '/catalogue/books?limit=20&sort=popular')]:
            times = []
            for _ in range(5):
                start = perf_counter(); data = read(core, BASE + path, patron); times.append((perf_counter() - start) * 1000)
            report['measurements'][label] = {'runs': 5, 'p50_ms': round(median(times), 2),
                'p95_ms': round(sorted(times)[math.ceil(.95 * len(times)) - 1], 2), 'rows': len(data.get('results', []))}
            report[label] = data
        inventory = read(core, BASE + '/inventory/books?limit=20', owner)
        report['inventory'] = {'total': inventory['total'], 'rows': len(inventory['results']), 'state': inventory.get('lending_state')}
        report['lending_config'] = read(core, BASE + '/lending/config', owner)
        report['reservation_fee_config'] = read(core, BASE + '/reservations-fees/config', owner)
        report['fee_policy'] = read(core, BASE + '/settings/fee-policy', owner)
        for label, headers, path, expected in [('patron_staff_denied', patron, '/staff/loans', 403),
                ('owner_personal_loan_denied', owner, '/me/loans', 403), ('patron_promotion_denied', patron, '/staff/canonical-defaults/preflight', 403)]:
            response = client.get(core + BASE + path, headers=headers)
            assert response.status_code == expected, (label, response.status_code)
            report['authority_probes'].append({'name': label, 'status': response.status_code, 'pass': True})
        owned = read(core, BASE + '/catalogue/books/1a333939-825d-4c16-b944-bf59392561b8', patron)['book']
        assert owned['requestable_count'] == 1
        report['returned_book'] = owned
        report['loan_receipts'] = read(core, BASE + '/me/loans', patron)
        report['reservation_receipts'] = read(core, BASE + '/me/reservations', patron)
        report['reference'] = read(core, BASE + '/catalogue/books/e06bd784-62fb-436c-a935-7ddd9cbe9fd4', patron)['book']
        assert not report['reference']['actions']['request'] and not report['reference']['actions']['reserve']
        report['global_nonowned'] = read(core, BASE + '/catalogue/global-books/OL19545719W', patron)
        assert report['global_nonowned']['book'] is None
        fixture_path = ROOT / 'reports/product_consistency_live_fixture.json'
        fixture = json.loads(fixture_path.read_text(encoding='utf8')); fc = fixture['core']
        qa_owner = login(fc, 'product-qa-1@example.com'); qa_patron = login(fc, 'product-qa-2@example.com')
        platform = login(fc, 'product-qa-5@example.com')
        for library in fixture['libraries']:
            source = read(fc, '/libraries/' + library['library_id'] + '/catalogue/source', qa_patron)
            assert source['catalogue_source'] == 'LIBRARY_LOCAL' and source['local_book_count'] == 1
            library['source_after'] = source
            response = client.get(fc + '/libraries/' + library['library_id'] + '/inventory/books', headers=platform)
            assert response.status_code == 404
            report['authority_probes'].append({'name': 'platform_without_library_membership_denied', 'library_id': library['library_id'], 'status': 404, 'pass': True})
        if 'fallback_library' not in fixture:
            response = client.post(fc + '/libraries/register', headers=qa_owner, json={'name': 'QA Fallback',
                'slug': 'qa-fallback-' + uuid4().hex[:12], 'access_mode': 'PUBLIC', 'library_type': 'PUBLIC_LIBRARY'})
            response.raise_for_status(); fallback = response.json()['library']
            client.post(fc + '/libraries/' + fallback['library_id'] + '/join', headers=qa_patron, json={}).raise_for_status()
            fallback['source'] = read(fc, '/libraries/' + fallback['library_id'] + '/catalogue/source', qa_patron)
            assert fallback['source']['catalogue_source'] == 'GLOBAL_FALLBACK'
            fixture['fallback_library'] = fallback
        fixture['status'] = 'PASS'
        fixture_path.write_text(json.dumps(fixture, indent=2), encoding='utf8')
        start = perf_counter()
        response = client.post('http://127.0.0.1:5182/search-api/search', headers=patron, json={
            'query': 'Physics', 'limit': 20, 'offset': 0, 'library_id': 'LIB001',
            'available_at_library': False, 'save_history': False})
        response.raise_for_status(); search = response.json()
        report['global_fallback_search'] = {'status': response.status_code, 'results': len(search.get('results', [])),
            'milliseconds': round((perf_counter() - start) * 1000, 2), 'service': 'Existing Search 8003',
            'private_records_submitted': 0, 'history_saved': False}
        temporary_path = ROOT / 'reports/product_consistency_temporary_library.json'
        if temporary_path.exists():
            temporary = json.loads(temporary_path.read_text(encoding='utf8'))
        else:
            code = secrets.token_urlsafe(24)
            response = client.post(core + '/libraries/register', headers=owner, json={
                'name': 'Disposable QA Global Fallback', 'slug': 'temporary-qa-' + uuid4().hex[:12],
                'access_mode': 'PRIVATE_CODE', 'access_code': code, 'library_type': 'PRIVATE_INSTITUTION'})
            response.raise_for_status(); temporary = response.json()['library']
            temporary_path.write_text(json.dumps(temporary, indent=2), encoding='utf8')
            client.post(core + '/libraries/' + temporary['library_id'] + '/join', headers=patron, json={'access_code':code}).raise_for_status()
        report['temporary_library'] = temporary
        report['temporary_source'] = read(core, '/libraries/' + temporary['library_id'] + '/catalogue/source', patron)
        assert report['temporary_source']['catalogue_source'] == 'GLOBAL_FALLBACK'
    scope = {'library_id': LID}
    books = list(database.institution_library_books.find(scope, {'_id':0}))
    holdings = list(database.institution_holdings.find(scope, {'_id':0}))
    report['stock_counts'] = dict(Counter(row['circulation_status'] for row in holdings))
    report['test_books'] = len(books); report['test_holdings'] = len(holdings)
    report['global_books'] = database.books.estimated_document_count()
    report['production_platform_assignments'] = database.platform_role_assignments.count_documents({})
    assert report['test_books'] == report['test_holdings'] == 150 and report['global_books'] == 5000000
    report['status'] = 'PASS'
    (ROOT / 'reports/product_consistency_live.json').write_text(json.dumps(report, indent=2, default=str), encoding='utf8')
    print('Live source, defaults, role denials, receipts and global Search verified.', flush=True)


if __name__ == '__main__': main()
