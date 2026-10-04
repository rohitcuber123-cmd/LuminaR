import os
import sys
import json
import time
import gc
from pathlib import Path
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ["LUMINAR_MOCK_LLM"] = "0"

from rag.qa import LuminaRAG

def run_v6_baseline():
    print("=" * 80)
    print("V6 PHASE 1: FREEZE V5 BASELINE EVALUATION (REAL GPU)")
    print("=" * 80)

    output_path = Path("eval_results_v6_baseline.json")
    results = []

    engine = LuminaRAG()

    baseline_file = Path("scratch_eval_results.json")
    if not baseline_file.exists():
        print(f"Error: Baseline file {baseline_file} not found.")
        return

    with open(baseline_file, "r", encoding="utf-8") as f:
        baseline_data = json.load(f)

    print(f"\nRunning {len(baseline_data)} baseline queries...\n")

    for idx, item in enumerate(baseline_data, start=1):
        q_id = item["id"]
        query = item["query"]
        work_id = item["work_id"]
        expected_intent = item["expected_intent"]

        print(f"[{idx}/{len(baseline_data)}] Q{q_id}: {query} (Work: {work_id})")

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        t0 = time.perf_counter()
        try:
            res = engine.ask(question=query, work_id=work_id, depth="normal")
        except Exception as e:
            print(f"ERROR on Q{q_id}: {e}")
            res = {
                "question": query,
                "answer": f"Error: {e}",
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

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    print(f"\n[DONE] Baseline saved to {output_path}")

if __name__ == "__main__":
    run_v6_baseline()
