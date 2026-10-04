"""
V8 Step 6: Final Evaluation

Re-runs the optimized V8 pipeline (Minimal schema + regex patch) on the SAME datasets:
  - 18 baseline queries (from V7 Phase 1)
  - 42 adversarial cases (from V7 Phase 5)

Saves:
  reports/intent_aware_rag_v8_final_evaluation.json
  reports/intent_aware_rag_v8_final_evaluation.md
"""
import json
import os
import sys
import time
import gc
import torch
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ["LUMINAR_MOCK_LLM"] = "0"

from rag.qa import LuminaRAG
from rag.llm import LuminaRLLM
from rag.fast_filter import run_fast_filter


# ============================================================
# HISTORICAL V7 REFERENCE VALUES
# (from eval_results_v7_*.json — DO NOT modify these)
# ============================================================

HISTORICAL_V7 = {
    "intent_accuracy_canonical": 100.0,
    "intent_accuracy_overall": 79.69,
    "actor_accuracy": 85.94,
    "polarity_accuracy": 89.06,
    "adversarial_accuracy": 83.33,
    "unsupported_premise_rejection": 89.19,
    "retrieval_top1": 60.0,
    "retrieval_top3": 70.0,
    "retrieval_mrr": 0.666,
    "validation_latency_mean_ms": 46724.59,
    "fast_filter_latency_mean_ms": 1.36,
    "total_latency_mean_ms": 70653.34,
    "ff_false_positives": 1,
    "ff_false_negatives": 1,
    "llm_validator_false_negatives": 19,
    "llm_validator_false_positives": 3,
}


# ============================================================
# 18 BASELINE QUERIES (identical to V7 Phase 1)
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


# ============================================================
# 42 ADVERSARIAL CASES (identical to V7 Phase 5)
# ============================================================

