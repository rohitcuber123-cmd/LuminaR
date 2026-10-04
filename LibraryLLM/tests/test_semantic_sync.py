"""Isolated catalogue sync tests: real FAISS, fake Mongo/model, temp-only writes."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import threading
import types
from unittest.mock import MagicMock

import faiss
import numpy as np
import pytest

from search.catalogue import current_books, semantic_text
from search.index_manager import IndexManager, new_index, writer_lock
from search.sync_queue import CatalogueImportSync

DIM = 8


class Encoder:
    def __init__(self):
        self.texts = []
        self.fail = False
        self.callback = None

    def encode(self, texts, **kwargs):
        if self.fail:
            raise RuntimeError("test encoder failure")
        self.texts.extend(texts)
        if self.callback:
            callback, self.callback = self.callback, None
            callback()
        rows = []
        for text in texts:
            row = np.frombuffer(hashlib.sha256(text.encode()).digest()[:DIM], dtype=np.uint8).astype('float32') - 127
            rows.append(row / np.linalg.norm(row))
        return np.asarray(rows)


class Books:
    def __init__(self, rows):
        self.rows = {row['work_id']: dict(row) for row in rows}
        self.find_calls = 0
        self.fail = False

    def find(self, query, projection=None):
        if self.fail:
            raise RuntimeError('Mongo unavailable')
        self.find_calls += 1
        ids = query.get('work_id', {}).get('$in', self.rows)
        return [dict(self.rows[wid]) for wid in ids if wid in self.rows]


def book(wid, **kwargs):
    return dict(work_id=wid, title='Title ' + wid, authors='Author', description='Initial text',
                total_copies=2, available_copies=1, **kwargs)


def legacy(root, rows, encoder):
    root.mkdir(exist_ok=True)
    index = new_index(DIM)
    if rows:
        index.add(encoder.encode([semantic_text(row) for row in rows]))
    faiss.write_index(index, str(root/'hnsw.index'))
    np.save(root/'index_work_ids.npy', np.array([row['work_id'] for row in rows], dtype=str))
    (root/'hnsw_metadata.json').write_text(json.dumps(dict(model_name='all-MiniLM-L6-v2',
        dimension=DIM, normalized=True, metric='inner_product', vector_count=len(rows))))
    encoder.texts.clear()


@pytest.fixture(autouse=True)
def isolated_queue_path(tmp_path, monkeypatch):
    monkeypatch.setenv('LUMINAR_SEARCH_INDEX_DIR', str(tmp_path / 'queue-root'))


@pytest.fixture
def setup(tmp_path):
    faiss.omp_set_num_threads(1)
    encoder = Encoder()
    books = Books([book('A'), book('B')])
    legacy(tmp_path, list(books.rows.values()), encoder)
    manager = IndexManager(tmp_path, books, encoder, dimension=DIM, model_version='test-v1')
    return manager, books, encoder


def drain(manager):
    manager.queue.state('STALE')
    assert manager.process_once(), manager.status()


def candidates(manager, encoder):
    return manager.snapshot.candidates(encoder.encode(['query']), 100)


def test_create_only_new_vector_and_preserve_base(setup):
    manager, books, encoder = setup
    base = manager.snapshot.base
    original = base.reconstruct_n(0, base.ntotal).copy()
    books.rows['C'] = book('C')
    manager.add_book('C')
    drain(manager)
    assert encoder.texts == [semantic_text(books.rows['C'])]
    assert manager.snapshot.base is base
    np.testing.assert_array_equal(base.reconstruct_n(0, base.ntotal), original)
    assert manager.snapshot.delta.ntotal == 1
    assert {c['work_id'] for c in candidates(manager, encoder)} == {'A','B','C'}


def test_update_replaces_only_one_identity_and_content(setup):
    manager, books, encoder = setup
    old = manager.snapshot.base.reconstruct(0).copy()
    books.rows['A']['description'] = 'Entirely different semantic content'
    manager.update_book('A')
    drain(manager)
    assert len(encoder.texts) == 1
    label = manager.snapshot.overrides['A']['label']
    assert not np.allclose(old, manager.snapshot.delta.reconstruct(label))
    assert [c['work_id'] for c in candidates(manager, encoder)].count('A') == 1
    np.testing.assert_array_equal(manager.snapshot.base.reconstruct(0), old)


def test_idempotent_add_update_delete(setup):
    manager, books, encoder = setup
    manager.add_book('A'); drain(manager)
    manager.add_book('A'); drain(manager)
    assert len(encoder.texts) == 1
    assert manager.snapshot.delta.ntotal == 1
    del books.rows['A']
    manager.delete_book('A'); drain(manager)
    manager.delete_book('A'); drain(manager)
    assert manager.snapshot.overrides['A']['label'] is None
    assert {c['work_id'] for c in candidates(manager, encoder)} == {'B'}


def test_current_mongo_filters_deleted_invalid_and_inactive(setup):
    manager, books, encoder = setup
    stale = candidates(manager, encoder)
    del books.rows['A']
    books.rows['B']['active'] = False
    assert current_books(books, [c['work_id'] for c in stale] + ['missing', '', None]) == {}
    books.fail = True
    with pytest.raises(RuntimeError):
        current_books(books, ['A'])


def test_metadata_immediate_without_sync(setup):
    _, books, _ = setup
    books.rows['A'].update(title='Current title', description='Current description', authors=None, average_rating=0)
    result = current_books(books, ['A'])['A']
    assert result['title'] == 'Current title'
    assert result['authors'] is None and result['average_rating'] == 0


def test_rapid_create_update_delete_final_state(setup):
    manager, books, encoder = setup
    books.rows['C'] = book('C'); manager.add_book('C')
    books.rows['C']['title'] = 'Changed'; manager.update_book('C')
    del books.rows['C']; manager.delete_book('C')
    drain(manager)
    assert encoder.texts == []
    assert {c['work_id'] for c in candidates(manager, encoder)} == {'A', 'B'}


def test_new_event_during_sync_not_lost(setup):
    manager, books, encoder = setup
    def during_encode():
        del books.rows['B']
        manager.delete_book('B')
    encoder.callback = during_encode
    manager.update_book('A')
    drain(manager)
    assert manager.status()['pending']
    # Even the old base candidate is filtered immediately, before the next sync.
    assert 'B' not in current_books(books, ['A', 'B'])
    drain(manager)
    assert not manager.status()['pending']
    assert manager.snapshot.overrides['B']['label'] is None


def test_concurrent_writer_process_lock_and_reload(setup):
    manager, books, encoder = setup
    other = IndexManager(manager.root, books, Encoder(), dimension=DIM, model_version='test-v1')
    manager.update_book('A')
    with writer_lock(manager.root) as acquired:
        assert acquired
        assert not other.process_once()
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda m: m.process_once(), [manager, other]))
    manager.refresh(); other.refresh()
    assert manager.snapshot.manifest['version'] == other.snapshot.manifest['version']
    assert manager.snapshot.delta.ntotal == 1


def test_failed_sync_retains_snapshot_and_retries(setup):
    manager, books, encoder = setup
    old = manager.snapshot
    books.rows['A']['title'] = 'New title'
    encoder.fail = True
    manager.update_book('A')
    assert not manager.process_once()
    assert manager.snapshot is old
    assert manager.status()['index_status'] == 'STALE'
    assert manager.status()['retry_attempts'] == 1
    assert not manager.process_once()  # backoff
    assert books.rows['A']['title'] == 'New title'
    encoder.fail = False
    drain(manager)
    assert manager.snapshot is not old


def test_repeated_failures_increase_retry_backoff(setup, monkeypatch):
    import time
    manager, _, encoder = setup
    encoder.fail = True
    manager.update_book('A')
    now = time.time()
    monkeypatch.setattr(time, 'time', lambda: now)
    assert not manager.process_once()
    assert manager.status()['retry_at'] == now + 2
    monkeypatch.setattr(time, 'time', lambda: now + 3)
    assert not manager.process_once()
    assert manager.status()['retry_attempts'] == 2
    assert manager.status()['retry_at'] == now + 7


def test_corrupt_temporary_snapshot_never_activates(setup, monkeypatch):
    manager, _, _ = setup
    old = manager.snapshot
    write = faiss.write_index
    def corrupt(index, path):
        write(index, path)
        Path(path).write_bytes(b'broken')
    monkeypatch.setattr(faiss, 'write_index', corrupt)
    manager.update_book('A')
    assert not manager.process_once()
    assert manager.snapshot is old
    assert not (manager.root/'active_index.json').exists()


def test_manifest_mapping_mismatch_rejected_and_previous_recovered(setup):
    manager, books, encoder = setup
    manager.update_book('A'); drain(manager)
    previous = manager.snapshot.manifest['version']
    books.rows['A']['title'] = 'Updated again'
    manager.update_book('A'); drain(manager)
    active = manager.snapshot.manifest['version']
    path = manager.root/'versions'/active/'delta.json'
    path.write_text('{"ids": []}')
    with pytest.raises(ValueError):
        manager.load_snapshot(active)
    recovered = IndexManager(manager.root, books, encoder, dimension=DIM, model_version='test-v1')
    assert recovered.snapshot.manifest['version'] == previous
    assert recovered.status()['pending']
    drain(recovered)
    assert recovered.snapshot.manifest['version'] != previous


def test_full_rebuild_current_records_and_cached_vectors(setup):
    manager, books, encoder = setup
    manager.batch_sync(['A', 'B']); drain(manager)
    encoder.texts.clear()
    del books.rows['B']
    books.rows['C'] = book('C')
    manager.rebuild_full_index(); drain(manager)
    assert encoder.texts == [semantic_text(books.rows['C'])]
    assert set(manager.snapshot.work_ids) == {'A','C'}
    assert manager.snapshot.delta.ntotal == 0
    assert manager.status()['index_status'] == 'HEALTHY'
    assert manager.status()['deleted_vectors'] == 0
    encoder.texts.clear()
    manager.rebuild_full_index(); drain(manager)
    assert encoder.texts == []


def test_changed_hash_invalidates_cache(setup):
    manager, books, encoder = setup
    manager.update_book('A'); drain(manager)
    encoder.texts.clear()
    books.rows['A']['description'] = 'changed description'
    manager.update_book('A'); drain(manager)
    assert encoder.texts == [semantic_text(books.rows['A'])]


def test_model_version_invalidates_cache(setup):
    manager, books, encoder = setup
    manager.update_book('A'); drain(manager)
    manager.cache.model_version = 'different-model-version'
    encoder.texts.clear()
    manager._embeddings([books.rows['A']])
    assert len(encoder.texts) == 1


def test_failed_full_rebuild_preserves_previous(setup):
    manager, books, encoder = setup
    old = manager.snapshot
    encoder.fail = True
    manager.rebuild_full_index()
    assert not manager.process_once()
    assert manager.snapshot is old


def test_full_build_mutation_replayed(setup):
    manager, books, encoder = setup
    def during():
        del books.rows['B']
        manager.delete_book('B')
    encoder.callback = during
    manager.rebuild_full_index(); drain(manager)
    assert manager.status()['pending']
    drain(manager)
    assert 'B' not in {c['work_id'] for c in candidates(manager, encoder)}


def test_low_quality_explicit_create_survives_multiple_rebuilds(setup):
    manager, books, encoder = setup
    books.rows['C'] = {'work_id':'C','title':'Only a title'}
    manager.add_book('C'); drain(manager)
    for _ in range(2):
        manager.rebuild_full_index(); drain(manager)
        assert 'C' in set(manager.snapshot.work_ids)


def test_batch_sync_one_snapshot_many_embeddings(setup, monkeypatch):
    manager, books, encoder = setup
    ids = [str(i) for i in range(100)]
    books.rows.update((wid, book(wid)) for wid in ids)
    persist = MagicMock(wraps=manager._persist)
    monkeypatch.setattr(manager, '_persist', persist)
    manager.batch_sync(ids); drain(manager)
    assert len(encoder.texts) == 100
    assert persist.call_count == 1
    assert manager.snapshot.delta.ntotal == 100


def test_import_one_event_and_partial_success(monkeypatch):
    from search import sync_queue
    from pymongo.errors import BulkWriteError
    request = MagicMock()
    monkeypatch.setattr(sync_queue, 'request_catalogue_sync', request)
    batch = CatalogueImportSync()
    collection = MagicMock()
    batch.insert(collection, [book('A'),book('B')])
    collection.insert_many.side_effect = BulkWriteError({'nInserted':1, 'writeErrors':[{'index':1}]})
    with pytest.raises(BulkWriteError):
        batch.insert(collection, [book('C'),book('D')])
    batch.finish()
    request.assert_called_once_with(['A','B','C'])


@pytest.fixture
def book_service(monkeypatch):
    # Import without backend.database.mongodb's production create_index side effect.
    fake = types.ModuleType('backend.database.mongodb')
    for name in ['books','issues','library_inventory','book_categories']:
        setattr(fake, name+'_collection', MagicMock())
    fake.issues_collection.find_one.return_value = None
    fake.library_inventory_collection.find_one.return_value = None
    monkeypatch.setitem(sys.modules, 'backend.database.mongodb', fake)
    # The service's availability helper has no DB import.
    sys.modules.pop('backend.services.book_service', None)
    from backend.services import book_service as service
    monkeypatch.setattr(service, 'books_collection', fake.books_collection)
    monkeypatch.setattr(service, 'issues_collection', fake.issues_collection)
    monkeypatch.setattr(service, 'library_inventory_collection', fake.library_inventory_collection)
    sync = MagicMock()
    from search import sync_queue
    monkeypatch.setattr(sync_queue, 'request_catalogue_sync', sync)
    monkeypatch.setattr(service, 'get_book_by_work_id', lambda wid: book(wid))
    return service, fake.books_collection, sync


def test_nonsemantic_and_noop_updates_do_not_sync(book_service):
    service, collection, sync = book_service
    collection.find_one.return_value = book('A')
    collection.find_one_and_update.return_value = book('A')
    service.update_book('A', {'available_copies': 0})
    service.update_book('A', {'title':'Title A'})
    sync.assert_not_called()


def test_semantic_update_hook_only_after_success(book_service):
    service, collection, sync = book_service
    collection.find_one.return_value = book('A')
    collection.find_one_and_update.side_effect = RuntimeError('failed Mongo write')
    with pytest.raises(RuntimeError):
        service.update_book('A', {'description':'changed'})
    sync.assert_not_called()
    collection.find_one_and_update.side_effect = None
    collection.find_one_and_update.return_value = book('A')
    service.update_book('A', {'description':'changed'})
    sync.assert_called_once_with(['A'])


def test_concurrent_update_uses_atomic_preimage(book_service):
    service, collection, sync = book_service
    collection.find_one.return_value = book('A')
    actual_before = book('A')
    actual_before['title'] = 'Concurrent edit after validation read'
    collection.find_one_and_update.return_value = actual_before
    service.update_book('A', {'title':'Title A'})
    sync.assert_called_once_with(['A'])


def test_create_delete_hooks_and_failed_mongo(book_service):
    service, collection, sync = book_service
    collection.find_one.return_value = None
    collection.insert_one.side_effect = RuntimeError('failed')
    with pytest.raises(RuntimeError):
        service.create_book(book('C'))
    sync.assert_not_called()
    collection.insert_one.side_effect = None
    service.create_book(book('C'))
    sync.assert_called_once_with(['C'])
    sync.reset_mock()
    collection.delete_one.return_value.deleted_count = 0
    assert service.delete_book('C') is None
    sync.assert_not_called()
    collection.delete_one.return_value.deleted_count = 1
    assert service.delete_book('C') is True
    sync.assert_called_once_with(['C'])


def test_engine_search_validates_and_overfetches(tmp_path):
    from search.luminar_search import LuminaRSearchEngine
    encoder = Encoder()
    rows = [book(str(i)) for i in range(100)]
    legacy(tmp_path, rows, encoder)
    books = Books(rows)
    manager = IndexManager(tmp_path, books, encoder, dimension=DIM, model_version='test-v1')
    first = manager.snapshot.candidates(encoder.encode(['query']), 50)
    for candidate in first:
        del books.rows[candidate['work_id']]
    engine = LuminaRSearchEngine.__new__(LuminaRSearchEngine)
    engine.device = 'cpu'
    engine.index_manager = manager
    engine.books_collection = books
    engine.library_inventory = Books([])
    engine.reranker = types.SimpleNamespace(predict=lambda pairs, **kw: np.ones(len(pairs)))
    result = engine.search('query', top_k=10)
    assert len(result['results']) == 10
    assert all(row['work_id'] in books.rows for row in result['results'])
    wid = result['results'][0]['work_id']
    books.rows[wid]['title'] = 'Current Mongo title'
    assert next(row for row in engine.search('query')['results'] if row['work_id']==wid)['title'] == 'Current Mongo title'
    books.rows.clear()
    assert engine.search('query')['results'] == []


def test_snapshot_reader_stable_during_swap(setup):
    manager, books, encoder = setup
    old = manager.snapshot
    books.rows['C'] = book('C')
    manager.add_book('C'); drain(manager)
    vector = encoder.encode(['query'])
    assert 'C' not in {row['work_id'] for row in old.candidates(vector, 50)}
    assert 'C' in {row['work_id'] for row in manager.snapshot.candidates(vector, 50)}


def test_corrupt_legacy_count_refuses_startup(setup):
    manager, books, encoder = setup
    np.save(manager.root/'index_work_ids.npy', np.array(['A']))
    with pytest.raises(ValueError):
        IndexManager(manager.root, books, encoder, dimension=DIM, model_version='test-v1')


def test_worker_reloads_without_restart(setup):
    import time
    manager, books, encoder = setup
    other = IndexManager(manager.root, books, Encoder(), dimension=DIM, model_version='test-v1', poll_seconds=.05)
    other.start()
    try:
        books.rows['C'] = book('C')
        seq = manager.add_book('C')
        deadline = time.monotonic() + 5
        while other.snapshot.manifest['semantic_generation'] < seq and time.monotonic() < deadline:
            time.sleep(.02)
        assert other.snapshot.manifest['semantic_generation'] == seq
    finally:
        other.close()


def test_single_writer_lock_across_processes(setup):
    import subprocess
    manager, _, _ = setup
    code = "from search.index_manager import writer_lock; import sys\nwith writer_lock(sys.argv[1]) as acquired: print(acquired)"
    with writer_lock(manager.root):
        result = subprocess.run([sys.executable,'-c',code,str(manager.root)], capture_output=True, text=True, check=True)
        assert result.stdout.strip() == 'False'
    result = subprocess.run([sys.executable,'-c',code,str(manager.root)], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == 'True'


def test_search_keeps_old_snapshot_during_blocked_build(setup):
    manager, books, encoder = setup
    entered, release = threading.Event(), threading.Event()
    def block():
        entered.set()
        assert release.wait(5)
    encoder.callback = block
    books.rows['C'] = book('C')
    manager.add_book('C')
    old = manager.snapshot
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(manager.process_once)
        assert entered.wait(5)
        del books.rows['B']
        manager.delete_book('B')
        assert manager.snapshot is old
        query = np.ones((1,DIM),dtype=np.float32)
        assert 'B' not in current_books(books, [c['work_id'] for c in old.candidates(query, 50)])
        release.set()
        assert future.result()
    drain(manager)
    assert manager.snapshot.overrides['B']['label'] is None


def test_full_rebuild_memory_guard_preserves_index(setup, monkeypatch):
    import search.index_manager as module
    manager, _, _ = setup
    old = manager.snapshot
    monkeypatch.setattr(module, 'available_memory', lambda: 0)
    manager.rebuild_full_index()
    assert not manager.process_once()
    assert manager.snapshot is old


def test_manual_recovery_when_all_graphs_corrupt(setup):
    manager, books, encoder = setup
    (manager.root/'hnsw.index').write_bytes(b'corrupt')
    recovery = IndexManager(manager.root, books, encoder, dimension=DIM, model_version='test-v1', recover=True)
    drain(recovery)
    assert set(recovery.snapshot.work_ids) == {'A','B'}


def test_queue_fallback_durable_retry(setup, monkeypatch):
    from search import sync_queue
    manager, _, _ = setup
    monkeypatch.setenv('LUMINAR_SEARCH_INDEX_DIR', str(manager.root))
    original = sync_queue.SyncQueue.request
    monkeypatch.setattr(sync_queue.SyncQueue, 'request', MagicMock(side_effect=OSError('queue locked')))
    assert sync_queue.request_catalogue_sync(['A']) == 'spooled'
    monkeypatch.setattr(sync_queue.SyncQueue, 'request', original)
    drain(manager)
    assert manager.snapshot.delta.ntotal == 1
    assert not list((manager.root/'pending_requests').glob('*.json'))


def test_inventory_import_confirmation_does_not_sync(monkeypatch):
    # This import edits physical copies only, not the searchable corpus.
    fake = types.ModuleType('backend.database.mongodb')
    for name in ['books','library_inventory','inventory_preview']:
        setattr(fake, name+'_collection', MagicMock())
    monkeypatch.setitem(sys.modules, 'backend.database.mongodb', fake)
    import importlib
    service = importlib.import_module('backend.services.inventory_import_service')
    monkeypatch.setattr(service, 'inventory_preview_collection', fake.inventory_preview_collection)
    monkeypatch.setattr(service, 'library_inventory_collection', fake.library_inventory_collection)
    fake.inventory_preview_collection.find_one.return_value = {'status':'PREVIEW','rows':[
        {'status':'MATCHED','work_id':'A','total_copies':2,'available_copies':2}]}
    fake.library_inventory_collection.find_one.return_value = None
    from search import sync_queue
    sync = MagicMock()
    monkeypatch.setattr(sync_queue, 'request_catalogue_sync', sync)
    result = service.confirm_inventory_import('preview','LIB001')
    assert result['imported'] == 1
    sync.assert_not_called()


def test_legacy_embedding_seed_verifies_ids_and_exact_text(setup, tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from search.embedding_cache import EmbeddingCache
    manager, books, encoder = setup
    legacy_dir = tmp_path/'legacy_embeddings'
    (legacy_dir/'vectors').mkdir(parents=True)
    rows = list(books.rows.values())
    texts = [semantic_text(row) for row in rows]
    ids = [row['work_id'] for row in rows]
    vectors = encoder.encode(texts)
    np.save(legacy_dir/'vectors/embeddings.npy', vectors)
    np.save(legacy_dir/'vectors/work_ids.npy', np.array(ids))
    (legacy_dir/'vectors/checkpoint.json').write_text(json.dumps({'model':'all-MiniLM-L6-v2','embedding_dimension':DIM}))
    pq.write_table(pa.table({'work_id':ids,'search_text':texts}), legacy_dir/'embedding_corpus.parquet')
    cache = EmbeddingCache(manager.root, 'legacy-test-v1', DIM, legacy_dir)
    cache.seed_legacy(manager.encode)
    from search.catalogue import content_hash
    cached = cache.get_many([(ids[0],content_hash(texts[0]))])
    np.testing.assert_allclose(cached[ids[0]], vectors[0])
    assert cache.get_many([(ids[0],content_hash('changed text'))]) == {}
    # Mismatched label mapping must not be imported for another model/cache key.
    np.save(legacy_dir/'vectors/work_ids.npy', np.array(ids[::-1]))
    other = EmbeddingCache(manager.root, 'legacy-test-v2', DIM, legacy_dir)
    with pytest.raises(ValueError, match='alignment'):
        other.seed_legacy(manager.encode)


def test_crash_after_pointer_before_status_recovers(setup):
    manager, books, encoder = setup
    manager.rebuild_full_index(); drain(manager)
    manager.queue.state('SYNCING')
    restarted = IndexManager(manager.root, books, encoder, dimension=DIM, model_version='test-v1')
    assert not restarted.process_once()
    assert restarted.status()['index_status'] == 'HEALTHY'


def test_core_crash_before_event_publication_recovers_intent(setup, monkeypatch):
    import subprocess
    manager, books, encoder = setup
    monkeypatch.setenv('LUMINAR_SEARCH_INDEX_DIR', str(manager.root))
    code = "from search.sync_queue import MutationJournal; import os\nj=MutationJournal(); j.add(['C']); os._exit(0)"
    subprocess.run([sys.executable,'-c',code], check=True)
    # Simulate the Mongo insert committed before that Core process died.
    books.rows['C'] = book('C')
    assert manager.queue.latest() == 0
    drain(manager)
    assert manager.snapshot.overrides['C']['label'] == 0
    assert not list((manager.root/'mutation_intents').glob('*.jsonl'))


def test_worker_cannot_consume_inflight_mongo_intent(setup, monkeypatch):
    from search.sync_queue import catalogue_mutation
    manager, books, encoder = setup
    monkeypatch.setenv('LUMINAR_SEARCH_INDEX_DIR', str(manager.root))
    with catalogue_mutation(['C']) as committed:
        assert not manager.process_once()
        books.rows['C'] = book('C')
        assert not manager.process_once()
        committed.append('C')
    drain(manager)
    assert len(encoder.texts) == 1


def test_definite_mongo_failure_discards_intent(setup, monkeypatch):
    from search.sync_queue import catalogue_mutation
    manager, _, encoder = setup
    monkeypatch.setenv('LUMINAR_SEARCH_INDEX_DIR', str(manager.root))
    with pytest.raises(RuntimeError):
        with catalogue_mutation(['C']):
            raise RuntimeError('definite Mongo failure')
    assert not manager.process_once()
    assert manager.queue.latest() == 0
    assert encoder.texts == []


def test_success_with_queue_unavailable_recovers_intent(setup, monkeypatch):
    from search import sync_queue
    manager, books, encoder = setup
    monkeypatch.setenv('LUMINAR_SEARCH_INDEX_DIR', str(manager.root))
    request = MagicMock(return_value=None)
    monkeypatch.setattr(sync_queue, 'request_catalogue_sync', request)
    with sync_queue.catalogue_mutation(['C']) as committed:
        books.rows['C'] = book('C')
        committed.append('C')
    assert manager.queue.latest() == 0
    drain(manager)
    assert manager.snapshot.overrides['C']['label'] == 0
