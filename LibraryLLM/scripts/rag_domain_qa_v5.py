"""V5 precision calibration over frozen V3/V4 rules; no free-form fact generation."""
from __future__ import annotations

from collections import Counter
import re

from rag_domain_qa_v2 import answer_quality
from rag_domain_qa_v3 import NAME, Relation, Span, _make, is_name, proposition_fingerprint, qa_fingerprint, validate_v3
from rag_domain_qa_v4 import extract_chunk_v4, training_value_of

SPEECH = "said|says|replied|answered|asked|declared|remarked|explained|cried|whispered|shouted|exclaimed|observed|responded"
FALSE_ENTITY = {"Well", "Oh", "Yes", "No", "Indeed", "Perhaps", "But", "And", "Then", "Now",
                "Why", "Come", "Look", "Sir", "Madam", "Dear", "Good", "Have", "Where", "Much",
                "Really", "Amen", "Nothing", "Not", "Your"}
DISCOURSE = re.compile(r"\b(?:this|that|it|he|she|they|there|then|such|the same|the promise|"
                       r"the pledge|the matter|the news|the plan|the purpose)\b", re.I)
DANGLING = re.compile(r"\b(?:will|would|could|should|had|has|have|was|were|is|are|to|of|for|"
                      r"and|but|because|if|before|after)\s*$", re.I)
PREDICATE = re.compile(r"\b(?:is|are|was|were|has|have|had|will|shall|must|should|could|"
                       r"went|go|gone|left|leave|return|come|came|wait|stay|keep|bring|brought|"
                       r"tell|told|say|said|know|care|feel|found|find|opened|read|died|live|"
                       r"be|disturbed|arrived|met|taken|take|written|write|swear|swore)\b", re.I)
COORDINATED_ACTION = re.compile(r"\b(?:and|but|then|yet)\s+(?:[A-Za-z]+\s+){0,2}"
                                 r"(?:destroyed|opened|closed|found|read|sent|wrote|left|returned|"
                                 r"said|asked|told|gave|took|came|went|entered|departed)\b", re.I)


def statement_content_reason(content):
    value = content.strip()
    if not value or len(value.split()) < 3 or len(value.split()) > 20:
        return "STATEMENT_CONTENT_FRAGMENT"
    if value[0].islower() or value[-1] not in ".?!":
        return "STATEMENT_CONTENT_FRAGMENT"
    if re.match(r"^(?:because|although|unless|if|since|when|while)\b", value, re.I):
        return "STATEMENT_CONTENT_FRAGMENT"
    if value.count(".") + value.count("?") + value.count("!") != 1:
        return "STATEMENT_CONTENT_FRAGMENT"
    if DANGLING.search(value.rstrip(".?!")):
        return "STATEMENT_CONTENT_FRAGMENT"
    if DISCOURSE.search(value):
        return "STATEMENT_DISCOURSE_DEPENDENT"
    if re.search(r"\b(?:you|your|yours|him|her|them|his|hers)\b", value, re.I):
        return "STATEMENT_DISCOURSE_DEPENDENT"
    if not PREDICATE.search(value):
        return "STATEMENT_CONTENT_NO_PREDICATE"
    return None


def answer_slot_sufficient(candidate):
    relation = candidate["relation_type"]
    answer = candidate["short_answer"].strip()
    if answer_quality(answer, candidate["answer_type"]):
        return "ANSWER_SLOT_FRAGMENT"
    if relation == "STATEMENT":
        return statement_content_reason(answer)
    if relation == "ACTION":
        p = candidate["proposition"]
        if COORDINATED_ACTION.search(p.get("object", "")):
            return "ACTION_OBJECT_SWALLOWS_SECOND_PREDICATE"
        if COORDINATED_ACTION.search(p.get("context", "")):
            return "ACTION_COORDINATED_PREDICATE_DRIFT"
    return None


def _speaker_valid(value):
    return is_name(value) and value.split()[0] not in FALSE_ENTITY


