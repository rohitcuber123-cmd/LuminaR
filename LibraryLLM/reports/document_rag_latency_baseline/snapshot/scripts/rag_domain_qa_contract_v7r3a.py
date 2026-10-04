"""Read-only contract replay for saved V7R3 deterministic QA passes."""
from __future__ import annotations

import re

from rag_domain_qa_v2 import answer_quality

INTENTS = {"WHO", "WHOM", "WHERE", "WHEN", "WHY", "HOW", "WHAT_ACTION", "WHAT_OBJECT",
           "WHAT_STATE", "WHAT_RELATION", "WHAT_QUOTE", "OTHER"}
CONCRETE_TYPES = {"PERSON", "PERSON_GROUP", "LOCATION", "TIME", "CAUSE", "MOTIVATION", "ACTION",
                  "EVENT", "OBJECT", "STATE", "RELATION", "QUOTE", "PHRASE"}
TEMPORAL_LEAD = re.compile(r"^(?:ago|before|after|yesterday|today|tomorrow|earlier|later)\b", re.I)
LOCATION_FRAGMENT = re.compile(r"\b(?:in|at|near|from|to)\s+[A-Z][A-Za-z'’\-]+\b")
BARE_FUNCTION = {"with", "your", "not", "was not", "look as", "forward", "ma"}


def question_intent(question):
    q = re.sub(r"\s+", " ", question.strip()).casefold()
    if re.match(r"^(?:what relationship|what relation|how (?:is|was|are|were|did).+related)", q):
        return "WHAT_RELATION"
    if q.startswith("whom "): return "WHOM"
    if q.startswith("who did ") or q.startswith("who does "): return "WHOM"
    if q.startswith("who ") or q.startswith("which person "): return "WHO"
    if q.startswith("where ") or q.startswith(("which place ", "what place ", "which boarding house ")):
        return "WHERE"
    if q.startswith("when ") or q.startswith(("what time ", "which day ", "what year ", "how long ")):
        return "WHEN"
    if q.startswith("why ") or q.startswith("for what reason "): return "WHY"
    if q.startswith("how "): return "HOW"
    if re.match(r"^what did .+ (?:say|quote|call)\b", q) or re.match(r"^what (?:words|phrase|quote)\b", q):
        return "WHAT_QUOTE"
    if re.match(r"^what (?:did|does) .+ (?:do|prefer to do)\b", q):
        return "WHAT_ACTION"
    if re.match(r"^what (?:state|condition|feeling)\b", q): return "WHAT_STATE"
    if q.startswith(("what ", "which ")): return "WHAT_OBJECT"
    return "OTHER"


def mixed_semantic_span(answer, intent):
    a = answer.strip()
    if intent == "WHERE" and TEMPORAL_LEAD.search(a): return True
    if intent == "WHEN" and LOCATION_FRAGMENT.search(a): return True
    return False


def reclassify_other(answer, evidence, question, intent):
    """Conservative surface-backed reclassification; never edits the answer."""
    a = re.sub(r"\s+", " ", answer.strip())
    e = re.sub(r"\s+", " ", evidence)
    q = question.casefold()
    if intent in {"WHO", "WHOM"}:
        if (re.fullmatch(r"(?:Mr\.?|Mrs\.?|Miss|Dr\.?)?\s*[A-Z][A-Za-z'’\-]*(?:\s+[A-Z][A-Za-z'’\-]*){0,3}", a)
                and re.search(r"\b" + re.escape(a) + r"\b", e, re.I)):
            return "PERSON"
    if intent == "WHAT_OBJECT":
        if "what group" in q and re.search(r"\b(?:a|the)\s+" + re.escape(a) + r"\s+of\b", e, re.I):
            return "PERSON_GROUP"
        if re.fullmatch(r"[A-Za-z][A-Za-z'’\-]{2,}", a) and a.casefold() not in BARE_FUNCTION and re.search(
                r"\b(?:a|an|the|these|those)\s+" + re.escape(a) + r"\b", e, re.I):
            return "OBJECT"
    if intent == "WHERE" and re.fullmatch(r"(?:in|at|near|from|to)\s+[A-Z][A-Za-z'’\-]+", a):
        return "LOCATION"
    if intent == "WHAT_ACTION" and re.fullmatch(r"[A-Za-z]+(?:ed|ing|ish)", a, re.I):
        return "ACTION"
    return None


