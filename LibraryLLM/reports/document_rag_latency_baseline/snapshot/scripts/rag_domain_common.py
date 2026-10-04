"""Shared fail-closed controls for isolated LuminaR domain QA preparation."""
from __future__ import annotations

from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "datasets" / "training"
CONTROL = ROOT / "datasets" / "rag_experiments" / "chunking_v1" / "tokens_220"
LABELS = ROOT / "rag" / "evaluation" / "rag_retrieval_eval_v1.json"
SOURCE_MAP = ROOT / "rag" / "evaluation" / "source_map_v1.json"
CATEGORIES = ("FACTUAL_DIRECT", "ENTITY_RELATION", "EVENT", "MOTIVATION", "CAUSAL",
              "LOCATION", "TEMPORAL", "SEMANTIC_PARAPHRASE", "QUOTE_OR_PHRASE")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def controls():
    saved = json.loads((TRAINING / "manifests" / "control_v1.json").read_text(encoding="utf-8"))
    checks = ((CONTROL / "chunks.parquet", "chunks_parquet_sha256"),
              (CONTROL / "mapping.json", "mapping_sha256"),
              (CONTROL / "manifest.json", "manifest_sha256"),
              (LABELS, "evaluation_labels_sha256"), (SOURCE_MAP, "source_map_sha256"))
    if any(sha(path) != saved[key] for path, key in checks):
        raise RuntimeError("Frozen corpus, mapping, manifest, source map, or labels changed")
    split = json.loads((TRAINING / "reports" / "rag_training_decontamination_v1.json").read_text(encoding="utf-8"))
    labels = json.loads(LABELS.read_text(encoding="utf-8"))["questions"]
    test = {q["work_id"] for q in labels if q["split"] == "TEST"}
    if test != set(split["protected_test_work_ids"]):
        raise RuntimeError("TEST split drifted")
    train = set(split["train_work_ids"])
    validation = set(split["validation_work_ids"])
    if train & validation or train & test or validation & test:
        raise RuntimeError("Book-level leakage")
    return saved, split, labels


def classification(row):
    text = row["text"].strip()
    tokens = row["token_count"]
    if "\ufffd" in text or text.count("<") > 5 or sum(ch.isalpha() for ch in text) < .55 * len(text):
        return "MALFORMED"
    if tokens < 70 or len(text) < 280:
        return "TOO_SHORT"
    lower = text.casefold()
    if any(term in lower for term in ("project gutenberg", "copyright", "all rights reserved",
                                      "license agreement", "transcriber's note")):
        return "BOILERPLATE"
    if "contents" in lower[:250] and (text.count("\n") > 8 or lower.startswith("contents")):
        return "BOILERPLATE"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > 7 and sum(len(line) < 55 for line in lines) > .7 * len(lines):
        return "WEAK_CONTEXT"
    if len(text.split()) < 65:
        return "TOO_SHORT"
    if re.match(r"^(?:chapter|part|book|contents)\s+[^.!?]{0,100}$", text, re.I):
        return "HEADER_ONLY"
    if text[:1] in ('“', '"', "'") and len(re.findall(r"[.!?]", text)) < 3:
        return "DIALOGUE_FRAGMENT_WITHOUT_CONTEXT"
    if len(re.findall(r"[.!?]", text)) < 2:
        return "WEAK_CONTEXT"
    if len(re.findall(r"\b[A-Z][a-z]{2,}\b", text)) < 2:
        return "TOO_AMBIGUOUS"
    return "GOOD_FOR_QA"


def passage_pool(classifier=classification):
    saved, split, labels = controls()
    train, validation, test = (set(split[f"{key}_work_ids"]) for key in ("train", "validation", "protected_test"))
    accepted = {}
    for q in labels:
        accepted.setdefault(q["work_id"], []).extend(p for p in q["accepted_passages"]
                                                       if p["relevance_grade"] == 2)
    source_map = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    sources = {}
    for wid in train | validation:
        item = source_map[wid]
        path = ROOT / item["source_file"]
        source_text = path.read_text(encoding="utf-8")
        if hashlib.sha256(source_text.encode("utf-8")).hexdigest() != saved["source_hashes"][wid]:
            raise RuntimeError(f"Source hash mismatch: {wid}")
        sources[wid] = source_text
    rows = pq.read_table(CONTROL / "chunks.parquet").to_pylist()
    eligible, counts = [], {}
    for row in rows:
        wid = row["work_id"]
        if wid in test:
            status = "PROTECTED_TEST"
        elif wid not in train | validation:
            status = "UNASSIGNED"
        elif row["source_sha256"] != saved["source_hashes"][wid] or sources[wid][row["source_start_char"]:row["source_end_char"]] != row["text"]:
            status = "MALFORMED"
        elif any(row["source_start_char"] < p["source_end"] and p["source_start"] < row["source_end_char"]
                 for p in accepted.get(wid, [])):
            status = "EVALUATION_SPAN_OVERLAP"
        else:
            status = classifier(row)
        counts[status] = counts.get(status, 0) + 1
        if status == "GOOD_FOR_QA":
            row["split"] = "TRAIN" if wid in train else "VALIDATION"
            eligible.append(row)
    return eligible, counts


