import json

def audit_all():
    after = json.load(open("eval_results_after.json", "r", encoding="utf-8"))
    baseline = json.load(open("scratch_eval_results.json", "r", encoding="utf-8"))

    print("FULL AUDIT OF 18 QUERIES")
    for i, a in enumerate(after):
        b = baseline[i]
        qid = a["id"]
        print(f"\n==================================================")
        print(f"QUERY {qid}: {a['query']}")
        print(f"Work ID: {a['work_id']}")
        print(f"Expected Intent: {a['expected_intent']}")
        print(f"Extracted Intent Data: {a.get('intent_data')}")
        print(f"Verdict: {a.get('verdict')}")
        print(f"Latency: Intent={a['timing_ms'].get('intent_analysis')}ms, Retr={a['timing_ms'].get('retrieval')}ms, Gen={a['timing_ms'].get('generation')}ms, Total={a['timing_ms'].get('total')}ms")
        
        print("\nTOP-7 CHUNKS:")
        for rk, src in enumerate(a.get("sources", [])[:7], start=1):
            cid = src.get("chunk_id")
            ch = src.get("chapter")
            ev = src.get("evidence_score", 0)
            ce = src.get("rerank_score", 0)
            cen = src.get("normalized_rerank_score", 0)
            fn = src.get("faiss_norm", 0)
            act = src.get("actor_alignment")
            dir_act = src.get("directional_subject_alignment")
            evt = src.get("event_alignment")
            pol = src.get("polarity_alignment")
            temp = src.get("temporal_phase_alignment")
            caus = src.get("local_causal_score")
            mot = src.get("motivation_priority")
            sigs = src.get("evidence_signals", [])
            print(f"  [{rk}] {cid} ({ch}) | Evid={ev:.3f} | CE_raw={ce:.3f} CE_n={cen:.3f} | FAISS_n={fn:.3f}")
            print(f"       Signals: act={act}, dir_act={dir_act}, evt={evt}, pol={pol}, temp={temp}, causal={caus}, mot_prio={mot}")
            print(f"       SigList: {sigs[:4]}")

        print("\nGENERATED ANSWER:")
        print(a.get("answer"))

if __name__ == "__main__":
    audit_all()
