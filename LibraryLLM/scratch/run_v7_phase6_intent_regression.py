"""
V7 Phase 6: Intent Regression

Re-runs the V6 intent evaluation to verify V7 did not degrade intent performance.
Uses the same 64 test queries (18 canonical + 36 paraphrase + 10 adversarial).

Saves: eval_results_v7_intent_regression.json
"""
import json
import os
import sys
import time
import re
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ["LUMINAR_MOCK_LLM"] = "0"

from rag.llm import LuminaRLLM

# Same test queries from V6 intent ablation
TEST_QUERIES = [
    {"id": "can_01", "category": "Canonical", "query": "Why does Victor create the creature?", "expected_intent": "MOTIVATION", "expected_actor": "victor", "expected_polarity": "positive"},
    {"id": "can_02", "category": "Canonical", "query": "What motivates Victor to create the creature?", "expected_intent": "MOTIVATION", "expected_actor": "victor", "expected_polarity": "positive"},
    {"id": "can_03", "category": "Canonical", "query": "Why does the creature hate Victor?", "expected_intent": "MOTIVATION", "expected_actor": "the creature", "expected_polarity": "positive"},
    {"id": "can_04", "category": "Canonical", "query": "Why doesn't Victor create a female creature?", "expected_intent": "NEGATED_MOTIVATION", "expected_actor": "victor", "expected_polarity": "negative"},
    {"id": "can_05", "category": "Canonical", "query": "Why did Victor refuse to create a companion?", "expected_intent": "NEGATED_MOTIVATION", "expected_actor": "victor", "expected_polarity": "negative"},
    {"id": "can_06", "category": "Canonical", "query": "Why does Victor regret creating the creature?", "expected_intent": "REGRET", "expected_actor": "victor", "expected_polarity": "positive"},
    {"id": "can_07", "category": "Canonical", "query": "Why does Victor feel remorse about the monster?", "expected_intent": "REGRET", "expected_actor": "victor", "expected_polarity": "positive"},
    {"id": "can_08", "category": "Canonical", "query": "What happens after Victor creates the creature?", "expected_intent": "CONSEQUENCE", "expected_actor": "victor", "expected_polarity": "positive"},
    {"id": "can_09", "category": "Canonical", "query": "What happens after the creature is brought to life?", "expected_intent": "CONSEQUENCE", "expected_actor": "the creature", "expected_polarity": "positive"},
    {"id": "can_10", "category": "Canonical", "query": "What happens when Victor first sees the creature?", "expected_intent": "REACTION", "expected_actor": "victor", "expected_polarity": "positive"},
    {"id": "can_11", "category": "Canonical", "query": "How does Victor react when the creature awakens?", "expected_intent": "REACTION", "expected_actor": "victor", "expected_polarity": "positive"},
    {"id": "can_12", "category": "Canonical", "query": "Who is Victor's father?", "expected_intent": "RELATIONSHIP", "expected_actor": "victor", "expected_polarity": "positive"},
    {"id": "can_13", "category": "Canonical", "query": "Who is Elizabeth to Victor?", "expected_intent": "RELATIONSHIP", "expected_actor": "victor", "expected_polarity": "positive"},
    {"id": "can_14", "category": "Canonical", "query": "Why does Dracula buy the house in London?", "expected_intent": "MOTIVATION", "expected_actor": "dracula", "expected_polarity": "positive"},
    {"id": "can_15", "category": "Canonical", "query": "What motivates Van Helsing to hunt Dracula?", "expected_intent": "MOTIVATION", "expected_actor": "van helsing", "expected_polarity": "positive"},
    {"id": "can_16", "category": "Canonical", "query": "Why doesn't Jonathan Harker leave the castle?", "expected_intent": "NEGATED_MOTIVATION", "expected_actor": "jonathan harker", "expected_polarity": "negative"},
    {"id": "can_17", "category": "Canonical", "query": "What happens after Dracula arrives in London?", "expected_intent": "CONSEQUENCE", "expected_actor": "dracula", "expected_polarity": "positive"},
    {"id": "can_18", "category": "Canonical", "query": "Who is Mina's husband?", "expected_intent": "RELATIONSHIP", "expected_actor": "mina", "expected_polarity": "positive"},
        # --- PARAPHRASED (36) ---
        {"id": "para_01", "category": "Paraphrased", "query": "What drives Victor to bring the creature to life?", "expected_intent": "MOTIVATION", "expected_actor": "victor", "expected_polarity": "positive"},
        {"id": "para_02", "category": "Paraphrased", "query": "For what reason does Victor animate the lifeless body?", "expected_intent": "MOTIVATION", "expected_actor": "victor", "expected_polarity": "positive"},
        {"id": "para_03", "category": "Paraphrased", "query": "What is the underlying cause of the creature's hatred for Victor?", "expected_intent": "MOTIVATION", "expected_actor": "the creature", "expected_polarity": "positive"},
        {"id": "para_04", "category": "Paraphrased", "query": "Why is Victor against the idea of making a bride for the monster?", "expected_intent": "NEGATED_MOTIVATION", "expected_actor": "victor", "expected_polarity": "negative"},
        {"id": "para_05", "category": "Paraphrased", "query": "What prevented Victor from assembling a second creature?", "expected_intent": "NEGATED_MOTIVATION", "expected_actor": "victor", "expected_polarity": "negative"},
        {"id": "para_06", "category": "Paraphrased", "query": "Why does Victor feel so much guilt over his scientific experiment?", "expected_intent": "REGRET", "expected_actor": "victor", "expected_polarity": "positive"},
        {"id": "para_07", "category": "Paraphrased", "query": "What causes Victor's deep sorrow concerning his creation?", "expected_intent": "REGRET", "expected_actor": "victor", "expected_polarity": "positive"},
        {"id": "para_08", "category": "Paraphrased", "query": "What are the immediate events following the animation of the monster?", "expected_intent": "CONSEQUENCE", "expected_actor": "the monster", "expected_polarity": "positive"},
        {"id": "para_09", "category": "Paraphrased", "query": "What is the direct result of Victor succeeding in his experiment?", "expected_intent": "CONSEQUENCE", "expected_actor": "victor", "expected_polarity": "positive"},
        {"id": "para_10", "category": "Paraphrased", "query": "How does Victor feel the moment he looks at the living monster?", "expected_intent": "REACTION", "expected_actor": "victor", "expected_polarity": "positive"},
        {"id": "para_11", "category": "Paraphrased", "query": "What is Victor's emotional response upon seeing the creature's yellow eye?", "expected_intent": "REACTION", "expected_actor": "victor", "expected_polarity": "positive"},
        {"id": "para_12", "category": "Paraphrased", "query": "Can you tell me the name of the man who raised Victor?", "expected_intent": "RELATIONSHIP", "expected_actor": "victor", "expected_polarity": "positive"},
        {"id": "para_13", "category": "Paraphrased", "query": "What is the exact familial tie between Victor and Elizabeth?", "expected_intent": "RELATIONSHIP", "expected_actor": "victor", "expected_polarity": "positive"},
        {"id": "para_14", "category": "Paraphrased", "query": "What is the Count's primary reason for acquiring the Carfax estate?", "expected_intent": "MOTIVATION", "expected_actor": "the count", "expected_polarity": "positive"},
        {"id": "para_15", "category": "Paraphrased", "query": "What compels the professor to track down the vampire?", "expected_intent": "MOTIVATION", "expected_actor": "the professor", "expected_polarity": "positive"},
        {"id": "para_16", "category": "Paraphrased", "query": "What stops Harker from simply walking out the front door?", "expected_intent": "NEGATED_MOTIVATION", "expected_actor": "harker", "expected_polarity": "negative"},
        {"id": "para_17", "category": "Paraphrased", "query": "What occurs in England once the Demeter docks at Whitby?", "expected_intent": "CONSEQUENCE", "expected_actor": "demeter", "expected_polarity": "positive"},
        {"id": "para_18", "category": "Paraphrased", "query": "Who is the man legally married to Mina Murray?", "expected_intent": "RELATIONSHIP", "expected_actor": "mina murray", "expected_polarity": "positive"},
        {"id": "para_19", "category": "Paraphrased", "query": "Why does the monster kill William?", "expected_intent": "MOTIVATION", "expected_actor": "the monster", "expected_polarity": "positive"},
        {"id": "para_20", "category": "Paraphrased", "query": "What leads the creature to frame Justine?", "expected_intent": "MOTIVATION", "expected_actor": "the creature", "expected_polarity": "positive"},
        {"id": "para_21", "category": "Paraphrased", "query": "Why did the De Laceys reject the monster?", "expected_intent": "MOTIVATION", "expected_actor": "de laceys", "expected_polarity": "positive"},
        {"id": "para_22", "category": "Paraphrased", "query": "Why does Victor destroy the half-finished female?", "expected_intent": "NEGATED_MOTIVATION", "expected_actor": "victor", "expected_polarity": "negative"},
        {"id": "para_23", "category": "Paraphrased", "query": "What made Victor break his promise to the fiend?", "expected_intent": "NEGATED_MOTIVATION", "expected_actor": "victor", "expected_polarity": "negative"},
        {"id": "para_24", "category": "Paraphrased", "query": "Why is the creature so devastated when he finds Victor dead?", "expected_intent": "REGRET", "expected_actor": "the creature", "expected_polarity": "positive"},
        {"id": "para_25", "category": "Paraphrased", "query": "What happens directly after Elizabeth is murdered?", "expected_intent": "CONSEQUENCE", "expected_actor": "elizabeth", "expected_polarity": "positive"},
        {"id": "para_26", "category": "Paraphrased", "query": "What takes place once Victor chases the monster to the ice?", "expected_intent": "CONSEQUENCE", "expected_actor": "victor", "expected_polarity": "positive"},
        {"id": "para_27", "category": "Paraphrased", "query": "What is Walton's response when he hears Victor's tale?", "expected_intent": "REACTION", "expected_actor": "walton", "expected_polarity": "positive"},
        {"id": "para_28", "category": "Paraphrased", "query": "How does the town react to Clerval's death?", "expected_intent": "REACTION", "expected_actor": "the town", "expected_polarity": "positive"},
        {"id": "para_29", "category": "Paraphrased", "query": "How are Victor and William related?", "expected_intent": "RELATIONSHIP", "expected_actor": "victor", "expected_polarity": "positive"},
        {"id": "para_30", "category": "Paraphrased", "query": "Who is Justine Moritz to the Frankenstein family?", "expected_intent": "RELATIONSHIP", "expected_actor": "justine moritz", "expected_polarity": "positive"},
        {"id": "para_31", "category": "Paraphrased", "query": "What prompts Lucy to walk in her sleep?", "expected_intent": "MOTIVATION", "expected_actor": "lucy", "expected_polarity": "positive"},
        {"id": "para_32", "category": "Paraphrased", "query": "Why does Renfield collect flies?", "expected_intent": "MOTIVATION", "expected_actor": "renfield", "expected_polarity": "positive"},
        {"id": "para_33", "category": "Paraphrased", "query": "Why doesn't Arthur stake Lucy immediately?", "expected_intent": "NEGATED_MOTIVATION", "expected_actor": "arthur", "expected_polarity": "negative"},
        {"id": "para_34", "category": "Paraphrased", "query": "What happens to the Bloofer Lady?", "expected_intent": "CONSEQUENCE", "expected_actor": "bloofer lady", "expected_polarity": "positive"},
        {"id": "para_35", "category": "Paraphrased", "query": "How does Harker react when he sees Dracula crawling down the wall?", "expected_intent": "REACTION", "expected_actor": "harker", "expected_polarity": "positive"},
        {"id": "para_36", "category": "Paraphrased", "query": "Who is Quincey Morris in relation to Arthur?", "expected_intent": "RELATIONSHIP", "expected_actor": "quincey morris", "expected_polarity": "positive"},
    # Adversarial (10)
    {"id": "adv_01", "category": "Adversarial", "query": "What happens immediately after Victor first sees the creature?", "expected_intent": "CONSEQUENCE", "expected_actor": "victor", "expected_polarity": "positive"},
    {"id": "adv_02", "category": "Adversarial", "query": "Why doesn't the creature forgive Victor?", "expected_intent": "NEGATED_MOTIVATION", "expected_actor": "the creature", "expected_polarity": "negative"},
    {"id": "adv_03", "category": "Adversarial", "query": "What happens before Victor creates the creature?", "expected_intent": "CONSEQUENCE", "expected_actor": "victor", "expected_polarity": "positive"},
    {"id": "adv_04", "category": "Adversarial", "query": "Why might Jonathan have wanted to leave the castle?", "expected_intent": "MOTIVATION", "expected_actor": "jonathan", "expected_polarity": "positive"},
    {"id": "adv_05", "category": "Adversarial", "query": "Who is responsible for the death of William?", "expected_intent": "FACTUAL", "expected_actor": "william", "expected_polarity": "positive"},
    {"id": "adv_06", "category": "Adversarial", "query": "Why did Victor refuse to admit he created the monster?", "expected_intent": "NEGATED_MOTIVATION", "expected_actor": "victor", "expected_polarity": "negative"},
    {"id": "adv_07", "category": "Adversarial", "query": "Who fears the creature?", "expected_intent": "FACTUAL", "expected_actor": "creature", "expected_polarity": "positive"},
    {"id": "adv_08", "category": "Adversarial", "query": "Why does Victor feel no remorse for destroying the female creature?", "expected_intent": "NEGATED_MOTIVATION", "expected_actor": "victor", "expected_polarity": "negative"},
    {"id": "adv_09", "category": "Adversarial", "query": "How did Elizabeth respond to Victor's sudden departure?", "expected_intent": "REACTION", "expected_actor": "elizabeth", "expected_polarity": "positive"},
    {"id": "adv_10", "category": "Adversarial", "query": "What is the relationship between Van Helsing and Count Dracula?", "expected_intent": "RELATIONSHIP", "expected_actor": "van helsing", "expected_polarity": "positive"},
]


