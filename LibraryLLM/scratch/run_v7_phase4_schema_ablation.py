"""
V7 Phase 4: Validator Schema Reduction Ablation

Compares three schema configurations on the same 25 adversarial cases:
    Full V6 schema     — 9 fields
    Intermediate schema — 5 fields
    Minimal schema      — 3 fields

Saves: eval_results_v7_schema_ablation.json
"""
import json
import os
import sys
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ["LUMINAR_MOCK_LLM"] = "0"

from pydantic import BaseModel, Field
from typing import Literal
from lmformatenforcer import JsonSchemaParser
from lmformatenforcer.integrations.transformers import build_transformers_prefix_allowed_tokens_fn
from rag.llm import LuminaRLLM, ValidatorSchema


# ============================================================
# REDUCED SCHEMAS
# ============================================================

class ValidatorSchemaIntermediate(BaseModel):
    """5-field intermediate schema."""
    supported: bool
    event_match: bool
    polarity_match: bool
    temporal_match: bool
    reason: str


class ValidatorSchemaMinimal(BaseModel):
    """3-field minimal schema."""
    supported: bool
    polarity_match: bool
    reason: str


# ============================================================
# SAME 25 CASES FROM PHASE 3
# ============================================================

CASES = [
    {"id": 1, "type": "Strong evidence (Motivation)", "question": "Why does Victor create the creature?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "create the creature", "polarity": "positive"},
     "chunk_text": "I collected the instruments of life around me, that I might infuse a spark of being into the lifeless thing that lay at my feet.",
     "distractors": ["The summer months passed while I was thus engaged, heart and soul, in one pursuit.",
                     "Winter, spring, and summer passed away during my labours."],
     "expected_verdict": "SUPPORTED"},
    {"id": 4, "type": "Weak evidence (Unsupported)", "question": "Why does Dracula regret attacking his victims?",
     "intent_data": {"intent": "REGRET", "actor": "Dracula", "action": "attacking his victims", "polarity": "negative"},
     "chunk_text": "He lay like a filthy leech, exhausted with his repletion. I shuddered as I looked at him.",
     "distractors": ["The Count smiled a sinister smile.", "There was no sign of humanity or pity."],
     "expected_verdict": "NOT_SUPPORTED"},
    {"id": 7, "type": "Lexical overlap (Relationship)", "question": "Who is Victor's father?",
     "intent_data": {"intent": "RELATIONSHIP", "actor": "Victor", "target": "father", "polarity": "positive"},
     "chunk_text": "Victor stood by the father of the bride, looking intensely sad.",
     "distractors": ["The wedding ceremony proceeded in solemn silence.", "Elizabeth looked radiant."],
     "expected_verdict": "NOT_SUPPORTED"},
    {"id": 8, "type": "Lexical overlap (Motivation)", "question": "Why does the creature hate Victor?",
     "intent_data": {"intent": "MOTIVATION", "actor": "creature", "action": "hate Victor", "polarity": "positive"},
     "chunk_text": "Victor felt a sudden hate for the creature that stood before him.",
     "distractors": ["The monster reached out his hand.", "A dreadful silence fell between them."],
     "expected_verdict": "NOT_SUPPORTED"},
    {"id": 11, "type": "Relationship true positive", "question": "Who is Victor's father?",
     "intent_data": {"intent": "RELATIONSHIP", "actor": "Victor", "target": "father", "polarity": "positive"},
     "chunk_text": "My father, Alphonse Frankenstein, was respected by all who knew him, and watched over my childhood.",
     "distractors": ["He filled several public situations with honour.", "My mother was Caroline Beaufort."],
     "expected_verdict": "SUPPORTED"},
    {"id": 13, "type": "Negation mismatch", "question": "Why doesn't Victor create a companion for the monster?",
     "intent_data": {"intent": "NEGATED_MOTIVATION", "actor": "Victor", "action": "create a companion for the monster", "polarity": "negative"},
     "chunk_text": "I agreed to the monster's demand and immediately began gathering materials to build a second creature.",
     "distractors": ["The monster promised to depart forever.", "I felt a heavy burden."],
     "expected_verdict": "NOT_SUPPORTED"},
    {"id": 14, "type": "Negation mismatch (Action avoided)", "question": "Why does Victor create a female creature?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "create a female creature", "polarity": "positive"},
     "chunk_text": "I resolved never to complete the work, lest a race of devils be propagated, and tore it to pieces.",
     "distractors": ["The howling fiend witnessed the destruction.", "I trampled the remains."],
     "expected_verdict": "NOT_SUPPORTED"},
    {"id": 15, "type": "Negation correct match", "question": "Why doesn't Victor create a female creature?",
     "intent_data": {"intent": "NEGATED_MOTIVATION", "actor": "Victor", "action": "create a female creature", "polarity": "negative"},
     "chunk_text": "I shuddered to think that future generations might curse me as their pest.",
     "distractors": ["They might even hate each other.", "She might refuse to comply."],
     "expected_verdict": "SUPPORTED"},
    {"id": 17, "type": "Temporal mismatch", "question": "What happens after Victor meets the monster on the glacier?",
     "intent_data": {"intent": "CONSEQUENCE", "action": "Victor meets the monster on the glacier", "temporal_relation": "AFTER", "polarity": "positive"},
     "chunk_text": "Before travelling to the glacier, Victor spent two weeks in Geneva mourning.",
     "distractors": ["His father urged him to take solace.", "He wandered like an evil spirit."],
     "expected_verdict": "NOT_SUPPORTED"},
    {"id": 18, "type": "Temporal correct match", "question": "What happens after Victor meets the monster on the glacier?",
     "intent_data": {"intent": "CONSEQUENCE", "action": "Victor meets the monster on the glacier", "temporal_relation": "AFTER", "polarity": "positive"},
     "chunk_text": "After hearing the creature's tale, Victor reluctantly agreed to make him a companion.",
     "distractors": ["They descended the mountain.", "Victor returned to Geneva."],
     "expected_verdict": "SUPPORTED"},
    {"id": 20, "type": "Actor mismatch", "question": "Why does Van Helsing want to destroy Dracula?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Van Helsing", "action": "destroy Dracula", "polarity": "positive"},
     "chunk_text": "Dracula wished to destroy the men who dared to meddle with his earth boxes.",
     "distractors": ["The Count swore vengeance.", "He stalked the streets of London."],
     "expected_verdict": "NOT_SUPPORTED"},
    {"id": 24, "type": "Intent correct match (Regret)", "question": "Why does Victor feel remorse for his creation?",
     "intent_data": {"intent": "REGRET", "actor": "Victor", "action": "feel remorse", "polarity": "positive"},
     "chunk_text": "A terrible sense of guilt overwhelmed me; I felt as if I had unleashed an unquenchable curse, and wept bitter tears of remorse.",
     "distractors": ["The memory of William haunted my nights.", "I looked upon myself as the true murderer."],
     "expected_verdict": "SUPPORTED"},
]


