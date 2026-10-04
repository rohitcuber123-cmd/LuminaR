"""Small, source-grounded regression checks for V4's new closed patterns."""
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from rag_domain_qa_v4 import extract_chunk_v4, validate_v4


def cases(text):
    row = {"text": text, "source_start_char": 0, "source_end_char": len(text),
           "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
           "work_id": "TRAIN1", "title": "Synthetic", "chapter": "One",
           "chunk_id": "A", "split": "TRAIN"}
    return extract_chunk_v4(row)[0]


def high(text, relation, answer):
    found = [c for c in cases(text) if c["relation_type"] == relation and
             c["short_answer"] == answer and c["extractor_confidence"] == "HIGH"]
    assert found, text
    assert validate_v4(found[0], text)["review_status"] == "AUTO_VALIDATED"
    return found[0]


def test_attribute_role_and_state_change():
    high("Elizabeth was a nurse.", "ATTRIBUTE", "a nurse")
    high("Filby became pensive.", "ATTRIBUTE", "became pensive")
    assert not any(c["extractor_confidence"] == "HIGH" for c in cases("The man was something strange."))


def test_v3_high_is_preserved_and_location_direction():
    high("Mr. Lloyd instructed Bessie to keep Jane undisturbed.", "INSTRUCTION", "Bessie")
    found = cases("Elizabeth travelled from London to Derbyshire.")
    assert {(c["relation_type"], c["short_answer"]) for c in found if c["extractor_confidence"] == "HIGH"} == {
        ("LOCATION_FROM", "London"), ("LOCATION_TO", "Derbyshire")}


def test_cause_and_unsupported_cause():
    high("Victor destroyed the work because he feared its consequences.",
         "CAUSE", "he feared its consequences")
    assert not any(c["relation_type"] == "CAUSE" for c in cases(
        "Victor came determined to carry out his purpose."))


def test_temporal_unsupported_spelled_clock_stays_medium():
    found = cases("Elizabeth arrived at ten o'clock.")
    assert not any(c["extractor_confidence"] == "HIGH" for c in found)


def test_quote_requires_named_topic_and_local_attribution():
    assert not any(c["relation_type"] == "STATEMENT" for c in cases(
        '"It must be done before morning," said Elizabeth.'))


def test_training_value_independent_of_confidence():
    found = cases("Filby became pensive.")
    assert all(c.get("training_value") in {"HIGH", "MEDIUM", "LOW"} for c in found)
