"""
V8 Step 2: Validator Schema Ablation

Tests three validator schemas on the 42-case adversarial dataset:
1. Full (V7 baseline): 9 fields (supported, actor_match, event_match, target_match, polarity_match, temporal_match, relationship_match, confidence, reason)
2. Intermediate: 4 fields (supported, polarity_match, confidence, reason)
3. Minimal: 2 fields (supported, confidence)

Hypothesis: Minimal schema will retain high accuracy while slashing latency.
"""
import json
import os
import sys
import time
import gc
import torch
import numpy as np
from pathlib import Path
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ["LUMINAR_MOCK_LLM"] = "0"

from rag.llm import LuminaRLLM
from rag.fast_filter import run_fast_filter
from lmformatenforcer import JsonSchemaParser
from lmformatenforcer.integrations.transformers import build_transformers_prefix_allowed_tokens_fn

# ============================================================
# ADVERSARIAL CASES (same 42 cases from V7)
# ============================================================
# We'll load them directly from the V7 script to avoid duplication
from scratch.run_v8_step1_v7_reproduction import ADVERSARIAL_CASES

# ============================================================
# TEMPORARY SCHEMAS
# ============================================================

class ValidatorSchemaFull(BaseModel):
    supported: bool
    actor_match: bool
    event_match: bool
    target_match: bool
    polarity_match: bool
    temporal_match: bool
    relationship_match: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str

class ValidatorSchemaIntermediate(BaseModel):
    supported: bool
    polarity_match: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str

class ValidatorSchemaMinimal(BaseModel):
    supported: bool
    confidence: float = Field(ge=0.0, le=1.0)


def build_prompt(schema_name, question, intent_data, context_text):
    if schema_name == "Full":
        rules = (
            "- Evaluate each dimension (actor, event, target, polarity, temporal, relationship) independently.\n"
            "- For RELATIONSHIP queries, relationship_match=true ONLY when the evidence explicitly establishes the requested relationship.\n"
            "- For TEMPORAL queries, if the requested temporal direction conflicts with the evidence, temporal_match=false.\n"
            "- For NEGATED queries (e.g. why X does NOT do Y), if evidence shows X DOES Y, polarity_match=false.\n"
            "- Preserve subject/object directionality.\n"
            "- For unsupported premises, prefer false over speculative inference.\n"
            "- supported=true requires all relevant dimensions to match.\n"
            "- 'reason' must be a short factual explanation based ONLY on the supplied evidence.\n\n"
        )
    elif schema_name == "Intermediate":
        rules = (
            "- For NEGATED queries (e.g. why X does NOT do Y), if evidence shows X DOES Y, polarity_match=false.\n"
            "- For unsupported premises, prefer false over speculative inference.\n"
            "- supported=true requires evidence to fully answer the query.\n"
            "- 'reason' must be a short factual explanation based ONLY on the supplied evidence.\n\n"
        )
    elif schema_name == "Minimal":
        rules = (
            "- For unsupported premises, prefer false over speculative inference.\n"
            "- supported=true requires evidence to fully answer the query, accounting for any negations or specific conditions.\n\n"
        )
    else:
        rules = ""

    prompt = (
        f"You are an evidence validation system evaluating if a text supports a structured query representation.\n"
        f"Question: {question}\n"
        f"Structured Intent: {intent_data}\n\n"
        f"Evidence Text:\n{context_text}\n\n"
        f"Rules:\n{rules}"
        "Does the provided evidence support the structured query? Respond ONLY with a valid JSON object matching the requested schema."
    )
    return prompt

