import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from rag_domain_qa_v5 import extract_chunk_v5, statement_content_reason, validate_v5
from probe_rag_domain_qa_v5 import overlaps


def extracted(text):
    row = {"text": text, "source_start_char": 0, "source_end_char": len(text),
           "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
           "work_id": "TRAIN1", "title": "Synthetic", "chapter": "One",
           "chunk_id": "A", "split": "TRAIN"}
    return extract_chunk_v5(row)[0]


def high(text, relation):
    found = [c for c in extracted(text) if c["relation_type"] == relation and
             c["extraction_confidence"] == "HIGH"]
    assert found
    assert validate_v5(found[0], text)["validation_status"] == "AUTO_VALIDATED"
    return found[0]


def test_statement_explicit_speaker_before_and_after_quote():
    a = high('Elizabeth said, "Darcy had already left."', "STATEMENT")
    b = high('"Darcy had already left." said Elizabeth.', "STATEMENT")
    for c in (a, b):
        assert c["proposition"]["speaker"] == "Elizabeth"
        assert c["proposition"]["topic"] is None
        assert c["short_answer"] == "Darcy had already left."


def test_statement_vocative_is_not_speaker_or_topic():
    c = high('"Jane, come here." said Rochester.', "STATEMENT")
    assert c["proposition"]["speaker"] == "Rochester"
    assert c["proposition"]["topic"] is None


def test_capitalized_pseudo_entity_and_discourse_are_not_high():
    for text in ('"Well, perhaps you are right." said Alice.',
                 '"I swear the same!" said Van Helsing.',
                 '"Have you brought his indentures with you?" asked Miss Havisham.'):
        assert not any(c["relation_type"] == "STATEMENT" and
                       c["extraction_confidence"] == "HIGH" for c in extracted(text))


def test_statement_fragment_and_dangling_auxiliary_rejected():
    for content in ("Well", "Before", "I will", "Then you mean to tell me, Mr. Lorry,",
                    "Because they left.", "Darcy had already left,", "I swear the same!"):
        assert statement_content_reason(content)


def test_complete_imperative_and_clause_allowed():
    assert statement_content_reason("Wait here until morning.") is None
    assert statement_content_reason("Darcy had already left.") is None


def test_coordinated_action_context_downgraded():
    text = "Quincey found the lairs at Walworth and Mile End and destroyed them."
    c = [x for x in extracted(text) if x["relation_type"] == "ACTION"][0]
    assert c["extraction_confidence"] == "MEDIUM"
    assert "ACTION_COORDINATED_PREDICATE_DRIFT" in c["confidence_reasons"]
    assert validate_v5(c, text)["validation_status"] == "NOT_RUN"


def test_safe_v4_family_retained_and_statuses_separate():
    c = high("Filby became pensive.", "ATTRIBUTE")
    assert c["source_audit_status"] == "NOT_AUDITED"
    assert c["extraction_confidence"] == "HIGH"
    assert c["validation_status"] == "NOT_RUN"


def test_saved_v4_replay_blocks_all_known_failures():
    path = Path(__file__).resolve().parents[1] / "datasets/training/reports/rag_domain_qa_v5_v4_replay.json"
    replay = json.loads(path.read_text(encoding="utf-8"))
    assert replay["old_high"] == 27
    assert replay["known_v4_failures_still_auto_validating"] == 0
    assert replay["transitions"]["STILL_HIGH"] == 7


def test_source_overlap_detects_distinct_chunk_ids():
    a = {"work_id": "W", "source_start_char": 100, "source_end_char": 200}
    b = {"work_id": "W", "source_start": 199, "source_end": 250, "chunk_id": "different"}
    assert overlaps(a, b)
    b["source_start"] = 200
    assert not overlaps(a, b)


def test_v5_probe_manifest_is_disjoint_from_frozen_v4():
    root = Path(__file__).resolve().parents[1] / "datasets/training/manifests"
    v4 = json.loads((root / "rag_domain_qa_v4_probe_ranges.json").read_text(encoding="utf-8"))
    v5 = json.loads((root / "rag_domain_qa_v5_probe_ranges.json").read_text(encoding="utf-8"))
    assert len(v5["source_ranges"]) == 40
    assert not any(a["work_id"] == b["work_id"] and
                   a["source_start"] < b["source_end"] and
                   b["source_start"] < a["source_end"]
                   for a in v5["source_ranges"] for b in v4["source_ranges"])
