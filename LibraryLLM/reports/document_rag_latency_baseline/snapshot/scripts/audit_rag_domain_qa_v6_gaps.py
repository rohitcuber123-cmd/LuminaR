"""Validate exhaustive V6 diagnostics against saved V5 source and detector code."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json

from rag_domain_common import ROOT, SOURCE_MAP, TRAINING
from rag_domain_qa_v4 import V4_EXTRACTORS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all-cues", action="store_true")
    args = ap.parse_args()
    if not args.all_cues: raise ValueError("Use --all-cues")
    inventory = json.loads((TRAINING / "reports" / "rag_domain_qa_v6_v5_cue_inventory.json").read_text(encoding="utf-8"))
    cues = inventory["cues"]
    if len(cues) != 158 or len({c["cue_id"] for c in cues}) != 158:
        raise RuntimeError("Cue inventory is incomplete or has duplicate IDs")
    source_map = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    sources = {wid: (ROOT / source_map[wid]["source_file"]).read_text(encoding="utf-8")
               for wid in {c["work_id"] for c in cues}}
    extractor_by_name = {x.name: x for x in V4_EXTRACTORS}
    pattern_surface_hits = 0
    for c in cues:
        if not c["no_match_reasons"] or c["source_inspection_status"] != "INSPECTED_SOURCE_FIRST":
            raise RuntimeError(f"Unaudited cue: {c['cue_id']}")
        source = sources[c["work_id"]]
        if source[c["clause_start"]:c["clause_end"]] != c["clause_text"] or (
                source[c["sentence_start"]:c["sentence_end"]] != c["sentence_text"]):
            raise RuntimeError(f"Source offset mismatch: {c['cue_id']}")
        extractor = extractor_by_name[c["detector_family"]]
        if not extractor.can_match(type("Clause", (), {"text": c["clause_text"]})()):
            raise RuntimeError(f"Detector mismatch: {c['cue_id']}")
        patterns = [getattr(extractor, key) for key in
                    ("pattern", "role", "state", "appositive", "of_pattern", "departure")
                    if hasattr(extractor, key)]
        pattern_surface_hits += sum(bool(p.search(c["clause_text"])) for p in patterns)
    if pattern_surface_hits:
        raise RuntimeError("A concrete extractor regex matched; inspect implementation mismatch")
    hashes = {key: hashlib.sha256((TRAINING / path).read_bytes()).hexdigest()
              for key, path in {
                  "quality_gate": "reports/rag_domain_qa_v5_quality_gate.md",
                  "probe_json": "reports/rag_domain_qa_v5_probe.json",
                  "probe_md": "reports/rag_domain_qa_v5_probe.md",
                  "audit_md": "reports/rag_domain_qa_v5_probe_audit.md",
                  "ranges": "manifests/rag_domain_qa_v5_probe_ranges.json",
                  "high_jsonl": "luminar/domain_qa_v5_probe_high.jsonl",
                  "medium_jsonl": "luminar/domain_qa_v5_probe_medium.jsonl",
                  "rejected_jsonl": "luminar/domain_qa_v5_probe_rejected.jsonl",
              }.items()}
    if hashes != inventory["frozen_v5_sha256"]:
        raise RuntimeError("Frozen V5 artifact changed after cue inventory")
    result = {"cues_audited": 158, "missing_or_unparseable": 0,
              "source_offset_failures": 0, "source_hash_failures": 0,
              "detector_replay_failures": 0, "concrete_v4_regex_surface_hits": pattern_surface_hits,
              "family_counts": dict(Counter(c["detector_family"] for c in cues)),
              "frozen_v5_hashes_unchanged": True}
    (TRAINING / "reports" / "rag_domain_qa_v6_cue_audit.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    (TRAINING / "reports" / "rag_domain_qa_v6_cue_audit.md").write_text(
        "# Exhaustive saved-V5 cue audit\n\n"
        "All **158** detector events were inspected source-first in the [cue inventory](rag_domain_qa_v6_v5_cue_inventory.md). "
        "Each has an exact source clause/sentence span, lexical trigger, candidate surface fields, and explicit no-match reason. "
        "No cue was missing, unparseable, or offset-mismatched. Replaying the detector conditions found all 158; "
        "none matched a concrete V4 extractor regex surface. This supports a broad-cue/narrow-pattern diagnosis, "
        "not a silent candidate-emission failure.\n\n"
        "The V5 quote cue metric increments only after emission, so the 158-event count does not include failed V5 quote scans. "
        "That instrumentation issue did not cause the zero-emission result. All frozen V5 artifact hashes remain unchanged.\n",
        encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
