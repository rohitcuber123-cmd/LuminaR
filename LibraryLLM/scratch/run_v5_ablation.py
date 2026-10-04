import json
import time
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from rag.llm import LuminaRLLM

def run_ablation():
    llm = LuminaRLLM()
    
    cases = [
        # Relationship
        {
            "q": "Who is Victor's father?",
            "intent": {"intent": "RELATIONSHIP", "target": "father", "actor": "Victor"},
            "chunks": [
                {"text": "I am Victor, and I stood beside Alphonse."},
                {"text": "Alphonse Frankenstein was the father of Victor."},
                {"text": "The father of the bride smiled at Victor."}
            ],
            "expected": True
        },
        # Relationship False Positive
        {
            "q": "Who is Mina to Jonathan Harker?",
            "intent": {"intent": "RELATIONSHIP", "actor": "Mina", "target": "Jonathan Harker"},
            "chunks": [
                {"text": "Jonathan Harker wrote a letter to Mina."},
                {"text": "Mina read the letter from Jonathan."},
                {"text": "They were both in London."}
            ],
            "expected": False
        },
        # Temporal
        {
            "q": "What happens before Victor creates the creature?",
            "intent": {"intent": "CONSEQUENCE", "temporal_relation": "BEFORE", "actor": "Victor", "action": "creates the creature"},
            "chunks": [
                {"text": "After the creature opened its eye, Victor fled."},
                {"text": "Victor rushed out of the room when it awoke."},
                {"text": "He spent months collecting bones from charnel houses before the fateful night."}
            ],
            "expected": True
        },
        # Temporal Mismatch
        {
            "q": "What happens before Victor creates the creature?",
            "intent": {"intent": "CONSEQUENCE", "temporal_relation": "BEFORE", "actor": "Victor", "action": "creates the creature"},
            "chunks": [
                {"text": "After the creature opened its eye, Victor fled."},
                {"text": "Victor rushed out of the room when it awoke."},
                {"text": "He fell ill the next day."}
            ],
            "expected": False
        },
        # Negation
        {
            "q": "Why doesn't Victor create the creature?",
            "intent": {"intent": "NEGATED_MOTIVATION", "actor": "Victor", "action": "create the creature", "polarity": "negative"},
            "chunks": [
                {"text": "Victor spent months collecting instruments of life to build the creature."},
                {"text": "He finally brought it to life on a dreary night in November."},
                {"text": "He was successful in his endeavor."}
            ],
            "expected": False
        },
        # Subject/Object
        {
            "q": "Who does Victor fear?",
            "intent": {"intent": "FACTUAL", "actor": "Victor", "action": "fear"},
            "chunks": [
                {"text": "The villagers feared Victor immensely."},
                {"text": "Victor was a terrifying sight to the townspeople."},
                {"text": "Everyone ran away from Victor in fear."}
            ],
            "expected": False
        }
    ]
    
    modes = ["top-1", "top-3-comb", "top-3-ind"]
    results = {m: {"correct": 0, "total": len(cases), "time": 0.0} for m in modes}
    
    for case in cases:
        for mode in modes:
            start = time.perf_counter()
            if mode == "top-3-ind":
                verdict_val = "NOT_SUPPORTED"
                for i in range(min(3, len(case["chunks"]))):
                    res = llm.validate_evidence(case["q"], case["intent"], [case["chunks"][i]], mode="top-1")
                    if res.get("verdict") == "SUPPORTED":
                        verdict_val = "SUPPORTED"
                        break
            else:
                res = llm.validate_evidence(case["q"], case["intent"], case["chunks"], mode=mode)
                verdict_val = res.get("verdict")
            
            elapsed = time.perf_counter() - start
            results[mode]["time"] += elapsed
            
            is_supported = (verdict_val == "SUPPORTED")
            if is_supported == case["expected"]:
                results[mode]["correct"] += 1
                
    with open("ablation_results.json", "w") as f:
        json.dump(results, f, indent=2)
        
    for m in modes:
        acc = results[m]["correct"] / results[m]["total"]
        print(f"Mode: {m} | Accuracy: {acc*100:.1f}% | Time: {results[m]['time']:.2f}s")
        
if __name__ == "__main__":
    run_ablation()
