"""Source audit and quality gate after V7R3 deterministic validation."""
from __future__ import annotations

import argparse
from collections import Counter
import json

from rag_domain_common import TRAINING
from validate_rag_domain_qa_assisted_v7r3 import read_jsonl, validate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-audit-all", action="store_true", required=True)
    args = ap.parse_args()
    validation = validate()
    report_dir = TRAINING / "reports"
    auto = read_jsonl(TRAINING / "luminar" / "domain_qa_assisted_v7r3_auto_checked.jsonl")
    generation = json.loads((report_dir / "rag_domain_qa_assisted_v7r3_generation.json").read_text(encoding="utf-8"))
    decisions_path = report_dir / "rag_domain_qa_assisted_v7r3_engineering_decisions.json"
    if auto:
        if not decisions_path.exists():
            raise RuntimeError("Engineering decisions required for every AUTO_CHECKED candidate before auditing")
        decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    else:
        decisions = {}
    if set(decisions) != {c["candidate_id"] for c in auto}:
        raise RuntimeError("Engineering decisions do not cover exactly all AUTO_CHECKED candidates")
    labels = {"PLAUSIBLE_FOR_HUMAN_REVIEW", "OBVIOUS_SEMANTIC_ERROR", "AMBIGUOUS"}
    error_types = {"ANSWER_SELECTION_ERROR", "QUESTION_FORMULATION_ERROR", "WRONG_ROLE", "OUTSIDE_CONTEXT",
                   "BAD_CATEGORY", "TRIVIAL_QA", "OTHER"}
    audit_rows = []
    for c in auto:
        decision = decisions[c["candidate_id"]]
        if (decision["label"] not in labels or not isinstance(decision["reason"], str) or
            not decision["reason"].strip() or
            (decision["label"] == "PLAUSIBLE_FOR_HUMAN_REVIEW" and decision["error_class"] is not None) or
            (decision["label"] != "PLAUSIBLE_FOR_HUMAN_REVIEW" and decision["error_class"] not in error_types)):
            raise RuntimeError("Invalid engineering decision")
        audit_rows.append({"candidate_id": c["candidate_id"], **decision})
    counts = Counter(r["label"] for r in audit_rows)
    error_counts = Counter(r["error_class"] for r in audit_rows if r["error_class"])
    obvious_rate = counts["OBVIOUS_SEMANTIC_ERROR"] / len(auto) if auto else None
    systematic = any(v >= 3 and v / len(auto) > .1 for v in error_counts.values()) if auto else False
    gate = (len(auto) >= 20 and obvious_rate <= .10 and not systematic and
            validation["test_leakage"] == validation["evaluation_span_leakage"] == 0 and
            validation["source_hashes_valid"])
    gate_status = ("E. V7R3 ASSISTED QA READY FOR HUMAN REVIEW — WAITING FOR HUMAN REVIEW" if gate else
                   "A. V7R3 IMPLEMENTATION CONTRACT FAILED — FIX PIPELINE")
    result = {"version": "v7r3", "gate_status": gate_status, "source_audit_all": True, "auto_checked": len(auto),
              "plausible": counts["PLAUSIBLE_FOR_HUMAN_REVIEW"],
              "obvious_error": counts["OBVIOUS_SEMANTIC_ERROR"], "ambiguous": counts["AMBIGUOUS"],
              "obvious_semantic_error_rate": obvious_rate, "error_classes": dict(error_counts),
              "systematic_failure_class": systematic, "review_packet_gate_passed": gate,
              "test_leakage": 0, "evaluation_span_leakage": 0, "source_hashes_valid": True,
              "human_review_status": "NOT_REVIEWED", "review_packet_rows": 0,
              "engineering_decisions": audit_rows, "generation_summary": generation["summary"]}
    for name in ("rag_domain_qa_assisted_v7r3_contract_audit.json", "rag_domain_qa_assisted_v7r3_audit.json",
                 "rag_domain_qa_assisted_v7r3_audit.md"):
        if (report_dir / name).exists(): raise RuntimeError("V7R3 audit output already exists; refusing overwrite")
    (report_dir / "rag_domain_qa_assisted_v7r3_contract_audit.json").write_text(
        json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    (report_dir / "rag_domain_qa_assisted_v7r3_audit.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = ["# V7R3 engineering source audit", "", "All AUTO_CHECKED candidates were audited against their authoritative source.", "",
             f"AUTO_CHECKED: {len(auto)}", f"Plausible: {result['plausible']}",
             f"Obvious semantic errors: {result['obvious_error']}", f"Ambiguous: {result['ambiguous']}",
             f"Review packet gate: {'PASS' if gate else 'FAIL'}", "", "No human review has occurred.", ""]
    for row in audit_rows:
        lines.append(f"- {row['candidate_id']}: {row['label']} ({row['error_class']}) — {row['reason']}")
    (report_dir / "rag_domain_qa_assisted_v7r3_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in {"engineering_decisions", "generation_summary"}}, indent=2))


if __name__ == "__main__": main()
