"""Proposition-first, fail-closed domain QA controls for the isolated pilot.

Automatic checks are deliberately narrower than human source review. A model's
claim of entailment never overrides a failed structural check.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
import hashlib
import re
from typing import Protocol

from rag_domain_common import normalized_query

STATES = {"GENERATED", "GROUNDING_FAILED", "SEMANTIC_FAILED", "AUTO_CHECKED",
          "AUTO_VALIDATED", "REVIEWED", "REJECTED", "EDITED"}
TYPES = {"PERSON", "PERSON_GROUP", "LOCATION", "TIME", "EVENT", "CAUSE", "MANNER",
         "RELATION", "PHRASE", "OTHER"}
SLOTS = {"subject", "object", "location", "time", "cause", "manner", "relation"}
RELATIONS = {"ENTITY_ACTION", "ENTITY_RELATION", "EVENT", "LOCATION", "TEMPORAL",
             "CAUSE_EFFECT", "MOTIVATION", "STATE_CHANGE", "ATTRIBUTE",
             "QUOTE_OR_STATEMENT", "SEQUENCE"}
UNRESOLVED = re.compile(r"\b(?:the man|the woman|the narrator|the speaker|the person|"
                        r"the news|this|that|here|there|he|she|they|it|his|her|their)\b", re.I)
META = re.compile(r"\b(?:this passage|the passage|the text|the title|the chapter|"
                  r"what word appears|who is mentioned|what is being discussed)\b", re.I)
CAUSAL = re.compile(r"\b(?:because|since|as a result|therefore|due to|for fear that|"
                    r"so that|in order to|reason|purpose was|wanted to|hoped to|feared that)\b", re.I)
TIME = re.compile(r"\b(?:\d{4}|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|"
                  r"January|February|March|April|May|June|July|August|September|October|"
                  r"November|December|yesterday|tomorrow|next day|previous day|morning|"
                  r"afternoon|evening|night|week|month|year|hour|before .+|after .+)\b", re.I)
LOCATION = re.compile(r"\b(?:in|at|to|from|near|through|inside|outside|beside)\s+"
                      r"(?:the\s+)?[A-Za-z][\w'-]*(?:\s+[A-Za-z][\w'-]*){0,4}", re.I)
WH_TYPES = {"who": {"PERSON", "PERSON_GROUP"}, "where": {"LOCATION"},
            "when": {"TIME"}, "why": {"CAUSE"}, "how": {"MANNER", "EVENT", "PHRASE"}}
CATEGORY_RELATIONS = {
    "FACTUAL_DIRECT": {"ENTITY_ACTION", "EVENT", "ATTRIBUTE", "STATE_CHANGE"},
    "ENTITY_RELATION": {"ENTITY_RELATION"}, "EVENT": {"EVENT", "ENTITY_ACTION", "STATE_CHANGE"},
    "MOTIVATION": {"MOTIVATION"}, "CAUSAL": {"CAUSE_EFFECT"},
    "LOCATION": {"LOCATION"}, "TEMPORAL": {"TEMPORAL"},
    "SEMANTIC_PARAPHRASE": {"ENTITY_ACTION", "EVENT", "STATE_CHANGE", "ATTRIBUTE"},
    "QUOTE_OR_PHRASE": {"QUOTE_OR_STATEMENT"}}
QUESTION_MIN_WORDS = 7


def classify_passage_v2(row):
    """Triage source chunks; quoted dialogue is allowed when names resolve it."""
    text = row["text"].strip()
    lower = text.casefold()
    if "\ufffd" in text or sum(x.isalpha() for x in text) < .55 * max(1, len(text)):
        return "MALFORMED"
    if row["token_count"] < 70 or len(text) < 280:
        return "TOO_SHORT"
    if re.search(r"\b(?:copyright|all rights reserved|publisher|publishing house)\b", lower):
        return "COPYRIGHT_OR_PUBLISHER"
    if re.search(r"\b(?:project gutenberg|license agreement|transcriber's note)\b", lower):
        return "BOILERPLATE"
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    if lower.startswith("contents") or ("contents" in lower[:100] and len(lines) >= 5):
        return "TABLE_OF_CONTENTS"
    if re.fullmatch(r"(?:chapter|part|book)\s+[^.!?]{0,100}", text, re.I):
        return "HEADER_ONLY"
    if len(lines) >= 7 and sum(len(x) < 50 for x in lines) >= .7 * len(lines):
        return "INDEX_LIKE"
    named = [x for x in re.findall(r"\b[A-Z][a-z]{2,}\b", text)
             if x not in {"The", "And", "But", "For", "Then", "When", "What", "This", "That"}]
    if text[0] in {'"', '“', "'"} and not named:
        return "DIALOGUE_WITH_UNCLEAR_REFERENTS"
    if len(named) < 2 or len(re.findall(r"[.!?]", text)) < 2:
        return "AMBIGUOUS_CONTEXT"
    if len(text.split()) < 65:
        return "WEAK_CONTEXT"
    return "GOOD_FOR_QA"


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def equal(a, b):
    return clean(a).casefold().strip(" .,!?:;'\"()") == clean(b).casefold().strip(" .,!?:;'\"()")


def _contains(haystack, needle):
    return clean(needle).casefold() in clean(haystack).casefold()


def answer_quality(answer, answer_type):
    a = clean(answer)
    failures = []
    if not a or not re.search(r"[A-Za-z0-9]", a) or a.count("(") != a.count(")") or a.count('"') % 2:
        failures.append("TRUNCATED_ANSWER")
    if a.endswith(("(", ")", ",", ";", ":", "-")) or a.casefold() in {
        "before", "after", "will", "information", "something", "someone", "the", "a", "an", "it"}:
        failures.append("ANSWER_TOO_VAGUE")
    if re.search(r"\b(?:will|would|could|should|shall|might|must|was|were|had|has|is|are|"
                 r"to|of|for|and|but)\s*$", a, re.I):
        failures.append("TRUNCATED_ANSWER")
    if len(a.split()) > 22:
        failures.append("ANSWER_TOO_LONG")
    if answer_type == "TIME" and (not TIME.search(a) or a.casefold() in {"before", "after"}):
        failures.append("ANSWER_TYPE_MISMATCH")
    if answer_type == "LOCATION" and not (LOCATION.search(a) or re.fullmatch(r"[A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,3}", a)):
        failures.append("ANSWER_TYPE_MISMATCH")
    if answer_type in {"PERSON", "PERSON_GROUP"} and not re.fullmatch(
            r"(?:Mr\.?|Mrs\.?|Miss|Dr\.?|Lord|Lady|[A-Z][\w'-]+)"
            r"(?:\s+(?:[A-Z][\w'-]+|of|the)){0,5}", a):
        failures.append("ANSWER_TYPE_MISMATCH")
    if answer_type == "CAUSE" and len(a.split()) < 3:
        failures.append("ANSWER_TYPE_MISMATCH")
    if answer_type in {"EVENT", "CAUSE", "RELATION", "PHRASE", "MANNER"} and len(a.split()) == 1:
        if not (answer_type in {"EVENT", "MANNER"} and re.search(r"(?:ed|ing|s)$", a, re.I)):
            failures.append("ANSWER_TOO_VAGUE")
    return sorted(set(failures))


def near_duplicate(question, other):
    a, b = normalized_query(question), normalized_query(other)
    if not a or not b:
        return False
    if a == b:
        return True
    ta, tb = set(a.split()), set(b.split())
    if len(ta | tb) < 5:
        return False
    jaccard = len(ta & tb) / len(ta | tb)
    return jaccard >= .78 and SequenceMatcher(None, a, b).ratio() >= .85


def generic_legacy_checks(record):
    """Audit old question-first records without inferring an absent proposition."""
    q = clean(record.get("query") or record.get("question"))
    a = clean(record.get("short_answer"))
    e = clean(record.get("evidence_text") or record.get("evidence_quote"))
    reasons = []
    wh = q.split(" ", 1)[0].casefold() if q else ""
    typ = {"who": "PERSON", "where": "LOCATION", "when": "TIME", "why": "CAUSE"}.get(wh, "OTHER")
    reasons.extend(answer_quality(a, typ))
    if UNRESOLVED.search(q): reasons.append("UNRESOLVED_REFERENT")
    if META.search(q): reasons.append("TRIVIAL_METADATA")
    if len(q.split()) < QUESTION_MIN_WORDS or re.match(r"^(?:What happened|What was said|Who was there)\?", q, re.I):
        reasons.append("QUESTION_TOO_GENERIC")
    if a and _contains(q, a): reasons.append("QUESTION_CONTAINS_ANSWER")
    if a and e and not _contains(e, a): reasons.append("ANSWER_NOT_IN_EVIDENCE")
    if wh == "why" and not CAUSAL.search(e): reasons.append("UNSUPPORTED_CAUSAL")
    if wh == "when" and not TIME.search(a): reasons.append("UNSUPPORTED_TEMPORAL")
    if wh == "who" and re.search(r"\bselected\s+by\b", e, re.I) and re.search(
            r"\b(?:son|daughter|brother|sister|wife|husband|friend)(?:[- ]in[- ]law)?\b"
            r"[\s,]+" + re.escape(a) + r"\b", e, re.I):
        reasons.append("WRONG_PROPOSITION_SLOT")
    if wh == "where" and re.search(r"\b(?:travel|traveled|went|came)\s+(?:from|to)\b", q, re.I):
        direction = re.search(r"\b(from|to)\b", q, re.I)
        if direction and not re.search(r"\b" + direction.group(1) + r"\s+" + re.escape(a), e, re.I):
            reasons.append("LOCATION_DIRECTION_ERROR")
    if q and e and re.search(r"\b(?:news|reason|purpose)\b", q, re.I) and not re.search(
            r"\b(?:news|reason|purpose)\b", e, re.I):
        reasons.append("UNSUPPORTED_PREMISE")
    reasons.append("MISSING_PROPOSITION")
    return sorted(set(reasons))


@dataclass(frozen=True)
class EntailmentResult:
    label: str
    reason: str
    supporting_text: str


class SemanticEntailmentJudge(Protocol):
    def judge(self, candidate: dict) -> EntailmentResult: ...


class RuleEntailmentJudge:
    """Entails only questions assembled from a verified exact relation template."""
    def judge(self, candidate):
        p = candidate.get("proposition") or {}
        if p.get("proof_kind") != "EXACT_RULE" or not p.get("rule_id"):
            return EntailmentResult("UNCERTAIN", "No deterministic proposition proof", "")
        if not candidate.get("question_from_template"):
            return EntailmentResult("UNCERTAIN", "Question was not derived from the verified template", "")
        return EntailmentResult("ENTAILED", "Exact relation pattern and fixed question template", p.get("evidence_quote", ""))


def validate(record, source, *, eval_queries=(), seen_queries=(), test_works=(), judge=None):
    """Return a new record with explicit state, checks and rejection codes."""
    c = dict(record)
    p = dict(c.get("proposition") or {})
    reasons = []
    checks = {}
    def fail(code, condition):
        checks[code] = not condition
        if condition: reasons.append(code)
    work = c.get("work_id")
    fail("TEST_LEAKAGE", work in set(test_works) or c.get("split") == "TEST")
    passage = c.get("positive_passage", "")
    start, end = c.get("source_start"), c.get("source_end")
    fail("SOURCE_MAPPING_FAILED", not isinstance(start, int) or not isinstance(end, int) or
         start < 0 or end > len(source) or source[start:end] != passage)
    fail("SOURCE_HASH_INTEGRITY", hashlib.sha256(source.encode("utf-8")).hexdigest() != c.get("source_hash"))
    evidence = p.get("evidence_quote", "")
    ev_start, ev_end = p.get("evidence_start"), p.get("evidence_end")
    fail("EVIDENCE_NOT_EXACT", not evidence or passage.count(evidence) != 1 or
         not isinstance(ev_start, int) or not isinstance(ev_end, int) or
         source[ev_start:ev_end] != evidence or not (start <= ev_start < ev_end <= end))
    fail("MISSING_PROPOSITION", not p or p.get("relation_type") not in RELATIONS or
         c.get("asked_slot") not in SLOTS)
    category = c.get("category") or c.get("validated_category")
    category_matches = category in CATEGORY_RELATIONS and p.get("relation_type") in CATEGORY_RELATIONS[category]
    c["validated_category"] = category if category_matches else None
    if not category_matches:
        reasons.append("CATEGORY_RELATION_MISMATCH")
    for field in ("subject", "predicate", "object"):
        if p.get(field) and not _contains(evidence, p[field]): reasons.append("PROPOSITION_SLOT_NOT_IN_EVIDENCE")
    if p.get("source_sentence") and not _contains(evidence, p["source_sentence"]):
        reasons.append("PROPOSITION_SOURCE_MISMATCH")
    slot = c.get("asked_slot", "")
    answer = c.get("short_answer", "")
    slot_value = p.get(slot)
    fail("WRONG_PROPOSITION_SLOT", not slot_value or not equal(answer, slot_value))
    fail("ANSWER_NOT_IN_EVIDENCE", bool(answer) and not _contains(evidence, answer))
    typ = c.get("answer_type", "OTHER")
    fail("ANSWER_TYPE_MISMATCH", typ not in TYPES)
    reasons.extend(answer_quality(answer, typ))
    q = clean(c.get("question") or c.get("query"))
    fail("QUESTION_TOO_GENERIC", not q.endswith("?") or len(q.split()) < QUESTION_MIN_WORDS or
         re.match(r"^(?:What happened|What was said|Who was there|What did he do)\?", q, re.I) is not None)
    fail("TRIVIAL_METADATA", META.search(q) is not None)
    fail("UNRESOLVED_REFERENT", UNRESOLVED.search(q) is not None)
    fail("QUESTION_CONTAINS_ANSWER", bool(answer) and _contains(q, answer))
    wh = q.split(" ", 1)[0].casefold() if q else ""
    if wh in WH_TYPES:
        fail("ANSWER_TYPE_MISMATCH", typ not in WH_TYPES[wh])
    if wh == "why" or p.get("relation_type") in {"CAUSE_EFFECT", "MOTIVATION"}:
        fail("UNSUPPORTED_CAUSAL", not CAUSAL.search(evidence) or not p.get("cause") or not p.get("effect") or
             not _contains(evidence, p.get("cause")) or not _contains(evidence, p.get("effect")))
    if wh == "when" or p.get("relation_type") == "TEMPORAL":
        fail("UNSUPPORTED_TEMPORAL", not p.get("time") or not TIME.search(p.get("time", "")) or
             p.get("temporal_relation") not in {"BEFORE", "AFTER", "DURING", "AT_TIME", "NEXT_DAY", "PREVIOUSLY"})
        if p.get("temporal_relation") == "BEFORE" and re.search(r"\bafter\b", q, re.I): reasons.append("RELATION_DIRECTION_ERROR")
        if p.get("temporal_relation") == "AFTER" and re.search(r"\bbefore\b", q, re.I): reasons.append("RELATION_DIRECTION_ERROR")
    if wh == "where" or p.get("relation_type") == "LOCATION":
        fail("ANSWER_TYPE_MISMATCH", typ != "LOCATION" or not p.get("location"))
        direction = p.get("location_direction")
        if direction not in {"AT", "IN", "FROM", "TO", "NEAR", "THROUGH"}: reasons.append("LOCATION_DIRECTION_ERROR")
        motion = r"\b(?:travel|traveled|go|went|come|came|move|moved|return|returned)\s+"
        if direction == "FROM" and re.search(motion + r"to\b", q, re.I): reasons.append("LOCATION_DIRECTION_ERROR")
        if direction == "TO" and re.search(motion + r"from\b", q, re.I): reasons.append("LOCATION_DIRECTION_ERROR")
    if p.get("relation_type") == "ENTITY_RELATION":
        if not p.get("entity_a") or not p.get("entity_b") or not p.get("relation_direction"):
            reasons.append("RELATION_DIRECTION_ERROR")
        elif slot == "subject" and not equal(answer, p.get("entity_a")):
            reasons.append("RELATION_DIRECTION_ERROR")
        elif slot == "object" and not equal(answer, p.get("entity_b")):
            reasons.append("RELATION_DIRECTION_ERROR")
    if p.get("relation_type") in {"ENTITY_ACTION", "EVENT"} and p.get("subject") and p.get("object"):
        positions = [clean(evidence).casefold().find(clean(p[k]).casefold()) for k in ("subject", "predicate", "object")]
        if -1 in positions or positions != sorted(positions): reasons.append("RELATION_DIRECTION_ERROR")
    if any(near_duplicate(q, other) for other in seen_queries): reasons.append("NEAR_DUPLICATE")
    if any(near_duplicate(q, other) for other in eval_queries): reasons.append("EVAL_QUERY_SIMILARITY")
    judgment = (EntailmentResult("UNCERTAIN", "Deterministic validation failed", "") if reasons
                else (judge or RuleEntailmentJudge()).judge(c))
    if judgment.label == "NOT_ENTAILED": reasons.append("SEMANTIC_NOT_ENTAILED")
    if judgment.label not in {"ENTAILED", "NOT_ENTAILED", "UNCERTAIN"}: reasons.append("SEMANTIC_JUDGE_INVALID")
    if judgment.label == "ENTAILED" and not _contains(evidence, judgment.supporting_text):
        reasons.append("SEMANTIC_JUDGE_INVALID")
    reasons = sorted(set(reasons))
    grounding = {"TEST_LEAKAGE", "SOURCE_MAPPING_FAILED", "SOURCE_HASH_INTEGRITY", "EVIDENCE_NOT_EXACT",
                 "MISSING_PROPOSITION", "PROPOSITION_SLOT_NOT_IN_EVIDENCE", "PROPOSITION_SOURCE_MISMATCH"}
    state = "GROUNDING_FAILED" if grounding & set(reasons) else "SEMANTIC_FAILED" if reasons else (
        "AUTO_VALIDATED" if judgment.label == "ENTAILED" else "AUTO_CHECKED")
    c["review_status"] = state
    c["auto_validation"] = {"passed": state == "AUTO_VALIDATED", "checks": checks,
                            "rejection_reasons": reasons, "entailment": judgment.__dict__}
    return c
