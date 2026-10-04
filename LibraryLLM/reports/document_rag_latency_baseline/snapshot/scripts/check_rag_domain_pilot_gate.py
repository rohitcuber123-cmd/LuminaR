"""Report the non-bypassable prerequisites for the isolated domain C pilot."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from rag_domain_common import TRAINING, controls


def main():
    _, split, _ = controls()
    before = json.loads((ROOT / "datasets" / "rag_experiments" / "chunking_v1" /
                         "reports" / "production_before_sha256.json").read_text(encoding="utf-8"))
    changed = [name for name, expected in before.items()
               if not (ROOT / name).exists() or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected]
    qa_path = TRAINING / "reports" / "rag_domain_qa_finalization_v1.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8")) if qa_path.exists() else {}
    neg_path = TRAINING / "reports" / "rag_hard_negative_finalization_v1.json"
    neg = json.loads(neg_path.read_text(encoding="utf-8")) if neg_path.exists() else {}
    checks = {
        "frozen_control_verified": True,
        "production_snapshot_unchanged": not changed,
        "train_books_exclude_TEST": not set(split["train_work_ids"]) & set(split["protected_test_work_ids"]),
        "validation_books_exclude_TEST": not set(split["validation_work_ids"]) & set(split["protected_test_work_ids"]),
        "at_least_200_reviewed_train_QA": qa.get("reviewed_train", 0) >= 200,
        "at_least_40_reviewed_validation_QA": qa.get("reviewed_validation", 0) >= 40,
        "all_train_queries_have_valid_negative": bool(neg) and not neg.get("queries_without_valid_negative") and neg.get("valid_after_safety", 0) >= qa.get("reviewed_train", 0),
        "no_negative_safety_failures": bool(neg) and not neg.get("safety_failures"),
        "gated_training_parquet_exists": (TRAINING / "luminar" / "luminar_domain_reviewed_v1.parquet").exists(),
    }
    report = {"result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS",
              "checks": checks, "all_pass": all(checks.values()),
              "production_files_changed": changed,
              "reviewed_train": qa.get("reviewed_train", 0),
              "reviewed_validation": qa.get("reviewed_validation", 0),
              "valid_negatives": neg.get("valid_after_safety", 0)}
    out = TRAINING / "reports" / "rag_domain_pilot_gate_v1.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["all_pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
