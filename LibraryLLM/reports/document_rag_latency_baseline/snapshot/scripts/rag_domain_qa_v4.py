"""Relation-specific high-precision extensions over the unchanged v3/v2 path."""
from __future__ import annotations

from collections import Counter
import re

from rag_domain_qa_v3 import (NAME, PLACE, KIN, BASE, Relation, Span, _make,
                              extract_from_clause as v3_extract_from_clause,
                              is_name, normalize, proposition_fingerprint,
                              qa_fingerprint, segment_clauses, segment_sentences,
                              subject_is_clause_head, validate_v3)

ROLE = ("doctor", "physician", "captain", "guardian", "servant", "master",
        "teacher", "magistrate", "clerk", "lawyer", "nurse", "companion", "friend")
STATE = ("pensive", "silent", "angry", "ill", "quiet", "sad", "frightened",
         "confused", "disjointed", "thoughtful")
MOTION = {"went": "go", "came": "come", "travelled": "travel", "traveled": "travel",
          "walked": "walk", "rode": "ride", "sailed": "sail", "returned": "return",
          "arrived": "arrive", "entered": "enter", "left": "leave", "departed": "depart"}
INSTRUCT = {"told": "tell", "asked": "ask", "ordered": "order", "instructed": "instruct",
            "charged": "charge", "warned": "warn", "advised": "advise", "urged": "urge",
            "requested": "request"}
CAUSE_VERB = {"destroyed": "destroy", "left": "leave", "returned": "return",
              "opened": "open", "closed": "close", "refused": "refuse", "came": "come",
              "went": "go", "hid": "hide", "stopped": "stop", "saved": "save",
              "chose": "choose", "bent": "bend"}
BAD_COMPLEMENT = {"it", "that", "so", "there", "one", "something", "nothing",
                  "good", "bad", "strange", "more", "very", "with", "beyond", "again"}


def _surface_safe(text):
    return bool(text) and not re.search(r"\b(?:he|she|they|it|this|that|there|here|someone|something)\b", text, re.I)


def _finalize(candidate, *, training_value=None, diagnostics=None):
    candidate["extractor_version"] = "v4"
    candidate["confidence_reasons"] = diagnostics or []
    candidate["training_value"] = training_value or training_value_of(candidate)
    candidate["difficulty"] = "MEDIUM" if candidate["relation_type"] in {
        "ENTITY_RELATION", "CAUSE", "STATEMENT", "ATTRIBUTE"} else "EASY"
    return candidate


def training_value_of(candidate):
    relation = candidate["relation_type"]
    q = candidate["question"]
    if relation in {"CAUSE", "ENTITY_RELATION", "INSTRUCTION"} and len(q.split()) >= 7:
        return "HIGH"
    if relation == "STATEMENT" and len(candidate["short_answer"].split()) >= 6:
        return "HIGH"
    if relation == "ATTRIBUTE":
        return "MEDIUM" if candidate["proposition"].get("attribute_kind") in {"ROLE", "STATE_CHANGE"} else "LOW"
    if relation in {"LOCATION_TO", "LOCATION_FROM", "TEMPORAL_AT", "ACTION", "MOTIVATION"}:
        return "MEDIUM"
    return "LOW"


def evidence_contract(candidate, source):
    """A HIGH v4 proposition must satisfy its own relation's required slots."""
    p = candidate["proposition"]
    relation = Relation(candidate["relation_type"])
    required = {
        Relation.ACTION: ("subject_span", "predicate_span", "object_span"),
        Relation.ENTITY_RELATION: ("entity_a_span", "relation_span", "entity_b_span"),
        Relation.LOCATION_AT: ("subject_span", "predicate_span", "location_span", "marker_span"),
        Relation.LOCATION_FROM: ("subject_span", "predicate_span", "location_span", "marker_span"),
        Relation.LOCATION_TO: ("subject_span", "predicate_span", "location_span", "marker_span"),
        Relation.TEMPORAL_AT: ("subject_span", "predicate_span", "time_span"),
        Relation.CAUSE: ("subject_span", "predicate_span", "cause_span", "effect_span", "causal_marker_span"),
        Relation.MOTIVATION: ("subject_span", "predicate_span", "cause_span"),
        Relation.INSTRUCTION: ("subject_span", "object_span", "instruction_span"),
        Relation.STATEMENT: ("subject_span", "predicate_span", "object_span"),
        Relation.ATTRIBUTE: ("subject_span", "predicate_span", "object_span"),
    }.get(relation, ())
    if not required or any(key not in p for key in required):
        return ["EVIDENCE_CONTRACT_INCOMPLETE"]
    for key in required + ("answer_span",):
        span = p[key]
        if not isinstance(span, list) or len(span) != 2 or not isinstance(span[0], int) or not isinstance(span[1], int):
            return ["EVIDENCE_CONTRACT_SPAN_INVALID"]
        if not (p["evidence_start"] <= span[0] < span[1] <= p["evidence_end"]):
            return ["EVIDENCE_CONTRACT_SPAN_OUTSIDE"]
        if not source[span[0]:span[1]]:
            return ["EVIDENCE_CONTRACT_EMPTY_SPAN"]
    if source[p["answer_span"][0]:p["answer_span"][1]] != candidate["short_answer"]:
        return ["ANSWER_SLOT_SPAN_MISMATCH"]
    return []


