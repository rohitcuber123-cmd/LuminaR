"""Side-by-side V7R0 misconfigured control vs fixed V7R1 metrics."""
from __future__ import annotations

from collections import Counter
import json

from rag_domain_common import TRAINING
from rag_domain_qa_assisted_v7 import strict_json
from validate_rag_domain_qa_assisted_v7r1 import read_jsonl, validate


def metrics(version):
    raw = read_jsonl(TRAINING / "luminar" / f"domain_qa_assisted_{version}_raw.jsonl")
    rejected = read_jsonl(TRAINING / "luminar" / f"domain_qa_assisted_{version}_rejected.jsonl")
    accepted = read_jsonl(TRAINING / "luminar" / f"domain_qa_assisted_{version}_auto_checked.jsonl")
    generation = json.loads((TRAINING / "reports" / f"rag_domain_qa_assisted_{version}_generation.json").read_text(encoding="utf-8"))
    reason = Counter(reason for r in rejected for reason in r.get("rejection_reasons", []))
    s = generation["summary"]
    zero = sum(1 for r in raw if (p := strict_json(r["generator_raw"])) is not None and not p["candidates"])
    evidence = (reason["EVIDENCE_NOT_UNIQUE_EXACT_IN_POSITIVE"] if version == "v7" else
                reason["EVIDENCE_NOT_EXACT_IN_POSITIVE"] + reason["EMPTY_EVIDENCE"])
    references = sum(reason[k] for k in ("UNRESOLVED_PRONOUN", "QUESTION_UNRESOLVED_REFERENT",
                                         "QUESTION_TOO_GENERIC", "GENERIC_METADATA_QUESTION",
                                         "TRIVIAL_METADATA", "QUESTION_CONTAINS_ANSWER"))
    return {"passages": len(raw), "raw_proposals": s.get("raw_generated_QA", 0),
            "zero_candidate_passages": zero, "invalid_json": s.get("format_failures", 0),
            "invalid_category": reason["INVALID_CATEGORY"],
            "invalid_difficulty": reason["INVALID_DIFFICULTY"],
            "evidence_exact_failures": evidence,
            "evidence_ambiguous_occurrences": reason["AMBIGUOUS_EVIDENCE_OCCURRENCE"],
            "answer_exact_failures": reason["ANSWER_NOT_EXACT_IN_EVIDENCE"],
            "question_reference_failures": references,
            "deterministic_passes": s.get("deterministic_passes", 0),
            "semantic_unsupported": s.get("semantic_UNSUPPORTED", 0),
            "semantic_uncertain": s.get("semantic_UNCERTAIN", 0),
            "AUTO_CHECKED": len(accepted)}


def main():
    validation = validate()
    old, new = metrics("v7"), metrics("v7r1")
    report = {"original_label": "V7R0 / MISCONFIGURED CONTROL",
              "corrected_label": "V7R1 / FIXED CONTRACT",
              "same_50_passages": validation["same_original_50_in_order"],
              "comparison": {key: {"v7_original": old[key], "v7r1_corrected": new[key]} for key in old}}
    output = TRAINING / "reports" / "rag_domain_qa_v7_vs_v7r1.json"
    if output.exists(): raise RuntimeError("Comparison exists; refusing overwrite")
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# V7R0 vs V7R1 controlled comparison", "",
             "The original V7R0 prompt omitted the required category enum; it is a misconfigured control, not a semantic-quality measurement.",
             "Both runs used exactly the same 50 TRAIN passages in the same order.", "",
             "Failure counts overlap. Downstream question and semantic metrics are censored when a proposal fails an earlier deterministic check.", "",
             "| Metric | V7R0 original | V7R1 corrected |", "|---|---:|---:|"]
    lines += [f"| {k.replace('_', ' ')} | {old[k]} | {new[k]} |" for k in old]
    lines.append("")
    (TRAINING / "reports" / "rag_domain_qa_v7_vs_v7r1.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__": main()
