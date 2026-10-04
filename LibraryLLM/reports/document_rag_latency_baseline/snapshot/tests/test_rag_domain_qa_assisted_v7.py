"""V7 pilot contracts: source grounding and fail-closed automatic status."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from rag_domain_qa_assisted_v7 import (candidate_record, decontamination_reasons,
                                       parse_judge, strict_json)


SOURCE = "Elizabeth opened the letter after dinner. Mr. Darcy gave the letter to Elizabeth."
ROW = {
    "work_id": "test-book", "title": "Test Book", "chapter": "One", "chunk_id": "test-1",
    "source_start_char": 0, "source_end_char": len(SOURCE), "text": SOURCE,
    "source_sha256": hashlib.sha256(SOURCE.encode()).hexdigest(),
    "split": "TRAIN", "token_count": 24,
}
GENERATED = {
    "question": "What did Elizabeth open after dinner?",
    "short_answer": "the letter", "evidence_quote": "Elizabeth opened the letter after dinner.",
    "category": "EVENT", "difficulty": "EASY", "support_explanation": "The action is explicit.",
}


def propose(row=None, generated=None, source=SOURCE):
    return candidate_record(row or ROW, generated or GENERATED, context=source,
                            context_start=0, generator_model="local-test", source=source)


def test_strict_json_rejects_prose_and_schema_drift():
    assert strict_json(json.dumps({"candidates": [GENERATED]})) is not None
    assert strict_json('{"candidates": []}') == {"candidates": []}
    assert strict_json("```json\n" + json.dumps({"candidates": []}) + "\n```") is None
    assert strict_json(json.dumps({"candidates": [dict(GENERATED, invented="x")]})) is None
    assert strict_json(json.dumps({"candidates": [GENERATED] * 3})) is None


def test_exact_grounding_and_never_human_reviewed():
    record, reasons = propose()
    assert not reasons
    assert record["review_status"] == "GENERATED"
    assert record["reviewer"] is None
    assert record["absolute_evidence_start"] == 0
    assert SOURCE[record["absolute_evidence_start"]:record["absolute_evidence_end"]] == GENERATED["evidence_quote"]


def test_rejects_evidence_outside_positive_and_nonexact_answer():
    _, reasons = propose(generated={**GENERATED, "evidence_quote": "Mr. Darcy sent a letter."})
    assert "EVIDENCE_NOT_UNIQUE_EXACT_IN_POSITIVE" in reasons
    _, reasons = propose(generated={**GENERATED, "short_answer": "a letter"})
    assert "ANSWER_NOT_EXACT_IN_EVIDENCE" in reasons


def test_rejects_test_source_hash_and_context_drift():
    _, reasons = propose(row={**ROW, "split": "TEST"})
    assert "NONTRAIN_AUTHORING_PROHIBITED" in reasons
    _, reasons = propose(row={**ROW, "source_sha256": "incorrect"})
    assert "SOURCE_HASH_INTEGRITY" in reasons
    _, reasons = propose(source="Different source")
    assert "SOURCE_MAPPING_FAILED" in reasons


def test_rejects_unresolved_question_and_answer_leak():
    _, reasons = propose(generated={**GENERATED, "question": "What did she open after dinner?"})
    assert "QUESTION_UNRESOLVED_REFERENT" in reasons
    _, reasons = propose(generated={**GENERATED, "question": "Did Elizabeth open the letter after dinner?"})
    assert "QUESTION_CONTAINS_ANSWER" in reasons


def test_rejects_metadata_and_incomplete_answer():
    _, reasons = propose(generated={**GENERATED, "question": "What is the title of this passage?"})
    assert "GENERIC_METADATA_QUESTION" in reasons
    _, reasons = propose(generated={**GENERATED, "short_answer": "opened"})
    assert "ANSWER_TOO_VAGUE" in reasons


def test_eval_duplicate_and_same_fact_are_excluded():
    record, _ = propose()
    reasons, fact = decontamination_reasons(record, [record["question"]], [], set())
    assert "EVALUATION_QUERY_DUPLICATE_OR_NEAR" in reasons
    reasons, _ = decontamination_reasons(record, [], [], {fact})
    assert "DUPLICATE_SOURCE_FACT" in reasons


def test_judge_fails_closed_on_invalid_or_unverifiable_support():
    assert parse_judge("not json", GENERATED["evidence_quote"])["label"] == "UNCERTAIN"
    supported = {"label": "SUPPORTED", "question_answered_by_passage": True,
                 "answer_supported": True, "question_self_contained": True,
                 "requires_outside_context": False, "wrong_semantic_role": False,
                 "reason": "explicit", "supporting_quote": "the letter"}
    assert parse_judge(json.dumps(supported), GENERATED["evidence_quote"])["label"] == "SUPPORTED"
    assert parse_judge(json.dumps({**supported, "supporting_quote": "invented"}),
                       GENERATED["evidence_quote"])["label"] == "UNCERTAIN"
    assert parse_judge(json.dumps({**supported, "requires_outside_context": True}),
                       GENERATED["evidence_quote"])["label"] == "UNCERTAIN"
