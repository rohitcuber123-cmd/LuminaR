"""Read-only audits for the previous batch and proposition-first v2 pilot."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from rag_domain_common import ROOT, SOURCE_MAP, TRAINING, controls
from rag_domain_qa_v2 import EntailmentResult, generic_legacy_checks, validate


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sources_for(records):
    mapping = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    return {wid: (ROOT / mapping[wid]["source_file"]).read_text(encoding="utf-8")
            for wid in {row["work_id"] for row in records}}


def old_batch(path):
    records = read_jsonl(path)
    sources = sources_for(records)
    counts, outcomes = Counter(), []
    for row in records:
        source = sources[row["work_id"]]
        reasons = generic_legacy_checks(row)
        if (source[row["source_start"]:row["source_end"]] != row["positive_passage"] or
                source[row["evidence_start"]:row["evidence_end"]] != row["evidence_text"] or
                hashlib.sha256(source.encode("utf-8")).hexdigest() != row["source_hash"]):
            reasons.append("SOURCE_MAPPING_FAILED")
        reasons = sorted(set(reasons))
        counts.update(reasons)
        outcomes.append({"candidate_id": row["candidate_id"], "status": "FAIL" if reasons else "PASS",
                         "rejection_codes": reasons})
    report = {"result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS",
              "input": str(path), "total": len(records), "pass": sum(not x["rejection_codes"] for x in outcomes),
              "fail": sum(bool(x["rejection_codes"]) for x in outcomes),
              "reason_distribution": dict(counts), "items": outcomes,
              "note": "Old question-first records lack propositions. This is a read-only diagnostic, not a migrated review decision."}
    out = TRAINING / "reports" / "rag_domain_qa_old_batch_revalidation_v2.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# Old domain QA batch: proposition-first revalidation", "",
             "**EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS**", "",
             f"Read-only audit: {report['pass']} PASS; {report['fail']} FAIL of {len(records)}.",
             "Legacy records cannot become AUTO_VALIDATED without a source-grounded proposition.", "",
             "## Generic rejection reasons", ""]
    lines += [f"- `{key}`: {value}" for key, value in sorted(counts.items())]
    lines += ["", "## Per candidate", ""]
    lines += [f"- {x['candidate_id']}: {', '.join(x['rejection_codes'])}" for x in outcomes]
    (TRAINING / "reports" / "rag_domain_qa_old_batch_revalidation_v2.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("total", "pass", "fail", "reason_distribution")}, indent=2))


class CachedJudge:
    def judge(self, candidate):
        saved = (candidate.get("auto_validation") or {}).get("entailment") or {}
        if saved.get("label") not in {"ENTAILED", "NOT_ENTAILED", "UNCERTAIN"}:
            return EntailmentResult("UNCERTAIN", "Missing cached judge output", "")
        return EntailmentResult(saved["label"], saved.get("reason", ""), saved.get("supporting_text", ""))


def v2_batch(path):
    records = read_jsonl(path)
    _, split, labels = controls()
    sources = sources_for(records)
    eval_queries = [x["question"] for x in labels]
    outcomes, reasons, seen = [], Counter(), []
    for row in records:
        checked = validate(row, sources[row["work_id"]], eval_queries=eval_queries,
                           seen_queries=seen, test_works=split["protected_test_work_ids"], judge=CachedJudge())
        if checked["review_status"] == "AUTO_VALIDATED": seen.append(checked["question"])
        codes = checked["auto_validation"]["rejection_reasons"]
        reasons.update(codes)
        outcomes.append({"candidate_id": row["candidate_id"], "original_status": row["review_status"],
                         "revalidated_status": checked["review_status"], "rejection_codes": codes})
    report = {"result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS", "total": len(outcomes),
              "statuses": dict(Counter(x["revalidated_status"] for x in outcomes)),
              "rejection_reasons": dict(reasons), "items": outcomes,
              "note": "Cached semantic judgment is checked against deterministic validation; no human review inferred."}
    out = TRAINING / "reports" / "rag_domain_qa_validation_v2.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("total", "statuses", "rejection_reasons")}, indent=2))


def v3_batch(path):
    from rag_domain_qa_v3 import validate_v3
    records = read_jsonl(path)
    _, split, labels = controls()
    sources = sources_for(records)
    seen, outcomes, reasons = [], [], Counter()
    for row in records:
        checked = validate_v3(row, sources[row["work_id"]],
                              eval_queries=[x["question"] for x in labels],
                              test_works=split["protected_test_work_ids"], seen_queries=seen)
        if checked["review_status"] == "AUTO_VALIDATED": seen.append(checked["question"])
        codes = checked["auto_validation"]["rejection_reasons"]
        reasons.update(codes)
        outcomes.append({"candidate_id": row["candidate_id"], "status": checked["review_status"],
                         "rejection_codes": codes})
    report = {"result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS",
              "total": len(records), "statuses": dict(Counter(x["status"] for x in outcomes)),
              "rejection_reasons": dict(reasons), "items": outcomes,
              "review_status": "UNREVIEWED"}
    out = TRAINING / "reports" / "rag_domain_qa_validation_v3.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("total", "statuses", "rejection_reasons")}, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path)
    ap.add_argument("--report-old-batch", action="store_true")
    ap.add_argument("--version", default="v2")
    args = ap.parse_args()
    controls()
    if args.report_old_batch:
        old_batch(args.input or TRAINING / "luminar" / "domain_qa_candidates_v1.jsonl")
    elif args.version == "v2":
        v2_batch(args.input or TRAINING / "luminar" / "domain_qa_candidates_v2.jsonl")
    elif args.version == "v3":
        v3_batch(args.input or TRAINING / "luminar" / "domain_qa_v3_high_confidence.jsonl")
    else:
        raise ValueError("Only v2/v3 validation is supported by this script")


if __name__ == "__main__": main()
