import os
import json
import time
import gc
from pathlib import Path
import torch

# Ensure mock mode is OFF so real LLM is used
os.environ["LUMINAR_MOCK_LLM"] = "0"

from rag.qa import LuminaRAG

def run_evaluation():
    print("=" * 80)
    print("STARTING FULL END-TO-END EVALUATION (REAL LLM ON CUDA)")
    print("=" * 80)

    output_path = Path("eval_results_v3_repro.json")
    results = []
    completed_ids = set()

    if output_path.exists():
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                results = json.load(f)
                completed_ids = {item["id"] for item in results}
                print(f"Found {len(results)} previously completed queries in {output_path}")
        except Exception as e:
            print(f"Error reading existing results: {e}")

    engine = LuminaRAG()

    baseline_file = Path("scratch_eval_results.json")
    if not baseline_file.exists():
        print(f"Error: Baseline file {baseline_file} not found.")
        return

    with open(baseline_file, "r", encoding="utf-8") as f:
        baseline_data = json.load(f)

    print(f"\nRunning {len(baseline_data)} queries through full pipeline...\n")

    for idx, item in enumerate(baseline_data, start=1):
        q_id = item["id"]
        query = item["query"]
        work_id = item["work_id"]
        expected_intent = item["expected_intent"]

        if q_id in completed_ids:
            print(f"[{idx}/{len(baseline_data)}] Q{q_id}: ALREADY COMPLETED ({query})")
            continue

        print(f"[{idx}/{len(baseline_data)}] Q{q_id}: {query} (Work: {work_id})")

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        t0 = time.perf_counter()
        try:
            res = engine.ask(question=query, work_id=work_id, depth="normal")
        except Exception as e:
            print(f"ERROR on Q{q_id}: {e}")
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            # Retry once after clearing cache
            try:
                res = engine.ask(question=query, work_id=work_id, depth="normal")
            except Exception as e2:
                print(f"FAILED on Q{q_id} retry: {e2}")
                res = {
                    "question": query,
                    "answer": f"Error: {e2}",
                    "sources": [],
                    "intent_data": {},
                    "verdict": "ERROR",
                    "timing_ms": {}
                }

        total_wall_ms = (time.perf_counter() - t0) * 1000

        entry = {
            "id": q_id,
            "query": query,
            "work_id": work_id,
            "expected_intent": expected_intent,
            "detected_intent": res.get("intent_data", {}).get("intent"),
            "intent_data": res.get("intent_data", {}),
            "verdict": res.get("verdict"),
            "answer": res.get("answer"),
            "sources": res.get("sources", []),
            "timing_ms": res.get("timing_ms", {}),
            "wall_time_ms": round(total_wall_ms, 2)
        }

        results.append(entry)
        completed_ids.add(q_id)

        # Sort by ID and save after each query
        results_sorted = sorted(results, key=lambda x: x["id"])
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results_sorted, f, indent=2, ensure_ascii=False)

        top1_ch = res["sources"][0]["chapter"] if res.get("sources") else "None"
        top1_cid = res["sources"][0]["chunk_id"] if res.get("sources") else "None"
        top1_ev = res["sources"][0].get("evidence_score", 0) if res.get("sources") else 0
        top1_score = res["sources"][0].get("final_score", 0) if res.get("sources") else 0

        print(f"     Intent: {entry['detected_intent']} | Verdict: {entry['verdict']}")
        print(f"     Top-1: {top1_cid} ({top1_ch}) | EvidScore: {top1_ev:.3f} | FinalScore: {top1_score:.3f}")
        print(f"     Timing: Intent={entry['timing_ms'].get('intent_analysis', 0):.1f}ms, Retr={entry['timing_ms'].get('retrieval', 0):.1f}ms, Gen={entry['timing_ms'].get('generation', 0):.1f}ms | Wall={total_wall_ms:.1f}ms")
        print()

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    print(f"\nEvaluation complete! Results written to {output_path.resolve()}\n")

if __name__ == "__main__":
    run_evaluation()
