"""Comprehensive closure tests for E-01, E-02, E-03, E-04 and 20-scenario combined recovery."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import numpy as np
import pytest
from fastapi import HTTPException

from backend.services import institution_repository as repo
from backend.services import library_intelligence_artifacts as artifacts
from backend.services import library_intelligence_service as service
from backend.services import library_intelligence_store as store
from search.library_intelligence import TenantIntelligence

MATRIX_REPORT = Path(__file__).resolve().parents[2] / 'reports' / 'closure_20261110_recovery_matrix.json'


def _encoder(texts):
    rows = []
    for text in texts:
        seed = int(hashlib.sha256(str(text).encode('utf8')).hexdigest()[:8], 16)
        vec = np.array([((seed >> (i % 24)) & 0xFF) + 1.0 for i in range(384)], dtype=np.float32)
        vec /= np.linalg.norm(vec)
        rows.append(vec)
    return np.stack(rows, axis=0) if rows else np.zeros((0, 384), dtype=np.float32)


@pytest.fixture
def intel_env(tmp_path, monkeypatch, database):
    intel_root = tmp_path / 'library-intelligence'
    intel_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv('LIBRARY_INTELLIGENCE_ROOT', str(intel_root))
    store.initialize()
    service.graph_cache.clear()
    return intel_root


def _seed_books(database, library_id, count=2, prefix='Closure synthetic book'):
    latest = database.institution_library_books.find_one({'library_id': library_id}, sort=[('accession_sequence', -1)])
    base_seq = (latest or {}).get('accession_sequence', 0)
    docs = []
    for idx in range(count):
        seq = base_seq + idx + 1
        docs.append({
            'library_id': library_id,
            'library_book_id': str(uuid4()),
            'status': 'ACTIVE',
            'accession_number': f'CLS-{seq}-{uuid4().hex[:6]}',
            'accession_sequence': seq,
            'title': f'{prefix} {idx}',
            'authors': [f'Author {idx}'],
            'subjects': ['Computer Science', 'Systems' if idx % 2 == 0 else 'Databases'],
            'description': f'Synthetic closure manual {idx}',
            'classification': 'QA76',
        })
    database.institution_library_books.insert_many(docs)
    database.institution_holdings.insert_many([{
        'holding_id': str(uuid4()),
        'library_id': library_id,
        'library_book_id': doc['library_book_id'],
        'tracking_mode': 'AGGREGATE',
        'total_copies': 1,
        'available_copies': 1,
        'reserved_copies': 0,
        'loaned_copies': 0,
        'circulation_status': 'AVAILABLE',
        'created_at': datetime.now(timezone.utc),
    } for doc in docs])
    return docs


def _add_member(database, library_id, user_id, role='ADMIN'):
    database.institution_memberships.insert_one({
        'library_id': library_id,
        'membership_id': str(uuid4()),
        'user_id': user_id,
        'role': role,
        'is_owner': role == 'ADMIN',
        'status': 'ACTIVE',
    })


def _make_worker(fail=None):
    return TenantIntelligence(_encoder, model_version=store.MODEL, fail=fail)


def _request_build(client, library_id, target, user=1):
    resp = client.post(
        f'/libraries/{library_id}/intelligence/builds',
        headers={'x-test-user': str(user)},
        json={'target': target},
    )
    assert resp.status_code == 202, resp.text
    return resp.json()


def _recover_http(client, library_id, job_id, user=1):
    return client.post(
        f'/libraries/{library_id}/intelligence/jobs/{job_id}/recover',
        headers={'x-test-user': str(user)},
    )


def _expire_job(database, job_id, seconds=180):
    database.institution_intelligence_jobs.update_one(
        {'job_id': job_id},
        {'$set': {'lease_expires_at': datetime.now(timezone.utc) - timedelta(seconds=seconds)}},
    )


def _build_and_publish(client, database, library_id, target, user=1):
    job = _request_build(client, library_id, target, user=user)
    worker = _make_worker()
    assert worker.run_one() is True
    job_doc = database.institution_intelligence_jobs.find_one({'job_id': job['job_id']})
    ptr = database.institution_intelligence_targets.find_one({'library_id': library_id, 'target': target})
    return worker, job_doc, ptr


def _tamper_same_length_preserve_mtime(path: Path, old_bytes: bytes, new_bytes: bytes):
    assert len(old_bytes) == len(new_bytes) and old_bytes != new_bytes
    st = path.stat()
    path.write_bytes(new_bytes)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))


def _kind(target):
    return 'search' if target == 'SEARCH_INDEX' else 'kg'


def _tamper_manifest_json(manifest_path: Path, **updates):
    """Modify JSON preserving exact byte length and mtime when modifying string fields of equal length."""
    raw = manifest_path.read_bytes()
    st = manifest_path.stat()
    obj = json.loads(raw.decode('utf8'))
    obj.update(updates)
    encoded = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf8')
    manifest_path.write_bytes(encoded)
    if len(encoded) == len(raw):
        os.utime(manifest_path, ns=(st.st_atime_ns, st.st_mtime_ns))


def _observe_reader(worker, library_id, target, user=1, staff=True):
    actor = {'sub': str(user)}
    if target == 'SEARCH_INDEX':
        res = worker.semantic(library_id, actor, 'Synthetic closure manual', staff=staff)
        return {'search_source': res['source']['search_source'], 'intelligence_status': res['source']['intelligence_status']}
    res = service.graph(library_id, actor, staff=staff)
    return {'source': res['source'], 'status': res['status'], 'node_count': len(res.get('nodes', []))}


# ============================================================
# PHASE 1: E-03 CORRUPT ARTIFACT PUBLICATION
# ============================================================

@pytest.mark.parametrize('target', ['SEARCH_INDEX', 'KNOWLEDGE_GRAPH'])
def test_e03_valid_build_and_reader_opening(client, database, library, intel_env, target):
    lib = library(owner=1, private=True)
    _add_member(database, lib, 4, role='GENERAL_USER')
    _seed_books(database, lib)
    worker, job_doc, ptr = _build_and_publish(client, database, lib, target)
    assert job_doc['state'] == 'SUCCEEDED'
    assert ptr['state'] == 'READY'
    assert ptr['published_by_job_id'] == job_doc['job_id']
    for u, is_staff in [(1, True), (4, False)]:
        reader = _observe_reader(worker, lib, target, user=u, staff=is_staff)
        if target == 'SEARCH_INDEX':
            assert reader == {'search_source': 'TENANT_SEMANTIC', 'intelligence_status': 'READY'}
        else:
            assert reader['source'] == 'TENANT_KG' and reader['status'] == 'READY' and reader['node_count'] > 0


@pytest.mark.parametrize('target', ['SEARCH_INDEX', 'KNOWLEDGE_GRAPH'])
@pytest.mark.parametrize('mutation_kind', ['manifest_library_same_len_mtime', 'manifest_target', 'manifest_gen_id', 'manifest_fingerprint', 'manifest_checksum_field', 'artifact_file_same_len_mtime', 'missing_file', 'extra_file'])
def test_e03_post_validation_tampering_never_publishes_and_preserves_last_good(client, database, library, intel_env, target, mutation_kind):
    lib = library(owner=1, private=True)
    _seed_books(database, lib, count=2, prefix='Baseline valid book')
    worker1, job1, ptr1 = _build_and_publish(client, database, lib, target)
    assert ptr1['state'] == 'READY'
    good_gen = ptr1['active_generation_id']
    good_chk = ptr1['manifest_checksum']

    # Add a third book so a new generation builds, then tamper after VALIDATION at SERIALIZATION_ACK
    _seed_books(database, lib, count=1, prefix='Second generation book')
    job2 = _request_build(client, lib, target)
    tampered = {'done': False}

    def fail_hook(stage):
        if stage != 'SERIALIZATION_ACK' or tampered['done']:
            return
        tampered['done'] = True
        temp_dir = store.directory(lib, _kind(target), job2['artifact_generation_id']).with_name(job2['artifact_generation_id'] + '.building')
        manifest_path = temp_dir / 'manifest.json'
        m_obj = json.loads(manifest_path.read_text(encoding='utf8'))
        if mutation_kind == 'manifest_library_same_len_mtime':
            other_lib = str(uuid4())
            assert len(other_lib) == len(lib)
            raw = manifest_path.read_bytes()
            replaced = raw.replace(lib.encode('utf8'), other_lib.encode('utf8'), 1)
            _tamper_same_length_preserve_mtime(manifest_path, raw, replaced)
        elif mutation_kind == 'manifest_target':
            _tamper_manifest_json(manifest_path, target='KNOWLEDGE_GRAPH' if target == 'SEARCH_INDEX' else 'SEARCH_INDEX')
        elif mutation_kind == 'manifest_gen_id':
            other_gen = str(uuid4())
            raw = manifest_path.read_bytes()
            replaced = raw.replace(job2['artifact_generation_id'].encode('utf8'), other_gen.encode('utf8'), 1)
            _tamper_same_length_preserve_mtime(manifest_path, raw, replaced)
        elif mutation_kind == 'manifest_fingerprint':
            bad_fp = '0' * 64 if not m_obj['source_fingerprint'].startswith('0' * 64) else 'f' * 64
            _tamper_manifest_json(manifest_path, source_fingerprint=bad_fp)
        elif mutation_kind == 'manifest_checksum_field':
            files = dict(m_obj['files'])
            first_key = next(iter(files))
            files[first_key] = ('a' if not files[first_key].startswith('a') else 'b') * 64
            _tamper_manifest_json(manifest_path, files=files)
        elif mutation_kind == 'artifact_file_same_len_mtime':
            target_file = temp_dir / 'metadata.json'
            raw = target_file.read_bytes()
            # Flip 1 character inside book title string while preserving exact length & JSON validity
            pos = raw.find(b'Closure')
            if pos == -1:
                pos = raw.find(b'Baseline')
            assert pos != -1
            mutated = bytearray(raw)
            mutated[pos] = ord('X') if mutated[pos] != ord('X') else ord('Y')
            _tamper_same_length_preserve_mtime(target_file, raw, bytes(mutated))
        elif mutation_kind == 'missing_file':
            victim = 'vectors.npy' if target == 'SEARCH_INDEX' else 'graph.json'
            (temp_dir / victim).unlink()
        elif mutation_kind == 'extra_file':
            (temp_dir / 'rogue.txt').write_text('unexpected file', encoding='utf8')

    worker2 = _make_worker(fail=fail_hook)
    assert worker2.run_one() is True
    assert tampered['done']

    job2_doc = database.institution_intelligence_jobs.find_one({'job_id': job2['job_id']})
    assert job2_doc['state'] == 'FAILED'
    assert job2_doc['effective_active'] is False

    ptr2 = database.institution_intelligence_targets.find_one({'library_id': lib, 'target': target})
    assert ptr2['active_generation_id'] == good_gen
    assert ptr2['manifest_checksum'] == good_chk
    assert ptr2['published_by_job_id'] == job1['job_id']
    # Last-good generation on disk remains completely intact and validates cleanly
    artifacts.validate(lib, target, good_gen, expected_manifest_checksum=good_chk, expected_job_id=job1['job_id'])
    # Tampered generation directory was never promoted to final active pointer
    assert ptr2['active_generation_id'] != job2['artifact_generation_id']


@pytest.mark.parametrize('target', ['SEARCH_INDEX', 'KNOWLEDGE_GRAPH'])
def test_e03_tamper_at_publish_after_rename_preserves_last_good(client, database, library, intel_env, target):
    lib = library(owner=1, private=True)
    _seed_books(database, lib, count=2, prefix='Initial pub book')
    _, job1, ptr1 = _build_and_publish(client, database, lib, target)
    good_gen, good_chk = ptr1['active_generation_id'], ptr1['manifest_checksum']

    _seed_books(database, lib, count=1, prefix='Tampered pub book')
    job2 = _request_build(client, lib, target)

    def fail_at_publish(stage):
        if stage == 'PUBLISH':
            final_dir = store.directory(lib, _kind(target), job2['artifact_generation_id'])
            _tamper_manifest_json(final_dir / 'manifest.json', source_generation_id=str(uuid4()))

    worker2 = _make_worker(fail=fail_at_publish)
    worker2.run_one()

    job2_doc = database.institution_intelligence_jobs.find_one({'job_id': job2['job_id']})
    assert job2_doc['state'] == 'FAILED'
    ptr2 = database.institution_intelligence_targets.find_one({'library_id': lib, 'target': target})
    assert ptr2['active_generation_id'] == good_gen
    assert ptr2['manifest_checksum'] == good_chk
    assert ptr2['published_by_job_id'] == job1['job_id']


@pytest.mark.parametrize('target', ['SEARCH_INDEX', 'KNOWLEDGE_GRAPH'])
def test_e03_crash_before_and_after_pointer_cas_and_stale_worker(client, database, library, intel_env, target):
    lib = library(owner=1, private=True)
    _seed_books(database, lib)

    # Crash BEFORE pointer CAS (inside PUBLISH failpoint)
    job1 = _request_build(client, lib, target)
    def crash_publish(stage):
        if stage == 'PUBLISH':
            raise HTTPException(409, 'WORKER_CRASH')
    _make_worker(fail=crash_publish).run_one()
    j1 = database.institution_intelligence_jobs.find_one({'job_id': job1['job_id']})
    assert j1['state'] == 'RECOVERY_REQUIRED'
    p1 = database.institution_intelligence_targets.find_one({'library_id': lib, 'target': target})
    assert p1.get('active_generation_id') is None
    _expire_job(database, job1['job_id'])
    rec1 = _recover_http(client, lib, job1['job_id'])
    assert rec1.status_code == 200 and rec1.json()['state'] == 'FAILED'

    # Crash AFTER pointer CAS, BEFORE job ack (ACKNOWLEDGEMENT_LOSS)
    job2 = _request_build(client, lib, target)
    def crash_ack(stage):
        if stage == 'ACKNOWLEDGEMENT_LOSS':
            raise HTTPException(409, 'WORKER_CRASH')
    _make_worker(fail=crash_ack).run_one()
    j2 = database.institution_intelligence_jobs.find_one({'job_id': job2['job_id']})
    assert j2['state'] == 'RECOVERY_REQUIRED'
    _expire_job(database, job2['job_id'])
    rec2 = _recover_http(client, lib, job2['job_id'])
    assert rec2.status_code == 200 and rec2.json()['state'] == 'SUCCEEDED'

    # Stale worker check: tampered fence token cannot mutate job/target via lease_query/check_lease
    stale_job = dict(j2)
    stale_job['fence_token'] = 'stale-token-' + str(uuid4())
    with pytest.raises(HTTPException) as exc:
        store.check_lease(stale_job)
    assert exc.value.status_code == 409 and exc.value.detail == 'WORKER_FENCED'


@pytest.mark.parametrize('target', ['SEARCH_INDEX', 'KNOWLEDGE_GRAPH'])
def test_e03_reader_rejects_post_publish_tampered_artifact_fail_closed(client, database, library, intel_env, target):
    lib = library(owner=1, private=True)
    _seed_books(database, lib)
    worker, job1, ptr1 = _build_and_publish(client, database, lib, target)
    # Tamper published artifact file on disk while keeping same length & mtime
    final_dir = store.directory(lib, _kind(target), ptr1['active_generation_id'])
    meta = final_dir / 'metadata.json'
    raw = meta.read_bytes()
    pos = raw.find(b'Closure')
    mutated = bytearray(raw)
    mutated[pos] = ord('Z')
    _tamper_same_length_preserve_mtime(meta, raw, bytes(mutated))

    # Even if ArtifactCache previously cached it or misses, reader must fail closed
    obs = _observe_reader(worker, lib, target)
    if target == 'SEARCH_INDEX':
        assert obs == {'search_source': 'LOCAL_FALLBACK', 'intelligence_status': 'RECOVERY_REQUIRED'}
    else:
        assert obs['status'] == 'RECOVERY_REQUIRED' and obs['node_count'] == 0


# ============================================================
# PHASE 2A: E-01 TERMINAL JOB RETAINED LOCK
# ============================================================

@pytest.mark.parametrize('target', ['SEARCH_INDEX', 'KNOWLEDGE_GRAPH'])
def test_e01_terminal_retained_lock_matrix(client, database, library, intel_env, target):
    lib = library(owner=1, private=True)
    _add_member(database, lib, 2, role='LIBRARIAN')
    other_lib = library(owner=1, private=True)
    _seed_books(database, lib)

    # Case 1: SUCCEEDED job with retained lock before active_job_id unset
    worker, job1, ptr1 = _build_and_publish(client, database, lib, target)
    assert database.institution_locks.find_one({'_id': lib}) is None  # normal completion left no lock
    database.institution_intelligence_targets.update_one(
        {'library_id': lib, 'target': target},
        {'$set': {'active_job_id': job1['job_id'], 'fence_token': job1['fence_token']}},
    )
    database.institution_locks.insert_one({
        '_id': lib,
        'holder': 'e01-retained-' + str(uuid4()),
        'acquired_at': datetime.now(timezone.utc),
        'intelligence_job_id': job1['job_id'],
        'intelligence_target': target,
    })

    # Active lease denial
    database.institution_intelligence_jobs.update_one(
        {'job_id': job1['job_id']},
        {'$set': {'lease_expires_at': datetime.now(timezone.utc) + timedelta(seconds=60)}},
    )
    r_active = _recover_http(client, lib, job1['job_id'])
    assert r_active.status_code == 409 and 'lease' in r_active.json()['detail'].lower()

    _expire_job(database, job1['job_id'])
    # Wrong owner/role (librarian) denied; wrong tenant denied (404 when no job/lock there; 409 if spoofed lock references job1)
    assert _recover_http(client, lib, job1['job_id'], user=2).status_code == 403
    assert _recover_http(client, other_lib, job1['job_id'], user=1).status_code == 404
    assert database.institution_locks.find_one({'_id': lib, 'intelligence_job_id': job1['job_id']}) is not None

    # Wrong fence rejected without deleting lock
    database.institution_intelligence_targets.update_one(
        {'library_id': lib, 'target': target},
        {'$set': {'fence_token': 'wrong-fence-' + str(uuid4())}},
    )
    r_fence = _recover_http(client, lib, job1['job_id'])
    assert r_fence.status_code == 409
    assert database.institution_locks.find_one({'_id': lib, 'intelligence_job_id': job1['job_id']}) is not None

    # Restore exact fence & recover; then repeat recovery (already released)
    database.institution_intelligence_targets.update_one(
        {'library_id': lib, 'target': target},
        {'$set': {'fence_token': job1['fence_token']}},
    )
    r_ok = _recover_http(client, lib, job1['job_id'])
    assert r_ok.status_code == 200 and r_ok.json()['state'] == 'SUCCEEDED'
    assert database.institution_locks.find_one({'_id': lib}) is None
    ptr_after = database.institution_intelligence_targets.find_one({'library_id': lib, 'target': target})
    assert 'active_job_id' not in ptr_after and ptr_after['active_generation_id'] == job1['artifact_generation_id']
    r_repeat = _recover_http(client, lib, job1['job_id'])
    assert r_repeat.status_code == 200 and r_repeat.json()['state'] == 'SUCCEEDED'

    # Case 2: Crash after target unset (lock still present) & partially persisted job state (missing completed_at / fence_token)
    database.institution_locks.insert_one({
        '_id': lib,
        'holder': 'e01-partial-' + str(uuid4()),
        'acquired_at': datetime.now(timezone.utc),
        'intelligence_job_id': job1['job_id'],
        'intelligence_target': target,
    })
    database.institution_intelligence_jobs.update_one({'job_id': job1['job_id']}, {'$set': {'completed_at': None}})
    assert _recover_http(client, lib, job1['job_id']).status_code == 409
    assert database.institution_locks.find_one({'_id': lib, 'intelligence_job_id': job1['job_id']}) is not None
    database.institution_intelligence_jobs.update_one({'job_id': job1['job_id']}, {'$set': {'completed_at': datetime.now(timezone.utc), 'fence_token': None}})
    assert _recover_http(client, lib, job1['job_id']).status_code == 409
    assert database.institution_locks.find_one({'_id': lib, 'intelligence_job_id': job1['job_id']}) is not None
    database.institution_intelligence_jobs.update_one({'job_id': job1['job_id']}, {'$set': {'fence_token': job1['fence_token']}})
    assert _recover_http(client, lib, job1['job_id']).status_code == 200
    assert database.institution_locks.find_one({'_id': lib}) is None

    # Case 3: Terminal FAILED job with retained lock preserves previous valid active generation
    _seed_books(database, lib, count=1, prefix='Second fail book')
    job2 = _request_build(client, lib, target)
    def fail_build(stage):
        if stage == 'SERIALIZATION_ACK':
            raise HTTPException(409, 'BUILD_ABORTED')
    _make_worker(fail=fail_build).run_one()
    job2_doc = database.institution_intelligence_jobs.find_one({'job_id': job2['job_id']})
    assert job2_doc['state'] == 'FAILED' and job2_doc['effective_active'] is False
    database.institution_locks.insert_one({
        '_id': lib,
        'holder': 'e01-failed-' + str(uuid4()),
        'acquired_at': datetime.now(timezone.utc),
        'intelligence_job_id': job2['job_id'],
        'intelligence_target': target,
    })
    _expire_job(database, job2['job_id'])
    r_fail_rec = _recover_http(client, lib, job2['job_id'])
    assert r_fail_rec.status_code == 200 and r_fail_rec.json()['state'] == 'FAILED'
    assert database.institution_locks.find_one({'_id': lib}) is None
    assert database.institution_intelligence_targets.find_one({'library_id': lib, 'target': target})['active_generation_id'] == job1['artifact_generation_id']


def test_e01_concurrent_recovery_workers(client, database, library, intel_env):
    lib = library(owner=1, private=True)
    _seed_books(database, lib)
    _, job1, _ = _build_and_publish(client, database, lib, 'SEARCH_INDEX')
    database.institution_intelligence_targets.update_one(
        {'library_id': lib, 'target': 'SEARCH_INDEX'},
        {'$set': {'active_job_id': job1['job_id'], 'fence_token': job1['fence_token']}},
    )
    database.institution_locks.insert_one({
        '_id': lib,
        'holder': 'e01-conc-' + str(uuid4()),
        'acquired_at': datetime.now(timezone.utc),
        'intelligence_job_id': job1['job_id'],
        'intelligence_target': 'SEARCH_INDEX',
    })
    _expire_job(database, job1['job_id'])

    barrier = Barrier(4)
    def run_rec():
        barrier.wait(timeout=5)
        return service.recover(lib, {'sub': '1'}, job1['job_id'])

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = [f.result() for f in [pool.submit(run_rec) for _ in range(4)]]
    assert all(r['state'] == 'SUCCEEDED' for r in results)
    assert database.institution_locks.find_one({'_id': lib}) is None


# ============================================================
# PHASE 2B: E-02 INTERRUPTED FENCE RECOVERY
# ============================================================

@pytest.mark.parametrize('target', ['SEARCH_INDEX', 'KNOWLEDGE_GRAPH'])
@pytest.mark.parametrize('crash_stage', ['before_intent', 'after_intent', 'after_first_update', 'after_second_update', 'after_lock_delete'])
def test_e02_interrupted_fence_crash_stages_and_stale_worker(client, database, library, intel_env, target, crash_stage):
    lib = library(owner=1, private=True)
    _seed_books(database, lib)
    job_req = _request_build(client, lib, target)
    worker = _make_worker()
    # Claim & advance to PUBLISHING by simulating crash at PUBLISH
    job = store.claim(worker.worker_id)
    assert job is not None
    old_fence = job['fence_token']
    next_fence = str(uuid4())
    holder = 'e02-holder-' + str(uuid4())

    database.institution_intelligence_jobs.update_one(
        {'job_id': job['job_id']},
        {'$set': {'state': 'PUBLISHING', 'stage': 'PUBLISH', 'lease_expires_at': datetime.now(timezone.utc) - timedelta(seconds=120)}},
    )
    if crash_stage == 'before_intent':
        database.institution_locks.insert_one({'_id': lib, 'holder': holder, 'acquired_at': datetime.now(timezone.utc), 'intelligence_job_id': job['job_id'], 'intelligence_target': target})
    elif crash_stage == 'after_intent':
        database.institution_locks.insert_one({'_id': lib, 'holder': holder, 'acquired_at': datetime.now(timezone.utc), 'intelligence_job_id': job['job_id'], 'intelligence_target': target,
            'recovery_intent': {'job_id': job['job_id'], 'target': target, 'old_fence': old_fence, 'next_fence': next_fence}})
    elif crash_stage == 'after_first_update':
        database.institution_locks.insert_one({'_id': lib, 'holder': holder, 'acquired_at': datetime.now(timezone.utc), 'intelligence_job_id': job['job_id'], 'intelligence_target': target,
            'recovery_intent': {'job_id': job['job_id'], 'target': target, 'old_fence': old_fence, 'next_fence': next_fence}})
        database.institution_intelligence_targets.update_one({'library_id': lib, 'target': target}, {'$set': {'fence_token': next_fence, 'state': 'RECOVERY_REQUIRED'}})
    elif crash_stage == 'after_second_update':
        database.institution_locks.insert_one({'_id': lib, 'holder': holder, 'acquired_at': datetime.now(timezone.utc), 'intelligence_job_id': job['job_id'], 'intelligence_target': target,
            'recovery_intent': {'job_id': job['job_id'], 'target': target, 'old_fence': old_fence, 'next_fence': next_fence}})
        database.institution_intelligence_targets.update_one({'library_id': lib, 'target': target}, {'$set': {'fence_token': next_fence, 'state': 'RECOVERY_REQUIRED'}})
        database.institution_intelligence_jobs.update_one({'job_id': job['job_id']}, {'$set': {'fence_token': next_fence, 'state': 'RECOVERY_REQUIRED'}})
    elif crash_stage == 'after_lock_delete':
        database.institution_intelligence_targets.update_one({'library_id': lib, 'target': target}, {'$set': {'fence_token': next_fence, 'state': 'RECOVERY_REQUIRED'}})
        database.institution_intelligence_jobs.update_one({'job_id': job['job_id']}, {'$set': {'fence_token': next_fence, 'state': 'RECOVERY_REQUIRED'}})

    res = _recover_http(client, lib, job['job_id'])
    assert res.status_code == 200, res.text
    assert res.json()['state'] == 'FAILED'
    assert database.institution_locks.find_one({'_id': lib}) is None

    # Repeat retry is idempotent; old worker cannot resume with old_fence
    replay = _recover_http(client, lib, job['job_id'])
    assert replay.status_code == 200 and replay.json()['state'] == 'FAILED'
    with pytest.raises(HTTPException) as exc:
        store.check_lease(job)
    assert exc.value.detail == 'WORKER_FENCED'


def test_e02_negative_guards_and_concurrent_recovery(client, database, library, intel_env):
    lib = library(owner=1, private=True)
    _add_member(database, lib, 2, role='LIBRARIAN')
    _seed_books(database, lib)
    _request_build(client, lib, 'KNOWLEDGE_GRAPH')
    job = store.claim('worker-neg')
    old_fence = job['fence_token']
    next_fence = str(uuid4())
    holder = 'e02-neg-' + str(uuid4())
    _expire_job(database, job['job_id'])

    # Wrong owner (librarian)
    database.institution_locks.insert_one({'_id': lib, 'holder': holder, 'acquired_at': datetime.now(timezone.utc), 'intelligence_job_id': job['job_id'], 'intelligence_target': 'KNOWLEDGE_GRAPH'})
    assert _recover_http(client, lib, job['job_id'], user=2).status_code == 403

    # Newer fence exists -> refuses blind overwrite
    database.institution_intelligence_targets.update_one({'library_id': lib, 'target': 'KNOWLEDGE_GRAPH'}, {'$set': {'fence_token': str(uuid4())}})
    assert _recover_http(client, lib, job['job_id'], user=1).status_code == 409
    assert database.institution_locks.find_one({'_id': lib}) is not None

    # Corrupt unknown recovery_intent (same old_fence and next_fence) -> 409
    database.institution_intelligence_targets.update_one({'library_id': lib, 'target': 'KNOWLEDGE_GRAPH'}, {'$set': {'fence_token': old_fence}})
    database.institution_locks.update_one({'_id': lib}, {'$set': {'recovery_intent': {'job_id': job['job_id'], 'target': 'KNOWLEDGE_GRAPH', 'old_fence': old_fence, 'next_fence': old_fence}}})
    assert _recover_http(client, lib, job['job_id'], user=1).status_code == 409

    # Fix intent -> split-fence & concurrent recovery succeeds across all threads
    database.institution_locks.update_one({'_id': lib}, {'$set': {'recovery_intent': {'job_id': job['job_id'], 'target': 'KNOWLEDGE_GRAPH', 'old_fence': old_fence, 'next_fence': next_fence}}})
    database.institution_intelligence_targets.update_one({'library_id': lib, 'target': 'KNOWLEDGE_GRAPH'}, {'$set': {'fence_token': next_fence, 'state': 'RECOVERY_REQUIRED'}})
    barrier = Barrier(4)
    def run_conc():
        barrier.wait(timeout=5)
        return service.recover(lib, {'sub': '1'}, job['job_id'])
    with ThreadPoolExecutor(max_workers=4) as pool:
        outs = [f.result() for f in [pool.submit(run_conc) for _ in range(4)]]
    assert all(o['state'] == 'FAILED' for o in outs)
    assert database.institution_locks.find_one({'_id': lib}) is None

    # Missing target / missing job with tagged lock -> 409
    missing_job_id = str(uuid4())
    database.institution_locks.insert_one({'_id': lib, 'holder': 'h-missing-job', 'acquired_at': datetime.now(timezone.utc), 'intelligence_job_id': missing_job_id, 'intelligence_target': 'KNOWLEDGE_GRAPH'})
    assert _recover_http(client, lib, missing_job_id).status_code == 409
    database.institution_locks.delete_many({'_id': lib})

    database.institution_locks.insert_one({'_id': lib, 'holder': 'h-missing-tgt', 'acquired_at': datetime.now(timezone.utc), 'intelligence_job_id': job['job_id'], 'intelligence_target': 'KNOWLEDGE_GRAPH'})
    database.institution_intelligence_targets.delete_many({'library_id': lib, 'target': 'KNOWLEDGE_GRAPH'})
    assert _recover_http(client, lib, job['job_id']).status_code == 409


# ============================================================
# PHASE 2C: E-04 UNTAGGED BARRIER & GENERIC LOCK BOUNDARY
# ============================================================

@pytest.mark.parametrize('target', ['SEARCH_INDEX', 'KNOWLEDGE_GRAPH'])
def test_e04_insertion_time_tagging_crash_and_legacy_lock_boundary(client, database, library, intel_env, monkeypatch, target):
    lib = library(owner=1, private=True)
    other_lib = library(owner=1, private=True)
    _seed_books(database, lib)

    # Normal non-intelligence library_mutation leaves ZERO intelligence fields on lock
    observed_non_intel = []
    with repo.library_mutation(lib):
        observed_non_intel.append(database.institution_locks.find_one({'_id': lib}))
    assert observed_non_intel[0] is not None
    assert 'intelligence_job_id' not in observed_non_intel[0] and 'intelligence_target' not in observed_non_intel[0]

    # Queue job and simulate hard crash inside barrier right after insertion before claim updates job/target
    req = _request_build(client, lib, target)
    orig_store_collection = store.collection
    class _JobsProxy:
        def __init__(self, real):
            self._real = real
        def __getattr__(self, item):
            return getattr(self._real, item)
        def find_one_and_update(self, *args, **kwargs):
            lock_doc = database.institution_locks.find_one({'_id': lib})
            assert lock_doc is not None
            assert lock_doc.get('intelligence_job_id') == req['job_id']
            assert lock_doc.get('intelligence_target') == target
            raise RuntimeError('SIMULATED_SIGKILL_INSIDE_CLAIM')
    monkeypatch.setattr(store, 'collection', lambda name: _JobsProxy(orig_store_collection(name)) if name == 'intelligence_jobs' else orig_store_collection(name))
    with pytest.raises(HTTPException) as exc_claim:
        store.claim('worker-e04-crash')
    assert exc_claim.value.detail == 'WORKER_CRASH'
    monkeypatch.undo()
    # Re-insert tagged lock representing uncleaned SIGKILL lock at claim boundary
    database.institution_locks.insert_one({
        '_id': lib, 'holder': 'e04-kill-' + str(uuid4()), 'acquired_at': datetime.now(timezone.utc),
        'intelligence_job_id': req['job_id'], 'intelligence_target': target,
    })

    # Wrong tenant must NOT release lib's lock
    assert _recover_http(client, other_lib, req['job_id']).status_code == 404
    assert database.institution_locks.find_one({'_id': lib}) is not None

    # Wrong target on lock fails closed
    database.institution_locks.update_one({'_id': lib}, {'$set': {'intelligence_target': 'KNOWLEDGE_GRAPH' if target == 'SEARCH_INDEX' else 'SEARCH_INDEX'}})
    assert _recover_http(client, lib, req['job_id']).status_code == 409
    database.institution_locks.update_one({'_id': lib}, {'$set': {'intelligence_target': target}})

    # Genuine E-04 recovery succeeds and unlocks clean retry + concurrent claim test
    r_ok = _recover_http(client, lib, req['job_id'])
    assert r_ok.status_code == 200 and r_ok.json()['state'] == 'FAILED'
    assert database.institution_locks.find_one({'_id': lib}) is None

    # After recovery, a fresh build can be queued, claimed concurrently by 2 workers (only 1 claims), and published
    req2 = _request_build(client, lib, target)
    barrier = Barrier(2)
    def compete(wid):
        barrier.wait(timeout=5)
        return store.claim(wid)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed = [f.result() for f in [pool.submit(compete, 'w1'), pool.submit(compete, 'w2')]]
    winners = [c for c in claimed if c is not None]
    assert len(winners) == 1 and winners[0]['job_id'] == req2['job_id']
    # Finish running claimed job manually isn't needed if we release or run cleanly via fresh build; cancel via expire+recover or run_one:
    _expire_job(database, req2['job_id'])
    assert _recover_http(client, lib, req2['job_id']).status_code == 200

    # Legacy generic UNTAGGED lock MUST remain blocked with 503 (never auto-stolen)
    req3 = _request_build(client, lib, target)
    database.institution_locks.insert_one({'_id': lib, 'holder': 'legacy-generic-holder', 'acquired_at': datetime.now(timezone.utc)})
    _expire_job(database, req3['job_id'])
    r_legacy = _recover_http(client, lib, req3['job_id'])
    assert r_legacy.status_code == 503
    assert database.institution_locks.find_one({'_id': lib, 'holder': 'legacy-generic-holder'}) is not None


# ============================================================
# PHASE 3: COMBINED RECOVERY STATE MACHINE MATRIX (SCENARIOS A-T)
# ============================================================

def test_combined_20_scenario_recovery_interaction_matrix(client, database, library, intel_env, monkeypatch):
    ledger = []

    def snapshot(lib, target, job_id=None, worker=None):
        tgt = database.institution_intelligence_targets.find_one({'library_id': lib, 'target': target}) or {}
        job = database.institution_intelligence_jobs.find_one({'job_id': job_id}) if job_id else None
        lock = database.institution_locks.find_one({'_id': lib})
        reader = _observe_reader(worker, lib, target) if worker else None
        return {
            'durable_job_state': job.get('state') if job else None,
            'lock_ownership': {'holder': lock.get('holder'), 'intelligence_job_id': lock.get('intelligence_job_id'), 'intelligence_target': lock.get('intelligence_target')} if lock else None,
            'fence': {'job': job.get('fence_token') if job else None, 'target': tgt.get('fence_token')},
            'source_fingerprint': tgt.get('source_fingerprint'),
            'manifest_digest': tgt.get('manifest_checksum'),
            'pointer': {'active_generation_id': tgt.get('active_generation_id'), 'state': tgt.get('state'), 'published_by_job_id': tgt.get('published_by_job_id')},
            'job_receipt': store.safe_job(job) if job else None,
            'observed_reader_status': reader,
        }

    # A: Build, publish and acknowledge
    lib_a = library(owner=1, private=True); _seed_books(database, lib_a)
    ptr_before = snapshot(lib_a, 'SEARCH_INDEX')['pointer']
    w_a, j_a, _ = _build_and_publish(client, database, lib_a, 'SEARCH_INDEX')
    after_a = snapshot(lib_a, 'SEARCH_INDEX', j_a['job_id'], w_a)
    assert after_a['durable_job_state'] == 'SUCCEEDED' and after_a['observed_reader_status']['intelligence_status'] == 'READY'
    ledger.append({'scenario': 'A', 'original_state': 'NOT_BUILT', 'pointer_before': ptr_before, 'pointer_after': after_a['pointer'], 'recovery_result': 'NOT_NEEDED', **after_a})

    # B: Build fails after artifact creation (at CHECKSUM)
    lib_b = library(owner=1, private=True); _seed_books(database, lib_b)
    j_b = _request_build(client, lib_b, 'KNOWLEDGE_GRAPH')
    ptr_b0 = snapshot(lib_b, 'KNOWLEDGE_GRAPH')['pointer']
    def f_b(st):
        if st == 'CHECKSUM': raise HTTPException(409, 'CHECK_FAIL')
    w_b = _make_worker(fail=f_b); w_b.run_one()
    after_b = snapshot(lib_b, 'KNOWLEDGE_GRAPH', j_b['job_id'], w_b)
    assert after_b['durable_job_state'] == 'FAILED' and after_b['pointer']['active_generation_id'] is None
    ledger.append({'scenario': 'B', 'original_state': 'NOT_BUILT', 'pointer_before': ptr_b0, 'pointer_after': after_b['pointer'], 'recovery_result': 'FAILED_CLEAN', **after_b})

    # C: Build fails after rename (at HEARTBEAT/PUBLISH)
    lib_c = library(owner=1, private=True); _seed_books(database, lib_c)
    j_c = _request_build(client, lib_c, 'SEARCH_INDEX')
    ptr_c0 = snapshot(lib_c, 'SEARCH_INDEX')['pointer']
    def f_c(st):
        if st == 'HEARTBEAT': raise HTTPException(409, 'POST_RENAME_FAIL')
    w_c = _make_worker(fail=f_c); w_c.run_one()
    after_c = snapshot(lib_c, 'SEARCH_INDEX', j_c['job_id'], w_c)
    assert after_c['durable_job_state'] == 'FAILED' and after_c['pointer']['active_generation_id'] is None
    ledger.append({'scenario': 'C', 'original_state': 'NOT_BUILT', 'pointer_before': ptr_c0, 'pointer_after': after_c['pointer'], 'recovery_result': 'FAILED_CLEAN', **after_c})

    # D: Build fails after pointer publication (at ACKNOWLEDGEMENT_LOSS) + recover
    lib_d = library(owner=1, private=True); _seed_books(database, lib_d)
    j_d = _request_build(client, lib_d, 'KNOWLEDGE_GRAPH')
    ptr_d0 = snapshot(lib_d, 'KNOWLEDGE_GRAPH')['pointer']
    def f_d(st):
        if st == 'ACKNOWLEDGEMENT_LOSS': raise HTTPException(409, 'ACK_FAIL')
    w_d = _make_worker(fail=f_d); w_d.run_one()
    _expire_job(database, j_d['job_id'])
    rec_d = _recover_http(client, lib_d, j_d['job_id']).json()
    after_d = snapshot(lib_d, 'KNOWLEDGE_GRAPH', j_d['job_id'], w_d)
    assert rec_d['state'] == 'SUCCEEDED' and after_d['observed_reader_status']['status'] == 'READY'
    ledger.append({'scenario': 'D', 'original_state': 'NOT_BUILT', 'pointer_before': ptr_d0, 'pointer_after': after_d['pointer'], 'recovery_result': rec_d['state'], **after_d})

    # E: Terminal write succeeds but process stops before lock release (E-01)
    lib_e = library(owner=1, private=True); _seed_books(database, lib_e)
    w_e, j_e, _ = _build_and_publish(client, database, lib_e, 'SEARCH_INDEX')
    database.institution_intelligence_targets.update_one({'library_id': lib_e, 'target': 'SEARCH_INDEX'}, {'$set': {'active_job_id': j_e['job_id'], 'fence_token': j_e['fence_token']}})
    database.institution_locks.insert_one({'_id': lib_e, 'holder': 'sc-e', 'acquired_at': datetime.now(timezone.utc), 'intelligence_job_id': j_e['job_id'], 'intelligence_target': 'SEARCH_INDEX'})
    _expire_job(database, j_e['job_id'])
    ptr_e0 = snapshot(lib_e, 'SEARCH_INDEX', j_e['job_id'])['pointer']
    rec_e = _recover_http(client, lib_e, j_e['job_id']).json()
    after_e = snapshot(lib_e, 'SEARCH_INDEX', j_e['job_id'], w_e)
    assert rec_e['state'] == 'SUCCEEDED' and after_e['lock_ownership'] is None
    ledger.append({'scenario': 'E', 'original_state': 'READY_WITH_RETAINED_LOCK', 'pointer_before': ptr_e0, 'pointer_after': after_e['pointer'], 'recovery_result': rec_e['state'], **after_e})

    # F: Recovery fence partially persists (E-02)
    lib_f = library(owner=1, private=True); _seed_books(database, lib_f)
    j_f_req = _request_build(client, lib_f, 'SEARCH_INDEX')
    j_f = store.claim('w-f')
    next_f = str(uuid4())
    database.institution_locks.insert_one({'_id': lib_f, 'holder': 'sc-f', 'acquired_at': datetime.now(timezone.utc), 'intelligence_job_id': j_f['job_id'], 'intelligence_target': 'SEARCH_INDEX',
        'recovery_intent': {'job_id': j_f['job_id'], 'target': 'SEARCH_INDEX', 'old_fence': j_f['fence_token'], 'next_fence': next_f}})
    database.institution_intelligence_targets.update_one({'library_id': lib_f, 'target': 'SEARCH_INDEX'}, {'$set': {'fence_token': next_f, 'state': 'RECOVERY_REQUIRED'}})
    _expire_job(database, j_f['job_id'])
    ptr_f0 = snapshot(lib_f, 'SEARCH_INDEX', j_f['job_id'])['pointer']
    rec_f = _recover_http(client, lib_f, j_f['job_id']).json()
    after_f = snapshot(lib_f, 'SEARCH_INDEX', j_f['job_id'], w_a)
    assert rec_f['state'] == 'FAILED' and after_f['lock_ownership'] is None
    ledger.append({'scenario': 'F', 'original_state': 'SPLIT_FENCE_RECOVERY_REQUIRED', 'pointer_before': ptr_f0, 'pointer_after': after_f['pointer'], 'recovery_result': rec_f['state'], **after_f})

    # G: Claim crashes before ownership tagging completes update (E-04)
    lib_g = library(owner=1, private=True); _seed_books(database, lib_g)
    j_g = _request_build(client, lib_g, 'KNOWLEDGE_GRAPH')
    database.institution_locks.insert_one({'_id': lib_g, 'holder': 'sc-g', 'acquired_at': datetime.now(timezone.utc), 'intelligence_job_id': j_g['job_id'], 'intelligence_target': 'KNOWLEDGE_GRAPH'})
    ptr_g0 = snapshot(lib_g, 'KNOWLEDGE_GRAPH', j_g['job_id'])['pointer']
    rec_g = _recover_http(client, lib_g, j_g['job_id']).json()
    after_g = snapshot(lib_g, 'KNOWLEDGE_GRAPH', j_g['job_id'], w_d)
    assert rec_g['state'] == 'FAILED' and after_g['lock_ownership'] is None
    ledger.append({'scenario': 'G', 'original_state': 'QUEUED_WITH_BARRIER_LOCK', 'pointer_before': ptr_g0, 'pointer_after': after_g['pointer'], 'recovery_result': rec_g['state'], **after_g})

    # H: Two workers race to recover
    lib_h = library(owner=1, private=True); _seed_books(database, lib_h)
    _request_build(client, lib_h, 'SEARCH_INDEX')
    j_h = store.claim('w-h')
    database.institution_locks.insert_one({'_id': lib_h, 'holder': 'sc-h', 'acquired_at': datetime.now(timezone.utc), 'intelligence_job_id': j_h['job_id'], 'intelligence_target': 'SEARCH_INDEX'})
    _expire_job(database, j_h['job_id'])
    ptr_h0 = snapshot(lib_h, 'SEARCH_INDEX', j_h['job_id'])['pointer']
    bar_h = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outs_h = [f.result() for f in [pool.submit(lambda: (bar_h.wait(5), service.recover(lib_h, {'sub': '1'}, j_h['job_id']))[1]) for _ in range(2)]]
    after_h = snapshot(lib_h, 'SEARCH_INDEX', j_h['job_id'], w_a)
    assert all(o['state'] == 'FAILED' for o in outs_h) and after_h['lock_ownership'] is None
    ledger.append({'scenario': 'H', 'original_state': 'EXPIRED_LOCKED', 'pointer_before': ptr_h0, 'pointer_after': after_h['pointer'], 'recovery_result': 'FAILED', **after_h})

    # I: Worker loses lease before publication CAS (expire during HEARTBEAT -> check_lease raises WORKER_FENCED)
    lib_i = library(owner=1, private=True); _seed_books(database, lib_i)
    j_i = _request_build(client, lib_i, 'SEARCH_INDEX')
    ptr_i0 = snapshot(lib_i, 'SEARCH_INDEX')['pointer']
    def f_i(st):
        if st == 'HEARTBEAT': _expire_job(database, j_i['job_id'])
    w_i = _make_worker(fail=f_i); w_i.run_one()
    after_i = snapshot(lib_i, 'SEARCH_INDEX', j_i['job_id'], w_i)
    assert after_i['durable_job_state'] == 'RECOVERY_REQUIRED' and after_i['pointer']['active_generation_id'] is None
    rec_i = _recover_http(client, lib_i, j_i['job_id']).json()
    after_i2 = snapshot(lib_i, 'SEARCH_INDEX', j_i['job_id'], w_i)
    ledger.append({'scenario': 'I', 'original_state': 'LEASE_EXPIRED_AT_PUBLISH', 'pointer_before': ptr_i0, 'pointer_after': after_i2['pointer'], 'recovery_result': rec_i['state'], **after_i2})

    # J: Source changes during build
    lib_j = library(owner=1, private=True); _seed_books(database, lib_j)
    j_j = _request_build(client, lib_j, 'KNOWLEDGE_GRAPH')
    ptr_j0 = snapshot(lib_j, 'KNOWLEDGE_GRAPH')['pointer']
    def f_j(st):
        if st == 'HEARTBEAT': _seed_books(database, lib_j, count=1, prefix='Mid-build book')
    w_j = _make_worker(fail=f_j); w_j.run_one()
    after_j = snapshot(lib_j, 'KNOWLEDGE_GRAPH', j_j['job_id'], w_j)
    assert after_j['durable_job_state'] == 'FAILED' and after_j['pointer']['active_generation_id'] is None
    ledger.append({'scenario': 'J', 'original_state': 'SOURCE_MUTATED_MID_BUILD', 'pointer_before': ptr_j0, 'pointer_after': after_j['pointer'], 'recovery_result': 'FAILED', **after_j})

    # K: Admin membership is revoked during build; backup admin recovers
    lib_k = library(owner=1, private=True); _seed_books(database, lib_k)
    _add_member(database, lib_k, 3, role='ADMIN')
    j_k = _request_build(client, lib_k, 'SEARCH_INDEX', user=1)
    ptr_k0 = snapshot(lib_k, 'SEARCH_INDEX')['pointer']
    def f_k(st):
        if st == 'HEARTBEAT': database.institution_memberships.update_one({'library_id': lib_k, 'user_id': 1}, {'$set': {'status': 'REVOKED'}})
    w_k = _make_worker(fail=f_k); w_k.run_one()
    assert _recover_http(client, lib_k, j_k['job_id'], user=1).status_code == 404
    assert _recover_http(client, lib_k, j_k['job_id'], user=3).status_code == 200
    after_k = snapshot(lib_k, 'SEARCH_INDEX', j_k['job_id'])
    after_k['observed_reader_status'] = _observe_reader(w_k, lib_k, 'SEARCH_INDEX', user=3)
    assert after_k['durable_job_state'] == 'FAILED'
    ledger.append({'scenario': 'K', 'original_state': 'ADMIN_REVOKED_MID_BUILD', 'pointer_before': ptr_k0, 'pointer_after': after_k['pointer'], 'recovery_result': 'REVOKED_DENIED_404_BACKUP_OK', **after_k})

    # L: Library becomes suspended during build
    lib_l = library(owner=1, private=True); _seed_books(database, lib_l)
    j_l = _request_build(client, lib_l, 'KNOWLEDGE_GRAPH')
    ptr_l0 = snapshot(lib_l, 'KNOWLEDGE_GRAPH')['pointer']
    def f_l(st):
        if st == 'HEARTBEAT': database.institution_libraries.update_one({'library_id': lib_l}, {'$set': {'status': 'SUSPENDED'}})
    w_l = _make_worker(fail=f_l); w_l.run_one()
    with pytest.raises(HTTPException) as exc_l:
        _observe_reader(w_l, lib_l, 'KNOWLEDGE_GRAPH')
    after_l = snapshot(lib_l, 'KNOWLEDGE_GRAPH', j_l['job_id'])
    after_l['observed_reader_status'] = {'http_status': exc_l.value.status_code}
    assert after_l['durable_job_state'] == 'FAILED' and after_l['pointer']['active_generation_id'] is None
    ledger.append({'scenario': 'L', 'original_state': 'LIBRARY_SUSPENDED_MID_BUILD', 'pointer_before': ptr_l0, 'pointer_after': after_l['pointer'], 'recovery_result': 'FAILED', **after_l})

    # M: Prior valid generation exists when subsequent job fails
    lib_m = library(owner=1, private=True); _seed_books(database, lib_m)
    w_m, j_m1, ptr_m1 = _build_and_publish(client, database, lib_m, 'SEARCH_INDEX')
    ptr_m0 = snapshot(lib_m, 'SEARCH_INDEX')['pointer']
    _seed_books(database, lib_m, count=1, prefix='Scenario M second book')
    j_m2 = _request_build(client, lib_m, 'SEARCH_INDEX')
    def f_m(st):
        if st == 'SERIALIZATION_ACK': raise HTTPException(409, 'ABORT_M')
    w_m2 = _make_worker(fail=f_m); w_m2.run_one()
    after_m = snapshot(lib_m, 'SEARCH_INDEX', j_m2['job_id'], w_m2)
    assert after_m['pointer']['active_generation_id'] == j_m1['artifact_generation_id']
    ledger.append({'scenario': 'M', 'original_state': 'PRIOR_READY', 'pointer_before': ptr_m0, 'pointer_after': after_m['pointer'], 'recovery_result': 'PRIOR_RETAINED', **after_m})

    # N: No prior generation exists when job fails
    lib_n = library(owner=1, private=True); _seed_books(database, lib_n)
    j_n = _request_build(client, lib_n, 'SEARCH_INDEX')
    ptr_n0 = snapshot(lib_n, 'SEARCH_INDEX')['pointer']
    _make_worker(fail=lambda st: (_ for _ in ()).throw(HTTPException(409, 'FAIL_N')) if st == 'FAISS_BUILD' else None).run_one()
    after_n = snapshot(lib_n, 'SEARCH_INDEX', j_n['job_id'], w_a)
    assert after_n['pointer']['active_generation_id'] is None and after_n['observed_reader_status']['search_source'] == 'LOCAL_FALLBACK'
    ledger.append({'scenario': 'N', 'original_state': 'NOT_BUILT', 'pointer_before': ptr_n0, 'pointer_after': after_n['pointer'], 'recovery_result': 'LOCAL_FALLBACK', **after_n})

    # O: Restart and repeat recovery idempotently
    lib_o = library(owner=1, private=True); _seed_books(database, lib_o)
    j_o = _request_build(client, lib_o, 'KNOWLEDGE_GRAPH')
    ptr_o0 = snapshot(lib_o, 'KNOWLEDGE_GRAPH')['pointer']
    def f_o(st):
        if st == 'PUBLISH': raise HTTPException(409, 'WORKER_CRASH')
    _make_worker(fail=f_o).run_one()
    _expire_job(database, j_o['job_id'])
    r_o1 = _recover_http(client, lib_o, j_o['job_id']).json()
    r_o2 = _recover_http(client, lib_o, j_o['job_id']).json()
    after_o = snapshot(lib_o, 'KNOWLEDGE_GRAPH', j_o['job_id'], w_d)
    assert r_o1['state'] == r_o2['state'] == 'FAILED'
    ledger.append({'scenario': 'O', 'original_state': 'RECOVERY_REQUIRED', 'pointer_before': ptr_o0, 'pointer_after': after_o['pointer'], 'recovery_result': r_o2['state'], **after_o})

    # P: Repeated same-target build request while active returns same job cleanly
    lib_p = library(owner=1, private=True); _seed_books(database, lib_p)
    j_p1 = _request_build(client, lib_p, 'SEARCH_INDEX')
    j_p2 = _request_build(client, lib_p, 'SEARCH_INDEX')
    assert j_p1['job_id'] == j_p2['job_id']
    w_p = _make_worker(); w_p.run_one()
    after_p = snapshot(lib_p, 'SEARCH_INDEX', j_p1['job_id'], w_p)
    ledger.append({'scenario': 'P', 'original_state': 'QUEUED', 'pointer_before': {'active_generation_id': None, 'state': 'QUEUED'}, 'pointer_after': after_p['pointer'], 'recovery_result': 'DEDUPED_AND_SUCCEEDED', **after_p})

    # Q: Wrong-tenant recovery attempt denied without affecting owning tenant
    lib_q1 = library(owner=1, private=True); _seed_books(database, lib_q1)
    lib_q2 = library(owner=1, private=True)
    j_q = _request_build(client, lib_q1, 'SEARCH_INDEX')
    resp_q = _recover_http(client, lib_q2, j_q['job_id'])
    assert resp_q.status_code == 404
    _make_worker().run_one()
    after_q = snapshot(lib_q1, 'SEARCH_INDEX', j_q['job_id'], w_a)
    assert after_q['durable_job_state'] == 'SUCCEEDED'
    ledger.append({'scenario': 'Q', 'original_state': 'QUEUED', 'pointer_before': {'active_generation_id': None, 'state': 'QUEUED'}, 'pointer_after': after_q['pointer'], 'recovery_result': 'CROSS_TENANT_DENIED_404', **after_q})

    # R: Concurrent Search and KG jobs on same tenant publish cleanly and independently
    lib_r = library(owner=1, private=True); _seed_books(database, lib_r)
    jr_s = _request_build(client, lib_r, 'SEARCH_INDEX')
    jr_k = _request_build(client, lib_r, 'KNOWLEDGE_GRAPH')
    bar_r = Barrier(2)
    def run_worker_pair():
        bar_r.wait(timeout=5)
        w = _make_worker()
        processed = 0
        while w.run_one():
            processed += 1
        return processed
    with ThreadPoolExecutor(max_workers=2) as pool:
        counts = [f.result() for f in [pool.submit(run_worker_pair), pool.submit(run_worker_pair)]]
    assert sum(counts) == 2
    after_rs = snapshot(lib_r, 'SEARCH_INDEX', jr_s['job_id'], w_a)
    after_rk = snapshot(lib_r, 'KNOWLEDGE_GRAPH', jr_k['job_id'], w_a)
    assert after_rs['durable_job_state'] == 'SUCCEEDED' and after_rk['durable_job_state'] == 'SUCCEEDED'
    ledger.append({'scenario': 'R', 'original_state': 'NOT_BUILT_BOTH', 'pointer_before': None, 'pointer_after': {'SEARCH_INDEX': after_rs['pointer'], 'KNOWLEDGE_GRAPH': after_rk['pointer']}, 'recovery_result': 'BOTH_SUCCEEDED', **after_rs})

    # S: Corrupt KG artifact while Search valid generation remains available
    lib_s = library(owner=1, private=True); _seed_books(database, lib_s)
    w_s, js_s, _ = _build_and_publish(client, database, lib_s, 'SEARCH_INDEX')
    _, jk_s, ptr_ks = _build_and_publish(client, database, lib_s, 'KNOWLEDGE_GRAPH')
    k_manifest = store.directory(lib_s, 'kg', ptr_ks['active_generation_id']) / 'manifest.json'
    _tamper_manifest_json(k_manifest, target='SEARCH_INDEX')
    obs_ss = _observe_reader(w_s, lib_s, 'SEARCH_INDEX')
    obs_sk = _observe_reader(w_s, lib_s, 'KNOWLEDGE_GRAPH')
    assert obs_ss['intelligence_status'] == 'READY' and obs_sk['status'] == 'RECOVERY_REQUIRED'
    after_s = snapshot(lib_s, 'KNOWLEDGE_GRAPH', jk_s['job_id'], w_s)
    ledger.append({'scenario': 'S', 'original_state': 'BOTH_READY_KG_CORRUPTED', 'pointer_before': ptr_ks.get('active_generation_id'), 'pointer_after': {'SEARCH_INDEX': obs_ss, 'KNOWLEDGE_GRAPH': obs_sk}, 'recovery_result': 'ISOLATED_CORRUPTION', **after_s})

    # T: Old job recovery after a subsequent valid job succeeded preserves subsequent generation
    lib_t = library(owner=1, private=True); _seed_books(database, lib_t)
    jt_1 = _request_build(client, lib_t, 'SEARCH_INDEX')
    _make_worker(fail=lambda st: (_ for _ in ()).throw(HTTPException(409, 'FAIL_T1')) if st == 'CHECKSUM' else None).run_one()
    w_t, jt_2, ptr_t2 = _build_and_publish(client, database, lib_t, 'SEARCH_INDEX')
    r_t = _recover_http(client, lib_t, jt_1['job_id'])
    after_t = snapshot(lib_t, 'SEARCH_INDEX', jt_2['job_id'], w_t)
    assert r_t.status_code == 200 and after_t['pointer']['active_generation_id'] == ptr_t2['active_generation_id']
    ledger.append({'scenario': 'T', 'original_state': 'SUBSEQUENT_READY', 'pointer_before': ptr_t2['active_generation_id'], 'pointer_after': after_t['pointer'], 'recovery_result': 'SUBSEQUENT_PRESERVED', **after_t})

    assert len(ledger) == 20
    if database.name.startswith('luminar_institution_v2g_test_'):
        MATRIX_REPORT.write_text(json.dumps(ledger, indent=2, default=str), encoding='utf8')