def validate_v4(candidate, source, *, eval_queries=(), test_works=(), seen_queries=()):
    if candidate["extractor_confidence"] != "HIGH":
        return {**candidate, "review_status": "MEDIUM_LOW_DIAGNOSTIC",
                "auto_validation": {"passed": False, "rejection_reasons": candidate.get("confidence_reasons", [])}}
    if candidate.get("extractor_version") == "v3_preserved":
        return validate_v3(candidate, source, eval_queries=eval_queries, test_works=test_works,
                           seen_queries=seen_queries)
    codes = evidence_contract(candidate, source)
    if codes:
        return {**candidate, "review_status": "GROUNDING_FAILED",
                "auto_validation": {"passed": False, "rejection_reasons": codes}}
    return validate_v3(candidate, source, eval_queries=eval_queries, test_works=test_works,
                       seen_queries=seen_queries)


class V4Extractor:
    name = "BASE"
    def can_match(self, clause): return False
    def extract(self, clause, row): return []


class InstructionV4(V4Extractor):
    name = "INSTRUCTION"
    pattern = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<predicate>{'|'.join(INSTRUCT)})\s+"
                         rf"(?P<object>{NAME})\s+to\s+(?P<instruction>[a-z][^,;!?]{{6,}})")
    def can_match(self, clause): return bool(re.search(r"\b(?:warned|advised|urged|requested)\b", clause.text, re.I))
    def extract(self, clause, row):
        out = []
        for m in self.pattern.finditer(clause.text):
            if m["predicate"] not in {"warned", "advised", "urged", "requested"}: continue
            if not is_name(m["subject"]) or not is_name(m["object"]) or not subject_is_clause_head(clause, m): continue
            instruction = m["instruction"].rstrip(".!").strip()
            if not 3 <= len(instruction.split()) <= 18 or re.search(r"\b(?:at|to|of|with|and|the)\s*$", instruction): continue
            q = f"Whom did {m['subject']} {INSTRUCT[m['predicate']]} to {instruction}?"
            c = _make(row, clause, Relation.INSTRUCTION, m, asked_slot="object", answer_type="PERSON",
                      category="FACTUAL_DIRECT", v2_relation="ENTITY_ACTION", question=q,
                      slot_group="object", extras={"instruction": m["instruction"],
                      "instruction_span": _span(row, clause, m, "instruction")})
            if c: out.append(_finalize(c))
        return out


def _span(row, clause, m, group):
    return [row["source_start_char"] + clause.start + m.start(group),
            row["source_start_char"] + clause.start + m.end(group)]


class RelationV4(V4Extractor):
    name = "ENTITY_RELATION"
    appositive = re.compile(rf"\b(?P<subject>{NAME}),\s+(?P<object>(?P<owner>{NAME})['’]s\s+"
                            rf"(?P<kin>{'|'.join(KIN)})),", re.I)
    of_pattern = re.compile(rf"\b(?P<subject>{NAME}),\s+(?P<object>the\s+(?P<kin>{'|'.join(KIN)})\s+of\s+"
                            rf"(?P<owner>{NAME})),", re.I)
    def can_match(self, clause): return any(re.search(r"\b" + re.escape(k) + r"\b", clause.text, re.I) for k in KIN)
    def extract(self, clause, row):
        out = []
        for pattern in (self.appositive, self.of_pattern):
            for m in pattern.finditer(clause.text):
                if not is_name(m["subject"]) or not is_name(m["owner"]) or not subject_is_clause_head(clause, m): continue
                # The appositive itself is the explicit relation marker.
                q = f"Which person was identified as {m['owner']}'s {m['kin']}?"
                c = _make(row, clause, Relation.ENTITY_RELATION, m, asked_slot="subject",
                          answer_type="PERSON", category="ENTITY_RELATION",
                          v2_relation="ENTITY_RELATION", question=q, slot_group="subject",
                          extras={"entity_a": m["subject"], "entity_b": m["owner"],
                                  "relation_direction": m["kin"].upper().replace("-", "_") + "_OF",
                                  "entity_a_span": _span(row, clause, m, "subject"),
                                  "entity_b_span": _span(row, clause, m, "owner"),
                                  "relation_span": _span(row, clause, m, "kin")})
                if c: out.append(_finalize(c))
        return out