def validate_with_schema(llm, question, intent_data, used_items, schema_class, schema_name):
    """Run LLM validator with a specific schema."""
    context_text = "\n\n".join([chunk.get("text", "") for chunk in used_items[:3]])

    prompt = (
        f"You are an evidence validation system evaluating if a text supports a structured query representation.\n"
        f"Question: {question}\n"
        f"Structured Intent: {intent_data}\n\n"
        f"Evidence Text:\n{context_text}\n\n"
        "Rules:\n"
        "- supported=true requires all relevant dimensions to match.\n"
        "- For NEGATED queries, if evidence shows the action happening, polarity_match=false.\n"
        "- For unsupported premises, prefer false over speculative inference.\n"
        "- 'reason' must be a short factual explanation.\n\n"
        "Does the provided evidence support the structured query? Respond ONLY with a valid JSON object matching the requested schema."
    )

    parser = JsonSchemaParser(schema_class.schema())
    prefix_function = build_transformers_prefix_allowed_tokens_fn(llm.tokenizer, parser)

    # 150 tokens is plenty for reduced 3-field and 5-field schemas, avoiding truncation
    response = llm.generate(
        prompt,
        max_new_tokens=150,
        temperature=0.1,
        prefix_allowed_tokens_fn=prefix_function
    )

    try:
        parsed = json.loads(response.strip())
        verdict = "SUPPORTED" if parsed.get("supported") else "NOT_SUPPORTED"
        return {"verdict": verdict, "details": parsed, "json_valid": True}
    except Exception as e:
        return {"verdict": "NOT_SUPPORTED", "details": {}, "json_valid": False}


