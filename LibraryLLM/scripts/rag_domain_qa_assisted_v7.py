"""Separate assisted-QA schema and fail-closed checks; never confers human review."""
from __future__ import annotations

import hashlib
import json
import re

from rag_domain_common import CATEGORIES, normalized_query, validate_candidate
from rag_domain_qa_v2 import CAUSAL, LOCATION, META, TIME, UNRESOLVED, answer_quality, near_duplicate

DIFFICULTIES = {"EASY", "MEDIUM", "HARD"}
STATUS = {"GENERATED", "FORMAT_FAILED", "GROUNDING_FAILED", "AUTO_REJECTED",
          "AUTO_CHECKED", "REVIEWED", "REJECTED", "EDITED"}
JUDGE_LABELS = {"SUPPORTED", "UNSUPPORTED", "UNCERTAIN"}
JUDGE_BOOLS = ("question_answered_by_passage", "answer_supported", "question_self_contained",
               "requires_outside_context", "wrong_semantic_role")
BAD_QUESTION = re.compile(r"\b(?:he|she|they|it|this|that|the man|the woman|the speaker|"
                          r"the narrator|the news|the matter|the plan|the purpose)\b", re.I)
BAD_ANSWER = re.compile(r"^(?:he|she|they|it|this|that|someone|something|there|him|her|them)$", re.I)
GENERIC = re.compile(r"^(?:what happened|why|what did (?:he|she|they|it) (?:do|say))\??$", re.I)


def strict_json(raw, *, judge=False):
    """Parse only a complete JSON object; never salvage prose or markdown."""
    try: obj = json.loads(raw)
    except (TypeError, json.JSONDecodeError): return None
    if not isinstance(obj, dict): return None
    if judge:
        if set(obj) != {"label", *JUDGE_BOOLS, "reason", "supporting_quote"}:
            return None
        if obj["label"] not in JUDGE_LABELS or not all(type(obj.get(k)) is bool for k in JUDGE_BOOLS):
            return None
        if not isinstance(obj["reason"], str) or not isinstance(obj["supporting_quote"], str):
            return None
    else:
        if set(obj) != {"candidates"} or not isinstance(obj["candidates"], list) or len(obj["candidates"]) > 2:
            return None
        keys = {"question", "short_answer", "evidence_quote", "category", "difficulty", "support_explanation"}
        if any(not isinstance(c, dict) or set(c) != keys or
               any(not isinstance(c[k], str) for k in keys) for c in obj["candidates"]):
            return None
    return obj


