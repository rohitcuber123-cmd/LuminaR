"""Accept only manually verified negatives; form the gated domain training file."""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json

import pyarrow as pa
import pyarrow.parquet as pq

from rag_domain_common import ROOT, SOURCE_MAP, TRAINING, controls
from mine_rag_domain_hard_negatives import safe_candidate
from render_rag_negative_review import CANDIDATES, REVIEW, CHECKS

QA = TRAINING / "luminar" / "domain_qa_reviewed_v1.jsonl"
VALID = TRAINING / "luminar" / "domain_negative_valid_v1.jsonl"
PARQUET = TRAINING / "luminar" / "luminar_domain_reviewed_v1.parquet"
REPORT = TRAINING / "reports" / "rag_hard_negative_finalization_v1.json"


def main():
    _, split, _ = controls()
    qa = [json.loads(x) for x in QA.read_text(encoding="utf-8").splitlines() if x.strip()]
    qa_by_id = {r["candidate_id"]: r for r in qa}
    negatives = {x["negative_id"]: x for line in CANDIDATES.read_text(encoding="utf-8").splitlines()
                 if line.strip() for x in [json.loads(line)]}
    with REVIEW.open(newline="", encoding="utf-8-sig") as file:
        decisions = list(csv.DictReader(file))
    if len(decisions) != len(negatives) or {r["negative_id"] for r in decisions} != set(negatives):
        raise RuntimeError("Negative review CSV does not match candidates")
    source_map = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    source_cache = {}
    counts = Counter()
    failures, valid = [], []
    for decision in decisions:
        action = (decision["negative_review"] or "").strip().upper()
        if action not in ("VALID", "FALSE_NEGATIVE", "UNCERTAIN"):
            counts["UNREVIEWED"] += 1
            continue
        counts[action] += 1
        if action != "VALID":
            continue
        neg = negatives[decision["negative_id"]]
        positive = qa_by_id[neg["candidate_id"]]
        if not decision["reviewer"].strip() or any(decision[c].strip().upper() != "YES" for c in CHECKS):
            failures.append({"negative_id": neg["negative_id"], "reason": "Missing reviewer or YES checklist"})
            continue
        wid = neg["work_id"]
        if wid in split["protected_test_work_ids"] or wid not in split["train_work_ids"]:
            failures.append({"negative_id": neg["negative_id"], "reason": "Protected or non-TRAIN work"})
            continue
        if wid not in source_cache:
            source_cache[wid] = (ROOT / source_map[wid]["source_file"]).read_text(encoding="utf-8")
        source = source_cache[wid]
        if (hashlib.sha256(source.encode("utf-8")).hexdigest() != neg["source_hash"] or
                source[neg["source_start"]:neg["source_end"]] != neg["negative"]):
            failures.append({"negative_id": neg["negative_id"], "reason": "Negative source mismatch"})
            continue
        row = {"split": "TRAIN", "work_id": wid, "chunk_id": neg["negative_chunk_id"],
               "text": neg["negative"], "source_start_char": neg["source_start"],
               "source_end_char": neg["source_end"]}
        safe, reason = safe_candidate(positive, row)
        if not safe:
            failures.append({"negative_id": neg["negative_id"], "reason": reason})
            continue
        neg["review_status"] = "VALID_NEGATIVE"
        neg["reviewer"] = decision["reviewer"].strip()
        neg["review_notes"] = decision["review_notes"].strip()
        valid.append(neg)
    if valid:
        VALID.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in valid) + "\n", encoding="utf-8")
    by_qa = {}
    for neg in valid:
        by_qa.setdefault(neg["candidate_id"], []).append(neg)
    train = [r for r in qa if r["split"] == "TRAIN"]
    validation = [r for r in qa if r["split"] == "VALIDATION"]
    gaps = [r["candidate_id"] for r in train if not by_qa.get(r["candidate_id"])]
    can_train = len(train) >= 200 and len(validation) >= 40 and not gaps and not failures
    if can_train:
        rows = [{"query": r["query"], "positive": r["positive_passage"],
                 "negatives": [n["negative"] for n in by_qa[r["candidate_id"]]][:4],
                 "work_id": r["work_id"], "book_title": r["book_title"], "chapter": r["chapter"],
                 "source_start": r["source_start"], "source_end": r["source_end"],
                 "source_hash": r["source_hash"], "category": r["question_category"],
                 "difficulty": r["difficulty"], "split": r["split"], "review_status": r["review_status"],
                 "candidate_id": r["candidate_id"]} for r in train]
        pq.write_table(pa.Table.from_pylist(rows), PARQUET, compression="zstd")
    report = {"negative_candidates": len(negatives), "decisions": dict(counts),
              "valid_after_safety": len(valid), "false_negative": counts["FALSE_NEGATIVE"],
              "uncertain": counts["UNCERTAIN"], "reviewed_train": len(train),
              "reviewed_validation": len(validation), "queries_without_valid_negative": gaps,
              "negatives_per_query": dict(Counter(len(by_qa.get(r["candidate_id"], [])) for r in train)),
              "safety_failures": failures, "training_file_created": can_train,
              "training_file": str(PARQUET) if can_train else None}
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("valid_after_safety", "false_negative", "uncertain",
                                               "reviewed_train", "reviewed_validation",
                                               "training_file_created")}, indent=2))


if __name__ == "__main__":
    main()
