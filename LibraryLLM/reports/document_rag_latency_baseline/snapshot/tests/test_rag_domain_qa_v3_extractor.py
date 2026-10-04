import hashlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from rag_domain_qa_v3 import (EXTRACTORS, Relation, accept_paraphrase, extract_chunk,
                              normalize, proposition_fingerprint, qa_fingerprint,
                              resolve_pronoun, segment_clauses, segment_sentences,
                              validate_v3)
from rag_domain_qa_v3_judge import StrictJSONEntailmentJudge


def row(text, *, chunk_id="A", start=0):
    source = " " * start + text
    return {"text": text, "source_start_char": start, "source_end_char": start + len(text),
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(), "work_id": "TRAIN1",
            "title": "Synthetic", "chapter": "One", "chunk_id": chunk_id, "split": "TRAIN"}, source


def get(text):
    r, source = row(text)
    return extract_chunk(r)[0], source


def test_relation_enum_closed():
    assert len(Relation) == 15
    with pytest.raises(ValueError): Relation("LLM_INVENTED_RELATION")


def test_llm_cannot_define_relation_type():
    c, _ = get("Mr. Lloyd instructed Bessie to keep Jane undisturbed.")
    assert c[0]["relation_type"] == "INSTRUCTION"
    assert c[0]["proposition"]["rule_id"] == "INSTRUCTION"


def test_sentence_offsets_preserve_honorifics():
    text = "Mr. Lloyd saw Bessie. Dr. Seward arrived later."
    spans = list(segment_sentences(text))
    assert len(spans) == 2
    assert all(text[s.start:s.end] == s.text for s in spans)


def test_clause_offsets_preserve_source():
    text = "Elizabeth left; Darcy remained: Jane arrived."
    sentence = list(segment_sentences(text))[0]
    clauses = list(segment_clauses(sentence))
    assert len(clauses) == 3
    assert all(text[c.start:c.end] == c.text for c in clauses)


def test_named_action_extraction():
    c, source = get("Old Orlick growled after Mr. Wopsle described the evening.")
    assert c[0]["relation_type"] == "ACTION"
    assert c[0]["short_answer"] == "growled"
    assert validate_v3(c[0], source)["review_status"] == "AUTO_VALIDATED"


def test_instruction_extraction_and_template():
    c, source = get("Mr. Lloyd instructed Bessie to keep Jane undisturbed.")
    assert c[0]["relation_type"] == "INSTRUCTION"
    assert c[0]["asked_slot"] == "object"
    assert c[0]["short_answer"] == "Bessie"
    assert "Mr. Lloyd" in c[0]["template_question"]
    assert validate_v3(c[0], source)["review_status"] == "AUTO_VALIDATED"


def test_entity_relation_extraction():
    c, source = get("Elizabeth was Darcy's cousin in the village.")
    assert c[0]["relation_type"] == "ENTITY_RELATION"
    assert c[0]["proposition"]["entity_a"] == "Elizabeth"
    assert c[0]["proposition"]["entity_b"] == "Darcy"
    assert c[0]["short_answer"] == "Elizabeth"
    assert validate_v3(c[0], source)["review_status"] == "AUTO_VALIDATED"


def test_location_from_to_extraction():
    c, source = get("Elizabeth travelled from London to Derbyshire.")
    assert [(x["relation_type"], x["short_answer"]) for x in c] == [
        ("LOCATION_FROM", "London"), ("LOCATION_TO", "Derbyshire")]
    assert all(validate_v3(x, source)["review_status"] == "AUTO_VALIDATED" for x in c)


def test_temporal_expression_extraction():
    c, source = get("Elizabeth arrived at ten o'clock.")
    assert c[0]["relation_type"] == "TEMPORAL_AT"
    assert c[0]["proposition"]["time"] == "at ten o'clock"
    assert c[0]["extractor_confidence"] == "MEDIUM"  # v2 currently rejects spelled-out clock times


def test_name_inside_from_phrase_is_not_event_subject():
    text = "The letter from Mr. Collins arrived on Tuesday, addressed to their father."
    c, _ = get(text)
    assert not any(x["relation_type"] == "TEMPORAL_AT" and
                   x["proposition"].get("subject") == "Mr. Collins" for x in c)


def test_explicit_causal_extraction():
    c, source = get("Victor destroyed the work because he feared its consequences.")
    assert c[0]["relation_type"] == "CAUSE"
    assert c[0]["short_answer"] == "he feared its consequences"
    assert validate_v3(c[0], source)["review_status"] == "AUTO_VALIDATED"


def test_noncausal_determined_rejected():
    c, _ = get("Victor came determined to carry out his purpose.")
    assert not any(x["relation_type"] == "CAUSE" for x in c)


def test_pronoun_unique_same_sentence_resolution():
    assert resolve_pronoun("she", "Elizabeth entered the room, and ")["resolved"] == "Elizabeth"
    c, source = get("Elizabeth entered the room, and she travelled from London to Derbyshire.")
    assert c[0]["referent_resolution"]["confidence"] == "HIGH"
    assert c[0]["proposition"]["subject"] == "Elizabeth"


