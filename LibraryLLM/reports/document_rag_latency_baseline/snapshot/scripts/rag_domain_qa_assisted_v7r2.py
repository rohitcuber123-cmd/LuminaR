"""V7R2 strict source-unit proposal, answer mapping, and judge contracts."""
from __future__ import annotations

import hashlib
import json
import re

from rag_domain_common import CATEGORIES
from rag_domain_qa_v2 import CAUSAL, LOCATION, META, TIME, answer_quality
from rag_domain_qa_assisted_v7 import BAD_ANSWER, BAD_QUESTION, GENERIC
from rag_domain_qa_source_units_v7r2 import reconstruct_evidence, resolve_answer

DIFFICULTIES = {"EASY", "MEDIUM", "HARD"}
GENERATOR_KEYS = {"question", "answer_text", "answer_unit_id", "evidence_unit_ids",
                  "category", "difficulty", "support_explanation"}
JUDGE_BOOLS = ("question_answered_by_passage", "answer_supported", "question_self_contained",
               "requires_outside_context", "wrong_semantic_role")


def strict_json_v7r2(raw, *, judge=False):
    try:
        obj = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(obj, dict): return None
    if judge:
        keys = {"label", *JUDGE_BOOLS, "reason", "supporting_unit_ids"}
        if (set(obj) != keys or not isinstance(obj["label"], str) or
                obj["label"] not in {"SUPPORTED", "UNSUPPORTED", "UNCERTAIN"}):
            return None
        if any(type(obj[k]) is not bool for k in JUDGE_BOOLS): return None
        if not isinstance(obj["reason"], str) or not isinstance(obj["supporting_unit_ids"], list):
            return None
        if any(not isinstance(v, str) for v in obj["supporting_unit_ids"]): return None
    else:
        if set(obj) != {"candidates"} or not isinstance(obj["candidates"], list) or len(obj["candidates"]) > 2:
            return None
        for c in obj["candidates"]:
            if not isinstance(c, dict) or set(c) != GENERATOR_KEYS:
                return None
            if any(not isinstance(c[k], str) for k in GENERATOR_KEYS - {"evidence_unit_ids"}):
                return None
            if not isinstance(c["evidence_unit_ids"], list) or any(
                    not isinstance(v, str) for v in c["evidence_unit_ids"]):
                return None
    return obj


def parse_judge_v7r2(raw, selected_ids):
    obj = strict_json_v7r2(raw, judge=True)
    if obj is None:
        return {"label": "UNCERTAIN", "reason": "INVALID_JUDGE_JSON", "supporting_unit_ids": []}
    if (len(obj["supporting_unit_ids"]) != len(set(obj["supporting_unit_ids"])) or
            any(x not in selected_ids for x in obj["supporting_unit_ids"])):
        return {"label": "UNCERTAIN", "reason": "JUDGE_SUPPORT_UNIT_OUTSIDE_EVIDENCE",
                "supporting_unit_ids": []}
    if obj["label"] == "SUPPORTED" and (not obj["supporting_unit_ids"] or
            not all(obj[k] for k in ("question_answered_by_passage", "answer_supported",
                                      "question_self_contained")) or
            obj["requires_outside_context"] or obj["wrong_semantic_role"]):
        return {"label": "UNCERTAIN", "reason": "JUDGE_SUPPORT_CONTRACT_FAILED",
                "supporting_unit_ids": []}
    return obj


def _question_reasons(question, answer, category, evidence, target_presentation):
    reasons = []
    if not question.endswith("?") or not 6 <= len(question.split()) <= 35:
        reasons.append("QUESTION_LENGTH_OR_FORMAT")
    if re.search(r"\b(?:this passage|the passage|the text|the title|the author|the chapter)\b",
                 question, re.I) or META.search(question):
        reasons.append("TRIVIAL_METADATA")
    if BAD_QUESTION.search(question): reasons.append("QUESTION_UNRESOLVED_REFERENT")
    if GENERIC.fullmatch(question): reasons.append("QUESTION_TOO_GENERIC")
    if BAD_ANSWER.fullmatch(answer): reasons.append("ANSWER_UNRESOLVED_REFERENT")
    if answer.casefold() in question.casefold(): reasons.append("QUESTION_CONTAINS_ANSWER")
    wh = question.split(" ", 1)[0].casefold() if question else ""
    typ = {"who": "PERSON", "where": "LOCATION", "when": "TIME", "why": "CAUSE"}.get(wh, "PHRASE")
    reasons.extend(answer_quality(answer, typ))
    starts = {"TEMPORAL": ("when ", "how long ", "what year ", "what time ", "on what day "),
              "LOCATION": ("where ", "in what place ", "at what place ", "which place "),
              "MOTIVATION": ("why ", "what motivated ", "what prompted ", "what desire "),
              "CAUSAL": ("why ", "what caused ", "what led ", "how did ")}
    if category in starts and not question.casefold().startswith(starts[category]):
        reasons.append("CATEGORY_QUESTION_MISMATCH")
    if category == "ENTITY_RELATION" and not re.search(
            r"\b(?:relationship|related|father|mother|sister|brother|daughter|son|wife|husband|"
            r"married|family|parent|child|relative|who was .+ to)\b", question, re.I):
        reasons.append("CATEGORY_QUESTION_MISMATCH")
    if wh == "where" and not (LOCATION.search(answer) or re.fullmatch(
            r"[A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,3}", answer)):
        reasons.append("ANSWER_TYPE_MISMATCH")
    if wh == "when" and not TIME.search(answer): reasons.append("ANSWER_TYPE_MISMATCH")
    if wh == "why" or category in {"CAUSAL", "MOTIVATION"}:
        if not CAUSAL.search(evidence): reasons.append("UNSUPPORTED_CAUSAL_OR_MOTIVATION")
    # An introduced proper name available only in the surrounding context
    # cannot rescue a target passage that never names that participant.
    skip = {"Who", "What", "Why", "When", "Where", "How", "Which", "Did", "Does", "Was", "Were",
            "The", "A", "An", "Mr", "Mrs", "Miss", "Dr", "Lord", "Lady"}
    for name in re.findall(r"\b[A-Z][a-z]{2,}\b", question):
        if name not in skip and not re.search(r"\b" + re.escape(name) + r"\b", target_presentation, re.I):
            reasons.append("CONTEXT_ONLY_NAMED_REFERENCE")
            break
    return sorted(set(reasons))


