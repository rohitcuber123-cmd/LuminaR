"""Resolve source-first RAG question seeds to versioned, reviewable spans.

No retriever, FAISS index, reranker, or benchmark output is read here.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rag.book_ingest import clean_text

DIRECTORY = ROOT / 'rag' / 'evaluation'
SEEDS = DIRECTORY / 'source_first_seeds_v1.json'
SOURCE_MAP = DIRECTORY / 'source_map_v1.json'
OUT = DIRECTORY / 'rag_retrieval_eval_v1.json'
CATEGORIES = {'FACTUAL_DIRECT', 'ENTITY_RELATION', 'CAUSAL', 'MOTIVATION',
              'EVENT', 'TEMPORAL', 'LOCATION', 'QUOTE_OR_PHRASE',
              'MULTI_PASSAGE', 'BOUNDARY_SENSITIVE', 'SEMANTIC_PARAPHRASE'}
AMBIGUITIES = {'CLEAR', 'MULTIPLE_VALID', 'BOUNDARY', 'QUESTIONABLE'}


def build():
    mapping = json.loads(SOURCE_MAP.read_text(encoding='utf-8'))['books']
    seeds = json.loads(SEEDS.read_text(encoding='utf-8'))
    legacy_tree = ast.parse((ROOT / 'scratch' / 'run_v8_step7_retrieval_regression.py').read_text(encoding='utf-8'))
    legacy = next(ast.literal_eval(node.value) for node in legacy_tree.body
                  if isinstance(node, ast.Assign) and any(
                      isinstance(target, ast.Name) and target.id == 'RETRIEVAL_QUERIES'
                      for target in node.targets))
    legacy_questions = {row['id']: row for row in legacy}
    rows = []
    seen = set()
    for seed in seeds['questions']:
        qid = seed['query_id']
        if qid in seen:
            raise ValueError(f'Duplicate query ID: {qid}')
        seen.add(qid)
        work_id = seed['work_id']
        book = mapping[work_id]
        ambiguity = seed.get('ambiguity_type', 'CLEAR')
        difficulty = seed.get('difficulty', 'MEDIUM')
        split = seed.get('split', seeds['book_splits'][work_id])
        if split != seeds['book_splits'][work_id]:
            raise ValueError(f'Book-group split mismatch: {qid}')
        if 'legacy_id' in seed:
            original = legacy_questions[seed['legacy_id']]
            if original['work_id'] != work_id:
                raise ValueError(f'Legacy book mismatch: {qid}')
            question = original['query']
        else:
            question = seed['question']
        if seed['category'] not in CATEGORIES or ambiguity not in AMBIGUITIES:
            raise ValueError(f'Invalid category or ambiguity: {qid}')
        if difficulty not in {'EASY', 'MEDIUM', 'HARD'}:
            raise ValueError(f'Invalid difficulty: {qid}')
        if split not in {'DEV', 'TEST'}:
            raise ValueError(f'Invalid split: {qid}')
        source = clean_text((ROOT / book['source_file']).read_text(
            encoding='utf-8', errors='replace'))
        if hashlib.sha256(source.encode('utf-8')).hexdigest() != book['source_sha256']:
            raise ValueError(f'Source changed since offset map: {work_id}')
        passages = []
        for raw_item in seed['accepted_passages']:
            item = {'anchor': raw_item} if isinstance(raw_item, str) else raw_item
            anchor = item['anchor']
            # Gutenberg source lines wrap prose; an anchor may cross a newline.
            pattern = re.escape(anchor).replace(r'\ ', r'\s+')
            matches = list(re.finditer(pattern, source))
            count = len(matches)
            occurrence = item.get('occurrence')
            if count == 0 or (count != 1 and occurrence is None):
                raise ValueError(f'Anchor requires unambiguous occurrence: {qid} {anchor!r} count={count}')
            if occurrence is not None and not 0 <= occurrence < count:
                raise ValueError(f'Invalid occurrence: {qid}')
            match = matches[0 if occurrence is None else occurrence]
            start, end = match.span()
            before = item.get('context_before', 70)
            after = item.get('context_after', 70)
            span_start = max(0, start - before)
            span_end = min(len(source), end + after)
            span_len = span_end - span_start
            candidates = []
            for chunk in book['chunks']:
                overlap = max(0, min(span_end, chunk['end']) - max(span_start, chunk['start']))
                if overlap >= min(40, span_len) and overlap / span_len >= .8:
                    candidates.append(chunk['chunk_id'])
            chapter_chunk = max(book['chunks'], key=lambda c: max(
                0, min(span_end, c['end']) - max(span_start, c['start'])))
            chunk_position = book['chunks'].index(chapter_chunk)
            adjacent = {}
            for label, offset in (('previous', -1), ('current', 0), ('next', 1)):
                index = chunk_position + offset
                adjacent[label] = (book['chunks'][index]['chunk_id']
                                   if 0 <= index < len(book['chunks']) and
                                   book['chunks'][index]['chunk_id'] in candidates
                                   else None)
            passages.append({
                'source_start': span_start, 'source_end': span_end,
                'source_sha256': book['source_sha256'],
                'chapter': chapter_chunk['chapter'],
                'text_excerpt': source[span_start:span_end],
                'neighbor_allowance': bool(item.get('neighbor_allowance', False)),
                'relevance_grade': item.get('relevance_grade', 2),
                'current_chunk_matches': candidates,
                'adjacent_chunk_coverage': adjacent,
            })
        if ambiguity != 'QUESTIONABLE' and not any(
            x['relevance_grade'] == 2 for x in passages):
            raise ValueError(f'No answer-bearing source passage: {qid}')
        rows.append({
            'query_id': qid, 'work_id': work_id, 'book_title': book['book_title'],
            'question': question, 'category': seed['category'],
            'difficulty': difficulty, 'split': split,
            'accepted_passages': passages,
            'label_notes': seed.get('label_notes',
                'Source-backed draft; a human should check all alternate passages.'),
            'ambiguity_type': ambiguity,
            'review_status': 'DRAFT', 'human_review_count': 0,
            'origin': seed.get('origin', 'source_first_new'),
        })
    data = {'format_version': 'rag_retrieval_eval_v1',
            'label_definition': 'grade_2_source_span_coverage',
            'source_map': 'source_map_v1.json',
            'legacy_benchmark': 'legacy_proxy_v8',
            'human_reviewed': 0, 'questions': rows}
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    return data


if __name__ == '__main__':
    data = build()
    print(f"Built {len(data['questions'])} DRAFT source-backed questions from "
          f"{len({x['work_id'] for x in data['questions']})} books")
