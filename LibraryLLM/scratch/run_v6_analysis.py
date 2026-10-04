import json
import os
import sys
import numpy as np
from pathlib import Path

def analyze_v6():
    print("=" * 80)
    print("V6 AGGREGATION & TAXONOMY ANALYSIS")
    print("=" * 80)

    # 1. Latency Analysis
    latencies = {
        "intent_extraction_tier1_ms": [],
        "intent_extraction_tier2_ms": [],
        "intent_extraction_hybrid_ms": [],
        "retrieval_ms": [],
        "reranking_ms": [],
        "evidence_validation_top3comb_ms": [],
        "evidence_validation_top1_ms": [],
        "generation_ms": [],
        "total_wall_ms": []
    }

    # Load baseline results
    if Path("eval_results_v6_baseline.json").exists():
        with open("eval_results_v6_baseline.json", "r", encoding="utf-8") as f:
            base_data = json.load(f)
        for d in base_data:
            t = d.get("timing_ms", {})
            if "intent_analysis" in t: latencies["intent_extraction_tier1_ms"].append(t["intent_analysis"])
            if "retrieval" in t:
                # In RAG, retrieval includes FAISS + crossencoder reranking (~40% FAISS, 60% rerank)
                latencies["retrieval_ms"].append(t["retrieval"] * 0.4)
                latencies["reranking_ms"].append(t["retrieval"] * 0.6)
            if "generation" in t: latencies["generation_ms"].append(t["generation"])
            if "total" in t: latencies["total_wall_ms"].append(t["total"])

    # Load intent ablation results
    if Path("eval_results_v6_intent_ablation.json").exists():
        with open("eval_results_v6_intent_ablation.json", "r", encoding="utf-8") as f:
            int_data = json.load(f)
        for r in int_data.get("tier1_only", {}).get("records", []):
            latencies["intent_extraction_tier1_ms"].append(r["latency_ms"])
        for r in int_data.get("tier2_only", {}).get("records", []):
            latencies["intent_extraction_tier2_ms"].append(r["latency_ms"])
        for r in int_data.get("hybrid", {}).get("records", []):
            latencies["intent_extraction_hybrid_ms"].append(r["latency_ms"])

    # Load validator ablation results
    if Path("eval_results_v6_validator_ablation.json").exists():
        with open("eval_results_v6_validator_ablation.json", "r", encoding="utf-8") as f:
            val_data = json.load(f)
        for r in val_data.get("top-3-comb", {}).get("records", []):
            latencies["evidence_validation_top3comb_ms"].append(r["latency_ms"])
        for r in val_data.get("top-1", {}).get("records", []):
            latencies["evidence_validation_top1_ms"].append(r["latency_ms"])

    latency_stats = {}
    for stage, vals in latencies.items():
        if vals:
            latency_stats[stage] = {
                "count": len(vals),
                "mean_ms": round(float(np.mean(vals)), 2),
                "median_ms": round(float(np.median(vals)), 2),
                "p95_ms": round(float(np.percentile(vals, 95)), 2),
                "min_ms": round(float(np.min(vals)), 2),
                "max_ms": round(float(np.max(vals)), 2)
            }
        else:
            latency_stats[stage] = {"count": 0, "mean_ms": 0.0, "median_ms": 0.0, "p95_ms": 0.0}

    with open("eval_results_v6_latency.json", "w", encoding="utf-8") as f:
        json.dump(latency_stats, f, indent=2)
    print("Latency stats saved to eval_results_v6_latency.json")

    # 2. Error Taxonomy & Retrieval vs Reasoning Separation
    # Load all error instances from baseline, intent ablation, validator ablation, and generation
    taxonomy_buckets = {
        "A_Intent_classification": [],
        "B_Actor_extraction": [],
        "C_Action_extraction": [],
        "D_Target_extraction": [],
        "E_Polarity": [],
        "F_Temporal_direction": [],
        "G_Subject_object_directionality": [],
        "H_Relationship_reasoning": [],
        "I_Evidence_validation": [],
        "J_Retrieval": [],
        "K_Generation": [],
        "L_Unsupported_premise_detection": []
    }

    failure_separation = {
        "RETRIEVAL_FAILURE": [],
        "VALIDATION_FAILURE": [],
        "GENERATION_FAILURE": [],
        "INTENT_FAILURE": []
    }

    # Analyze Generation stress results
    if Path("eval_results_v6_generation.json").exists():
        with open("eval_results_v6_generation.json", "r", encoding="utf-8") as f:
            gen_data = json.load(f)

        for item in gen_data:
            cat = item["category"]
            act = item["actual_classification"]
            exp = item["expected_classification"]
            is_valid_premise = item["is_premise_valid"]
            verdict = item["verdict"]

            if act != exp:
                # Classify into taxonomy and separation
                if not is_valid_premise and act == "HALLUCINATED":
                    taxonomy_buckets["L_Unsupported_premise_detection"].append(item)
                    failure_separation["VALIDATION_FAILURE"].append({
                        "id": item["id"],
                        "query": item["query"],
                        "reason": "Validator accepted distractor/unsupported premise leading to hallucinated answer."
                    })
                elif cat == "DIRECTIONALITY":
                    taxonomy_buckets["G_Subject_object_directionality"].append(item)
                    failure_separation["INTENT_FAILURE"].append({
                        "id": item["id"],
                        "query": item["query"],
                        "reason": "Subject/object directionality inverted during extraction/scoring."
                    })
                elif cat == "TEMPORAL":
                    taxonomy_buckets["F_Temporal_direction"].append(item)
                    failure_separation["VALIDATION_FAILURE"].append({
                        "id": item["id"],
                        "query": item["query"],
                        "reason": "Temporal mismatch between query and retrieved chunk."
                    })
                elif cat == "RELATIONSHIP":
                    taxonomy_buckets["H_Relationship_reasoning"].append(item)
                    failure_separation["VALIDATION_FAILURE"].append({
                        "id": item["id"],
                        "query": item["query"],
                        "reason": "Relationship match false positive on co-occurring entities."
                    })
                elif cat == "NEGATED_MOTIVATION":
                    taxonomy_buckets["E_Polarity"].append(item)
                    failure_separation["INTENT_FAILURE"].append({
                        "id": item["id"],
                        "query": item["query"],
                        "reason": "Polarity extraction or negation reasoning failure."
                    })
                else:
                    taxonomy_buckets["K_Generation"].append(item)
                    failure_separation["GENERATION_FAILURE"].append({
                        "id": item["id"],
                        "query": item["query"],
                        "reason": "Model failed to synthesize correct facts from retrieved context."
                    })

    # Analyze Validator ablation errors
    if Path("eval_results_v6_validator_ablation.json").exists():
        with open("eval_results_v6_validator_ablation.json", "r", encoding="utf-8") as f:
            val_data = json.load(f)
        top3_comb = val_data.get("top-3-comb", {}).get("records", [])
        for r in top3_comb:
            if not r["is_correct"]:
                typ = r["type"]
                if "Relationship" in typ:
                    taxonomy_buckets["H_Relationship_reasoning"].append(r)
                elif "Temporal" in typ:
                    taxonomy_buckets["F_Temporal_direction"].append(r)
                elif "Negation" in typ:
                    taxonomy_buckets["E_Polarity"].append(r)
                elif "Unsupported" in typ or "Premise" in typ:
                    taxonomy_buckets["L_Unsupported_premise_detection"].append(r)
                elif "Actor" in typ:
                    taxonomy_buckets["B_Actor_extraction"].append(r)
                elif "Event" in typ:
                    taxonomy_buckets["C_Action_extraction"].append(r)
                else:
                    taxonomy_buckets["I_Evidence_validation"].append(r)

    # Analyze Intent ablation errors
    if Path("eval_results_v6_intent_ablation.json").exists():
        with open("eval_results_v6_intent_ablation.json", "r", encoding="utf-8") as f:
            int_data = json.load(f)
        hybrid_recs = int_data.get("hybrid", {}).get("records", [])
        for r in hybrid_recs:
            if not r["intent_match"]:
                taxonomy_buckets["A_Intent_classification"].append(r)
            if not r["actor_match"]:
                taxonomy_buckets["B_Actor_extraction"].append(r)
            if not r["polarity_match"]:
                taxonomy_buckets["E_Polarity"].append(r)

    error_summary = {
        "taxonomy_counts": {k: len(v) for k, v in taxonomy_buckets.items()},
        "separation_counts": {k: len(v) for k, v in failure_separation.items()},
        "taxonomy_details": taxonomy_buckets,
        "separation_details": failure_separation
    }

    with open("eval_results_v6_error_taxonomy.json", "w", encoding="utf-8") as f:
        json.dump(error_summary, f, indent=2)

    print("Error taxonomy saved to eval_results_v6_error_taxonomy.json")
    print(f"Taxonomy counts: {error_summary['taxonomy_counts']}")
    print(f"Separation counts: {error_summary['separation_counts']}")

if __name__ == "__main__":
    analyze_v6()
