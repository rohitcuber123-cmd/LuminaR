"""Operational invariants; real isolated Mongo, actual native tenant artifacts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from pathlib import Path
from threading import Event
from uuid import uuid4
import importlib.util

import pytest
from fastapi import HTTPException
from backend.services import library_intelligence_store as store, library_intelligence_service as service
from backend.services import library_intelligence_artifacts as artifacts, library_catalogue_experience as catalogue
from search.library_intelligence import TenantIntelligence
from tests.institution_v2g.test_intelligence import book, build, encoder

ACTOR = {'sub': '1'}


@pytest.mark.parametrize('target', ['SEARCH_INDEX', 'KNOWLEDGE_GRAPH'])
@pytest.mark.parametrize('state', ['NOT_BUILT', 'READY', 'STALE', 'BUILDING', 'FAILED', 'RECOVERY_REQUIRED', 'CORRUPT'])
def test_public_response_matches_frozen_baseline(client, library, target, state):
    path = Path(__file__).resolve().parents[2]/'.scratch/institution-v2i/before/backend/services/library_intelligence_service.py'
    spec = importlib.util.spec_from_file_location('v2i_original_service', path)
    before = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(before)
    lib = library()
    book(client, lib)
    if state != 'NOT_BUILT':
        job, _ = build(lib, target)
        if state == 'STALE':
            store.collection('library_books').update_one({'library_id': lib}, {'$set': {'description': 'Changed'}})
        elif state in ['BUILDING', 'RECOVERY_REQUIRED']:
            store.request_build(lib, ACTOR, target)
            claimed = store.claim('fixture-worker')
            if state == 'RECOVERY_REQUIRED':
                store.collection('intelligence_jobs').update_one({'job_id': claimed['job_id']}, {'$set': {'lease_expires_at': store.now()-timedelta(seconds=1)}})
        elif state == 'FAILED':
            store.collection('intelligence_targets').update_one({'library_id': lib, 'target': target}, {'$set': {'state': 'FAILED', 'error_code': 'FIXTURE'}})
        elif state == 'CORRUPT':
            (store.directory(lib, 'search' if target=='SEARCH_INDEX' else 'kg', job['artifact_generation_id'])/'metadata.json').write_bytes(b'corrupt')
    expected = before.status(lib, ACTOR)
    assert service.status(lib, ACTOR) == expected
    assert service.target_status(lib, target) == before.target_status(lib, target)


@pytest.mark.parametrize('field,value', [
    ('title', 'Revised networks'), ('authors', ['New author']), ('subjects', ['New subject']),
    ('description', 'New description'), ('publication_year', '2024'), ('classification', '005'),
    ('publisher', 'New publisher'), ('edition', 'Second'), ('isbn_10', '1234567890'),
    ('isbn_13', '1234567890123'), ('global_work_id', 'OL1W'),
])
def test_shared_fingerprint_conservative_field_contract(client, library, field, value):
    lib = library()
    row = book(client, lib)
    build(lib)
    build(lib, 'KNOWLEDGE_GRAPH')
    before = service.status(lib, ACTOR)
    assert before['search']['status'] == before['kg']['status'] == 'READY'
    store.collection('library_books').update_one({'library_book_id': row['library_book_id']}, {'$set': {field: value}})
    after = service.status(lib, ACTOR)
    assert after['search']['status'] == after['kg']['status'] == 'STALE'
    assert before['dataset']['current_source_fingerprint'] != after['dataset']['current_source_fingerprint']
    assert store.collection('intelligence_jobs').count_documents({'library_id': lib}) == 2


@pytest.mark.parametrize('field,value', [
    ('shelf_location', 'Other shelf'), ('local_call_number', 'LOCAL-9'), ('local_tags', ['local']),
    ('updated_at', 'changed audit timestamp'), ('cover_url', 'https://example.invalid/cover'),
    ('language', 'English'), ('rating', 4.5), ('acquisition_note', 'Changed holding note'),
])
def test_non_source_fields_do_not_invent_staleness(client, library, field, value):
    lib = library()
    row = book(client, lib)
    build(lib)
    build(lib, 'KNOWLEDGE_GRAPH')
    store.collection('library_books').update_one({'library_book_id': row['library_book_id']}, {'$set': {field: value}})
    value = service.status(lib, ACTOR)
    assert value['search']['status'] == value['kg']['status'] == 'READY'


def test_global_enrichment_mutation_detected_without_local_revision(client, library, database):
    lib = library()
    row = book(client, lib, linked=True)
    store.collection('library_books').update_one({'library_book_id': row['library_book_id']}, {'$set': {'description': ''}})
    build(lib)
    database.books.update_one({'work_id': 'OL1W'}, {'$set': {'description': 'New global enrichment'}})
    assert service.status(lib, ACTOR)['search']['status'] == 'STALE'


def test_bulk_direct_mutation_and_restart_do_not_use_cached_ready(client, library):
    lib = library()
    book(client, lib)
    build(lib)
    before = service.status(lib, ACTOR)
    assert before['search']['status'] == 'READY'
    # Bypasses all mutation service hooks: rejects authoritative revision cache.
    store.collection('library_books').update_many({'library_id': lib}, {'$set': {'description': 'Bulk imported revision'}})
    service.graph_cache.clear()
    for _ in range(3):
        assert service.status(lib, ACTOR)['search']['status'] == 'STALE'


@pytest.mark.parametrize('operation', ['add', 'remove', 'withdraw', 'empty_title'])
def test_record_eligibility_changes_are_detected(client, library, operation):
    lib = library()
    row = book(client, lib)
    build(lib)
    build(lib, 'KNOWLEDGE_GRAPH')
    if operation == 'add':
        book(client, lib, 'A second unique book')
    elif operation == 'remove':
        store.collection('library_books').delete_one({'library_book_id': row['library_book_id']})
    else:
        store.collection('library_books').update_one({'library_book_id': row['library_book_id']}, {'$set': {'status': 'WITHDRAWN'} if operation == 'withdraw' else {'title': '   '}})
    result = service.status(lib, ACTOR)
    assert result['search']['status'] == result['kg']['status'] == 'STALE'


def test_private_asset_content_not_a_source_mutation(client, library, upload, ready):
    lib = library()
    row = book(client, lib)
    build(lib)
    build(lib, 'KNOWLEDGE_GRAPH')
    fp = service.status(lib, ACTOR)['dataset']['current_source_fingerprint']
    asset = upload(lib, book_id=row['library_book_id']).json()
    ready(asset)
    result = service.status(lib, ACTOR)
    assert result['dataset']['current_source_fingerprint'] == fp
    assert result['search']['status'] == result['kg']['status'] == 'READY'


def test_each_request_rechecks_current_membership_and_account(client, library):
    lib = library()
    assert service.status(lib, ACTOR)['can_build']
    store.collection('memberships').update_one({'library_id': lib, 'user_id': 1}, {'$set': {'role': 'LIBRARIAN'}})
    assert not service.status(lib, ACTOR)['can_build']
    with pytest.raises(HTTPException) as denied:
        store.request_build(lib, ACTOR, 'SEARCH_INDEX')
    assert denied.value.status_code == 403
    store.collection('memberships').update_one({'library_id': lib, 'user_id': 1}, {'$set': {'status': 'REVOKED'}})
    assert client.get(f'/libraries/{lib}/intelligence').status_code in [403, 404]


@pytest.mark.parametrize('target', ['SEARCH_INDEX', 'KNOWLEDGE_GRAPH'])
@pytest.mark.parametrize('fault', ['checksum', 'missing', 'foreign_manifest'])
def test_warm_status_never_reuses_verification_across_requests(client, library, target, fault):
    lib = library()
    book(client, lib)
    job, _ = build(lib, target)
    key = 'search' if target == 'SEARCH_INDEX' else 'kg'
    assert service.status(lib, ACTOR)[key]['artifact_verified']
    p = store.directory(lib, 'search' if key == 'search' else 'kg', job['artifact_generation_id'])
    if fault == 'missing':
        (p/'metadata.json').unlink()
    elif fault == 'checksum':
        (p/'metadata.json').write_bytes(b'corrupt')
    else:
        data = json.loads((p/'manifest.json').read_text())
        data['library_id'] = str(uuid4())
        (p/'manifest.json').write_text(json.dumps(data))
    result = service.status(lib, ACTOR)[key]
    assert result['status'] == result['active_status'] == 'RECOVERY_REQUIRED'
    assert not result['artifact_verified']


def test_verification_exactly_once_per_target_per_control_read(client, library, monkeypatch):
    lib = library()
    book(client, lib)
    build(lib)
    build(lib, 'KNOWLEDGE_GRAPH')
    original, calls = service.pointer_manifest, []
    def observed(*args, **kw):
        calls.append((args[0], args[1]))
        return original(*args, **kw)
    monkeypatch.setattr(service, 'pointer_manifest', observed)
    for _ in range(2):
        assert service.status(lib, ACTOR)['search']['status'] == 'READY'
    assert calls == [(lib, 'SEARCH_INDEX'), (lib, 'KNOWLEDGE_GRAPH')] * 2


def test_two_libraries_never_share_observations(client, library):
    a, b = library(), library()
    book(client, a)
    book(client, b, 'Other catalogue')
    build(a)
    build(b, 'KNOWLEDGE_GRAPH')
    def read(lib):
        return service.status(lib, ACTOR)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(read, [a, b]))
    assert results[0]['search']['status'] == 'READY' and results[0]['kg']['status'] == 'NOT_BUILT'
    assert results[1]['search']['status'] == 'NOT_BUILT' and results[1]['kg']['status'] == 'READY'
    assert results[0]['library_id'] == a and results[1]['library_id'] == b


def test_status_does_not_hide_active_job_or_expired_lease(client, library):
    lib = library()
    book(client, lib)
    build(lib)
    service.status(lib, ACTOR)
    request = store.request_build(lib, ACTOR, 'SEARCH_INDEX')
    assert service.status(lib, ACTOR)['search']['current_job']['job_id'] == request['job_id']
    job = store.claim('private-worker-secret')
    store.collection('intelligence_jobs').update_one({'job_id': job['job_id']}, {'$set': {'lease_expires_at': store.now()-timedelta(seconds=1)}})
    value = service.status(lib, ACTOR)['search']
    assert value['status'] == 'RECOVERY_REQUIRED' and value['active_status'] == 'READY'
    payload = json.dumps(value, default=str)
    assert all(s not in payload for s in ['private-worker-secret', 'fence_token', 'lease_expires_at', str(store.root()), 'Traceback'])


def test_publication_rechecks_mutation_during_build(client, library):
    lib = library()
    row = book(client, lib)
    first, _ = build(lib)
    store.request_build(lib, ACTOR, 'SEARCH_INDEX')
    def mutation(stage):
        if stage == 'VALIDATION':
            store.collection('library_books').update_one({'library_book_id': row['library_book_id']}, {'$set': {'description': 'Concurrent revision during build'}})
    assert TenantIntelligence(encoder, model_version='isolated', fail=mutation).run_one()
    status = service.status(lib, ACTOR)['search']
    assert status['active_generation_id'] == first['artifact_generation_id']
    assert status['status'] == 'FAILED' and status['active_status'] == 'STALE'


def test_fifo_and_per_target_duplicate_not_per_tenant_scheduler(client, library):
    a, b, c = library(), library(), library()
    jobs = [store.request_build(a, ACTOR, 'SEARCH_INDEX'), store.request_build(b, ACTOR, 'KNOWLEDGE_GRAPH'),
            store.request_build(c, ACTOR, 'SEARCH_INDEX')]
    assert store.request_build(a, ACTOR, 'SEARCH_INDEX')['job_id'] == jobs[0]['job_id']
    assert store.request_build(a, ACTOR, 'KNOWLEDGE_GRAPH')['job_id'] not in {j['job_id'] for j in jobs}
    assert store.claim('single-worker')['job_id'] == jobs[0]['job_id']
    assert store.claim('single-worker')['job_id'] == jobs[1]['job_id']
    assert store.claim('single-worker')['job_id'] == jobs[2]['job_id']


def test_no_added_cancel_or_automatic_controls(client, library):
    lib = library()
    book(client, lib)
    for _ in range(2):
        assert service.status(lib, ACTOR)['search']['status'] == 'NOT_BUILT'
    assert store.collection('intelligence_jobs').count_documents({'library_id': lib}) == 0
    assert client.post(f'/libraries/{lib}/intelligence/jobs/{uuid4()}/cancel').status_code == 404


def test_recommendations_do_not_require_ready_intelligence(client, library):
    a, b = library(), library(owner=2)
    own = book(client, a)
    assert client.post(f'/libraries/{b}/inventory/books', headers={'x-test-user': '2'},
        json={'title': 'Foreign title', 'subjects': ['Technology'], 'copies': 1, 'idempotency_key': str(uuid4())}).status_code == 201
    # Status observation cannot make recommendations depend on HNSW or KG.
    assert service.status(a, ACTOR)['search']['status'] == 'NOT_BUILT'
    store.collection('memberships').insert_one({'membership_id': str(uuid4()), 'library_id': a,
        'user_id': 3, 'role': 'GENERAL_USER', 'status': 'ACTIVE'})
    patron = {'sub': '3'}
    result = catalogue.recommendations(a, patron, ['OL999W'], 10)
    assert {r['library_book_id'] for r in result['results']} == {own['library_book_id']}
    with pytest.raises(HTTPException):
        catalogue.recommendations(b, patron, [], 10)


@pytest.mark.parametrize('state', ['READY', 'STALE', 'BUILDING', 'FAILED', 'RECOVERY_REQUIRED'])
def test_runtime_selection_retains_existing_safe_fallback(client, library, state):
    lib = library()
    own = book(client, lib)
    job, worker = build(lib)
    store.collection('intelligence_targets').update_one({'library_id': lib, 'target': 'SEARCH_INDEX'}, {'$set': {'state': state}})
    page = worker.semantic(lib, ACTOR, 'computer', staff=True)
    assert page['source']['search_source'] == ('TENANT_SEMANTIC' if state == 'READY' else 'LOCAL_FALLBACK')
    assert {r['library_book_id'] for r in page['results']} == {own['library_book_id']}
    assert service.target_status(lib, 'SEARCH_INDEX')['active_generation_id'] == job['artifact_generation_id']


def test_actual_flat_hnsw_add_but_no_supported_remove():
    import faiss
    import numpy as np
    index = faiss.IndexHNSWFlat(384, 16, faiss.METRIC_INNER_PRODUCT)
    vector = np.zeros((1, 384), dtype=np.float32)
    vector[0, 0] = 1
    index.add(vector)
    assert index.ntotal == 1
    with pytest.raises(RuntimeError, match='remove_ids not implemented'):
        index.remove_ids(np.array([0], dtype=np.int64))
