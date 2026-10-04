"""Freeze history and audit reversible source units on the same 50 passages."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq

from rag_domain_common import CONTROL, ROOT, SOURCE_MAP, TRAINING, controls
from rag_domain_qa_source_units_v7r2 import (SEGMENTATION_VERSION,
                                              NormalizedSourceView, build_source_units)

V7R1_FILES = [
    "datasets/training/luminar/domain_qa_assisted_v7r1_raw.jsonl",
    "datasets/training/luminar/domain_qa_assisted_v7r1_auto_checked.jsonl",
    "datasets/training/luminar/domain_qa_assisted_v7r1_rejected.jsonl",
    "datasets/training/reports/rag_domain_qa_assisted_v7r1_generation.json",
    "datasets/training/reports/rag_domain_qa_assisted_v7r1_audit.json",
    "datasets/training/reports/rag_domain_qa_assisted_v7r1_audit.md",
    "datasets/training/reports/rag_domain_qa_v7_vs_v7r1.json",
    "datasets/training/reports/rag_domain_qa_v7_vs_v7r1.md",
    "datasets/training/manifests/rag_domain_qa_v7r1_original_passages.json",
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    args = ap.parse_args()
    manifest_path = args.manifest.resolve()
    expected_path = (TRAINING / "manifests" / "rag_domain_qa_v7r1_original_passages.json").resolve()
    if manifest_path != expected_path:
        raise RuntimeError("V7R2 must use the saved original V7/V7R1 50-passage manifest")
    saved, split, labels = controls()
    frozen = {name: sha(ROOT / name) for name in V7R1_FILES}
    v7 = json.loads((TRAINING / "reports" / "rag_domain_qa_assisted_v7r1_contract_audit.json").read_text(encoding="utf-8"))
    if any(sha(ROOT / p) != h for p, h in v7["original_v7_frozen_sha256"].items()):
        raise RuntimeError("Original V7 artifact drifted")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if len(manifest["passages"]) != 50:
        raise RuntimeError("Original source manifest is not 50 passages")
    rows = {(r["work_id"], r["chunk_id"]): r for r in pq.read_table(CONTROL / "chunks.parquet").to_pylist()}
    source_map = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    eval_spans = {}
    for q in labels:
        eval_spans.setdefault(q["work_id"], []).extend(p for p in q["accepted_passages"] if p["relevance_grade"] == 2)
    all_passages = []
    counts = Counter()
    for original in manifest["passages"]:
        wid, cid = original["work_id"], original["chunk_id"]
        row = rows[(wid, cid)]
        if wid not in split["train_work_ids"] or wid in split["protected_test_work_ids"]:
            raise RuntimeError("V7R2 source set contains non-TRAIN work")
        source = (ROOT / source_map[wid]["source_file"]).read_text(encoding="utf-8")
        source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if source_hash != original["source_hash"] or source_hash != saved["source_hashes"][wid]:
            raise RuntimeError("V7R2 source hash mismatch")
        start, end = original["source_start"], original["source_end"]
        if (start, end) != (row["source_start_char"], row["source_end_char"]):
            raise RuntimeError("V7R2 source range mismatch")
        if source[start:end] != row["text"]:
            raise RuntimeError("V7R2 source text mismatch")
        if any(start < p["source_end"] and p["source_start"] < end for p in eval_spans.get(wid, [])):
            raise RuntimeError("V7R2 evaluation span leakage")
        view = NormalizedSourceView.build(row["text"], start, source_hash)
        units = build_source_units(view)
        if units != build_source_units(view):
            raise RuntimeError("V7R2 unit IDs are nondeterministic")
        for unit in units:
            a, b = unit["authoritative_start_in_passage"], unit["authoritative_end_in_passage"]
            p, q = unit["presentation_start"], unit["presentation_end"]
            if (unit["authoritative_text"] != row["text"][a:b] or
                    unit["presentation_text"] != view.presentation_text[p:q] or
                    unit["absolute_source_start"] != start + a or
                    unit["absolute_source_end"] != start + b or unit["source_hash"] != source_hash):
                raise RuntimeError("V7R2 unit offset/hash integrity failed")
            counts["source_units"] += 1
            if len(unit["presentation_text"]) > 650: counts["long_unsplit_units"] += 1
        counts["passages"] += 1
        all_passages.append({"passage_index": original["passage_index"], "work_id": wid,
                             "chunk_id": cid, "source_start": start, "source_end": end,
                             "source_hash": source_hash, "segmentation_version": SEGMENTATION_VERSION,
                             "presentation_text": view.presentation_text,
                             "presentation_to_authoritative_map": view.presentation_to_authoritative_map,
                             "units": units})
    units_path = TRAINING / "manifests" / "rag_domain_qa_v7r2_source_units.json"
    contract_path = TRAINING / "reports" / "rag_domain_qa_assisted_v7r2_contract_audit.json"
    if units_path.exists() or contract_path.exists():
        raise RuntimeError("V7R2 unit/contract audit already exists; refusing overwrite")
    units_path.write_text(json.dumps({"version": "v7r2", "source_manifest_sha256": sha(manifest_path),
                                      "segmentation_version": SEGMENTATION_VERSION,
                                      "passages": all_passages}, ensure_ascii=False) + "\n", encoding="utf-8")
    report = {"v7r1_frozen_sha256": frozen, "v7r0_frozen_sha256": v7["original_v7_frozen_sha256"],
              "same_original_50_passages": True, "source_manifest_sha256": sha(manifest_path),
              "source_units_manifest_sha256": sha(units_path),
              "segmentation_version": SEGMENTATION_VERSION,
              "presentation_design": "NFKC character clusters and whitespace runs map to exact authoritative spans; no fuzzy matching or modified training positive",
              "round_trip_passages": counts["passages"], "unit_offset_hash_failures": 0,
              "source_units": counts["source_units"],
              "long_unsplit_units": counts["long_unsplit_units"],
              "test_leakage": 0, "evaluation_span_leakage": 0}
    contract_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# V7R2 source presentation and unit contract", "",
             "V7R0 and V7R1 are frozen; hashes are in the JSON audit. The exact same 50 TRAIN passages are used.",
             f"{counts['passages']} presentation views round-trip; {counts['source_units']} deterministic units passed authoritative offset and source-hash checks.",
             f"Long unsplit units: {counts['long_unsplit_units']}.",
             "Presentation normalization collapses whitespace and applies NFKC with a per-character source map. Source text and the training positive are unchanged.",
             "Each source unit has stable S-IDs and exact authoritative/presentation spans. Evidence may reference one or two adjacent units.",
             "TEST leakage 0; accepted evaluation-span leakage 0.", ""]
    (TRAINING / "reports" / "rag_domain_qa_assisted_v7r2_contract_audit.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"passages": counts["passages"], "source_units": counts["source_units"],
                      "long_unsplit_units": counts["long_unsplit_units"]}, indent=2))


if __name__ == "__main__": main()
