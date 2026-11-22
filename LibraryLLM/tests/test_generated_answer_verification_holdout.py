"""Held-out entities and values; labels are fixed independently of the verifier."""
import pytest

from evaluation.generated_answer_verification import verify_generated_answer


@pytest.mark.parametrize("question,text,answer,expected", [
    ("Does 7 hours equal 420 minutes?", "7 hours = 420 minutes.", "Yes.", "VERIFIED"),
    ("Does 7 hours equal 421 minutes?", "7 hours = 420 minutes.", "Yes.", "UNKNOWN"),
    ("Does 7 hours equal 421 minutes?", "7 hours = 421 minutes.", "No.", "UNKNOWN"),
    ("Is beacon runtime 540 seconds?", "Beacon runtime is 9 minutes.", "Yes.", "VERIFIED"),
    ("Is beacon runtime 540 minutes?", "Beacon runtime is 9 minutes.", "Yes.", "CONTRADICTED"),
    ("What is atlas release date?", "Atlas release date is 2026-08-19.", "2026-08-20.", "CONTRADICTED"),
    ("What is atlas release date?", "Atlas release date is 2026-08-19.", "2026-08-19.", "VERIFIED"),
    ("What is beacon access token?", "Beacon access token is VELA-27.", "VELA-27.", "VERIFIED"),
    ("What is beacon access token?", "Beacon access token is VELA-27.", "Beacon access token is VELA-28.", "CONTRADICTED"),
    ("Is beacon runtime 540 seconds?", "Other beacon runtime is 9 minutes.", "Yes.", "CONTRADICTED"),
    ("Is beacon runtime 540 seconds?", "No runtime is recorded.", "No.", "UNKNOWN"),
    ("What is beacon access token?", "Beacon access token might be VELA-27.", "VELA-27.", "UNKNOWN"),
    ("What is beacon access token?", "Beacon access token is VELA-27.", "I cannot determine that from the passages.", "ABSTAINED"),
])
def test_holdout(question, text, answer, expected):
    evidence = [{"chunk_id": "selected-doc-1", "text": text}]
    assert verify_generated_answer(question, evidence, answer, ["selected-doc-1"]).status == expected


def test_multiple_authorized_citations_and_negated_answer():
    evidence = [
        {"chunk_id": "selected-doc-1", "text": "Beacon access token is VELA-27."},
        {"chunk_id": "selected-doc-2", "text": "Beacon runtime is 9 minutes."},
    ]
    assert verify_generated_answer(
        "What is beacon access token?", evidence,
        "Beacon access token is VELA-27. Beacon runtime is 9 minutes.",
        ["selected-doc-1", "selected-doc-2"],
    ).status == "VERIFIED"
    assert verify_generated_answer(
        "What is beacon access token?", evidence,
        "Beacon access token is not VELA-27.", ["selected-doc-1"],
    ).status == "CONTRADICTED"


def test_foreign_library_content_cannot_supply_selected_document():
    evidence = [{"chunk_id": "foreign-1", "document_id": "library-b",
                 "text": "Beacon access token is VELA-27."}]
    result = verify_generated_answer(
        "What is beacon access token?", evidence, "VELA-27.",
        ["foreign-1"], selected_source_id="library-a",
    )
    assert result.status == "CONTRADICTED"
