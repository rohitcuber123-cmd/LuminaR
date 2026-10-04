"""Read-only audit of the actual RAG bi-encoder input window and gold spans."""
import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
BOOKS = ROOT / 'rag' / 'book_index' / 'books'
EVAL = ROOT / 'rag' / 'evaluation' / 'rag_retrieval_eval_v1.json'
SOURCE_MAP = ROOT / 'rag' / 'evaluation' / 'source_map_v1.json'
OUT_JSON = ROOT / 'reports' / 'rag_embedding_truncation_audit.json'
OUT_MD = ROOT / 'reports' / 'rag_embedding_truncation_audit.md'
MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'


def overlap(a, b, c, d):
    return max(0, min(b, d) - max(a, c))


def visible_char_end(encoded, tokenizer, max_length):
    """Match the body-token budget of single-sequence model truncation."""
    body_limit = max_length - tokenizer.num_special_tokens_to_add(pair=False)
    offsets = [offset for offset, special in zip(
        encoded['offset_mapping'], encoded['special_tokens_mask']) if not special][:body_limit]
    return max((end for _, end in offsets), default=0)


def audit():
    model = SentenceTransformer(MODEL_NAME, local_files_only=True, device='cpu')
    max_length = model.max_seq_length
    tokenizer = model.tokenizer
    chunks = {}
    for path in sorted(BOOKS.glob('*_metadata.json')):
        for row in json.loads(path.read_text(encoding='utf-8')):
            chunks[row['chunk_id']] = {'work_id': row['work_id'], 'text': row['text']}
    source_map = json.loads(SOURCE_MAP.read_text(encoding='utf-8'))['books']
    expected = {c['chunk_id']: c for b in source_map.values() for c in b['chunks']}
    if set(chunks) != set(expected):
        raise ValueError('Indexed metadata and evaluation source map have different chunk IDs')
    lengths = []
    length_by_id = {}
    by_book = {}
    visible_char_ends = {}
    for i, (cid, row) in enumerate(chunks.items(), 1):
        encoded = tokenizer(row['text'], add_special_tokens=True,
                            truncation=False, return_offsets_mapping=True,
                            return_special_tokens_mask=True)
        length = len(encoded['input_ids'])
        visible_end = visible_char_end(encoded, tokenizer, max_length)
        visible_char_ends[cid] = visible_end
        lengths.append(length)
        length_by_id[cid] = length
        by_book.setdefault(row['work_id'], []).append(length)
        if i % 500 == 0:
            print(f'Tokenized {i}/{len(chunks)} chunks', flush=True)
    arr = np.asarray(lengths, dtype=int)
    truncated = np.maximum(arr - max_length, 0)
    labels = json.loads(EVAL.read_text(encoding='utf-8'))['questions']
    span_rows = []
    for q in labels:
        for passage in q['accepted_passages']:
            per_chunk = []
            for cid in passage['current_chunk_matches']:
                chunk = expected[cid]
                covered = overlap(passage['source_start'], passage['source_end'],
                                  chunk['start'], chunk['end'])
                visible = overlap(passage['source_start'], passage['source_end'],
                                  chunk['start'], chunk['start'] + visible_char_ends[cid])
                per_chunk.append({'chunk_id': cid, 'chunk_token_count':
                                  length_by_id[cid],
                                  'source_chars_in_chunk': covered,
                                  'source_chars_visible': visible,
                                  'fraction_visible_of_chunk_covered':
                                  visible / covered if covered else 0})
            span_rows.append({
                'query_id': q['query_id'], 'work_id': q['work_id'],
                'source_start': passage['source_start'],
                'source_end': passage['source_end'],
                'matching_chunks': per_chunk,
                'any_matching_chunk_loses_evidence': any(
                    c['source_chars_visible'] < c['source_chars_in_chunk']
                    for c in per_chunk),
                'no_fully_visible_match': all(
                    c['source_chars_visible'] < c['source_chars_in_chunk']
                    for c in per_chunk),
                'entirely_beyond_window_in_all_matches': all(
                    c['source_chars_visible'] == 0 for c in per_chunk),
            })
    result = {
        'model_name': MODEL_NAME,
        'model_max_seq_length_including_special_tokens': max_length,
        'tokenizer_model_max_length': tokenizer.model_max_length,
        'embedding_dimension': model.get_embedding_dimension(),
        'chunk_count': len(chunks),
        'token_counts': {
            'mean': float(arr.mean()), 'median': float(np.median(arr)),
            'p90': float(np.percentile(arr, 90)),
            'p95': float(np.percentile(arr, 95)),
            'p99': float(np.percentile(arr, 99)),
            'max': int(arr.max()),
            'at_or_below_window_count': int((arr <= max_length).sum()),
            'at_or_below_window_percent': float((arr <= max_length).mean() * 100),
            'truncated_count': int((arr > max_length).sum()),
            'truncated_percent': float((arr > max_length).mean() * 100),
            'mean_truncated_tokens_all_chunks': float(truncated.mean()),
            'mean_truncated_tokens_if_truncated': float(
                truncated[arr > max_length].mean()) if (arr > max_length).any() else 0,
            'max_truncated_tokens': int(truncated.max()),
        },
        'by_book': {wid: {'chunks': len(vals),
                          'truncated': sum(n > max_length for n in vals),
                          'truncated_percent': 100 * sum(n > max_length for n in vals) / len(vals)}
                    for wid, vals in by_book.items()},
        'evaluation_span_risk': {
            'accepted_spans': len(span_rows),
            'spans_with_any_matching_chunk_losing_evidence': sum(
                x['any_matching_chunk_loses_evidence'] for x in span_rows),
            'spans_without_a_fully_visible_match': sum(
                x['no_fully_visible_match'] for x in span_rows),
            'spans_entirely_beyond_in_all_matches': sum(
                x['entirely_beyond_window_in_all_matches'] for x in span_rows),
        },
        'evaluation_spans': span_rows,
    }
    OUT_JSON.write_text(json.dumps(result, indent=2), encoding='utf-8')
    t = result['token_counts']
    s = result['evaluation_span_risk']
    lines = [
        '# LuminaR RAG embedding truncation audit', '',
        f"Model: `{MODEL_NAME}`; SentenceTransformer effective window: **{max_length} tokens including special tokens**; embedding dimension: **{result['embedding_dimension']}**.",
        f"Tokenizer model_max_length advertises {tokenizer.model_max_length}; the SentenceTransformer module setting controls actual encoding.", '',
        '| Statistic | Value |', '|---|---:|',
        f"| Chunks | {len(chunks):,} |",
        f"| Mean / median tokens | {t['mean']:.1f} / {t['median']:.1f} |",
        f"| p90 / p95 / p99 / max | {t['p90']:.0f} / {t['p95']:.0f} / {t['p99']:.0f} / {t['max']} |",
        f"| At or below {max_length} | {t['at_or_below_window_count']:,} ({t['at_or_below_window_percent']:.1f}%) |",
        f"| Truncated | {t['truncated_count']:,} ({t['truncated_percent']:.1f}%) |",
        f"| Mean excess tokens, all / truncated only | {t['mean_truncated_tokens_all_chunks']:.1f} / {t['mean_truncated_tokens_if_truncated']:.1f} |",
        f"| Maximum excess tokens | {t['max_truncated_tokens']} |", '',
        f"Of {s['accepted_spans']} accepted draft evaluation spans, {s['spans_with_any_matching_chunk_losing_evidence']} have at least one matching chunk whose answer evidence extends beyond the usable window; {s['spans_without_a_fully_visible_match']} have no fully visible matching chunk; {s['spans_entirely_beyond_in_all_matches']} are entirely beyond the window in every matching chunk.", '',
        'This audit reads production chunks and the DRAFT evaluation spans. It does not change production chunking, embeddings, or indexes. Span risks may change when labels are independently reviewed.',
    ]
    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    report = audit()
    print(f"Truncated {report['token_counts']['truncated_percent']:.1f}% of chunks")
    print(OUT_JSON)
    print(OUT_MD)
