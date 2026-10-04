import hashlib
from datetime import date
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from rag_domain_qa_v2 import (EntailmentResult, answer_quality, classify_passage_v2,
                              generic_legacy_checks, near_duplicate, validate)
from rag_domain_qa_v2_review import CHECKS, review_decision


SOURCE = "Alice gave Bob a letter at London on Tuesday because Bob had requested a written answer."


def case(source=SOURCE):
    p = {"subject": "Alice", "predicate": "gave", "object": "a letter",
         "relation_type": "ENTITY_ACTION", "source_sentence": source, "evidence_quote": source,
         "evidence_start": 0, "evidence_end": len(source), "proof_kind": "EXACT_RULE",
         "rule_id": "synthetic_transitive"}
    return {"candidate_id": "SYNTH", "work_id": "TRAIN1", "split": "TRAIN",
            "source_start": 0, "source_end": len(source),
            "source_hash": hashlib.sha256(source.encode()).hexdigest(),
            "positive_passage": source, "proposition": p, "asked_slot": "object",
            "question": "What did Alice give Bob at London on Tuesday?",
            "short_answer": "a letter", "answer_type": "EVENT", "category": "FACTUAL_DIRECT",
            "question_from_template": True}


def codes(c, source=SOURCE, **kw):
    return validate(c, source, **kw)["auto_validation"]["rejection_reasons"]


def test_valid_exact_rule_is_auto_only():
    c = validate(case(), SOURCE)
    assert c["review_status"] == "AUTO_VALIDATED"
    assert c["review_status"] != "REVIEWED"


def test_exact_evidence_required():
    c = case(); c["proposition"]["evidence_quote"] += " extra"
    assert "EVIDENCE_NOT_EXACT" in codes(c)


def test_source_offsets_and_hash_integrity():
    c = case(); c["proposition"]["evidence_start"] = 1
    assert "EVIDENCE_NOT_EXACT" in codes(c)
    c = case(); c["source_hash"] = "wrong"
    assert "SOURCE_HASH_INTEGRITY" in codes(c)
    c = case(); c["source_end"] -= 1
    assert "SOURCE_MAPPING_FAILED" in codes(c)


def test_answer_must_belong_to_asked_slot_and_wrong_entity_role():
    c = case(); c["short_answer"] = "Bob"
    assert "WRONG_PROPOSITION_SLOT" in codes(c)
    c = case(); c["asked_slot"] = "subject"; c["short_answer"] = "Bob"; c["answer_type"] = "PERSON"
    c["question"] = "Who gave Bob a letter at London on Tuesday?"
    assert "WRONG_PROPOSITION_SLOT" in codes(c)


def test_subject_object_reversal_rejected():
    c = case(); c["proposition"].update(subject="Bob", object="Alice")
    c["short_answer"] = "Alice"; c["answer_type"] = "PERSON"
    assert "RELATION_DIRECTION_ERROR" in codes(c)


def test_relation_direction_rejected():
    source = "Alice was Bob's sister in the village."
    c = case(source); c["proposition"].update(subject="Alice", predicate="was", object="Bob",
        relation_type="ENTITY_RELATION", entity_a="Alice", entity_b="Bob")
    c["short_answer"] = "Bob"; c["answer_type"] = "PERSON"
    c["question"] = "Who was Alice related to in the village?"
    assert "RELATION_DIRECTION_ERROR" in codes(c, source)


def test_generator_category_is_not_silently_reassigned():
    c = case(); c["proposition"]["relation_type"] = "CAUSE_EFFECT"
    assert "CATEGORY_RELATION_MISMATCH" in codes(c)


def test_from_to_location_reversal_rejected():
    source = "Alice traveled from London to Dover during the spring."
    c = case(source); c["proposition"].update(subject="Alice", predicate="traveled", object="Dover",
        relation_type="LOCATION", location="from London", location_direction="FROM")
    c["asked_slot"] = "location"; c["short_answer"] = "from London"; c["answer_type"] = "LOCATION"
    c["question"] = "Where did Alice travel to during the spring?"
    assert "LOCATION_DIRECTION_ERROR" in codes(c, source)


