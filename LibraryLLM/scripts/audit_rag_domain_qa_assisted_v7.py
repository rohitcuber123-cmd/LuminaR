"""Summarize the V7 pilot without promoting any proposal to human reviewed."""
from __future__ import annotations

from collections import Counter
import json

from rag_domain_common import TRAINING
from validate_rag_domain_qa_assisted_v7 import read_jsonl, validate


def main():
    result = validate()
    rejected = read_jsonl(TRAINING / "luminar" / "domain_qa_assisted_v7_rejected.jsonl")
    reasons = Counter(reason for item in rejected for reason in item.get("rejection_reasons", []))
    result["rejection_reasons"] = dict(reasons.most_common())
    result["gate_decision"] = ("READY_FOR_ENGINEERING_SOURCE_AUDIT" if result["review_packet_gate_passed"]
                               else "ASSISTED AUTHORING PILOT STILL TOO LOW QUALITY")
    result["human_review_status"] = "NOT_REVIEWED"
    report = TRAINING / "reports"
    (report / "rag_domain_qa_assisted_v7_audit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = ["# V7 assisted QA pilot audit", "", "Experimental only; no human review or training approval.", "",
             f"Decision: **{result['gate_decision']}**", "",
             f"- TRAIN passages: {result['selected_train_passages']}",
             f"- Raw proposals: {result['raw_generated_QA']}",
             f"- AUTO_CHECKED: {result['auto_checked']}",
             f"- Rejected records: {result['rejected_records']}",
             f"- Format failures: {result['format_failures']}",
             f"- TEST/evaluation span leakage: {result['test_leakage']}/{result['evaluation_span_leakage']}",
             "", "## Rejection reasons", ""]
    lines += [f"- {reason}: {count}" for reason, count in reasons.most_common()]
    lines += ["", "The generator used free-form category labels because the initial prompt omitted the required enum.",
              "It also often paraphrased the evidence rather than copying an exact source substring.",
              "The prompt has been corrected in code, but this fixed pilot was not rerun or relabeled.",
              "The <20 AUTO_CHECKED stop gate applies; no review packet, V8, V9, or V10 was produced.", ""]
    (report / "rag_domain_qa_assisted_v7_audit.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