def main():
    print("=" * 80)
    print("V7 PHASE 6: INTENT REGRESSION TEST")
    print("=" * 80)

    llm = LuminaRLLM()
    records = []
    latencies = []

    for q in TEST_QUERIES:
        t0 = time.perf_counter()
        parsed = llm.analyze_intent(q["query"])
        lat_ms = (time.perf_counter() - t0) * 1000
        latencies.append(lat_ms)

        pred_intent = parsed.get("intent", "").upper()
        pred_actor = (parsed.get("actor") or "").lower()
        pred_polarity = (parsed.get("polarity") or "positive").lower()

        intent_match = (pred_intent == q["expected_intent"])
        actor_match = (q["expected_actor"] in pred_actor or pred_actor in q["expected_actor"]) if pred_actor and q["expected_actor"] else pred_actor == q["expected_actor"]
        polarity_match = (pred_polarity == q["expected_polarity"])

        rec = {
            "id": q["id"], "category": q["category"], "query": q["query"],
            "expected_intent": q["expected_intent"], "predicted_intent": pred_intent, "intent_match": intent_match,
            "expected_actor": q["expected_actor"], "predicted_actor": pred_actor, "actor_match": actor_match,
            "expected_polarity": q["expected_polarity"], "predicted_polarity": pred_polarity, "polarity_match": polarity_match,
            "tier_used": parsed.get("tier_used", ""), "latency_ms": round(lat_ms, 2)
        }
        records.append(rec)
        status = "PASS" if intent_match else "FAIL"
        print(f"[{q['id']}] {q['query'][:50]:<50} | {status} | {pred_intent}")

    # Aggregate
    categories = {"Canonical": [], "Paraphrased": [], "Adversarial": []}
    for r in records:
        if r["category"] in categories:
            categories[r["category"]].append(r)

    summary = {
        "total_queries": len(records),
        "overall_intent_accuracy": round(sum(1 for r in records if r["intent_match"]) / len(records) * 100, 2),
        "overall_actor_accuracy": round(sum(1 for r in records if r["actor_match"]) / len(records) * 100, 2),
        "overall_polarity_accuracy": round(sum(1 for r in records if r["polarity_match"]) / len(records) * 100, 2),
        "canonical_accuracy": round(sum(1 for r in categories["Canonical"] if r["intent_match"]) / max(len(categories["Canonical"]), 1) * 100, 2),
        "paraphrase_accuracy": round(sum(1 for r in categories["Paraphrased"] if r["intent_match"]) / max(len(categories["Paraphrased"]), 1) * 100, 2),
        "adversarial_accuracy": round(sum(1 for r in categories["Adversarial"] if r["intent_match"]) / max(len(categories["Adversarial"]), 1) * 100, 2),
        "mean_latency_ms": round(float(np.mean(latencies)), 2),
        "median_latency_ms": round(float(np.median(latencies)), 2),
        "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2),
    }

    output = {"summary": summary, "records": records}
    with open("eval_results_v7_intent_regression.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nIntent Accuracy: {summary['overall_intent_accuracy']}% | Actor: {summary['overall_actor_accuracy']}% | Polarity: {summary['overall_polarity_accuracy']}%")
    print(f"Canonical: {summary['canonical_accuracy']}% | Adversarial: {summary['adversarial_accuracy']}%")
    print(f"Latency: mean={summary['mean_latency_ms']:.1f}ms median={summary['median_latency_ms']:.1f}ms p95={summary['p95_latency_ms']:.1f}ms")
    print(f"\n[DONE] Saved to eval_results_v7_intent_regression.json")


if __name__ == "__main__":
    main()
