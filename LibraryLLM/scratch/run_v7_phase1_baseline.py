"""
V7 Phase 1: V6 Baseline Reproduction

Runs the V6 pipeline (with fast filter DISABLED via passthrough) on 18
representative queries. Records intent accuracy, retrieval, validation,
generation groundedness, and all latency breakdowns.

Saves: eval_results_v7_v6_baseline.json
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
os.environ["LUMINAR_MOCK_LLM"] = "0"

from rag.qa import LuminaRAG


# ============================================================
# EMBEDDED TEST QUERIES (from V6 regression suite)
# ============================================================

BASELINE_QUERIES = [
    {"id": 1,  "query": "Why does Victor create the creature?",                          "work_id": "OL45326637W", "expected_intent": "MOTIVATION"},
    {"id": 2,  "query": "What motivates Victor to study natural philosophy?",             "work_id": "OL45326637W", "expected_intent": "MOTIVATION"},
    {"id": 3,  "query": "Why does the creature hate Victor?",                             "work_id": "OL45326637W", "expected_intent": "MOTIVATION"},
    {"id": 4,  "query": "Why doesn't Victor create a female creature?",                   "work_id": "OL45326637W", "expected_intent": "NEGATED_MOTIVATION"},
    {"id": 5,  "query": "Why does Victor regret creating the creature?",                  "work_id": "OL45326637W", "expected_intent": "REGRET"},
    {"id": 6,  "query": "What happens after Victor creates the creature?",                "work_id": "OL45326637W", "expected_intent": "CONSEQUENCE"},
    {"id": 7,  "query": "What happens when Victor first sees the creature?",              "work_id": "OL45326637W", "expected_intent": "REACTION"},
    {"id": 8,  "query": "Who is Victor's father?",                                        "work_id": "OL45326637W", "expected_intent": "RELATIONSHIP"},
    {"id": 9,  "query": "Who is Elizabeth to Victor?",                                     "work_id": "OL45326637W", "expected_intent": "RELATIONSHIP"},
    {"id": 10, "query": "Where was Victor Frankenstein born?",                             "work_id": "OL45326637W", "expected_intent": "FACTUAL"},
    {"id": 11, "query": "Why does Dracula travel to London?",                              "work_id": "OL85892W",    "expected_intent": "MOTIVATION"},
    {"id": 12, "query": "Why doesn't Jonathan Harker leave the castle?",                   "work_id": "OL85892W",    "expected_intent": "NEGATED_MOTIVATION"},
    {"id": 13, "query": "What happens after Dracula arrives in London?",                   "work_id": "OL85892W",    "expected_intent": "CONSEQUENCE"},
    {"id": 14, "query": "Who is Mina's husband?",                                         "work_id": "OL85892W",    "expected_intent": "RELATIONSHIP"},
    {"id": 15, "query": "What ship transported Dracula to England?",                       "work_id": "OL85892W",    "expected_intent": "FACTUAL"},
    {"id": 16, "query": "Why does Dracula regret attacking his victims?",                  "work_id": "OL85892W",    "expected_intent": "REGRET"},
    {"id": 17, "query": "Why does Victor invite the creature to live with Elizabeth?",     "work_id": "OL45326637W", "expected_intent": "MOTIVATION"},
    {"id": 18, "query": "Why doesn't Victor finish creating the female creature in the Orkneys?", "work_id": "OL45326637W", "expected_intent": "NEGATED_MOTIVATION"},
]


def run_phase1():
    print("=" * 80)
    print("V7 PHASE 1: V6 BASELINE REPRODUCTION")
    print("=" * 80)

    output_path = Path("eval_results_v7_v6_baseline.json")
    results = []

    engine = LuminaRAG()

    print(f"\nRunning {len(BASELINE_QUERIES)} baseline queries...\n")

    for idx, item in enumerate(BASELINE_QUERIES, start=1):
        q_id = item["id"]
        query = item["query"]
        work_id = item["work_id"]
        expected_intent = item["expected_intent"]

        print(f"[{idx}/{len(BASELINE_QUERIES)}] Q{q_id}: {query} (Work: {work_id})")

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
                "timing_ms": {},
                "fast_filter_decision": "ERROR",
                "fast_filter_signals": {},
                "fast_filter_reasons": []
            }

        total_wall_ms = (time.perf_counter() - t0) * 1000

        # Extract top-3 chunk IDs for retrieval analysis
        sources = res.get("sources", [])
        top3_chunks = [s.get("chunk_id", "") for s in sources[:3]]

        entry = {
            "id": q_id,
            "query": query,
            "work_id": work_id,
            "expected_intent": expected_intent,
            "detected_intent": res.get("intent_data", {}).get("intent"),
            "intent_correct": res.get("intent_data", {}).get("intent") == expected_intent,
            "intent_data": res.get("intent_data", {}),
            "verdict": res.get("verdict"),
            "fast_filter_decision": res.get("fast_filter_decision", "N/A"),
            "fast_filter_signals": res.get("fast_filter_signals", {}),
            "fast_filter_reasons": res.get("fast_filter_reasons", []),
            "answer": res.get("answer"),
            "top3_chunks": top3_chunks,
            "source_count": len(sources),
            "timing_ms": res.get("timing_ms", {}),
            "wall_time_ms": round(total_wall_ms, 2)
        }

        results.append(entry)

        status = "PASS" if entry["intent_correct"] else "FAIL"
        ff = entry["fast_filter_decision"]
        lat = entry["timing_ms"].get("total", total_wall_ms)
        print(f"  -> Intent: {entry['detected_intent']} ({status}) | Verdict: {entry['verdict']} | FF: {ff} | Time: {lat:.1f}ms\n")

        # Save incrementally
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    # --------------------------------------------------------
    # AGGREGATE METRICS
    # --------------------------------------------------------
    intent_correct = sum(1 for r in results if r["intent_correct"])
    intent_acc = intent_correct / len(results) * 100

    verdicts = [r["verdict"] for r in results]
    supported_count = verdicts.count("SUPPORTED")
    not_supported_count = verdicts.count("NOT_SUPPORTED")

    ff_decisions = [r["fast_filter_decision"] for r in results]
    ff_reject = ff_decisions.count("FAST_REJECT")
    ff_accept = ff_decisions.count("FAST_ACCEPT")
    ff_llm = ff_decisions.count("NEEDS_LLM_VALIDATION")

    timing_keys = ["intent_analysis", "retrieval", "fast_filter", "validation", "generation", "total"]
    latency_stats = {}
    for key in timing_keys:
        vals = [r["timing_ms"].get(key, 0) for r in results if r["timing_ms"].get(key)]
        if vals:
            latency_stats[key] = {
                "mean_ms": round(float(np.mean(vals)), 2),
                "median_ms": round(float(np.median(vals)), 2),
                "p95_ms": round(float(np.percentile(vals, 95)), 2),
                "min_ms": round(float(np.min(vals)), 2),
                "max_ms": round(float(np.max(vals)), 2)
            }

    summary = {
        "total_queries": len(results),
        "intent_accuracy_percent": round(intent_acc, 2),
        "intent_correct": intent_correct,
        "intent_total": len(results),
        "verdicts": {
            "SUPPORTED": supported_count,
            "NOT_SUPPORTED": not_supported_count,
            "OTHER": len(results) - supported_count - not_supported_count
        },
        "fast_filter_decisions": {
            "FAST_REJECT": ff_reject,
            "FAST_ACCEPT": ff_accept,
            "NEEDS_LLM_VALIDATION": ff_llm,
            "llm_calls_avoided_percent": round((ff_reject + ff_accept) / len(results) * 100, 2)
        },
        "latency_stats": latency_stats
    }

    output = {
        "summary": summary,
        "records": results
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("\n" + "=" * 80)
    print("V7 PHASE 1 SUMMARY")
    print("=" * 80)
    print(f"Intent Accuracy    : {intent_acc:.1f}% ({intent_correct}/{len(results)})")
    print(f"Verdicts           : SUPPORTED={supported_count}, NOT_SUPPORTED={not_supported_count}")
    print(f"Fast Filter        : REJECT={ff_reject}, ACCEPT={ff_accept}, LLM={ff_llm}")
    print(f"LLM Calls Avoided  : {(ff_reject + ff_accept) / len(results) * 100:.1f}%")
    if "total" in latency_stats:
        print(f"Mean Total Latency : {latency_stats['total']['mean_ms']:.1f}ms")
        print(f"Median Total       : {latency_stats['total']['median_ms']:.1f}ms")
    print(f"\n[DONE] Saved to {output_path}")


if __name__ == "__main__":
    run_phase1()
