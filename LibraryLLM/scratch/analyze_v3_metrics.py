import json
from pathlib import Path

def analyze():
    # Load V1 baseline
    try:
        with open("eval_results_after.json", "r") as f:
            v1_data = json.load(f)
    except:
        v1_data = []

    # Load V2
    try:
        with open("eval_results_v2.json", "r") as f:
            v2_data = json.load(f)
    except:
        v2_data = []

    # Load V3 Repro
    try:
        with open("eval_results_v3_repro.json", "r") as f:
            v3_data = json.load(f)
    except:
        v3_data = []
        
    print("===== METRICS COMPARISON =====")
    for name, data in [("V1 Baseline", v1_data), ("V2 Implementation", v2_data), ("V3 Reproduction", v3_data)]:
        if not data:
            continue
        
        # Retrieval metrics
        # For our 18 queries, top-1 accuracy is based on evidence support scoring > 0.
        # But we can look at the average rank of the first valid source if stored.
        # Since we don't have explicit ground truth chunk IDs, we can measure total latency and intent accuracy.
        intent_acc = sum(1 for q in data if q.get("expected_intent") == q.get("detected_intent"))
        avg_intent_latency = sum(q.get("timing_ms", {}).get("intent_ms", 22000) for q in data) / len(data)
        avg_retrieval_latency = sum(q.get("timing_ms", {}).get("retrieval_ms", 0) for q in data) / len(data)
        avg_generation_latency = sum(q.get("timing_ms", {}).get("generation_ms", 0) for q in data) / len(data)
        avg_total_latency = sum(q.get("wall_time_ms", 0) for q in data) / len(data)
        
        rejections = sum(1 for q in data if q.get("verdict") == "NOT_SUPPORTED")
        
        print(f"\n[{name}]")
        print(f"Intent Acc: {intent_acc}/{len(data)} ({(intent_acc/len(data))*100:.1f}%)")
        print(f"Rejections: {rejections}/{len(data)} ({(rejections/len(data))*100:.1f}%)")
        print(f"Avg Intent Latency : {avg_intent_latency:.1f} ms")
        print(f"Avg Retr Latency   : {avg_retrieval_latency:.1f} ms")
        print(f"Avg Gen Latency    : {avg_generation_latency:.1f} ms")
        print(f"Avg Wall Time      : {avg_total_latency:.1f} ms")

if __name__ == "__main__":
    analyze()
