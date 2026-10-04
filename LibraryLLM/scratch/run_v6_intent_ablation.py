import json
import os
import sys
import time
import re
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from rag.llm import LuminaRLLM, IntentSchema
from lmformatenforcer import JsonSchemaParser
from lmformatenforcer.integrations.transformers import build_transformers_prefix_allowed_tokens_fn

def extract_tier1(question):
    low_q = question.lower().strip()
    result = {
        "intent": "FACTUAL",
        "actor": None,
        "action": None,
        "target": None,
        "polarity": "positive",
        "temporal_relation": None,
        "question_focus": None,
        "tier_used": "Tier 1"
    }
    verbs = r"(create|refuse|decide|regret|feel|sees?|hate|study|attack|leave|bitten)"
    m_neg_1 = re.search(rf"why\s+(?:doesn't|didn't|does\s+not|did\s+not)\s+(.*?)\s+{verbs}\b(.*)", low_q)
    m_neg_2 = re.search(rf"why\s+(?:does|did)\s+(.*?)\s+(refuse|avoid|decline|decide)\b(.*)", low_q)
    m_reg_1 = re.search(rf"why\s+(?:does|did)\s+(.*?)\s+(regret|feel\s+remorse)\b(.*)", low_q)
    m_mot_1 = re.search(rf"why\s+(?:does|did)\s+(.*?)\s+{verbs}\b(.*)", low_q)
    m_mot_2 = re.search(r"what\s+motivates\s+(.*?)\s+to\s+(.*)", low_q)
    m_cons = re.search(r"what\s+happens\s+after\s+(.*)", low_q)
    m_react = re.search(r"what\s+happens\s+when\s+(.*?)\s+first\s+(.*)", low_q)
    m_rel_1 = re.search(r"who\s+is\s+(.*?)'s\s+(.*)", low_q)
    m_rel_2 = re.search(r"who\s+is\s+(.*?)\s+to\s+(.*)", low_q)

    if m_neg_1:
        result["intent"] = "NEGATED_MOTIVATION"
        result["actor"] = m_neg_1.group(1).strip()
        result["action"] = (m_neg_1.group(2) + m_neg_1.group(3)).strip("?")
        result["polarity"] = "negative"
    elif m_neg_2:
        result["intent"] = "NEGATED_MOTIVATION"
        result["actor"] = m_neg_2.group(1).strip()
        result["action"] = (m_neg_2.group(2) + m_neg_2.group(3)).strip("?")
        result["polarity"] = "negative"
    elif m_reg_1:
        result["intent"] = "REGRET"
        result["actor"] = m_reg_1.group(1).strip()
        result["action"] = (m_reg_1.group(2) + m_reg_1.group(3)).strip("?")
        result["polarity"] = "negative"
    elif m_mot_1:
        result["intent"] = "MOTIVATION"
        result["actor"] = m_mot_1.group(1).strip()
        result["action"] = (m_mot_1.group(2) + m_mot_1.group(3)).strip("?")
    elif m_mot_2:
        result["intent"] = "MOTIVATION"
        result["actor"] = m_mot_2.group(1).strip()
        result["action"] = m_mot_2.group(2).strip("?")
    elif m_cons:
        result["intent"] = "CONSEQUENCE"
        result["action"] = m_cons.group(1).strip("?")
    elif m_react:
        result["intent"] = "REACTION"
        result["actor"] = m_react.group(1).strip()
        result["action"] = m_react.group(2).strip("?")
    elif m_rel_1:
        result["intent"] = "RELATIONSHIP"
        result["actor"] = m_rel_1.group(1).strip()
        result["target"] = m_rel_1.group(2).strip("?")
    elif m_rel_2:
        result["intent"] = "RELATIONSHIP"
        result["actor"] = m_rel_2.group(1).strip()
        result["target"] = m_rel_2.group(2).strip("?")
    return result