def normalized_query(text):
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def validate_candidate(row, generated, eval_queries):
    reasons = []
    if not isinstance(generated, dict):
        return None, ["INVALID_JSON_OBJECT"]
    question = str(generated.get("question", "")).strip()
    answer = str(generated.get("short_answer", "")).strip()
    evidence = str(generated.get("evidence_quote", "")).strip()
    category = str(generated.get("category", "")).strip().upper()
    difficulty = str(generated.get("difficulty", "")).strip().upper()
    if not question or not answer or not evidence:
        reasons.append("MISSING_QUESTION_ANSWER_OR_EVIDENCE")
    words = question.split()
    if not question.endswith("?") or not 6 <= len(words) <= 35:
        reasons.append("QUESTION_LENGTH_OR_FORMAT")
    if re.search(r"\b(?:this passage|the passage|the text|the title|the author|the chapter)\b", question, re.I):
        reasons.append("GENERIC_METADATA_QUESTION")
    if re.match(r"^(?:who|what|why|when|where|how)\s+(?:is|was|are|were|did|does)\s+(?:he|she|it|they|this|that)\b", question, re.I):
        reasons.append("UNRESOLVED_PRONOUN")
    if category not in CATEGORIES:
        reasons.append("INVALID_CATEGORY")
    category_starts = {
        "TEMPORAL": ("when ", "how long ", "what year ", "what time ", "on what day "),
        "LOCATION": ("where ", "in what place ", "at what place ", "which place ", "what location "),
        "MOTIVATION": ("why ", "what motivated ", "what prompted ", "what desire "),
        "CAUSAL": ("why ", "what caused ", "what led ", "how did "),
    }
    if category in category_starts and not question.casefold().startswith(category_starts[category]):
        reasons.append("CATEGORY_QUESTION_MISMATCH")
    if category == "ENTITY_RELATION" and not re.search(
        r"\b(?:relationship|related|father|mother|sister|brother|daughter|son|wife|husband|friend|"
        r"married|family|parent|child|relative|who was .+ to)\b", question, re.I):
        reasons.append("CATEGORY_QUESTION_MISMATCH")
    if difficulty not in ("EASY", "MEDIUM", "HARD"):
        reasons.append("INVALID_DIFFICULTY")
    if len(answer.split()) > 18:
        reasons.append("ANSWER_TOO_LONG")
    if evidence and row["text"].count(evidence) != 1:
        reasons.append("EVIDENCE_NOT_UNIQUE_VERBATIM")
    compact_answer = re.sub(r"\s+", " ", answer).casefold()
    compact_evidence = re.sub(r"\s+", " ", evidence).casefold()
    if answer and evidence and compact_answer not in compact_evidence:
        reasons.append("ANSWER_NOT_IN_EVIDENCE")
    if row["token_count"] > 220:
        reasons.append("POSITIVE_TOO_LONG")
    norm = normalized_query(question)
    if any(norm == normalized_query(q) or SequenceMatcher(None, norm, normalized_query(q)).ratio() >= .82
           for q in eval_queries):
        reasons.append("EVALUATION_QUERY_DUPLICATE_OR_NEAR")
    if reasons:
        return None, reasons
    offset = row["text"].index(evidence)
    candidate = {
        "query": question, "short_answer": answer, "positive_passage": row["text"],
        "evidence_text": evidence, "evidence_start": row["source_start_char"] + offset,
        "evidence_end": row["source_start_char"] + offset + len(evidence),
        "work_id": row["work_id"], "book_title": row["title"], "chapter": row["chapter"],
        "source_start": row["source_start_char"], "source_end": row["source_end_char"],
        "source_hash": row["source_sha256"], "question_category": category,
        "difficulty": difficulty, "review_status": "AUTO_VALIDATED",
        "generation_method": "Qwen2.5-3B-Instruct local structured source prompt",
        "validation_notes": "Exact evidence and answer containment verified; semantic support awaits review.",
        "hard_negatives": [], "chunk_id": row["chunk_id"], "split": row["split"]}
    return candidate, []