class CauseV4(V4Extractor):
    name = "CAUSE"
    pattern = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<predicate>{'|'.join(CAUSE_VERB)})\s*"
                         rf"(?P<object>[^,;.!?]{{0,35}}?)\s*,?\s*(?P<marker>because)\s+"
                         rf"(?P<cause>[^,;.!?]{{10,100}})")
    def can_match(self, clause): return "because" in clause.text.casefold()
    def extract(self, clause, row):
        out = []
        for m in self.pattern.finditer(clause.text):
            if not is_name(m["subject"]) or not subject_is_clause_head(clause, m): continue
            if len(m["cause"].split()) < 3 or re.search(r"\b(?:this|that|something)\b", m["cause"], re.I): continue
            obj = m["object"].strip()
            if not obj or len(obj.split()) > 6: continue
            effect = clause.text[m.start("subject"):m.end("object")].strip()
            q = f"What caused {m['subject']} to {CAUSE_VERB[m['predicate']]} {obj}?"
            c = _make(row, clause, Relation.CAUSE, m, asked_slot="cause", answer_type="CAUSE",
                      category="CAUSAL", v2_relation="CAUSE_EFFECT", question=q, slot_group="cause",
                      extras={"cause": m["cause"], "effect": effect,
                              "cause_span": _span(row, clause, m, "cause"),
                              "effect_span": [row["source_start_char"] + clause.start + m.start("subject"),
                                              row["source_start_char"] + clause.start + m.end("object")],
                              "causal_marker_span": _span(row, clause, m, "marker")})
            if c: out.append(_finalize(c))
        return out


class MotivationV4(V4Extractor):
    name = "MOTIVATION"
    pattern = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<predicate>hoped|wanted)\s+"
                         rf"(?P<cause>to\s+(?:kill|visit|go|leave|find|take|help|speak|write|send|tell|meet|call)"
                         rf"\s+[^,;.!?]{{4,70}})")
    def can_match(self, clause): return bool(re.search(r"\b(?:hoped|wanted)\s+to\b", clause.text, re.I))
    def extract(self, clause, row):
        out = []
        for m in self.pattern.finditer(clause.text):
            if not is_name(m["subject"]) or not subject_is_clause_head(clause, m): continue
            if re.search(r"\b(?:he|she|they|it|me|him|her|them|something)\b", m["cause"], re.I): continue
            if len(m["cause"].split()) < 3: continue
            q = f"What action did {m['subject']} {('hope' if m['predicate']=='hoped' else 'want')} to take?"
            c = _make(row, clause, Relation.MOTIVATION, m, asked_slot="cause", answer_type="CAUSE",
                      category="MOTIVATION", v2_relation="MOTIVATION", question=q, slot_group="cause",
                      extras={"cause": m["cause"], "effect": m.group(0),
                              "cause_span": _span(row, clause, m, "cause")})
            if c: out.append(_finalize(c))
        return out


class LocationV4(V4Extractor):
    name = "LOCATION"
    pattern = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<predicate>{'|'.join(MOTION)})\s+"
                         rf"(?P<marker>from|to|into|in|at)\s+(?P<location>{PLACE})\b")
    departure = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<predicate>left|departed)\s+"
                           rf"(?P<location>{PLACE})\b")
    def can_match(self, clause): return any(re.search(r"\b" + x + r"\b", clause.text) for x in MOTION)
    def extract(self, clause, row):
        out = []
        for pattern in (self.pattern, self.departure):
            for m in pattern.finditer(clause.text):
                if not is_name(m["subject"]) or not is_name(m["location"]) or not subject_is_clause_head(clause, m): continue
                marker = m.groupdict().get("marker") or "left"
                direction = "FROM" if marker in {"from", "left"} else "TO" if marker in {"to", "into", "in"} else "AT"
                relation = Relation.LOCATION_FROM if direction == "FROM" else Relation.LOCATION_TO if direction == "TO" else Relation.LOCATION_AT
                if m["predicate"] == "arrived" and direction == "FROM": continue
                q = (f"Which place did {m['subject']} leave on the journey?" if marker == "left" else
                     f"Where did {m['subject']} {MOTION[m['predicate']]} {marker} on the journey?")
                c = _make(row, clause, relation, m, asked_slot="location", answer_type="LOCATION",
                          category="LOCATION", v2_relation="LOCATION", question=q, slot_group="location",
                          extras={"location": m["location"], "location_direction": direction,
                                  "location_span": _span(row, clause, m, "location"),
                                  "marker_span": _span(row, clause, m, "marker") if "marker" in m.groupdict() else
                                  _span(row, clause, m, "predicate")})
                if c: out.append(_finalize(c))
        return out[:2]