def _statement_candidates(row):
    # A complete local utterance plus an explicit attribution; no inferred topic.
    quote = r'[“"](?P<object>[^”"\n]{12,145}[.?!])[”"]'
    before = re.compile(rf'{quote}\s*,?\s*(?P<predicate>{SPEECH})\s+(?P<subject>{NAME})\b')
    after = re.compile(rf'\b(?P<subject>{NAME})\s+(?P<predicate>{SPEECH})\s*,?\s*{quote}')
    out = []
    for pattern in (before, after):
        for global_match in pattern.finditer(row["text"]):
            clause = Span(global_match.group(), global_match.start(), global_match.end(),
                          global_match.start(), global_match.end())
            m = pattern.fullmatch(clause.text)
            if not m or not _speaker_valid(m["subject"]):
                continue
            reason = statement_content_reason(m["object"])
            if reason:
                continue
            q = f"What did {m['subject']} {('ask' if m['predicate']=='asked' else 'say')} in the quoted exchange?"
            base = row["source_start_char"] + clause.start
            c = _make(row, clause, Relation.STATEMENT, m, asked_slot="object", answer_type="PHRASE",
                      category="QUOTE_OR_PHRASE", v2_relation="QUOTE_OR_STATEMENT", question=q,
                      slot_group="object", extras={"speaker": m["subject"], "topic": None,
                      "speaker_span": [base + m.start("subject"), base + m.end("subject")],
                      "speech_verb_span": [base + m.start("predicate"), base + m.end("predicate")],
                      "statement_span": [base + m.start("object"), base + m.end("object")]})
            if c:
                c["extractor_version"] = "v5"
                c["confidence_reasons"] = []
                c["training_value"] = training_value_of(c)
                out.append(c)
    return out


def _status(candidate, reason=None):
    c = candidate.copy()
    c["extraction_confidence"] = "MEDIUM" if reason else c["extractor_confidence"]
    c["extractor_confidence"] = c["extraction_confidence"]
    c["validation_status"] = "NOT_RUN"
    c["source_audit_status"] = "NOT_AUDITED"
    if reason:
        c["confidence_reasons"] = list(dict.fromkeys(c.get("confidence_reasons", []) + [reason]))
    return c


def extract_chunk_v5(row):
    prior, stats = extract_chunk_v4(row)
    out, seen = [], set()
    counts = Counter(stats)
    for candidate in prior:
        reason = None
        if candidate["relation_type"] == "STATEMENT":
            reason = "STATEMENT_TOPIC_UNSUPPORTED" if candidate["proposition"].get("topic") else (
                statement_content_reason(candidate["short_answer"]) or "STATEMENT_SPEAKER_NOT_GROUNDED")
        else:
            reason = answer_slot_sufficient(candidate)
        c = _status(candidate, reason)
        if reason: counts["answer_sufficiency_rejects"] += 1
        fp = c["proposition_fingerprint"]
        if fp not in seen:
            seen.add(fp); out.append(c)
    for candidate in _statement_candidates(row):
        c = _status(candidate, answer_slot_sufficient(candidate))
        fp = proposition_fingerprint(c)
        if fp in seen:
            continue
        c["proposition_fingerprint"] = fp
        c["qa_fingerprint"] = qa_fingerprint(c)
        seen.add(fp); out.append(c)
        counts["matches"] += 1
        counts["cue_STATEMENT_V5"] += 1
    return out, dict(counts)


def validate_v5(candidate, source, *, eval_queries=(), test_works=(), seen_queries=()):
    if candidate["extraction_confidence"] != "HIGH":
        return {**candidate, "validation_status": "NOT_RUN", "review_status": "MEDIUM_LOW_DIAGNOSTIC",
                "auto_validation": {"passed": False, "rejection_reasons": candidate.get("confidence_reasons", [])}}
    if candidate["relation_type"] == "STATEMENT":
        p = candidate["proposition"]
        for slot in ("speaker_span", "speech_verb_span", "statement_span"):
            span = p.get(slot)
            if not span or source[span[0]:span[1]] != p[{"speaker_span":"speaker", "speech_verb_span":"predicate", "statement_span":"object"}[slot]]:
                return {**candidate, "validation_status": "FAILED", "review_status": "GROUNDING_FAILED",
                        "auto_validation": {"passed": False, "rejection_reasons": ["STATEMENT_SPEAKER_NOT_GROUNDED"]}}
    checked = validate_v3(candidate, source, eval_queries=eval_queries, test_works=test_works,
                          seen_queries=seen_queries)
    checked["validation_status"] = ("AUTO_VALIDATED" if checked["review_status"] == "AUTO_VALIDATED"
                                    else "FAILED")
    return checked
