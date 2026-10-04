"""Strict two-stage V7R3 contracts and deterministic QA validation."""
from __future__ import annotations

import json
import re

from rag_domain_common import CATEGORIES
from rag_domain_qa_assisted_v7 import BAD_ANSWER, BAD_QUESTION, GENERIC
from rag_domain_qa_v2 import CAUSAL, META, answer_quality
from rag_domain_qa_word_units_v7r3 import resolve_word_span

FACT_TYPES = set(CATEGORIES)
ANSWER_TYPES = {"PERSON", "PERSON_GROUP", "LOCATION", "TIME", "CAUSE", "EVENT", "ACTION",
                "RELATION", "STATE", "OBJECT", "PHRASE", "QUOTE", "OTHER_EXPLICIT"}
STAGE_A_KEYS = {"evidence_unit_ids", "answer_unit_id", "answer_start_word_id",
                "answer_end_word_id", "fact_type", "fact_description", "answer_type"}
DIFFICULTIES = {"EASY", "MEDIUM", "HARD"}


def parse_stage_a(raw):
    try: obj = json.loads(raw)
    except (TypeError, json.JSONDecodeError): return None
    if not isinstance(obj, dict) or set(obj) != {"candidates"} or not isinstance(obj["candidates"], list) or len(obj["candidates"]) > 2:
        return None
    for c in obj["candidates"]:
        if not isinstance(c, dict) or set(c) != STAGE_A_KEYS:
            return None
        if any(not isinstance(c[k], str) for k in STAGE_A_KEYS - {"evidence_unit_ids"}):
            return None
        if not isinstance(c["evidence_unit_ids"], list) or any(not isinstance(x, str) for x in c["evidence_unit_ids"]):
            return None
    return obj


def parse_stage_b(raw):
    try: obj = json.loads(raw)
    except (TypeError, json.JSONDecodeError): return None
    if not isinstance(obj, dict): return None
    if obj.get("question") is None:
        if set(obj) != {"question", "difficulty", "reason"} or obj["difficulty"] is not None or not isinstance(obj["reason"], str):
            return None
    elif set(obj) != {"question", "difficulty"} or not isinstance(obj["question"], str) or not isinstance(obj["difficulty"], str):
        return None
    return obj


def parse_judge(raw, selected_ids):
    try: obj = json.loads(raw)
    except (TypeError, json.JSONDecodeError): obj = None
    keys = {"label", "outside_context", "wrong_role", "supporting_unit_ids"}
    if not isinstance(obj, dict) or not keys <= set(obj) or set(obj) - keys - {"reason"}:
        return {"label": "UNCERTAIN", "failure_code": "JUDGE_INVALID_JSON", "supporting_unit_ids": []}
    if (not isinstance(obj["label"], str) or obj["label"] not in {"SUPPORTED", "UNSUPPORTED", "UNCERTAIN"} or
        type(obj["outside_context"]) is not bool or type(obj["wrong_role"]) is not bool or
        not isinstance(obj["supporting_unit_ids"], list) or
        any(not isinstance(x, str) for x in obj["supporting_unit_ids"]) or
        ("reason" in obj and not isinstance(obj["reason"], str))):
        return {"label": "UNCERTAIN", "failure_code": "JUDGE_INVALID_JSON", "supporting_unit_ids": []}
    ids = obj["supporting_unit_ids"]
    if len(ids) != len(set(ids)) or any(x not in selected_ids for x in ids):
        return {"label": "UNCERTAIN", "failure_code": "JUDGE_SUPPORT_UNIT_OUTSIDE_EVIDENCE", "supporting_unit_ids": []}
    if obj["label"] == "SUPPORTED" and (not ids or obj["outside_context"] or obj["wrong_role"]):
        return {"label": "UNCERTAIN", "failure_code": "JUDGE_SUPPORT_CONTRACT_FAILED", "supporting_unit_ids": []}
    if obj["label"] == "UNCERTAIN": obj["failure_code"] = "JUDGE_SEMANTIC_UNCERTAIN"
    return obj