class TemporalV4(V4Extractor):
    name = "TEMPORAL"
    pattern = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<predicate>arrived|left|returned|came|went)\s+"
                         rf"(?P<time>on\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)|"
                         rf"at\s+\d{{1,2}}\s+o['’]clock|at\s+noon|at\s+midnight)\b")
    def can_match(self, clause): return bool(re.search(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|noon|midnight|o'clock|o’clock)\b", clause.text, re.I))
    def extract(self, clause, row):
        out = []
        for m in self.pattern.finditer(clause.text):
            if not is_name(m["subject"]) or not subject_is_clause_head(clause, m): continue
            day = m["time"].startswith("on ")
            q = (f"On which day did {m['subject']} {BASE[m['predicate']]}?" if day else
                 f"At what clock time did {m['subject']} {BASE[m['predicate']]}?")
            c = _make(row, clause, Relation.TEMPORAL_AT, m, asked_slot="time", answer_type="TIME",
                      category="TEMPORAL", v2_relation="TEMPORAL", question=q, slot_group="time",
                      extras={"time": m["time"], "temporal_relation": "AT_TIME",
                              "time_span": _span(row, clause, m, "time")})
            if c: out.append(_finalize(c))
        return out


class ActionV4(V4Extractor):
    name = "ACTION"
    pattern = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<predicate>opened|closed|found|gave|sent|wrote)\s+"
                         rf"(?P<object>(?:a|an|the)\s+[a-z]{{3,20}}(?:\s+[a-z]{{3,20}}){{0,2}})\s+"
                         rf"(?P<anchor>in|at|on|after|before)\s+(?P<context>[^,;.!?]{{5,50}})")
    def can_match(self, clause): return bool(re.search(r"\b(?:opened|closed|found|gave|sent|wrote)\b", clause.text, re.I))
    def extract(self, clause, row):
        out = []
        for m in self.pattern.finditer(clause.text):
            if not is_name(m["subject"]) or not subject_is_clause_head(clause, m): continue
            if not _surface_safe(m["context"]) or len(m["context"].split()) > 8: continue
            context = m["context"].strip().rstrip(".!")
            q = f"What did {m['subject']} {BASE[m['predicate']]} {m['anchor']} {context}?"
            c = _make(row, clause, Relation.ACTION, m, asked_slot="object", answer_type="PHRASE",
                      category="EVENT", v2_relation="ENTITY_ACTION", question=q, slot_group="object",
                      extras={"context": m["anchor"] + " " + context,
                              "context_span": [row["source_start_char"] + clause.start + m.start("anchor"),
                                               row["source_start_char"] + clause.start + m.end("context")]})
            if c: out.append(_finalize(c))
        return out


class AttributeV4(V4Extractor):
    name = "ATTRIBUTE"
    role = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<predicate>was|is)\s+"
                      rf"(?P<object>(?:a|an|the)\s+(?:{'|'.join(ROLE)}))\b")
    state = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<predicate>became)\s+"
                       rf"(?P<attribute>{'|'.join(STATE)})\b")
    def can_match(self, clause): return bool(re.search(r"\b(?:was|is|became)\b", clause.text))
    def extract(self, clause, row):
        out = []
        for m in self.role.finditer(clause.text):
            if not is_name(m["subject"]) or not subject_is_clause_head(clause, m): continue
            if m["object"].split()[-1] in KIN: continue  # relation extractor wins
            q = f"What profession or role did {m['subject']} hold?"
            c = _make(row, clause, Relation.ATTRIBUTE, m, asked_slot="object", answer_type="RELATION",
                      category="FACTUAL_DIRECT", v2_relation="ATTRIBUTE", question=q, slot_group="object",
                      extras={"attribute_kind": "ROLE"})
            if c: out.append(_finalize(c))
        for m in self.state.finditer(clause.text):
            if not is_name(m["subject"]) or not subject_is_clause_head(clause, m): continue
            if clause.text[m.end("attribute"):].lstrip().startswith(("than", "to", "of")): continue
            state = clause.text[m.start("predicate"):m.end("attribute")]
            q = f"What change in state did {m['subject']} undergo?"
            c = _make(row, clause, Relation.ATTRIBUTE, m, asked_slot="object", answer_type="PHRASE",
                      category="FACTUAL_DIRECT", v2_relation="ATTRIBUTE", question=q,
                      slot_group="attribute", extras={"object": state,
                      "object_span": [row["source_start_char"] + clause.start + m.start("predicate"),
                                      row["source_start_char"] + clause.start + m.end("attribute")],
                      "attribute_kind": "STATE_CHANGE"})
            if c:
                c["short_answer"] = state
                c["answer_surface"] = state
                c["answer_normalized"] = normalize(state)
                c["proposition"]["answer_span"] = c["proposition"]["object_span"]
                out.append(_finalize(c))
        return out


