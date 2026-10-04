"""Evidence visibility for isolated chunk variants using unchanged DRAFT spans."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import pyarrow.parquet as pq
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rag.evaluation.metrics import overlaps
from scripts.audit_rag_embedding_lengths import visible_char_end

BASE = ROOT / 'datasets' / 'rag_experiments' / 'chunking_v1'
LABELS = ROOT / 'rag' / 'evaluation' / 'rag_retrieval_eval_v1.json'
MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'


def common(a, b, c, d):
    return max(0, min(b, d) - max(a, c))


def audit(variant):
    folder = BASE / variant
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['evaluation_labels_sha256'] != hashlib.sha256(LABELS.read_bytes()).hexdigest():
        raise ValueError('Evaluation labels changed since chunk construction')
    labels = json.loads(LABELS.read_text(encoding='utf-8'))['questions']
    rows = pq.read_table(folder / 'chunks.parquet').to_pylist()
    by_book = {}
    for row in rows:
        by_book.setdefault(row['work_id'], []).append(row)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, local_files_only=True)
    max_length = manifest['model_max_seq_length']
    visible_ends = {}

    def visible_end(row):
        cid = row['chunk_id']
        if cid not in visible_ends:
            if row['token_count'] <= max_length:
                visible_ends[cid] = row['source_end_char']
            else:
                encoded = tokenizer(row['text'], add_special_tokens=True,
                                    truncation=False, return_offsets_mapping=True,
                                    return_special_tokens_mask=True)
                visible_ends[cid] = row['source_start_char'] + visible_char_end(
                    encoded, tokenizer, max_length)
        return visible_ends[cid]

    outcomes = []
    for q in labels:
        for p in q['accepted_passages']:
            start, end = p['source_start'], p['source_end']
            length = end - start
            touching = [r for r in by_book[q['work_id']]
                        if common(start, end, r['source_start_char'], r['source_end_char'])]
            matching = [r for r in touching if overlaps({
                'start': r['source_start_char'], 'end': r['source_end_char']}, p)]
            best_visible = max((common(start, end, r['source_start_char'],
                                       visible_end(r)) for r in touching), default=0)
            best_match_visible = max((common(start, end, r['source_start_char'],
                                             visible_end(r)) for r in matching), default=0)
            policy_full = (best_match_visible >= min(40, length)
                           and best_match_visible / length >= .8)
            strict_full = any(r['source_start_char'] <= start and visible_end(r) >= end
                              for r in matching)
            status = ('FULLY_VISIBLE' if policy_full else
                      'PARTIALLY_VISIBLE' if best_visible else 'INVISIBLE')
            outcomes.append({
                'query_id': q['query_id'], 'work_id': q['work_id'],
                'source_start': start, 'source_end': end,
                'status': status, 'strict_entire_span_visible': strict_full,
                'best_visible_fraction': best_visible / length,
                'matching_chunk_count': len(matching),
                'cross_boundary_no_policy_match': bool(touching and not matching),
                'matching_chunk_ids': [r['chunk_id'] for r in matching],
            })
    counts = {status: sum(x['status'] == status for x in outcomes)
              for status in ('FULLY_VISIBLE', 'PARTIALLY_VISIBLE', 'INVISIBLE')}
    summary = {'result_label': 'EXPLORATORY_ONLY_DRAFT_EVALUATION_LABELS',
               'variant': variant, 'accepted_spans': len(outcomes),
               'counts': counts, 'fully_visible_percent':
               counts['FULLY_VISIBLE'] / len(outcomes) * 100,
               'strict_entire_span_visible': sum(x['strict_entire_span_visible']
                                                 for x in outcomes),
               'cross_boundary_no_policy_match': sum(
                   x['cross_boundary_no_policy_match'] for x in outcomes),
               'policy': '>=80% of source span and >=40 characters (or full shorter span) inside one encoder-visible matching chunk'}
    (folder / 'visibility.json').write_text(json.dumps(
        {'summary': summary, 'spans': outcomes}, indent=2), encoding='utf-8')
    print(variant, summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--variant', choices=[
        'current_baseline', 'tokens_180', 'tokens_220', 'tokens_240'], required=True)
    audit(parser.parse_args().variant)
