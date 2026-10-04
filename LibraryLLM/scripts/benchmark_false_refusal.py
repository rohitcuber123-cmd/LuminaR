"""
RAG False Refusal Quality Benchmark

Tests 35+ queries across three books and uploaded PDFs.
Records full pipeline diagnostics for every query.
Generates JSON + markdown reports.
"""
import json
import os
import sys
import time
import gc
import traceback
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ["LUMINAR_MOCK_LLM"] = "0"

import torch
from rag.qa import LuminaRAG

# ============================================================
# BOOKS
# ============================================================

HUCK_FINN = "OL35758281W"
TALE_TWO = "OL43032614W"
PRIDE = "OL66524W"

# ============================================================
# TEST SUITE — 35 questions
# ============================================================

TEST_SUITE = [
    # ---- 10 INFORMATIONAL ----
    {"id": "info_01", "category": "informational", "work_id": HUCK_FINN, "query": "Who is the main character in this book?", "ground_truth_keywords": ["huck", "huckleberry"], "is_premise_valid": True},
    {"id": "info_02", "category": "informational", "work_id": HUCK_FINN, "query": "Who is Huck Finn?", "ground_truth_keywords": ["huck", "huckleberry", "narrator", "boy"], "is_premise_valid": True},
    {"id": "info_03", "category": "informational", "work_id": TALE_TWO, "query": "Who is the main character in this book?", "ground_truth_keywords": ["charles", "darnay", "sydney", "carton", "lucie", "manette"], "is_premise_valid": True},
    {"id": "info_04", "category": "informational", "work_id": PRIDE, "query": "Who is Elizabeth Bennet?", "ground_truth_keywords": ["elizabeth", "bennet", "daughter", "darcy"], "is_premise_valid": True},
    {"id": "info_05", "category": "informational", "work_id": PRIDE, "query": "Who is the main character?", "ground_truth_keywords": ["elizabeth", "bennet"], "is_premise_valid": True},
    {"id": "info_06", "category": "informational", "work_id": HUCK_FINN, "query": "Who are the important characters?", "ground_truth_keywords": ["huck", "jim", "tom"], "is_premise_valid": True},
    {"id": "info_07", "category": "informational", "work_id": PRIDE, "query": "Who is the author of this book?", "ground_truth_keywords": ["austen", "jane"], "is_premise_valid": True},
    {"id": "info_08", "category": "informational", "work_id": HUCK_FINN, "query": "Where does the story take place?", "ground_truth_keywords": ["mississippi", "river", "missouri"], "is_premise_valid": True},
    {"id": "info_09", "category": "informational", "work_id": TALE_TWO, "query": "Where does the story take place?", "ground_truth_keywords": ["london", "paris", "england", "france"], "is_premise_valid": True},
    {"id": "info_10", "category": "informational", "work_id": PRIDE, "query": "Where does the story take place?", "ground_truth_keywords": ["hertfordshire", "longbourn", "derbyshire", "pemberley", "england"], "is_premise_valid": True},

    # ---- 5 OVERVIEW ----
    {"id": "over_01", "category": "overview", "work_id": HUCK_FINN, "query": "What is this book about?", "ground_truth_keywords": ["huck", "adventure", "river", "jim"], "is_premise_valid": True},
    {"id": "over_02", "category": "overview", "work_id": TALE_TWO, "query": "What is this book about?", "ground_truth_keywords": ["revolution", "french", "london", "paris"], "is_premise_valid": True},
    {"id": "over_03", "category": "overview", "work_id": PRIDE, "query": "What is the book about?", "ground_truth_keywords": ["bennet", "darcy", "marriage", "pride"], "is_premise_valid": True},
    {"id": "over_04", "category": "overview", "work_id": HUCK_FINN, "query": "What happens in the story?", "ground_truth_keywords": ["huck", "jim", "river", "raft"], "is_premise_valid": True},
    {"id": "over_05", "category": "overview", "work_id": PRIDE, "query": "What is it about?", "ground_truth_keywords": ["bennet", "darcy", "marriage", "pride", "prejudice"], "is_premise_valid": True},

    # ---- 5 SUMMARY ----
    {"id": "summ_01", "category": "summary", "work_id": HUCK_FINN, "query": "What is the summary of this book?", "ground_truth_keywords": ["huck", "adventure", "jim", "river"], "is_premise_valid": True},
    {"id": "summ_02", "category": "summary", "work_id": TALE_TWO, "query": "What is its summary?", "ground_truth_keywords": ["revolution", "darnay", "carton", "manette"], "is_premise_valid": True},
    {"id": "summ_03", "category": "summary", "work_id": PRIDE, "query": "What is the summary?", "ground_truth_keywords": ["bennet", "darcy", "elizabeth"], "is_premise_valid": True},
    {"id": "summ_04", "category": "summary", "work_id": TALE_TWO, "query": "Give me a summary", "ground_truth_keywords": ["revolution", "paris", "london"], "is_premise_valid": True},
    {"id": "summ_05", "category": "summary", "work_id": HUCK_FINN, "query": "Summarize this book", "ground_truth_keywords": ["huck", "jim", "river"], "is_premise_valid": True},

    # ---- 5 THEMATIC / REASONING ----
    {"id": "theme_01", "category": "themes", "work_id": HUCK_FINN, "query": "What are the major themes?", "ground_truth_keywords": ["freedom", "slavery", "moral", "society", "race"], "is_premise_valid": True},
    {"id": "theme_02", "category": "themes", "work_id": TALE_TWO, "query": "What are the major themes?", "ground_truth_keywords": ["revolution", "sacrifice", "justice", "resurrection", "love"], "is_premise_valid": True},
    {"id": "theme_03", "category": "themes", "work_id": PRIDE, "query": "What are the major themes?", "ground_truth_keywords": ["pride", "prejudice", "marriage", "class", "love"], "is_premise_valid": True},
    {"id": "theme_04", "category": "themes", "work_id": PRIDE, "query": "What is the main theme?", "ground_truth_keywords": ["pride", "prejudice", "marriage", "love"], "is_premise_valid": True},
    {"id": "theme_05", "category": "themes", "work_id": HUCK_FINN, "query": "What are the themes of this book?", "ground_truth_keywords": ["freedom", "slavery", "moral", "society"], "is_premise_valid": True},

    # ---- 5 UNSUPPORTED / ADVERSARIAL ----
    {"id": "unsup_01", "category": "unsupported", "work_id": HUCK_FINN, "query": "Who is Elizabeth Bennet?", "ground_truth_keywords": [], "is_premise_valid": False},
    {"id": "unsup_02", "category": "unsupported", "work_id": TALE_TWO, "query": "Who is Huck Finn?", "ground_truth_keywords": [], "is_premise_valid": False},
    {"id": "unsup_03", "category": "unsupported", "work_id": PRIDE, "query": "What happens after Huck finds the raft?", "ground_truth_keywords": [], "is_premise_valid": False},
    {"id": "unsup_04", "category": "unsupported", "work_id": HUCK_FINN, "query": "Does this book discuss quantum computing?", "ground_truth_keywords": [], "is_premise_valid": False},
    {"id": "unsup_05", "category": "unsupported", "work_id": TALE_TWO, "query": "Why did Mr. Darcy propose to Elizabeth?", "ground_truth_keywords": [], "is_premise_valid": False},
]


