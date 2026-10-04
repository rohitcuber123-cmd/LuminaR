"""Read-only, source-first inventory of every saved V5 detector cue."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re

from rag_domain_common import ROOT, SOURCE_MAP, TRAINING
from rag_domain_qa_v3 import NAME, segment_clauses, segment_sentences, is_name
from rag_domain_qa_v4 import V4_EXTRACTORS, KIN, MOTION, CAUSE_VERB

FROZEN = {
    "quality_gate": "reports/rag_domain_qa_v5_quality_gate.md",
    "probe_json": "reports/rag_domain_qa_v5_probe.json",
    "probe_md": "reports/rag_domain_qa_v5_probe.md",
    "audit_md": "reports/rag_domain_qa_v5_probe_audit.md",
    "ranges": "manifests/rag_domain_qa_v5_probe_ranges.json",
    "high_jsonl": "luminar/domain_qa_v5_probe_high.jsonl",
    "medium_jsonl": "luminar/domain_qa_v5_probe_medium.jsonl",
    "rejected_jsonl": "luminar/domain_qa_v5_probe_rejected.jsonl",
}
TRIGGER = {
    "ATTRIBUTE": r"\b(?:was|is|became)\b",
    "ENTITY_RELATION": r"\b(?:" + "|".join(re.escape(k) for k in KIN) + r")\b",
    "LOCATION": r"\b(?:" + "|".join(re.escape(k) for k in MOTION) + r")\b",
    "ACTION": r"\b(?:opened|closed|found|gave|sent|wrote)\b",
    "CAUSE": r"\bbecause\b",
    "MOTIVATION": r"\b(?:hoped|wanted)\s+to\b",
    "INSTRUCTION": r"\b(?:warned|advised|urged|requested)\b",
    "TEMPORAL": r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|noon|midnight|o'clock|o’clock)\b",
}
PRONOUN = re.compile(r"\b(?:he|she|they|it|I|we|you|him|her|them|my|your|his|their)\b", re.I)
SAFE_ACTION = re.compile(rf"\b(?P<subject>{NAME})\s+(?P<verb>opened|closed|found|gave|sent|wrote)\s+"
                         r"(?P<object>(?:a|an|the)\s+[a-z-]+(?:\s+[a-z-]+){0,3})\b")
SAFE_ATTRIBUTE = re.compile(rf"\b(?P<subject>{NAME})\s+was\s+(?P<complement>determined\s+to\s+[^,;.!?]{{8,80}})", re.I)

# Source-first corrections to diagnostic triage only. These IDs are frozen-probe
# row numbers, never candidate-generation exceptions or extractor rules.
AUDIT_OVERRIDES = {
    39: ("RELATION_ENDPOINT_MISSING", "EXPECTED_PRECISION_REJECTION", "FALSE_POSITIVE_CUE", "UNNAMED_FRIEND_MENTION", False),
    48: ("PARSER_REQUIRED", "EXPECTED_PRECISION_REJECTION", "AMBIGUOUS", "RELATIVE_CLAUSE_ANTECEDENT", False),
    57: ("PARSER_REQUIRED", "EXPECTED_PRECISION_REJECTION", "AMBIGUOUS", "INVERTED_COPULA", False),
    84: ("RELATION_ENDPOINT_MISSING", "EXPECTED_PRECISION_REJECTION", "FALSE_POSITIVE_CUE", "UNNAMED_FRIEND_MENTION", False),
    103: ("PARSER_REQUIRED", "EXPECTED_PRECISION_REJECTION", "AMBIGUOUS", "MULTIPLE_RELATIVE_CLAUSES", False),
    107: ("RELATION_ENDPOINT_MISSING", "REQUIRES_DISCOURSE_REASONING", "AMBIGUOUS", "PRONOUN_FRIEND_ENDPOINT", False),
    130: ("SUBJECT_ONLY_IN_PREVIOUS_SENTENCE", "REQUIRES_DISCOURSE_REASONING", "AMBIGUOUS", "SPEAKER_IDENTITY_OUTSIDE_CLAUSE", False),
    142: ("RELATION_ENDPOINT_MISSING", "EXPECTED_PRECISION_REJECTION", "AMBIGUOUS", "UNNAMED_POSSESSIVE_KIN", False),
}


def _trigger(family, clause):
    m = re.search(TRIGGER[family], clause)
    return (m.group(), [m.start(), m.end()]) if m else (None, None)


def _surface_fields(family, clause):
    names = [m.group() for m in re.finditer(r"\b(?:" + NAME + r")\b", clause)
             if is_name(m.group())]
    predicate = _trigger(family, clause)[0]
    locations = [m.group(1) for m in re.finditer(r"\b(?:to|from|into|in|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", clause)]
    times = [m.group() for m in re.finditer(r"\b(?:on\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)|"
             r"at\s+(?:noon|midnight|\d{1,2}\s+o['’]clock))\b", clause, re.I)]
    return {"candidate_participants": names, "candidate_predicate": predicate,
            "candidate_object": None, "candidate_location": locations,
            "candidate_time": times, "candidate_cause": None, "candidate_effect": None,
            "candidate_statement": None, "candidate_relation_phrase": predicate if family == "ENTITY_RELATION" else None}


def _diagnose(family, clause, fields):
    """Conservative triage. These are hypotheses for source inspection, not QA labels."""
    names = fields["candidate_participants"]
    pronoun = bool(PRONOUN.search(clause))
    if family == "ATTRIBUTE":
        if re.search(r"\b(?:there|it|this|that)\s+(?:was|is)\b", clause, re.I):
            return "FALSE_POSITIVE_CUE", "DETECTOR_TOO_BROAD", "FALSE_POSITIVE_CUE", "GENERIC_OR_DEICTIC_COPULA", False
        if SAFE_ATTRIBUTE.search(clause):
            return "ATTRIBUTE_COMPLEMENT_UNSAFE", "EXTRACTOR_TOO_NARROW_BUT_FIXABLE", "TRUE_STRUCTURAL_OPPORTUNITY", "NAMED_PERSON_COMPLEX_ATTRIBUTE", True
        if not names and pronoun:
            return "SUBJECT_PRONOUN_UNRESOLVED", "REQUIRES_DISCOURSE_REASONING", "AMBIGUOUS", "PRONOUN_COPULA", False
        if re.search(r"\b(?:was|is)\s+(?:very|so|quite|a|an|the)\b", clause, re.I):
            return "ATTRIBUTE_COMPLEMENT_UNSAFE", "EXPECTED_PRECISION_REJECTION", "AMBIGUOUS", "NONPERSON_OR_VAGUE_ATTRIBUTE", False
        return "ATTRIBUTE_COMPLEMENT_UNSAFE", "DETECTOR_TOO_BROAD", "FALSE_POSITIVE_CUE", "NON_CANONICAL_COPULA", False
    if family == "ENTITY_RELATION":
        if len(names) < 2:
            return "RELATION_ENDPOINT_MISSING", "EXPECTED_PRECISION_REJECTION", "AMBIGUOUS", "KINSHIP_MENTION_WITHOUT_TWO_ENDPOINTS", False
        if re.search(r"\b(?:my|your|his|her|their)\s+(?:" + "|".join(KIN) + r")\b", clause, re.I):
            return "RELATION_ENDPOINT_MISSING", "REQUIRES_DISCOURSE_REASONING", "AMBIGUOUS", "POSSESSIVE_PRONOUN_RELATION", False
        return "APPOSITIVE_STRUCTURE_UNSUPPORTED", "EXTRACTOR_TOO_NARROW_BUT_FIXABLE", "AMBIGUOUS", "NON_CANONICAL_NAMED_RELATION", False
    if family == "LOCATION":
        if re.search(r"\b(?:went on|went echoing|came feeling|went to getting|came out by)\b", clause, re.I):
            return "FALSE_POSITIVE_CUE", "DETECTOR_TOO_BROAD", "FALSE_POSITIVE_CUE", "MOTION_IDIOM_OR_METAPHOR", False
        if not fields["candidate_location"]:
            return "LOCATION_DESTINATION_MISSING", "DETECTOR_TOO_BROAD", "FALSE_POSITIVE_CUE", "MOTION_WITHOUT_NAMED_DESTINATION", False
        if not names or re.search(r"\b(?:he|she|they|we|I|you)\s+(?:" + "|".join(MOTION) + r")\b", clause, re.I):
            return "SUBJECT_PRONOUN_UNRESOLVED", "REQUIRES_DISCOURSE_REASONING", "AMBIGUOUS", "PRONOUN_MOTION_LOCATION", False
        return "OBJECT_BOUNDARY_AMBIGUOUS", "EXPECTED_PRECISION_REJECTION", "AMBIGUOUS", "COMPLEX_MOTION_LOCATION", False
    if family == "ACTION":
        match = SAFE_ACTION.search(clause)
        if match and is_name(match["subject"]):
            fields["candidate_object"] = match["object"]
            if re.search(r"\b(?:and|but|then|yet)\s+(?:\w+\s+){0,2}(?:opened|closed|found|gave|sent|wrote|read|destroyed|walked)\b", clause[match.end():], re.I):
                return "ACTION_CONTEXT_AMBIGUOUS", "EXPECTED_PRECISION_REJECTION", "AMBIGUOUS", "COORDINATED_NAMED_ACTION", False
            return "ACTION_CONTEXT_AMBIGUOUS", "EXTRACTOR_TOO_NARROW_BUT_FIXABLE", "TRUE_STRUCTURAL_OPPORTUNITY", "NAMED_DIRECT_OBJECT_ACTION", True
        if not names or pronoun:
            return "SUBJECT_PRONOUN_UNRESOLVED", "REQUIRES_DISCOURSE_REASONING", "AMBIGUOUS", "PRONOUN_ACTION", False
        return "OBJECT_BOUNDARY_AMBIGUOUS", "EXPECTED_PRECISION_REJECTION", "AMBIGUOUS", "ACTION_WITH_NONCANONICAL_OBJECT", False
    if family == "CAUSE":
        split = re.split(r"\bbecause\b", clause, maxsplit=1, flags=re.I)
        if len(split) == 2:
            fields["candidate_effect"] = split[0].strip()
            fields["candidate_cause"] = split[1].strip()
        if pronoun:
            return "CAUSE_EFFECT_SUBJECT_UNRESOLVED", "REQUIRES_DISCOURSE_REASONING", "AMBIGUOUS", "PRONOUN_BECAUSE_CLAUSE", False
        return "CAUSE_MARKER_FOUND_BUT_SIDE_BOUNDARY_UNCLEAR", "EXPECTED_PRECISION_REJECTION", "AMBIGUOUS", "NONCANONICAL_BECAUSE_CLAUSE", False
    if family == "MOTIVATION":
        return "MOTIVATION_VERB_FOUND_BUT_ACTOR_UNRESOLVED", "REQUIRES_DISCOURSE_REASONING", "AMBIGUOUS", "PRONOUN_MOTIVATION", False
    return "OTHER", "EXPECTED_PRECISION_REJECTION", "AMBIGUOUS", "OTHER", False


def build_inventory():
    hashes = {key: hashlib.sha256((TRAINING / path).read_bytes()).hexdigest()
              for key, path in FROZEN.items()}
    probe = json.loads((TRAINING / FROZEN["probe_json"]).read_text(encoding="utf-8"))
    if probe["stats"]["can_match_cues"] != 158 or probe["stats"]["relation_matches"] != 0:
        raise RuntimeError("Frozen V5 probe is not the expected zero-yield probe")
    mapping = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    sources = {case["work_id"]: (ROOT / mapping[case["work_id"]]["source_file"]).read_text(encoding="utf-8")
               for case in probe["cases"]}
    manifest = json.loads((TRAINING / FROZEN["ranges"]).read_text(encoding="utf-8"))
    range_by_chunk = {x["chunk_id"]: x for x in manifest["source_ranges"]}
    cues = []
    for case in probe["cases"]:
        work, start, end = case["work_id"], *case["range"]
        source = sources[work]
        saved_range = range_by_chunk[case["chunk_id"]]
        if source[start:end] != case["text"] or saved_range["source_start"] != start or (
                saved_range["source_end"] != end or hashlib.sha256(source.encode()).hexdigest() != saved_range["source_hash"]):
            raise RuntimeError(f"Frozen source mapping mismatch: {case['chunk_id']}")
        for sentence in segment_sentences(case["text"]):
            for clause in segment_clauses(sentence):
                for extractor in V4_EXTRACTORS:
                    if not extractor.can_match(clause): continue
                    family = extractor.name
                    trigger, relative = _trigger(family, clause.text)
                    fields = _surface_fields(family, clause.text)
                    reason, classification, opportunity, pattern, safe = _diagnose(family, clause.text, fields)
                    index = len(cues)
                    if index in AUDIT_OVERRIDES:
                        reason, classification, opportunity, pattern, safe = AUDIT_OVERRIDES[index]
                    cue = {"cue_id": f"V6C-{index:03d}", "work_id": work,
                           "book_title": case["title"], "chapter": case["chapter"],
                           "chunk_id": case["chunk_id"], "source_start": start, "source_end": end,
                           "sentence_start": start + sentence.start, "sentence_end": start + sentence.end,
                           "clause_start": start + clause.start, "clause_end": start + clause.end,
                           "sentence_text": sentence.text, "clause_text": clause.text,
                           "detector_family": family, "detector_reason": f"LEXICAL_CUE_{family}",
                           "lexical_trigger": trigger, "trigger_span": (
                               [start + clause.start + relative[0], start + clause.start + relative[1]] if relative else None),
                           **fields, "extractor_attempted": [f"V4_{family}", "V3_FALLBACK"],
                           "extractor_result": "NO_MATCH_IN_FROZEN_V5_PROBE",
                           "no_match_reasons": [reason], "consistency_class": classification,
                           "opportunity_class": opportunity, "structural_pattern": pattern,
                           "safe_v6_candidate": safe, "source_context": sentence.text,
                           "source_inspection_status": "INSPECTED_SOURCE_FIRST"}
                    if source[cue["clause_start"]:cue["clause_end"]] != cue["clause_text"] or (
                            source[cue["sentence_start"]:cue["sentence_end"]] != cue["sentence_text"]):
                        raise RuntimeError("Diagnostic offsets drifted")
                    cues.append(cue)
    if len(cues) != 158: raise RuntimeError(f"Expected 158 cues, got {len(cues)}")
    return hashes, cues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe-existing", action="store_true")
    ap.add_argument("--version", default="v6")
    args = ap.parse_args()
    if not args.probe_existing or args.version != "v6":
        raise ValueError("Read-only V6 analysis requires --probe-existing --version v6")
    hashes, cues = build_inventory()
    report = {"result_label": "DIAGNOSTIC ONLY — NO QA GENERATED",
              "frozen_v5_sha256": hashes, "cue_count": len(cues), "cues": cues}
    (TRAINING / "reports" / "rag_domain_qa_v6_v5_cue_inventory.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# V6 source-first inventory of all saved V5 cues", "", "DIAGNOSTIC ONLY — NO QA GENERATED", "",
             f"Cues: {len(cues)}; source/hash/offset failures: 0.", ""]
    for c in cues:
        lines += [f"## {c['cue_id']} — {c['detector_family']} — {c['book_title']}", "",
                  f"- Source offsets: sentence {c['sentence_start']}–{c['sentence_end']}; clause {c['clause_start']}–{c['clause_end']}",
                  f"- Trigger: `{c['lexical_trigger']}`; detector: `{c['detector_reason']}`; extractor: `{c['extractor_result']}`",
                  f"- No-match: `{', '.join(c['no_match_reasons'])}`; classification: `{c['consistency_class']}`; opportunity: `{c['opportunity_class']}`",
                  f"- Candidate names (unverified): {c['candidate_participants']}",
                  f"- Clause: {c['clause_text']}", f"- Sentence context: {c['sentence_text']}", ""]
    (TRAINING / "reports" / "rag_domain_qa_v6_v5_cue_inventory.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"cues": len(cues), "families": dict(Counter(c["detector_family"] for c in cues)),
                      "classes": dict(Counter(c["consistency_class"] for c in cues))}, indent=2))


if __name__ == "__main__": main()
