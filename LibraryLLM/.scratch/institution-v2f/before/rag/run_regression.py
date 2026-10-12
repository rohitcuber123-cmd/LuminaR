import json
import time
import os
from pathlib import Path
from rag.qa import LuminaRAG

def main():
    print("==================================================")
    print("RUNNING 18-QUERY RAG REGRESSION SUITE")
    print("==================================================")

    # Set mock mode for speed (we only care about retrieval and validation, not text generation)
    os.environ["LUMINAR_MOCK_LLM"] = "1"
    
    engine = LuminaRAG()
    
    baseline_path = Path("d:/SDC/LibraryLLM/scratch_eval_results.json")
    if not baseline_path.exists():
        print(f"Error: Baseline {baseline_path} not found.")
        return
        
    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline_data = json.load(f)
        
    after_data = []
    
    print("\nRunning queries...\n")
    
    total_latency = 0
    
    for i, base in enumerate(baseline_data):
        q = base["query"]
        w = base["work_id"]
        print(f"[{i+1}/18] {q}")
        
        start_t = time.perf_counter()
        result = engine.ask(question=q, work_id=w, depth="normal")
        end_t = time.perf_counter()
        
        latency = (end_t - start_t) * 1000
        total_latency += latency
        
        after_data.append({
            "id": base["id"],
            "query": q,
            "work_id": w,
            "expected_intent": base["expected_intent"],
            "detected_intent": result.get("intent_data", {}).get("intent"),
            "verdict": result.get("verdict"),
            "top_7_chunks": result.get("sources", []),
            "latency": latency
        })
        
    print("\n==================================================")
    print("REGRESSION RESULTS")
    print("==================================================")
    
    intent_acc = sum(1 for a in after_data if a["expected_intent"] == a["detected_intent"])
    avg_latency = total_latency / len(after_data)
    
    print(f"Intent Accuracy       : {intent_acc}/{len(after_data)}")
    print(f"Avg Retrieval Latency : {avg_latency:.2f} ms")
    print()
    
    # Analyze Specific Queries
    print("--- KEY IMPROVEMENT COMPARISONS ---")
    
    key_queries = [11, 12, 14]
    
    for q_id in key_queries:
        before = next(b for b in baseline_data if b["id"] == q_id)
        after = next(a for a in after_data if a["id"] == q_id)
        
        print(f"\nQ{q_id}: {before['query']}")
        b_ch = before["top_7_chunks"][0]["chapter"] if before["top_7_chunks"] else "?"
        b_cid = before["top_7_chunks"][0]["chunk_id"] if before["top_7_chunks"] else "?"
        a_ch = after["top_7_chunks"][0]["chapter"] if after["top_7_chunks"] else "?"
        a_cid = after["top_7_chunks"][0]["chunk_id"] if after["top_7_chunks"] else "?"
        
        print(f"  BEFORE Top-1: {b_ch} ({b_cid})")
        print(f"  AFTER  Top-1: {a_ch} ({a_cid})")
        
    print("\n--- EVIDENCE VALIDATION CHECKS ---")
    q17 = next(a for a in after_data if a["id"] == 17)
    print(f"Q17 (Dracula regret): Verdict = {q17['verdict']} (Expected: NOT_SUPPORTED)")
    
if __name__ == "__main__":
    main()
