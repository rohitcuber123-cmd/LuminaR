"""Controlled V7R0/V7R1/V7R2 comparison on identical 50 passages."""
from __future__ import annotations

import argparse
from collections import Counter
import json

from rag_domain_common import TRAINING
from rag_domain_qa_assisted_v7 import strict_json
from rag_domain_qa_assisted_v7r2 import strict_json_v7r2
from validate_rag_domain_qa_assisted_v7r2 import read_jsonl, validate
from validate_rag_domain_qa_assisted_v7r3 import validate as validate_v7r3


QUESTION_CODES = ("UNRESOLVED_PRONOUN", "QUESTION_UNRESOLVED_REFERENT", "QUESTION_TOO_GENERIC",
                  "QUESTION_LENGTH_OR_FORMAT", "GENERIC_METADATA_QUESTION", "TRIVIAL_METADATA",
                  "QUESTION_CONTAINS_ANSWER", "CONTEXT_ONLY_NAMED_REFERENCE", "CATEGORY_QUESTION_MISMATCH")
ANSWER_COMPLETENESS_CODES = ("ANSWER_TOO_VAGUE", "TRUNCATED_ANSWER", "ANSWER_TYPE_MISMATCH",
                             "ANSWER_UNRESOLVED_REFERENT", "ANSWER_TOO_LONG")
UNIT_CODES = ("INVALID_EVIDENCE_UNIT_ID", "NONCONTIGUOUS_EVIDENCE_UNITS", "TOO_MANY_EVIDENCE_UNITS",
              "INVALID_ANSWER_UNIT_ID", "ANSWER_UNIT_OUTSIDE_EVIDENCE")
SOURCE_CODES = ("SOURCE_MAPPING_FAILED", "SOURCE_HASH_INTEGRITY", "SOURCE_VIEW_INTEGRITY_FAILED",
                "SOURCE_UNIT_INTEGRITY_FAILED", "AUTHORING_CONTEXT_NOT_AUTHORITATIVE")


def collect(version):
    raw = read_jsonl(TRAINING / "luminar" / f"domain_qa_assisted_{version}_raw.jsonl")
    auto = read_jsonl(TRAINING / "luminar" / f"domain_qa_assisted_{version}_auto_checked.jsonl")
    rejected = read_jsonl(TRAINING / "luminar" / f"domain_qa_assisted_{version}_rejected.jsonl")
    report = json.loads((TRAINING / "reports" / f"rag_domain_qa_assisted_{version}_generation.json").read_text(encoding="utf-8"))
    summary = report["summary"]
    reasons = Counter(x for item in rejected for x in item.get("rejection_reasons", []))
    parse = strict_json_v7r2 if version == "v7r2" else strict_json
    zero = sum(1 for r in raw if (p := parse(r["generator_raw"])) is not None and not p["candidates"])
    common = {"passages": len(raw),
              "raw_proposals": summary.get("raw_proposals", summary.get("raw_generated_QA", 0)),
              "zero_candidate_passages": zero,
              "invalid_json": summary.get("invalid_json", summary.get("format_failures", 0)),
              "invalid_category": reasons["INVALID_CATEGORY"],
              "invalid_difficulty": reasons["INVALID_DIFFICULTY"],
              "answer_completeness_failures": sum(reasons[x] for x in ANSWER_COMPLETENESS_CODES),
              "question_failures": sum(reasons[x] for x in QUESTION_CODES),
              "deterministic_passes": summary.get("deterministic_passes", 0),
              "semantic_SUPPORTED": summary.get("semantic_SUPPORTED", 0),
              "semantic_UNSUPPORTED": summary.get("semantic_UNSUPPORTED", 0),
              "semantic_UNCERTAIN": summary.get("semantic_UNCERTAIN", 0),
              "AUTO_CHECKED": len(auto)}
    if version == "v7r2":
        common.update({"evidence_failures": sum(reasons[x] for x in SOURCE_CODES),
                       "unit_reference_failures": sum(reasons[x] for x in UNIT_CODES),
                       "answer_presentation_match_failures": reasons["ANSWER_NOT_EXACT_IN_PRESENTATION"] + reasons["EMPTY_ANSWER"] + reasons["ANSWER_MAPPING_FAILED"],
                       "answer_ambiguity": reasons["AMBIGUOUS_ANSWER_OCCURRENCE"]})
    else:
        common.update({"evidence_failures": (reasons["EVIDENCE_NOT_UNIQUE_EXACT_IN_POSITIVE"] if version == "v7"
                                             else reasons["EVIDENCE_NOT_EXACT_IN_POSITIVE"] + reasons["EMPTY_EVIDENCE"]),
                       "unit_reference_failures": None,
                       "answer_presentation_match_failures": None,
                       "answer_ambiguity": None})
    return common