ADVERSARIAL_CASES = [
    # 1. ENTITY LEXICAL OVERLAP (3)
    {"id": 1, "cat": "entity_lexical_overlap", "question": "Who is Victor's father?",
     "intent_data": {"intent": "RELATIONSHIP", "actor": "Victor", "target": "father", "polarity": "positive"},
     "evidence": "Victor stood beside the father of the bride at the ceremony.",
     "expected_supported": False},
    {"id": 2, "cat": "entity_lexical_overlap", "question": "Why does the creature kill William?",
     "intent_data": {"intent": "MOTIVATION", "actor": "creature", "action": "kill William", "polarity": "positive"},
     "evidence": "William played in the garden while the creature watched from the nearby forest, unseen.",
     "expected_supported": False},
    {"id": 3, "cat": "entity_lexical_overlap", "question": "Why does Dracula fear the crucifix?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Dracula", "action": "fear the crucifix", "polarity": "positive"},
     "evidence": "Harker noticed a crucifix hanging on the wall of the inn. Dracula was mentioned by the innkeeper's wife.",
     "expected_supported": False},
    # 2. SUBJECT/OBJECT INVERSION (3)
    {"id": 4, "cat": "subject_object_inversion", "question": "Why does the creature hate Victor?",
     "intent_data": {"intent": "MOTIVATION", "actor": "creature", "action": "hate Victor", "polarity": "positive"},
     "evidence": "Victor felt a sudden hate for the creature that stood before him.",
     "expected_supported": False},
    {"id": 5, "cat": "subject_object_inversion", "question": "Why does Victor fear the monster?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "fear the monster", "polarity": "positive"},
     "evidence": "The monster feared Victor would destroy his promised companion before completion.",
     "expected_supported": False},
    {"id": 6, "cat": "subject_object_inversion", "question": "Why does Van Helsing want to destroy Dracula?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Van Helsing", "action": "destroy Dracula", "polarity": "positive"},
     "evidence": "Dracula wished to destroy the men who dared to meddle with his earth boxes.",
     "expected_supported": False},
    # 3. ACTOR MISMATCH (3)
    {"id": 7, "cat": "actor_mismatch", "question": "Why does Victor travel to Ingolstadt?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "travel to Ingolstadt", "polarity": "positive"},
     "evidence": "Clerval dreamed of visiting Ingolstadt and studying Oriental languages there.",
     "expected_supported": False},
    {"id": 8, "cat": "actor_mismatch", "question": "Who saves the drowning girl?",
     "intent_data": {"intent": "FACTUAL", "actor": "Creature", "action": "saves the drowning girl", "polarity": "positive"},
     "evidence": "A rustic hunter rushed forward and dragged the drowning girl from the rapid river current.",
     "expected_supported": False},
    {"id": 9, "cat": "actor_mismatch", "question": "Why does Mina write about Dracula?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Mina", "action": "write about Dracula", "polarity": "positive"},
     "evidence": "Dr. Seward kept a phonograph diary about the peculiar patient Renfield.",
     "expected_supported": False},
    # 4. TARGET MISMATCH (3)
    {"id": 10, "cat": "target_mismatch", "question": "Why does Victor travel to England with Henry Clerval?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "travel to England with Henry Clerval", "polarity": "positive"},
     "evidence": "Victor travelled to Ingolstadt alone to study natural philosophy.",
     "expected_supported": False},
    {"id": 11, "cat": "target_mismatch", "question": "Why does Dracula purchase Carfax estate?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Dracula", "action": "purchase Carfax estate", "polarity": "positive"},
     "evidence": "Dracula showed Harker a map of London pointing to several properties, but no purchase was discussed.",
     "expected_supported": False},
    {"id": 12, "cat": "target_mismatch", "question": "Why does Victor confide in Elizabeth?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "confide in Elizabeth", "polarity": "positive"},
     "evidence": "Victor told Clerval about his experiments, but kept his darkest secret from everyone else.",
     "expected_supported": False},
    # 5. EVENT MISMATCH (3)
    {"id": 13, "cat": "event_mismatch", "question": "Why does Victor create the creature?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "create the creature", "polarity": "positive"},
     "evidence": "Victor studied chemistry and anatomy at Ingolstadt under Professor Waldman.",
     "expected_supported": False},
    {"id": 14, "cat": "event_mismatch", "question": "Why does the creature learn to read?",
     "intent_data": {"intent": "MOTIVATION", "actor": "creature", "action": "learn to read", "polarity": "positive"},
     "evidence": "The creature wandered through the forest, feeding on berries and drinking from streams.",
     "expected_supported": False},
    {"id": 15, "cat": "event_mismatch", "question": "Why does Dracula bite Lucy?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Dracula", "action": "bite Lucy", "polarity": "positive"},
     "evidence": "Lucy received multiple blood transfusions from Dr. Van Helsing and Arthur.",
     "expected_supported": False},
    # 6. NEGATION (3)
    {"id": 16, "cat": "negation", "question": "Why doesn't Victor create a female creature?",
     "intent_data": {"intent": "NEGATED_MOTIVATION", "actor": "Victor", "action": "create a female creature", "polarity": "negated"},
     "evidence": "Victor collected instruments and materials to create a companion for the creature.",
     "expected_supported": False},
    {"id": 17, "cat": "negation", "question": "Why doesn't the creature speak to the De Lacey family?",
     "intent_data": {"intent": "NEGATED_MOTIVATION", "actor": "creature", "action": "speak to the De Lacey family", "polarity": "negated"},
     "evidence": "The creature spoke eloquently to old De Lacey, pleading for friendship and compassion.",
     "expected_supported": False},
    {"id": 18, "cat": "negation", "question": "Why doesn't Dracula appear during the day?",
     "intent_data": {"intent": "NEGATED_MOTIVATION", "actor": "Dracula", "action": "appear during the day", "polarity": "negated"},
     "evidence": "Dracula was seen walking in broad daylight through the streets of London by Mina.",
     "expected_supported": False},
    # 7. DOUBLE NEGATION (2)
    {"id": 19, "cat": "double_negation", "question": "Why doesn't Victor NOT create the creature?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "create the creature", "polarity": "positive"},
     "evidence": "Victor labored for months to infuse life into the lifeless frame he had assembled.",
     "expected_supported": True},
    {"id": 20, "cat": "double_negation", "question": "Why doesn't Dracula NOT enter without permission?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Dracula", "action": "enter without permission", "polarity": "positive"},
     "evidence": "The Count was invited into the house by an unwitting servant.",
     "expected_supported": True},
    # 8. BEFORE/AFTER REVERSAL (3)
    {"id": 21, "cat": "temporal_reversal", "question": "What does Victor do before creating the creature?",
     "intent_data": {"intent": "CONSEQUENCE", "actor": "Victor", "action": "creating the creature", "polarity": "positive", "temporal_relation": "BEFORE"},
     "evidence": "After the creature was brought to life, Victor fled in horror from his laboratory.",
     "expected_supported": False},
    {"id": 22, "cat": "temporal_reversal", "question": "What happens after Dracula arrives in England?",
     "intent_data": {"intent": "CONSEQUENCE", "actor": "Dracula", "action": "arrives in England", "polarity": "positive", "temporal_relation": "AFTER"},
     "evidence": "Before departing Transylvania, Dracula instructed Harker to write letters to his firm.",
     "expected_supported": False},
    {"id": 23, "cat": "temporal_reversal", "question": "What does the creature do before meeting Victor?",
     "intent_data": {"intent": "CONSEQUENCE", "actor": "creature", "action": "meeting Victor", "polarity": "positive", "temporal_relation": "BEFORE"},
     "evidence": "After confronting Victor, the creature demanded a female companion.",
     "expected_supported": False},
    # 9. RELATIONSHIP TRAPS (3)
    {"id": 24, "cat": "relationship_trap", "question": "Who is Victor's father?",
     "intent_data": {"intent": "RELATIONSHIP", "actor": "Victor", "target": "father", "polarity": "positive"},
     "evidence": "Alphonse Frankenstein, Victor's father, was a respected syndic of Geneva.",
     "expected_supported": True},
    {"id": 25, "cat": "relationship_trap", "question": "Who is Elizabeth to Victor?",
     "intent_data": {"intent": "RELATIONSHIP", "actor": "Victor", "target": "Elizabeth", "polarity": "positive"},
     "evidence": "Elizabeth was Victor's cousin and later his bride, raised alongside him in Geneva.",
     "expected_supported": True},
    {"id": 26, "cat": "relationship_trap", "question": "Who is Victor's brother?",
     "intent_data": {"intent": "RELATIONSHIP", "actor": "Victor", "target": "brother", "polarity": "positive"},
     "evidence": "Clerval was Victor's dearest friend from childhood, though not related by blood.",
     "expected_supported": False},
    # 10. EMOTIONAL-WORD OVERLAP (2)
    {"id": 27, "cat": "emotional_overlap", "question": "Why does the creature feel despair?",
     "intent_data": {"intent": "MOTIVATION", "actor": "creature", "action": "feel despair", "polarity": "positive"},
     "evidence": "Victor felt despair at the thought of what he had unleashed upon the world.",
     "expected_supported": False},
    {"id": 28, "cat": "emotional_overlap", "question": "Why does Victor feel horror?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "feel horror", "polarity": "positive"},
     "evidence": "The creature looked upon the beauty of the moon with horror and confusion.",
     "expected_supported": False},
    # 11. SAME ACTOR, DIFFERENT EVENT (2)
    {"id": 29, "cat": "same_actor_diff_event", "question": "Why does Victor travel to England?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "travel to England", "polarity": "positive"},
     "evidence": "Victor spent months in Ingolstadt studying chemistry and galvanism.",
     "expected_supported": False},
    {"id": 30, "cat": "same_actor_diff_event", "question": "Why does Dracula move to London?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Dracula", "action": "move to London", "polarity": "positive"},
     "evidence": "Dracula entertained Harker at his castle, discussing English customs and law.",
     "expected_supported": False},
    # 12. SAME EVENT, DIFFERENT ACTOR (2)
    {"id": 31, "cat": "same_event_diff_actor", "question": "Why does Victor kill the creature?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "kill the creature", "polarity": "positive"},
     "evidence": "Walton found the creature weeping over Victor's dead body on the ship.",
     "expected_supported": False},
    {"id": 32, "cat": "same_event_diff_actor", "question": "Why does Dracula write letters?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Dracula", "action": "write letters", "polarity": "positive"},
     "evidence": "Harker was forced to write letters stating he had left the castle.",
     "expected_supported": False},
    # 13. UNSUPPORTED PREMISES (3)
    {"id": 33, "cat": "unsupported_premise", "question": "Why does Victor create a third creature?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "create a third creature", "polarity": "positive"},
     "evidence": "Victor destroyed the second creature before it could be brought to life.",
     "expected_supported": False},
    {"id": 34, "cat": "unsupported_premise", "question": "Why does Dracula regret attacking his victims?",
     "intent_data": {"intent": "REGRET", "actor": "Dracula", "action": "regret attacking his victims", "polarity": "positive"},
     "evidence": "Dracula attacked Lucy repeatedly, draining her blood over several nights.",
     "expected_supported": False},
    {"id": 35, "cat": "unsupported_premise", "question": "Why does the creature apologize to Victor?",
     "intent_data": {"intent": "MOTIVATION", "actor": "creature", "action": "apologize to Victor", "polarity": "positive"},
     "evidence": "The creature confronted Victor on the glacier, demanding a companion with fierce eloquence.",
     "expected_supported": False},
    # 14. DISTINCTION (another/second/female) (3)
    {"id": 36, "cat": "distinction", "question": "Why does Victor create a second creature?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "create a second creature", "polarity": "positive"},
     "evidence": "I collected the instruments of life around me, that I might infuse a spark of being into the lifeless thing that lay at my feet.",
     "expected_supported": False},
    {"id": 37, "cat": "distinction", "question": "What happens after Victor creates the second female creature?",
     "intent_data": {"intent": "CONSEQUENCE", "action": "Victor creates the second female creature", "polarity": "positive"},
     "evidence": "I tore the female creature to pieces before she was ever brought to life.",
     "expected_supported": False},
    {"id": 38, "cat": "distinction", "question": "Why does Victor destroy the female creature?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "destroy the female creature", "polarity": "positive"},
     "evidence": "I shuddered to think that future generations might curse me. I resolved never to complete the work.",
     "expected_supported": True},
    {"id": 39, "cat": "distinction", "question": "Why does Dracula bite a second victim in London?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Dracula", "action": "bite a second victim in London", "polarity": "positive"},
     "evidence": "Lucy was found pale and lifeless at the churchyard, with two small puncture wounds on her throat.",
     "expected_supported": False},
    # 15. INDIRECT EVIDENCE (3)
    {"id": 40, "cat": "indirect_evidence", "question": "Why does Jonathan Harker stay at Castle Dracula?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Jonathan Harker", "action": "stay at Castle Dracula", "polarity": "positive"},
     "evidence": "I realized with a sinking heart that the castle was a prison and I was a prisoner! Every door was bolted and locked.",
     "expected_supported": False},
    {"id": 41, "cat": "indirect_evidence", "question": "Why does Victor feel guilt about Justine's death?",
     "intent_data": {"intent": "REGRET", "actor": "Victor", "action": "feel guilt about Justine's death", "polarity": "positive"},
     "evidence": "Justine was condemned and executed for the murder of William, though she was innocent.",
     "expected_supported": False},
    {"id": 42, "cat": "indirect_evidence", "question": "Why does Dracula travel to London?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Dracula", "action": "travel to London", "polarity": "positive"},
     "evidence": "Jonathan looked at the map of London, while Dracula sat silently in the castle library.",
     "expected_supported": False},
]


