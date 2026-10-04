"""V7R2 source-referenced QA and reversible normalization contracts."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_rag_domain_qa_assisted_v7r2 import SYSTEM, generation_prompt
from rag_domain_common import CATEGORIES, TRAINING, controls
from rag_domain_qa_assisted_v7r2 import (candidate_record_v7r2, parse_judge_v7r2,
                                         strict_json_v7r2)
from rag_domain_qa_source_units_v7r2 import (NormalizedSourceView, build_source_units,
                                               reconstruct_evidence, resolve_answer)


SOURCE = ("Mr. Lloyd instructed Bessie to keep Jane undisturbed during the night. "
          "After hearing the instructions, the nurse agreed and quietly left the room.")
BASE = {"question": "Who did Mr. Lloyd instruct to keep Jane undisturbed?",
        "answer_text": "Bessie", "answer_unit_id": "S01", "evidence_unit_ids": ["S01"],
        "category": "FACTUAL_DIRECT", "difficulty": "EASY",
        "support_explanation": "S01 explicitly names Bessie."}


def setup(source=SOURCE, split="TRAIN"):
    row = {"work_id": "test-train", "title": "Test", "chapter": "One", "chunk_id": "c1",
           "source_start_char": 0, "source_end_char": len(source), "text": source,
           "source_sha256": hashlib.sha256(source.encode()).hexdigest(), "split": split,
           "token_count": 25}
    view = NormalizedSourceView.build(source, 0, row["source_sha256"])
    return row, view, build_source_units(view)


def propose(source=SOURCE, generated=None, split="TRAIN"):
    row, view, units = setup(source, split)
    return candidate_record_v7r2(row, generated or BASE, view=view, units=units,
                                 context=source, context_start=0,
                                 generator_model="mock", source=source)


def test_presentation_normalization_round_trip():
    source = "Cafe\u0301\r\n  opened   the\tletter."
    view = NormalizedSourceView.build(source, 100, "hash")
    assert view.presentation_text == "Café opened the letter."
    assert view.verify_round_trip()
    a, b = view.map_presentation_span_to_authoritative(0, 4)
    assert source[a:b] == "Cafe\u0301"


def test_line_wrapped_source_maps_back_exactly():
    source = "Elizabeth opened the\nletter."
    view = NormalizedSourceView.build(source, 10, "hash")
    assert view.presentation_text == "Elizabeth opened the letter."
    p = view.presentation_text.index("opened the letter")
    assert view.get_authoritative_text_for_presentation_span(p, p + len("opened the letter")) == "opened the\nletter"


def test_source_unit_ids_offsets_and_hash_deterministic():
    row, view, units = setup()
    assert units == build_source_units(view)
    assert [u["unit_id"] for u in units] == ["S01", "S02"]
    for unit in units:
        a, b = unit["authoritative_start_in_passage"], unit["authoritative_end_in_passage"]
        assert row["text"][a:b] == unit["authoritative_text"]
        assert unit["source_hash"] == row["source_sha256"]
        assert (unit["absolute_source_start"], unit["absolute_source_end"]) == (a, b)


def test_evidence_reconstructed_from_source_not_model():
    row, view, units = setup()
    evidence, reasons = reconstruct_evidence(view, units, ["S01"])
    assert not reasons
    assert evidence["evidence_quote_authoritative"] == units[0]["authoritative_text"]
    record, reasons = propose()
    assert not reasons
    assert record["evidence_quote"] == units[0]["authoritative_text"]
    assert record["review_status"] == "GENERATED" and record["reviewer"] is None
    assert record["same_model_generator_judge"] is True


def test_two_adjacent_units_reconstruct_one_authoritative_span():
    row, view, units = setup()
    evidence, reasons = reconstruct_evidence(view, units, ["S01", "S02"])
    assert not reasons
    a, b = evidence["evidence_start_in_passage"], evidence["evidence_end_in_passage"]
    assert evidence["evidence_quote_authoritative"] == row["text"][a:b]
    assert units[0]["authoritative_text"] in evidence["evidence_quote_authoritative"]
    assert units[1]["authoritative_text"] in evidence["evidence_quote_authoritative"]


def test_model_cannot_supply_evidence_text_and_zero_candidate_valid():
    assert strict_json_v7r2(json.dumps({"candidates": [{**BASE, "evidence_quote": "invented"}]})) is None
    assert strict_json_v7r2('{"candidates": []}') == {"candidates": []}
    assert "DO NOT COPY EVIDENCE TEXT" in SYSTEM
    assert "[S01]" in generation_prompt(setup()[0], setup()[2], "context")


def test_invalid_evidence_unit_duplicate_and_noncontiguous():
    _, reasons = propose(generated={**BASE, "evidence_unit_ids": ["S99"]})
    assert "INVALID_EVIDENCE_UNIT_ID" in reasons
    _, reasons = propose(generated={**BASE, "evidence_unit_ids": ["S01", "S01"]})
    assert "INVALID_EVIDENCE_UNIT_ID" in reasons
    source = ("Alice found a handwritten note inside the old wooden desk. "
              "Bessie read the note aloud to everyone in the quiet room. "
              "Clara kept the note in a drawer until the following morning.")
    row, view, units = setup(source)
    assert [u["unit_id"] for u in units] == ["S01", "S02", "S03"]
    _, reasons = reconstruct_evidence(view, units, ["S01", "S03"])
    assert "NONCONTIGUOUS_EVIDENCE_UNITS" in reasons
    _, reasons = reconstruct_evidence(view, units, ["S01", "S02", "S03"])
    assert "TOO_MANY_EVIDENCE_UNITS" in reasons


def test_answer_unit_must_be_selected_evidence():
    _, reasons = propose(generated={**BASE, "answer_unit_id": "S02"})
    assert "ANSWER_UNIT_OUTSIDE_EVIDENCE" in reasons


def test_answer_exact_presentation_and_authoritative_line_wrap_mapping():
    source = "Elizabeth opened the\nletter."
    row, view, units = setup(source)
    result, reasons = resolve_answer(view, units, "S01", "opened the letter", ["S01"])
    assert not reasons
    assert result["answer_authoritative_text"] == "opened the\nletter"
    assert source[result["answer_authoritative_start"]:result["answer_authoritative_end"]] == result["answer_authoritative_text"]
    _, reasons = resolve_answer(view, units, "S01", "read the letter", ["S01"])
    assert "ANSWER_NOT_EXACT_IN_PRESENTATION" in reasons


def test_multiple_answer_occurrences_rejected():
    _, view, units = setup("Bessie spoke to Bessie after dinner.")
    _, reasons = resolve_answer(view, units, "S01", "Bessie", ["S01"])
    assert "AMBIGUOUS_ANSWER_OCCURRENCE" in reasons


def test_answer_fragment_rejected():
    source = "Clara arrived before sunrise."
    candidate = {**BASE, "question": "When did Clara arrive before the others?",
                 "answer_text": "before", "category": "TEMPORAL"}
    _, reasons = propose(source, candidate)
    assert "ANSWER_TOO_VAGUE" in reasons


def test_category_difficulty_and_context_only_name():
    _, reasons = propose(generated={**BASE, "category": "character_action"})
    assert "INVALID_CATEGORY" in reasons
    _, reasons = propose(generated={**BASE, "difficulty": "easy"})
    assert "INVALID_DIFFICULTY" in reasons
    assert len(CATEGORIES) == 9 and all(v in SYSTEM for v in CATEGORIES)
    assert all(v in SYSTEM for v in ("EASY", "MEDIUM", "HARD"))
    _, reasons = propose(generated={**BASE, "question": "Who did Elizabeth instruct to keep Jane undisturbed?"})
    assert "CONTEXT_ONLY_NAMED_REFERENCE" in reasons


def test_test_work_exclusion_and_real_manifest_eval_span_exclusion():
    _, reasons = propose(split="TEST")
    assert "NONTRAIN_AUTHORING_PROHIBITED" in reasons
    _, split, labels = controls()
    saved = json.loads((TRAINING / "manifests" / "rag_domain_qa_v7r1_original_passages.json").read_text())
    eval_spans = {}
    for q in labels:
        eval_spans.setdefault(q["work_id"], []).extend(p for p in q["accepted_passages"] if p["relevance_grade"] == 2)
    for p in saved["passages"]:
        assert p["work_id"] in split["train_work_ids"]
        assert p["work_id"] not in split["protected_test_work_ids"]
        assert not any(p["source_start"] < s["source_end"] and s["source_start"] < p["source_end"]
                       for s in eval_spans.get(p["work_id"], []))


def test_semantic_judge_cannot_change_evidence_units():
    good = {"label": "SUPPORTED", "question_answered_by_passage": True,
            "answer_supported": True, "question_self_contained": True,
            "requires_outside_context": False, "wrong_semantic_role": False,
            "reason": "explicit", "supporting_unit_ids": ["S01"]}
    assert parse_judge_v7r2(json.dumps(good), ["S01"])["label"] == "SUPPORTED"
    assert parse_judge_v7r2(json.dumps({**good, "supporting_unit_ids": ["S02"]}),
                            ["S01"])["label"] == "UNCERTAIN"
    assert parse_judge_v7r2("not json", ["S01"])["label"] == "UNCERTAIN"