def test_before_after_reversal_rejected():
    source = "Alice left on Tuesday before Bob arrived."
    c = case(source); c["proposition"].update(subject="Alice", predicate="left", object="Bob arrived",
        relation_type="TEMPORAL", time="on Tuesday", temporal_relation="BEFORE")
    c["asked_slot"] = "time"; c["short_answer"] = "on Tuesday"; c["answer_type"] = "TIME"
    c["question"] = "When did Alice leave after Bob arrived?"
    assert "RELATION_DIRECTION_ERROR" in codes(c, source)


@pytest.mark.parametrize("question,answer,typ,expected", [
    ("Who did Alice give the letter to on Tuesday?", "on Tuesday", "TIME", "ANSWER_TYPE_MISMATCH"),
    ("Where did Alice give Bob a letter on Tuesday?", "Bob", "PERSON", "ANSWER_TYPE_MISMATCH"),
    ("When did Alice give Bob a letter at London?", "Bob", "PERSON", "ANSWER_TYPE_MISMATCH"),
    ("Why did Alice give Bob a letter on Tuesday?", "a letter", "EVENT", "ANSWER_TYPE_MISMATCH"),
])
def test_wh_requires_compatible_answer_type(question, answer, typ, expected):
    c = case(); c.update(question=question, short_answer=answer, answer_type=typ)
    assert expected in codes(c)


def test_why_requires_explicit_cause_and_effect():
    source = "Alice came determined to carry out her purpose."
    c = case(source); c["proposition"].update(subject="Alice", predicate="came", object="her purpose",
        relation_type="MOTIVATION", cause="her purpose", effect="Alice came")
    c["asked_slot"] = "cause"; c["short_answer"] = "her purpose"; c["answer_type"] = "CAUSE"
    c["question"] = "Why did Alice come to the place that day?"
    assert "UNSUPPORTED_CAUSAL" in codes(c, source)


@pytest.mark.parametrize("answer", ["before)", "will", "information", "(", "the", "Thornfield will"])
def test_truncated_or_vague_answer_rejected(answer):
    assert answer_quality(answer, "PHRASE")


@pytest.mark.parametrize("question", [
    "What did the man give Bob at London on Tuesday?",
    "What did the speaker give Bob at London on Tuesday?",
    "What did he give Bob at London on Tuesday?",
    "What did the narrator give Bob at London on Tuesday?",
])
def test_unresolved_referent_rejected(question):
    c = case(); c["question"] = question
    assert "UNRESOLVED_REFERENT" in codes(c)


def test_question_contains_answer_guard():
    c = case(); c["question"] = "What did Alice do with a letter at London on Tuesday?"
    assert "QUESTION_CONTAINS_ANSWER" in codes(c)


@pytest.mark.parametrize("question", [
    "What is the title of this passage about Alice?",
    "What word appears in this passage about Alice?",
])
def test_trivial_metadata_and_meta_question_rejected(question):
    c = case(); c["question"] = question
    assert "TRIVIAL_METADATA" in codes(c)


def test_duplicate_and_eval_leakage():
    q = case()["question"]
    assert "NEAR_DUPLICATE" in codes(case(), seen_queries=[q])
    assert "EVAL_QUERY_SIMILARITY" in codes(case(), eval_queries=[q])
    assert "EVAL_QUERY_SIMILARITY" in codes(case(), eval_queries=["What did Alice give Bob at London that Tuesday?"])
    assert not near_duplicate(q, "What did Alice find in the library many years later?")


def test_test_book_rejected():
    assert "TEST_LEAKAGE" in codes(case(), test_works=["TRAIN1"])


