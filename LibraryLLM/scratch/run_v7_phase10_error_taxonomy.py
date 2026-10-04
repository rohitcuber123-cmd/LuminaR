"""
V7 Phase 10: Error Taxonomy

Classifies every V7 failure across 14 categories (A-N) with explicit
distinction between fast-filter and LLM-validator errors.

Saves: eval_results_v7_error_taxonomy.json
"""
import json
import os
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


TAXONOMY_BUCKETS = {
    "A_Intent_classification": [],
    "B_Actor_extraction": [],
    "C_Action_extraction": [],
    "D_Target_extraction": [],
    "E_Polarity": [],
    "F_Temporal_direction": [],
    "G_Subject_object_directionality": [],
    "H_Relationship_reasoning": [],
    "I_Evidence_validation_FF_FP": [],
    "J_Evidence_validation_FF_FN": [],
    "K_Evidence_validation_LLM_FP": [],
    "L_Evidence_validation_LLM_FN": [],
    "M_Retrieval": [],
    "N_Generation": [],
}


def load_json(filename):
    p = Path(filename)
    if not p.exists():
        print(f"  [SKIP] {filename} not found")
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def classify_intent_errors(records):
    """Classify intent-related errors from Phase 6."""
    errors = []
    for r in records:
        if not r.get("intent_match"):
            error = {
                "id": r["id"],
                "query": r["query"],
                "expected": r["expected_intent"],
                "predicted": r["predicted_intent"],
                "source": "intent_regression"
            }
            errors.append(error)

            # Sub-classify
            if not r.get("actor_match"):
                TAXONOMY_BUCKETS["B_Actor_extraction"].append(error)
            if not r.get("polarity_match"):
                TAXONOMY_BUCKETS["E_Polarity"].append(error)

            TAXONOMY_BUCKETS["A_Intent_classification"].append(error)

    return errors


def classify_adversarial_errors(records):
    """Classify adversarial validation errors from Phase 5."""
    errors = []
    for r in records:
        if not r.get("is_correct"):
            error = {
                "id": r["id"],
                "category": r["category"],
                "query": r["query"],
                "expected": r["expected_verdict"],
                "final_decision": r["final_decision"],
                "ff_decision": r.get("fast_filter_decision"),
                "llm_decision": r.get("validator_decision"),
                "source": "adversarial"
            }
            errors.append(error)

            cat = r["category"]

            # Fast-filter specific errors
            ff = r.get("fast_filter_decision")
            if ff == "FAST_ACCEPT" and r["expected_verdict"] == "NOT_SUPPORTED":
                TAXONOMY_BUCKETS["I_Evidence_validation_FF_FP"].append(error)
            elif ff == "FAST_REJECT" and r["expected_verdict"] == "SUPPORTED":
                TAXONOMY_BUCKETS["J_Evidence_validation_FF_FN"].append(error)

            # LLM validator errors (only if LLM was called)
            if ff == "NEEDS_LLM_VALIDATION":
                llm_v = r.get("validator_decision")
                if llm_v == "SUPPORTED" and r["expected_verdict"] == "NOT_SUPPORTED":
                    TAXONOMY_BUCKETS["K_Evidence_validation_LLM_FP"].append(error)
                elif llm_v == "NOT_SUPPORTED" and r["expected_verdict"] == "SUPPORTED":
                    TAXONOMY_BUCKETS["L_Evidence_validation_LLM_FN"].append(error)

            # Category-specific taxonomy
            if cat == "subject_object_inversion":
                TAXONOMY_BUCKETS["G_Subject_object_directionality"].append(error)
            elif cat == "actor_mismatch":
                TAXONOMY_BUCKETS["B_Actor_extraction"].append(error)
            elif cat in ("target_mismatch", "event_mismatch"):
                TAXONOMY_BUCKETS["C_Action_extraction"].append(error)
            elif cat in ("negation", "double_negation"):
                TAXONOMY_BUCKETS["E_Polarity"].append(error)
            elif cat == "before_after_reversal":
                TAXONOMY_BUCKETS["F_Temporal_direction"].append(error)
            elif cat == "relationship_trap":
                TAXONOMY_BUCKETS["H_Relationship_reasoning"].append(error)
            elif cat in ("entity_lexical_overlap", "emotional_overlap"):
                TAXONOMY_BUCKETS["D_Target_extraction"].append(error)

    return errors


