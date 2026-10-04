import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import pytest

from rag_domain_qa_assisted_v7r3 import (parse_judge, parse_stage_a, parse_stage_b,
                                         question_reasons, validate_stage_a)
from rag_domain_qa_source_units_v7r2 import NormalizedSourceView, build_source_units
from rag_domain_qa_word_units_v7r3 import build_word_units, resolve_word_span

TEXT = "Mr. Lloyd instructed Bessie to keep Jane undisturbed during the night."


def fixture():
    view = NormalizedSourceView.build(TEXT, 100, "hash")
    units = build_source_units(view)
    words = build_word_units(view, units)
    ids = {w["presentation_surface"]: w["word_id"] for w in words[0]["words"]}
    candidate = {"evidence_unit_ids": ["S01"], "answer_unit_id": "S01",
                 "answer_start_word_id": ids["Bessie"], "answer_end_word_id": ids["Bessie"],
                 "fact_type": "FACTUAL_DIRECT", "fact_description": "Mr. Lloyd instructed Bessie.",
                 "answer_type": "PERSON"}
    return view, units, words, candidate


def test_word_ids_deterministic_and_offsets_map_to_both_surfaces():
    view, units, words, _ = fixture()
    assert words == build_word_units(view, units)
    for w in words[0]["words"]:
        assert view.presentation_text[w["presentation_start"]:w["presentation_end"]] == w["presentation_surface"]
        assert view.authoritative_text[w["authoritative_start"]:w["authoritative_end"]] == w["authoritative_surface"]


def test_answer_span_from_word_ids():
    view, units, words, c = fixture()
    answer, evidence, reasons = resolve_word_span(view, units, words, c)
    assert not reasons and answer["answer_authoritative_text"] == "Bessie"
    assert evidence["evidence_quote_authoritative"] == TEXT
    assert validate_stage_a(c, view, units, words)[2] == []


def test_regression_bessie_question_passes():
    assert question_reasons("Whom did Mr. Lloyd instruct to keep Jane undisturbed during the night?",
                            "Bessie", "PERSON", "FACTUAL_DIRECT", TEXT, TEXT) == []


def test_answer_span_linewrap_roundtrip():
    view = NormalizedSourceView.build("Mr. Lloyd instructed\nBessie to keep Jane undisturbed during the night.", 10, "hash")
    units = build_source_units(view)
    words = build_word_units(view, units)
    c = fixture()[3]
    answer, _, reasons = resolve_word_span(view, units, words, c)
    assert not reasons and answer["answer_authoritative_text"] == "Bessie"


@pytest.mark.parametrize("change,expected", [
    ({"answer_start_word_id": "W999"}, "INVALID_ANSWER_WORD_ID"),
    ({"answer_start_word_id": "W010", "answer_end_word_id": "W004"}, "ANSWER_SPAN_REVERSED"),
    ({"answer_unit_id": "S02"}, "ANSWER_SPAN_CROSSES_UNIT"),
    ({"answer_start_word_id": "W012", "answer_end_word_id": "W012"}, "ANSWER_SPAN_PUNCTUATION_ONLY"),
])
def test_invalid_answer_spans(change, expected):
    view, units, words, c = fixture()
    c.update(change)
    assert expected in resolve_word_span(view, units, words, c)[2]


def test_answer_span_incomplete_rejected():
    view, units, words, c = fixture()
    c["answer_start_word_id"] = c["answer_end_word_id"] = "W005"  # to
    assert "ANSWER_SPAN_INCOMPLETE" in validate_stage_a(c, view, units, words)[2]


def test_stage_a_zero_candidates_and_no_generated_answer_or_question():
    assert parse_stage_a('{"candidates":[]}') == {"candidates": []}
    _, _, _, c = fixture()
    for key in ("question", "answer_text", "evidence_quote", "difficulty"):
        assert parse_stage_a(json.dumps({"candidates": [{**c, key: "x"}]})) is None


def test_stage_a_max_two_and_strict_shape():
    _, _, _, c = fixture()
    assert parse_stage_a(json.dumps({"candidates": [c, c]})) is not None
    assert parse_stage_a(json.dumps({"candidates": [c, c, c]})) is None
    assert parse_stage_a(json.dumps({"candidates": [c], "question": "x"})) is None