def final_category(question, intent, answer_type, proposed):
    q = question.casefold()
    if intent in {"WHO", "WHOM"}:
        if re.search(r"\b(?:related to|relationship between|relationship to)\b", q) or re.match(
                r"who (?:was|is) .+ (?:father|mother|sister|brother|wife|husband|parent|child)\b", q):
            return "ENTITY_RELATION"
        return "FACTUAL_DIRECT"
    if intent == "WHERE": return "LOCATION"
    if intent == "WHEN": return "TEMPORAL"
    if intent == "WHY": return "MOTIVATION" if "motivat" in q else "CAUSAL"
    if intent == "WHAT_ACTION": return "EVENT"
    if intent == "WHAT_QUOTE": return "QUOTE_OR_PHRASE"
    if intent == "WHAT_OBJECT": return "FACTUAL_DIRECT"
    if intent == "WHAT_RELATION": return "ENTITY_RELATION"
    return proposed


def contract_replay(record):
    """Return metadata and fail-closed compatibility without changing source or QA."""
    question, answer, evidence = record["question"], record["short_answer"], record["evidence_quote"]
    intent = question_intent(question)
    proposed_type = record["answer_type"]
    proposed_category = record["category_proposed"]
    category = final_category(question, intent, proposed_type, proposed_category)
    answer_type = proposed_type
    reasons = []
    if mixed_semantic_span(answer, intent): reasons.append("MIXED_SEMANTIC_ANSWER_SPAN")
    if proposed_type == "OTHER_EXPLICIT":
        answer_type = reclassify_other(answer, evidence, question, intent)
        if answer_type is None: reasons.append("OTHER_EXPLICIT_NEEDS_REVIEW")
    if answer_type and answer_type in CONCRETE_TYPES:
        type_failures = answer_quality(answer, "PHRASE" if answer_type == "QUOTE" else answer_type)
        if type_failures: reasons.append("ANSWER_TYPE_COMPATIBILITY_FAILED")
    allowed = {
        "WHO": {"PERSON", "PERSON_GROUP"}, "WHOM": {"PERSON", "PERSON_GROUP"},
        "WHERE": {"LOCATION"}, "WHEN": {"TIME"}, "WHY": {"CAUSE", "MOTIVATION"},
        "WHAT_RELATION": {"RELATION"}, "WHAT_ACTION": {"ACTION", "EVENT"},
        "WHAT_OBJECT": {"OBJECT", "PERSON_GROUP"}, "WHAT_STATE": {"STATE"},
        "WHAT_QUOTE": {"QUOTE", "PHRASE"},
    }
    if intent == "OTHER": reasons.append("QUESTION_INTENT_OTHER")
    elif intent == "HOW": reasons.append("QUESTION_INTENT_NEEDS_REVIEW")
    elif answer_type not in allowed[intent]: reasons.append("QUESTION_ANSWER_TYPE_MISMATCH")
    if answer.casefold() in {"with", "your", "not", "look as", "was not"}:
        reasons.append("ANSWER_SPAN_INCOMPLETE")
    if answer_type == "OBJECT" and re.fullmatch(r"[A-Za-z]+ing", answer.strip()) and re.search(
            r"\b(?:was|were|is|are)\s+" + re.escape(answer.strip()) + r"\b", evidence, re.I):
        reasons.append("ANSWER_TYPE_COMPATIBILITY_FAILED")
    return {"question_intent": intent, "answer_type_proposed": proposed_type,
            "answer_type_final": answer_type, "category_proposed": proposed_category,
            "category_final": category, "category_changed": category != proposed_category,
            "question_unchanged": question == record["question"],
            "answer_unchanged": answer == record["short_answer"],
            "evidence_unchanged": evidence == record["evidence_quote"],
            "contract_reasons": sorted(set(reasons)), "contract_pass": not reasons}


def readiness(contract, engineering_label, *, source_valid, leakage_free):
    ready = (source_valid and leakage_free and contract["contract_pass"] and
             engineering_label == "PLAUSIBLE_FOR_HUMAN_REVIEW")
    engineering_status = {"PLAUSIBLE_FOR_HUMAN_REVIEW": "ENGINEERING_PLAUSIBLE",
                          "OBVIOUS_SEMANTIC_ERROR": "ENGINEERING_REJECTED",
                          "AMBIGUOUS": "ENGINEERING_AMBIGUOUS"}[engineering_label]
    return {"deterministic_pass": True,
            "engineering_status": engineering_status,
            "ready_for_human_review": ready,
            "status": "READY_FOR_HUMAN_REVIEW" if ready else "DETERMINISTIC_PASS",
            "reviewed": False}


def judge_bucket(judgment):
    failure = judgment.get("failure_code")
    if failure == "JUDGE_INVALID_JSON": return "INVALID_JSON"
    if failure == "JUDGE_SUPPORT_UNIT_OUTSIDE_EVIDENCE": return "INVALID_SUPPORT_REFERENCE"
    if judgment["label"] == "UNCERTAIN": return "SEMANTIC_UNCERTAIN"
    return judgment["label"]