def validate_stage_a(candidate, view, units, word_units):
    reasons = []
    if candidate["fact_type"] not in FACT_TYPES: reasons.append("INVALID_CATEGORY")
    if candidate["answer_type"] not in ANSWER_TYPES: reasons.append("INVALID_ANSWER_TYPE")
    if reasons: return None, None, reasons
    answer, evidence, reasons = resolve_word_span(view, units, word_units, candidate)
    if reasons: return None, None, reasons
    surface = answer["answer_presentation_text"].strip()
    if re.fullmatch(r"(?i:it|that|this|he|she|they|was|were|is|are|to|of|and|or|because)", surface):
        return None, None, ["ANSWER_SPAN_INCOMPLETE"]
    if surface.lower().endswith((" of", " to", " for", " by", " and", " or", " the", " a")):
        return None, None, ["ANSWER_SPAN_INCOMPLETE"]
    if candidate["answer_type"] in {"PERSON", "PERSON_GROUP"} and surface.lower() in {"him", "her", "them", "me", "us"}:
        return None, None, ["ANSWER_SPAN_INCOMPLETE"]
    quality = answer_quality(surface, candidate["answer_type"])
    if candidate["fact_type"] in {"CAUSAL", "MOTIVATION", "QUOTE_OR_PHRASE"}:
        quality = [q for q in quality if q != "ANSWER_TOO_LONG"]
    if quality:
        return None, None, ["ANSWER_SPAN_INCOMPLETE"]
    return answer, evidence, []


def question_reasons(question, answer, answer_type, fact_type, evidence, target):
    reasons = []
    if not question.endswith("?") or not 6 <= len(question.split()) <= 35:
        reasons.append("QUESTION_LENGTH_OR_FORMAT")
    if META.search(question): reasons.append("TRIVIAL_METADATA")
    if BAD_QUESTION.search(question): reasons.append("QUESTION_UNRESOLVED_REFERENT")
    if GENERIC.fullmatch(question): reasons.append("QUESTION_TOO_GENERIC")
    if BAD_ANSWER.fullmatch(answer): reasons.append("ANSWER_UNRESOLVED_REFERENT")
    if answer.casefold() in question.casefold(): reasons.append("QUESTION_CONTAINS_ANSWER")
    reasons.extend(answer_quality(answer, answer_type))
    q = question.casefold().strip()
    starts = {
        "PERSON": ("who ", "whom ", "which person ", "what person "),
        "PERSON_GROUP": ("who ", "whom ", "which people ", "what group "),
        "LOCATION": ("where ", "which place ", "what place ", "in what ", "at what "),
        "TIME": ("when ", "what time ", "which day ", "what year ", "how long "),
        "CAUSE": ("why ", "for what reason ", "what caused ", "what led "),
        "RELATION": ("how ", "what relationship ", "who ", "what relation "),
    }
    if answer_type in starts and not q.startswith(starts[answer_type]):
        reasons.append("QUESTION_ANSWER_TYPE_MISMATCH")
    if fact_type == "ENTITY_RELATION" and not re.search(r"\b(?:relationship|related|father|mother|sister|brother|daughter|son|wife|husband|married|family|parent|child|relative)\b", q):
        reasons.append("CATEGORY_QUESTION_MISMATCH")
    if fact_type == "TEMPORAL" and not q.startswith(starts["TIME"]):
        reasons.append("CATEGORY_QUESTION_MISMATCH")
    if fact_type == "LOCATION" and not q.startswith(starts["LOCATION"]):
        reasons.append("CATEGORY_QUESTION_MISMATCH")
    if fact_type in {"CAUSAL", "MOTIVATION"} and not CAUSAL.search(evidence):
        reasons.append("UNSUPPORTED_CAUSAL_OR_MOTIVATION")
    skip = {"Who", "Whom", "What", "Why", "When", "Where", "How", "Which", "Did", "Does",
            "Was", "Were", "The", "A", "An", "Mr", "Mrs", "Miss", "Dr", "Lord", "Lady"}
    for name in re.findall(r"\b[A-Z][a-z]{2,}\b", question):
        if name not in skip and not re.search(r"\b" + re.escape(name) + r"\b", target, re.I):
            reasons.append("CONTEXT_ONLY_NAMED_REFERENCE")
            break
    return sorted(set(reasons))
