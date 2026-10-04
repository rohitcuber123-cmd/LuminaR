"""Admit only explicitly reviewed, fully checked source-grounded QA examples."""
from __future__ import annotations

import csv
import hashlib
import json

from rag_domain_common import ROOT, SOURCE_MAP, TRAINING, controls, normalized_query, validate_candidate
from render_rag_domain_qa_review import CANDIDATES, CHECKS, REVIEW

OUT = TRAINING / "luminar" / "domain_qa_reviewed_v1.jsonl"
REPORT = TRAINING / "reports" / "rag_domain_qa_finalization_v1.json"


def main():
    _, _, labels = controls()
    eval_queries = [q["question"] for q in labels]
    source_map = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    source_cache = {}
    candidates = {x["candidate_id"]: x for line in CANDIDATES.read_text(encoding="utf-8").splitlines()
                  if line.strip() for x in [json.loads(line)]}
    with REVIEW.open(newline="", encoding="utf-8-sig") as file:
        decisions = list(csv.DictReader(file))
    if len(decisions) != len(candidates) or {r["candidate_id"] for r in decisions} != set(candidates):
        raise RuntimeError("Review CSV candidate IDs do not match frozen candidate set")
    approved = []
    counts = {"APPROVE": 0, "REJECT": 0, "EDIT": 0, "UNREVIEWED": 0, "INVALID_REVIEW": 0}
    failures = []
    seen_queries = set()
    for decision in decisions:
        key = decision["candidate_id"]
        action = (decision["qa_review"] or "").strip().upper()
        if action not in ("APPROVE", "REJECT", "EDIT"):
            counts["UNREVIEWED"] += 1
            continue
        counts[action] += 1
        if action == "REJECT":
            continue
        if not decision["reviewer"].strip() or any(decision[c].strip().upper() != "YES" for c in CHECKS):
            counts["INVALID_REVIEW"] += 1
            failures.append({"candidate_id": key, "reason": "Missing reviewer or YES checklist"})
            continue
        candidate = candidates[key]
        wid = candidate["work_id"]
        if wid not in source_cache:
            source_cache[wid] = (ROOT / source_map[wid]["source_file"]).read_text(encoding="utf-8")
        source = source_cache[wid]
        if (hashlib.sha256(source.encode("utf-8")).hexdigest() != candidate["source_hash"] or
                source[candidate["source_start"]:candidate["source_end"]] != candidate["positive_passage"]):
            counts["INVALID_REVIEW"] += 1
            failures.append({"candidate_id": key, "reason": "Source hash or passage offsets changed"})
            continue
        row = {"text": candidate["positive_passage"], "source_start_char": candidate["source_start"],
               "source_end_char": candidate["source_end"], "source_sha256": candidate["source_hash"],
               "token_count": candidate["token_count"], "work_id": candidate["work_id"],
               "title": candidate["book_title"], "chapter": candidate["chapter"],
               "chunk_id": candidate["chunk_id"], "split": candidate["split"]}
        generated = {"question": decision["edited_question"].strip() or candidate["query"],
                     "short_answer": decision["edited_answer"].strip() or candidate["short_answer"],
                     "evidence_quote": decision["edited_evidence"].strip() or candidate["evidence_text"],
                     "category": decision["edited_category"].strip() or candidate["question_category"],
                     "difficulty": decision["edited_difficulty"].strip() or candidate["difficulty"]}
        result, reasons = validate_candidate(row, generated, eval_queries)
        if result is None:
            counts["INVALID_REVIEW"] += 1
            failures.append({"candidate_id": key, "reason": reasons})
            continue
        normalized = normalized_query(result["query"])
        if normalized in seen_queries:
            counts["INVALID_REVIEW"] += 1
            failures.append({"candidate_id": key, "reason": "Duplicate reviewed question"})
            continue
        seen_queries.add(normalized)
        result.update({"candidate_id": key, "review_status": "REVIEWED",
                       "reviewer": decision["reviewer"].strip(),
                       "review_notes": decision["review_notes"].strip(),
                       "review_action": action, "token_count": candidate["token_count"]})
        approved.append(result)
    if approved:
        OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in approved) + "\n", encoding="utf-8")
    elif OUT.exists():
        raise RuntimeError("Existing reviewed output present but review CSV has no valid approvals")
    report = {"candidates": len(candidates), "decisions": counts,
              "reviewed_train": sum(r["split"] == "TRAIN" for r in approved),
              "reviewed_validation": sum(r["split"] == "VALIDATION" for r in approved),
              "failures": failures, "output": str(OUT) if approved else None}
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("candidates", "decisions", "reviewed_train", "reviewed_validation")}, indent=2))


if __name__ == "__main__":
    main()
