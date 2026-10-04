import json
from pathlib import Path

def get_data():
    with open('eval_results_v7_v6_baseline.json', 'r', encoding='utf-8') as f:
        p1 = json.load(f)
    with open('eval_results_v7_validator_ablation.json', 'r', encoding='utf-8') as f:
        p3 = json.load(f)
    with open('eval_results_v7_schema_ablation.json', 'r', encoding='utf-8') as f:
        p4 = json.load(f)
    with open('eval_results_v7_adversarial.json', 'r', encoding='utf-8') as f:
        p5 = json.load(f)
    with open('eval_results_v7_intent_regression.json', 'r', encoding='utf-8') as f:
        p6 = json.load(f)
    with open('eval_results_v7_retrieval_regression.json', 'r', encoding='utf-8') as f:
        p7 = json.load(f)
    with open('eval_results_v7_e2e_generation.json', 'r', encoding='utf-8') as f:
        p8 = json.load(f)
    with open('eval_results_v7_latency_analysis.json', 'r', encoding='utf-8') as f:
        p9 = json.load(f)
    with open('eval_results_v7_error_taxonomy.json', 'r', encoding='utf-8') as f:
        p10 = json.load(f)

    print("=== PHASE 1: V6 BASELINE ===")
    print(json.dumps(p1.get("summary", {}), indent=2))

    print("\n=== PHASE 3: VALIDATOR ABLATION ===")
    for k, v in p3["configs"].items():
        print(f"Config {k}: Acc={v['accuracy_percent']}%, FP={v['false_positives']}, FN={v['false_negatives']}, Mean Lat={v['mean_latency_ms']}ms, LLM Calls={v['llm_calls']}/{v['total_cases']}")
    print("Comparison Cascade vs Baseline:", json.dumps(p3.get("comparison_cascade_vs_baseline", {}), indent=2))

    print("\n=== PHASE 4: SCHEMA ABLATION ===")
    for k, v in p4.items():
        print(f"Schema {k}: Acc={v['accuracy_percent']}%, FP={v['false_positives']}, FN={v['false_negatives']}, JSON Compliance={v['json_compliance_percent']}%, Mean Lat={v['mean_latency_ms']}ms")

    print("\n=== PHASE 5: ADVERSARIAL ===")
    print(json.dumps(p5.get("summary", {}), indent=2))

    print("\n=== PHASE 6: INTENT REGRESSION ===")
    print(json.dumps(p6.get("summary", {}), indent=2))

    print("\n=== PHASE 7: RETRIEVAL REGRESSION ===")
    print(json.dumps(p7.get("summary", {}), indent=2))

    print("\n=== PHASE 8: E2E GENERATION ===")
    correct = sum(1 for r in p8 if r["actual_classification"] == "CORRECT")
    partial = sum(1 for r in p8 if r["actual_classification"] == "PARTIALLY_CORRECT")
    unsupported = sum(1 for r in p8 if r["actual_classification"] == "UNSUPPORTED")
    hallucinated = sum(1 for r in p8 if r["actual_classification"] == "HALLUCINATED")
    match = sum(1 for r in p8 if r["actual_classification"] == r["expected_classification"])
    valid = [r for r in p8 if r["is_premise_valid"]]
    invalid = [r for r in p8 if not r["is_premise_valid"]]
    groundedness_valid = sum(1 for r in valid if r["actual_classification"] in ("CORRECT", "PARTIALLY_CORRECT")) / max(len(valid), 1) * 100
    groundedness_invalid = sum(1 for r in invalid if r["actual_classification"] == "UNSUPPORTED") / max(len(invalid), 1) * 100
    print(f"Total: {len(p8)}, Match: {match}/{len(p8)} ({match/len(p8)*100:.2f}%)")
    print(f"CORRECT={correct}, PARTIAL={partial}, UNSUPPORTED={unsupported}, HALLUCINATED={hallucinated}")
    print(f"Groundedness Valid: {groundedness_valid:.2f}%, Groundedness Invalid Rejection: {groundedness_invalid:.2f}%")

    print("\n=== PHASE 9: LATENCY ANALYSIS ===")
    print(json.dumps(p9, indent=2))

    print("\n=== PHASE 10: ERROR TAXONOMY ===")
    print("Total Errors:", p10.get("total_errors"))
    print(json.dumps(p10.get("failure_separation", {}), indent=2))

if __name__ == '__main__':
    get_data()
