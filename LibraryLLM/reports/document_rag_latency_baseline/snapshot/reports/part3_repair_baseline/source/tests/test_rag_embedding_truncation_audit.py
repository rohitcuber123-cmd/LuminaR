"""The audit's usable prefix matches actual tokenizer truncation."""
import json
from pathlib import Path

from transformers import AutoTokenizer

from scripts.audit_rag_embedding_lengths import visible_char_end

ROOT = Path(__file__).resolve().parents[1]


def test_visible_prefix_matches_real_tokenizer_truncation():
    tokenizer = AutoTokenizer.from_pretrained(
        'sentence-transformers/all-MiniLM-L6-v2', local_files_only=True)
    rows = json.loads((ROOT / 'rag' / 'book_index' / 'books' /
                       'OL45326637W_metadata.json').read_text(encoding='utf-8'))
    text = next(row['text'] for row in rows
                if row['chunk_id'] == 'OL45326637W_000044')
    raw = tokenizer(text, add_special_tokens=True, truncation=False,
                    return_offsets_mapping=True, return_special_tokens_mask=True)
    truncated = tokenizer(text, add_special_tokens=True, truncation=True,
                          max_length=256, return_offsets_mapping=True)
    actual_end = max(end for _, end in truncated['offset_mapping'])
    assert len(truncated['input_ids']) == 256
    assert len(raw['input_ids']) > 256
    assert visible_char_end(raw, tokenizer, 256) == actual_end
    assert actual_end < len(text)


def test_audit_covers_current_source_spans():
    audit = json.loads((ROOT / 'reports' / 'rag_embedding_truncation_audit.json').read_text())
    labels = json.loads((ROOT / 'rag' / 'evaluation' /
                         'rag_retrieval_eval_v1.json').read_text(encoding='utf-8'))
    assert audit['chunk_count'] == 3959
    assert audit['token_counts']['truncated_count'] + audit['token_counts'][
        'at_or_below_window_count'] == audit['chunk_count']
    assert audit['evaluation_span_risk']['accepted_spans'] == sum(
        len(q['accepted_passages']) for q in labels['questions'])
    assert all(p['matching_chunks'] for p in audit['evaluation_spans'])
