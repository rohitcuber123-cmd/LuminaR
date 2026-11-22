"""Independent labels for an isolated post-generation verifier pilot."""
import pytest

from evaluation.generated_answer_verification import verify_generated_answer


@pytest.mark.parametrize("question,passages,answer,label", [
    ("Does 61 minutes equal 3660 seconds?", ["61 minutes = 3660 seconds."], "No.", "CONTRADICTED"),
    ("Does 61 minutes equal 3660 seconds?", ["61 minutes = 3660 seconds."], "Yes.", "VERIFIED"),
    ("Does 2 hours equal 120 minutes?", ["2 hours = 120 minutes."], "Yes.", "VERIFIED"),
    ("Does 3 minutes equal 180 seconds?", ["3 minutes = 180 seconds."], "No.", "CONTRADICTED"),
    ("Is instrument duration 3660 seconds?", ["Instrument duration is 61 minutes."], "Yes.", "VERIFIED"),
    ("Is instrument duration 3600 seconds?", ["Instrument duration is 61 minutes."], "Yes.", "CONTRADICTED"),
    ("Is instrument duration 3600 seconds?", ["Instrument duration is 61 minutes."], "No.", "VERIFIED"),
    ("Is instrument duration 61 hours?", ["Instrument duration is 61 minutes."], "Yes.", "CONTRADICTED"),
    ("Is instrument duration 61 minutes?", ["Other instrument duration is 61 minutes."], "Yes.", "CONTRADICTED"),
    ("What is instrument duration?", ["Instrument duration is 61 minutes."], "61 minutes.", "VERIFIED"),
    ("What is instrument duration?", ["Instrument duration is 61 minutes."], "60 minutes.", "CONTRADICTED"),
    ("What is gauge access code?", ["Gauge access code is BRAVO-NINE."], "BRAVO-NINE.", "VERIFIED"),
    ("What is gauge access code?", ["Gauge access code is BRAVO-NINE."], "ALPHA-SEVEN.", "CONTRADICTED"),
    ("What is gauge test date?", ["Gauge test date is 2026-11-10."], "2026-11-10.", "VERIFIED"),
    ("What is gauge test date?", ["Gauge test date is 2026-11-10."], "2026-11-11.", "CONTRADICTED"),
    ("What is gauge access code?", ["Gauge access code is BRAVO-NINE."], "The passages do not establish it.", "ABSTAINED"),
    ("What is gauge access code?", ["Gauge access code is BRAVO-NINE."], "The checked passages do not provide the requested code.", "ABSTAINED"),
    ("What is gauge access code?", ["Gauge access code is BRAVO-NINE."], "The passages do not establish the code. Gauge access code is ALPHA-SEVEN.", "CONTRADICTED"),
    ("What is gauge access code?", ["Gauge access code is BRAVO-NINE."], "The passages do not establish it, but gauge access code is ALPHA-SEVEN.", "UNKNOWN"),
    ("What is gauge access code?", ["Gauge access code is BRAVO-NINE."], "Gauge access code is BRAVO-NINE. Gauge test code is C-924.", "CONTRADICTED"),
    ("What is gauge access code?", ["Gauge access code is BRAVO-NINE.", "Gauge test code is C-924."], "Gauge access code is BRAVO-NINE. Gauge test code is C-924.", "VERIFIED"),
    ("What is gauge access code?", ["Gauge access code is BRAVO-NINE."], "It might be BRAVO-NINE.", "UNKNOWN"),
    ("Does 61 minutes equal 1 hour?", ["61 minutes = 3660 seconds."], "Yes.", "UNKNOWN"),
    ("Why did Mira leave?", ["Mira left."], "Because she was tired.", "UNKNOWN"),
])
def test_development_matrix(question, passages, answer, label):
    evidence = [{"chunk_id": f"own-{i}", "text": text} for i, text in enumerate(passages)]
    assert verify_generated_answer(question, evidence, answer).status == label


def test_foreign_citation_is_rejected():
    evidence = [{"chunk_id": "own", "text": "Gauge access code is BRAVO-NINE."}]
    result = verify_generated_answer("What is gauge access code?", evidence, "BRAVO-NINE", ["foreign"])
    assert result.status == "CONTRADICTED"