def extract_tier2(llm, question):
    prompt = (
        "Analyze the following question and extract its semantic intent and components.\n"
        "Supported intents and explicit boundaries:\n"
        "- MOTIVATION: Why does X do Y? (e.g., Why did he leave?)\n"
        "- NEGATED_MOTIVATION: Why doesn't X do Y? What prevents X from doing Y? (e.g., Why did he refuse?)\n"
        "  * NOTE: Words like 'reject' or 'refuse' as the action do NOT automatically make it NEGATED_MOTIVATION unless it means avoiding an action.\n"
        "- REGRET: Why does X regret Y? What makes X remorseful about Y?\n"
        "  * NOTE: REGRET must ONLY represent remorse, guilt, or regret. Do NOT classify hatred, killing, rejection, fear, or ordinary negative actions as REGRET unless explicitly asking about remorse.\n"
        "- CONSEQUENCE: What happens after X does Y? What follows an event.\n"
        "- REACTION: How does X react when Y happens? What does X feel/do upon seeing Y? (Response to an event).\n"
        "- RELATIONSHIP: Who is X to Y? What is the relationship between X and Y? (Explicit relationship).\n"
        "- FACTUAL: What is/was X? What fact does the text state about X?\n\n"
        "Additional Extraction Rules:\n"
        "- You MUST populate 'actor', 'action', and 'target' whenever the query provides enough information. Do NOT leave them null if the entity or action is present.\n"
        "- TEMPORAL: Explicitly represent temporal_relation as BEFORE, AFTER, DURING, or NONE.\n"
        "- POLARITY: POSITIVE, NEGATED, or UNKNOWN.\n"
        "- CONFIDENCE: A float from 0.0 to 1.0 representing your certainty.\n\n"
        f"Question: {question}\n\n"
        "Respond ONLY with a valid JSON object matching the requested schema."
    )
    parser = JsonSchemaParser(IntentSchema.schema())
    prefix_function = build_transformers_prefix_allowed_tokens_fn(llm.tokenizer, parser)
    response = llm.generate(
        prompt,
        max_new_tokens=400,
        temperature=0.1,
        prefix_allowed_tokens_fn=prefix_function
    )
    try:
        parsed = json.loads(response.strip())
        parsed["tier_used"] = "Tier 2"
        return parsed
    except Exception as e:
        return {"intent": "FACTUAL", "confidence": 0.0, "tier_used": "Tier 2"}

