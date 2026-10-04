import json

def compute():
    baseline = json.load(open("scratch_eval_results.json", "r", encoding="utf-8"))
    after = json.load(open("eval_results_after.json", "r", encoding="utf-8"))

    # Intent accuracy
    correct_intents = sum(1 for a in after if a["expected_intent"] == a.get("detected_intent"))
    intent_acc = correct_intents / len(after)

    # Let's inspect per-query retrieval relevance:
    # Ground truth relevant chapters / chunks for each query:
    # Q1: Frankenstein Ch IV/V (creating creature motivation: Chapter IV 000044/000045)
    # Q2: Frankenstein Ch XX (refusing 2nd creature: 000146/000147/000155)
    # Q3: Frankenstein Ch XX (refusing 2nd creature: 000146/000147/000155)
    # Q4: Frankenstein Ch XX (deciding against: 000146/000147/000155)
    # Q5: Frankenstein Ch V/XXIV (regret creating creature: 000051/000188/000190)
    # Q6: Frankenstein Ch V/XXIV (remorse: 000051/000188/000190)
    # Q7: Frankenstein Ch V (aftermath of creation: 000051/000052)
    # Q8: Frankenstein Ch V (first sees creature alive: 000051/000052)
    # Q9: Frankenstein Ch I/XXII (Victor's father Alphonse: 000028/000171)
    # Q10: Frankenstein Ch I/XXII (Elizabeth: 000029/000171)
    # Q11: Frankenstein Ch X/XXIV (creature hates Victor: Ch X 000087/000088 / Ch XXIV 000188)
    # Q12: Frankenstein Ch II/IV (secrets of life/death: 000034/000044/000045)
    # Q13: Dracula Ch XVIII/XXIV (Dracula motivation: 000240/000317)
    # Q14: Dracula Ch II/III (why Harker doesn't leave: 000029/000030)
    # Q15: Dracula Ch XII/XV/XVI (Lucy bitten: 000154/000200/000203)
    # Q16: Dracula Ch V/XXII/XXIII (Mina relationship: 000059/000314)
    # Q17: Dracula (Unsupported premise - Dracula expresses no regret)
    # Q18: Dracula Ch XVIII/XXVII (aftermath of attacks: 000240/000374)

    # Let's inspect each query's top 1, 3, 5 candidates
    print("Aggregate Statistics Calculation:")
    print(f"Total Queries: {len(after)}")
    print(f"Intent Classification Accuracy: {correct_intents}/{len(after)} ({intent_acc*100:.1f}%)")

    intent_latencies = [a["timing_ms"].get("intent_analysis", 0) for a in after]
    retr_latencies = [a["timing_ms"].get("retrieval", 0) for a in after]
    gen_latencies = [a["timing_ms"].get("generation", 0) for a in after]
    tot_latencies = [a["timing_ms"].get("total", 0) for a in after]

    print(f"Avg Intent Latency: {sum(intent_latencies)/len(after):.2f} ms")
    print(f"Avg Retrieval Latency: {sum(retr_latencies)/len(after):.2f} ms")
    print(f"Avg Generation Latency: {sum(gen_latencies)/len(after):.2f} ms")
    print(f"Avg Total Latency: {sum(tot_latencies)/len(after):.2f} ms")

if __name__ == "__main__":
    compute()