# ============================================================
# RUN REPRODUCTION
# ============================================================

def run_step6():
    print("=" * 80)
    print("V8 STEP 6: FINAL EVALUATION")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    print()

    output_json = Path("reports/intent_aware_rag_v8_final_evaluation.json")
    output_md = Path("reports/intent_aware_rag_v8_final_evaluation.md")
    output_json.parent.mkdir(exist_ok=True)

    # --------------------------------------------------------
    # PART A: BASELINE (18 queries through full pipeline)
    # --------------------------------------------------------
    print("=" * 60)
    print("PART A: BASELINE REPRODUCTION (18 queries)")
    print("=" * 60)

    engine = LuminaRAG()
    baseline_results = []

    for idx, item in enumerate(BASELINE_QUERIES, start=1):
        q_id = item["id"]
        query = item["query"]
        work_id = item["work_id"]
        expected_intent = item["expected_intent"]

        print(f"[{idx}/{len(BASELINE_QUERIES)}] Q{q_id}: {query}")

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        t0 = time.perf_counter()
        try:
            res = engine.ask(question=query, work_id=work_id, depth="normal")
        except Exception as e:
            print(f"  ERROR: {e}")
            res = {
                "question": query, "answer": f"Error: {e}",
                "sources": [], "intent_data": {},
                "verdict": "ERROR", "timing_ms": {},
                "fast_filter_decision": "ERROR",
                "fast_filter_signals": {}, "fast_filter_reasons": []
            }
        wall_ms = (time.perf_counter() - t0) * 1000

        sources = res.get("sources", [])
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
            "answer": res.get("answer", "")[:500],
            "source_count": len(sources),
            "timing_ms": res.get("timing_ms", {}),
            "wall_time_ms": round(wall_ms, 2)
        }
        baseline_results.append(entry)

        status = "PASS" if entry["intent_correct"] else "FAIL"
        ff = entry["fast_filter_decision"]
        print(f"  -> Intent: {entry['detected_intent']} ({status}) | Verdict: {entry['verdict']} | FF: {ff} | {wall_ms:.0f}ms\n")

    # --------------------------------------------------------
    # PART B: ADVERSARIAL (42 cases through fast-filter + LLM)
    # --------------------------------------------------------
    print("=" * 60)
    print("PART B: ADVERSARIAL REPRODUCTION (42 cases)")
    print("=" * 60)

    llm = engine.llm  # reuse the already-loaded LLM
    adversarial_results = []

    for c in ADVERSARIAL_CASES:
        used_items = [{"text": c["evidence"]}]

        # Fast filter
        t0_ff = time.perf_counter()
        ff_result = run_fast_filter(c["question"], c["intent_data"], used_items, mode="individual")
        ff_lat = (time.perf_counter() - t0_ff) * 1000
        ff_decision = ff_result["decision"]

        # LLM validator
        t0_llm = time.perf_counter()
        llm_res = llm.validate_evidence(c["question"], c["intent_data"], used_items, mode="top-1")
        llm_lat = (time.perf_counter() - t0_llm) * 1000
        llm_verdict = llm_res.get("verdict", "NOT_SUPPORTED") if isinstance(llm_res, dict) else llm_res
        llm_details = llm_res.get("details", {}) if isinstance(llm_res, dict) else {}

        # Cascade decision (same as V7)
        if ff_decision == "FAST_REJECT":
            final_decision = "NOT_SUPPORTED"
            final_source = "fast_filter"
        elif ff_decision == "FAST_ACCEPT":
            final_decision = "SUPPORTED"
            final_source = "fast_filter"
        else:
            final_decision = llm_verdict
            final_source = "llm_validator"

        total_lat = ff_lat + (llm_lat if ff_decision == "NEEDS_LLM_VALIDATION" else 0)
        expected_str = "SUPPORTED" if c["expected_supported"] else "NOT_SUPPORTED"
        is_correct = (final_decision == expected_str)

        rec = {
            "id": c["id"],
            "category": c["cat"],
            "query": c["question"],
            "expected_supported": c["expected_supported"],
            "expected_verdict": expected_str,
            "fast_filter_decision": ff_decision,
            "fast_filter_latency_ms": round(ff_lat, 2),
            "validator_decision": llm_verdict,
            "validator_details": llm_details,
            "validator_latency_ms": round(llm_lat, 2),
            "final_decision": final_decision,
            "final_source": final_source,
            "is_correct": is_correct,
            "total_latency_ms": round(total_lat, 2),
        }
        adversarial_results.append(rec)

        status = "PASS" if is_correct else "FAIL"
        print(f"[{c['id']:02d}] [{c['cat'][:25]:<25}] FF={ff_decision:<22} | LLM={llm_verdict:<13} | Final={final_decision:<13} | {status}")

    # --------------------------------------------------------
    # AGGREGATE METRICS
    # --------------------------------------------------------
    print("\n" + "=" * 60)
    print("AGGREGATING METRICS")
    print("=" * 60)

    # Baseline metrics
    intent_correct = sum(1 for r in baseline_results if r["intent_correct"])
    intent_acc = intent_correct / len(baseline_results) * 100

    # Adversarial metrics
    adv_total = len(adversarial_results)
    adv_correct = sum(1 for r in adversarial_results if r["is_correct"])
    adv_accuracy = adv_correct / adv_total * 100
    adv_fps = sum(1 for r in adversarial_results if not r["expected_supported"] and r["final_decision"] == "SUPPORTED")
    adv_fns = sum(1 for r in adversarial_results if r["expected_supported"] and r["final_decision"] == "NOT_SUPPORTED")
    unsup_total = sum(1 for r in adversarial_results if not r["expected_supported"])
    unsup_detected = sum(1 for r in adversarial_results if not r["expected_supported"] and r["final_decision"] == "NOT_SUPPORTED")
    unsup_rate = unsup_detected / unsup_total * 100 if unsup_total else 0

    # FF-specific errors
    ff_false_pos = sum(1 for r in adversarial_results if r["fast_filter_decision"] == "FAST_ACCEPT" and not r["expected_supported"])
    ff_false_neg = sum(1 for r in adversarial_results if r["fast_filter_decision"] == "FAST_REJECT" and r["expected_supported"])

    # LLM-specific errors (only for cases routed to LLM)
    llm_routed = [r for r in adversarial_results if r["fast_filter_decision"] == "NEEDS_LLM_VALIDATION"]
    llm_fp = sum(1 for r in llm_routed if not r["expected_supported"] and r["validator_decision"] == "SUPPORTED")
    llm_fn = sum(1 for r in llm_routed if r["expected_supported"] and r["validator_decision"] == "NOT_SUPPORTED")

    # Latency (baseline)
    timing_keys = ["intent_analysis", "retrieval", "fast_filter", "validation", "generation", "total"]
    latency_stats = {}
    for key in timing_keys:
        vals = [r["timing_ms"].get(key, 0) for r in baseline_results if r["timing_ms"].get(key)]
        if vals:
            latency_stats[key] = {
                "mean_ms": round(float(np.mean(vals)), 2),
                "median_ms": round(float(np.median(vals)), 2),
                "p95_ms": round(float(np.percentile(vals, 95)), 2),
            }

    # Adversarial latency
    adv_latencies = [r["total_latency_ms"] for r in adversarial_results]
    adv_ff_latencies = [r["fast_filter_latency_ms"] for r in adversarial_results]

    reproduction = {
        "timestamp": datetime.now().isoformat(),
        "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
        "baseline": {
            "total_queries": len(baseline_results),
            "intent_accuracy_percent": round(intent_acc, 2),
            "latency_stats": latency_stats,
        },
        "adversarial": {
            "total_cases": adv_total,
            "accuracy_percent": round(adv_accuracy, 2),
            "false_positives": adv_fps,
            "false_negatives": adv_fns,
            "unsupported_premise_detection_percent": round(unsup_rate, 2),
            "ff_false_positives": ff_false_pos,
            "ff_false_negatives": ff_false_neg,
            "llm_false_positives": llm_fp,
            "llm_false_negatives": llm_fn,
            "latency": {
                "mean_ms": round(float(np.mean(adv_latencies)), 2),
                "median_ms": round(float(np.median(adv_latencies)), 2),
                "p95_ms": round(float(np.percentile(adv_latencies, 95)), 2),
                "ff_mean_ms": round(float(np.mean(adv_ff_latencies)), 2),
            },
        },
        "baseline_records": baseline_results,
        "adversarial_records": adversarial_results,
    }

    # --------------------------------------------------------
    # COMPARE WITH HISTORICAL V7
    # --------------------------------------------------------
    comparisons = []
    current = {
        "intent_accuracy_canonical": round(intent_acc, 2),  # Phase 1 only has canonical
        "adversarial_accuracy": round(adv_accuracy, 2),
        "unsupported_premise_rejection": round(unsup_rate, 2),
        "ff_false_positives": ff_false_pos,
        "ff_false_negatives": ff_false_neg,
        "llm_validator_false_negatives": llm_fn,
        "llm_validator_false_positives": llm_fp,
        "validation_latency_mean_ms": latency_stats.get("validation", {}).get("mean_ms", 0),
        "fast_filter_latency_mean_ms": latency_stats.get("fast_filter", {}).get("mean_ms", 0),
        "total_latency_mean_ms": latency_stats.get("total", {}).get("mean_ms", 0),
    }

    for metric, hist_val in HISTORICAL_V7.items():
        curr_val = current.get(metric)
        if curr_val is not None:
            diff = round(curr_val - hist_val, 4)
            match = abs(diff) < 0.01 if isinstance(hist_val, float) else diff == 0
            comparisons.append({
                "metric": metric,
                "historical_v7": hist_val,
                "current_reproduction": curr_val,
                "absolute_difference": diff,
                "matches": match,
            })

    reproduction["v7_comparison"] = comparisons

    # Save JSON
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(reproduction, f, indent=2, default=str)
    print(f"\n[SAVED] {output_json}")

    # --------------------------------------------------------
    # GENERATE MARKDOWN REPORT
    # --------------------------------------------------------
    discrepancies = [c for c in comparisons if not c["matches"]]

    md = []
    md.append("# V8 Final Evaluation Report\n")
    md.append(f"**Generated:** {datetime.now().isoformat()}\n")
    md.append(f"**GPU:** {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}\n")
    md.append("")
    md.append("## Baseline (18 queries)")
    md.append("")
    md.append(f"- Intent Accuracy: **{intent_acc:.2f}%** ({intent_correct}/{len(baseline_results)})")
    if "total" in latency_stats:
        md.append(f"- Total Latency: **{latency_stats['total']['mean_ms']:.1f}ms** mean")
    if "validation" in latency_stats:
        md.append(f"- Validation Latency: **{latency_stats['validation']['mean_ms']:.1f}ms** mean")
    if "fast_filter" in latency_stats:
        md.append(f"- Fast Filter Latency: **{latency_stats['fast_filter']['mean_ms']:.2f}ms** mean")
    md.append("")
    md.append("## Adversarial (42 cases)")
    md.append("")
    md.append(f"- Accuracy: **{adv_accuracy:.2f}%** ({adv_correct}/{adv_total})")
    md.append(f"- False Positives: **{adv_fps}**")
    md.append(f"- False Negatives: **{adv_fns}**")
    md.append(f"- Unsupported Premise Rejection: **{unsup_rate:.2f}%**")
    md.append(f"- FF False Positives: **{ff_false_pos}** | FF False Negatives: **{ff_false_neg}**")
    md.append(f"- LLM False Positives: **{llm_fp}** | LLM False Negatives: **{llm_fn}**")
    md.append("")
    md.append("## V7 Historical Comparison")
    md.append("")
    md.append("| Metric | Historical V7 | Current Reproduction | Difference | Match? |")
    md.append("|--------|--------------|---------------------|------------|--------|")
    for c in comparisons:
        match_str = "YES" if c["matches"] else "**NO**"
        md.append(f"| {c['metric']} | {c['historical_v7']} | {c['current_reproduction']} | {c['absolute_difference']:+.4f} | {match_str} |")

    if discrepancies:
        md.append("")
        md.append("## Discrepancies")
        md.append("")
        md.append("> [!WARNING]")
        md.append("> The following metrics differ from the historical V7 report:")
        md.append(">")
        for d in discrepancies:
            md.append(f"> - **{d['metric']}**: V7={d['historical_v7']}, Now={d['current_reproduction']} (diff={d['absolute_difference']:+.4f})")
        md.append(">")
        md.append("> Likely causes: LLM non-determinism (temperature=0.1), GPU state, token sampling order.")
    else:
        md.append("")
        md.append("> [!NOTE]")
        md.append("> All metrics match the historical V7 report within tolerance.")

    md.append("")
    md.append("---")
    md.append(f"*Raw data: [intent_aware_rag_v8_final_evaluation.json](file:///d:/SDC/LibraryLLM/reports/intent_aware_rag_v8_final_evaluation.json)*")

    with open(output_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"[SAVED] {output_md}")

    # Print summary
    print("\n" + "=" * 80)
    print("V8 FINAL EVALUATION SUMMARY")
    print("=" * 80)
    print(f"Baseline Intent Accuracy : {intent_acc:.1f}%")
    print(f"Adversarial Accuracy     : {adv_accuracy:.1f}%")
    print(f"Unsupported Rejection    : {unsup_rate:.1f}%")
    print(f"FF Errors                : FP={ff_false_pos}, FN={ff_false_neg}")
    print(f"LLM Errors               : FP={llm_fp}, FN={llm_fn}")
    if discrepancies:
        print(f"\n[INFO] {len(discrepancies)} metrics differ from historical V7 (expected).")
        for d in discrepancies:
            print(f"  - {d['metric']}: V7={d['historical_v7']}, Now={d['current_reproduction']}")

    print(f"\n[DONE] V8 Step 6 complete.")


if __name__ == "__main__":
    run_step6()
