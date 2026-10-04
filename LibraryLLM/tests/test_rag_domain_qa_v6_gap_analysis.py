"""Read-only integrity checks for the frozen-probe V6 diagnosis."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_rag_domain_qa_v5_gaps import FROZEN, build_inventory

ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "datasets/training"


def test_every_saved_cue_accounted_for_with_reason_and_offsets():
    hashes, cues = build_inventory()
    assert len(cues) == 158
    assert len({c["cue_id"] for c in cues}) == 158
    assert all(c["no_match_reasons"] and c["clause_start"] < c["clause_end"]
               and c["sentence_start"] <= c["clause_start"] for c in cues)
    assert len(hashes) == len(FROZEN)


def test_frozen_v5_hashes_and_pattern_grouping_deterministic():
    saved = json.loads((TRAINING / "reports/rag_domain_qa_v6_v5_cue_inventory.json").read_text(encoding="utf-8"))
    hashes, cues = build_inventory()
    assert saved["frozen_v5_sha256"] == hashes
    assert [(c["cue_id"], c["structural_pattern"]) for c in saved["cues"]] == [
        (c["cue_id"], c["structural_pattern"]) for c in cues]
    assert all(hashlib.sha256((TRAINING / path).read_bytes()).hexdigest() == hashes[key]
               for key, path in FROZEN.items())


def test_v4_v5_failure_inventory_preserved():
    replay = json.loads((TRAINING / "reports/rag_domain_qa_v5_v4_replay.json").read_text(encoding="utf-8"))
    assert replay["old_high"] == 27
    assert replay["known_v4_failures_still_auto_validating"] == 0
    assert replay["transitions"] == {"DOWNGRADED_MEDIUM": 20, "STILL_HIGH": 7}