def candidate_record_v7r2(row, generated, *, view, units, context, context_start,
                          generator_model, source):
    reasons = []
    if generated["category"] not in CATEGORIES: reasons.append("INVALID_CATEGORY")
    if generated["difficulty"] not in DIFFICULTIES: reasons.append("INVALID_DIFFICULTY")
    if source[row["source_start_char"]:row["source_end_char"]] != row["text"]:
        reasons.append("SOURCE_MAPPING_FAILED")
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != row["source_sha256"]:
        reasons.append("SOURCE_HASH_INTEGRITY")
    if row["split"] != "TRAIN": reasons.append("NONTRAIN_AUTHORING_PROHIBITED")
    if not (0 <= context_start <= row["source_start_char"] and
            row["source_end_char"] <= context_start + len(context) <= len(source) and
            source[context_start:context_start + len(context)] == context):
        reasons.append("AUTHORING_CONTEXT_NOT_AUTHORITATIVE")
    if view.authoritative_text != row["text"] or view.source_hash != row["source_sha256"]:
        reasons.append("SOURCE_VIEW_INTEGRITY_FAILED")
    if reasons: return None, sorted(set(reasons))
    evidence, unit_reasons = reconstruct_evidence(view, units, generated["evidence_unit_ids"])
    reasons.extend(unit_reasons)
    if generated["answer_unit_id"] not in generated["evidence_unit_ids"]:
        reasons.append("ANSWER_UNIT_OUTSIDE_EVIDENCE")
    if reasons: return None, sorted(set(reasons))
    answer, answer_reasons = resolve_answer(view, units, generated["answer_unit_id"],
                                            generated["answer_text"], generated["evidence_unit_ids"])
    reasons.extend(answer_reasons)
    if reasons: return None, sorted(set(reasons))
    a, b = answer["answer_authoritative_start"], answer["answer_authoritative_end"]
    if not (evidence["evidence_start_in_passage"] <= a < b <= evidence["evidence_end_in_passage"]):
        return None, ["ANSWER_OUTSIDE_AUTHORITATIVE_EVIDENCE"]
    reasons.extend(_question_reasons(generated["question"].strip(),
                                     generated["answer_text"], generated["category"],
                                     evidence["evidence_quote_authoritative"], view.presentation_text))
    if reasons: return None, sorted(set(reasons))
    record = {"generation_version": "v7r2", "generation_method": "source_referenced_assisted",
              "generator_model": generator_model, "work_id": row["work_id"], "book_title": row["title"],
              "chapter": row["chapter"], "chunk_id": row["chunk_id"], "source_hash": row["source_sha256"],
              "split": row["split"], "positive_source_start": row["source_start_char"],
              "positive_source_end": row["source_end_char"], "positive_passage": row["text"],
              "presentation_passage": view.presentation_text, "source_units": units,
              "authoring_context_start": context_start,
              "authoring_context_end": context_start + len(context), "authoring_context": context,
              "question": generated["question"].strip(),
              "short_answer": answer["answer_authoritative_text"],
              "evidence_quote": evidence["evidence_quote_authoritative"],
              "answer_unit_id": generated["answer_unit_id"],
              "evidence_unit_ids": generated["evidence_unit_ids"],
              "category_proposed": generated["category"], "category_validated": generated["category"],
              "difficulty_proposed": generated["difficulty"],
              "generation_support_explanation": generated["support_explanation"],
              "automatic_checks": {"passed": True, "rejection_reasons": []},
              "semantic_audit": None, "same_model_generator_judge": True,
              "review_status": "GENERATED", "reviewer": None, "review_date": None,
              **evidence, **answer}
    return record, []
