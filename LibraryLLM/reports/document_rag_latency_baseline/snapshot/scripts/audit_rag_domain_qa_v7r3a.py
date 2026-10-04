"""Read-only V7R3A replay of the 19 saved deterministic QA passes."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json

from rag_domain_common import ROOT, TRAINING
from rag_domain_qa_contract_v7r3a import contract_replay, judge_bucket, readiness
from validate_rag_domain_qa_assisted_v7r3 import read_jsonl, validate

FROZEN = [
    "luminar/domain_qa_assisted_v7r3_stage_a_raw.jsonl",
    "luminar/domain_qa_assisted_v7r3_stage_a_valid.jsonl",
    "luminar/domain_qa_assisted_v7r3_raw.jsonl",
    "luminar/domain_qa_assisted_v7r3_auto_checked.jsonl",
    "luminar/domain_qa_assisted_v7r3_rejected.jsonl",
    "manifests/rag_domain_qa_v7r3_word_units.json",
    "reports/rag_domain_qa_assisted_v7r3_generation.json",
    "reports/rag_domain_qa_assisted_v7r3_contract_audit.json",
    "reports/rag_domain_qa_assisted_v7r3_audit.json",
    "reports/rag_domain_qa_assisted_v7r3_audit.md",
    "reports/rag_domain_qa_assisted_v7r3_engineering_decisions.json",
    "reports/rag_domain_qa_v7_all_versions_comparison.json",
    "reports/rag_domain_qa_v7_all_versions_comparison.md",
]
LABELS = {"PLAUSIBLE_FOR_HUMAN_REVIEW", "OBVIOUS_SEMANTIC_ERROR", "AMBIGUOUS"}
ERRORS = {"ANSWER_SELECTION_ERROR", "QUESTION_FORMULATION_ERROR", "WRONG_SEMANTIC_ROLE", "BAD_CATEGORY",
          "ANSWER_TYPE_ERROR", "UNRESOLVED_REFERENCE", "OUTSIDE_CONTEXT", "TRIVIAL_QA", "BAD_SOURCE_UNIT", "OTHER"}


def load_saved():
    base = TRAINING / "luminar"
    auto = read_jsonl(base / "domain_qa_assisted_v7r3_auto_checked.jsonl")
    rejected = read_jsonl(base / "domain_qa_assisted_v7r3_rejected.jsonl")
    records = sorted((r for r in auto + rejected if r.get("semantic_audit")), key=lambda r: r["candidate_id"])
    generation = json.loads((TRAINING / "reports" / "rag_domain_qa_assisted_v7r3_generation.json").read_text(encoding="utf-8"))
    if len(records) != generation["summary"]["deterministic_passes"] or len(records) != 19:
        raise RuntimeError("Saved deterministic pass count differs from frozen V7R3 result")
    if len({r["candidate_id"] for r in records}) != len(records):
        raise RuntimeError("Duplicate deterministic candidate ID")
    return records


def run():
    paths = [TRAINING / p for p in FROZEN]
    if any(not p.exists() for p in paths): raise RuntimeError("Missing frozen V7R3 artifact")
    frozen_hashes = {name: hashlib.sha256((TRAINING / name).read_bytes()).hexdigest() for name in FROZEN}
    validation = validate()
    records = load_saved()
    decisions_path = TRAINING / "reports" / "rag_domain_qa_v7r3a_engineering_decisions.json"
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    if set(decisions) != {r["candidate_id"] for r in records}:
        raise RuntimeError("Engineering audit must cover exactly all 19 passes")
    results = []
    for record in records:
        cid = record["candidate_id"]
        decision = decisions[cid]
        if (decision.get("label") not in LABELS or not isinstance(decision.get("reason"), str) or
            not decision["reason"].strip() or
            (decision.get("error_type") is not None and decision["error_type"] not in ERRORS) or
            (decision["label"] == "PLAUSIBLE_FOR_HUMAN_REVIEW") != (decision.get("error_type") is None)):
            raise RuntimeError(f"Invalid engineering decision: {cid}")
        # Every saved pass must still point into its authoritative positive source.
        passage = record["positive_passage"]
        if (passage[record["answer_authoritative_start"]:record["answer_authoritative_end"]] != record["short_answer"] or
            passage[record["evidence_start_in_passage"]:record["evidence_end_in_passage"]] != record["evidence_quote"]):
            raise RuntimeError(f"Source span drift: {cid}")
        contract = contract_replay(record)
        state = readiness(contract, decision["label"], source_valid=True, leakage_free=True)
        judge = record["semantic_audit"]
        bucket = judge_bucket(judge)
        ids_valid = None if bucket == "INVALID_JSON" else bool(
            set(judge.get("supporting_unit_ids", [])) <= set(record["evidence_unit_ids"]))
        if bucket == "INVALID_SUPPORT_REFERENCE": ids_valid = False
        reason = judge.get("reason") or judge.get("failure_code")
        if not reason:
            reason = f"outside_context={judge.get('outside_context')}; wrong_role={judge.get('wrong_role')}"
        statuses = ["DETERMINISTIC_PASS", state["engineering_status"],
                    "JUDGE_SUPPORTED" if bucket == "SUPPORTED" else "JUDGE_UNCERTAIN"]
        if state["ready_for_human_review"]: statuses.append("READY_FOR_HUMAN_REVIEW")
        results.append({"candidate_id": cid, "question": record["question"], "answer": record["short_answer"],
                        "authoritative_evidence": record["evidence_quote"], "engineering_audit": decision,
                        "contract": contract, "judge": {"bucket": bucket, "label": judge["label"],
                        "reason": reason, "format_valid": bucket != "INVALID_JSON",
                        "supporting_ids_valid": ids_valid, "supporting_unit_ids": judge.get("supporting_unit_ids", [])},
                        "statuses": statuses, **state})
    labels = Counter(r["engineering_audit"]["label"] for r in results)
    errors = Counter(r["engineering_audit"]["error_type"] for r in results if r["engineering_audit"]["error_type"])
    judge_by_engineering = defaultdict(Counter)
    for row in results:
        judge_by_engineering[row["engineering_audit"]["label"]][row["judge"]["bucket"]] += 1
    ready = [r for r in results if r["ready_for_human_review"]]
    contract_valid = [r for r in results if r["contract"]["contract_pass"]]
    category_only = [r for r in results if r["engineering_audit"]["label"] == "PLAUSIBLE_FOR_HUMAN_REVIEW"
                     and r["contract"]["category_changed"] and r["contract"]["contract_pass"]]
    result = {"version": "v7r3a", "read_only_saved_generation": True, "frozen_v7r3_sha256": frozen_hashes,
              "v7r3_validation": validation, "deterministic_passes": len(results),
              "engineering_audit_counts": dict(labels), "engineering_error_types": dict(errors),
              "other_explicit_failures": sum("OTHER_EXPLICIT_NEEDS_REVIEW" in r["contract"]["contract_reasons"] for r in results),
              "mixed_semantic_answer_failures": sum("MIXED_SEMANTIC_ANSWER_SPAN" in r["contract"]["contract_reasons"] for r in results),
              "corrected_category_candidates": sum(r["contract"]["category_changed"] for r in results),
              "category_only_repaired_candidates": [r["candidate_id"] for r in category_only],
              "contract_valid_count": len(contract_valid), "contract_valid_ids": [r["candidate_id"] for r in contract_valid],
              "judge_buckets_among_contract_valid": dict(Counter(r["judge"]["bucket"] for r in contract_valid)),
              "ready_for_human_review_count": len(ready), "ready_for_human_review_ids": [r["candidate_id"] for r in ready],
              "pilot_threshold": 10, "pilot_gate_passed": len(ready) >= 10,
              "current_gate": ("A. SAVED V7R3 OUTPUT IS GOOD ENOUGH FOR A HUMAN REVIEW PILOT — WAITING FOR HUMAN REVIEW"
                               if len(ready) >= 10 else
                               "B. QWEN-3B AUTONOMOUS QA AUTHORING IS TOO WEAK — SWITCH TO HUMAN-FIRST / QWEN-ASSISTED AUTHORING"),
              "review_packet_rows": 0, "human_review_status": "NOT_REVIEWED",
              "test_leakage": validation["test_leakage"], "evaluation_leakage": validation["evaluation_span_leakage"],
              "production_snapshot_files": validation["production_snapshot_files"],
              "production_snapshot_changed": validation["production_snapshot_changed"], "rows": results}
    judge_report = {"version": "v7r3a", "same_model_generator_judge": True,
                    "deterministic_passes": len(results),
                    "judge_buckets": dict(Counter(r["judge"]["bucket"] for r in results)),
                    "by_engineering_audit": {k: dict(v) for k, v in judge_by_engineering.items()},
                    "plausible_false_rejections": sum(r["engineering_audit"]["label"] == "PLAUSIBLE_FOR_HUMAN_REVIEW"
                                                      and r["judge"]["bucket"] != "SUPPORTED" for r in results),
                    "bad_supported": sum(r["engineering_audit"]["label"] == "OBVIOUS_SEMANTIC_ERROR"
                                         and r["judge"]["bucket"] == "SUPPORTED" for r in results),
                    "judge_advisory_for_human_review": True,
                    "judge_not_training_authority": True,
                    "rows": [{"candidate_id": r["candidate_id"], "engineering": r["engineering_audit"]["label"],
                              "judge": r["judge"]} for r in results]}
    report_dir = TRAINING / "reports"
    outputs = [report_dir / n for n in ("rag_domain_qa_v7r3_contract_reaudit.json",
                                       "rag_domain_qa_v7r3_contract_reaudit.md",
                                       "rag_domain_qa_v7r3_judge_audit.json",
                                       "rag_domain_qa_v7r3_judge_audit.md")]
    if any(p.exists() for p in outputs): raise RuntimeError("V7R3A report exists; refusing overwrite")
    outputs[0].write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    outputs[2].write_text(json.dumps(judge_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    contract_lines = ["# V7R3A saved-contract reaudit", "",
                      "All 19 rows are saved V7R3 deterministic passes. No Stage A, Stage B or judge call was rerun.", "",
                      f"Engineering audit: {labels['PLAUSIBLE_FOR_HUMAN_REVIEW']} plausible, {labels['OBVIOUS_SEMANTIC_ERROR']} obvious errors, {labels['AMBIGUOUS']} ambiguous.",
                      f"Corrected contract passes: {len(contract_valid)}; ready for human review: {len(ready)}; pilot threshold: 10.",
                      f"OTHER_EXPLICIT unresolved: {result['other_explicit_failures']}; mixed semantic spans: {result['mixed_semantic_answer_failures']}.",
                      f"Category metadata changed for {result['corrected_category_candidates']} rows; category-only repair retained: {', '.join(result['category_only_repaired_candidates'])}.",
                      "", "| Candidate | Question | Answer | Engineering audit | Error type | Intent | Final answer type | Final category | Contract | Judge | Ready |",
                      "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        def cell(value): return str(value).replace("|", "\\|").replace("\n", " ")
        contract_lines.append("| " + " | ".join(cell(x) for x in (
            r["candidate_id"], r["question"], r["answer"], r["engineering_audit"]["label"],
            r["engineering_audit"]["error_type"] or "—", r["contract"]["question_intent"],
            r["contract"]["answer_type_final"] or "NEEDS_REVIEW", r["contract"]["category_final"],
            "PASS" if r["contract"]["contract_pass"] else ", ".join(r["contract"]["contract_reasons"]),
            r["judge"]["bucket"], "YES" if r["ready_for_human_review"] else "NO")) + " |")
    contract_lines += ["", "## Decision", "", "Fewer than 10 saved pairs qualify for a human pilot packet.",
                       "Stop autonomous QA iteration; move to human-first, Qwen-assisted source authoring.",
                       "No candidate is REVIEWED or eligible for training.", ""]
    outputs[1].write_text("\n".join(contract_lines), encoding="utf-8")
    judge_lines = ["# V7R3A same-model judge audit", "", "Judge status is diagnostic and separate from engineering source audit.", "",
                   f"Plausible false rejections: {judge_report['plausible_false_rejections']}; obvious errors marked SUPPORTED: {judge_report['bad_supported']}.",
                   "", "| Candidate | Engineering audit | Judge result | Judge reason | Format valid | Supporting IDs valid |",
                   "|---|---|---|---|---|---|"]
    for r in results:
        j = r["judge"]
        judge_lines.append("| " + " | ".join(str(x).replace("|", "\\|").replace("\n", " ") for x in (
            r["candidate_id"], r["engineering_audit"]["label"], j["bucket"], j["reason"],
            j["format_valid"], j["supporting_ids_valid"])) + " |")
    judge_lines += ["", "The same Qwen snapshot generated both stages and judged them. Judge support is not independent review.",
                    "Judge output is advisory for a future human packet; human decisions remain mandatory for training.", ""]
    outputs[3].write_text("\n".join(judge_lines), encoding="utf-8")
    print(json.dumps({"audited": len(results), "engineering": dict(labels), "contract_valid": len(contract_valid),
                      "ready_for_human_review": len(ready), "pilot_gate_passed": len(ready) >= 10,
                      "judge_by_engineering": judge_report["by_engineering_audit"]}, indent=2))


if __name__ == "__main__": run()
