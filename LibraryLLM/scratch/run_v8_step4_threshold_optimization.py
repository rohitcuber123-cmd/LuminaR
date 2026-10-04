"""
V8 Step 4: Fast-Filter Threshold Optimization

Sweeps 25 combinations of actor_score and event_score thresholds
to find the Pareto-optimal configuration that maximizes F1 score 
while keeping False Positives (FAST_ACCEPT on unsupported premise) <= 2.

Runs strictly on CPU, using the fast-filter only.
"""
import json
import os
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rag.fast_filter import compute_alignment_signals
from scratch.run_v8_step1_v7_reproduction import ADVERSARIAL_CASES

def test_thresholds(actor_threshold, event_threshold):
    records = []
    
    for c in ADVERSARIAL_CASES:
        signals = compute_alignment_signals(
            question=c["question"],
            intent_data=c["intent_data"],
            evidence_text=c["evidence"]
        )
        
        # Copied from fast_filter_decision but with parameterized thresholds
        if signals.polarity_mismatch or signals.temporal_conflict or signals.direction_inverted:
            decision = "FAST_REJECT"
        elif (signals.actor_score >= actor_threshold
              and signals.event_score >= event_threshold
              and signals.polarity_aligned
              and signals.temporal_aligned
              and signals.relationship_check_passed
              and not signals.direction_inverted
              and not signals.mere_lexical_cooccurrence):
            decision = "FAST_ACCEPT"
        else:
            decision = "NEEDS_LLM_VALIDATION"
            
        records.append({
            "expected": c["expected_supported"],
            "decision": decision
        })
        
    # Calculate metrics
    # True Positives: Expected True, FAST_ACCEPT
    tp = sum(1 for r in records if r["expected"] and r["decision"] == "FAST_ACCEPT")
    # False Positives: Expected False, FAST_ACCEPT (Dangerous!)
    fp = sum(1 for r in records if not r["expected"] and r["decision"] == "FAST_ACCEPT")
    # True Negatives: Expected False, FAST_REJECT
    tn = sum(1 for r in records if not r["expected"] and r["decision"] == "FAST_REJECT")
    # False Negatives: Expected True, FAST_REJECT (Bad, but LLM can't fix it)
    fn = sum(1 for r in records if r["expected"] and r["decision"] == "FAST_REJECT")
    
    # Needs LLM: ambiguous
    llm = sum(1 for r in records if r["decision"] == "NEEDS_LLM_VALIDATION")
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn + llm) if (tp + fn + llm) > 0 else 0  # Assuming LLM *could* have gotten the rest, recall of the fast-filter
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    return {
        "actor_threshold": actor_threshold,
        "event_threshold": event_threshold,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn, "llm": llm,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "total_filtered": tp + tn + fp + fn
    }

def run_step4():
    print("=" * 80)
    print("V8 STEP 4: FAST-FILTER THRESHOLD OPTIMIZATION")
    print("=" * 80)

    output_json = Path("reports/v8_experiment_c_threshold_optimization.json")
    output_json.parent.mkdir(exist_ok=True)

    actor_thresholds = [0.6, 0.7, 0.8, 0.9, 1.0]
    event_thresholds = [0.4, 0.5, 0.6, 0.7, 0.8]
    
    results = []
    
    print(f"Sweeping {len(actor_thresholds) * len(event_thresholds)} combinations...\n")
    print(f"{'Actor':<6} | {'Event':<6} | {'TP':<3} | {'FP':<3} | {'TN':<3} | {'FN':<3} | {'LLM':<4} | {'F1':<6}")
    print("-" * 50)
    
    for a_thresh in actor_thresholds:
        for e_thresh in event_thresholds:
            metrics = test_thresholds(a_thresh, e_thresh)
            results.append(metrics)
            print(f"{a_thresh:<6} | {e_thresh:<6} | {metrics['tp']:<3} | {metrics['fp']:<3} | {metrics['tn']:<3} | {metrics['fn']:<3} | {metrics['llm']:<4} | {metrics['f1']:<6.4f}")
            
    # Find the best: maximize F1 where FP <= 2
    valid_results = [r for r in results if r["fp"] <= 2]
    if valid_results:
        best = max(valid_results, key=lambda x: (x["f1"], -x["fp"], x["total_filtered"]))
        print("\n" + "=" * 50)
        print("BEST CONFIGURATION (FP <= 2)")
        print("=" * 50)
        print(f"Actor Threshold : {best['actor_threshold']}")
        print(f"Event Threshold : {best['event_threshold']}")
        print(f"Metrics         : F1={best['f1']:.4f}, FP={best['fp']}, TP={best['tp']}, TN={best['tn']}")
    else:
        best = None
        print("\nNo configuration met the FP <= 2 constraint.")

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump({"results": results, "best": best}, f, indent=2)
    print(f"\n[SAVED] {output_json}")

if __name__ == "__main__":
    run_step4()
