import json
from pathlib import Path

def main():
    baseline_path = Path("scratch_eval_results.json")
    after_path = Path("eval_results_after.json")

    baseline = json.load(open(baseline_path, "r", encoding="utf-8"))
    after = json.load(open(after_path, "r", encoding="utf-8"))

    print("=" * 80)
    print("18-QUERY REGRESSION SUITE COMPARISON")
    print("=" * 80)

    for i in range(len(after)):
        b = baseline[i]
        a = after[i]
        qid = a["id"]
        q = a["query"]
        exp_intent = a["expected_intent"]
        b_intent = b.get("detected_intent")
        a_intent = a.get("detected_intent")
        
        b_top1 = b["top_7_chunks"][0] if b.get("top_7_chunks") else {}
        a_top1 = a["sources"][0] if a.get("sources") else {}

        b_top1_cid = b_top1.get("chunk_id", "None")
        b_top1_ch = b_top1.get("chapter", "None")
        b_top1_ev = b_top1.get("evidence_score", 0)

        a_top1_cid = a_top1.get("chunk_id", "None")
        a_top1_ch = a_top1.get("chapter", "None")
        a_top1_ev = a_top1.get("evidence_score", 0)

        print(f"\n--- Q{qid}: {q} ---")
        print(f"Work ID: {a['work_id']} | Expected Intent: {exp_intent}")
        print(f"Detected Intent: BEFORE={b_intent} -> AFTER={a_intent}")
        print(f"Evidence Verdict: {a.get('verdict')}")
        print(f"Top-1 Chunk: BEFORE={b_top1_cid} ({b_top1_ch}, Evid={b_top1_ev:.3f}) -> AFTER={a_top1_cid} ({a_top1_ch}, Evid={a_top1_ev:.3f})")
        print(f"Answer snippet: {a.get('answer', '')[:150]}...")
        print(f"Timing (ms): Intent={a['timing_ms'].get('intent_analysis', 0):.1f}, Retr={a['timing_ms'].get('retrieval', 0):.1f}, Gen={a['timing_ms'].get('generation', 0):.1f}, Total={a['timing_ms'].get('total', 0):.1f}")

if __name__ == "__main__":
    main()