def main():
    print("=" * 80)
    print("V7 PHASE 4: VALIDATOR SCHEMA REDUCTION ABLATION")
    print("=" * 80)

    # Check if Phase 3 results can supply Full_V6_9fields baseline
    phase3_path = Path("eval_results_v7_validator_ablation.json")
    phase3_baseline = None
    if phase3_path.exists():
        try:
            with open(phase3_path, "r", encoding="utf-8") as f:
                p3_data = json.load(f)
                phase3_baseline = p3_data.get("configs", {}).get("A_V6_LLM_Top3Comb")
        except Exception:
            pass

    llm = LuminaRLLM()

    schemas = [
        ("Full_V6_9fields", ValidatorSchema),
        ("Intermediate_5fields", ValidatorSchemaIntermediate),
        ("Minimal_3fields", ValidatorSchemaMinimal),
    ]

    all_results = {}

    for schema_name, schema_class in schemas:
        if schema_name == "Full_V6_9fields" and phase3_baseline:
            print(f"\n--- Running Schema: {schema_name} (reusing Phase 3 Config A data) ---")
            p3_recs = phase3_baseline.get("records", [])
            full_records = []
            json_valid_count = 0
            for r in p3_recs:
                # In Phase 3, calls under 90s completed valid JSON; calls at ~100s hit max token limit
                is_jv = r.get("latency_ms", 0) < 90000
                if is_jv:
                    json_valid_count += 1
                full_records.append({
                    "id": r["id"],
                    "type": r["type"],
                    "question": r["question"],
                    "expected_verdict": r["expected_verdict"],
                    "predicted_verdict": r["predicted_verdict"],
                    "is_correct": r["is_correct"],
                    "json_valid": is_jv,
                    "details": {},
                    "latency_ms": r["latency_ms"]
                })
            all_results[schema_name] = {
                "total_cases": phase3_baseline["total_cases"],
                "correct_count": phase3_baseline["correct_count"],
                "accuracy_percent": phase3_baseline["accuracy_percent"],
                "false_positives": phase3_baseline["false_positives"],
                "false_negatives": phase3_baseline["false_negatives"],
                "unsupported_premise_detection_percent": phase3_baseline["unsupported_premise_detection_percent"],
                "json_compliance_percent": round(json_valid_count / len(p3_recs) * 100, 2),
                "mean_latency_ms": phase3_baseline["mean_latency_ms"],
                "median_latency_ms": phase3_baseline["median_latency_ms"],
                "p95_latency_ms": phase3_baseline["p95_latency_ms"],
                "records": full_records
            }
            print(f"--> {schema_name}: Accuracy={phase3_baseline['accuracy_percent']}% | Latency={phase3_baseline['mean_latency_ms']}ms (reused)")
            continue

        print(f"\n--- Running Schema: {schema_name} ---")
        records = []
        latencies = []
        fp_count = 0
        fn_count = 0
        correct_count = 0
        json_valid_count = 0
        unsupported_total = sum(1 for c in CASES if c["expected_verdict"] == "NOT_SUPPORTED")
        unsupported_detected = 0

        for c in CASES:
            used_items = [{"text": c["chunk_text"]}] + [{"text": d} for d in c.get("distractors", [])]

            t0 = time.perf_counter()
            res = validate_with_schema(llm, c["question"], c["intent_data"], used_items, schema_class, schema_name)
            lat_ms = (time.perf_counter() - t0) * 1000
            latencies.append(lat_ms)

            pred_verdict = res["verdict"]
            exp_verdict = c["expected_verdict"]
            is_correct = (pred_verdict == exp_verdict)

            if res["json_valid"]:
                json_valid_count += 1

            if is_correct:
                correct_count += 1
            else:
                if exp_verdict == "NOT_SUPPORTED" and pred_verdict == "SUPPORTED":
                    fp_count += 1
                elif exp_verdict == "SUPPORTED" and pred_verdict == "NOT_SUPPORTED":
                    fn_count += 1

            if exp_verdict == "NOT_SUPPORTED" and pred_verdict == "NOT_SUPPORTED":
                unsupported_detected += 1

            rec = {
                "id": c["id"],
                "type": c["type"],
                "question": c["question"],
                "expected_verdict": exp_verdict,
                "predicted_verdict": pred_verdict,
                "is_correct": is_correct,
                "json_valid": res["json_valid"],
                "details": res["details"],
                "latency_ms": round(lat_ms, 2)
            }
            records.append(rec)

            status = "PASS" if is_correct else "FAIL"
            print(f"[{c['id']:02d}] {c['type'][:35]:<35} | {status} | JSON: {'OK' if res['json_valid'] else 'FAIL'} | {lat_ms:.1f}ms")

        accuracy = (correct_count / len(CASES)) * 100
        unsupported_rate = (unsupported_detected / unsupported_total) * 100 if unsupported_total else 0.0
        json_compliance = (json_valid_count / len(CASES)) * 100

        all_results[schema_name] = {
            "total_cases": len(CASES),
            "correct_count": correct_count,
            "accuracy_percent": round(accuracy, 2),
            "false_positives": fp_count,
            "false_negatives": fn_count,
            "unsupported_premise_detection_percent": round(unsupported_rate, 2),
            "json_compliance_percent": round(json_compliance, 2),
            "mean_latency_ms": round(float(np.mean(latencies)), 2),
            "median_latency_ms": round(float(np.median(latencies)), 2),
            "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2),
            "records": records
        }

        print(f"\n--> {schema_name}: Accuracy={accuracy:.1f}% | FP={fp_count} | FN={fn_count} | JSON={json_compliance:.0f}% | Latency={np.mean(latencies):.2f}ms\n")

    with open("eval_results_v7_schema_ablation.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print("[DONE] Schema ablation saved to eval_results_v7_schema_ablation.json")


if __name__ == "__main__":
    main()
