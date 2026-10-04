"""Render source-first QA review packet and editable review CSV."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from rag_domain_common import TRAINING, controls

CANDIDATES = TRAINING / "luminar" / "domain_qa_candidates_v1.jsonl"
REVIEW = TRAINING / "luminar" / "domain_qa_review_v1.csv"
PACKET = TRAINING / "reports" / "rag_domain_qa_review_v1.md"
CHECKS = ("clear", "premise_correct", "direct_answer", "evidence_correct",
          "no_outside_knowledge", "no_missing_context", "category_reasonable",
          "not_metadata", "unambiguous", "test_clean")


def main():
    controls()
    rows = [json.loads(line) for line in CANDIDATES.read_text(encoding="utf-8").splitlines() if line.strip()]
    fields = ["candidate_id", "qa_review", "reviewer", "review_notes", "edited_question",
              "edited_answer", "edited_evidence", "edited_category", "edited_difficulty", *CHECKS]
    existing = {}
    if REVIEW.exists():
        with REVIEW.open(newline="", encoding="utf-8-sig") as file:
            existing = {item["candidate_id"]: item for item in csv.DictReader(file)}
    expected = {row["candidate_id"] for row in rows}
    if set(existing) - expected:
        raise RuntimeError("Review CSV contains IDs absent from the candidate file")
    with REVIEW.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(existing.get(row["candidate_id"], {"candidate_id": row["candidate_id"]}))
    lines = ["# LuminaR domain QA source review", "", "**EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS**", "",
             "**Diagnostic packet:** this generation batch failed a semantic-quality spot review. Do not bulk-approve it. Edit or reject each item against the source; this packet is far below the 200-reviewed-example training gate.", "",
             "Mark the companion CSV with APPROVE, REJECT, or EDIT; name the reviewer and mark every checklist column YES for an approved item. For EDIT, enter only changed fields. These are unreviewed candidates. Retriever rankings are intentionally absent.", ""]
    for row in rows:
        lines += [f"## {row['candidate_id']} — {row['book_title']}", "",
                  f"- Split: {row['split']}; chapter: {row['chapter']}; category: {row['question_category']}; difficulty: {row['difficulty']}",
                  f"- Question: {row['query']}", f"- Short answer: {row['short_answer']}",
                  f"- Evidence: {row['evidence_text']}",
                  f"- Source offsets: {row['evidence_start']}–{row['evidence_end']}; chunk: {row['chunk_id']}",
                  f"- Validation note: {row['validation_notes']}", "", "```text", row['positive_passage'], "```", ""]
    PACKET.parent.mkdir(parents=True, exist_ok=True)
    PACKET.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"candidates": len(rows), "packet": str(PACKET), "review_csv": str(REVIEW)}))


if __name__ == "__main__":
    main()