def main():
    print("=" * 80)
    print("V6 PHASE 6: INTENT EXTRACTION ABLATION STUDY")
    print("=" * 80)

    llm = LuminaRLLM()

    # Ground truth dataset with pre-established annotations
    test_queries = [
        # --- CANONICAL (18) ---
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

        # --- ADVERSARIAL (10) ---
        {"id": "adv_01", "category": "Adversarial", "query": "What happens immediately after Victor first sees the creature?", "expected_intent": "CONSEQUENCE", "expected_actor": "victor", "expected_polarity": "positive"},
        {"id": "adv_02", "category": "Adversarial", "query": "Why doesn't the creature forgive Victor?", "expected_intent": "NEGATED_MOTIVATION", "expected_actor": "the creature", "expected_polarity": "negative"},
        {"id": "adv_03", "category": "Adversarial", "query": "What happens before Victor creates the creature?", "expected_intent": "CONSEQUENCE", "expected_actor": "victor", "expected_polarity": "positive"},
        {"id": "adv_04", "category": "Adversarial", "query": "Why might Jonathan have wanted to leave the castle?", "expected_intent": "MOTIVATION", "expected_actor": "jonathan", "expected_polarity": "positive"},
        {"id": "adv_05", "category": "Adversarial", "query": "Who is responsible for the death of William?", "expected_intent": "FACTUAL", "expected_actor": "william", "expected_polarity": "positive"},
        {"id": "adv_06", "category": "Adversarial", "query": "Why did Victor refuse to admit he created the monster?", "expected_intent": "NEGATED_MOTIVATION", "expected_actor": "victor", "expected_polarity": "negative"},
        {"id": "adv_07", "category": "Adversarial", "query": "Who fears the creature?", "expected_intent": "FACTUAL", "expected_actor": "creature", "expected_polarity": "positive"},
        {"id": "adv_08", "category": "Adversarial", "query": "Why does Victor feel no remorse for destroying the female creature?", "expected_intent": "NEGATED_MOTIVATION", "expected_actor": "victor", "expected_polarity": "negative"},
        {"id": "adv_09", "category": "Adversarial", "query": "How did Elizabeth respond to Victor's sudden departure?", "expected_intent": "REACTION", "expected_actor": "elizabeth", "expected_polarity": "positive"},
        {"id": "adv_10", "category": "Adversarial", "query": "What is the relationship between Van Helsing and Count Dracula?", "expected_intent": "RELATIONSHIP", "expected_actor": "van helsing", "expected_polarity": "positive"}
    ]

    modes = ["tier1_only", "tier2_only", "hybrid"]
    ablation_results = {}

    for mode in modes:
        print(f"\n--- Running Intent Mode: {mode} ---")
        mode_records = []
        latencies = []

        for q in test_queries:
            t0 = time.perf_counter()

            if mode == "tier1_only":
                parsed = extract_tier1(q["query"])
                tier_used = "Tier 1"
            elif mode == "tier2_only":
                parsed = extract_tier2(llm, q["query"])
                tier_used = "Tier 2"
            else:
                parsed = llm.analyze_intent(q["query"])
                tier_used = parsed.get("tier_used", "Tier 2")

            lat_ms = (time.perf_counter() - t0) * 1000
            latencies.append(lat_ms)

            pred_intent = parsed.get("intent", "").upper()
            pred_actor = (parsed.get("actor") or "").lower()
            pred_polarity = (parsed.get("polarity") or "positive").lower()

            exp_intent = q["expected_intent"].upper()
            exp_actor = q["expected_actor"].lower()
            exp_polarity = q["expected_polarity"].lower()

            intent_match = (pred_intent == exp_intent)
            actor_match = (exp_actor in pred_actor or pred_actor in exp_actor) if (pred_actor and exp_actor) else (pred_actor == exp_actor)
            polarity_match = (pred_polarity == exp_polarity)

            rec = {
                "id": q["id"],
                "category": q["category"],
                "query": q["query"],
                "expected_intent": exp_intent,
                "predicted_intent": pred_intent,
                "intent_match": intent_match,
                "expected_actor": exp_actor,
                "predicted_actor": pred_actor,
                "actor_match": actor_match,
                "expected_polarity": exp_polarity,
                "predicted_polarity": pred_polarity,
                "polarity_match": polarity_match,
                "tier_used": tier_used,
                "confidence": parsed.get("confidence", 1.0),
                "latency_ms": round(lat_ms, 2)
            }
            mode_records.append(rec)

        # Aggregate metrics for this mode
        categories = ["Canonical", "Paraphrased", "Adversarial"]
        cat_acc = {}
        for cat in categories:
            cat_recs = [r for r in mode_records if r["category"] == cat]
            acc = sum(1 for r in cat_recs if r["intent_match"]) / len(cat_recs) if cat_recs else 0.0
            cat_acc[cat] = round(acc * 100, 2)

        total_intent_acc = sum(1 for r in mode_records if r["intent_match"]) / len(mode_records) * 100
        total_actor_acc = sum(1 for r in mode_records if r["actor_match"]) / len(mode_records) * 100
        total_polarity_acc = sum(1 for r in mode_records if r["polarity_match"]) / len(mode_records) * 100

        ablation_results[mode] = {
            "canonical_accuracy": cat_acc["Canonical"],
            "paraphrase_accuracy": cat_acc["Paraphrased"],
            "adversarial_accuracy": cat_acc["Adversarial"],
            "overall_intent_accuracy": round(total_intent_acc, 2),
            "overall_actor_accuracy": round(total_actor_acc, 2),
            "overall_polarity_accuracy": round(total_polarity_acc, 2),
            "mean_latency_ms": round(float(np.mean(latencies)), 2),
            "median_latency_ms": round(float(np.median(latencies)), 2),
            "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2),
            "records": mode_records
        }

        print(f"Results for {mode}: Canonical={cat_acc['Canonical']}% | Para={cat_acc['Paraphrased']}% | Adv={cat_acc['Adversarial']}% | Latency(mean)={np.mean(latencies):.2f}ms")

    with open("eval_results_v6_intent_ablation.json", "w", encoding="utf-8") as f:
        json.dump(ablation_results, f, indent=2)

    print("\n[DONE] Intent ablation saved to eval_results_v6_intent_ablation.json")

if __name__ == "__main__":
    main()
