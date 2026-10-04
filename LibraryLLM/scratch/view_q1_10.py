import json

def main():
    after = json.load(open("eval_results_after.json", "r", encoding="utf-8"))
    for x in after[:10]:
        print(f"==================================================")
        print(f"Q{x['id']}: {x['query']}")
        print(f"Expected Intent: {x['expected_intent']}")
        print(f"Detected Intent: {x.get('detected_intent')}")
        print(f"Intent Data: {x.get('intent_data')}")
        print(f"Verdict: {x.get('verdict')}")
        top1 = x['sources'][0] if x.get('sources') else {}
        print(f"Top-1: {top1.get('chunk_id')} ({top1.get('chapter')}) Evid={top1.get('evidence_score', 0):.3f}")
        print(f"Answer:\n{x.get('answer')}\n")

if __name__ == "__main__":
    main()
