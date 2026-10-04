"""V7R3 word references over the frozen V7R2 presentation units."""
from __future__ import annotations

import re
import unicodedata

from rag_domain_qa_source_units_v7r2 import reconstruct_evidence

WORD_VERSION = "v7r3-word-units-1"
# Keep contractions, hyphenated words and initials together; punctuation is selectable
# separately, so source surfaces and offsets always remain exact.
TOKEN = re.compile(r"(?:Mr|Mrs|Ms|Dr|St)\.|[^\W_]+(?:[’'_-][^\W_]+)*|[^\s]", re.UNICODE)
PUNCT = set(".,;:!?()[]{}\"“”‘’—–-")


def build_word_units(view, units):
    result = []
    for unit in units:
        words = []
        for i, match in enumerate(TOKEN.finditer(unit["presentation_text"]), 1):
            start = unit["presentation_start"] + match.start()
            end = unit["presentation_start"] + match.end()
            a, b = view.map_presentation_span_to_authoritative(start, end)
            words.append({"unit_id": unit["unit_id"], "word_id": f"W{i:03d}",
                          "presentation_start": start, "presentation_end": end,
                          "authoritative_start": a, "authoritative_end": b,
                          "absolute_source_start": view.authoritative_source_start + a,
                          "absolute_source_end": view.authoritative_source_start + b,
                          "presentation_surface": view.presentation_text[start:end],
                          "authoritative_surface": view.authoritative_text[a:b]})
        result.append({"unit_id": unit["unit_id"], "words": words})
    return result


def tagged_units(units, word_units):
    lines = []
    for unit, entry in zip(units, word_units):
        lines.append(f"[{unit['unit_id']}] " + " ".join(
            f"[{w['word_id']}] {w['presentation_surface']}" for w in entry["words"]))
    return "\n".join(lines)


def resolve_word_span(view, units, word_units, candidate):
    unit_id = candidate["answer_unit_id"]
    evidence_ids = candidate["evidence_unit_ids"]
    evidence, reasons = reconstruct_evidence(view, units, evidence_ids)
    if reasons:
        return None, None, reasons
    entry = next((e for e in word_units if e["unit_id"] == unit_id), None)
    if entry is None or unit_id not in evidence_ids:
        return None, None, ["ANSWER_SPAN_CROSSES_UNIT"]
    words = entry["words"]
    lookup = {w["word_id"]: i for i, w in enumerate(words)}
    start_id, end_id = candidate["answer_start_word_id"], candidate["answer_end_word_id"]
    if start_id not in lookup or end_id not in lookup:
        return None, None, ["INVALID_ANSWER_WORD_ID"]
    start, end = lookup[start_id], lookup[end_id]
    if start > end:
        return None, None, ["ANSWER_SPAN_REVERSED"]
    while start <= end and all(ch in PUNCT for ch in words[start]["presentation_surface"]):
        start += 1
    while end >= start and all(ch in PUNCT for ch in words[end]["presentation_surface"]):
        end -= 1
    if start > end:
        return None, None, ["ANSWER_SPAN_PUNCTUATION_ONLY"]
    limit = 30 if candidate["fact_type"] in {"CAUSE", "MOTIVATION", "QUOTE_OR_PHRASE"} else 20
    if end - start + 1 > limit:
        return None, None, ["ANSWER_SPAN_TOO_LONG"]
    p_start, p_end = words[start]["presentation_start"], words[end]["presentation_end"]
    if p_start >= p_end:
        return None, None, ["ANSWER_SPAN_EMPTY"]
    a, b = view.map_presentation_span_to_authoritative(p_start, p_end)
    answer = view.authoritative_text[a:b]
    if not answer.strip():
        return None, None, ["ANSWER_SPAN_EMPTY"]
    if all(unicodedata.category(ch).startswith("P") or ch.isspace() for ch in answer):
        return None, None, ["ANSWER_SPAN_PUNCTUATION_ONLY"]
    if not (evidence["evidence_start_in_passage"] <= a < b <= evidence["evidence_end_in_passage"]):
        return None, None, ["ANSWER_SPAN_CROSSES_UNIT"]
    return {"answer_presentation_text": view.presentation_text[p_start:p_end],
            "answer_authoritative_text": answer,
            "answer_presentation_start": p_start, "answer_presentation_end": p_end,
            "answer_authoritative_start": a, "answer_authoritative_end": b,
            "absolute_answer_start": view.authoritative_source_start + a,
            "absolute_answer_end": view.authoritative_source_start + b,
            "answer_start_word_id_resolved": words[start]["word_id"],
            "answer_end_word_id_resolved": words[end]["word_id"]}, evidence, []