def validate_evidence_custom(llm, schema_model, schema_name, question, intent_data, used_items):
    if not used_items:
        return {"verdict": "NOT_SUPPORTED", "details": {}}

    context_text = used_items[0].get("text", "")
    prompt = build_prompt(schema_name, question, intent_data, context_text)
    
    parser = JsonSchemaParser(schema_model.schema())
    prefix_function = build_transformers_prefix_allowed_tokens_fn(llm.tokenizer, parser)

    response = llm.generate(
        prompt,
        max_new_tokens=160,
        temperature=0.1,
        prefix_allowed_tokens_fn=prefix_function
    )
    
    try:
        parsed = json.loads(response.strip())
        verdict = "SUPPORTED" if parsed.get("supported") else "NOT_SUPPORTED"
        return {"verdict": verdict, "details": parsed}
    except Exception as e:
        print(f"[LLM ERROR] {schema_name} parsing failed: {e}")
        return {"verdict": "NOT_SUPPORTED", "details": {}}


def run_step2():
    print("=" * 80)
    print("V8 STEP 2: VALIDATOR SCHEMA ABLATION")
    print("=" * 80)

    llm = LuminaRLLM()
    output_json = Path("reports/v8_experiment_a_schema_ablation.json")
    output_json.parent.mkdir(exist_ok=True)

    schemas = {
        "Full": ValidatorSchemaFull,
        "Intermediate": ValidatorSchemaIntermediate,
        "Minimal": ValidatorSchemaMinimal
    }

    all_results = {}

    for schema_name, schema_model in schemas.items():
        print(f"\nEvaluating Schema: {schema_name}")
        print("-" * 40)
        
        records = []
        latencies = []
        
        for idx, c in enumerate(ADVERSARIAL_CASES, 1):
            used_items = [{"text": c["evidence"]}]
            
            # Fast filter
            ff_res = run_fast_filter(c["question"], c["intent_data"], used_items, mode="individual")
            ff_decision = ff_res["decision"]
            
            if ff_decision == "FAST_REJECT":
                final_decision = "NOT_SUPPORTED"
                llm_lat = 0
            elif ff_decision == "FAST_ACCEPT":
                final_decision = "SUPPORTED"
                llm_lat = 0
            else:
                t0_llm = time.perf_counter()
                llm_res = validate_evidence_custom(llm, schema_model, schema_name, c["question"], c["intent_data"], used_items)
                llm_lat = (time.perf_counter() - t0_llm) * 1000
                final_decision = llm_res["verdict"]

            latencies.append(llm_lat)
            expected_str = "SUPPORTED" if c["expected_supported"] else "NOT_SUPPORTED"
            is_correct = (final_decision == expected_str)

            records.append({
                "id": c["id"],
                "category": c["cat"],
                "expected_supported": c["expected_supported"],
                "final_decision": final_decision,
                "is_correct": is_correct,
                "latency_ms": llm_lat
            })

            if idx % 10 == 0:
                print(f"  Processed {idx}/{len(ADVERSARIAL_CASES)}...")

        # Calculate metrics for this schema
        correct = sum(1 for r in records if r["is_correct"])
        fps = sum(1 for r in records if not r["expected_supported"] and r["final_decision"] == "SUPPORTED")
        fns = sum(1 for r in records if r["expected_supported"] and r["final_decision"] == "NOT_SUPPORTED")
        unsup_detected = sum(1 for r in records if not r["expected_supported"] and r["final_decision"] == "NOT_SUPPORTED")
        unsup_total = sum(1 for r in records if not r["expected_supported"])
        
        # Only compute mean latency for cases routed to LLM (llm_lat > 0)
        llm_routed_latencies = [l for l in latencies if l > 0]
        mean_lat = float(np.mean(llm_routed_latencies)) if llm_routed_latencies else 0.0

        all_results[schema_name] = {
            "accuracy_percent": round(correct / len(records) * 100, 2),
            "false_positives": fps,
            "false_negatives": fns,
            "unsupported_rejection_percent": round(unsup_detected / unsup_total * 100, 2) if unsup_total else 0,
            "mean_validation_latency_ms": round(mean_lat, 2),
            "records": records
        }
        
        print(f"  Accuracy: {all_results[schema_name]['accuracy_percent']}% | FP: {fps} | FN: {fns} | Latency: {all_results[schema_name]['mean_validation_latency_ms']}ms")

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n[SAVED] {output_json}")

if __name__ == "__main__":
    run_step2()
