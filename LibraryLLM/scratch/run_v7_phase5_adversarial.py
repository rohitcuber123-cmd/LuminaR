"""
V7 Phase 5: Adversarial Semantic Test (40+ cases)

Creates 42 adversarial validation cases covering all 15 categories.
Tests both fast filter and LLM validator independently.

Saves: eval_results_v7_adversarial.json
"""
import json
import os
import sys
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ["LUMINAR_MOCK_LLM"] = "0"

from rag.llm import LuminaRLLM
from rag.fast_filter import run_fast_filter


# ============================================================
# 42 ADVERSARIAL CASES (15 categories)
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
     "evidence": "Victor confided his terrible secret to Clerval during their travels through England.",
     "expected_supported": False},

    # 5. EVENT MISMATCH (3)
    {"id": 13, "cat": "event_mismatch", "question": "Why does Victor study alchemy?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "study alchemy", "polarity": "positive"},
     "evidence": "Victor was assigned to study modern chemistry under the direction of Professor Waldman.",
     "expected_supported": False},
    {"id": 14, "cat": "event_mismatch", "question": "Why does Harker photograph the castle?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Harker", "action": "photograph the castle", "polarity": "positive"},
     "evidence": "Harker made shorthand notes in his journal about the layout of the castle rooms.",
     "expected_supported": False},
    {"id": 15, "cat": "event_mismatch", "question": "How does Victor react when the creature speaks to him?",
     "intent_data": {"intent": "REACTION", "actor": "Victor", "action": "react when creature speaks", "polarity": "positive"},
     "evidence": "Three months later, Victor received a letter from his father informing him of William's death.",
     "expected_supported": False},

    # 6. NEGATION (3)
    {"id": 16, "cat": "negation", "question": "Why doesn't Victor create the creature?",
     "intent_data": {"intent": "NEGATED_MOTIVATION", "actor": "Victor", "action": "create the creature", "polarity": "negative"},
     "evidence": "Victor collected instruments to create the creature and infused a spark of being into the lifeless body.",
     "expected_supported": False},
    {"id": 17, "cat": "negation", "question": "Why doesn't Victor create a companion for the monster?",
     "intent_data": {"intent": "NEGATED_MOTIVATION", "actor": "Victor", "action": "create a companion for the monster", "polarity": "negative"},
     "evidence": "I agreed to the monster's demand and immediately began gathering materials to build a second creature.",
     "expected_supported": False},
    {"id": 18, "cat": "negation", "question": "Why does Victor create a female creature?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "create a female creature", "polarity": "positive"},
     "evidence": "I resolved never to complete the work and tore it to pieces.",
     "expected_supported": False},

    # 7. DOUBLE NEGATION (2)
    {"id": 19, "cat": "double_negation", "question": "Why doesn't Victor refuse to make the creature?",
     "intent_data": {"intent": "NEGATED_MOTIVATION", "actor": "Victor", "action": "refuse to make the creature", "polarity": "negative"},
     "evidence": "Victor consented to make the creature after hearing the monster's long and persuasive argument.",
     "expected_supported": True},
    {"id": 20, "cat": "double_negation", "question": "Why doesn't Victor refuse to destroy the female creature?",
     "intent_data": {"intent": "NEGATED_MOTIVATION", "actor": "Victor", "action": "refuse to destroy the female creature", "polarity": "negative"},
     "evidence": "Victor tore the half-finished female creature to pieces before the howling monster's eyes.",
     "expected_supported": False},

    # 8. BEFORE/AFTER REVERSAL (3)
    {"id": 21, "cat": "before_after_reversal", "question": "What happens after Victor meets the monster on the glacier?",
     "intent_data": {"intent": "CONSEQUENCE", "action": "Victor meets the monster on the glacier", "temporal_relation": "AFTER", "polarity": "positive"},
     "evidence": "Before travelling to the glacier, Victor spent two weeks mourning in Geneva.",
     "expected_supported": False},
    {"id": 22, "cat": "before_after_reversal", "question": "What does Harker do before entering Castle Dracula?",
     "intent_data": {"intent": "CONSEQUENCE", "action": "entering Castle Dracula", "temporal_relation": "BEFORE", "polarity": "positive"},
     "evidence": "After entering the castle courtyard, Harker was greeted by a tall old man.",
     "expected_supported": False},
    {"id": 23, "cat": "before_after_reversal", "question": "What happens after the creature is created?",
     "intent_data": {"intent": "CONSEQUENCE", "action": "creature is created", "temporal_relation": "AFTER", "polarity": "positive"},
     "evidence": "After the creature opened its dull yellow eye, Victor rushed from the room in horror and spent the night in agony.",
     "expected_supported": True},

    # 9. RELATIONSHIP TRAPS (3)
    {"id": 24, "cat": "relationship_trap", "question": "Who is Victor's father?",
     "intent_data": {"intent": "RELATIONSHIP", "actor": "Victor", "target": "father", "polarity": "positive"},
     "evidence": "Alphonse Frankenstein was a respected magistrate. Victor studied at Ingolstadt.",
     "expected_supported": False},
    {"id": 25, "cat": "relationship_trap", "question": "Who is Mina's husband?",
     "intent_data": {"intent": "RELATIONSHIP", "actor": "Mina", "target": "husband", "polarity": "positive"},
     "evidence": "Jonathan Harker admired Mina Murray's handwriting in her letters.",
     "expected_supported": False},
    {"id": 26, "cat": "relationship_trap", "question": "Who is Victor's father?",
     "intent_data": {"intent": "RELATIONSHIP", "actor": "Victor", "target": "father", "polarity": "positive"},
     "evidence": "My father, Alphonse Frankenstein, watched over my childhood with immense tenderness.",
     "expected_supported": True},

    # 10. EMOTIONAL-WORD OVERLAP (3)
    {"id": 27, "cat": "emotional_overlap", "question": "Why does Victor feel remorse for his creation?",
     "intent_data": {"intent": "REGRET", "actor": "Victor", "action": "feel remorse", "polarity": "positive"},
     "evidence": "I was seized with a fierce determination to hunt the creature down and slaughter him.",
     "expected_supported": False},
    {"id": 28, "cat": "emotional_overlap", "question": "Why does Victor feel remorse for his creation?",
     "intent_data": {"intent": "REGRET", "actor": "Victor", "action": "feel remorse", "polarity": "positive"},
     "evidence": "A terrible sense of guilt overwhelmed me; I wept bitter tears of remorse.",
     "expected_supported": True},
    {"id": 29, "cat": "emotional_overlap", "question": "Why does Dracula feel sorrow for Lucy?",
     "intent_data": {"intent": "REGRET", "actor": "Dracula", "action": "feel sorrow for Lucy", "polarity": "positive"},
     "evidence": "Lucy's face was pale and her suffering was evident, but the Count showed no mercy.",
     "expected_supported": False},

    # 11. SAME ACTOR, DIFFERENT EVENT (2)
    {"id": 30, "cat": "same_actor_diff_event", "question": "Why does Victor travel to England?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "travel to England", "polarity": "positive"},
     "evidence": "Victor travelled to Ingolstadt alone to study chemistry under Professor Waldman.",
     "expected_supported": False},
    {"id": 31, "cat": "same_actor_diff_event", "question": "Why does Harker write in his journal?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Harker", "action": "write in his journal", "polarity": "positive"},
     "evidence": "Harker counted the remaining gold coins in his travelling bag nervously.",
     "expected_supported": False},

    # 12. SAME EVENT, DIFFERENT ACTOR (2)
    {"id": 32, "cat": "same_event_diff_actor", "question": "Why does Victor study natural philosophy?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "study natural philosophy", "polarity": "positive"},
     "evidence": "Clerval studied oriental languages with passionate dedication at the university.",
     "expected_supported": False},
    {"id": 33, "cat": "same_event_diff_actor", "question": "Why does Dracula crawl down the castle wall?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Dracula", "action": "crawl down the castle wall", "polarity": "positive"},
     "evidence": "Harker attempted to climb down the castle wall by grasping the crevices between the stones.",
     "expected_supported": False},

    # 13. UNSUPPORTED PREMISES (3)
    {"id": 34, "cat": "unsupported_premise", "question": "Why does Victor invite the creature to live with Elizabeth?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "invite the creature to live with Elizabeth", "polarity": "positive"},
     "evidence": "Victor shuddered at the thought of the creature approaching Elizabeth.",
     "expected_supported": False},
    {"id": 35, "cat": "unsupported_premise", "question": "Why did Van Helsing buy Castle Dracula?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Van Helsing", "action": "buy Castle Dracula", "polarity": "positive"},
     "evidence": "Van Helsing arrived in England to treat Lucy Westenra's mysterious blood loss.",
     "expected_supported": False},
    {"id": 36, "cat": "unsupported_premise", "question": "Why did Lucy become a nun after recovering?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Lucy", "action": "become a nun after recovering", "polarity": "positive"},
     "evidence": "Lucy died and was buried in the churchyard. She rose as an un-dead vampire.",
     "expected_supported": False},

    # 14. "ANOTHER" / "SECOND" / "FEMALE" DISTINCTIONS (3)
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


