"""Fail-closed validation of V7R1 rerun artifacts and frozen source set."""
from __future__ import annotations

from collections import Counter
import hashlib
import json

import pyarrow.parquet as pq

from rag_domain_common import CONTROL, ROOT, SOURCE_MAP, TRAINING, controls
from rag_domain_qa_assisted_v7 import strict_json
from rag_domain_qa_assisted_v7r1 import evidence_diagnostics


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def validate():
    saved, split, labels = controls()
    manifest_path = TRAINING / "manifests" / "rag_domain_qa_v7r1_original_passages.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))["passages"]
    original = read_jsonl(TRAINING / "luminar" / "domain_qa_assisted_v7_raw.jsonl")
    raw = read_jsonl(TRAINING / "luminar" / "domain_qa_assisted_v7r1_raw.jsonl")
    auto = read_jsonl(TRAINING / "luminar" / "domain_qa_assisted_v7r1_auto_checked.jsonl")
    rejected = read_jsonl(TRAINING / "luminar" / "domain_qa_assisted_v7r1_rejected.jsonl")
    generation = json.loads((TRAINING / "reports" / "rag_domain_qa_assisted_v7r1_generation.json").read_text(encoding="utf-8"))
    if len(original) != len(manifest) or len(raw) != len(manifest) or len(raw) != 50:
        raise RuntimeError("V7/V7R1 passage count mismatch")
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != generation["source_manifest_sha256"]:
        raise RuntimeError("V7R1 manifest hash mismatch")
    chunks = {(r["work_id"], r["chunk_id"]): r for r in pq.read_table(CONTROL / "chunks.parquet").to_pylist()}
    source_map = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    eval_spans = {}
    for q in labels:
        eval_spans.setdefault(q["work_id"], []).extend(p for p in q["accepted_passages"] if p["relevance_grade"] == 2)
    raw_ids = []
    diagnostics = Counter()
    for i, (old, entry, r) in enumerate(zip(original, manifest, raw), 1):
        key = (entry["work_id"], entry["chunk_id"])
        if (old["work_id"], old["chunk_id"], old["source_start"], old["source_end"]) != (
                *key, entry["source_start"], entry["source_end"]):
            raise RuntimeError("Original passage set/order drift")
        if (r["passage_index"], r["work_id"], r["chunk_id"], r["source_start"], r["source_end"], r["source_hash"]) != (
                i, *key, entry["source_start"], entry["source_end"], entry["source_hash"]):
            raise RuntimeError("V7R1 passage set/order drift")
        if r["work_id"] not in split["train_work_ids"] or r["work_id"] in split["protected_test_work_ids"]:
            raise RuntimeError("V7R1 TEST/non-TRAIN source")
        chunk = chunks[key]
        source = (ROOT / source_map[r["work_id"]]["source_file"]).read_text(encoding="utf-8")
        if hashlib.sha256(source.encode()).hexdigest() != saved["source_hashes"][r["work_id"]]:
            raise RuntimeError("V7R1 source hash mismatch")
        if source[r["source_start"]:r["source_end"]] != chunk["text"]:
            raise RuntimeError("V7R1 source mapping mismatch")
        if any(r["source_start"] < p["source_end"] and p["source_start"] < r["source_end"]
               for p in eval_spans.get(r["work_id"], [])):
            raise RuntimeError("V7R1 evaluation span leakage")
        parsed = strict_json(r["generator_raw"])
        if parsed is None:
            if r.get("status") != "FORMAT_FAILED" or r["candidate_ids"]:
                raise RuntimeError("Invalid JSON not recorded as FORMAT_FAILED")
            diagnostics["format_failures"] += 1
        else:
            if len(parsed["candidates"]) != len(r["candidate_ids"]) or len(parsed["candidates"]) > 2:
                raise RuntimeError("V7R1 candidate cap/IDs invalid")
            if not parsed["candidates"]: diagnostics["zero_candidate_passages"] += 1
            if len(r["candidate_diagnostics"]) != len(parsed["candidates"]):
                raise RuntimeError("V7R1 missing evidence diagnostics")
            for c, d in zip(parsed["candidates"], r["candidate_diagnostics"]):
                expected = evidence_diagnostics(chunk["text"], c["evidence_quote"], c["short_answer"])
                if any(d[k] != v for k, v in expected.items()):
                    raise RuntimeError("V7R1 evidence diagnostics drift")
                diagnostics["raw_generated_QA"] += 1
        raw_ids.extend(r["candidate_ids"])
    if len(raw_ids) != len(set(raw_ids)):
        raise RuntimeError("V7R1 duplicate candidate IDs")
    found_ids = [r["candidate_id"] for r in auto + rejected if r.get("candidate_id")]
    if sorted(raw_ids) != sorted(found_ids):
        raise RuntimeError("V7R1 missing or extra candidate outcome")
    if len(auto) != generation["summary"].get("AUTO_CHECKED", 0):
        raise RuntimeError("V7R1 AUTO_CHECKED count drift")
    for c in auto:
        if c["review_status"] != "AUTO_CHECKED" or c["reviewer"] or c["review_date"]:
            raise RuntimeError("V7R1 human-review status unexpectedly populated")
        if c["evidence_exact_match_count"] != 1 or c["answer_exact_match_count_in_evidence"] < 1:
            raise RuntimeError("V7R1 accepted non-exact evidence or answer")
        if c["positive_passage"][c["evidence_start_in_passage"]:c["evidence_end_in_passage"]] != c["evidence_quote"]:
            raise RuntimeError("V7R1 accepted evidence offset drift")
    return {"passages": 50, "same_original_50_in_order": True, "raw_generated_QA": len(raw_ids),
            "auto_checked": len(auto), "rejected_records": len(rejected),
            "test_leakage": 0, "evaluation_span_leakage": 0,
            "source_hashes_valid": True, **dict(diagnostics)}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
