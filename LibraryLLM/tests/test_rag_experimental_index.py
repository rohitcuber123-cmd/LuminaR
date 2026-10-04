"""Isolated FAISS indexes and production-file guardrails."""
import hashlib
import json
from pathlib import Path

import faiss
import numpy as np
import pyarrow.parquet as pq

from scripts.evaluate_rag_candidate_union_v2 import union

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'datasets' / 'rag_experiments' / 'chunking_v1'


def test_index_shape_normalization_and_book_mapping():
    for variant in ('current_baseline', 'tokens_180', 'tokens_220', 'tokens_240'):
        folder = BASE / variant
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        rows = pq.read_table(folder / 'chunks.parquet', columns=[
            'chunk_id', 'work_id']).to_pylist()
        vectors = np.load(folder / 'embeddings.npy', mmap_mode='r')
        index = faiss.read_index(str(folder / 'faiss.index'))
        assert isinstance(index, faiss.IndexFlatIP)
        assert vectors.shape == (len(rows), 384)
        assert index.d == 384 and index.ntotal == len(rows)
        assert manifest['index_build']['index_ntotal'] == len(rows)
        sample = np.linspace(0, len(rows)-1, min(100, len(rows)), dtype=int)
        for position in sample:
            assert np.isclose(np.linalg.norm(vectors[position]), 1, atol=1e-4)
            assert np.allclose(index.reconstruct(int(position)), vectors[position], atol=1e-6)
        counts = {}
        for row in rows:
            counts[row['work_id']] = counts.get(row['work_id'], 0) + 1
        assert len(counts) == 18
        for work_id, count in counts.items():
            book_index = faiss.read_index(str(folder / 'books' / f'{work_id}.index'))
            assert isinstance(book_index, faiss.IndexFlatIP)
            assert book_index.d == 384 and book_index.ntotal == count


def test_production_and_evaluation_files_unchanged():
    snapshot = json.loads((BASE / 'reports' / 'production_before_sha256.json').read_text())
    assert snapshot
    for relative, before in snapshot.items():
        path = ROOT / relative
        assert path.exists(), relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before, relative


def test_visibility_and_union_guardrails():
    for variant in ('current_baseline', 'tokens_180', 'tokens_220', 'tokens_240'):
        folder = BASE / variant
        visibility = json.loads((folder / 'visibility.json').read_text())
        counts = visibility['summary']['counts']
        assert sum(counts.values()) == 55
        assert len(visibility['spans']) == 55
        assert all(x['status'] in counts for x in visibility['spans'])
    dense = [f'd{i}' for i in range(50)]
    expanded = ['x', 'd0', 'y'] + [f'e{i}' for i in range(70)]
    for preserve, cap in ((30, 50), (40, 60), (50, 80)):
        result = union(dense, expanded, preserve=preserve, cap=cap)
        assert result[:preserve] == dense[:preserve]
        assert len(result) == len(set(result)) == cap
    short = union(['a', 'b'], ['b', 'c'], preserve=30, cap=50)
    assert short == ['a', 'b', 'c']


def test_candidate_pool_results_preserve_promised_dense_prefix():
    configurations = {'union_30_50': (30, 50), 'union_40_60': (40, 60),
                      'union_50_80': (50, 80)}
    for variant in ('tokens_220', 'tokens_240'):
        data = json.loads((BASE / variant / 'candidate_pool_evaluation.json').read_text())
        assert data['summary']['result_label'] == 'EXPLORATORY_ONLY_DRAFT_EVALUATION_LABELS'
        assert data['summary']['python_hash_seed'] == '0'
        assert len(data['queries']) == 50
        for row in data['queries']:
            pools = row['pools']
            dense = pools['raw_dense']['ids']
            for name, (preserve, cap) in configurations.items():
                ids = pools[name]['ids']
                guaranteed = min(preserve, len(dense))
                assert ids[:guaranteed] == dense[:guaranteed]
                assert len(ids) == len(set(ids)) <= cap
