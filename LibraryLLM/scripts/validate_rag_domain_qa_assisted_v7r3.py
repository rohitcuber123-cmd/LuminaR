"""Read-only validation of controlled V7R3 source and output integrity."""
from __future__ import annotations

from collections import Counter
import hashlib
import json

from rag_domain_common import ROOT, SOURCE_MAP, TRAINING, controls
from rag_domain_qa_assisted_v7r3 import parse_stage_a
from rag_domain_qa_source_units_v7r2 import NormalizedSourceView, build_source_units
from rag_domain_qa_word_units_v7r3 import build_word_units


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def validate():
    saved, split, labels = controls()
    manifest_path = TRAINING / "manifests" / "rag_domain_qa_v7r1_original_passages.json"
    old_path = TRAINING / "manifests" / "rag_domain_qa_v7r2_source_units.json"
    word_path = TRAINING / "manifests" / "rag_domain_qa_v7r3_word_units.json"
    original = json.loads(manifest_path.read_text(encoding="utf-8"))["passages"]
    old = json.loads(old_path.read_text(encoding="utf-8"))["passages"]
    word = json.loads(word_path.read_text(encoding="utf-8"))["passages"]
    base = TRAINING / "luminar"
    raw = read_jsonl(base / "domain_qa_assisted_v7r3_stage_a_raw.jsonl")
    valid = read_jsonl(base / "domain_qa_assisted_v7r3_stage_a_valid.jsonl")
    stage_b = read_jsonl(base / "domain_qa_assisted_v7r3_raw.jsonl")
    auto = read_jsonl(base / "domain_qa_assisted_v7r3_auto_checked.jsonl")
    rejected = read_jsonl(base / "domain_qa_assisted_v7r3_rejected.jsonl")
    report = json.loads((TRAINING / "reports" / "rag_domain_qa_assisted_v7r3_generation.json").read_text(encoding="utf-8"))
    if not len(original) == len(old) == len(word) == len(raw) == 50:
        raise RuntimeError("V7R3 source selection/count drift")
    for name, path in (("source_manifest_sha256", manifest_path), ("source_units_manifest_sha256", old_path),
                       ("word_units_manifest_sha256", word_path)):
        if report[name] != hashlib.sha256(path.read_bytes()).hexdigest():
            raise RuntimeError(name + " changed")
    eval_spans = {}
    for label in labels:
        eval_spans.setdefault(label["work_id"], []).extend(p for p in label["accepted_passages"] if p["relevance_grade"] == 2)
    source_map = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    sources = {wid: (ROOT / source_map[wid]["source_file"]).read_text(encoding="utf-8") for wid in {r["work_id"] for r in raw}}
    if any(hashlib.sha256(s.encode("utf-8")).hexdigest() != saved["source_hashes"][wid] for wid, s in sources.items()):
        raise RuntimeError("Authoritative source hash changed")
    production_path = ROOT / "datasets" / "rag_experiments" / "chunking_v1" / "reports" / "production_before_sha256.json"
    production = json.loads(production_path.read_text(encoding="utf-8"))
    if any(not (ROOT / name).exists() or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest
           for name, digest in production.items()):
        raise RuntimeError("Production snapshot changed")
    proposal_ids = []
    for i, (r, o, s, w) in enumerate(zip(raw, original, old, word), 1):
        keys = ("work_id", "chunk_id", "source_start", "source_end", "source_hash")
        if r["passage_index"] != i or any(r[k] != o[k] or o[k] != s[k] or o[k] != w[k] for k in keys):
            raise RuntimeError("Passage order/identity changed")
        if r["work_id"] not in split["train_work_ids"] or r["work_id"] in split["protected_test_work_ids"]:
            raise RuntimeError("TEST leakage")
        if any(r["source_start"] < p["source_end"] and p["source_start"] < r["source_end"] for p in eval_spans.get(r["work_id"], [])):
            raise RuntimeError("Evaluation span leakage")
        text = sources[r["work_id"]][r["source_start"]:r["source_end"]]
        view = NormalizedSourceView.build(text, r["source_start"], r["source_hash"])
        units = build_source_units(view)
        if view.presentation_text != s["presentation_text"] or units != s["units"] or build_word_units(view, units) != w["word_units"]:
            raise RuntimeError("Presentation, unit, or word offset drift")
        parsed = parse_stage_a(r["generator_raw"])
        if parsed is None:
            if r["candidate_ids"]: raise RuntimeError("Invalid Stage A JSON produced candidate IDs")
        elif len(parsed["candidates"]) != len(r["candidate_ids"]):
            raise RuntimeError("Stage A candidate count drift")
        proposal_ids.extend(r["candidate_ids"])
    if len(proposal_ids) != len(set(proposal_ids)):
        raise RuntimeError("Duplicate V7R3 candidate ID")
    outcome = [r["candidate_id"] for r in auto + rejected if r.get("candidate_id")]
    if sorted(outcome) != sorted(proposal_ids):
        raise RuntimeError("Missing or duplicated candidate outcome")
    if len(valid) != report["summary"].get("stage_a_valid_facts", 0) or len(stage_b) != report["summary"].get("stage_b_calls", 0):
        raise RuntimeError("Stage A/B counts drift")
    for c in auto:
        o = next(x for x in original if x["work_id"] == c["work_id"] and x["chunk_id"] == c["chunk_id"])
        text = sources[o["work_id"]][o["source_start"]:o["source_end"]]
        if c["positive_passage"] != text or c["source_hash"] != o["source_hash"]:
            raise RuntimeError("Accepted positive source drift")
        if text[c["answer_authoritative_start"]:c["answer_authoritative_end"]] != c["short_answer"]:
            raise RuntimeError("Accepted answer offset drift")
        if text[c["evidence_start_in_passage"]:c["evidence_end_in_passage"]] != c["evidence_quote"]:
            raise RuntimeError("Accepted evidence offset drift")
        if c["review_status"] != "AUTO_CHECKED" or c["reviewer"] is not None or c["review_date"] is not None:
            raise RuntimeError("Human review was auto-populated")
        if c["semantic_audit"]["label"] != "SUPPORTED" or not set(c["semantic_audit"]["supporting_unit_ids"]) <= set(c["evidence_unit_ids"]):
            raise RuntimeError("Judge escaped selected evidence")
    return {"passages": 50, "same_original_50_in_order": True, "source_hashes_valid": True,
            "unit_word_mapping_failures": 0, "test_leakage": 0, "evaluation_span_leakage": 0,
            "production_snapshot_files": len(production), "production_snapshot_changed": 0,
            "stage_a_valid_facts": len(valid), "stage_b_calls": len(stage_b), "auto_checked": len(auto),
            "rejected_records": len(rejected), "rejection_reasons": dict(Counter(reason for r in rejected for reason in r.get("rejection_reasons", [])))}


if __name__ == "__main__": print(json.dumps(validate(), indent=2))