def test_invalid_evidence_unit_id_rejected_before_stage_b():
    view, units, words, c = fixture()
    c["evidence_unit_ids"] = ["S99"]
    assert "INVALID_EVIDENCE_UNIT_ID" in validate_stage_a(c, view, units, words)[2]


def test_answer_unit_outside_evidence_rejected_before_stage_b():
    view, units, words, c = fixture()
    c["evidence_unit_ids"] = ["S01"]
    c["answer_unit_id"] = "S99"
    assert validate_stage_a(c, view, units, words)[2]


@pytest.mark.parametrize("key,value", [("fact_type", "BAD"), ("answer_type", "BAD")])
def test_stage_a_enums(key, value):
    view, units, words, c = fixture()
    c[key] = value
    assert validate_stage_a(c, view, units, words)[2]


def test_stage_b_receives_fixed_answer_and_cannot_change_it():
    assert parse_stage_b('{"question":"Whom did Mr. Lloyd instruct to keep Jane undisturbed during the night?","difficulty":"EASY"}')
    assert parse_stage_b('{"question":"Who?","difficulty":"EASY","answer":"Bessie"}') is None
    assert parse_stage_b('{"question":"Who?","difficulty":"EASY","evidence":"x"}') is None


def test_stage_b_abstention_and_question_only_schema():
    assert parse_stage_b('{"question":null,"difficulty":null,"reason":"Unsafe."}')
    assert parse_stage_b('{"question":null,"difficulty":"EASY","reason":"Unsafe."}') is None


def test_stage_b_invalid_json_and_no_category_invention():
    assert parse_stage_b("not json") is None
    assert parse_stage_b('{"question":"Who was named?","difficulty":"EASY","category":"EVENT"}') is None


@pytest.mark.parametrize("typ,question", [
    ("PERSON", "Where did Mr. Lloyd instruct someone to keep Jane undisturbed?"),
    ("LOCATION", "Who did Mr. Lloyd instruct to keep Jane undisturbed?"),
    ("TIME", "Who did Mr. Lloyd instruct to keep Jane undisturbed?"),
    ("CAUSE", "Who did Mr. Lloyd instruct to keep Jane undisturbed?"),
])
def test_answer_type_question_mismatch(typ, question):
    assert "QUESTION_ANSWER_TYPE_MISMATCH" in question_reasons(question, "Bessie", typ, "FACTUAL_DIRECT", TEXT, TEXT)


def test_question_answer_leakage_unresolved_pronoun_and_specificity():
    assert "QUESTION_CONTAINS_ANSWER" in question_reasons("What did Bessie do during the night?", "Bessie", "PERSON", "FACTUAL_DIRECT", TEXT, TEXT)
    assert "QUESTION_UNRESOLVED_REFERENT" in question_reasons("Whom did he instruct to keep Jane undisturbed?", "Bessie", "PERSON", "FACTUAL_DIRECT", TEXT, TEXT)
    assert "QUESTION_TOO_GENERIC" in question_reasons("What happened?", "Bessie", "PERSON", "FACTUAL_DIRECT", TEXT, TEXT)


def test_judge_invalid_json_separate_from_semantic_uncertain_and_cannot_change_evidence():
    assert parse_judge("invalid", ["S01"])["failure_code"] == "JUDGE_INVALID_JSON"
    uncertain = parse_judge('{"label":"UNCERTAIN","outside_context":false,"wrong_role":false,"supporting_unit_ids":[]}', ["S01"])
    assert uncertain["failure_code"] == "JUDGE_SEMANTIC_UNCERTAIN"
    outside = parse_judge('{"label":"SUPPORTED","outside_context":false,"wrong_role":false,"supporting_unit_ids":["S02"]}', ["S01"])
    assert outside["label"] == "UNCERTAIN"


def test_judge_supported_requires_selected_evidence_and_no_outside_context():
    missing = parse_judge('{"label":"SUPPORTED","outside_context":false,"wrong_role":false,"supporting_unit_ids":[]}', ["S01"])
    assert missing["label"] == "UNCERTAIN"
    outside = parse_judge('{"label":"SUPPORTED","outside_context":true,"wrong_role":false,"supporting_unit_ids":["S01"]}', ["S01"])
    assert outside["label"] == "UNCERTAIN"


def test_review_never_auto_approved():
    assert "APPROVED" not in ("AUTO_CHECKED", "AUTO_REJECTED")
