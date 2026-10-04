"""V7R1 evidence diagnostics and strict contract layered over V7 validators."""
from __future__ import annotations

import unicodedata

from rag_domain_common import CATEGORIES
from rag_domain_qa_assisted_v7 import candidate_record

DIFFICULTIES = ("EASY", "MEDIUM", "HARD")


def all_offsets(haystack: str, needle: str) -> list[int]:
    if not needle or not needle.strip():
        return []
    out = []
    start = 0
    while True:
        at = haystack.find(needle, start)
        if at < 0:
            return out
        out.append(at)
        start = at + 1


def evidence_diagnostics(passage: str, evidence: str, answer: str) -> dict:
    offsets = all_offsets(passage, evidence)
    answer_offsets = all_offsets(evidence, answer)
    # Normalization is diagnostic only. It never produces an accepted span.
    normalized_match = (unicodedata.normalize("NFKC", evidence) in
                        unicodedata.normalize("NFKC", passage)) if evidence and evidence.strip() else False
    return {"evidence_exact_match_count": len(offsets),
            "evidence_match_offsets": offsets,
            "answer_exact_match_count_in_evidence": len(answer_offsets),
            "normalization_applied": False,
            "diagnostic_nfkc_match": normalized_match}


def candidate_record_v7r1(row, generated, *, context, context_start, generator_model, source):
    evidence = generated["evidence_quote"]
    answer = generated["short_answer"]
    diag = evidence_diagnostics(row["text"], evidence, answer)
    reasons = []
    if generated["category"] not in CATEGORIES:
        reasons.append("INVALID_CATEGORY")
    if generated["difficulty"] not in DIFFICULTIES:
        reasons.append("INVALID_DIFFICULTY")
    if not evidence or not evidence.strip():
        reasons.append("EMPTY_EVIDENCE")
    elif diag["evidence_exact_match_count"] == 0:
        reasons.append("EVIDENCE_NOT_EXACT_IN_POSITIVE")
    elif diag["evidence_exact_match_count"] > 1:
        # No model offset exists in the strict schema. An arbitrary first match
        # would falsely claim an authoritative source position.
        reasons.append("AMBIGUOUS_EVIDENCE_OCCURRENCE")
    if not answer or not answer.strip() or diag["answer_exact_match_count_in_evidence"] == 0:
        reasons.append("ANSWER_NOT_EXACT_IN_EVIDENCE")
    if reasons:
        return None, sorted(set(reasons)), diag
    record, old_reasons = candidate_record(row, generated, context=context,
                                            context_start=context_start,
                                            generator_model=generator_model, source=source)
    if old_reasons:
        # All exact-match and enum conditions above are already satisfied;
        # retain the shared source, answer-quality and question checks.
        return None, old_reasons, diag
    record["generation_version"] = "v7r1"
    record.update(diag)
    return record, [], diag
