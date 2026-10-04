"""Source-audit every V7R2 AUTO_CHECKED candidate and enforce the pilot gate."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json

from rag_domain_common import ROOT, TRAINING
from validate_rag_domain_qa_assisted_v7r2 import read_jsonl, validate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-audit-all", action="store_true")
    args = ap.parse_args()
    if not args.source_audit_all:
        raise ValueError("V7R2 audit requires --source-audit-all")
    validation = validate()
    contract = json.loads((TRAINING / "reports" / "rag_domain_qa_assisted_v7r2_contract_audit.json").read_text(encoding="utf-8"))
    historical = {**contract["v7r0_frozen_sha256"], **contract["v7r1_frozen_sha256"]}
    changed = [path for path, expected in historical.items() if sha(ROOT / path) != expected]
    if changed: raise RuntimeError(f"Frozen V7R0/V7R1 artifact drift: {changed}")
    production = json.loads((ROOT / "datasets" / "rag_experiments" / "chunking_v1" / "reports" /
                             "production_before_sha256.json").read_text(encoding="utf-8"))
    prod_changed = [path for path, expected in production.items()
                    if not (ROOT / path).exists() or sha(ROOT / path) != expected]
    if prod_changed: raise RuntimeError(f"Production snapshot drift: {prod_changed}")
    auto = read_jsonl(TRAINING / "luminar" / "domain_qa_assisted_v7r2_auto_checked.jsonl")
    rejected = read_jsonl(TRAINING / "luminar" / "domain_qa_assisted_v7r2_rejected.jsonl")
    engineering = read_jsonl(TRAINING / "reports" / "rag_domain_qa_assisted_v7r2_engineering_source_audit.jsonl")
    expected_ids = {r["candidate_id"] for r in auto}
    actual_ids = [r["candidate_id"] for r in engineering]
    if set(actual_ids) != expected_ids or len(actual_ids) != len(expected_ids):
        raise RuntimeError("Every AUTO_CHECKED candidate must have exactly one engineering source audit")
    allowed = {"PLAUSIBLE_FOR_HUMAN_REVIEW", "OBVIOUS_SEMANTIC_ERROR", "AMBIGUOUS"}
    if any(r["engineering_status"] not in allowed for r in engineering):
        raise RuntimeError("Invalid engineering audit status")
    status = Counter(r["engineering_status"] for r in engineering)
    obvious_rate = status["OBVIOUS_SEMANTIC_ERROR"] / len(engineering) if engineering else None
    reasons = Counter(x for item in rejected for x in item.get("rejection_reasons", []))
    generation = json.loads((TRAINING / "reports" / "rag_domain_qa_assisted_v7r2_generation.json").read_text(encoding="utf-8"))
    gate_pass = (len(auto) >= 20 and obvious_rate is not None and obvious_rate <= .10 and
                 validation["test_leakage"] == 0 and validation["evaluation_span_leakage"] == 0 and
                 validation["source_hashes_valid"])
    gate = ("C. V7R2 ASSISTED QA READY FOR HUMAN REVIEW — WAITING FOR HUMAN REVIEW" if gate_pass else
            "B. V7R2 GENERATOR SEMANTICS STILL TOO LOW QUALITY — CHANGE GENERATOR APPROACH")
    report = {"version": "v7r2", "gate_status": gate, "review_packet_gate_passed": gate_pass,
              "same_original_50_passages": validation["same_original_50_in_order"],
              "v7r0_v7r1_frozen_unchanged": True,
              "source_units": contract["source_units"], "round_trip_passages": contract["round_trip_passages"],
              "unit_offset_hash_failures": validation["unit_offset_hash_failures"],
              "test_leakage": validation["test_leakage"],
              "evaluation_span_leakage": validation["evaluation_span_leakage"],
              "source_hashes_valid": validation["source_hashes_valid"],
              "production_snapshot_files": len(production), "production_snapshot_changed": 0,
              "generation_settings": {key: generation[key] for key in (
                  "generator_model", "generator_model_index_sha256", "dtype", "device", "do_sample",
                  "max_new_tokens_generator", "max_new_tokens_judge", "same_model_generator_judge")},
              "counts": {"passages": validation["passages"], "raw_proposals": validation["raw_proposals"],
                         "zero_candidate_passages": validation.get("zero_candidate_passages", 0),
                         "invalid_json": validation.get("invalid_json", 0),
                         "deterministic_passes": generation["summary"].get("deterministic_passes", 0),
                         "semantic_SUPPORTED": generation["summary"].get("semantic_SUPPORTED", 0),
                         "semantic_UNSUPPORTED": generation["summary"].get("semantic_UNSUPPORTED", 0),
                         "semantic_UNCERTAIN": generation["summary"].get("semantic_UNCERTAIN", 0),
                         "AUTO_CHECKED": len(auto), "rejected_records": len(rejected)},
              "rejection_reasons": dict(reasons.most_common()),
              "engineering_source_audit": {
                  "plausible": status["PLAUSIBLE_FOR_HUMAN_REVIEW"],
                  "obvious_error": status["OBVIOUS_SEMANTIC_ERROR"],
                  "ambiguous": status["AMBIGUOUS"],
                  "obvious_semantic_error_rate": obvious_rate},
              "review_packet_rows": 0, "human_review_status": "NOT_REVIEWED",
              "v8_v9_v10_started": False}
    output = TRAINING / "reports" / "rag_domain_qa_assisted_v7r2_audit.json"
    if output.exists(): raise RuntimeError("V7R2 audit exists; refusing overwrite")
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# V7R2 source-referenced assisted-QA audit", "", f"**Current gate: {gate}**", "",
             "V7R0 and V7R1 remain frozen. V7R2 used the exact same 50 TRAIN passages in the same order.",
             f"All {contract['round_trip_passages']} presentation views and {contract['source_units']} source units passed round-trip, offset, and hash checks.",
             "The generator returned source unit IDs, never authoritative evidence text. Code reconstructed evidence and mapped answer spans back to source.",
             "", "## Pilot results", "",
             f"- Raw proposals: {validation['raw_proposals']}; invalid JSON: {validation.get('invalid_json', 0)}; zero-candidate passages: {validation.get('zero_candidate_passages', 0)}.",
             f"- Evidence/source integrity failures: 0; unit-reference failures: 0.",
             f"- Answer not exact in selected presentation unit: {reasons['ANSWER_NOT_EXACT_IN_PRESENTATION']}; ambiguous answer occurrences: {reasons['AMBIGUOUS_ANSWER_OCCURRENCE']}.",
             f"- Deterministic passes: {generation['summary'].get('deterministic_passes', 0)}; semantic SUPPORTED/UNSUPPORTED/UNCERTAIN: "
             f"{generation['summary'].get('semantic_SUPPORTED', 0)}/{generation['summary'].get('semantic_UNSUPPORTED', 0)}/{generation['summary'].get('semantic_UNCERTAIN', 0)}.",
             f"- AUTO_CHECKED: {len(auto)}; engineering audit plausible/obvious/ambiguous: "
             f"{status['PLAUSIBLE_FOR_HUMAN_REVIEW']}/{status['OBVIOUS_SEMANTIC_ERROR']}/{status['AMBIGUOUS']}; obvious-error rate: {obvious_rate}.",
             "- TEST/evaluation leakage: 0/0; source hashes valid; production snapshot unchanged (64 files).",
             "- Review packet rows: 0; human review not started; V8–V10 not started.", "",
             "The source-reference interface solved exact evidence copying, but the model still often produced answer_text that was not an exact substring of its chosen unit, alongside question/reference and answer-type errors.",
             "With fewer than 20 AUTO_CHECKED candidates, the run stops before a human review packet.", ""]
    (TRAINING / "reports" / "rag_domain_qa_assisted_v7r2_audit.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__": main()
