"""
V8 Step 5: Directionality Improvement

Tests 15 custom adversarial cases specifically targeting subject-object 
inversion and complex negation, which caused the 2 fast-filter errors in V7.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rag.fast_filter import run_fast_filter

DIRECTIONALITY_CASES = [
    # Basic Inversions (Actor vs Target)
    {"id": 1, "question": "Why does Victor fear the monster?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "fear the monster", "polarity": "positive", "target": "monster"},
     "evidence": "The monster feared Victor would destroy his promised companion before completion.",
     "expected_supported": False},
    
    {"id": 2, "question": "Why does the monster fear Victor?",
     "intent_data": {"intent": "MOTIVATION", "actor": "monster", "action": "fear Victor", "polarity": "positive", "target": "Victor"},
     "evidence": "The monster feared Victor would destroy his promised companion before completion.",
     "expected_supported": True},

    {"id": 3, "question": "Why does Victor hate the creature?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "hate the creature", "polarity": "positive", "target": "creature"},
     "evidence": "Victor felt a sudden hate for the creature that stood before him.",
     "expected_supported": True},

    {"id": 4, "question": "Why does the creature hate Victor?",
     "intent_data": {"intent": "MOTIVATION", "actor": "creature", "action": "hate Victor", "polarity": "positive", "target": "Victor"},
     "evidence": "Victor felt a sudden hate for the creature that stood before him.",
     "expected_supported": False},

    # Relationships Inversions
    {"id": 5, "question": "Who is Victor's father?",
     "intent_data": {"intent": "RELATIONSHIP", "actor": "Victor", "target": "father", "polarity": "positive"},
     "evidence": "Victor stood beside the father of the bride at the ceremony.",
     "expected_supported": False},

    {"id": 6, "question": "Who is Victor's father?",
     "intent_data": {"intent": "RELATIONSHIP", "actor": "Victor", "target": "father", "polarity": "positive"},
     "evidence": "Alphonse was Victor's father, a respected syndic.",
     "expected_supported": True},
     
    {"id": 7, "question": "Who is Alphonse to Victor?",
     "intent_data": {"intent": "RELATIONSHIP", "actor": "Victor", "target": "Alphonse", "polarity": "positive"},
     "evidence": "Alphonse was Victor's father.",
     "expected_supported": True},

    # Complex Sub-clause Negation
    {"id": 8, "question": "Why does Victor create the creature?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "create the creature", "polarity": "positive"},
     "evidence": "Victor collected instruments, but resolved not to create the creature.",
     "expected_supported": False},

    {"id": 9, "question": "Why doesn't Victor create the creature?",
     "intent_data": {"intent": "NEGATED_MOTIVATION", "actor": "Victor", "action": "create the creature", "polarity": "negated"},
     "evidence": "Victor collected instruments, but resolved not to create the creature.",
     "expected_supported": True},

    # More Inversions
    {"id": 10, "question": "Why does Dracula hunt Jonathan Harker?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Dracula", "action": "hunt Jonathan Harker", "polarity": "positive", "target": "Jonathan Harker"},
     "evidence": "Jonathan Harker hunted Dracula across Europe, tracking his earth boxes.",
     "expected_supported": False},
     
    {"id": 11, "question": "Why does Jonathan Harker hunt Dracula?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Jonathan Harker", "action": "hunt Dracula", "polarity": "positive", "target": "Dracula"},
     "evidence": "Jonathan Harker hunted Dracula across Europe, tracking his earth boxes.",
     "expected_supported": True},
     
    # Distractors
    {"id": 12, "question": "Why does Victor fear the monster?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "fear the monster", "polarity": "positive", "target": "monster"},
     "evidence": "Elizabeth feared the monster, while Victor remained resolute.",
     "expected_supported": False},
     
    {"id": 13, "question": "Why does the monster kill Elizabeth?",
     "intent_data": {"intent": "MOTIVATION", "actor": "monster", "action": "kill Elizabeth", "polarity": "positive", "target": "Elizabeth"},
     "evidence": "The monster threatened to kill Elizabeth, though he hadn't yet done so.",
     "expected_supported": False},
     
    {"id": 14, "question": "Who is the bride of the monster?",
     "intent_data": {"intent": "RELATIONSHIP", "actor": "monster", "target": "bride", "polarity": "positive"},
     "evidence": "The monster demanded Victor create a bride for him.",
     "expected_supported": False},
     
    {"id": 15, "question": "Who is Elizabeth's husband?",
     "intent_data": {"intent": "RELATIONSHIP", "actor": "Elizabeth", "target": "husband", "polarity": "positive"},
     "evidence": "Victor became Elizabeth's husband in a quiet ceremony.",
     "expected_supported": True}
]

def run_step5():
    print("=" * 80)
    print("V8 STEP 5: DIRECTIONALITY IMPROVEMENT TEST")
    print("=" * 80)

    output_json = Path("reports/v8_experiment_d_directionality.json")
    output_json.parent.mkdir(exist_ok=True)

    records = []
    
    for idx, c in enumerate(DIRECTIONALITY_CASES, 1):
        used_items = [{"text": c["evidence"]}]
        ff_res = run_fast_filter(c["question"], c["intent_data"], used_items, mode="individual")
        
        decision = ff_res["decision"]
        signals = ff_res["signals"]
        
        # Determine if FF correctly caught the trap, or if it incorrectly accepted/rejected
        expected_supported = c["expected_supported"]
        
        if decision == "FAST_ACCEPT" and not expected_supported:
            status = "FALSE_POSITIVE (FAIL)"
            is_correct = False
        elif decision == "FAST_REJECT" and expected_supported:
            status = "FALSE_NEGATIVE (FAIL)"
            is_correct = False
        elif decision == "FAST_REJECT" and not expected_supported:
            status = "TRUE_NEGATIVE (PASS)"
            is_correct = True
        elif decision == "FAST_ACCEPT" and expected_supported:
            status = "TRUE_POSITIVE (PASS)"
            is_correct = True
        else:
            status = "DEFERRED_TO_LLM (NEUTRAL)"
            is_correct = None # Deferred

        records.append({
            "id": c["id"],
            "question": c["question"],
            "expected_supported": expected_supported,
            "decision": decision,
            "is_correct": is_correct,
            "status": status,
            "direction_inverted": signals.get("direction_inverted", False)
        })
        
        print(f"[{idx:02d}] Expected: {expected_supported:<5} | Decision: {decision:<20} | Inverted Flag: {signals.get('direction_inverted', False)} | {status}")

    # Metrics
    passes = sum(1 for r in records if r["is_correct"] is True)
    fails = sum(1 for r in records if r["is_correct"] is False)
    deferred = sum(1 for r in records if r["is_correct"] is None)
    
    fps = sum(1 for r in records if r["status"].startswith("FALSE_POSITIVE"))
    fns = sum(1 for r in records if r["status"].startswith("FALSE_NEGATIVE"))
    
    print("\n" + "=" * 50)
    print("DIRECTIONALITY METRICS")
    print("=" * 50)
    print(f"Total Cases : {len(records)}")
    print(f"Pass (FF)   : {passes}")
    print(f"Fail (FF)   : {fails}")
    print(f"Deferred    : {deferred}")
    print(f"False Pos   : {fps} (Dangerous!)")
    print(f"False Neg   : {fns}")
    
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump({"metrics": {"passes": passes, "fails": fails, "deferred": deferred, "false_positives": fps, "false_negatives": fns}, "records": records}, f, indent=2)
    print(f"\n[SAVED] {output_json}")

if __name__ == "__main__":
    run_step5()
