"""Real Core lifespan, JWT/Staff login and scoped service reads, owned DB only."""
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
assert os.environ['MONGO_DB_NAME'].startswith('luminar_v2n_fixture_')
from backend.database.mongo_configuration import connect, settings


def timed(call, n=15):
    values = []
    for _ in range(n):
        at = time.perf_counter(); call(); values.append((time.perf_counter() - at) * 1000)
    return {'n': n, 'median_ms': statistics.median(values), 'min_ms': min(values), 'max_ms': max(values), 'samples_ms': values}


def main():
    report = {'scope': 'Owned synthetic database only', 'mode': os.environ['LUMINAR_MONGO_MODE']}
    def opening():
        with connect(settings()) as client:
            client[os.environ['MONGO_DB_NAME']].users.find_one({}, {'_id': 1})
    report['connection_and_first_read'] = timed(opening, 8)
    at = time.perf_counter()
    from backend.main import app
    from backend.database.mongodb import db, client as mongo
    report['core_module_import_ms'] = (time.perf_counter() - at) * 1000
    from fastapi.testclient import TestClient
    from backend.services.auth_service import hash_password
    from backend.utils.jwt_utils import create_access_token
    from backend.services import library_asset_service as assets, library_intelligence_store as store
    from recommendation.recommendation_service import get_user_behavior, get_book_by_work_id
    for user in range(1, 7):
        db.users.insert_one({'user_id': user, 'email': f'n-bench-{user}@example.com', 'name': 'Synthetic account',
                             'role': 'GENERAL_USER', 'is_email_verified': True, 'is_active': True,
                             'password_hash': hash_password('Synthetic fixture passphrase')})
    db.books.insert_many([{'work_id': 'OL' + str(n) + 'W', 'title': f'Synthetic Networks {n}', 'subjects': ['Networks']} for n in range(151)])
    def headers(user):
        return {'Authorization': 'Bearer ' + create_access_token(user, f'n-bench-{user}@example.com', 'GENERAL_USER')}
    at = time.perf_counter()
    with TestClient(app) as api:
        report['core_lifespan_start_ms'] = (time.perf_counter() - at) * 1000
        libraries = []
        for owner in [1, 2]:
            response = api.post('/libraries/register', headers=headers(owner), json={'name': 'Synthetic Private', 'slug': 'n-' + uuid4().hex,
                'library_type': 'PRIVATE_INSTITUTION', 'access_mode': 'PRIVATE_CODE', 'access_code': 'Synthetic fixture code'})
            assert response.status_code == 201, response.text
            libraries.append(response.json()['library']['library_id'])
        lib = libraries[0]
        for user, role in [(3, 'LIBRARIAN'), (4, 'GENERAL_USER')]:
            db.institution_memberships.insert_one({'membership_id': str(uuid4()), 'library_id': lib, 'user_id': user, 'role': role, 'status': 'ACTIVE'})
        db.platform_role_assignments.insert_one({'user_id': 5, 'role': 'PLATFORM_ADMIN', 'status': 'ACTIVE',
            'approval_ref': 'fixture-only', 'approved_by': 'fixture-controller', 'approved_at': datetime.now(timezone.utc)})
        response = api.post('/auth/staff-login', json={'email': 'n-bench-1@example.com', 'password': 'Synthetic fixture passphrase'})
        report['staff_password_login_http'] = response.status_code
        assert response.status_code == 200
        response = api.post(f'/libraries/{lib}/inventory/books', headers=headers(1), json={'title': 'Private synthetic catalogue', 'subjects': ['Networks'], 'idempotency_key': str(uuid4())})
        assert response.status_code == 201, response.text
        def catalogue():
            r = api.get(f'/libraries/{lib}/inventory/books', headers=headers(1)); assert r.status_code == 200
        def status():
            # Intelligence routes are hosted by Search, not Core.
            from backend.services.library_intelligence_service import status as read_status
            read_status(lib, {'sub': '1'})
        report['catalogue_read'] = timed(catalogue)
        report['tenant_status'] = timed(status)
        report['isolation'] = []
        for user, expected in [(1, 200), (3, 200), (4, 200), (2, 404), (5, 404), (6, 404)]:
            # Catalogue permits active members; unrelated platform authority does not.
            r = api.get(f'/libraries/{lib}/inventory/books', headers=headers(user))
            report['isolation'].append({'user': user, 'http': r.status_code, 'expected': expected})
            assert r.status_code == expected, f'user={user} http={r.status_code} expected={expected} body={r.text}'
        assert api.get(f'/libraries/{libraries[1]}/inventory/books', headers=headers(1)).status_code == 404
        aid = str(uuid4())
        db.institution_library_assets.insert_one({'library_id': lib, 'asset_id': aid, 'status': 'READY', 'visibility': 'MEMBERS'})
        report['private_rag_metadata_retrieval'] = timed(lambda: assets.authorize_asset(lib, aid, {'sub': '4'}))
        from fastapi import HTTPException
        for user in [2, 5, 6]:
            try: assets.authorize_asset(lib, aid, {'sub': str(user)})
            except HTTPException as error: assert error.status_code in {403, 404}
            else: raise AssertionError('Private RAG metadata isolation failed')
        report['recommendation_history_retrieval'] = timed(lambda: (get_user_behavior(1), get_book_by_work_id('OL1W')))
        store.initialize()
        store.request_build(lib, {'sub': '1'}, 'KNOWLEDGE_GRAPH')
        at = time.perf_counter(); job = store.claim('owned-n-benchmark'); report['native_claim_ms'] = (time.perf_counter() - at) * 1000
        assert job
        report['native_lease_renewal'] = timed(lambda: store.heartbeat(job))
        # No worker is launched in this metadata benchmark; discard with owned DB.
    report['qualified_scope'] = 'Core startup/JWT/Staff/catalogue/private authorization and RAG metadata/recommendation history. Full Qwen, 5M Search and semantic recommendation HTTP dependencies are not started.'
    mongo.close()
    Path(sys.argv[1]).write_text(json.dumps(report, indent=2))


if __name__ == '__main__': main()