def collect_v7r3():
    base = TRAINING / "luminar"
    raw = read_jsonl(base / "domain_qa_assisted_v7r3_stage_a_raw.jsonl")
    auto = read_jsonl(base / "domain_qa_assisted_v7r3_auto_checked.jsonl")
    rejected = read_jsonl(base / "domain_qa_assisted_v7r3_rejected.jsonl")
    report = json.loads((TRAINING / "reports" / "rag_domain_qa_assisted_v7r3_generation.json").read_text(encoding="utf-8"))
    summary = report["summary"]
    reasons = Counter(x for item in rejected for x in item.get("rejection_reasons", []))
    return {"passages": len(raw), "raw_proposals": summary.get("stage_a_raw_selections", 0),
            "zero_candidate_passages": summary.get("stage_a_zero_candidate_passages", 0),
            "invalid_json": summary.get("invalid_stage_a_json", 0) + summary.get("invalid_stage_b_json", 0),
            "invalid_category": reasons["INVALID_CATEGORY"],
            "invalid_difficulty": reasons["INVALID_DIFFICULTY"],
            "answer_completeness_failures": reasons["ANSWER_SPAN_INCOMPLETE"],
            "question_failures": sum(v for k, v in reasons.items() if k.startswith("QUESTION_") or k in
                                     {"TRIVIAL_METADATA", "CONTEXT_ONLY_NAMED_REFERENCE", "CATEGORY_QUESTION_MISMATCH"}),
            "deterministic_passes": summary.get("deterministic_passes", 0),
            "semantic_SUPPORTED": summary.get("judge_SUPPORTED", 0),
            "semantic_UNSUPPORTED": summary.get("judge_UNSUPPORTED", 0),
            "semantic_UNCERTAIN": summary.get("judge_UNCERTAIN", 0),
            "AUTO_CHECKED": len(auto),
            "evidence_failures": sum(reasons[k] for k in SOURCE_CODES),
            "unit_reference_failures": sum(reasons[k] for k in UNIT_CODES),
            "answer_presentation_match_failures": 0,
            "answer_ambiguity": 0,
            "answer_span_failures": sum(v for k, v in reasons.items() if k.startswith("ANSWER_SPAN_") or k == "INVALID_ANSWER_WORD_ID"),
            "judge_invalid_json": summary.get("judge_invalid_json", 0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--versions", default="v7,v7r1,v7r2")
    args = ap.parse_args()
    if args.versions not in {"v7,v7r1,v7r2", "v7,v7r1,v7r2,v7r3"}:
        raise ValueError("The controlled comparison requires v7,v7r1,v7r2[,v7r3]")
    four = args.versions.endswith(",v7r3")
    validation = validate()
    runs = {v: collect(v) for v in ("v7", "v7r1", "v7r2")}
    if four:
        validation_v7r3 = validate_v7r3()
        runs["v7r3"] = collect_v7r3()
    if not all(run["passages"] == 50 for run in runs.values()):
        raise RuntimeError("The three generations did not use 50 passages")
    report = {"same_original_50_passages_in_order": validation["same_original_50_in_order"] and
              (validation_v7r3["same_original_50_in_order"] if four else True),
              "version_labels": {"v7": "V7R0 misconfigured control", "v7r1": "V7R1 exact-copy prompt",
                                 "v7r2": "V7R2 source references", **({"v7r3": "V7R3 answer-first, question-second"} if four else {})}, "runs": runs}
    path = TRAINING / "reports" / ("rag_domain_qa_v7_all_versions_comparison.json" if four else "rag_domain_qa_v7r0_v7r1_v7r2_comparison.json")
    if path.exists(): raise RuntimeError("V7 comparison exists; refusing overwrite")
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    labels = {"v7": "V7R0", "v7r1": "V7R1", "v7r2": "V7R2", **({"v7r3": "V7R3"} if four else {})}
    lines = ["# Controlled QA comparison" + (" through V7R3" if four else " through V7R2"), "",
             "All runs used the same 50 TRAIN passages. V7R0 was a misconfigured control; counts of failure reasons can overlap.",
             "Downstream checks are censored by earlier deterministic failures. A dash means the interface did not have that check.",
             "", "| Metric | " + " | ".join(labels.values()) + " |", "|---|" + "---:|" * len(labels)]
    keys = list(dict.fromkeys(k for run in runs.values() for k in run))
    for key in keys:
        cells = ["—" if runs[v].get(key) is None else str(runs[v][key]) for v in labels]
        lines.append(f"| {key.replace('_', ' ')} | {' | '.join(cells)} |")
    lines.append("")
    (TRAINING / "reports" / ("rag_domain_qa_v7_all_versions_comparison.md" if four else "rag_domain_qa_v7r0_v7r1_v7r2_comparison.md")).write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__": main()
