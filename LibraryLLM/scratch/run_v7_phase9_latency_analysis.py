"""
V7 Phase 9: Latency Analysis

Aggregates timing data from all phase result files and produces
per-stage statistics: mean, median, P95, min, max.

Saves: eval_results_v7_latency_analysis.json
"""
import json
import os
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def load_json(filename):
    p = Path(filename)
    if not p.exists():
        print(f"  [SKIP] {filename} not found")
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def stats(vals):
    if not vals:
        return {"count": 0, "mean_ms": 0, "median_ms": 0, "p95_ms": 0, "min_ms": 0, "max_ms": 0}
    return {
        "count": len(vals),
        "mean_ms": round(float(np.mean(vals)), 2),
        "median_ms": round(float(np.median(vals)), 2),
        "p95_ms": round(float(np.percentile(vals, 95)), 2),
        "min_ms": round(float(np.min(vals)), 2),
        "max_ms": round(float(np.max(vals)), 2),
    }


def main():
    print("=" * 80)
    print("V7 PHASE 9: LATENCY ANALYSIS")
    print("=" * 80)

    latencies = {
        "intent_analysis": [],
        "retrieval": [],
        "fast_filter": [],
        "validation": [],
        "generation": [],
        "total": [],
        "wall_time": [],
    }

    # Phase 1: Baseline
    p1 = load_json("eval_results_v7_v6_baseline.json")
    if p1:
        recs = p1.get("records", p1 if isinstance(p1, list) else [])
        for r in recs:
            t = r.get("timing_ms", {})
            for key in ["intent_analysis", "retrieval", "fast_filter", "validation", "generation", "total"]:
                if key in t and t[key] > 0:
                    latencies[key].append(t[key])
            if "wall_time_ms" in r:
                latencies["wall_time"].append(r["wall_time_ms"])

    # Phase 3: Validator ablation (cascade config only)
    p3 = load_json("eval_results_v7_validator_ablation.json")
    if p3:
        cascade = p3.get("configs", {}).get("C_FastFilter_Plus_LLM", {})
        for r in cascade.get("records", []):
            if "latency_ms" in r and r["latency_ms"] > 0:
                latencies["validation"].append(r["latency_ms"])

    # Phase 5: Adversarial
    p5 = load_json("eval_results_v7_adversarial.json")
    if p5:
        for r in p5.get("records", []):
            if "fast_filter_latency_ms" in r:
                latencies["fast_filter"].append(r["fast_filter_latency_ms"])
            if "validator_latency_ms" in r:
                latencies["validation"].append(r["validator_latency_ms"])

    # Phase 8: E2E Generation
    p8 = load_json("eval_results_v7_e2e_generation.json")
    if p8:
        recs = p8 if isinstance(p8, list) else p8.get("records", [])
        for r in recs:
            t = r.get("timing_ms", {})
            for key in ["intent_analysis", "retrieval", "fast_filter", "validation", "generation", "total"]:
                if key in t and t[key] > 0:
                    latencies[key].append(t[key])
            if "wall_time_ms" in r:
                latencies["wall_time"].append(r["wall_time_ms"])

    # Compute stats
    result = {}
    for stage, vals in latencies.items():
        result[stage] = stats(vals)
        print(f"{stage:>20}: count={len(vals):>4}  mean={result[stage]['mean_ms']:>10.2f}ms  median={result[stage]['median_ms']:>10.2f}ms  p95={result[stage]['p95_ms']:>10.2f}ms")

    # V6 comparison (if baseline has separate validation data)
    comparison = {}
    if p1:
        baseline_records = p1.get("records", p1 if isinstance(p1, list) else [])
        v6_val_lats = [r.get("timing_ms", {}).get("validation", 0) for r in baseline_records if r.get("timing_ms", {}).get("validation", 0) > 0]
        v7_val_lats = latencies["validation"]

        if v6_val_lats and v7_val_lats:
            v6_mean = float(np.mean(v6_val_lats))
            v7_mean = float(np.mean(v7_val_lats))
            comparison = {
                "v6_validation_mean_ms": round(v6_mean, 2),
                "v7_validation_mean_ms": round(v7_mean, 2),
                "absolute_reduction_ms": round(v6_mean - v7_mean, 2),
                "percentage_reduction": round((1 - v7_mean / v6_mean) * 100, 2) if v6_mean > 0 else 0
            }

    output = {
        "per_stage_stats": result,
        "v6_vs_v7_validation_comparison": comparison,
    }

    with open("eval_results_v7_latency_analysis.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    if comparison:
        print(f"\nV6 vs V7 Validation: {comparison.get('v6_validation_mean_ms')}ms -> {comparison.get('v7_validation_mean_ms')}ms ({comparison.get('percentage_reduction')}% reduction)")

    print(f"\n[DONE] Saved to eval_results_v7_latency_analysis.json")


if __name__ == "__main__":
    main()
