"""High-precision, source-clause-driven domain QA extraction.

The LLM has no path to assign a relation, participant, answer, or category.
Every HIGH proposition is created by a closed deterministic extractor.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
import unicodedata

from rag_domain_qa_v2 import RuleEntailmentJudge, validate
from rag_domain_common import normalized_query


class Relation(str, Enum):
    ACTION = "ACTION"
    ENTITY_RELATION = "ENTITY_RELATION"
    LOCATION_AT = "LOCATION_AT"
    LOCATION_FROM = "LOCATION_FROM"
    LOCATION_TO = "LOCATION_TO"
    TEMPORAL_AT = "TEMPORAL_AT"
    TEMPORAL_BEFORE = "TEMPORAL_BEFORE"
    TEMPORAL_AFTER = "TEMPORAL_AFTER"
    CAUSE = "CAUSE"
    MOTIVATION = "MOTIVATION"
    INSTRUCTION = "INSTRUCTION"
    STATEMENT = "STATEMENT"
    ATTRIBUTE = "ATTRIBUTE"
    STATE_CHANGE = "STATE_CHANGE"
    SEQUENCE = "SEQUENCE"


NAME = r"(?:Mr\.|Mrs\.|Miss|Dr\.|Lord|Lady)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?|[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?"
PLACE = r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}"
HONORIFICS = {"Mr.", "Mrs.", "Dr.", "St."}
BAD_NAME = {"The", "And", "But", "For", "Then", "When", "What", "This", "That", "Next",
            "After", "Before", "From", "Although", "Yet", "However", "There", "They", "She",
            "He", "His", "Her", "Their", "One", "You", "I", "We", "It", "Having", "In", "At"}
KIN = ("brother-in-law", "sister-in-law", "brother", "sister", "father", "mother", "son",
       "daughter", "husband", "wife", "friend", "servant", "master", "guardian", "uncle",
       "aunt", "cousin")
ACTION_VERBS = {"growled", "laughed", "smiled", "cried", "shouted", "replied", "nodded",
                "refused", "left", "returned", "opened", "closed", "destroyed", "found",
                "gave", "sent", "wrote", "rescued", "helped", "warned", "invited"}
BASE = {"growled": "growl", "laughed": "laugh", "smiled": "smile", "cried": "cry",
        "shouted": "shout", "replied": "reply", "nodded": "nod", "refused": "refuse",
        "left": "leave", "returned": "return", "opened": "open", "closed": "close",
        "destroyed": "destroy", "found": "find", "gave": "give", "sent": "send",
        "wrote": "write", "rescued": "rescue", "helped": "help", "warned": "warn",
        "invited": "invite", "travelled": "travel", "traveled": "travel", "went": "go",
        "moved": "move", "arrived": "arrive", "came": "come", "told": "tell",
        "asked": "ask", "ordered": "order", "instructed": "instruct", "charged": "charge",
        "wanted": "want", "hoped": "hope", "wished": "wish", "intended": "intend"}


@dataclass(frozen=True)
class Span:
    text: str
    start: int  # relative to chunk
    end: int
    sentence_start: int
    sentence_end: int


def segment_sentences(text):
    """Conservative offset-preserving punctuation splitter."""
    start = 0
    for i, char in enumerate(text):
        if char not in ".!?": continue
        if char == ".":
            prev = text[max(start, i - 5):i + 1].split()[-1] if text[max(start, i - 5):i + 1].split() else ""
            if any(prev.endswith(h) for h in HONORIFICS): continue
            if i and i + 1 < len(text) and text[i - 1].isdigit() and text[i + 1].isdigit(): continue
        end = i + 1
        while end < len(text) and text[end] in '"”’\')]}': end += 1
        raw = text[start:end]
        trimmed = raw.strip()
        if trimmed:
            left = start + len(raw) - len(raw.lstrip())
            yield Span(trimmed, left, left + len(trimmed), left, left + len(trimmed))
        start = end
    if start < len(text):
        raw = text[start:]
        trimmed = raw.strip()
        if trimmed:
            left = start + len(raw) - len(raw.lstrip())
            yield Span(trimmed, left, left + len(trimmed), left, left + len(trimmed))


def segment_clauses(sentence: Span):
    """Keep causal/temporal connectives attached; split strong punctuation only."""
    text = sentence.text
    boundaries = [0] + [i + 1 for i, x in enumerate(text) if x in ";:"] + [len(text)]
    for lo, hi in zip(boundaries, boundaries[1:]):
        raw = text[lo:hi]
        trimmed = raw.strip()
        if not trimmed: continue
        left = sentence.start + lo + len(raw) - len(raw.lstrip())
        yield Span(trimmed, left, left + len(trimmed), sentence.start, sentence.end)


def is_name(value):
    val = re.sub(r"\s+", " ", value).strip()
    return val.split()[0] not in BAD_NAME and re.fullmatch(NAME, val) is not None


def subject_is_clause_head(clause, match):
    """Reject names embedded in a preceding prepositional noun phrase."""
    prefix = clause.text[:match.start("subject")]
    prior = re.search(r"([A-Za-z]+)\s*$", prefix)
    return prior is None or prior.group(1).casefold() not in {
        "from", "of", "to", "for", "by", "with", "about", "near", "beside", "toward", "towards"}


def normalize(value):
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("“", '"').replace("”", '"').replace("’", "'")
    return re.sub(r"\s+", " ", value).casefold().strip()


def resolve_pronoun(pronoun, prefix):
    """Only a unique local named antecedent before a singular pronoun may resolve."""
    if pronoun.casefold() not in {"he", "she", "him", "her", "his"}: return None
    names = [m.group() for m in re.finditer(r"\b(?:" + NAME + r")\b", prefix) if is_name(m.group())]
    unique = list(dict.fromkeys(names))
    if len(unique) != 1: return None
    return {"original": pronoun, "resolved": unique[0],
            "method": "same_sentence_unique_antecedent", "confidence": "HIGH"}


def _slot_span(clause: Span, match, group, row):
    return [row["source_start_char"] + clause.start + match.start(group),
            row["source_start_char"] + clause.start + match.end(group)]


def _make(row, clause, relation, match, *, asked_slot, answer_type, category,
          v2_relation, question, slot_group, extras=None, confidence="HIGH"):
    if not isinstance(relation, Relation): raise TypeError("Closed relation enum required")
    if row["text"].count(clause.text) != 1: return None
    span = _slot_span(clause, match, slot_group, row)
    answer = match.group(slot_group)
    base = {"relation_type": v2_relation, "v3_relation": relation.value,
            "source_sentence": clause.text, "evidence_quote": clause.text,
            "evidence_start": row["source_start_char"] + clause.start,
            "evidence_end": row["source_start_char"] + clause.end,
            "answer_span": span, "proof_kind": "EXACT_RULE", "rule_id": relation.value}
    for key in ("subject", "predicate", "object"):
        if key in match.groupdict() and match.group(key):
            base[key] = match.group(key)
            base[f"{key}_span"] = _slot_span(clause, match, key, row)
    base.update(extras or {})
    if asked_slot not in base: base[asked_slot] = answer
    return {"work_id": row["work_id"], "book_title": row["title"], "chapter": row["chapter"],
            "chunk_id": row["chunk_id"], "source_hash": row["source_sha256"],
            "source_start": row["source_start_char"], "source_end": row["source_end_char"],
            "positive_passage": row["text"], "split": row["split"],
            "sentence_start": row["source_start_char"] + clause.sentence_start,
            "sentence_end": row["source_start_char"] + clause.sentence_end,
            "clause_start": row["source_start_char"] + clause.start,
            "clause_end": row["source_start_char"] + clause.end,
            "clause_text": clause.text, "proposition": base, "relation_type": relation.value,
            "asked_slot": asked_slot, "answer_surface": answer,
            "answer_normalized": normalize(answer), "short_answer": answer,
            "answer_type": answer_type, "generator_category": category,
            "validated_category": category, "category": category,
            "difficulty": "EASY", "template_question": question, "question": question,
            "final_question": question, "question_from_template": True,
            "extractor_confidence": confidence, "review_status": "GENERATED",
            "reviewer": None, "reviewed_at": None}


class Extractor:
    relation: Relation
    def can_match(self, clause): return False
    def extract(self, clause, row): return []


class InstructionExtractor(Extractor):
    relation = Relation.INSTRUCTION
    pattern = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<predicate>told|asked|ordered|instructed|charged)\s+"
                         rf"(?P<object>{NAME})\s+to\s+(?P<instruction>[a-z][^,;!?]{{4,}})")
    def can_match(self, clause): return bool(re.search(r"\b(?:told|asked|ordered|instructed|charged)\b", clause.text, re.I))
    def extract(self, clause, row):
        out = []
        for m in self.pattern.finditer(clause.text):
            if not is_name(m["subject"]) or not subject_is_clause_head(clause, m) or not is_name(m["object"]): continue
            instruction = m["instruction"].strip().rstrip(".!")
            if len(instruction.split()) < 3 or len(instruction) > 100 or re.search(
                    r"\b(?:at|to|from|of|with|and|or|the|a|an)\s*$", instruction, re.I):
                continue
            q = f"Whom did {m['subject']} {BASE[m['predicate'].lower()]} to {instruction}?"
            prop = _make(row, clause, self.relation, m, asked_slot="object", answer_type="PERSON",
                         category="FACTUAL_DIRECT", v2_relation="ENTITY_ACTION", question=q,
                         slot_group="object", extras={"instruction": m["instruction"],
                         "instruction_span": _slot_span(clause, m, "instruction", row)})
            if prop: out.append(prop)
        return out


class EntityRelationExtractor(Extractor):
    relation = Relation.ENTITY_RELATION
    pattern = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<predicate>was|is)\s+"
                         rf"(?P<object>(?P<owner>{NAME})['’]s\s+(?P<kin>{'|'.join(KIN)}))\b")
    def can_match(self, clause): return any(re.search(r"\b" + re.escape(k) + r"\b", clause.text, re.I) for k in KIN)
    def extract(self, clause, row):
        out = []
        for m in self.pattern.finditer(clause.text):
            if not is_name(m["subject"]) or not subject_is_clause_head(clause, m) or not is_name(m["owner"]): continue
            q = f"Which person was identified as {m['owner']}'s {m['kin']}?"
            prop = _make(row, clause, self.relation, m, asked_slot="subject", answer_type="PERSON",
                         category="ENTITY_RELATION", v2_relation="ENTITY_RELATION", question=q,
                         slot_group="subject", extras={"entity_a": m["subject"], "entity_b": m["owner"],
                         "relation_direction": m["kin"].upper().replace("-", "_") + "_OF"})
            if prop: out.append(prop)
        return out


class CauseExtractor(Extractor):
    relation = Relation.CAUSE
    pattern = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<predicate>destroyed|left|returned|opened|closed|"
                         rf"refused|hid|stopped|cried|smiled|went|came)\s+(?P<object>[^,;.!?]{{0,40}}?)\s+"
                         rf"because\s+(?P<cause>[^,;.!?]{{10,90}})")
    def can_match(self, clause): return "because" in clause.text.casefold()
    def extract(self, clause, row):
        out = []
        for m in self.pattern.finditer(clause.text):
            if not is_name(m["subject"]) or not subject_is_clause_head(clause, m): continue
            cause = m["cause"].strip()
            if len(cause.split()) < 3: continue
            effect = clause.text[m.start("subject"):m.end("object")].strip()
            action = BASE[m["predicate"].lower()]
            obj = m["object"].strip()
            q = f"What caused {m['subject']} to {action} {obj}?" if obj else f"What caused {m['subject']} to {action} at that time?"
            if "that" in q.casefold(): continue
            prop = _make(row, clause, self.relation, m, asked_slot="cause", answer_type="CAUSE",
                         category="CAUSAL", v2_relation="CAUSE_EFFECT", question=q, slot_group="cause",
                         extras={"cause": cause, "effect": effect,
                                 "cause_span": _slot_span(clause, m, "cause", row),
                                 "effect_span": [row["source_start_char"] + clause.start + m.start("subject"),
                                                 row["source_start_char"] + clause.start + m.end("object")]})
            if prop: out.append(prop)
        return out


class MotivationExtractor(Extractor):
    relation = Relation.MOTIVATION
    pattern = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<predicate>wanted|hoped|wished|intended)\s+"
                         rf"(?P<cause>to\s+[^,;.!?]{{8,70}})")
    def can_match(self, clause): return bool(re.search(r"\b(?:wanted|hoped|wished|intended)\s+to\b", clause.text, re.I))
    def extract(self, clause, row):
        out = []
        for m in self.pattern.finditer(clause.text):
            if not is_name(m["subject"]) or not subject_is_clause_head(clause, m) or len(m["cause"].split()) < 3: continue
            if re.search(r"\b(?:something|someone|somewhere|somewheres)\b|--", m["cause"], re.I):
                continue
            motive_action = re.match(r"to\s+(\w+)", m["cause"], re.I)
            if not motive_action or motive_action.group(1).lower() not in {
                    "kill", "visit", "go", "leave", "find", "take", "help", "speak", "write",
                    "send", "tell", "meet", "dissuade", "call"}:
                continue
            q = f"What action did {m['subject']} {BASE[m['predicate'].lower()]} to take?"
            prop = _make(row, clause, self.relation, m, asked_slot="cause", answer_type="CAUSE",
                         category="MOTIVATION", v2_relation="MOTIVATION", question=q,
                         slot_group="cause", extras={"cause": m["cause"],
                         "effect": m.group(0), "cause_span": _slot_span(clause, m, "cause", row)},
                         confidence="HIGH" if m["predicate"].lower() == "wanted" else "MEDIUM")
            if prop: out.append(prop)
        return out


class LocationExtractor(Extractor):
    relation = Relation.LOCATION_FROM
    pattern = re.compile(rf"\b(?P<subject>{NAME}|he|she)\s+(?P<predicate>travelled|traveled|went|moved)\s+"
                         rf"(?P<direction>from|to|into|at|in)\s+(?P<location>{PLACE})\b")
    second = re.compile(rf"\b(?P<direction>from|to|into)\s+(?P<location>{PLACE})\b")
    def can_match(self, clause): return bool(re.search(r"\b(?:travelled|traveled|went|moved)\b", clause.text, re.I))
    def extract(self, clause, row):
        out = []
        for m in self.pattern.finditer(clause.text):
            resolution = None
            subject = m["subject"]
            if not is_name(subject):
                resolution = resolve_pronoun(subject, clause.text[:m.start("subject")])
                if resolution is None: continue
                subject = resolution["resolved"]
            if not is_name(m["location"]) or (resolution is None and not subject_is_clause_head(clause, m)): continue
            spans = [(m["direction"], m["location"], m.start("location"), m.end("location"))]
            tail = clause.text[m.end("location"):m.end("location") + 55]
            s = self.second.search(tail)
            if s:
                spans.append((s["direction"], s["location"], m.end("location") + s.start("location"),
                              m.end("location") + s.end("location")))
            for direction, location, lo, hi in spans[:2]:
                d = "FROM" if direction.lower() == "from" else "TO" if direction.lower() in {"to", "into"} else "IN"
                relation = Relation.LOCATION_FROM if d == "FROM" else Relation.LOCATION_TO if d == "TO" else Relation.LOCATION_AT
                q = f"Where did {subject} {BASE[m['predicate'].lower()]} {direction.lower()} on the journey?"
                prop = _make(row, clause, relation, m, asked_slot="location", answer_type="LOCATION",
                             category="LOCATION", v2_relation="LOCATION", question=q, slot_group="location",
                             extras={"location": location, "location_direction": d,
                                     "location_span": [row["source_start_char"] + clause.start + lo,
                                                       row["source_start_char"] + clause.start + hi]})
                if prop:
                    if resolution:
                        prop["proposition"]["subject"] = subject
                        pos = clause.text[:m.start("subject")].rfind(subject)
                        prop["proposition"]["subject_span"] = [row["source_start_char"] + clause.start + pos,
                                                                 row["source_start_char"] + clause.start + pos + len(subject)]
                        prop["referent_resolution"] = resolution
                    prop["short_answer"] = location
                    prop["answer_surface"] = location
                    prop["answer_normalized"] = normalize(location)
                    prop["proposition"]["answer_span"] = prop["proposition"]["location_span"]
                    out.append(prop)
        return out


class TemporalExtractor(Extractor):
    relation = Relation.TEMPORAL_AT
    pattern = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<predicate>arrived|left|returned|came|went)\s+"
                         rf"(?P<time>at\s+(?:\d{{1,2}}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+o['’]clock|on\s+(?:Monday|Tuesday|Wednesday|Thursday|"
                         rf"Friday|Saturday|Sunday)|the next day|during the night)\b", re.I)
    def can_match(self, clause): return bool(re.search(r"\b(?:arrived|left|returned|came|went)\b", clause.text, re.I))
    def extract(self, clause, row):
        out = []
        for m in self.pattern.finditer(clause.text):
            if not is_name(m["subject"]) or not subject_is_clause_head(clause, m): continue
            day = m["time"].lower().startswith("on ")
            clock = "o'clock" in m["time"].lower() or "o’clock" in m["time"].lower()
            q = (f"On which day did {m['subject']} {BASE[m['predicate'].lower()]}?" if day else
                 f"At what clock time did {m['subject']} {BASE[m['predicate'].lower()]}?" if clock else
                 f"When in the sequence did {m['subject']} {BASE[m['predicate'].lower()]}?")
            prop = _make(row, clause, self.relation, m, asked_slot="time", answer_type="TIME",
                         category="TEMPORAL", v2_relation="TEMPORAL", question=q, slot_group="time",
                         extras={"time": m["time"], "temporal_relation": "AT_TIME",
                                 "time_span": _slot_span(clause, m, "time", row)},
                         confidence="MEDIUM" if (not day and not clock) or re.search(
                             r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b",
                             m["time"], re.I) else "HIGH")
            if prop: out.append(prop)
        return out


class StatementExtractor(Extractor):
    relation = Relation.STATEMENT
    pattern = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<predicate>said|stated|replied)\s+that\s+"
                         rf"(?P<object>[^,;.!?]{{15,85}})")
    def can_match(self, clause): return bool(re.search(r"\b(?:said|stated|replied)\s+that\b", clause.text, re.I))
    def extract(self, clause, row):
        out = []
        for m in self.pattern.finditer(clause.text):
            if not is_name(m["subject"]) or not subject_is_clause_head(clause, m) or not 4 <= len(m["object"].split()) <= 16: continue
            names = [n.group() for n in re.finditer(r"\b(?:" + NAME + r")\b", m["object"]) if is_name(n.group())]
            if not names: continue
            q = f"What did {m['subject']} say about {names[0]} in the conversation?"
            prop = _make(row, clause, self.relation, m, asked_slot="object", answer_type="PHRASE",
                         category="FACTUAL_DIRECT", v2_relation="EVENT", question=q, slot_group="object")
            if prop: out.append(prop)
        return out


class ActionExtractor(Extractor):
    relation = Relation.ACTION
    pattern = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<predicate>{'|'.join(ACTION_VERBS)})\b"
                         rf"(?P<trigger>\s+after\s+[^,;!?]{{12,75}})")
    def can_match(self, clause): return "after" in clause.text.casefold()
    def extract(self, clause, row):
        out = []
        for m in self.pattern.finditer(clause.text):
            if not is_name(m["subject"]) or not subject_is_clause_head(clause, m): continue
            trigger = m["trigger"].strip().rstrip(".!")
            if not re.search(r"\b[A-Z][a-z]{2,}\b", trigger): continue
            q = f"How did {m['subject']} react {trigger}?"
            prop = _make(row, clause, self.relation, m, asked_slot="object", answer_type="EVENT",
                         category="EVENT", v2_relation="ENTITY_ACTION", question=q,
                         slot_group="predicate", extras={"object": m["predicate"],
                         "object_span": _slot_span(clause, m, "predicate", row),
                         "trigger": trigger})
            if prop: out.append(prop)
        return out


class AttributeExtractor(Extractor):
    relation = Relation.ATTRIBUTE
    pattern = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<predicate>became|remained|appeared)\s+"
                         rf"(?P<object>[a-z]{{4,20}})\b")
    def can_match(self, clause): return bool(re.search(r"\b(?:became|remained|appeared)\b", clause.text, re.I))
    def extract(self, clause, row):
        out = []
        for m in self.pattern.finditer(clause.text):
            if not is_name(m["subject"]) or not subject_is_clause_head(clause, m): continue
            q = f"What state did {m['subject']} become in the account?"
            prop = _make(row, clause, self.relation, m, asked_slot="object", answer_type="PHRASE",
                         category="FACTUAL_DIRECT", v2_relation="ATTRIBUTE", question=q,
                         slot_group="object", confidence="MEDIUM")
            if prop: out.append(prop)
        return out


EXTRACTORS = [InstructionExtractor(), EntityRelationExtractor(), CauseExtractor(),
              MotivationExtractor(), LocationExtractor(), TemporalExtractor(),
              StatementExtractor(), ActionExtractor(), AttributeExtractor()]


def extract_from_clause(clause, row):
    for extractor in EXTRACTORS:
        if extractor.can_match(clause):
            found = extractor.extract(clause, row)
            if found: return found[:2]
    return []


def proposition_fingerprint(candidate):
    p = candidate["proposition"]
    values = [candidate["work_id"], str(p["evidence_start"]), str(p["evidence_end"]),
              candidate["relation_type"], candidate["asked_slot"],
              normalize(p.get("subject", "")), normalize(p.get("predicate", "")),
              normalize(candidate["short_answer"])]
    return hashlib.sha256("\x1f".join(values).encode()).hexdigest()[:24]


def qa_fingerprint(candidate):
    return hashlib.sha256("\x1f".join((normalized_query(candidate["question"]),
                                       normalize(candidate["short_answer"]),
                                       proposition_fingerprint(candidate))).encode()).hexdigest()[:24]


def extract_chunk(row):
    seen = set()
    stats = {"sentences": 0, "clauses": 0, "relation_patterns_matched": 0,
             "duplicates_within_chunk": 0}
    out = []
    for sentence in segment_sentences(row["text"]):
        stats["sentences"] += 1
        for clause in segment_clauses(sentence):
            stats["clauses"] += 1
            for candidate in extract_from_clause(clause, row):
                stats["relation_patterns_matched"] += 1
                fp = proposition_fingerprint(candidate)
                if fp in seen:
                    stats["duplicates_within_chunk"] += 1
                    continue
                seen.add(fp)
                candidate["proposition_fingerprint"] = fp
                candidate["qa_fingerprint"] = qa_fingerprint(candidate)
                out.append(candidate)
    return out, stats


def validate_v3(candidate, source, *, eval_queries=(), test_works=(), seen_queries=()):
    if candidate["extractor_confidence"] != "HIGH":
        return {**candidate, "review_status": "MEDIUM_LOW_DIAGNOSTIC",
                "auto_validation": {"passed": False, "rejection_reasons": ["CONFIDENCE_NOT_HIGH"]}}
    p = candidate["proposition"]
    for name in ("answer_span", "subject_span", "predicate_span", "object_span", "cause_span",
                 "effect_span", "location_span", "time_span", "instruction_span"):
        if name in p:
            span = p[name]
            if (not isinstance(span, list) or len(span) != 2 or
                    source[span[0]:span[1]] != (candidate["short_answer"] if name == "answer_span" else
                    p.get(name.removesuffix("_span"), p.get("instruction", "")))):
                return {**candidate, "review_status": "GROUNDING_FAILED",
                        "auto_validation": {"passed": False, "rejection_reasons": ["SOURCE_SLOT_SPAN_MISMATCH"]}}
    return validate(candidate, source, eval_queries=eval_queries, test_works=test_works,
                    seen_queries=seen_queries, judge=RuleEntailmentJudge())


def accept_paraphrase(candidate, proposed, source, *, eval_queries=(), test_works=()):
    """Keep the template whenever wording changes a protected semantic anchor."""
    if not proposed or not proposed.endswith("?") or normalize(proposed) == normalize(candidate["question"]):
        return candidate, "NO_PARAPHRASE"
    answer = normalize(candidate["short_answer"])
    if answer in normalize(proposed): return candidate, "ANSWER_DRIFT"
    protected = [candidate["proposition"].get("subject", "")]
    protected += [candidate["proposition"].get(k, "") for k in ("entity_a", "entity_b")]
    if any(x and normalize(x) not in normalize(proposed) for x in protected):
        return candidate, "PARTICIPANT_DRIFT"
    old_direction = set(re.findall(r"\b(?:from|to|before|after)\b", candidate["question"], re.I))
    new_direction = set(re.findall(r"\b(?:from|to|before|after)\b", proposed, re.I))
    if old_direction != new_direction: return candidate, "RELATION_DRIFT"
    changed = {**candidate, "question": proposed, "final_question": proposed,
               "question_from_template": False}
    checked = validate_v3(changed, source, eval_queries=eval_queries, test_works=test_works)
    if checked["review_status"] != "AUTO_VALIDATED": return candidate, "VALIDATOR_REJECTED_PARAPHRASE"
    # Rule entailment accepts only templates; without a separate dependable
    # judge a free paraphrase is never auto-admitted.
    return candidate, "PARAPHRASE_REQUIRES_SEMANTIC_JUDGE"
