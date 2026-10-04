"""The draft labels remain aligned with the immutable local source corpus."""
import ast
import hashlib
import json
from pathlib import Path

from rag.book_ingest import clean_text
from rag.evaluation.metrics import overlaps

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / 'rag' / 'evaluation'


def test_source_spans_and_book_group_split():
    dataset = json.loads((EVAL / 'rag_retrieval_eval_v1.json').read_text(encoding='utf-8'))
    mapping = json.loads((EVAL / 'source_map_v1.json').read_text(encoding='utf-8'))['books']
    assert len(dataset['questions']) >= 50
    assert len({q['work_id'] for q in dataset['questions']}) >= 10
    assert len({q['query_id'] for q in dataset['questions']}) == len(dataset['questions'])
    splits = {}
    for q in dataset['questions']:
        assert q['review_status'] == 'DRAFT' and q['human_review_count'] == 0
        splits.setdefault(q['work_id'], q['split'])
        assert splits[q['work_id']] == q['split']
        book = mapping[q['work_id']]
        source = clean_text((ROOT / book['source_file']).read_text(
            encoding='utf-8', errors='replace'))
        assert hashlib.sha256(source.encode('utf-8')).hexdigest() == book['source_sha256']
        chunks = {c['chunk_id']: c for c in book['chunks']}
        for p in q['accepted_passages']:
            assert p['text_excerpt'] == source[p['source_start']:p['source_end']]
            assert p['source_sha256'] == book['source_sha256']
            assert p['relevance_grade'] in (1, 2)
            assert p['current_chunk_matches']
            assert all(overlaps(chunks[cid], p) for cid in p['current_chunk_matches'])
            adjacent = p['adjacent_chunk_coverage']
            assert set(adjacent) == {'previous', 'current', 'next'}
            assert adjacent['current'] in p['current_chunk_matches']
            assert all(cid is None or cid in p['current_chunk_matches']
                       for cid in adjacent.values())


def test_legacy_questions_remain_verbatim():
    tree = ast.parse((ROOT / 'scratch' / 'run_v8_step7_retrieval_regression.py').read_text(
        encoding='utf-8'))
    original = next(ast.literal_eval(node.value) for node in tree.body
                    if isinstance(node, ast.Assign) and any(
                        isinstance(target, ast.Name) and target.id == 'RETRIEVAL_QUERIES'
                        for target in node.targets))
    labels = json.loads((EVAL / 'rag_retrieval_eval_v1.json').read_text(
        encoding='utf-8'))['questions']
    by_id = {q['query_id']: q for q in labels}
    for case in original:
        row = by_id[f"v8_{case['id']:02d}"]
        assert row['question'] == case['query']
        assert row['work_id'] == case['work_id']
        assert row['origin'] == 'legacy_proxy_v8'
