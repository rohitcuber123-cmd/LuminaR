"""Fail-closed book split and evaluation-span exclusion plan for domain QA."""
from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq

from prepare_rag_finetuning_data import freeze_control

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "datasets" / "training"
LABELS = ROOT / "rag" / "evaluation" / "rag_retrieval_eval_v1.json"
CHUNKS = ROOT / "datasets" / "rag_experiments" / "chunking_v1" / "tokens_220" / "chunks.parquet"


def overlaps(row, passage):
    return row["source_start_char"] < passage["source_end"] and passage["source_start"] < row["source_end_char"]


def audit():
    control = freeze_control()
    questions = json.loads(LABELS.read_text(encoding="utf-8"))["questions"]
    test = {q["work_id"] for q in questions if q["split"] == "TEST"}
    dev = {q["work_id"] for q in questions if q["split"] == "DEV"}
    books = set(control["source_hashes"])
    if test & dev or not test <= books:
        raise RuntimeError("Evaluation book splits invalid")
    # Two books unused by evaluation become validation; all remaining non-TEST works train.
    unused = sorted(books - test - dev)
    if len(unused) < 2:
        raise RuntimeError("No book-disjoint validation source")
    validation = set(unused[:2])
    train = books - test - validation
    if train & test or validation & test or train & validation:
        raise RuntimeError("Book leakage in split")
    accepted = {}
    for q in questions:
        accepted.setdefault(q["work_id"], []).extend(p for p in q["accepted_passages"] if p["relevance_grade"] == 2)
    rows = pq.read_table(CHUNKS, columns=["chunk_id", "work_id", "source_start_char",
                                          "source_end_char", "source_sha256", "token_count"]).to_pylist()
    eligible = []
    rejected = {"protected_test_book": 0, "evaluation_span_overlap": 0, "invalid_source_hash": 0,
                "short_or_long_passage": 0}
    for row in rows:
        wid = row["work_id"]
        if wid in test:
            rejected["protected_test_book"] += 1
        elif row["source_sha256"] != control["source_hashes"][wid]:
            rejected["invalid_source_hash"] += 1
        elif row["token_count"] < 25 or row["token_count"] > 220:
            rejected["short_or_long_passage"] += 1
        elif any(overlaps(row, p) for p in accepted.get(wid, [])):
            rejected["evaluation_span_overlap"] += 1
        else:
            eligible.append({"chunk_id": row["chunk_id"], "work_id": wid,
                             "split": "VALIDATION" if wid in validation else "TRAIN"})
    if any(r["work_id"] in test for r in eligible):
        raise RuntimeError("TEST chunk leaked into domain pool")
    report = {"result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS",
              "train_work_ids": sorted(train), "validation_work_ids": sorted(validation),
              "protected_test_work_ids": sorted(test),
              "train_source_hashes": {wid: control["source_hashes"][wid] for wid in sorted(train)},
              "validation_source_hashes": {wid: control["source_hashes"][wid] for wid in sorted(validation)},
              "protected_test_source_hashes": {wid: control["source_hashes"][wid] for wid in sorted(test)},
              "eligible_train_chunks": sum(r["split"] == "TRAIN" for r in eligible),
              "eligible_validation_chunks": sum(r["split"] == "VALIDATION" for r in eligible),
              "rejected": rejected,
              "training_examples_generated": 0,
              "hard_negatives_generated": 0,
              "domain_training_gate": "BLOCKED_UNTIL_SOURCE_GROUNDED_QA_AND_FALSE_NEGATIVE_REVIEW"}
    out = TRAIN / "reports" / "rag_training_decontamination_v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("train_work_ids", "validation_work_ids", "protected_test_work_ids",
                                               "eligible_train_chunks", "eligible_validation_chunks", "rejected")}, indent=2))
    return report


if __name__ == "__main__":
    audit()
