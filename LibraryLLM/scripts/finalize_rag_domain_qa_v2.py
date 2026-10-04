"""Future v2 review admission; deliberately not run by the generation pilot."""
from __future__ import annotations

import csv
import json

from rag_domain_common import ROOT, SOURCE_MAP, TRAINING, controls
from rag_domain_qa_v2_review import CSV, review_decision


def main():
    if not CSV.exists(): raise RuntimeError("Human review CSV is absent")
    with CSV.open(newline="", encoding="utf-8-sig") as f:
        decisions = list(csv.DictReader(f))
    if not any((r.get("decision") or "").strip() for r in decisions):
        raise RuntimeError("Human review is incomplete; no finalization attempted")
    path = TRAINING / "luminar" / "domain_qa_auto_validated_v2.jsonl"
    candidates = {x["candidate_id"]: x for line in path.read_text(encoding="utf-8").splitlines()
                  if line.strip() for x in [json.loads(line)]}
    if {r["candidate_id"] for r in decisions} != set(candidates):
        raise RuntimeError("Review CSV does not match frozen AUTO_VALIDATED candidate IDs")
    _, split, labels = controls()
    eval_queries = [x["question"] for x in labels]
    mapping = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    sources = {wid: (ROOT / mapping[wid]["source_file"]).read_text(encoding="utf-8")
               for wid in {c["work_id"] for c in candidates.values()}}
    need_judge = any((r.get("decision") or "").strip().upper() == "EDIT" for r in decisions)
    semantic_judge = None
    if need_judge:
        from build_rag_domain_qa_candidates_v2 import LocalQwen, QwenJudge
        semantic_judge = QwenJudge(LocalQwen())
    reviewed, failures = [], []
    for d in decisions:
        c = candidates[d["candidate_id"]]
        result, codes = review_decision(c, d, sources[c["work_id"]], eval_queries=eval_queries,
                                        test_works=split["protected_test_work_ids"],
                                        semantic_judge=semantic_judge)
        if result: reviewed.append(result)
        elif codes: failures.append({"candidate_id": c["candidate_id"], "codes": codes})
    if reviewed:
        out = TRAINING / "luminar" / "domain_qa_reviewed_v2.jsonl"
        out.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in reviewed) + "\n", encoding="utf-8")
    report = {"reviewed": len(reviewed), "failures": failures,
              "training_gate": "CLOSED_PENDING_200_TRAIN_40_VALIDATION_AND_REVIEWED_NEGATIVES"}
    (TRAINING / "reports" / "rag_domain_qa_finalization_v2.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__": main()
