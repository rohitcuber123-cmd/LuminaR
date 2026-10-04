"""Token-aware RAG chunks retain source provenance and word boundaries."""
import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from transformers import AutoTokenizer

from rag.book_ingest import clean_text
from rag.experimental_chunker import chunk_source, coverage_audit, stable_chunk_id

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'datasets' / 'rag_experiments' / 'chunking_v1'


@pytest.fixture(scope='module')
def tokenizer():
    return AutoTokenizer.from_pretrained(
        'sentence-transformers/all-MiniLM-L6-v2', local_files_only=True)


def test_paragraph_sentence_word_preference_and_overlap(tokenizer):
    first = ' '.join('alpha' for _ in range(18))
    second = ' '.join('beta' for _ in range(18))
    source = first + '\n\n' + second + '\n\n' + ' '.join(
        'gamma' for _ in range(35))
    rows = chunk_source(source, tokenizer, max_total_tokens=32,
                        overlap_body_tokens=6)
    assert rows[0]['text'].endswith('alpha')
    assert source[rows[0]['end']:].startswith('\n\n')
    assert any(b['start'] < a['end'] for a, b in zip(rows, rows[1:]))
    assert coverage_audit(source, rows)['uncovered_meaningful_chars'] == 0
    assert coverage_audit(source, rows)['midword_starts'] == 0
    assert coverage_audit(source, rows)['midword_ends'] == 0
    assert max(r['token_count'] for r in rows) <= 32

    sentences = ' '.join('This is a complete source sentence.' for _ in range(12))
    sentence_rows = chunk_source(sentences, tokenizer, max_total_tokens=26,
                                 overlap_body_tokens=5)
    assert sentence_rows[0]['text'].endswith('.')
    assert coverage_audit(sentences, sentence_rows)['uncovered_meaningful_chars'] == 0

    words = ' '.join(f'Word{i}' for i in range(70))
    word_rows = chunk_source(words, tokenizer, max_total_tokens=25,
                             overlap_body_tokens=5)
    assert len(word_rows) > 1
    assert coverage_audit(words, word_rows)['midword_starts'] == 0
    assert coverage_audit(words, word_rows)['midword_ends'] == 0


def test_stable_ids_and_source_integrity_for_all_books():
    source_map = json.loads((ROOT / 'rag' / 'evaluation' /
                             'source_map_v1.json').read_text(encoding='utf-8'))['books']
    label_sha = hashlib.sha256((ROOT / 'rag' / 'evaluation' /
                                'rag_retrieval_eval_v1.json').read_bytes()).hexdigest()
    for variant, cap in [('current_baseline', None), ('tokens_180', 180),
                         ('tokens_220', 220), ('tokens_240', 240)]:
        folder = BASE / variant
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        rows = pq.read_table(folder / 'chunks.parquet').to_pylist()
        assert len(manifest['books']) == len(source_map) == 18
        assert manifest['evaluation_labels_sha256'] == label_sha
        assert len(rows) == manifest['statistics']['chunk_count']
        assert len({r['chunk_id'] for r in rows}) == len(rows)
        assert manifest['statistics']['uncovered_meaningful_chars'] == 0
        assert manifest['statistics']['invalid_offsets_or_text'] == 0
        if cap:
            assert manifest['statistics']['midword_starts'] == 0
            assert manifest['statistics']['midword_ends'] == 0
            assert max(r['token_count'] for r in rows) <= cap
        by_book = {}
        for row in rows:
            by_book.setdefault(row['work_id'], []).append(row)
        for work_id, book in source_map.items():
            source = clean_text((ROOT / book['source_file']).read_text(
                encoding='utf-8', errors='replace'))
            assert hashlib.sha256(source.encode('utf-8')).hexdigest() == book['source_sha256']
            book_rows = by_book[work_id]
            assert book_rows
            assert coverage_audit(source, [{'start': r['source_start_char'],
                                            'end': r['source_end_char'],
                                            'text': r['text']} for r in book_rows]
                                  )['uncovered_meaningful_chars'] == 0
            for row in book_rows:
                assert row['text'] == source[row['source_start_char']:row['source_end_char']]
                if cap:
                    assert row['chunk_id'] == stable_chunk_id(
                        work_id, variant, row['source_start_char'],
                        row['source_end_char'], book['source_sha256'])
