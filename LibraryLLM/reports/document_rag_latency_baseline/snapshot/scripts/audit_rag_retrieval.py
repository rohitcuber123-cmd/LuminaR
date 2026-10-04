"""Read-only diagnostic for the frozen v8 RAG retrieval questions.

Records dense first-stage ranks, the actual expanded candidate pool and the
existing rerank order. It deliberately does not invent gold passage labels.
"""
import ast
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rag.evidence import generate_expanded_queries
from rag.reranker import CANDIDATE_K, RAGReranker

SOURCE = ROOT / 'scratch' / 'run_v8_step7_retrieval_regression.py'
OUTPUT = ROOT / 'reports' / 'rag_retrieval_diagnostic_20260925.json'


def frozen_cases():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == 'RETRIEVAL_QUERIES'
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise RuntimeError('Frozen retrieval cases not found')


def project(item):
    return {key: item.get(key) for key in (
        'rank', 'chunk_id', 'score', 'faiss_score', 'rerank_score',
        'evidence_score', 'final_score', 'work_id', 'title', 'chapter',
        'page', 'chunk_index', 'text'
    )}


def main():
    cases = frozen_cases()
    reranker = RAGReranker()
    retriever = reranker.retriever
    rows = []
    for case in cases:
        query, work_id = case['query'], case['work_id']
        start = time.perf_counter()
        dense = retriever.search(query=query, top_k=50, work_id=work_id)
        expanded = generate_expanded_queries(query)
        candidate_ids = []
        for expanded_query in expanded:
            result = retriever.search(query=expanded_query,
                                      top_k=CANDIDATE_K, work_id=work_id)
            for item in result['results']:
                chunk_id = item['chunk_id']
                if chunk_id not in candidate_ids:
                    candidate_ids.append(chunk_id)
        candidate_ids = candidate_ids[:40]
        final = reranker.search(query=query, top_k=40, work_id=work_id,
                                intent_data={})
        actual_ids = [item['chunk_id'] for item in final['results']]
        if set(actual_ids) != set(candidate_ids):
            raise RuntimeError('Candidate capture diverged from production path')
        rows.append({
            'id': case['id'], 'query': query, 'work_id': work_id,
            'original_keyword_rubric': {
                'top1': case['expected_top1_keywords'],
                'top3': case['expected_top3_keywords'],
            },
            'expanded_queries': expanded,
            'dense_original_top50': [project(item) for item in dense['results']],
            'expanded_candidate_ids_in_admission_order': candidate_ids,
            'reranked_all_candidates': [project(item) for item in final['results']],
            'elapsed_ms': round((time.perf_counter() - start) * 1000, 2),
        })
        print(f"{case['id']}/{len(cases)} dense={len(dense['results'])} "
              f"candidates={len(candidate_ids)}")
    output = {
        'purpose': 'Diagnostic only; no gold chunk labels exist in frozen suite',
        'source': str(SOURCE.relative_to(ROOT)),
        'case_count': len(rows),
        'records': rows,
    }
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
    print(OUTPUT)


if __name__ == '__main__':
    main()
