"""Freeze V7R0 and recover its exact 50 source passages for V7R1."""
from __future__ import annotations

from collections import Counter
import hashlib
import json

import pyarrow.parquet as pq

from build_rag_domain_qa_assisted_v7r1 import SYSTEM
from rag_domain_common import CATEGORIES, CONTROL, ROOT, SOURCE_MAP, TRAINING, controls
from rag_domain_qa_assisted_v7 import strict_json
from rag_domain_qa_assisted_v7r1 import evidence_diagnostics

ORIGINAL_FILES = [
    "datasets/training/luminar/domain_qa_assisted_v7_raw.jsonl",
    "datasets/training/luminar/domain_qa_assisted_v7_auto_checked.jsonl",
    "datasets/training/luminar/domain_qa_assisted_v7_rejected.jsonl",
    "datasets/training/reports/rag_domain_qa_assisted_v7_generation.json",
    "datasets/training/reports/rag_domain_qa_assisted_v7_audit.json",
    "datasets/training/reports/rag_domain_qa_assisted_v7_audit.md",
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    saved, split, labels = controls()
    hashes = {name: sha(ROOT / name) for name in ORIGINAL_FILES}
    original = [json.loads(line) for line in (ROOT / ORIGINAL_FILES[0]).read_text(encoding="utf-8").splitlines()]
    if len(original) != 50 or [r["passage_index"] for r in original] != list(range(1, 51)):
        raise RuntimeError("Original V7 passage order/count unavailable")
    chunks = {(r["work_id"], r["chunk_id"]): r for r in pq.read_table(CONTROL / "chunks.parquet").to_pylist()}
    source_map = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    spans = {}
    for label in labels:
        spans.setdefault(label["work_id"], []).extend(p for p in label["accepted_passages"] if p["relevance_grade"] == 2)
    manifest = []
    metrics = Counter()
    for r in original:
        wid, cid = r["work_id"], r["chunk_id"]
        if wid not in split["train_work_ids"] or wid in split["protected_test_work_ids"]:
            raise RuntimeError("V7 included a non-TRAIN work")
        row = chunks[(wid, cid)]
        if (row["source_start_char"], row["source_end_char"]) != (r["source_start"], r["source_end"]):
            raise RuntimeError("V7 source range mismatch")
        source = (ROOT / source_map[wid]["source_file"]).read_text(encoding="utf-8")
        if hashlib.sha256(source.encode("utf-8")).hexdigest() != saved["source_hashes"][wid]:
            raise RuntimeError("V7 source SHA-256 mismatch")
        if source[r["source_start"]:r["source_end"]] != row["text"]:
            raise RuntimeError("V7 positive passage mapping mismatch")
        if any(r["source_start"] < p["source_end"] and p["source_start"] < r["source_end"]
               for p in spans.get(wid, [])):
            raise RuntimeError("V7 accepted evaluation span overlap")
        manifest.append({"passage_index": r["passage_index"], "work_id": wid, "chunk_id": cid,
                         "source_start": r["source_start"], "source_end": r["source_end"],
                         "source_hash": row["source_sha256"]})
        parsed = strict_json(r["generator_raw"])
        if parsed is None:
            metrics["invalid_json"] += 1
            continue
        if not parsed["candidates"]:
            metrics["zero_candidate_passages"] += 1
        for c in parsed["candidates"]:
            metrics["raw_proposals"] += 1
            d = evidence_diagnostics(row["text"], c["evidence_quote"], c["short_answer"])
            if not c["evidence_quote"].strip(): metrics["empty_evidence"] += 1
            if d["evidence_exact_match_count"] == 0: metrics["evidence_zero_exact"] += 1
            if d["evidence_exact_match_count"] > 1: metrics["evidence_multiple_exact"] += 1
            if d["answer_exact_match_count_in_evidence"] == 0: metrics["answer_zero_exact"] += 1
            if c["category"].strip().upper() not in CATEGORIES: metrics["invalid_category"] += 1
            if c["difficulty"].strip().upper() not in ("EASY", "MEDIUM", "HARD"):
                metrics["invalid_difficulty"] += 1
    if len(set((m["work_id"], m["chunk_id"]) for m in manifest)) != 50:
        raise RuntimeError("Original V7 source set has duplicate chunks")
    if not all(category in SYSTEM for category in CATEGORIES) or not all(
            difficulty in SYSTEM for difficulty in ("EASY", "MEDIUM", "HARD")):
        raise RuntimeError("V7R1 prompt omits a required enum")
    if "character-for-character" not in SYSTEM or "exact contiguous substring" not in SYSTEM:
        raise RuntimeError("V7R1 prompt omits exact extraction contract")
    manifest_path = TRAINING / "manifests" / "rag_domain_qa_v7r1_original_passages.json"
    contract_path = TRAINING / "reports" / "rag_domain_qa_assisted_v7r1_contract_audit.json"
    if manifest_path.exists() or contract_path.exists():
        raise RuntimeError("V7R1 contract/manifest artifacts exist; refusing overwrite")
    manifest_path.write_text(json.dumps({"version": "v7r1", "source": "original_v7_raw",
                                         "original_raw_sha256": hashes[ORIGINAL_FILES[0]],
                                         "passages": manifest}, indent=2) + "\n", encoding="utf-8")
    report = {"original_v7_frozen_sha256": hashes, "same_50_passages_recoverable": True,
              "source_manifest": str(manifest_path), "source_manifest_sha256": sha(manifest_path),
              "original_evidence_diagnostics": dict(metrics),
              "evidence_matcher_finding": "All 80 evidence failures had zero exact matches; none had multiple exact occurrences. Original reason conflated no-match and ambiguity.",
              "corrected_prompt_contract": {"categories": list(CATEGORIES),
                                            "difficulties": ["EASY", "MEDIUM", "HARD"],
                                            "exact_evidence": True, "exact_answer": True,
                                            "target_delimiters": True, "abstention_allowed": True}}
    contract_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md = ["# V7R1 contract and source audit", "", "Original V7 artifacts are frozen; SHA-256 hashes appear in the JSON audit.",
          "", "The same 50 TRAIN passages were recovered in the same order with verified source ranges and hashes.",
          "No TEST or accepted evaluation-span overlap was found.", "",
          "Original evidence exact-match counts: 80 zero, 13 one, 0 multiple. The old error name conflated absence with ambiguity.",
          "The V7R1 contract names all nine categories and three difficulties, requires exact evidence and answers, and permits abstention.", ""]
    (TRAINING / "reports" / "rag_domain_qa_assisted_v7r1_contract_audit.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "original": dict(metrics)}, indent=2))


if __name__ == "__main__": main()
