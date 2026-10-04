"""Aggregate bounded v2 pilot outcomes without admitting training examples."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json

from rag_domain_common import TRAINING, controls


def read(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v2")
    args = ap.parse_args()
    if args.version != "v2": raise ValueError("Only v2 audit supported")
    controls()
    base = TRAINING / "luminar"
    attempts = read(base / "domain_qa_attempts_v2.jsonl")
    candidates = read(base / "domain_qa_candidates_v2.jsonl")
    if not attempts: raise RuntimeError("No v2 attempts to audit")
    if len(attempts) > 50: raise RuntimeError("v2 attempt count exceeds bounded pilot")
    rejected_path = base / "domain_qa_rejected_v2.jsonl"
    rejected = {x["candidate_id"]: x for x in read(rejected_path)}
    for item in attempts:
        if item["stage"] in {"PROPOSITION_REJECTED", "QUESTION_REJECTED"} and item["candidate_id"] not in rejected:
            rejected[item["candidate_id"]] = {k: item.get(k) for k in
                ("candidate_id", "stage", "rejection_codes", "short_reason", "generator_output",
                 "question_generator_output", "chunk_id", "work_id")}
    rejected_path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rejected.values()) + "\n",
                             encoding="utf-8")
    states = Counter(x["stage"] for x in attempts)
    validation_path = TRAINING / "reports" / "rag_domain_qa_validation_v2.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.exists() else {}
    rechecked = {x["candidate_id"]: x["rejection_codes"] for x in validation.get("items", [])}
    reasons = Counter(code for x in attempts for code in
                      rechecked.get(x["candidate_id"], x.get("rejection_codes", [])))
    category = defaultdict(Counter)
    for item in attempts:
        category[item["generator_category"]]["attempts"] += 1
        category[item["generator_category"]][item["stage"]] += 1
    difficulties = Counter(x["difficulty"] for x in candidates)
    auto = [x for x in candidates if x["review_status"] == "AUTO_VALIDATED"]
    distribution = Counter(x["category"] for x in auto)
    wrong = [x["candidate_id"] for x in candidates if x.get("auto_validation", {}).get("passed") !=
             (x["review_status"] == "AUTO_VALIDATED")]
    generation_path = TRAINING / "reports" / "rag_domain_qa_generation_audit_v2.json"
    generation = json.loads(generation_path.read_text(encoding="utf-8")) if generation_path.exists() else {}
    report = {"result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS",
              "model": generation.get("model"), "seed": generation.get("seed"),
              "generation_summary": generation.get("summary", {}),
              "attempts": len(attempts), "states": dict(states), "candidate_records": len(candidates),
              "auto_validated": len(auto), "rejection_reasons": dict(reasons),
              "category_success": {k: dict(v) for k, v in category.items()},
              "auto_category_distribution": dict(distribution), "generated_difficulty_distribution": dict(difficulties),
              "duplicate_rejections": reasons["NEAR_DUPLICATE"],
              "eval_leakage_rejections": reasons["EVAL_QUERY_SIMILARITY"],
              "test_leakage_rejections": reasons["TEST_LEAKAGE"],
              "validation_state_inconsistencies": wrong,
              "human_review": "NOT YET COMPLETE", "training_gate": "CLOSED"}
    out = generation_path
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# LuminaR proposition-first QA generation audit", "",
             "**EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS**", "",
             f"Attempts: {len(attempts)}; candidates with generated questions: {len(candidates)}; "
             f"AUTO_VALIDATED: {len(auto)}; human review: NOT YET COMPLETE.", "",
             "## States", ""]
    lines += [f"- {k}: {v}" for k, v in sorted(states.items())]
    lines += ["", "## Rejection reasons", ""]
    lines += [f"- {k}: {v}" for k, v in sorted(reasons.items())]
    lines += ["", "## Categories", ""]
    lines += [f"- {k}: {dict(v)}" for k, v in sorted(category.items())]
    lines += ["", "No reviewed training examples were created. No training was run.", ""]
    (TRAINING / "reports" / "rag_domain_qa_generation_audit_v2.md").write_text(
        "\n".join(lines), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("attempts", "states", "auto_validated", "rejection_reasons")}, indent=2))


if __name__ == "__main__": main()
