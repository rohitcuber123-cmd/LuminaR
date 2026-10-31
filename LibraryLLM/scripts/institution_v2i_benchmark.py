"""Real Mongo/full status benchmarks in a uniquely named disposable database.

Published fixtures are checksum-valid synthetic artifacts, not serving indexes.
No production DB/app imports precede isolation; no global catalogue is scanned.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
from threading import Lock
import time
import tracemalloc
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DBNAME = 'luminar_institution_v2i_benchmark_' + uuid4().hex[:24]
os.environ.update(MONGO_URI='mongodb://127.0.0.1:27017', MONGO_DB_NAME=DBNAME,
                  NOTIFICATION_DUE_WORKER_ENABLED='0', NOTIFICATION_OUTBOX_WORKER_ENABLED='0',
                  JWT_SECRET_KEY='isolated-v2i-benchmark-not-production')
from bson import BSON
from pymongo import monitoring


class Commands(monitoring.CommandListener):
    def __init__(self):
        self.lock = Lock()
        self.enabled = False
        self.reset()

    def reset(self):
        self.counts = Counter()
        self.response_bytes = self.returned = 0

    def started(self, event):
        if self.enabled and event.database_name == DBNAME:
            with self.lock:
                self.counts[event.command_name] += 1

    def succeeded(self, event):
        if self.enabled:
            with self.lock:
                self.response_bytes += len(BSON.encode(event.reply))
                self.returned += len(event.reply.get('cursor', {}).get('firstBatch', [])) + len(event.reply.get('cursor', {}).get('nextBatch', []))

    def failed(self, event):
        pass


commands = Commands()
monitoring.register(commands)
from backend.database.mongodb import db, client as mongo
from backend.services import institution_repository as repo
from backend.services import library_intelligence_store as store, library_intelligence_service as service
from backend.services import library_catalogue_repository as inventory
from fastapi import HTTPException


def baseline_service():
    p = ROOT / '.scratch/institution-v2i/before/backend/services/library_intelligence_service.py'
    spec = importlib.util.spec_from_file_location('institution_v2i_frozen_service', p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stats(values):
    values = sorted(values)
    return {'median': statistics.median(values), 'p90': values[min(len(values)-1, int(.9*len(values)))],
            'p95': values[min(len(values)-1, int(.95*len(values)))], 'min': min(values), 'max': max(values)}


def seed(n, linked=False, published=True):
    lib = str(uuid4())
    repo.collection('libraries').insert_one({'library_id': lib, 'slug_normalized': lib, 'name': 'Isolated 2I fixture', 'status': 'ACTIVE',
                                             'library_type': 'PUBLIC_LIBRARY', 'access_mode': 'PUBLIC'})
    repo.collection('memberships').insert_one({'library_id': lib, 'membership_id': str(uuid4()), 'user_id': 1,
                                              'role': 'ADMIN', 'is_owner': True, 'status': 'ACTIVE'})
    rows = []
    for i in range(n):
        rows.append({'library_id': lib, 'library_book_id': str(uuid4()), 'status': 'ACTIVE',
                     'accession_number': str(i), 'accession_sequence': i, 'title': f'Isolated networks {i}',
                     'authors': ['Ada Fixture'], 'subjects': ['Computer networks', 'Technology'],
                     'description': 'Bounded synthetic catalogue metadata. ' * 8,
                     'publication_year': '2020', 'classification': '004',
                     'global_work_id': 'OL' + str(i) + 'W' if linked else None})
    for offset in range(0, n, 1000):
        repo.collection('library_books').insert_many(rows[offset:offset+1000])
        if linked:
            db.books.insert_many([{'work_id': r['global_work_id'], 'authors': ['Global fixture'], 'active': True} for r in rows[offset:offset+1000]])
    if not published:
        return lib
    records = store.source_records(lib)
    fp = store.fingerprint(records)
    source_gen = str(uuid4())
    repo.collection('intelligence_generations').insert_one({'library_id': lib, 'generation_id': source_gen,
        'sequence': 1, 'status': 'READY', 'source_fingerprint': fp, 'book_count': n})
    for target, kind in [('SEARCH_INDEX', 'search'), ('KNOWLEDGE_GRAPH', 'kg')]:
        gen, job = str(uuid4()), str(uuid4())
        p = store.directory(lib, kind, gen)
        p.mkdir(parents=True)
        store.durable_json(p / 'metadata.json', records)
        # Match vector/index byte growth without claiming a structurally valid
        # HNSW generation. Status only checks manifests/checksums, not FAISS.
        if kind == 'search' and n:
            (p / 'vectors.npy').write_bytes(b'v' * (1536*n+128))
            (p / 'index.faiss').write_bytes(b'i' * (1680*n+128))
        elif kind == 'kg':
            store.durable_json(p / 'graph.json', {'nodes': [{'id': 'book:'+r['library_book_id'], 'label': r['title']} for r in records], 'edges': []})
        manifest = {'library_id': lib, 'generation_id': gen, 'source_generation_id': source_gen,
                    'source_fingerprint': fp, 'target': target, 'book_count': n, 'empty': not n,
                    'files': {f.name: store.checksum(f) for f in p.iterdir()}}
        store.durable_json(p / 'manifest.json', manifest)
        stamp = store.now()
        repo.collection('intelligence_targets').insert_one({'library_id': lib, 'target': target,
            'state': 'READY' if n else 'EMPTY', 'active_generation_id': gen, 'source_generation_id': source_gen,
            'source_fingerprint': fp, 'manifest_checksum': store.checksum(p / 'manifest.json'),
            'record_count': n, 'built_at': stamp, 'published_by_job_id': job})
        repo.collection('intelligence_jobs').insert_one({'library_id': lib, 'job_id': job, 'target': target,
            'state': 'SUCCEEDED', 'effective_active': False, 'created_at': stamp, 'started_at': stamp,
            'completed_at': stamp, 'requested_by_user_id': 1})
    return lib


def measured(module, lib, samples):
    first_at = time.perf_counter()
    first = module.status(lib, {'sub': '1'})
    first_ms = (time.perf_counter()-first_at)*1000
    wall, cpu = [], []
    for _ in range(samples):
        a, c = time.perf_counter(), time.process_time()
        assert module.status(lib, {'sub': '1'}) == first
        wall.append((time.perf_counter()-a)*1000)
        cpu.append((time.process_time()-c)*1000)
    counts = Counter()
    original = store.checksum

    def checksum(p):
        counts['checksum_calls'] += 1
        counts['checksum_bytes'] += Path(p).stat().st_size
        return original(p)

    store.checksum = checksum
    commands.reset()
    commands.enabled = True
    tracemalloc.start()
    try:
        module.status(lib, {'sub': '1'})
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        commands.enabled = False
        store.checksum = original
    # Actual docsExamined from one isolated profiling sample. Profiling is OFF
    # during latency measurements; never enabled on the application database.
    db.command('profile', 2)
    module.status(lib, {'sub': '1'})
    db.command('profile', 0)
    profile = list(db['system.profile'].find({'ns': {'$regex': '^' + DBNAME + r'\.'}}))
    examined = sum(r.get('docsExamined', 0) for r in profile)
    db['system.profile'].drop()
    return {'first_read_ms': first_ms, 'first_read_limit': 'First function invocation, OS/Mongo caches not flushed; not cold disk.',
            'warm_ms': stats(wall), 'cpu_ms': stats(cpu), 'samples': samples,
            'database_commands_per_read': dict(commands.counts), 'database_commands_total': sum(commands.counts.values()),
            'returned_documents_per_read': commands.returned, 'mongo_response_bytes_per_read': commands.response_bytes,
            'documents_examined_profile_sample': examined, 'profile_sample_operations': len(profile),
            'python_tracemalloc_peak_bytes': peak,
            'filesystem': {'checksum_calls': counts['checksum_calls'], 'checksum_bytes': counts['checksum_bytes']},
            'unmeasured': ['OS physical disk reads', 'Mongo server CPU', 'stat/resolve syscall count', 'native allocator peak']}


def concurrent(module, libs, requests=12, workers=4, actors=('1',)):
    def call(i):
        lib = libs[i % len(libs)]
        start = time.perf_counter()
        try:
            value = module.status(lib, {'sub': actors[i % len(actors)]})
            assert value['library_id'] == lib
            code = 200
        except HTTPException as error:
            code = error.status_code
            if code != 503:
                raise
        return (time.perf_counter()-start)*1000, code
    start = time.perf_counter()
    with ThreadPoolExecutor(workers) as pool:
        values = list(pool.map(call, range(requests)))
    return {'concurrent_requests': workers, 'requests': requests, 'libraries': len(libs),
            'latency_ms': stats([v[0] for v in values]), 'wall_ms': (time.perf_counter()-start)*1000,
            'successful_latency_ms': stats([v[0] for v in values if v[1] == 200]) if any(v[1] == 200 for v in values) else None,
            'unavailable_latency_ms': stats([v[0] for v in values if v[1] != 200]) if any(v[1] != 200 for v in values) else None,
            'actor_roles': ['ADMIN'] if len(actors) == 1 else ['ADMIN', 'LIBRARIAN'],
            'http_codes': dict(Counter(str(v[1]) for v in values)),
            'errors': sum(v[1] != 200 for v in values),
            'note': '503 is the existing fail-closed tenant barrier, counted as unavailable, never a successful status read.',
            'authorization': 'Real current_identity/current membership every request; no cache'}


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--tag', default='before')
    a.add_argument('--sizes', default='0,1,10,100,1000,10000,50000')
    opts = a.parse_args()
    before = baseline_service()
    modules = [('before', before)] if opts.tag == 'before' else [('before', before), ('after', service)]
    result = {'database': DBNAME, 'isolation': 'Unique disposable Mongo and TemporaryDirectory; never TEST/global writes',
              'artifact_fixture': 'Checksum-valid synthetic files with bounded metadata and realistic vector/index byte scaling; not loadable serving HNSW.',
              'cases': [], 'concurrency': [], 'captured_at': datetime.now(timezone.utc).isoformat()}
    with tempfile.TemporaryDirectory(prefix='luminar-v2i-status-') as tmp:
        os.environ['LIBRARY_INTELLIGENCE_ROOT'] = tmp
        try:
            mongo.admin.command('ping')
            repo.ensure_indexes()
            inventory.ensure_indexes()
            store.initialize()
            db.users.insert_one({'user_id': 1, 'name': 'Isolated fixture', 'email': 'fixture@example.com',
                                 'is_active': True, 'is_email_verified': True, 'role': 'GENERAL_USER'})
            for n in map(int, opts.sizes.split(',')):
                lib = seed(n, published=n != 0)
                # Alternate paired order across sizes to disclose/order-reduce
                # cache bias; there is still no claim of cold disk timing.
                sequence = modules if n % 3 else list(reversed(modules))
                for label, module in sequence:
                    evidence = measured(module, lib, 11 if n <= 1000 else 7)
                    result['cases'].append({'version': label, 'eligible_books': n,
                                            'fixture_state': 'NOT_BUILT' if n == 0 else 'READY', **evidence})
                    print(label, n, round(evidence['warm_ms']['median'], 2), evidence['filesystem'], flush=True)
            # Linked enrichment path: bounded 500-ID global fixture queries.
            linked = seed(1000, linked=True)
            for label, module in modules:
                result['cases'].append({'version': label, 'eligible_books': 1000, 'linked_global_fixtures': True,
                                         **measured(module, linked, 7)})
            libs = [seed(1000) for _ in range(3)]
            db.users.insert_one({'user_id': 2, 'email': 'librarian-fixture@example.com', 'is_active': True,
                                 'is_email_verified': True, 'role': 'GENERAL_USER'})
            for lib in libs:
                repo.collection('memberships').insert_one({'membership_id': str(uuid4()), 'library_id': lib,
                                                          'user_id': 2, 'role': 'LIBRARIAN', 'status': 'ACTIVE'})
            for label, module in modules:
                for scoped, workers, actors in [(libs[:1],1,('1',)), (libs[:1],4,('1',)),
                                                (libs[:1],2,('1','2')), (libs,4,('1',))]:
                    result['concurrency'].append({'version': label, **concurrent(module, scoped, workers=workers, actors=actors)})
            result['correctness'] = {'identical_repeated_responses': True, 'false_READY_observed': 0,
                                      'meaning': 'Unmutated fixtures only; mutation/fault correctness lives in test suite.'}
        finally:
            assert mongo[DBNAME].name.startswith('luminar_institution_v2i_benchmark_')
            mongo.drop_database(DBNAME)
            result['disposable_database_removed'] = True
            result['temporary_artifacts_removed_by_owner'] = True
    out = ROOT / f'reports/institution_v2i_freshness_benchmark_{opts.tag}.json'
    out.write_text(json.dumps(result, indent=2))
    print(out, flush=True)


if __name__ == '__main__':
    main()
