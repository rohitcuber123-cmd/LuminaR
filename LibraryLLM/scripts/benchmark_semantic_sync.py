"""Offline-model benchmark. Writes only temporary indices; Mongo probe is read-only."""
import argparse
import json
import os
from pathlib import Path
import statistics
import tempfile
import time

import faiss
import numpy as np

from search.catalogue import current_books, semantic_text
from search.index_manager import IndexManager, new_index


class MemoryBooks:
    def __init__(self, rows):
        self.rows = {row['work_id']: row for row in rows}

    def find(self, query, projection=None):
        ids = query.get('work_id', {}).get('$in', self.rows)
        return [dict(self.rows[wid]) for wid in ids if wid in self.rows]


def elapsed(fn):
    start = time.perf_counter()
    result = fn()
    return (time.perf_counter() - start) * 1000, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--records', type=int, default=500)
    parser.add_argument('--mongo-read-only', action='store_true')
    parser.add_argument('--baseline-engine', type=Path, help='Optional saved pre-change luminar_search.py for an isolated end-to-end comparison')
    parser.add_argument('--output', type=Path, default=Path('reports/semantic_sync_benchmark.json'))
    args = parser.parse_args()
    from sentence_transformers import SentenceTransformer
    import torch
    model = SentenceTransformer('all-MiniLM-L6-v2', device='cuda' if torch.cuda.is_available() else 'cpu', local_files_only=True)
    model.max_seq_length = 256
    faiss.omp_set_num_threads(4)
    rows = [dict(work_id=f'BENCH{i}', title=f'Catalogue benchmark {i}', authors='Benchmark author',
                 subjects=f'Subject {i%10}', description=('A synthetic book about science, mathematics and library research. ' * 8))
            for i in range(args.records)]
    books = MemoryBooks(rows)
    texts = [semantic_text(row) for row in rows]
    model.encode(texts[:8], normalize_embeddings=True)
    embedding_ms, vectors = elapsed(lambda: model.encode(texts, batch_size=64, normalize_embeddings=True,
                                                        convert_to_numpy=True, show_progress_bar=False))
    output = dict(records=args.records, device=str(model.device), embedding_ms=embedding_ms,
                  embedding_texts_per_second=args.records/(embedding_ms/1000), faiss_threads=4,
                  note='Synthetic temporary corpus. Not a 5-million-book rebuild estimate.')
    with tempfile.TemporaryDirectory(prefix='luminar-semantic-benchmark-') as temp:
        root = Path(temp)
        base = new_index()
        output['base_graph_build_ms'], _ = elapsed(lambda: base.add(vectors))
        faiss.write_index(base, str(root/'hnsw.index'))
        np.save(root/'index_work_ids.npy', np.array([row['work_id'] for row in rows]))
        (root/'hnsw_metadata.json').write_text(json.dumps(dict(model_name='all-MiniLM-L6-v2',
            dimension=384, normalized=True, metric='inner_product', vector_count=len(rows))))
        manager = IndexManager(root, books, model)
        def sync(ids):
            manager.batch_sync(ids)
            if not manager.process_once():
                raise RuntimeError('Benchmark sync failed')
        for label, action in [('add', None), ('update', None), ('delete', None)]:
            samples = []
            for i in range(5):
                wid = f'NEW{i}'
                if label == 'add':
                    books.rows[wid] = dict(rows[i], work_id=wid)
                elif label == 'update':
                    books.rows[wid]['description'] = 'Changed semantic description about ancient history and archaeology.'
                else:
                    del books.rows[wid]
                ms, _ = elapsed(lambda: sync([wid]))
                samples.append(ms)
            output[label+'_ms'] = dict(median=statistics.median(samples), samples=samples)
        batch = [dict(rows[i%len(rows)], work_id=f'BATCH{i}') for i in range(100)]
        books.rows.update((row['work_id'],row) for row in batch)
        output['batch_100_ms'], _ = elapsed(lambda: sync([row['work_id'] for row in batch]))
        manager.rebuild_full_index()
        output['full_cold_cache_ms'], ok = elapsed(manager.process_once)
        assert ok
        manager.rebuild_full_index()
        output['full_warm_cache_ms'], ok = elapsed(manager.process_once)
        assert ok
        vector = manager.encode(['science books'])
        output['base_hnsw_search_ms'] = statistics.median(elapsed(lambda: base.search(vector, 50))[0] for _ in range(30))
        output['snapshot_retrieval_ms'] = statistics.median(elapsed(lambda: manager.snapshot.candidates(vector, 50))[0] for _ in range(30))
        output['memory_mongo_substitute_validation_ms'] = statistics.median(elapsed(lambda: current_books(books, list(books.rows)[:50]))[0] for _ in range(30))
        if args.baseline_engine:
            import importlib.util
            import types
            from sentence_transformers import CrossEncoder
            from search.luminar_search import LuminaRSearchEngine
            spec = importlib.util.spec_from_file_location('baseline_search', args.baseline_engine)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', device=str(model.device), local_files_only=True)
            old = module.LuminaRSearchEngine.__new__(module.LuminaRSearchEngine)
            old.index = base
            old.work_ids = np.array([row['work_id'] for row in rows])
            old.embedding_model = model
            old.metadata_store = types.SimpleNamespace(
                get_by_work_ids=lambda ids: current_books(books, ids),
                get_rerank_text_by_work_ids=lambda ids: current_books(books, ids))
            new = LuminaRSearchEngine.__new__(LuminaRSearchEngine)
            new.index_manager = manager
            for engine in (old, new):
                engine.device = str(model.device).split(':')[0]
                engine.books_collection = books
                engine.library_inventory = MemoryBooks([])
                engine.reranker = reranker
                engine.search('science books')
            output['isolated_old_pipeline_ms'] = statistics.median(elapsed(lambda: old.search('science books'))[0] for _ in range(10))
            output['isolated_new_pipeline_ms'] = statistics.median(elapsed(lambda: new.search('science books'))[0] for _ in range(10))
            output['pipeline_comparison_note'] = 'Actual old/new engine methods and real local models; temporary ~500/600-vector graphs, in-memory metadata substitutes.'
    if args.mongo_read_only:
        from dotenv import load_dotenv
        from pymongo import MongoClient
        import duckdb
        load_dotenv()
        client = MongoClient(os.getenv('MONGO_URI'), serverSelectionTimeoutMS=3000)
        collection = client[os.getenv('MONGO_DB_NAME', 'luminar_library')].books
        ids = [row['work_id'] for row in collection.find({}, {'work_id':1,'_id':0}).limit(50)]
        current_books(collection, ids)
        output['real_mongo_validation_50_ms'] = statistics.median(elapsed(lambda: current_books(collection, ids))[0] for _ in range(30))
        path = Path(__file__).resolve().parents[1]/'datasets/ai/metadata/book_metadata.duckdb'
        with duckdb.connect(str(path), read_only=True) as db:
            query = 'SELECT work_id,title,authors,subjects FROM books WHERE work_id IN (' + ','.join('?' for _ in ids) + ')'
            db.execute(query, ids).fetchall()
            output['old_duckdb_metadata_50_ms'] = statistics.median(elapsed(lambda: db.execute(query, ids).fetchall())[0] for _ in range(30))
        # Read only a bounded sample to quantify legacy publication-field mismatch.
        import pyarrow.parquet as pq
        corpus = pq.ParquetFile(Path(__file__).resolve().parents[1]/'datasets/ai/embeddings/embedding_corpus.parquet')
        sample = next(corpus.iter_batches(batch_size=500, columns=['work_id','search_text'])).to_pydict()
        current = current_books(collection, sample['work_id'])
        output['legacy_sample_count'] = len(sample['work_id'])
        output['legacy_exact_text_reusable'] = sum(wid in current and semantic_text(current[wid]) == text
            for wid,text in zip(sample['work_id'],sample['search_text']))
        legacy_vectors = np.load(Path(__file__).resolve().parents[1]/'datasets/ai/embeddings/vectors/embeddings.npy', mmap_mode='r')
        checked = model.encode(sample['search_text'][:8], normalize_embeddings=True, convert_to_numpy=True)
        output['legacy_model_sample_max_absolute_error'] = float(np.max(np.abs(checked - legacy_vectors[:8])))
        output['mongo_estimated_count'] = collection.estimated_document_count()
        base_ids = np.load(Path(__file__).resolve().parents[1]/'datasets/ai/faiss/hnsw/index_work_ids.npy', allow_pickle=True)
        output['legacy_mapping_count'] = len(base_ids)
        output['five_million_base_membership_ms'] = statistics.median(
            elapsed(lambda: np.isin(base_ids, ids[:1]))[0] for _ in range(10))
        client.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
