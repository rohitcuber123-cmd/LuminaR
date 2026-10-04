"""Render an unreviewed V7R3 human decision packet only after the quality gate."""
from __future__ import annotations

import csv
import json

from rag_domain_common import TRAINING
from validate_rag_domain_qa_assisted_v7r3 import read_jsonl, validate

FIELDS = ("candidate_id", "decision", "reviewer", "review_date", "premise_correct", "question_clear",
          "answer_correct", "evidence_supports_answer", "self_contained", "category_correct",
          "no_outside_context", "edited_question", "edited_answer_start_word_id",
          "edited_answer_end_word_id", "edited_evidence_unit_ids", "edited_category", "review_notes")


def main():
    validation = validate()
    audit = json.loads((TRAINING / "reports" / "rag_domain_qa_assisted_v7r3_audit.json").read_text(encoding="utf-8"))
    if not audit["review_packet_gate_passed"] or validation["auto_checked"] < 20:
        raise RuntimeError("V7R3 human review packet gate is closed")
    auto = read_jsonl(TRAINING / "luminar" / "domain_qa_assisted_v7r3_auto_checked.jsonl")
    csv_path = TRAINING / "reports" / "rag_domain_qa_assisted_review_v7r3.csv"
    md_path = TRAINING / "reports" / "rag_domain_qa_assisted_review_v7r3.md"
    if csv_path.exists() or md_path.exists():
        raise RuntimeError("Review packet exists; refusing overwrite")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        for c in auto:
            writer.writerow({"candidate_id": c["candidate_id"]})
    lines = ["# V7R3 human source review packet", "", "Every row is AUTO_CHECKED and unreviewed.",
             "Enter APPROVE, EDIT, or REJECT in the CSV. For edits, use question text and unit/word IDs; "
             "the source answer and evidence are reconstructed by code.", ""]
    for c in auto:
        lines += [f"## {c['candidate_id']}", "", f"Source hash: `{c['source_hash']}`", "",
                  f"Question: {c['question']}", "", f"Answer: {c['short_answer']}", "",
                  f"Category: {c['category_validated']}; Answer type: {c['answer_type']}", "",
                  f"Answer reference: {c['answer_unit_id']} {c['answer_start_word_id']}–{c['answer_end_word_id']}", "",
                  f"Evidence units: {', '.join(c['evidence_unit_ids'])}", "", "Authoritative evidence:", "",
                  "> " + c["evidence_quote"].replace("\n", "\n> "), ""]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"review_packet_rows": len(auto), "human_review_status": "WAITING_FOR_HUMAN_REVIEW"}))


if __name__ == "__main__": main()