def test_ambiguous_pronoun_rejected():
    assert resolve_pronoun("she", "Elizabeth met Jane, and ") is None
    c, _ = get("Elizabeth met Jane, and she travelled from London to Derbyshire.")
    assert not c


def test_negative_source_fragments_rejected():
    for text in ("He went there.", "She told him.", "The man was upset.", "Before.",
                 "He was determined."):
        assert not get(text)[0]


def test_participant_role_not_conflated():
    c, _ = get("A witness was selected. He was fishing with his brother-in-law, Daniel Nugent.")
    assert not any(x["short_answer"] == "Daniel Nugent" and "selected" in x["question"] for x in c)


def test_relation_extractor_priority():
    names = [type(x).__name__ for x in EXTRACTORS]
    assert names.index("InstructionExtractor") < names.index("ActionExtractor")
    assert names.index("EntityRelationExtractor") < names.index("ActionExtractor")


def test_generic_action_does_not_override_specific_relation():
    c, _ = get("Mr. Lloyd instructed Bessie to keep Jane undisturbed after Jane woke.")
    assert c and c[0]["relation_type"] == "INSTRUCTION"


def test_instruction_does_not_clip_at_length_limit():
    text = ("Van Helsing asked Mrs. Harker to look up the copy of the diaries "
            "and find him the part of Harker's journal at the Castle.")
    c, _ = get(text)
    assert c and c[0]["relation_type"] == "INSTRUCTION"
    assert "at the Castle?" in c[0]["question"]


def test_answer_slot_category_type_derived_from_rule():
    c, _ = get("Elizabeth travelled from London to Derbyshire.")
    assert c[0]["asked_slot"] == "location"
    assert c[0]["category"] == "LOCATION"
    assert c[0]["answer_type"] == "LOCATION"
    assert c[0]["proposition"]["location_direction"] == "FROM"


def test_template_preserves_relation_direction():
    c, _ = get("Elizabeth travelled from London to Derbyshire.")
    assert "travel from" in c[0]["template_question"]
    assert "travel to" in c[1]["template_question"]


def test_paraphrase_cannot_change_answer_or_direction():
    c, source = get("Elizabeth travelled from London to Derbyshire.")
    unchanged, reason = accept_paraphrase(c[0], "Where did Elizabeth travel from London?", source)
    assert unchanged["question"] == c[0]["question"]
    assert reason in {"ANSWER_DRIFT", "RELATION_DRIFT"}
    unchanged, reason = accept_paraphrase(c[0], "Where did Elizabeth travel to on the journey?", source)
    assert reason == "RELATION_DRIFT"


def test_proposition_fingerprint_deterministic():
    c, _ = get("Elizabeth travelled from London to Derbyshire.")
    assert proposition_fingerprint(c[0]) == proposition_fingerprint(c[0])
    assert proposition_fingerprint(c[0]) != proposition_fingerprint(c[1])


def test_qa_fingerprint_deterministic():
    c, _ = get("Elizabeth travelled from London to Derbyshire.")
    assert qa_fingerprint(c[0]) == qa_fingerprint(c[0])
    assert qa_fingerprint(c[0]) != qa_fingerprint(c[1])


def test_overlapping_chunks_collapse_by_authoritative_offsets():
    text = "Elizabeth travelled from London to Derbyshire."
    r1, _ = row(text, chunk_id="one")
    r2, _ = row(text, chunk_id="two")
    a, _ = extract_chunk(r1)
    b, _ = extract_chunk(r2)
    assert [x["proposition_fingerprint"] for x in a] == [x["proposition_fingerprint"] for x in b]


def test_normalization_keeps_authoritative_surface():
    assert normalize("Daniel\u00a0Nugent") == "daniel nugent"
    c, _ = get("Elizabeth travelled from London to Derbyshire.")
    assert c[0]["answer_surface"] == "London"
    assert c[0]["answer_normalized"] == "london"


def test_strict_json_judge_retries_once_then_uncertain():
    c, _ = get("Elizabeth travelled from London to Derbyshire.")
    calls = []
    def malformed(prompt):
        calls.append(prompt)
        return "not json"
    result = StrictJSONEntailmentJudge(malformed).judge(c[0])
    assert result.label == "UNCERTAIN"
    assert len(calls) == 2


def test_strict_json_judge_schema_and_support_required():
    import json
    c, _ = get("Elizabeth travelled from London to Derbyshire.")
    fields = {"label": "ENTAILED", "question_is_answered": True,
              "answer_matches_question": True, "evidence_supports_answer": True,
              "relation_direction_correct": False, "reason": "direction uncertain",
              "supporting_quote": "Elizabeth travelled from London"}
    result = StrictJSONEntailmentJudge(lambda _: json.dumps(fields)).judge(c[0])
    assert result.label == "UNCERTAIN"
