"""Evaluation-only dense-preserving union from captured v8 candidates."""
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rag.evaluation.metrics import evaluate_query, overlaps

BASELINE = ROOT / 'reports' / 'rag_retrieval_v1_draft_baseline.json'
LABELS = ROOT / 'rag' / 'evaluation' / 'rag_retrieval_eval_v1.json'
SOURCE_MAP = ROOT / 'rag' / 'evaluation' / 'source_map_v1.json'
OUT = ROOT / 'reports' / 'rag_candidate_union_draft_diagnostic.json'


def full_pool(query, ids, chunks):
    spans = [p for p in query['accepted_passages'] if p['relevance_grade'] == 2]
    if not spans:
        return None
    found = {i for cid in ids if cid in chunks for i, p in enumerate(spans)
             if overlaps(chunks[cid], p)}
    return {'hit': bool(found), 'recall': len(found) / len(spans)}


def main():
    baseline = json.loads(BASELINE.read_text(encoding='utf-8'))
    if baseline['summary']['label_status'] != 'DRAFT_ONLY_NOT_FOR_SELECTION':
        raise ValueError('Expected draft-only baseline')
    queries = {q['query_id']: q for q in json.loads(LABELS.read_text(
        encoding='utf-8'))['questions']}
    books = json.loads(SOURCE_MAP.read_text(encoding='utf-8'))['books']
    maps = {wid: {c['chunk_id']: c for c in b['chunks']}
            for wid, b in books.items()}
    records = []
    for row in baseline['records']:
        q = queries[row['query_id']]
        dense = row['dense_top50']
        expanded = row['expanded_admission_order']
        union = list(dict.fromkeys(dense + expanded))[:80]
        chunks = maps[q['work_id']]
        records.append({
            'query_id': q['query_id'], 'dense_count': len(dense),
            'expanded_count': len(expanded), 'union_count': len(union),
            'dense_full': full_pool(q, dense, chunks),
            'expanded_full': full_pool(q, expanded, chunks),
            'union_full': full_pool(q, union, chunks),
            'union_first_rank': (evaluate_query(q, union, chunks) or {}).get('first_rank'),
        })
    evaluable = [r for r in records if r['dense_full'] is not None]
    summary = {
        'label_status': 'DRAFT_ONLY_NOT_FOR_SELECTION',
        'construction': 'original dense Top-50, then new expanded candidates, deterministic dedupe, cap 80',
        'evaluable': len(evaluable),
        'mean_candidate_count': {key: statistics.mean(r[f'{key}_count'] for r in evaluable)
                                 for key in ('dense', 'expanded', 'union')},
        'full_pool_hit': {key: statistics.mean(r[f'{key}_full']['hit'] for r in evaluable)
                          for key in ('dense', 'expanded', 'union')},
        'full_pool_recall': {key: statistics.mean(r[f'{key}_full']['recall'] for r in evaluable)
                             for key in ('dense', 'expanded', 'union')},
        'expansion_recovers_dense_miss': sum(
            not r['dense_full']['hit'] and r['expanded_full']['hit'] for r in evaluable),
        'union_recovers_dense_miss': sum(
            not r['dense_full']['hit'] and r['union_full']['hit'] for r in evaluable),
    }
    OUT.write_text(json.dumps({'summary': summary, 'records': records}, indent=2),
                   encoding='utf-8')
    print(OUT)


if __name__ == '__main__':
    main()
