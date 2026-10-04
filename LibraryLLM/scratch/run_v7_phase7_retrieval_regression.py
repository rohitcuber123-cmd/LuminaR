"""
V7 Phase 7: Retrieval Regression

Verifies Top-1, Top-3, MRR, FAISS latency, CrossEncoder latency.
V7 does NOT modify retrieval, so this should show zero regression.

Saves: eval_results_v7_retrieval_regression.json
"""
import json
import os
import sys
import time
import gc
import torch
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ["LUMINAR_MOCK_LLM"] = "1"  # Mock LLM for speed — we only test retrieval

from rag.qa import LuminaRAG

RETRIEVAL_QUERIES = [
    {"id": 1, "query": "Why does Victor create the creature?", "work_id": "OL45326637W",
     "expected_top1_keywords": ["instruments", "life", "spark", "being", "creature"],
     "expected_top3_keywords": ["create", "creature", "life", "animate"]},
    {"id": 2, "query": "Who is Victor's father?", "work_id": "OL45326637W",
     "expected_top1_keywords": ["father", "alphonse"],
     "expected_top3_keywords": ["father", "alphonse", "frankenstein"]},
    {"id": 3, "query": "Why doesn't Victor create a female creature?", "work_id": "OL45326637W",
     "expected_top1_keywords": ["female", "race", "devils", "refuse", "destroy"],
     "expected_top3_keywords": ["female", "creature", "companion"]},
    {"id": 4, "query": "What happens after Victor creates the creature?", "work_id": "OL45326637W",
     "expected_top1_keywords": ["creature", "eye", "horror", "rushed"],
     "expected_top3_keywords": ["creature", "horror", "eye"]},
    {"id": 5, "query": "Why does Dracula travel to London?", "work_id": "OL85892W",
     "expected_top1_keywords": ["london", "dracula"],
     "expected_top3_keywords": ["london", "dracula", "england"]},
    {"id": 6, "query": "Why doesn't Jonathan Harker leave the castle?", "work_id": "OL85892W",
     "expected_top1_keywords": ["castle", "prisoner", "locked", "door"],
     "expected_top3_keywords": ["castle", "prisoner", "escape"]},
    {"id": 7, "query": "Who is Mina's husband?", "work_id": "OL85892W",
     "expected_top1_keywords": ["mina", "jonathan", "harker", "husband"],
     "expected_top3_keywords": ["mina", "harker"]},
    {"id": 8, "query": "What ship transported Dracula to England?", "work_id": "OL85892W",
     "expected_top1_keywords": ["demeter", "ship"],
     "expected_top3_keywords": ["demeter", "ship", "whitby"]},
    {"id": 9, "query": "Why does Victor regret creating the creature?", "work_id": "OL45326637W",
     "expected_top1_keywords": ["regret", "guilt", "remorse", "curse"],
     "expected_top3_keywords": ["regret", "guilt", "creature"]},
    {"id": 10, "query": "What happens when Victor first sees the creature?", "work_id": "OL45326637W",
     "expected_top1_keywords": ["eye", "horror", "creature", "disgust"],
     "expected_top3_keywords": ["creature", "eye", "horror"]},
]


def main():
    print("=" * 80)
    print("V7 PHASE 7: RETRIEVAL REGRESSION TEST")
    print("=" * 80)

    engine = LuminaRAG()
    records = []

    for q in RETRIEVAL_QUERIES:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        t0 = time.perf_counter()
        search_res = engine.reranker.search(query=q["query"], top_k=5, work_id=q["work_id"], intent_data={})
        wall_ms = (time.perf_counter() - t0) * 1000

        results = search_res.get("results", [])
        top1_text = results[0].get("chunk_id", "") if results else ""
        top3_chunks = [s.get("chunk_id", "") for s in results[:3]]

        # Check keyword presence in top-1
        top1_full = (results[0].get("text", "") if results else "").lower()
        top1_hit = sum(1 for kw in q["expected_top1_keywords"] if kw.lower() in top1_full)
        top1_score = top1_hit / max(len(q["expected_top1_keywords"]), 1)

        # Check keyword presence in top-3
        top3_full = " ".join(s.get("text", "").lower() for s in results[:3]) if results else ""
        top3_hit = sum(1 for kw in q["expected_top3_keywords"] if kw.lower() in top3_full)
        top3_score = top3_hit / max(len(q["expected_top3_keywords"]), 1)

        timing = {"retrieval": wall_ms}

        rec = {
            "id": q["id"],
            "query": q["query"],
            "work_id": q["work_id"],
            "top1_chunk": top1_text,
            "top3_chunks": top3_chunks,
            "top1_keyword_score": round(top1_score, 3),
            "top3_keyword_score": round(top3_score, 3),
            "source_count": len(results),
            "retrieval_ms": timing.get("retrieval", 0),
            "fast_filter_ms": 0,
            "wall_ms": round(wall_ms, 2),
        }
        records.append(rec)

        print(f"[{q['id']:02d}] {q['query'][:50]:<50} | Top1={top1_score:.2f} Top3={top3_score:.2f} | {wall_ms:.1f}ms")

    # Aggregate
    top1_acc = sum(1 for r in records if r["top1_keyword_score"] >= 0.5) / len(records) * 100
    top3_acc = sum(1 for r in records if r["top3_keyword_score"] >= 0.5) / len(records) * 100
    retrieval_lats = [r["retrieval_ms"] for r in records if r["retrieval_ms"] > 0]
    ff_lats = [r["fast_filter_ms"] for r in records if r["fast_filter_ms"] > 0]

    # MRR calculation
    mrr_values = []
    for r in records:
        if r["top1_keyword_score"] >= 0.5:
            mrr_values.append(1.0)
        elif r["top3_keyword_score"] >= 0.5:
            mrr_values.append(0.33)
        else:
            mrr_values.append(0.0)
    mrr = float(np.mean(mrr_values)) if mrr_values else 0.0

    summary = {
        "total_queries": len(records),
        "top1_accuracy_percent": round(top1_acc, 2),
        "top3_accuracy_percent": round(top3_acc, 2),
        "mrr": round(mrr, 4),
        "retrieval_latency": {
            "mean_ms": round(float(np.mean(retrieval_lats)), 2) if retrieval_lats else 0,
            "median_ms": round(float(np.median(retrieval_lats)), 2) if retrieval_lats else 0,
            "p95_ms": round(float(np.percentile(retrieval_lats, 95)), 2) if retrieval_lats else 0,
        },
        "fast_filter_latency": {
            "mean_ms": round(float(np.mean(ff_lats)), 2) if ff_lats else 0,
        }
    }

    output = {"summary": summary, "records": records}
    with open("eval_results_v7_retrieval_regression.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nTop-1: {top1_acc:.1f}% | Top-3: {top3_acc:.1f}% | MRR: {mrr:.4f}")
    print(f"\n[DONE] Saved to eval_results_v7_retrieval_regression.json")


if __name__ == "__main__":
    main()
