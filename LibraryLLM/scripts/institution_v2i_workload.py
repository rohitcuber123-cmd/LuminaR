"""Bounded real tenant builds, offline cached MiniLM, disposable Mongo/artifacts."""
import os
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
import json
import gc
from pathlib import Path
import sys
import tempfile
from threading import Event, Thread
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.institution_v2i_benchmark import seed, db, mongo, repo, inventory, store, DBNAME
from backend.services import library_intelligence_artifacts as artifacts
from search.library_intelligence import TenantIntelligence


def main():
    import psutil
    import torch
    import faiss
    from sentence_transformers import SentenceTransformer
    torch.set_num_threads(2)
    faiss.omp_set_num_threads(2)
    cache = Path.home() / '.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2'
    revision = (cache / 'refs/main').read_text().strip()
    path = cache / 'snapshots' / revision
    started = time.perf_counter()
    model = SentenceTransformer(str(path), device='cpu', local_files_only=True)
    model.max_seq_length = 256
    result = {'database': DBNAME, 'model': store.MODEL, 'revision': revision,
              'offline_only': True, 'device': 'cpu', 'model_load_ms': (time.perf_counter()-started)*1000,
              'torch_threads': 2, 'faiss_threads': 2, 'samples_per_configuration': 1,
              'limits': 'Representative bounded workloads, no production latency SLO or large-tenant GPU extrapolation.',
              'cases': []}
    process = psutil.Process()
    with tempfile.TemporaryDirectory(prefix='luminar-v2i-build-') as tmp:
        os.environ['LIBRARY_INTELLIGENCE_ROOT'] = tmp
        try:
            repo.ensure_indexes()
            inventory.ensure_indexes()
            store.initialize()
            db.users.insert_one({'user_id': 1, 'email': 'fixture@example.com', 'is_active': True,
                                 'is_email_verified': True, 'role': 'GENERAL_USER'})
            for n in [10, 100, 1000]:
                lib = seed(n, published=False)
                for target in ['SEARCH_INDEX', 'KNOWLEDGE_GRAPH']:
                    for cache_mode in ['first_build', 'unchanged_rebuild']:
                        metrics = {'eligible_books': n, 'target': target, 'cache_mode': cache_mode,
                                   'encoder_calls': 0, 'encoded_books': 0, 'embedding_ms': 0,
                                   'cache_hits': 0, 'cache_misses': 0, 'source_reads_ms': [],
                                   'validation_ms': [], 'gpu_memory': 'NOT_USED_CPU', 'stages': []}
                        def encode(texts):
                            at = time.perf_counter()
                            v = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
                            metrics['encoder_calls'] += 1
                            metrics['encoded_books'] += len(texts)
                            metrics['embedding_ms'] += (time.perf_counter()-at)*1000
                            return v
                        marks = {}
                        def stage(name):
                            marks.setdefault(name, time.perf_counter())
                            if name not in metrics['stages']:
                                metrics['stages'].append(name)
                        original_get, original_source, original_validate = artifacts.VectorCache.get, store.source_records, artifacts.validate
                        def get(cache_instance, record):
                            v = original_get(cache_instance, record)
                            metrics['cache_hits' if v is not None else 'cache_misses'] += 1
                            return v
                        def source(library_id):
                            at = time.perf_counter()
                            rows = original_source(library_id)
                            metrics['source_reads_ms'].append((time.perf_counter()-at)*1000)
                            return rows
                        def validate(*a, **kw):
                            at = time.perf_counter()
                            value = original_validate(*a, **kw)
                            metrics['validation_ms'].append((time.perf_counter()-at)*1000)
                            return value
                        artifacts.VectorCache.get, store.source_records, artifacts.validate = get, source, validate
                        stopped = Event()
                        peak = [process.memory_info().rss]
                        metrics['rss_before_bytes'] = peak[0]
                        def memory():
                            while not stopped.wait(.01):
                                peak[0] = max(peak[0], process.memory_info().rss)
                        sampler = Thread(target=memory, daemon=True)
                        sampler.start()
                        try:
                            request = store.request_build(lib, {'sub': '1'}, target)
                            worker = TenantIntelligence(encode, model_version=store.MODEL+':'+revision+':normalized384-v1', fail=stage)
                            at, cpu = time.perf_counter(), time.process_time()
                            assert worker.run_one()
                            metrics['build_ms'] = (time.perf_counter()-at)*1000
                            metrics['cpu_ms'] = (time.process_time()-cpu)*1000
                            job = store.collection('intelligence_jobs').find_one({'job_id': request['job_id']})
                            assert job['state'] == 'SUCCEEDED', job.get('error_code')
                            pointer = store.collection('intelligence_targets').find_one({'library_id': lib, 'target': target})
                            final = store.directory(lib, 'search' if target == 'SEARCH_INDEX' else 'kg', job['artifact_generation_id'])
                            metrics['artifact_bytes'] = sum(p.stat().st_size for p in final.iterdir())
                            metrics['embedding_cache_bytes'] = (store.root()/lib/'embedding-cache.sqlite').stat().st_size if (store.root()/lib/'embedding-cache.sqlite').exists() else 0
                            metrics['retained_tenant_bytes'] = sum(p.stat().st_size for p in (store.root()/lib).rglob('*') if p.is_file())
                            metrics['node_count'], metrics['edge_count'] = pointer.get('node_count'), pointer.get('edge_count')
                            metrics['faiss_construction_ms'] = (marks['FAISS_SERIALIZATION']-marks['FAISS_BUILD'])*1000 if 'FAISS_BUILD' in marks else None
                            metrics['graph_construction_serialization_ms'] = (marks['CHECKSUM']-marks['KG_NODES'])*1000 if 'KG_NODES' in marks else None
                            metrics['pointer_publication_ms'] = (marks['ACKNOWLEDGEMENT_LOSS']-marks['PUBLISH'])*1000
                            metrics['temporary_payload_bytes_before_rename'] = metrics['artifact_bytes']
                            metrics['publication_and_last_good'] = 'SUCCEEDED; immutable rename and fenced pointer; prior generation retained on rebuild'
                        finally:
                            stopped.set()
                            sampler.join()
                            metrics['sampled_peak_rss_bytes'] = peak[0]
                            metrics['sampled_peak_rss_increase_bytes'] = peak[0]-metrics['rss_before_bytes']
                            metrics['memory_limit'] = '10 ms process RSS sampler; native peaks shorter than interval may be missed; resident model included.'
                            artifacts.VectorCache.get, store.source_records, artifacts.validate = original_get, original_source, original_validate
                        result['cases'].append(metrics)
                        (ROOT/'reports/institution_v2i_workload_benchmark.json').write_text(json.dumps(result, indent=2))
                        print(target, n, cache_mode, round(metrics['build_ms'], 2), metrics['encoded_books'], flush=True)
        finally:
            assert db.name == DBNAME and DBNAME.startswith('luminar_institution_v2i_benchmark_')
            mongo.drop_database(DBNAME)
            result['disposable_database_removed'] = True
            # Existing VectorCache uses sqlite transaction context managers;
            # CPython may defer closing those handles until cyclic collection.
            # Do not change production lifecycle as part of a benchmark.
            gc.collect()
    result['owned_temporary_artifacts_removed'] = True
    (ROOT/'reports/institution_v2i_workload_benchmark.json').write_text(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
