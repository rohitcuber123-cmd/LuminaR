import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from rag_domain_qa_contract_v7r3a import contract_replay, judge_bucket, question_intent, readiness


def record(question, answer, answer_type, evidence=None, category="FACTUAL_DIRECT"):
    return {"question": question, "short_answer": answer, "answer_type": answer_type,
            "evidence_quote": evidence or f"The source says {answer}.", "category_proposed": category}


def test_other_explicit_cannot_auto_pass():
    c = contract_replay(record("What object was used?", "thing", "OTHER_EXPLICIT"))
    assert not c["contract_pass"] and "OTHER_EXPLICIT_NEEDS_REVIEW" in c["contract_reasons"]


def test_where_requires_location():
    assert "QUESTION_ANSWER_TYPE_MISMATCH" in contract_replay(record("Where did Jane wait?", "Jane", "PERSON"))["contract_reasons"]
    assert question_intent("Where did Jane wait?") == "WHERE"


def test_when_requires_time():
    assert "QUESTION_ANSWER_TYPE_MISMATCH" in contract_replay(record("When did Jane leave?", "London", "LOCATION"))["contract_reasons"]


def test_who_requires_person():
    assert "QUESTION_ANSWER_TYPE_MISMATCH" in contract_replay(record("Who said this?", "guns", "OBJECT"))["contract_reasons"]


def test_why_requires_cause_or_motivation():
    assert "QUESTION_ANSWER_TYPE_MISMATCH" in contract_replay(record("Why did Jane leave?", "London", "LOCATION"))["contract_reasons"]


def test_mixed_time_location_answer_rejected():
    c = contract_replay(record("When did Jane visit?", "yesterday in London", "TIME"))
    assert "MIXED_SEMANTIC_ANSWER_SPAN" in c["contract_reasons"]


def test_ago_in_london_rejected_for_where():
    c = contract_replay(record("Where was Georgiana admired?", "ago in London", "OTHER_EXPLICIT"))
    assert "MIXED_SEMANTIC_ANSWER_SPAN" in c["contract_reasons"]


def test_speaker_identification_not_event():
    c = contract_replay(record("Who said, 'I'd rather finish my tea'?", "Hatter", "PERSON",
                               "'I'd rather finish my tea,' said the Hatter.", "EVENT"))
    assert c["category_final"] == "FACTUAL_DIRECT" and c["category_changed"]


def test_category_can_be_repaired_without_changing_qa():
    old = record("Who said, 'I'd rather finish my tea'?", "Hatter", "OTHER_EXPLICIT",
                 "'I'd rather finish my tea,' said the Hatter.", "EVENT")
    c = contract_replay(old)
    assert c["contract_pass"] and c["answer_type_final"] == "PERSON"
    assert c["category_changed"] and c["question_unchanged"] and c["answer_unchanged"] and c["evidence_unchanged"]
    assert old["category_proposed"] == "EVENT" and old["short_answer"] == "Hatter"


def test_answer_span_cannot_be_semantically_rewritten():
    old = record("Where was Georgiana admired?", "ago in London", "OTHER_EXPLICIT")
    c = contract_replay(old)
    assert not c["contract_pass"] and c["answer_unchanged"] and old["short_answer"] == "ago in London"


def test_judge_uncertain_not_equal_rejected():
    c = contract_replay(record("Who said hello?", "Hatter", "PERSON", "The Hatter said hello."))
    assert judge_bucket({"label": "UNCERTAIN", "failure_code": "JUDGE_SEMANTIC_UNCERTAIN"}) == "SEMANTIC_UNCERTAIN"
    assert readiness(c, "PLAUSIBLE_FOR_HUMAN_REVIEW", source_valid=True, leakage_free=True)["ready_for_human_review"]


def test_judge_invalid_json_not_semantic_uncertainty():
    assert judge_bucket({"label": "UNCERTAIN", "failure_code": "JUDGE_INVALID_JSON"}) == "INVALID_JSON"
    assert judge_bucket({"label": "UNCERTAIN", "failure_code": "JUDGE_SUPPORT_UNIT_OUTSIDE_EVIDENCE"}) == "INVALID_SUPPORT_REFERENCE"


def test_ready_for_human_review_requires_engineering_plausible():
    c = contract_replay(record("Who said hello?", "Hatter", "PERSON", "The Hatter said hello."))
    assert not readiness(c, "OBVIOUS_SEMANTIC_ERROR", source_valid=True, leakage_free=True)["ready_for_human_review"]


def test_ready_for_human_review_not_equal_reviewed():
    c = contract_replay(record("Who said hello?", "Hatter", "PERSON", "The Hatter said hello."))
    state = readiness(c, "PLAUSIBLE_FOR_HUMAN_REVIEW", source_valid=True, leakage_free=True)
    assert state["status"] == "READY_FOR_HUMAN_REVIEW" and not state["reviewed"]
