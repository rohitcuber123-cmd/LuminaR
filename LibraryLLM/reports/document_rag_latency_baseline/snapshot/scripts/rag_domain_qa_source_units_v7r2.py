"""Deterministic, reversible presentation view of authoritative QA passages."""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

SEGMENTATION_VERSION = "v7r2-sentence-units-1"


def _normalize_with_map(authoritative: str):
    chars, spans = [], []
    i = 0
    while i < len(authoritative):
        if authoritative[i].isspace():
            j = i + 1
            while j < len(authoritative) and authoritative[j].isspace():
                j += 1
            chars.append(" ")
            spans.append((i, j))
        else:
            j = i + 1
            while j < len(authoritative) and unicodedata.combining(authoritative[j]):
                j += 1
            normalized = unicodedata.normalize("NFKC", authoritative[i:j])
            for ch in normalized:
                chars.append(ch)
                spans.append((i, j))
        i = j
    return "".join(chars), spans


@dataclass(frozen=True)
class NormalizedSourceView:
    authoritative_text: str
    presentation_text: str
    presentation_to_authoritative_map: tuple[tuple[int, int], ...]
    authoritative_source_start: int
    source_hash: str

    @classmethod
    def build(cls, authoritative_text, authoritative_source_start, source_hash):
        presentation, spans = _normalize_with_map(authoritative_text)
        view = cls(authoritative_text, presentation, tuple(spans),
                   authoritative_source_start, source_hash)
        if not view.verify_round_trip():
            raise ValueError("Presentation/source map is not reversible")
        return view

    def map_presentation_span_to_authoritative(self, start, end):
        spans = self.presentation_to_authoritative_map
        if not 0 <= start < end <= len(spans):
            raise ValueError("Invalid presentation span")
        if start and spans[start] == spans[start - 1]:
            raise ValueError("Span starts inside a normalized character cluster")
        if end < len(spans) and spans[end - 1] == spans[end]:
            raise ValueError("Span ends inside a normalized character cluster")
        source_start, source_end = spans[start][0], spans[end - 1][1]
        recovered, _ = _normalize_with_map(self.authoritative_text[source_start:source_end])
        if recovered != self.presentation_text[start:end]:
            raise ValueError("Presentation span does not round-trip to source")
        return source_start, source_end

    def get_authoritative_text_for_presentation_span(self, start, end):
        a, b = self.map_presentation_span_to_authoritative(start, end)
        return self.authoritative_text[a:b]

    def verify_round_trip(self):
        text, spans = _normalize_with_map(self.authoritative_text)
        return (text == self.presentation_text and tuple(spans) == self.presentation_to_authoritative_map
                and len(text) == len(spans)
                and all(0 <= a < b <= len(self.authoritative_text) for a, b in spans)
                and all(spans[i][0] >= spans[i - 1][0] for i in range(1, len(spans))))


def _sentence_spans(text):
    """Find conservative sentence ends; merge tiny fragments."""
    spans = []
    start = 0
    for m in re.finditer(r"(?<=[.!?])\s+(?=[\"'“”‘’\ufffd]*[A-Z])", text):
        end = m.start()
        if end - start >= 35:
            spans.append((start, end))
            start = m.end()
    if start < len(text):
        spans.append((start, len(text)))
    if not spans and text:
        spans = [(0, len(text))]
    # Split only unusually long sentences at safe punctuation, retaining
    # complete clauses of useful size. Unsplit long sentences remain intact.
    bounded = []
    for a, b in spans:
        while b - a > 650:
            candidates = [m.end() for m in re.finditer(r"[;,]\s+", text[a:b])
                          if 200 <= m.end() <= 550 and b - (a + m.end()) >= 100]
            if not candidates:
                break
            cut = a + max(candidates)
            bounded.append((a, cut))
            a = cut
        bounded.append((a, b))
    merged = []
    for a, b in bounded:
        while a < b and text[a].isspace(): a += 1
        while b > a and text[b - 1].isspace(): b -= 1
        if a == b: continue
        if merged and b - a < 45:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    if len(merged) > 1 and merged[0][1] - merged[0][0] < 45:
        merged[1] = (merged[0][0], merged[1][1])
        merged.pop(0)
    return merged


