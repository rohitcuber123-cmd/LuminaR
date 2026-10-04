"""Raw dense, book-scoped evaluation of isolated unchanged-MiniLM indexes."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

import faiss
import numpy as np
import psutil
import pyarrow.parquet as pq
import torch
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rag.evaluation.metrics import aggregate, evaluate_query

BASE = ROOT / 'datasets' / 'rag_experiments' / 'chunking_v1'
LABELS = ROOT / 'rag' / 'evaluation' / 'rag_retrieval_eval_v1.json'
MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'
VARIANTS = ('current_baseline', 'tokens_180', 'tokens_220', 'tokens_240')


def timing(values):
    return {'mean_ms': statistics.mean(values), 'median_ms': statistics.median(values),
            'p95_ms': float(np.percentile(values, 95))}


def evaluate_variant(variant, model, queries, *, index_folder=None, output_file=None):
    folder = BASE / variant
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['evaluation_labels_sha256'] != hashlib.sha256(LABELS.read_bytes()).hexdigest():
        raise ValueError('Labels changed since index build')
    if 'index_build' not in manifest:
        raise ValueError(f'Index missing: {variant}')
    rows = pq.read_table(folder / 'chunks.parquet', columns=[
        'chunk_id', 'work_id', 'source_start_char', 'source_end_char']).to_pylist()
    by_book = {}
    for row in rows:
        by_book.setdefault(row['work_id'], []).append(row)
    work_ids = {q['work_id'] for q in queries}
    index_root = index_folder or folder
    indexes = {wid: faiss.read_index(str(index_root / 'books' / f'{wid}.index'))
               for wid in work_ids}
    for wid, index in indexes.items():
        if index.d != 384 or index.ntotal != len(by_book[wid]):
            raise ValueError(f'Book index/metadata mismatch: {variant} {wid}')
    process = psutil.Process()
    peak_rss = process.memory_info().rss
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    result_rows = []
    for number, q in enumerate(queries, 1):
        start = time.perf_counter()
        vector = np.asarray(model.encode([q['question']], convert_to_numpy=True,
                                         normalize_embeddings=True), dtype='float32')
        encoded_at = time.perf_counter()
        scores, positions = indexes[q['work_id']].search(vector, 50)
        searched_at = time.perf_counter()
        book_rows = by_book[q['work_id']]
        candidates = [{
            'rank': rank, 'chunk_id': book_rows[position]['chunk_id'],
            'source_start': book_rows[position]['source_start_char'],
            'source_end': book_rows[position]['source_end_char'],
            'similarity': float(score),
        } for rank, (position, score) in enumerate(zip(positions[0], scores[0]), 1)
            if position >= 0]
        ids = [c['chunk_id'] for c in candidates]
        chunks = {r['chunk_id']: {'start': r['source_start_char'],
                                  'end': r['source_end_char']} for r in book_rows}
        metrics = evaluate_query(q, ids, chunks)
        first = (candidates[metrics['first_rank'] - 1]
                 if metrics and metrics['first_rank'] else None)
        result_rows.append({
            'query_id': q['query_id'], 'work_id': q['work_id'], 'split': q['split'],
            'review_status': q['review_status'], 'metrics': metrics,
            'first_accepted': first, 'top50': candidates,
            'encoding_ms': round((encoded_at - start) * 1000, 3),
            'faiss_ms': round((searched_at - encoded_at) * 1000, 3),
            'total_ms': round((searched_at - start) * 1000, 3),
        })
        peak_rss = max(peak_rss, process.memory_info().rss)
        if number % 10 == 0 or number == len(queries):
            print(f'{variant} evaluated {number}/{len(queries)}', flush=True)
    summary = {
        'result_label': 'EXPLORATORY_ONLY_DRAFT_EVALUATION_LABELS',
        'variant': variant, 'question_count': len(queries),
        'metrics': aggregate(r['metrics'] for r in result_rows),
        'latency': {key: timing([r[key] for r in result_rows])
                    for key in ('encoding_ms', 'faiss_ms', 'total_ms')},
        'peak_process_rss_bytes': peak_rss,
        'peak_torch_gpu_allocated_bytes': (
            torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None),
        'no_gold_in_top50': sum(r['metrics'] is not None
                                and r['metrics']['first_rank'] is None
                                for r in result_rows),
    }
    (output_file or (folder / 'dense_evaluation.json')).write_text(json.dumps(
        {'summary': summary, 'queries': result_rows}, indent=2), encoding='utf-8')
    print(f"{variant}: MRR {summary['metrics']['mrr']:.3f}, "
          f"Hit@50 {summary['metrics']['hit']['50']:.3f}, "
          f"Recall@50 {summary['metrics']['recall']['50']:.3f}", flush=True)
    return summary


def compare_all():
    by_variant = {name: json.loads((BASE / name / 'dense_evaluation.json').read_text(
        encoding='utf-8')) for name in VARIANTS}
    baseline = {q['query_id']: q for q in by_variant['current_baseline']['queries']}
    comparison = {}
    for name in VARIANTS[1:]:
        changes = []
        for row in by_variant[name]['queries']:
            old = baseline[row['query_id']]['metrics']
            new = row['metrics']
            if old is None:
                continue
            old_rank = old['first_rank']
            new_rank = new['first_rank']
            old_value = old_rank if old_rank is not None else float('inf')
            new_value = new_rank if new_rank is not None else float('inf')
            status = ('IMPROVED' if new_value < old_value else
                      'REGRESSED' if new_value > old_value else 'UNCHANGED')
            changes.append({'query_id': row['query_id'], 'status': status,
                            'old_first_rank': old_rank, 'new_first_rank': new_rank,
                            'old_top50': old_rank is not None,
                            'new_top50': new_rank is not None})
        comparison[name] = {
            'counts': {status: sum(c['status'] == status for c in changes)
                       for status in ('IMPROVED', 'REGRESSED', 'UNCHANGED')},
            'top50_recovered': sum(not c['old_top50'] and c['new_top50'] for c in changes),
            'top50_lost': sum(c['old_top50'] and not c['new_top50'] for c in changes),
            'queries': changes,
        }
    out = BASE / 'reports' / 'dense_variant_comparison.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({'result_label': 'EXPLORATORY_ONLY_DRAFT_EVALUATION_LABELS',
                               'variants': comparison}, indent=2), encoding='utf-8')
    print(out)


def main(names):
    queries = json.loads(LABELS.read_text(encoding='utf-8'))['questions']
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = SentenceTransformer(MODEL_NAME, device=device, local_files_only=True)
    model.encode(['warm up'], convert_to_numpy=True, normalize_embeddings=True)
    for name in names:
        evaluate_variant(name, model, queries)
    if all((BASE / v / 'dense_evaluation.json').exists() for v in VARIANTS):
        compare_all()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--dense-only', action='store_true')
    group.add_argument('--variant', choices=VARIANTS)
    args = parser.parse_args()
    main(VARIANTS if args.dense_only else (args.variant,))
