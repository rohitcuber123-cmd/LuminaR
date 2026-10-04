"""Read-only V7R2 source, schema, and outcome integrity validation."""
from __future__ import annotations

from collections import Counter
import hashlib
import json

import pyarrow.parquet as pq

from rag_domain_common import CONTROL, ROOT, SOURCE_MAP, TRAINING, controls
from rag_domain_qa_assisted_v7r2 import strict_json_v7r2
from rag_domain_qa_source_units_v7r2 import NormalizedSourceView, build_source_units


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def validate():
    saved, split, labels = controls()
    base = TRAINING / "luminar"
    raw = read_jsonl(base / "domain_qa_assisted_v7r2_raw.jsonl")
    auto = read_jsonl(base / "domain_qa_assisted_v7r2_auto_checked.jsonl")
    rejected = read_jsonl(base / "domain_qa_assisted_v7r2_rejected.jsonl")
    generation = json.loads((TRAINING / "reports" / "rag_domain_qa_assisted_v7r2_generation.json").read_text(encoding="utf-8"))
    manifest_path = TRAINING / "manifests" / "rag_domain_qa_v7r1_original_passages.json"
    unit_path = TRAINING / "manifests" / "rag_domain_qa_v7r2_source_units.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))["passages"]
    unit_manifest = json.loads(unit_path.read_text(encoding="utf-8"))["passages"]
    if len(raw) != len(manifest) or len(raw) != len(unit_manifest) or len(raw) != 50:
        raise RuntimeError("V7R2 must have the original 50 passages")
    if (hashlib.sha256(manifest_path.read_bytes()).hexdigest() != generation["source_manifest_sha256"] or
            hashlib.sha256(unit_path.read_bytes()).hexdigest() != generation["source_units_manifest_sha256"]):
        raise RuntimeError("V7R2 source manifest hash drift")
    chunks = {(r["work_id"], r["chunk_id"]): r for r in pq.read_table(CONTROL / "chunks.parquet").to_pylist()}
    source_map = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    eval_spans = {}
    for label in labels:
        eval_spans.setdefault(label["work_id"], []).extend(p for p in label["accepted_passages"] if p["relevance_grade"] == 2)
    counts = Counter()
    ids = []
    for i, (r, original, unit_entry) in enumerate(zip(raw, manifest, unit_manifest), 1):
        key = (original["work_id"], original["chunk_id"])
        if (r["passage_index"], r["work_id"], r["chunk_id"], r["source_start"], r["source_end"], r["source_hash"]) != (
                i, *key, original["source_start"], original["source_end"], original["source_hash"]):
            raise RuntimeError("V7R2 passage order/source drift")
        if key != (unit_entry["work_id"], unit_entry["chunk_id"]):
            raise RuntimeError("V7R2 source-unit selection drift")
        if r["work_id"] not in split["train_work_ids"] or r["work_id"] in split["protected_test_work_ids"]:
            raise RuntimeError("V7R2 non-TRAIN source")
        row = chunks[key]
        source = (ROOT / source_map[r["work_id"]]["source_file"]).read_text(encoding="utf-8")
        if hashlib.sha256(source.encode("utf-8")).hexdigest() != saved["source_hashes"][r["work_id"]]:
            raise RuntimeError("V7R2 source hash mismatch")
        if source[r["source_start"]:r["source_end"]] != row["text"]:
            raise RuntimeError("V7R2 authoritative source mismatch")
        if any(r["source_start"] < p["source_end"] and p["source_start"] < r["source_end"]
               for p in eval_spans.get(r["work_id"], [])):
            raise RuntimeError("V7R2 evaluation span overlap")
        view = NormalizedSourceView.build(row["text"], r["source_start"], r["source_hash"])
        if view.presentation_text != unit_entry["presentation_text"] or build_source_units(view) != unit_entry["units"]:
            raise RuntimeError("V7R2 presentation/unit drift")
        parsed = strict_json_v7r2(r["generator_raw"])
        if parsed is None:
            if r.get("status") != "FORMAT_FAILED" or r["candidate_ids"]:
                raise RuntimeError("V7R2 invalid JSON outcome drift")
            counts["invalid_json"] += 1
        else:
            if len(parsed["candidates"]) != len(r["candidate_ids"]):
                raise RuntimeError("V7R2 proposal IDs/schema count drift")
            if not parsed["candidates"]: counts["zero_candidate_passages"] += 1
            counts["raw_proposals"] += len(parsed["candidates"])
        ids.extend(r["candidate_ids"])
    if len(ids) != len(set(ids)):
        raise RuntimeError("V7R2 duplicate candidate ID")
    outcome_ids = [x["candidate_id"] for x in auto + rejected if x.get("candidate_id")]
    if sorted(ids) != sorted(outcome_ids):
        raise RuntimeError("V7R2 candidate outcome missing or duplicated")
    if counts["raw_proposals"] != generation["summary"].get("raw_proposals", 0):
        raise RuntimeError("V7R2 proposal count drift")
    if len(auto) != generation["summary"].get("AUTO_CHECKED", 0):
        raise RuntimeError("V7R2 accepted count drift")
    for c in auto:
        row = chunks[(c["work_id"], c["chunk_id"])]
        if c["review_status"] != "AUTO_CHECKED" or c["reviewer"] or c["review_date"]:
            raise RuntimeError("V7R2 human review was populated automatically")
        if c["positive_passage"] != row["text"] or c["source_hash"] != row["source_sha256"]:
            raise RuntimeError("V7R2 accepted positive source drift")
        if c["positive_passage"][c["evidence_start_in_passage"]:c["evidence_end_in_passage"]] != c["evidence_quote"]:
            raise RuntimeError("V7R2 authoritative evidence span drift")
        if c["positive_passage"][c["answer_authoritative_start"]:c["answer_authoritative_end"]] != c["short_answer"]:
            raise RuntimeError("V7R2 authoritative answer span drift")
        if not set(c["semantic_audit"]["supporting_unit_ids"]).issubset(c["evidence_unit_ids"]):
            raise RuntimeError("V7R2 judge escaped selected evidence")
    return {"passages": 50, "same_original_50_in_order": True,
            "source_hashes_valid": True, "unit_offset_hash_failures": 0,
            "test_leakage": 0, "evaluation_span_leakage": 0,
            "auto_checked": len(auto), "rejected_records": len(rejected), **dict(counts)}


if __name__ == "__main__": print(json.dumps(validate(), indent=2))
