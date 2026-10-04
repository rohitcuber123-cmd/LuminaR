"""
V8 Step 3: Reason-Field Ablation

Tests three configurations of the validator on the 42-case adversarial dataset:
1. Full (current): reason field with max_new_tokens=160
2. Short: reason field with max_new_tokens=100 and a prompt restricting length
3. None: no reason field with max_new_tokens=80

Hypothesis: Removing or shortening the reason field will eliminate the 19 LLM_VALIDATOR_FALSE_NEGATIVE errors caused by token truncation.
"""
import json
import os
import sys
import time
import numpy as np
from pathlib import Path
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ["LUMINAR_MOCK_LLM"] = "0"

from rag.llm import LuminaRLLM
from rag.fast_filter import run_fast_filter
from lmformatenforcer import JsonSchemaParser
from lmformatenforcer.integrations.transformers import build_transformers_prefix_allowed_tokens_fn

from scratch.run_v8_step1_v7_reproduction import ADVERSARIAL_CASES

class ValidatorSchemaWithReason(BaseModel):
    supported: bool
    actor_match: bool
    event_match: bool
    target_match: bool
    polarity_match: bool
    temporal_match: bool
    relationship_match: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str

class ValidatorSchemaNoReason(BaseModel):
    supported: bool
    actor_match: bool
    event_match: bool
    target_match: bool
    polarity_match: bool
    temporal_match: bool
    relationship_match: bool
    confidence: float = Field(ge=0.0, le=1.0)


def build_prompt(config_name, question, intent_data, context_text):
    rules = (
        "- Evaluate each dimension (actor, event, target, polarity, temporal, relationship) independently.\n"
        "- For RELATIONSHIP queries, relationship_match=true ONLY when the evidence explicitly establishes the requested relationship.\n"
        "- For TEMPORAL queries, if the requested temporal direction conflicts with the evidence, temporal_match=false.\n"
        "- For NEGATED queries (e.g. why X does NOT do Y), if evidence shows X DOES Y, polarity_match=false.\n"
        "- Preserve subject/object directionality.\n"
        "- For unsupported premises, prefer false over speculative inference.\n"
        "- supported=true requires all relevant dimensions to match.\n"
    )

    if config_name == "Full":
        rules += "- 'reason' must be a short factual explanation based ONLY on the supplied evidence.\n\n"
    elif config_name == "Short":
        rules += "- 'reason' must be an EXTREMELY BRIEF factual explanation (MAXIMUM 20 WORDS) based ONLY on the supplied evidence.\n\n"
    elif config_name == "None":
        rules += "\n"

    prompt = (
        f"You are an evidence validation system evaluating if a text supports a structured query representation.\n"
        f"Question: {question}\n"
        f"Structured Intent: {intent_data}\n\n"
        f"Evidence Text:\n{context_text}\n\n"
        f"Rules:\n{rules}"
        "Does the provided evidence support the structured query? Respond ONLY with a valid JSON object matching the requested schema."
    )
    return prompt


def run_step3():
    print("=" * 80)
    print("V8 STEP 3: REASON-FIELD ABLATION")
    print("=" * 80)

    llm = LuminaRLLM()
    output_json = Path("reports/v8_experiment_b_reason_ablation.json")
    output_json.parent.mkdir(exist_ok=True)

    configs = [
        {"name": "Full", "schema": ValidatorSchemaWithReason, "max_tokens": 160},
        {"name": "Short", "schema": ValidatorSchemaWithReason, "max_tokens": 100},
        {"name": "None", "schema": ValidatorSchemaNoReason, "max_tokens": 80}
    ]

    all_results = {}

    for cfg in configs:
        name = cfg["name"]
        schema_model = cfg["schema"]
        max_tok = cfg["max_tokens"]
        
        print(f"\nEvaluating Config: {name} (max_tokens={max_tok})")
        print("-" * 40)
        
        records = []
        latencies = []
        truncation_count = 0
        
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
                context_text = used_items[0].get("text", "")
                prompt = build_prompt(name, c["question"], c["intent_data"], context_text)
                
                parser = JsonSchemaParser(schema_model.schema())
                prefix_function = build_transformers_prefix_allowed_tokens_fn(llm.tokenizer, parser)

                t0_llm = time.perf_counter()
                response = llm.generate(
                    prompt,
                    max_new_tokens=max_tok,
                    temperature=0.1,
                    prefix_allowed_tokens_fn=prefix_function
                )
                llm_lat = (time.perf_counter() - t0_llm) * 1000
                
                try:
                    import json
                    parsed = json.loads(response.strip())
                    final_decision = "SUPPORTED" if parsed.get("supported") else "NOT_SUPPORTED"
                except Exception as e:
                    print(f"[LLM ERROR] {name} parsing failed: {e}")
                    final_decision = "NOT_SUPPORTED"
                    truncation_count += 1

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

        correct = sum(1 for r in records if r["is_correct"])
        fps = sum(1 for r in records if not r["expected_supported"] and r["final_decision"] == "SUPPORTED")
        fns = sum(1 for r in records if r["expected_supported"] and r["final_decision"] == "NOT_SUPPORTED")
        
        llm_routed_latencies = [l for l in latencies if l > 0]
        mean_lat = float(np.mean(llm_routed_latencies)) if llm_routed_latencies else 0.0

        all_results[name] = {
            "accuracy_percent": round(correct / len(records) * 100, 2),
            "false_positives": fps,
            "false_negatives": fns,
            "truncation_errors": truncation_count,
            "mean_validation_latency_ms": round(mean_lat, 2),
            "records": records
        }
        
        print(f"  Accuracy: {all_results[name]['accuracy_percent']}% | FP: {fps} | FN: {fns} | Truncations: {truncation_count} | Latency: {all_results[name]['mean_validation_latency_ms']}ms")

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n[SAVED] {output_json}")

if __name__ == "__main__":
    run_step3()