V4_EXTRACTORS = [InstructionV4(), RelationV4(), CauseV4(), MotivationV4(),
                 LocationV4(), TemporalV4(), ActionV4(), AttributeV4()]


def _quote_candidates(row):
    # Quote attribution is scanned over the chunk so a question mark inside a
    # quote cannot sever the following "said X" attribution.
    before = re.compile(rf"[“\"](?P<object>[^”\"]{{18,140}})[”\"]\s*,?\s*"
                        rf"(?P<predicate>said|asked|replied|answered)\s+(?P<subject>{NAME})")
    after = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<predicate>said|asked|replied|answered)\s*,?\s*"
                       rf"[“\"](?P<object>[^”\"]{{18,140}})[”\"]")
    out = []
    for pattern in (before, after):
        for global_match in pattern.finditer(row["text"]):
            clause_text = global_match.group()
            span = Span(clause_text, global_match.start(), global_match.end(),
                        global_match.start(), global_match.end())
            m = pattern.fullmatch(clause_text)
            if not m or not is_name(m["subject"]): continue
            quote = m["object"]
            if not 5 <= len(quote.split()) <= 20 or re.search(
                    r"\b(?:he|she|they|it|this|that|there|here)\b", quote, re.I):
                continue
            topics = [x.group() for x in re.finditer(r"\b(?:" + NAME + r")\b", quote)
                      if is_name(x.group()) and x.group() != m["subject"]]
            if not topics: continue
            topic = topics[0]
            question = (f"What question did {m['subject']} ask about {topic}?" if quote.rstrip().endswith("?") else
                        f"Which statement did {m['subject']} make about {topic}?")
            c = _make(row, span, Relation.STATEMENT, m, asked_slot="object", answer_type="PHRASE",
                      category="QUOTE_OR_PHRASE", v2_relation="QUOTE_OR_STATEMENT", question=question,
                      slot_group="object", extras={"speaker": m["subject"], "topic": topic})
            if c: out.append(_finalize(c))
    return out


def extract_chunk_v4(row):
    stats = Counter()
    seen, out = set(), []
    for candidate in _quote_candidates(row):
        fp = proposition_fingerprint(candidate)
        if fp not in seen:
            seen.add(fp); candidate["proposition_fingerprint"] = fp
            candidate["qa_fingerprint"] = qa_fingerprint(candidate); out.append(candidate)
            stats["matches"] += 1
    for sentence in segment_sentences(row["text"]):
        stats["sentences"] += 1
        for clause in segment_clauses(sentence):
            stats["clauses"] += 1
            for extractor in V4_EXTRACTORS:
                if extractor.can_match(clause): stats[f"cue_{extractor.name}"] += 1
            found = []
            for extractor in V4_EXTRACTORS:
                if extractor.can_match(clause):
                    found = extractor.extract(clause, row)
                    if found: break
            prior = v3_extract_from_clause(clause, row)
            for c in prior:
                c["extractor_version"] = ("v3_preserved" if c["extractor_confidence"] == "HIGH"
                                          else "v3_fallback")
                c["confidence_reasons"] = ([] if c["extractor_confidence"] == "HIGH"
                                           else ["NO_V4_EVIDENCE_CONTRACT"])
                c["training_value"] = training_value_of(c)
            for candidate in found + prior:
                fp = proposition_fingerprint(candidate)
                if fp in seen:
                    stats["duplicates_within_chunk"] += 1
                    continue
                seen.add(fp)
                candidate["proposition_fingerprint"] = fp
                candidate["qa_fingerprint"] = qa_fingerprint(candidate)
                out.append(candidate)
                stats["matches"] += 1
    return out, dict(stats)
