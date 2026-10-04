"""Classify every v3 MEDIUM proposition before changing extraction rules."""
from __future__ import annotations

from collections import Counter, defaultdict
import json
import re

from rag_domain_common import TRAINING, controls


def diagnose(record):
    p = record["proposition"]
    relation = record["relation_type"]
    clause = record["clause_text"]
    subject = p.get("subject", "")
    complement = p.get("object", "")
    codes = []
    possible = False
    if relation == "ATTRIBUTE":
        if subject.casefold() in {"everything", "something", "nothing", "someone", "anyone"}:
            codes.append("AMBIGUOUS_SUBJECT")
        if complement.casefold() in {"more", "very", "with", "beyond", "again", "able", "inclined", "aware"}:
            codes.append("ATTRIBUTE_COMPLEMENT_UNSAFE")
        if re.search(r"\b(?:and|when|while)\b", clause, re.I) and not codes:
            codes.append("CLAUSE_TOO_COMPLEX")
        if complement.casefold() in {"pensive", "thoughtful", "silent", "disjointed"}:
            codes.append("ONE_WORD_STATE_REQUIRES_FULL_STATE_SLOT")
            possible = True
        if not codes: codes.append("ATTRIBUTE_COMPLEMENT_UNSAFE")
    elif relation == "TEMPORAL_AT":
        if re.search(r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+o['’]clock\b",
                     p.get("time", ""), re.I):
            codes.append("V2_TIME_FORM_UNSUPPORTED")
        else: codes.append("TEMPORAL_EXPRESSION_INCOMPLETE")
    elif relation == "MOTIVATION":
        if p.get("predicate", "").casefold() in {"wished", "hoped", "intended"}:
            codes.append("V2_CAUSAL_MARKER_UNSUPPORTED")
        if re.search(r"\b(?:me|him|her|them|it)\b", p.get("cause", ""), re.I):
            codes.append("PRONOUN_UNRESOLVED")
    else:
        codes.append("EVIDENCE_CONTRACT_INCOMPLETE")
    return sorted(set(codes)), possible


def main():
    controls()
    path = TRAINING / "luminar" / "domain_qa_v3_medium_low.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    reasons, families, surfaces = Counter(), Counter(), defaultdict(list)
    analyzed = []
    for row in rows:
        codes, possible = diagnose(row)
        reasons.update(codes)
        families[row["relation_type"]] += 1
        key = row["relation_type"] + ":" + "+".join(codes)
        surfaces[key].append(row["clause_text"])
        analyzed.append({"candidate_id": row.get("candidate_id"), "relation": row["relation_type"],
                         "clause": row["clause_text"], "confidence_reasons": codes,
                         "deterministic_high_possible": possible,
                         "reason_note": "A new source-grounded rule is required; confidence is not promoted by threshold."})
    report = {"result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS",
              "medium_count": len(rows), "by_relation": dict(families),
              "reason_distribution": dict(reasons),
              "surface_groups": {k: {"count": len(v), "representative_clauses": v[:3]}
                                 for k, v in sorted(surfaces.items())},
              "potential_high_after_new_rule": sum(x["deterministic_high_possible"] for x in analyzed),
              "records": analyzed}
    out = TRAINING / "reports" / "rag_domain_qa_v4_medium_analysis.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# V4 prerequisite: all v3 MEDIUM propositions", "",
             "**EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS**", "",
             f"Records: {len(rows)}; reason counts overlap.", "",
             "## Reasons", ""]
    lines += [f"- {k}: {v}" for k, v in sorted(reasons.items())]
    lines += ["", "## Surface groups", ""]
    for key, group in sorted(report["surface_groups"].items()):
        lines += [f"### {key} — {group['count']}", ""]
        lines += [f"- {x}" for x in group["representative_clauses"]]
        lines += [""]
    lines += ["## Implication", "",
              "Most v3 MEDIUM attributes are not safely promotable: the complement is incomplete, "
              "the subject is vague, or multiple clauses interfere. A small exact state-change rule "
              "may promote a complete named-person state such as 'became pensive'. The spelled-out "
              "clock and 'wished to' forms remain MEDIUM under unchanged v2 checks. New v4 coverage "
              "must come mainly from independently grounded source patterns, not a blanket MEDIUM promotion.", ""]
    (TRAINING / "reports" / "rag_domain_qa_v4_medium_analysis.md").write_text(
        "\n".join(lines), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("medium_count", "by_relation", "reason_distribution",
                                                 "potential_high_after_new_rule")}, indent=2))


if __name__ == "__main__": main()