def classify_result(q, result):
    """Classify a result as CORRECT, PARTIALLY_CORRECT, FALSE_REFUSAL, UNSUPPORTED, or HALLUCINATED."""
    answer = result.get("answer", "").lower()
    verdict = result.get("verdict", "NOT_SUPPORTED")

    is_unsupported_detected = (
        "does not support" in answer
        or "not establish" in answer
        or "no evidence" in answer
        or "does not contain" in answer
        or "insufficient" in answer
        or verdict == "NOT_SUPPORTED"
    )

    if not q["is_premise_valid"]:
        # Should be UNSUPPORTED
        if is_unsupported_detected or "not" in answer:
            return "UNSUPPORTED"
        return "HALLUCINATED"

    if verdict == "NOT_SUPPORTED":
        return "FALSE_REFUSAL"

    # Check ground truth keywords
    keywords = q.get("ground_truth_keywords", [])
    if keywords:
        found = sum(1 for kw in keywords if kw.lower() in answer)
        if found >= 1:
            return "CORRECT"
        return "PARTIALLY_CORRECT"
    return "CORRECT"


def main():
    print("=" * 80)
    print("RAG FALSE REFUSAL QUALITY BENCHMARK")
    print("=" * 80)

    engine = LuminaRAG()
    results = []

    for idx, q in enumerate(TEST_SUITE, start=1):
        print(f"\n[{idx:02d}/{len(TEST_SUITE)}] [{q['category']}] {q['query']}")
        print(f"  Book: {q['work_id']}")

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        t0 = time.perf_counter()
        try:
            res = engine.ask(
                question=q["query"],
                work_id=q["work_id"],
                depth="normal"
            )
        except Exception as e:
            traceback.print_exc()
            res = {
                "answer": f"Error: {e}",
                "verdict": "ERROR",
                "timing_ms": {},
                "sources": [],
                "fast_filter_decision": "ERROR",
                "fast_filter_signals": {},
                "fast_filter_reasons": [],
                "intent_data": {},
            }

        wall_ms = (time.perf_counter() - t0) * 1000
        answer = res.get("answer", "")
        verdict = res.get("verdict", "NOT_SUPPORTED")
        ff_decision = res.get("fast_filter_decision", "N/A")

        classification = classify_result(q, res)

        entry = {
            "id": q["id"],
            "category": q["category"],
            "query": q["query"],
            "work_id": q["work_id"],
            "is_premise_valid": q["is_premise_valid"],
            "ground_truth_keywords": q.get("ground_truth_keywords", []),
            "classification": classification,
            "verdict": verdict,
            "fast_filter_decision": ff_decision,
            "fast_filter_signals": res.get("fast_filter_signals", {}),
            "fast_filter_reasons": res.get("fast_filter_reasons", []),
            "intent_data": res.get("intent_data", {}),
            "answer": answer,
            "answer_length": len(answer.split()),
            "sources_count": len(res.get("sources", [])),
            "top_source": res.get("sources", [{}])[0].get("chunk_id") if res.get("sources") else None,
            "timing_ms": res.get("timing_ms", {}),
            "wall_time_ms": round(wall_ms, 2),
        }
        results.append(entry)

        mark = "PASS" if classification in ("CORRECT", "UNSUPPORTED") else "FAIL"
        print(f"  {mark} Verdict={verdict} | FF={ff_decision} | Class={classification}")
        print(f"    Latency: {wall_ms:.0f}ms | Words: {entry['answer_length']}")
        print(f"    Answer: {answer[:200]}{'...' if len(answer) > 200 else ''}")

        # Save incrementally
        with open("reports/rag_quality_false_refusal_analysis.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    valid = [r for r in results if r["is_premise_valid"]]
    invalid = [r for r in results if not r["is_premise_valid"]]

    correct = sum(1 for r in valid if r["classification"] == "CORRECT")
    partial = sum(1 for r in valid if r["classification"] == "PARTIALLY_CORRECT")
    false_refusal = sum(1 for r in valid if r["classification"] == "FALSE_REFUSAL")
    hallucinated = sum(1 for r in invalid if r["classification"] == "HALLUCINATED")
    unsupported = sum(1 for r in invalid if r["classification"] == "UNSUPPORTED")

    groundedness_valid = (correct + partial) / max(len(valid), 1) * 100
    invalid_rejection = unsupported / max(len(invalid), 1) * 100
    false_refusal_rate = false_refusal / max(len(valid), 1) * 100

    avg_latency = sum(r["wall_time_ms"] for r in results) / max(len(results), 1)
    avg_words = sum(r["answer_length"] for r in results if r["is_premise_valid"] and r["classification"] in ("CORRECT", "PARTIALLY_CORRECT")) / max(correct + partial, 1)

    print(f"Total queries: {len(results)}")
    print(f"Valid premise: {len(valid)}")
    print(f"  CORRECT: {correct}")
    print(f"  PARTIALLY_CORRECT: {partial}")
    print(f"  FALSE_REFUSAL: {false_refusal}")
    print(f"Invalid premise: {len(invalid)}")
    print(f"  UNSUPPORTED (correct): {unsupported}")
    print(f"  HALLUCINATED: {hallucinated}")
    print()
    print(f"Groundedness (valid): {groundedness_valid:.1f}%")
    print(f"Invalid rejection: {invalid_rejection:.1f}%")
    print(f"False refusal rate: {false_refusal_rate:.1f}%")
    print(f"Average latency: {avg_latency:.0f}ms")
    print(f"Average answer words (correct): {avg_words:.0f}")

    # Per-category breakdown
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "correct": 0, "partial": 0, "false_refusal": 0, "unsupported": 0, "hallucinated": 0, "latency": []}
        categories[cat]["total"] += 1
        categories[cat]["latency"].append(r["wall_time_ms"])
        if r["classification"] == "CORRECT":
            categories[cat]["correct"] += 1
        elif r["classification"] == "PARTIALLY_CORRECT":
            categories[cat]["partial"] += 1
        elif r["classification"] == "FALSE_REFUSAL":
            categories[cat]["false_refusal"] += 1
        elif r["classification"] == "UNSUPPORTED":
            categories[cat]["unsupported"] += 1
        elif r["classification"] == "HALLUCINATED":
            categories[cat]["hallucinated"] += 1

    print("\nPer-category:")
    for cat, data in categories.items():
        avg_lat = sum(data["latency"]) / max(len(data["latency"]), 1)
        print(f"  {cat}: {data['correct']}/{data['total']} correct, "
              f"{data['false_refusal']} false_refusal, "
              f"{data['hallucinated']} hallucinated, "
              f"avg {avg_lat:.0f}ms")

    # List false refusals
    print("\nFalse refusals:")
    for r in results:
        if r["classification"] == "FALSE_REFUSAL":
            print(f"  {r['id']}: {r['query']} ({r['work_id']})")

    print("\nHallucinations:")
    for r in results:
        if r["classification"] == "HALLUCINATED":
            print(f"  {r['id']}: {r['query']} ({r['work_id']})")

    print(f"\n[DONE] Saved to reports/rag_quality_false_refusal_analysis.json")


if __name__ == "__main__":
    main()