def candidate_record(row, generated, *, context, context_start, generator_model, source):
    """Ground a model proposal strictly in the target positive chunk."""
    question = generated["question"].strip()
    answer = generated["short_answer"].strip()
    evidence = generated["evidence_quote"]
    category = generated["category"].strip().upper()
    difficulty = generated["difficulty"].strip().upper()
    reasons = []
    if category not in CATEGORIES: reasons.append("INVALID_CATEGORY")
    if difficulty not in DIFFICULTIES: reasons.append("INVALID_DIFFICULTY")
    if source[row["source_start_char"]:row["source_end_char"]] != row["text"]:
        reasons.append("SOURCE_MAPPING_FAILED")
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != row["source_sha256"]:
        reasons.append("SOURCE_HASH_INTEGRITY")
    if row["split"] != "TRAIN": reasons.append("NONTRAIN_AUTHORING_PROHIBITED")
    if not evidence or row["text"].count(evidence) != 1:
        reasons.append("EVIDENCE_NOT_UNIQUE_EXACT_IN_POSITIVE")
    if not answer or answer not in evidence:
        reasons.append("ANSWER_NOT_EXACT_IN_EVIDENCE")
    if not (0 <= context_start <= row["source_start_char"] and
            row["source_end_char"] <= context_start + len(context) <= len(source) and
            source[context_start:context_start + len(context)] == context):
        reasons.append("AUTHORING_CONTEXT_NOT_AUTHORITATIVE")
    if reasons:
        return None, sorted(set(reasons))
    offset = row["text"].index(evidence)
    abs_start = row["source_start_char"] + offset
    base, old_reasons = validate_candidate(row, {"question": question, "short_answer": answer,
                                              "evidence_quote": evidence, "category": category,
                                              "difficulty": difficulty}, [])
    # validate_candidate's source-first checks are reused; evaluation-query
    # similarity is checked separately with the authoritative list.
    reasons.extend(old_reasons)
    if BAD_QUESTION.search(question): reasons.append("QUESTION_UNRESOLVED_REFERENT")
    if GENERIC.fullmatch(question): reasons.append("QUESTION_TOO_GENERIC")
    if BAD_ANSWER.fullmatch(answer): reasons.append("ANSWER_UNRESOLVED_REFERENT")
    if META.search(question): reasons.append("TRIVIAL_METADATA")
    if answer.casefold() in question.casefold(): reasons.append("QUESTION_CONTAINS_ANSWER")
    wh = question.split(" ", 1)[0].casefold() if question else ""
    typ = {"who": "PERSON", "where": "LOCATION", "when": "TIME", "why": "CAUSE"}.get(wh, "PHRASE")
    reasons.extend(answer_quality(answer, typ))
    if wh == "where" and not (LOCATION.search(answer) or re.fullmatch(
            r"[A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,3}", answer)):
        reasons.append("ANSWER_TYPE_MISMATCH")
    if wh == "when" and not TIME.search(answer): reasons.append("ANSWER_TYPE_MISMATCH")
    if wh == "why" or category in {"CAUSAL", "MOTIVATION"}:
        if not CAUSAL.search(evidence): reasons.append("UNSUPPORTED_CAUSAL_OR_MOTIVATION")
    if reasons: return None, sorted(set(reasons))
    return {"generation_version": "v7", "generation_method": "source_first_assisted",
            "generator_model": generator_model, "work_id": row["work_id"],
            "book_title": row["title"], "chapter": row["chapter"], "chunk_id": row["chunk_id"],
            "source_hash": row["source_sha256"], "split": row["split"],
            "positive_source_start": row["source_start_char"],
            "positive_source_end": row["source_end_char"], "positive_passage": row["text"],
            "authoring_context_start": context_start,
            "authoring_context_end": context_start + len(context), "authoring_context": context,
            "question": question, "short_answer": answer, "evidence_quote": evidence,
            "evidence_start_in_passage": offset, "evidence_end_in_passage": offset + len(evidence),
            "absolute_evidence_start": abs_start, "absolute_evidence_end": abs_start + len(evidence),
            "category_proposed": category, "category_validated": category,
            "difficulty_proposed": difficulty,
            "generation_support_explanation": generated["support_explanation"],
            "automatic_checks": {"passed": True, "rejection_reasons": []},
            "semantic_audit": None, "review_status": "GENERATED",
            "reviewer": None, "review_date": None}, []


def decontamination_reasons(candidate, eval_queries, seen_questions, seen_facts):
    reasons = []
    q = candidate["question"]
    if any(near_duplicate(q, old) for old in eval_queries):
        reasons.append("EVALUATION_QUERY_DUPLICATE_OR_NEAR")
    if any(near_duplicate(q, old) for old in seen_questions):
        reasons.append("DUPLICATE_QUESTION")
    fact = (candidate["work_id"], candidate["absolute_evidence_start"],
            candidate["absolute_evidence_end"], candidate["short_answer"].casefold())
    if fact in seen_facts: reasons.append("DUPLICATE_SOURCE_FACT")
    return reasons, fact


def parse_judge(raw, evidence):
    obj = strict_json(raw, judge=True)
    if obj is None: return {"label": "UNCERTAIN", "reason": "INVALID_JUDGE_JSON", "supporting_quote": ""}
    if obj["supporting_quote"] and obj["supporting_quote"] not in evidence:
        return {"label": "UNCERTAIN", "reason": "JUDGE_QUOTE_NOT_IN_EVIDENCE", "supporting_quote": ""}
    if obj["label"] == "SUPPORTED" and (not all(obj[k] for k in
            ("question_answered_by_passage", "answer_supported", "question_self_contained")) or
            obj["requires_outside_context"] or obj["wrong_semantic_role"] or not obj["supporting_quote"]):
        return {"label": "UNCERTAIN", "reason": "JUDGE_SUPPORT_CONTRACT_FAILED", "supporting_quote": ""}
    return obj