def test_legacy_synthetic_failure_patterns():
    role = {"query": "Who was selected by the magistrate to testify?", "short_answer": "Daniel",
            "evidence_text": "A witness was selected by the magistrate. He was fishing with his brother-in-law, Daniel."}
    assert "WRONG_PROPOSITION_SLOT" in generic_legacy_checks(role)
    time = {"query": "When did she like Darcy before the visit?", "short_answer": "before)",
            "evidence_text": "She said she had never been bold enough before to say how much she liked Darcy."}
    assert "ANSWER_TYPE_MISMATCH" in generic_legacy_checks(time)
    why = {"query": "Why did he come to the house that day?", "short_answer": "because he was determined",
           "evidence_text": "He came determined to carry out his purpose."}
    assert "UNSUPPORTED_CAUSAL" in generic_legacy_checks(why)
    location = {"query": "Where did Alice travel to on the journey?", "short_answer": "London",
                "evidence_text": "Alice traveled from London to Dover."}
    assert "LOCATION_DIRECTION_ERROR" in generic_legacy_checks(location)


def decision(**overrides):
    d = {"decision": "APPROVE", "reviewer": "Human Reader", "review_date": date.today().isoformat(),
         **{k: "YES" for k in CHECKS}}
    d.update(overrides)
    return d


def test_approve_requires_reviewer_date_and_checklist():
    c = validate(case(), SOURCE)
    assert review_decision(c, decision(reviewer=""), SOURCE)[1] == ["REVIEWER_REQUIRED"]
    assert review_decision(c, decision(review_date=""), SOURCE)[1] == ["REVIEW_DATE_REQUIRED"]
    assert review_decision(c, decision(answer_correct="NO"), SOURCE)[1] == ["CHECKLIST_INCOMPLETE"]


def test_edit_is_revalidated_and_cannot_change_evidence_silently():
    c = validate(case(), SOURCE)
    assert review_decision(c, decision(decision="EDIT", edited_answer="Bob"), SOURCE)[1] == ["EDIT_REQUIRES_FRESH_SEMANTIC_JUDGE"]
    result, why = review_decision(c, decision(decision="EDIT", edited_answer="Bob"), SOURCE,
                                  semantic_judge=lambda: None)
    assert result is None and "WRONG_PROPOSITION_SLOT" in why
    result, why = review_decision(c, decision(decision="EDIT", edited_evidence="Alice gave Bob"), SOURCE)
    assert result is None and why == ["EDITED_EVIDENCE_REQUIRES_PROPOSITION"]


def test_uncertain_semantic_judge_cannot_auto_validate():
    class Uncertain:
        def judge(self, candidate):
            return EntailmentResult("UNCERTAIN", "Ambiguous participant role", "")
    assert validate(case(), SOURCE, judge=Uncertain())["review_status"] == "AUTO_CHECKED"


def test_judge_cannot_override_wrong_slot():
    class Overconfident:
        def judge(self, candidate):
            return EntailmentResult("ENTAILED", "claims yes", SOURCE)
    c = case(); c["short_answer"] = "Bob"
    checked = validate(c, SOURCE, judge=Overconfident())
    assert checked["review_status"] == "SEMANTIC_FAILED"
    assert "WRONG_PROPOSITION_SLOT" in checked["auto_validation"]["rejection_reasons"]


def test_dialogue_with_named_person_not_automatically_rejected():
    named = '“Good evening,” Alice said to Bob. She then handed him the letter. Bob thanked Alice.'
    row = {"text": named * 5, "token_count": 120}
    assert classify_passage_v2(row) == "GOOD_FOR_QA"
    vague = '“What should he do?” she asked. “It was that,” he replied. “We shall see,” she said.'
    row = {"text": vague * 5, "token_count": 120}
    assert classify_passage_v2(row) == "DIALOGUE_WITH_UNCLEAR_REFERENTS"


def test_deterministic_source_selection_seed():
    from build_rag_domain_qa_candidates_v2 import select_passages
    from rag_domain_common import passage_pool
    rows, _ = passage_pool()
    first = [x["chunk_id"] for x, _ in select_passages(rows, 42, 50)]
    second = [x["chunk_id"] for x, _ in select_passages(rows, 42, 50)]
    assert len(set(first)) == 50
    assert first == second
