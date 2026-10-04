import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from rag.llm import LuminaRLLM

def main():
    llm = LuminaRLLM()
    
    # 18 Canonical
    canonical_queries = [
        ("Why does Victor create the creature?", "MOTIVATION"),
        ("What motivates Victor to create the creature?", "MOTIVATION"),
        ("Why does the creature hate Victor?", "MOTIVATION"),
        ("Why doesn't Victor create a female creature?", "NEGATED_MOTIVATION"),
        ("Why did Victor refuse to create a companion?", "NEGATED_MOTIVATION"),
        ("Why does Victor regret creating the creature?", "REGRET"),
        ("Why does Victor feel remorse about the monster?", "REGRET"),
        ("What happens after Victor creates the creature?", "CONSEQUENCE"),
        ("What happens after the creature is brought to life?", "CONSEQUENCE"),
        ("What happens when Victor first sees the creature?", "REACTION"),
        ("How does Victor react when the creature awakens?", "REACTION"),
        ("Who is Victor's father?", "RELATIONSHIP"),
        ("Who is Elizabeth to Victor?", "RELATIONSHIP"),
        ("Why does Dracula buy the house in London?", "MOTIVATION"),
        ("What motivates Van Helsing to hunt Dracula?", "MOTIVATION"),
        ("Why doesn't Jonathan Harker leave the castle?", "NEGATED_MOTIVATION"),
        ("What happens after Dracula arrives in London?", "CONSEQUENCE"),
        ("Who is Mina's husband?", "RELATIONSHIP")
    ]
    
    # 36 Paraphrased (simplified subset for evaluation)
    paraphrased_queries = [
        ("What drives Victor to bring the creature to life?", "MOTIVATION"),
        ("For what reason does Victor animate the lifeless body?", "MOTIVATION"),
        ("What is the underlying cause of the creature's hatred for Victor?", "MOTIVATION"),
        ("Why is Victor against the idea of making a bride for the monster?", "NEGATED_MOTIVATION"),
        ("What prevented Victor from assembling a second creature?", "NEGATED_MOTIVATION"),
        ("Why does Victor feel so much guilt over his scientific experiment?", "REGRET"),
        ("What causes Victor's deep sorrow concerning his creation?", "REGRET"),
        ("What are the immediate events following the animation of the monster?", "CONSEQUENCE"),
        ("What is the direct result of Victor succeeding in his experiment?", "CONSEQUENCE"),
        ("How does Victor feel the moment he looks at the living monster?", "REACTION"),
        ("What is Victor's emotional response upon seeing the creature's yellow eye?", "REACTION"),
        ("Can you tell me the name of the man who raised Victor?", "RELATIONSHIP"),
        ("What is the exact familial tie between Victor and Elizabeth?", "RELATIONSHIP"),
        ("What is the Count's primary reason for acquiring the Carfax estate?", "MOTIVATION"),
        ("What compels the professor to track down the vampire?", "MOTIVATION"),
        ("What stops Harker from simply walking out the front door?", "NEGATED_MOTIVATION"),
        ("What occurs in England once the Demeter docks at Whitby?", "CONSEQUENCE"),
        ("Who is the man legally married to Mina Murray?", "RELATIONSHIP"),
        # Additional challenging paraphrases
        ("Why does the monster kill William?", "MOTIVATION"),
        ("What leads the creature to frame Justine?", "MOTIVATION"),
        ("Why did the De Laceys reject the monster?", "MOTIVATION"),
        ("Why does Victor destroy the half-finished female?", "NEGATED_MOTIVATION"),
        ("What made Victor break his promise to the fiend?", "NEGATED_MOTIVATION"),
        ("Why is the creature so devastated when he finds Victor dead?", "REGRET"),
        ("What happens directly after Elizabeth is murdered?", "CONSEQUENCE"),
        ("What takes place once Victor chases the monster to the ice?", "CONSEQUENCE"),
        ("What is Walton's response when he hears Victor's tale?", "REACTION"),
        ("How does the town react to Clerval's death?", "REACTION"),
        ("How are Victor and William related?", "RELATIONSHIP"),
        ("Who is Justine Moritz to the Frankenstein family?", "RELATIONSHIP"),
        ("What prompts Lucy to walk in her sleep?", "MOTIVATION"),
        ("Why does Renfield collect flies?", "MOTIVATION"),
        ("Why doesn't Arthur stake Lucy immediately?", "NEGATED_MOTIVATION"),
        ("What happens to the Bloofer Lady?", "CONSEQUENCE"),
        ("How does Harker react when he sees Dracula crawling down the wall?", "REACTION"),
        ("Who is Quincey Morris in relation to Arthur?", "RELATIONSHIP")
    ]
    
    adversarial_queries = [
        ("What happens immediately after Victor first sees the creature?", "CONSEQUENCE"),
        ("Why doesn't the creature forgive Victor?", "NEGATED_MOTIVATION"),
        ("What happens before Victor creates the creature?", "CONSEQUENCE"),
        ("Why might Jonathan have wanted to leave the castle?", "MOTIVATION"),
        ("Who is responsible for the death of William?", "FACTUAL")
    ]

    all_tests = [
        ("Canonical", canonical_queries),
        ("Paraphrased", paraphrased_queries),
        ("Adversarial", adversarial_queries)
    ]

    results = []

    for category, queries in all_tests:
        for q, expected_intent in queries:
            start_t = time.perf_counter()
            res = llm.analyze_intent(q)
            lat = (time.perf_counter() - start_t) * 1000
            
            # Since lm-format-enforcer forces valid schema, we just check if it returned a dict with the expected keys
            valid_json = isinstance(res, dict) and "intent" in res
            
            results.append({
                "category": category,
                "query": q,
                "expected_intent": expected_intent,
                "predicted_intent": res.get("intent"),
                "actor": res.get("actor"),
                "action": res.get("action"),
                "target": res.get("target"),
                "polarity": res.get("polarity"),
                "temporal_relation": res.get("temporal_relation"),
                "question_focus": res.get("question_focus"),
                "tier_used": res.get("tier_used", "Tier 2"),
                "valid_json": valid_json,
                "latency_ms": lat
            })
            print(f"[{category}] {q[:40]}... -> {res.get('intent')} (Expected: {expected_intent}) | {res.get('tier_used')} | {lat:.1f}ms")

    with open("eval_results_v4_intent.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