def classify_generation_errors(records):
    """Classify generation errors from Phase 8."""
    errors = []
    for r in records:
        if r.get("actual_classification") != r.get("expected_classification"):
            error = {
                "id": r["id"],
                "category": r["category"],
                "query": r["query"],
                "expected": r["expected_classification"],
                "actual": r["actual_classification"],
                "verdict": r.get("verdict"),
                "ff_decision": r.get("fast_filter_decision"),
                "source": "generation"
            }
            errors.append(error)

            if r["actual_classification"] == "HALLUCINATED":
                TAXONOMY_BUCKETS["N_Generation"].append(error)
            elif r["actual_classification"] == "UNSUPPORTED" and r["expected_classification"] == "CORRECT":
                # False negative in validation
                ff = r.get("fast_filter_decision")
                if ff == "FAST_REJECT":
                    TAXONOMY_BUCKETS["J_Evidence_validation_FF_FN"].append(error)
                else:
                    TAXONOMY_BUCKETS["L_Evidence_validation_LLM_FN"].append(error)
            elif r["actual_classification"] in ("CORRECT", "PARTIALLY_CORRECT") and r["expected_classification"] == "UNSUPPORTED":
                ff = r.get("fast_filter_decision")
                if ff == "FAST_ACCEPT":
                    TAXONOMY_BUCKETS["I_Evidence_validation_FF_FP"].append(error)
                else:
                    TAXONOMY_BUCKETS["K_Evidence_validation_LLM_FP"].append(error)

    return errors


def classify_retrieval_errors(records):
    """Classify retrieval errors from Phase 7."""
    errors = []
    for r in records:
        if r.get("top1_keyword_score", 0) < 0.5:
            error = {
                "id": r["id"],
                "query": r["query"],
                "top1_score": r["top1_keyword_score"],
                "top3_score": r["top3_keyword_score"],
                "source": "retrieval"
            }
            errors.append(error)
            TAXONOMY_BUCKETS["M_Retrieval"].append(error)
    return errors


def main():
    print("=" * 80)
    print("V7 PHASE 10: ERROR TAXONOMY")
    print("=" * 80)

    all_errors = []

    # Phase 6: Intent regression
    p6 = load_json("eval_results_v7_intent_regression.json")
    if p6:
        recs = p6.get("records", [])
        errs = classify_intent_errors(recs)
        all_errors.extend(errs)
        print(f"Intent errors: {len(errs)}")

    # Phase 5: Adversarial
    p5 = load_json("eval_results_v7_adversarial.json")
    if p5:
        recs = p5.get("records", [])
        errs = classify_adversarial_errors(recs)
        all_errors.extend(errs)
        print(f"Adversarial errors: {len(errs)}")

    # Phase 8: Generation
    p8 = load_json("eval_results_v7_e2e_generation.json")
    if p8:
        recs = p8 if isinstance(p8, list) else p8.get("records", [])
        errs = classify_generation_errors(recs)
        all_errors.extend(errs)
        print(f"Generation errors: {len(errs)}")

    # Phase 7: Retrieval
    p7 = load_json("eval_results_v7_retrieval_regression.json")
    if p7:
        recs = p7.get("records", [])
        errs = classify_retrieval_errors(recs)
        all_errors.extend(errs)
        print(f"Retrieval errors: {len(errs)}")

    # Build summary
    summary = {}
    for bucket_name, bucket_errors in TAXONOMY_BUCKETS.items():
        summary[bucket_name] = {
            "count": len(bucket_errors),
            "errors": bucket_errors[:10]  # Limit to first 10 for readability
        }

    # Failure separation
    failure_separation = {
        "FAST_FILTER_FALSE_POSITIVE": len(TAXONOMY_BUCKETS["I_Evidence_validation_FF_FP"]),
        "FAST_FILTER_FALSE_NEGATIVE": len(TAXONOMY_BUCKETS["J_Evidence_validation_FF_FN"]),
        "LLM_VALIDATOR_FALSE_POSITIVE": len(TAXONOMY_BUCKETS["K_Evidence_validation_LLM_FP"]),
        "LLM_VALIDATOR_FALSE_NEGATIVE": len(TAXONOMY_BUCKETS["L_Evidence_validation_LLM_FN"]),
        "INTENT_FAILURE": len(TAXONOMY_BUCKETS["A_Intent_classification"]),
        "RETRIEVAL_FAILURE": len(TAXONOMY_BUCKETS["M_Retrieval"]),
        "GENERATION_FAILURE": len(TAXONOMY_BUCKETS["N_Generation"]),
    }

    output = {
        "total_errors": len(all_errors),
        "failure_separation": failure_separation,
        "taxonomy": summary,
    }

    with open("eval_results_v7_error_taxonomy.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*80}")
    print("ERROR TAXONOMY SUMMARY")
    print("=" * 80)
    for k, v in failure_separation.items():
        print(f"  {k:<35}: {v}")
    print(f"\n  TOTAL ERRORS: {len(all_errors)}")
    print(f"\n[DONE] Saved to eval_results_v7_error_taxonomy.json")


if __name__ == "__main__":
    main()
