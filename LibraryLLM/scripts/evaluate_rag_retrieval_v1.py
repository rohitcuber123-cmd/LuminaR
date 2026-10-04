"""Exploratory v8 retrieval baseline against source-first DRAFT labels.

This runs the current retriever unchanged. It makes no adoption decision.
"""
import json
import hashlib
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rag.evaluation.metrics import aggregate, evaluate_query, oracle
from rag.evidence import generate_expanded_queries
from rag.reranker import RAGReranker
from rag.reranker import CANDIDATE_K

DATA = ROOT / 'rag' / 'evaluation' / 'rag_retrieval_eval_v1.json'
MAP = ROOT / 'rag' / 'evaluation' / 'source_map_v1.json'
OUTPUT = ROOT / 'reports' / 'rag_retrieval_v1_draft_baseline.json'


def main():
    hash_seed = os.environ.get('PYTHONHASHSEED')
    if hash_seed is None:
        raise RuntimeError('Set PYTHONHASHSEED before process start for reproducible query expansion')
    dataset = json.loads(DATA.read_text(encoding='utf-8'))
    mapping = json.loads(MAP.read_text(encoding='utf-8'))['books']
    chunk_maps = {wid: {c['chunk_id']: c for c in book['chunks']}
                  for wid, book in mapping.items()}
    reranker = RAGReranker()
    rows = []
    for i, q in enumerate(dataset['questions'], 1):
        t0 = time.perf_counter()
        dense = reranker.retriever.search(query=q['question'], top_k=50,
                                          work_id=q['work_id'])
        dense_ids = [x['chunk_id'] for x in dense['results']]
        t1 = time.perf_counter()
        expanded_ids = []
        for expanded_query in generate_expanded_queries(q['question']):
            result = reranker.retriever.search(query=expanded_query,
                                                top_k=CANDIDATE_K,
                                                work_id=q['work_id'])
            for item in result['results']:
                if item['chunk_id'] not in expanded_ids:
                    expanded_ids.append(item['chunk_id'])
        expanded_ids = expanded_ids[:40]
        ranked = reranker.search(query=q['question'], top_k=40,
                                 work_id=q['work_id'], intent_data={})
        ranked_ids = [x['chunk_id'] for x in ranked['results']]
        if set(ranked_ids) != set(expanded_ids):
            raise RuntimeError(f'Expanded candidate capture diverged: {q["query_id"]}')
        chunks = chunk_maps[q['work_id']]
        dense_metrics = evaluate_query(q, dense_ids, chunks)
        expanded_metrics = evaluate_query(q, expanded_ids, chunks)
        ranked_metrics = evaluate_query(q, ranked_ids, chunks)
        if ranked_metrics is None:
            failure = 'AMBIGUOUS_LABEL'
        elif ranked_metrics['first_rank'] == 1:
            failure = None
        elif not dense_metrics['hit']['50'] and not expanded_metrics['hit']['50']:
            failure = 'NO_GOLD_IN_TOP50'
        elif ranked_metrics['first_rank'] is None and dense_metrics['hit']['50']:
            failure = 'CANDIDATE_POOL_LOSS'
        elif ranked_metrics['first_rank'] is None:
            failure = 'NO_GOLD_IN_EXPANDED_POOL'
        elif ranked_metrics['first_rank'] <= 20:
            failure = 'GOLD_RANK_4_20' if ranked_metrics['first_rank'] >= 4 else 'RERANKER_DEMOTION'
        else:
            failure = 'GOLD_RANK_21_50'
        rows.append({'query_id': q['query_id'], 'work_id': q['work_id'],
                     'split': q['split'], 'review_status': q['review_status'],
                     'dense_top50': dense_ids, 'expanded_admission_order': expanded_ids,
                     'reranked': ranked_ids, 'dense_metrics': dense_metrics,
                     'expanded_metrics': expanded_metrics,
                     'reranked_metrics': ranked_metrics,
                     'failure_primary': failure,
                     'dense_ms': round((t1-t0)*1000, 2),
                     'rerank_path_ms': round((time.perf_counter()-t1)*1000, 2)})
        print(f"{i}/{len(dataset['questions'])} {q['query_id']} "
              f"dense={dense_metrics['first_rank'] if dense_metrics else '-'} "
              f"ranked={ranked_metrics['first_rank'] if ranked_metrics else '-'}", flush=True)
    evaluable = [r for r in rows if r['dense_metrics'] is not None]
    summary = {'label_status': 'DRAFT_ONLY_NOT_FOR_SELECTION',
               'python_hash_seed': hash_seed,
               'dataset_sha256': hashlib.sha256(DATA.read_bytes()).hexdigest(),
               'source_map_sha256': hashlib.sha256(MAP.read_bytes()).hexdigest(),
               'question_count': len(rows), 'evaluable': len(evaluable),
               'reranked_candidate_cap': 40,
               'dense': aggregate(r['dense_metrics'] for r in rows),
               'expanded_admission_order': aggregate(r['expanded_metrics'] for r in rows),
               'current_v8': aggregate(r['reranked_metrics'] for r in rows),
               'oracle_dense': [oracle((r['dense_metrics'] for r in rows), k)
                                for k in (5, 10, 20, 50)],
               'oracle_expanded': [oracle((r['expanded_metrics'] for r in rows), k)
                                   for k in (5, 10, 20, 40)],
               'failure_primary_counts': {x: sum(r['failure_primary'] == x for r in rows)
                                          for x in sorted({r['failure_primary'] for r in rows
                                                           if r['failure_primary']})},
               'mean_dense_ms': sum(r['dense_ms'] for r in rows)/len(rows),
               'mean_rerank_path_ms': sum(r['rerank_path_ms'] for r in rows)/len(rows)}
    OUTPUT.write_text(json.dumps({'summary': summary, 'records': rows}, indent=2),
                      encoding='utf-8')
    print(OUTPUT)


if __name__ == '__main__':
    main()
