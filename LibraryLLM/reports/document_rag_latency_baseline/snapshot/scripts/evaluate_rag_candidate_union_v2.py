"""Candidate availability for unchanged MiniLM on shortlisted chunk variants.

Requires PYTHONHASHSEED set before Python starts because the current generic
query expander iterates synonym sets when constructing expansion strings.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time

import faiss
import numpy as np
import pyarrow.parquet as pq
import torch
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rag.evidence import generate_expanded_queries
from rag.evaluation.metrics import evaluate_query, overlaps

BASE = ROOT / 'datasets' / 'rag_experiments' / 'chunking_v1'
LABELS = ROOT / 'rag' / 'evaluation' / 'rag_retrieval_eval_v1.json'
MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'
VARIANTS = ('tokens_220', 'tokens_240')


def full_pool(query, ids, chunks):
    spans = [p for p in query['accepted_passages'] if p['relevance_grade'] == 2]
    if not spans:
        return None
    found = {i for cid in ids for i, p in enumerate(spans)
             if cid in chunks and overlaps(chunks[cid], p)}
    return {'hit': int(bool(found)), 'recall': len(found) / len(spans)}


def union(dense, expanded, *, preserve, cap):
    if preserve > cap:
        raise ValueError('Preserve depth exceeds cap')
    result = list(dict.fromkeys(dense[:preserve] + expanded))[:cap]
    guaranteed = min(preserve, len(dense))
    if result[:guaranteed] != dense[:guaranteed]:
        raise AssertionError('Dense prefix was not preserved')
    return result


def pool_summary(records, name):
    valid = [r for r in records if r['pools'][name]['full'] is not None]
    depths = (5, 10, 20, 40, 50)
    return {
        'evaluable': len(valid),
        'mean_candidate_count': statistics.mean(r['pools'][name]['count'] for r in valid),
        'hit': {str(k): statistics.mean(r['pools'][name]['metrics']['hit'][str(k)]
                                        for r in valid) for k in depths},
        'recall': {str(k): statistics.mean(r['pools'][name]['metrics']['recall'][str(k)]
                                           for r in valid) for k in depths},
        'full_pool_hit': statistics.mean(r['pools'][name]['full']['hit'] for r in valid),
        'full_pool_recall': statistics.mean(r['pools'][name]['full']['recall'] for r in valid),
    }


def evaluate(variant, model, queries, hash_seed):
    folder = BASE / variant
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['evaluation_labels_sha256'] != hashlib.sha256(LABELS.read_bytes()).hexdigest():
        raise ValueError('Labels changed since index build')
    rows = pq.read_table(folder / 'chunks.parquet', columns=[
        'chunk_id', 'work_id', 'source_start_char', 'source_end_char']).to_pylist()
    by_book = {}
    for row in rows:
        by_book.setdefault(row['work_id'], []).append(row)
    indexes = {wid: faiss.read_index(str(folder / 'books' / f'{wid}.index'))
               for wid in {q['work_id'] for q in queries}}
    baseline_rows = {r['query_id']: r for r in json.loads((folder / 'dense_evaluation.json').read_text(
        encoding='utf-8'))['queries']}
    records = []
    for number, q in enumerate(queries, 1):
        index = indexes[q['work_id']]
        book_rows = by_book[q['work_id']]
        chunks = {r['chunk_id']: {'start': r['source_start_char'],
                                  'end': r['source_end_char']} for r in book_rows}

        def search(text, limit):
            vector = np.asarray(model.encode([text], convert_to_numpy=True,
                                             normalize_embeddings=True), dtype='float32')
            _, positions = index.search(vector, limit)
            return [book_rows[p]['chunk_id'] for p in positions[0] if p >= 0]

        started = time.perf_counter()
        dense = search(q['question'], 50)
        dense_at = time.perf_counter()
        if dense != [x['chunk_id'] for x in baseline_rows[q['query_id']]['top50']]:
            raise RuntimeError(f'Original dense order diverged: {variant} {q["query_id"]}')
        expanded = []
        expansion_strings = generate_expanded_queries(q['question'])
        for text in expansion_strings:
            for cid in search(text, 15):
                if cid not in expanded:
                    expanded.append(cid)
        expanded = expanded[:40]
        expanded_at = time.perf_counter()
        pools = {
            'raw_dense': dense,
            'current_expansion': expanded,
            'union_30_50': union(dense, expanded, preserve=30, cap=50),
            'union_40_60': union(dense, expanded, preserve=40, cap=60),
            'union_50_80': union(dense, expanded, preserve=50, cap=80),
        }
        formed_at = time.perf_counter()
        scored = {name: {'count': len(ids), 'ids': ids,
                         'metrics': evaluate_query(q, ids, chunks),
                         'full': full_pool(q, ids, chunks)}
                  for name, ids in pools.items()}
        records.append({'query_id': q['query_id'], 'work_id': q['work_id'],
                        'split': q['split'], 'expanded_queries': expansion_strings,
                        'dense_retrieval_ms': round((dense_at-started)*1000, 3),
                        'expansion_ms': round((expanded_at-dense_at)*1000, 3),
                        'union_ms': round((formed_at-expanded_at)*1000, 3),
                        'pools': scored})
        if number % 10 == 0 or number == len(queries):
            print(f'{variant} candidate pools {number}/{len(queries)}', flush=True)
    summary = {
        'result_label': 'EXPLORATORY_ONLY_DRAFT_EVALUATION_LABELS',
        'variant': variant, 'python_hash_seed': hash_seed,
        'pools': {name: pool_summary(records, name) for name in pools},
        'latency': {
            key: {'mean_ms': statistics.mean(r[key] for r in records),
                  'median_ms': statistics.median(r[key] for r in records),
                  'p95_ms': float(np.percentile([r[key] for r in records], 95))}
            for key in ('dense_retrieval_ms', 'expansion_ms', 'union_ms')},
        'reranker_used': False,
    }
    (folder / 'candidate_pool_evaluation.json').write_text(json.dumps(
        {'summary': summary, 'queries': records}, indent=2), encoding='utf-8')
    print(variant, {name: round(p['full_pool_hit'], 3)
                    for name, p in summary['pools'].items()}, flush=True)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--variant', choices=VARIANTS)
    args = parser.parse_args()
    hash_seed = os.environ.get('PYTHONHASHSEED')
    if hash_seed is None:
        raise RuntimeError('Set PYTHONHASHSEED before process start')
    names = (args.variant,) if args.variant else VARIANTS
    labels = json.loads(LABELS.read_text(encoding='utf-8'))['questions']
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = SentenceTransformer(MODEL_NAME, device=device, local_files_only=True)
    model.encode(['warm up'], convert_to_numpy=True, normalize_embeddings=True)
    for name in names:
        evaluate(name, model, labels, hash_seed)
