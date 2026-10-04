"""V7R1 fixed-contract and evidence diagnostics regression tests."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_rag_domain_qa_assisted_v7r1 import SYSTEM, generation_prompt
from rag_domain_common import CATEGORIES
from rag_domain_qa_assisted_v7 import strict_json
from rag_domain_qa_assisted_v7r1 import candidate_record_v7r1, evidence_diagnostics


def row_for(source):
    return {"work_id": "test-train", "title": "Test", "chapter": "One", "chunk_id": "c1",
            "source_start_char": 0, "source_end_char": len(source), "text": source,
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "split": "TRAIN", "token_count": 25}


def check(source, generated):
    return candidate_record_v7r1(row_for(source), generated, context=source,
                                 context_start=0, generator_model="mock", source=source)


BASE = {"question": "Who did Mr. Lloyd instruct to wait?", "short_answer": "Bessie",
        "evidence_quote": "Mr. Lloyd instructed Bessie to wait.",
        "category": "FACTUAL_DIRECT", "difficulty": "EASY",
        "support_explanation": "The source states it."}


def test_prompt_names_every_enum_and_extractiveness_rule():
    for category in CATEGORIES:
        assert category in SYSTEM
    for difficulty in ("EASY", "MEDIUM", "HARD"):
        assert difficulty in SYSTEM
    assert "character-for-character" in SYSTEM
    assert "exact contiguous substring" in SYSTEM
    assert '{"candidates":[]}' in SYSTEM
    prompt = generation_prompt(row_for(BASE["evidence_quote"]), BASE["evidence_quote"])
    assert "<TARGET_PASSAGE>" in prompt and "<AUTHORING_CONTEXT>" in prompt


def test_mock_generator_schema_and_grounding():
    response = strict_json(json.dumps({"candidates": [BASE]}))
    assert response is not None
    record, reasons, diag = check(BASE["evidence_quote"], response["candidates"][0])
    assert not reasons
    assert record["generation_version"] == "v7r1"
    assert record["review_status"] == "GENERATED"
    assert diag["evidence_exact_match_count"] == 1
    assert diag["evidence_match_offsets"] == [0]
    assert diag["answer_exact_match_count_in_evidence"] == 1
    assert diag["normalization_applied"] is False


def test_invalid_category_and_exact_difficulty():
    _, reasons, _ = check(BASE["evidence_quote"], {**BASE, "category": "character_action"})
    assert "INVALID_CATEGORY" in reasons
    _, reasons, _ = check(BASE["evidence_quote"], {**BASE, "difficulty": "easy"})
    assert "INVALID_DIFFICULTY" in reasons


def test_all_nine_category_values_are_legal_in_contract():
    assert len(CATEGORIES) == 9
    for category in CATEGORIES:
        assert category in SYSTEM
        _, reasons, _ = check(BASE["evidence_quote"], {**BASE, "category": category})
        assert "INVALID_CATEGORY" not in reasons


def test_paraphrase_and_empty_evidence_have_distinct_failures():
    _, reasons, diag = check("Elizabeth opened the letter.",
                             {**BASE, "evidence_quote": "Elizabeth read the letter."})
    assert "EVIDENCE_NOT_EXACT_IN_POSITIVE" in reasons
    assert diag["evidence_exact_match_count"] == 0
    _, reasons, diag = check("Elizabeth opened the letter.", {**BASE, "evidence_quote": ""})
    assert "EMPTY_EVIDENCE" in reasons
    assert diag["evidence_match_offsets"] == []
    assert diag["evidence_exact_match_count"] == 0


def test_multiple_exact_occurrences_are_ambiguous_without_offset():
    source = "He waited. He waited."
    _, reasons, diag = check(source, {**BASE, "evidence_quote": "He waited.", "short_answer": "waited"})
    assert "AMBIGUOUS_EVIDENCE_OCCURRENCE" in reasons
    assert diag["evidence_match_offsets"] == [0, 11]


def test_answer_exactness_and_completeness():
    source = "Clara arrived before sunrise."
    good = {**BASE, "question": "When did Clara arrive before the others?",
            "evidence_quote": source, "short_answer": "before sunrise", "category": "TEMPORAL"}
    record, reasons, _ = check(source, good)
    assert not reasons and record is not None
    _, reasons, _ = check(source, {**good, "short_answer": "before"})
    assert "ANSWER_TOO_VAGUE" in reasons
    _, reasons, _ = check("Elizabeth opened the letter.",
                          {**BASE, "evidence_quote": "Elizabeth opened the letter.",
                           "short_answer": "read the letter"})
    assert "ANSWER_NOT_EXACT_IN_EVIDENCE" in reasons


def test_category_question_mismatch():
    _, reasons, _ = check("Elizabeth went to London.",
                          {**BASE, "question": "Where did Elizabeth go after leaving?",
                           "evidence_quote": "Elizabeth went to London.",
                           "short_answer": "London", "category": "CAUSAL"})
    assert "CATEGORY_QUESTION_MISMATCH" in reasons
