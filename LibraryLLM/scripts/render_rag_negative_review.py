"""Render unranked source-first negative review packet and editable CSV."""
from __future__ import annotations

import csv
import json

from rag_domain_common import TRAINING, controls

CANDIDATES = TRAINING / "luminar" / "domain_negative_candidates_v1.jsonl"
REVIEW = TRAINING / "luminar" / "domain_negative_review_v1.csv"
PACKET = TRAINING / "reports" / "rag_hard_negative_review_v1.md"
CHECKS = ("does_not_answer", "no_alternate_answer", "no_evidence_overlap", "test_clean")


def main():
    controls()
    rows = [json.loads(line) for line in CANDIDATES.read_text(encoding="utf-8").splitlines() if line.strip()]
    fields = ["negative_id", "negative_review", "reviewer", "review_notes", *CHECKS]
    existing = {}
    if REVIEW.exists():
        with REVIEW.open(newline="", encoding="utf-8-sig") as file:
            existing = {item["negative_id"]: item for item in csv.DictReader(file)}
    expected = {row["negative_id"] for row in rows}
    if set(existing) - expected:
        raise RuntimeError("Negative review CSV contains IDs absent from candidate file")
    with REVIEW.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(existing.get(row["negative_id"], {"negative_id": row["negative_id"]}))
    lines = ["# LuminaR hard-negative review", "", "**EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS**", "",
             "Mark VALID, FALSE_NEGATIVE, or UNCERTAIN in the companion CSV. Only VALID with named reviewer and all YES checks can enter training.", ""]
    for row in rows:
        lines += [f"## {row['negative_id']} — {row['book_title']}", "",
                  f"- Question: {row['query']}", f"- Accepted answer: {row['short_answer']}",
                  f"- Accepted evidence: {row['evidence']}",
                  f"- Proposed negative chapter: {row['chapter']}; source offsets: {row['source_start']}–{row['source_end']}",
                  f"- Reason selected: {row['negative_type']}; baseline rank: {row['baseline_rank']}; similarity: {row['similarity']:.4f}", "", "### Positive", "", "```text",
                  row['positive'], "```", "", "### Candidate negative", "", "```text",
                  row['negative'], "```", ""]
    PACKET.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"candidates": len(rows), "packet": str(PACKET), "review_csv": str(REVIEW)}))


if __name__ == "__main__":
    main()
