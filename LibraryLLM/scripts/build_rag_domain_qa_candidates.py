"""Generate source-anchored domain QA candidates; never mark them reviewed."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import random
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from probe_qwen_domain_qa import evidence_sentence, parse_json
from rag_domain_common import TRAINING, controls, normalized_query, passage_pool, validate_candidate

ATTEMPTS = TRAINING / "luminar" / "domain_qa_attempts_v1.jsonl"
CANDIDATES = TRAINING / "luminar" / "domain_qa_candidates_v1.jsonl"
REPORT = TRAINING / "reports" / "rag_domain_qa_generation_v1.json"

TARGETS = {"FACTUAL_DIRECT": 36, "ENTITY_RELATION": 30, "EVENT": 30,
           "MOTIVATION": 25, "CAUSAL": 25, "LOCATION": 15,
           "TEMPORAL": 15, "SEMANTIC_PARAPHRASE": 20, "QUOTE_OR_PHRASE": 4}
PATTERNS = {
    "ENTITY_RELATION": r"\b(?:father|mother|sister|brother|daughter|son|wife|husband|friend|married|family|parent|child|relative)\b",
    "MOTIVATION": r"\b(?:wanted|wished|desired|hoped|decided|refused|intended|determined|ambition|fear|purpose)\b",
    "CAUSAL": r"\b(?:because|therefore|hence|consequently|caused|owing to|as a result|so that|for this reason)\b",
    "LOCATION": r"\b(?:in|at|near|beside|outside|inside|across|toward|from)\b",
    "TEMPORAL": r"\b(?:when|after|before|morning|night|evening|day|year|hour|week|month|later|earlier)\b",
    "QUOTE_OR_PHRASE": r"[“\"]",
}


def source_options(rows):
    rng = random.Random(42)
    base = []
    for row in rows:
        if row["split"] != "TRAIN":
            continue
        evidence = evidence_sentence(row["text"])
        if evidence is not None:
            base.append((row, evidence))
    rng.shuffle(base)
    options = {}
    for category in TARGETS:
        expression = PATTERNS.get(category)
        options[category] = [(row, evidence) for row, evidence in base
                             if expression is None or re.search(expression, evidence, re.I)]
    return options


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=200)
    parser.add_argument("--max-attempts", type=int, default=500)
    args = parser.parse_args()
    if args.target < 1 or args.target > 500 or args.max_attempts < args.target or args.max_attempts > 2000:
        raise ValueError("Target/attempt limits outside the bounded pilot range")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    rows, quality = passage_pool()
    _, split, labels = controls()
    eval_queries = [q["question"] for q in labels]
    options = source_options(rows)
    ATTEMPTS.parent.mkdir(parents=True, exist_ok=True)
    attempts = [json.loads(line) for line in ATTEMPTS.read_text(encoding="utf-8").splitlines() if line.strip()] if ATTEMPTS.exists() else []
    candidates = [json.loads(line) for line in CANDIDATES.read_text(encoding="utf-8").splitlines() if line.strip()] if CANDIDATES.exists() else []
    used = {(a["chunk_id"], a["category"]) for a in attempts}
    used_chunks = {a["chunk_id"] for a in attempts}
    counts = Counter(c["question_category"] for c in candidates)
    category_attempts = Counter(a["category"] for a in attempts)
    seen_queries = {normalized_query(c["query"]) for c in candidates}
    cursor = {c: 0 for c in TARGETS}
    snapshots = sorted((Path.home() / ".cache" / "huggingface" / "hub" /
                        "models--Qwen--Qwen2.5-3B-Instruct" / "snapshots").glob("*"))
    if not snapshots:
        raise RuntimeError("Locally cached Qwen2.5-3B-Instruct is unavailable")
    tokenizer = AutoTokenizer.from_pretrained(str(snapshots[-1]), local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(str(snapshots[-1]), dtype=torch.float16,
                                                 device_map="cuda", low_cpu_mem_usage=True,
                                                 local_files_only=True, attn_implementation="sdpa")
    system = ("Create one source-grounded literary retrieval question. Return ONLY a JSON object with keys "
              "question, short_answer, difficulty. The short_answer MUST be an exact contiguous substring "
              "of the EVIDENCE SENTENCE, copying spelling and punctuation. The question must be specific, "
              "self-contained, and accurately match the requested category. Use a named person or event when "
              "available. Do not ask about passage metadata, titles, or external facts. If the category cannot "
              "be answered from the sentence, return {\"skip_reason\":\"unsupported category\"}.")
    new_attempts = 0
    while len(candidates) < args.target and len(attempts) < args.max_attempts:
        active = [c for c in TARGETS if category_attempts[c] < TARGETS[c] * 5
                  and counts[c] < TARGETS[c] * args.target / sum(TARGETS.values())]
        if not active:
            break
        category = min(active, key=lambda c: (counts[c] / TARGETS[c], category_attempts[c] / TARGETS[c], c))
        pool = options[category]
        while cursor[category] < len(pool) and pool[cursor[category]][0]["chunk_id"] in used_chunks:
            cursor[category] += 1
        if cursor[category] >= len(pool):
            category_attempts[category] = TARGETS[category] * 5
            continue
        row, evidence = pool[cursor[category]]
        cursor[category] += 1
        used.add((row["chunk_id"], category))
        used_chunks.add(row["chunk_id"])
        prompt = f"Requested category: {category}\nEVIDENCE SENTENCE:\n{evidence}"
        encoded = tokenizer.apply_chat_template([{"role": "system", "content": system},
                                                 {"role": "user", "content": prompt}],
                                                tokenize=True, add_generation_prompt=True,
                                                return_tensors="pt")
        input_ids = (encoded["input_ids"] if hasattr(encoded, "keys") else encoded).to(model.device)
        with torch.inference_mode():
            generated = model.generate(input_ids, max_new_tokens=110, do_sample=False,
                                       pad_token_id=tokenizer.eos_token_id)
        raw = tokenizer.decode(generated[0][input_ids.shape[1]:], skip_special_tokens=True).strip()
        obj = parse_json(raw)
        if isinstance(obj, dict) and "skip_reason" not in obj:
            obj = {**obj, "evidence_quote": evidence, "category": category}
        candidate, reasons = validate_candidate(row, obj, eval_queries)
        if candidate is not None:
            nq = normalized_query(candidate["query"])
            if nq in seen_queries:
                reasons = ["DUPLICATE_DOMAIN_QUERY"]
                candidate = None
            else:
                seen_queries.add(nq)
                candidate["candidate_id"] = f"DQ{len(candidates) + 1:05d}"
                candidate["token_count"] = row["token_count"]
                candidate["validation_notes"] += " Category, referents, and answerability need human review."
                with CANDIDATES.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(candidate, ensure_ascii=False) + "\n")
                candidates.append(candidate)
                counts[category] += 1
        record = {"attempt": len(attempts) + 1, "chunk_id": row["chunk_id"],
                  "work_id": row["work_id"], "category": category,
                  "evidence_text": evidence, "raw_generation": raw,
                  "candidate_id": candidate["candidate_id"] if candidate else None,
                  "rejections": reasons}
        with ATTEMPTS.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
        attempts.append(record)
        category_attempts[category] += 1
        new_attempts += 1
        if new_attempts % 10 == 0:
            print(f"attempts {len(attempts)}/{args.max_attempts}; auto-validated {len(candidates)}/{args.target}; categories {dict(counts)}", flush=True)
    report = {"result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS",
              "requested_target": args.target, "max_attempts": args.max_attempts,
              "attempts": len(attempts), "auto_validated": len(candidates),
              "auto_by_category": dict(counts), "attempts_by_category": dict(category_attempts),
              "rejection_reasons": dict(Counter(reason for a in attempts for reason in a["rejections"])),
              "passage_classification": quality,
              "train_works": split["train_work_ids"], "validation_works": split["validation_work_ids"],
              "protected_test_works": split["protected_test_work_ids"],
              "reviewed": 0, "training_gate": "CLOSED_PENDING_HUMAN_QA_AND_NEGATIVE_REVIEW"}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"attempts": len(attempts), "auto_validated": len(candidates),
                      "auto_by_category": dict(counts), "report": str(REPORT)}, indent=2))


if __name__ == "__main__":
    main()