def build_source_units(view: NormalizedSourceView):
    units = []
    for i, (start, end) in enumerate(_sentence_spans(view.presentation_text), 1):
        auth_start, auth_end = view.map_presentation_span_to_authoritative(start, end)
        units.append({"unit_id": f"S{i:02d}", "presentation_start": start,
                      "presentation_end": end,
                      "authoritative_start_in_passage": auth_start,
                      "authoritative_end_in_passage": auth_end,
                      "absolute_source_start": view.authoritative_source_start + auth_start,
                      "absolute_source_end": view.authoritative_source_start + auth_end,
                      "authoritative_text": view.authoritative_text[auth_start:auth_end],
                      "presentation_text": view.presentation_text[start:end],
                      "source_hash": view.source_hash})
    if not units:
        raise ValueError("No source units for passage")
    return units


def reconstruct_evidence(view, units, ids):
    lookup = {u["unit_id"]: (i, u) for i, u in enumerate(units)}
    reasons = []
    if not isinstance(ids, list) or len(ids) > 2:
        return None, ["TOO_MANY_EVIDENCE_UNITS"]
    if not ids or any(not isinstance(x, str) for x in ids) or len(ids) != len(set(ids)) or any(x not in lookup for x in ids):
        return None, ["INVALID_EVIDENCE_UNIT_ID"]
    indexes = [lookup[x][0] for x in ids]
    if indexes != list(range(indexes[0], indexes[0] + len(indexes))):
        return None, ["NONCONTIGUOUS_EVIDENCE_UNITS"]
    first, last = lookup[ids[0]][1], lookup[ids[-1]][1]
    a, b = first["authoritative_start_in_passage"], last["authoritative_end_in_passage"]
    if a < 0 or b > len(view.authoritative_text) or a >= b:
        return None, ["SOURCE_UNIT_INTEGRITY_FAILED"]
    return {"evidence_quote_authoritative": view.authoritative_text[a:b],
            "evidence_start_in_passage": a, "evidence_end_in_passage": b,
            "absolute_evidence_start": view.authoritative_source_start + a,
            "absolute_evidence_end": view.authoritative_source_start + b}, reasons


def resolve_answer(view, units, answer_unit_id, answer_text, evidence_unit_ids):
    lookup = {u["unit_id"]: u for u in units}
    if answer_unit_id not in lookup:
        return None, ["INVALID_ANSWER_UNIT_ID"]
    if answer_unit_id not in evidence_unit_ids:
        return None, ["ANSWER_UNIT_OUTSIDE_EVIDENCE"]
    unit = lookup[answer_unit_id]
    if not answer_text or not answer_text.strip():
        return None, ["EMPTY_ANSWER"]
    offsets = []
    search_from = 0
    while True:
        match = unit["presentation_text"].find(answer_text, search_from)
        if match < 0: break
        offsets.append(match)
        search_from = match + 1
    if not offsets:
        return None, ["ANSWER_NOT_EXACT_IN_PRESENTATION"]
    if len(offsets) > 1:
        return None, ["AMBIGUOUS_ANSWER_OCCURRENCE"]
    p_start = unit["presentation_start"] + offsets[0]
    p_end = p_start + len(answer_text)
    try:
        a, b = view.map_presentation_span_to_authoritative(p_start, p_end)
    except ValueError:
        return None, ["ANSWER_MAPPING_FAILED"]
    return {"generated_answer_text": answer_text,
            "answer_presentation_start": p_start, "answer_presentation_end": p_end,
            "answer_authoritative_start": a, "answer_authoritative_end": b,
            "answer_authoritative_text": view.authoritative_text[a:b],
            "absolute_answer_start": view.authoritative_source_start + a,
            "absolute_answer_end": view.authoritative_source_start + b}, []