def main():
    print("=" * 80)
    print("V7 PHASE 5: ADVERSARIAL SEMANTIC TEST (42 CASES)")
    print("=" * 80)

    llm = LuminaRLLM()

    records = []
    latencies = []

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

        # Cascade decision
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
        latencies.append(total_lat)

        expected_str = "SUPPORTED" if c["expected_supported"] else "NOT_SUPPORTED"
        is_correct = (final_decision == expected_str)

        rec = {
            "id": c["id"],
            "category": c["cat"],
            "query": c["question"],
            "expected_supported": c["expected_supported"],
            "expected_verdict": expected_str,
            "fast_filter_decision": ff_decision,
            "fast_filter_signals": ff_result.get("signals", {}),
            "fast_filter_reasons": ff_result.get("reasons", []),
            "fast_filter_latency_ms": round(ff_lat, 2),
            "validator_decision": llm_verdict,
            "validator_details": {
                "actor_match": llm_details.get("actor_match"),
                "event_match": llm_details.get("event_match"),
                "target_match": llm_details.get("target_match"),
                "polarity_match": llm_details.get("polarity_match"),
                "temporal_match": llm_details.get("temporal_match"),
                "relationship_match": llm_details.get("relationship_match"),
            },
            "validator_latency_ms": round(llm_lat, 2),
            "final_decision": final_decision,
            "final_source": final_source,
            "is_correct": is_correct,
            "total_latency_ms": round(total_lat, 2),
        }
        records.append(rec)

        status = "PASS" if is_correct else "FAIL"
        print(f"[{c['id']:02d}] [{c['cat'][:25]:<25}] FF={ff_decision:<22} | LLM={llm_verdict:<13} | Final={final_decision:<13} | {status}")

    # Aggregate
    total = len(records)
    correct = sum(1 for r in records if r["is_correct"])
    fps = sum(1 for r in records if not r["expected_supported"] and r["final_decision"] == "SUPPORTED")
    fns = sum(1 for r in records if r["expected_supported"] and r["final_decision"] == "NOT_SUPPORTED")
    unsup_total = sum(1 for r in records if not r["expected_supported"])
    unsup_detected = sum(1 for r in records if not r["expected_supported"] and r["final_decision"] == "NOT_SUPPORTED")

    ff_rejects = sum(1 for r in records if r["fast_filter_decision"] == "FAST_REJECT")
    ff_accepts = sum(1 for r in records if r["fast_filter_decision"] == "FAST_ACCEPT")
    ff_llm = sum(1 for r in records if r["fast_filter_decision"] == "NEEDS_LLM_VALIDATION")

    # FF-specific error analysis
    ff_false_pos = sum(1 for r in records if r["fast_filter_decision"] == "FAST_ACCEPT" and not r["expected_supported"])
    ff_false_neg = sum(1 for r in records if r["fast_filter_decision"] == "FAST_REJECT" and r["expected_supported"])

    summary = {
        "total_cases": total,
        "accuracy_percent": round(correct / total * 100, 2),
        "false_positives": fps,
        "false_negatives": fns,
        "unsupported_premise_detection_percent": round(unsup_detected / unsup_total * 100, 2) if unsup_total else 0,
        "fast_filter_stats": {
            "FAST_REJECT": ff_rejects,
            "FAST_ACCEPT": ff_accepts,
            "NEEDS_LLM_VALIDATION": ff_llm,
            "llm_calls_avoided_percent": round((ff_rejects + ff_accepts) / total * 100, 2),
            "false_positives": ff_false_pos,
            "false_negatives": ff_false_neg,
        },
        "latency": {
            "mean_ms": round(float(np.mean(latencies)), 2),
            "median_ms": round(float(np.median(latencies)), 2),
            "p95_ms": round(float(np.percentile(latencies, 95)), 2),
        },
        "categories": {}
    }

    # Per-category analysis
    categories = set(r["category"] for r in records)
    for cat in sorted(categories):
        cat_recs = [r for r in records if r["category"] == cat]
        cat_correct = sum(1 for r in cat_recs if r["is_correct"])
        summary["categories"][cat] = {
            "total": len(cat_recs),
            "correct": cat_correct,
            "accuracy_percent": round(cat_correct / len(cat_recs) * 100, 2)
        }

    output = {"summary": summary, "records": records}

    with open("eval_results_v7_adversarial.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*80}")
    print(f"ADVERSARIAL RESULTS: Accuracy={summary['accuracy_percent']}% | FP={fps} | FN={fns}")
    print(f"Fast Filter: REJECT={ff_rejects} ACCEPT={ff_accepts} LLM={ff_llm} | LLM Avoided={summary['fast_filter_stats']['llm_calls_avoided_percent']}%")
    print(f"FF Errors: FP={ff_false_pos} FN={ff_false_neg}")
    print(f"Latency: Mean={summary['latency']['mean_ms']:.1f}ms")
    print(f"\n[DONE] Saved to eval_results_v7_adversarial.json")


if __name__ == "__main__":
    main()
