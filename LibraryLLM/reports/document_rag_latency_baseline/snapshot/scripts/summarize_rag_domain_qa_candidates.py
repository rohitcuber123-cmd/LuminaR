"""Summarize interrupted bounded QA probes without admitting any candidates."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from rag_domain_common import TRAINING, controls

LUM = TRAINING / "luminar"
REPORT = TRAINING / "reports" / "rag_domain_qa_generation_v1.json"

# Source-first assistant spot findings; these are not human review decisions.
SPOT_FINDINGS = {
    "DQ00001": "Ambiguous unnamed man; needs clearer named context.",
    "DQ00002": "Answer is visible but the question is awkward and purely literal; needs edit.",
    "DQ00003": "Question introduces hearing news, absent from the evidence.",
    "DQ00004": "Daniel Nugent is the brother-in-law; the selected witness is unnamed.",
    "DQ00005": "Low-value, awkward event question; answer is an adjective.",
    "DQ00006": "Selected answer fragment does not state the cause clearly.",
    "DQ00007": "Temporal answer 'before)' is meaningless in context.",
    "DQ00008": "Purpose is unspecified, so the passage does not answer why.",
    "DQ00009": "Short answer is an incomplete phrase.",
    "DQ00010": "Answer depends on omitted referents and is too generic.",
}


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    _, split, _ = controls()
    attempts = read_jsonl(LUM / "domain_qa_attempts_v1.jsonl")
    candidates = read_jsonl(LUM / "domain_qa_candidates_v1.jsonl")
    old_attempts = read_jsonl(TRAINING / "reports" / "domain_qa_attempts_rejected_probe_v1.jsonl")
    old_candidates = read_jsonl(TRAINING / "reports" / "domain_qa_candidates_rejected_probe_v1.jsonl")
    qa_review = json.loads((TRAINING / "reports" / "rag_domain_qa_finalization_v1.json").read_text(encoding="utf-8"))
    quality = json.loads((TRAINING / "reports" / "rag_domain_passage_quality_v1.json").read_text(encoding="utf-8"))
    if any(c["work_id"] not in split["train_work_ids"] for c in candidates + old_candidates):
        raise RuntimeError("Probe included a non-TRAIN work")
    report = {
        "result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS",
        "passage_quality_counts": quality["classification_counts"],
        "first_probe": {"attempts": len(old_attempts), "auto_validated": len(old_candidates),
                        "duplicate_source_chunks": len(old_candidates) - len({r["chunk_id"] for r in old_candidates}),
                        "stopped_reason": "Unsupported premises, category errors, and duplicate source reuse"},
        "refined_probe": {"attempts": len(attempts), "auto_validated": len(candidates),
                          "auto_rejections": dict(Counter(reason for a in attempts for reason in a["rejections"])),
                          "category_counts": dict(Counter(c["question_category"] for c in candidates)),
                          "difficulty_counts": dict(Counter(c["difficulty"] for c in candidates)),
                          "duplicate_source_chunks": len(candidates) - len({r["chunk_id"] for r in candidates}),
                          "stopped_reason": "Assistant source spot audit found no candidate ready as-is"},
        "assistant_source_spot_findings": SPOT_FINDINGS,
        "human_reviewed_train": qa_review["reviewed_train"],
        "human_reviewed_validation": qa_review["reviewed_validation"],
        "negative_candidates_mined": 0,
        "training_gate": "CLOSED_DOMAIN_DATA_QUALITY",
    }
    if set(SPOT_FINDINGS) != {c["candidate_id"] for c in candidates}:
        raise RuntimeError("Spot findings no longer cover the diagnostic candidate set")
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"first_probe": report["first_probe"], "refined_probe": report["refined_probe"],
                      "human_reviewed_train": report["human_reviewed_train"],
                      "training_gate": report["training_gate"]}, indent=2))


if __name__ == "__main__":
    main()
