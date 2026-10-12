"""Deterministic, source-offset-preserving token chunks for RAG experiments.

This module never writes production chunks or indexes.
"""
from bisect import bisect_left, bisect_right
import hashlib
import re

VARIANTS = {
    'tokens_180': {'max_total_tokens': 180, 'overlap_body_tokens': 30},
    'tokens_220': {'max_total_tokens': 220, 'overlap_body_tokens': 40},
    'tokens_240': {'max_total_tokens': 240, 'overlap_body_tokens': 40},
}


def _breaks(source):
    paragraphs = [m.end() for m in re.finditer(r'\n\s*\n', source)]
    sentences = [m.end() for m in re.finditer(r'[.!?](?:["\'”’])?\s+', source)]
    words = [m.end() for m in re.finditer(r'\s+', source)]
    return paragraphs, sentences, words


def _last_between(points, low, high):
    at = bisect_right(points, high) - 1
    return points[at] if at >= 0 and points[at] >= low else None


def _trim(source, start, end):
    while start < end and source[start].isspace():
        start += 1
    while end > start and source[end - 1].isspace():
        end -= 1
    return start, end


def _is_midword(source, position):
    return (0 < position < len(source) and source[position - 1].isalnum()
            and source[position].isalnum())


def stable_chunk_id(work_id, variant, start, end, source_sha256):
    payload = f'{work_id}|{variant}|{start}|{end}|{source_sha256}'
    digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]
    return f'{work_id}__{variant}__{digest}'


def chunk_source(source, tokenizer, *, max_total_tokens, overlap_body_tokens):
    """Yield source offsets and text, preferring paragraph/sentence boundaries.

    The tokenizer's real special-token count is reserved before choosing body
    tokens. Final chunks are re-tokenized to enforce the configured total cap.
    """
    if not 0 < overlap_body_tokens < max_total_tokens // 2:
        raise ValueError('Overlap must be positive and smaller than half the window')
    body_limit = max_total_tokens - tokenizer.num_special_tokens_to_add(pair=False)
    if body_limit < 2:
        raise ValueError('No usable body-token capacity')
    tokenization = tokenizer(source, add_special_tokens=False, truncation=False,
                             return_offsets_mapping=True)
    offsets = [(a, b) for a, b in tokenization['offset_mapping'] if b > a]
    if not offsets:
        return []
    starts = [a for a, _ in offsets]
    ends = [b for _, b in offsets]
    paragraphs, sentences, words = _breaks(source)
    rows = []
    cursor = 0
    while cursor < len(source):
        left = bisect_left(starts, cursor)
        if left >= len(offsets):
            if source[cursor:].strip():
                raise ValueError('Tokenizer omitted meaningful source suffix')
            break
        last = min(left + body_limit - 1, len(offsets) - 1)
        max_end = ends[last]
        if last == len(offsets) - 1:
            end = len(source)
        else:
            min_index = min(left + max(1, int(body_limit * .55)) - 1, last)
            min_end = ends[min_index]
            end = (_last_between(paragraphs, min_end, max_end)
                   or _last_between(sentences, min_end, max_end)
                   or _last_between(words, cursor + 1, max_end))
            if end is None:
                if _is_midword(source, max_end):
                    raise ValueError('A single source word exceeds the token budget')
                end = max_end
        start, end = _trim(source, cursor, end)
        while start < end and len(tokenizer(source[start:end], add_special_tokens=True,
                                             truncation=False)['input_ids']) > max_total_tokens:
            prior = _last_between(words, start + 1, end - 1)
            if prior is None:
                raise ValueError('Cannot shorten overlong chunk at a word boundary')
            _, end = _trim(source, start, prior)
        if start >= end:
            raise ValueError('No forward progress in token-aware chunking')
        if _is_midword(source, start) or _is_midword(source, end):
            raise ValueError(f'Mid-word chunk boundary at [{start},{end})')
        rows.append({'start': start, 'end': end, 'text': source[start:end],
                     'token_count': len(tokenizer(source[start:end],
                                                  add_special_tokens=True,
                                                  truncation=False)['input_ids'])})
        if end >= len(source):
            break
        end_token = bisect_right(ends, end)
        desired_index = max(left + 1, end_token - overlap_body_tokens)
        desired_char = starts[min(desired_index, len(starts) - 1)]
        max_overlap = body_limit // 2
        sentence_candidates = [p for p in sentences[
            bisect_right(sentences, cursor):bisect_left(sentences, end)]
            if end_token - bisect_left(starts, p) <= max_overlap]
        if sentence_candidates:
            earlier = [p for p in sentence_candidates if p <= desired_char]
            next_start = max(earlier) if earlier else min(sentence_candidates)
        else:
            word_candidates = words[bisect_right(words, cursor):bisect_left(words, end)]
            next_start = (min(word_candidates, key=lambda p: abs(p - desired_char))
                          if word_candidates else end)
        if next_start <= cursor:
            next_start = end
        cursor = next_start
    return rows


def coverage_audit(source, rows):
    """Count meaningful uncovered characters without counting overlap twice."""
    covered_until = 0
    uncovered = 0
    invalid = 0
    midword_starts = 0
    midword_ends = 0
    for row in sorted(rows, key=lambda r: (r['start'], r['end'])):
        start, end = row['start'], row['end']
        invalid += int(not 0 <= start < end <= len(source)
                       or source[start:end] != row['text'])
        midword_starts += int(_is_midword(source, start))
        midword_ends += int(_is_midword(source, end))
        if start > covered_until:
            uncovered += sum(not c.isspace() for c in source[covered_until:start])
        covered_until = max(covered_until, end)
    uncovered += sum(not c.isspace() for c in source[covered_until:])
    return {'uncovered_meaningful_chars': uncovered, 'invalid_offsets_or_text': invalid,
            'midword_starts': midword_starts, 'midword_ends': midword_ends,
            'empty_chunks': sum(not r['text'].strip() for r in rows),
            'invalid_unicode_boundaries': sum(any(0xD800 <= ord(c) <= 0xDFFF
                                                   for c in r['text']) for r in rows),
            'malformed_whitespace': sum('\r' in r['text'] or '\x00' in r['text']
                                        for r in rows)}
