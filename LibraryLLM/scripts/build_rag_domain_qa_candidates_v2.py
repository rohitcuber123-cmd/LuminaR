"""Run one bounded proposition-first domain QA pilot; never create reviewed data."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import re

from probe_qwen_domain_qa import evidence_sentence, parse_json
from rag_domain_common import TRAINING, controls, passage_pool
from rag_domain_qa_v2 import EntailmentResult, SemanticEntailmentJudge, classify_passage_v2, validate

TARGETS = {"FACTUAL_DIRECT": 8, "ENTITY_RELATION": 7, "EVENT": 8, "MOTIVATION": 6,
           "CAUSAL": 6, "LOCATION": 4, "TEMPORAL": 4, "SEMANTIC_PARAPHRASE": 5,
           "QUOTE_OR_PHRASE": 2}
RELATION = {"FACTUAL_DIRECT": "ENTITY_ACTION", "ENTITY_RELATION": "ENTITY_RELATION",
            "EVENT": "EVENT", "MOTIVATION": "MOTIVATION", "CAUSAL": "CAUSE_EFFECT",
            "LOCATION": "LOCATION", "TEMPORAL": "TEMPORAL",
            "SEMANTIC_PARAPHRASE": "ENTITY_ACTION", "QUOTE_OR_PHRASE": "QUOTE_OR_STATEMENT"}
SLOT = {"FACTUAL_DIRECT": "object", "ENTITY_RELATION": "object", "EVENT": "object",
        "MOTIVATION": "cause", "CAUSAL": "cause", "LOCATION": "location",
        "TEMPORAL": "time", "SEMANTIC_PARAPHRASE": "object", "QUOTE_OR_PHRASE": "object"}
TYPE = {"FACTUAL_DIRECT": "EVENT", "ENTITY_RELATION": "PERSON", "EVENT": "EVENT",
        "MOTIVATION": "CAUSE", "CAUSAL": "CAUSE", "LOCATION": "LOCATION",
        "TEMPORAL": "TIME", "SEMANTIC_PARAPHRASE": "EVENT", "QUOTE_OR_PHRASE": "PHRASE"}
HINT = {"ENTITY_RELATION": r"\b(?:son|daughter|brother|sister|wife|husband|father|mother|friend|relative)\b",
        "MOTIVATION": r"\b(?:because|wanted to|hoped to|feared that|in order to|so that)\b",
        "CAUSAL": r"\b(?:because|since|therefore|as a result|due to|so that)\b",
        "LOCATION": r"\b(?:in|at|to|from|near|through)\s+[A-Z][a-z]",
        "TEMPORAL": r"\b(?:\d{4}|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|"
                    r"morning|afternoon|evening|night|next day|before|after)\b",
        "QUOTE_OR_PHRASE": r"[\"“”]"}


class LocalQwen:
    def __init__(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        path = Path.home() / ".cache" / "huggingface" / "hub" / "models--Qwen--Qwen2.5-3B-Instruct" / "snapshots"
        snapshots = sorted(path.glob("*"))
        if not snapshots:
            raise RuntimeError("Existing local Qwen2.5-3B-Instruct snapshot unavailable; no download attempted")
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(str(snapshots[-1]), local_files_only=True)
        self.model = AutoModelForCausalLM.from_pretrained(str(snapshots[-1]), dtype=torch.float16,
                                                          device_map="cuda", low_cpu_mem_usage=True,
                                                          local_files_only=True, attn_implementation="sdpa")
        self.model_id = str(snapshots[-1])

    def ask(self, system, user, max_tokens=180):
        encoded = self.tokenizer.apply_chat_template([
            {"role": "system", "content": system}, {"role": "user", "content": user}],
            tokenize=True, add_generation_prompt=True, return_tensors="pt")
        inputs = (encoded["input_ids"] if hasattr(encoded, "keys") else encoded).to(self.model.device)
        with self.torch.inference_mode():
            output = self.model.generate(inputs, max_new_tokens=max_tokens, do_sample=False,
                                         pad_token_id=self.tokenizer.eos_token_id)
        return self.tokenizer.decode(output[0][inputs.shape[1]:], skip_special_tokens=True).strip()


class QwenJudge(SemanticEntailmentJudge):
    def __init__(self, local):
        self.local = local

    def judge(self, candidate):
        p = candidate["proposition"]
        payload = {"question": candidate["question"], "answer": candidate["short_answer"],
                   "evidence_quote": p["evidence_quote"], "local_passage": candidate["positive_passage"],
                   "structured_proposition": {k: v for k, v in p.items() if k not in {"proof_kind", "rule_id"}}}
        raw = self.local.ask(
            "Judge ONLY whether this exact question/answer relation is stated in the evidence. "
            "Do not use book knowledge. Return strict JSON with label ENTAILED, NOT_ENTAILED, or UNCERTAIN; "
            "question_is_answered, answer_matches_question, evidence_supports_answer, "
            "relation_direction_correct (booleans); reason; supporting_quote copied exactly from evidence. "
            "If an entity merely occurs in the evidence with a different role, choose NOT_ENTAILED. "
            "If unclear, choose UNCERTAIN.", json.dumps(payload, ensure_ascii=False), 180)
        obj = parse_json(raw)
        if not isinstance(obj, dict) or obj.get("label") not in {"ENTAILED", "NOT_ENTAILED", "UNCERTAIN"}:
            return EntailmentResult("UNCERTAIN", "Invalid judge JSON", "")
        yes = all(obj.get(k) is True for k in ("question_is_answered", "answer_matches_question",
                                                  "evidence_supports_answer", "relation_direction_correct"))
        quote = str(obj.get("supporting_quote", ""))
        if obj["label"] == "ENTAILED" and (not yes or not quote or quote not in p["evidence_quote"]):
            return EntailmentResult("UNCERTAIN", "Judge claim missing supporting checks/quote", "")
        return EntailmentResult(obj["label"], str(obj.get("reason", ""))[:300], quote)


def select_passages(rows, seed, count):
    rng = random.Random(seed)
    by_category_book = defaultdict(list)
    for row in rows:
        if row["split"] != "TRAIN": continue
        basic = evidence_sentence(row["text"])
        for category in TARGETS:
            evidence = basic
            if category in HINT and (not evidence or not re.search(HINT[category], evidence, re.I)):
                sentences = (m.group().strip() for m in re.finditer(r"[^.!?]+[.!?]", row["text"], re.S))
                evidence = next((s for s in sentences if 12 <= len(s.split()) <= 55 and
                                 re.search(HINT[category], s, re.I) and
                                 re.search(r"\b[A-Z][a-z]{2,}\b", s)), None)
            if evidence and row["text"].count(evidence) == 1:
                by_category_book[(category, row["work_id"])].append((row, evidence))
    for group in by_category_book.values(): rng.shuffle(group)
    books = sorted({wid for _, wid in by_category_book})
    rng.shuffle(books)
    selected = []
    used, book_counts = set(), Counter()
    schedule = [c for c, n in TARGETS.items() for _ in range(n)]
    for category in schedule[:count]:
        choices = [(book_counts[wid], wid) for wid in books
                   if any(row["chunk_id"] not in used for row, _ in by_category_book[(category, wid)])]
        if not choices: raise RuntimeError(f"Insufficient distinct source passages for {category}")
        _, wid = min(choices)
        row, evidence = next((row, evidence) for row, evidence in by_category_book[(category, wid)]
                             if row["chunk_id"] not in used)
        selected.append((row, evidence))
        used.add(row["chunk_id"])
        book_counts[wid] += 1
    return selected


def extract(local, evidence, category):
    prompt = {"requested_relation_type": RELATION[category], "asked_slot": SLOT[category],
              "answer_type": TYPE[category], "evidence_sentence": evidence}
    raw = local.ask(
        "FIRST extract one explicit source proposition; do NOT generate a question. "
        "Return JSON keys subject, predicate, object, relation_type, plus when applicable "
        "cause, effect, location, location_direction, time, temporal_relation, "
        "entity_a, entity_b, relation_direction. Every nonempty subject/predicate/object/cause/"
        "effect/location/time/entity span must be a contiguous exact substring of the evidence. "
        "Preserve participant roles and relation direction. Do not infer from book knowledge. "
        "If the requested type or asked slot is not explicit, return {\"skip_reason\":\"...\"}. "
        "No question in this stage.", json.dumps(prompt, ensure_ascii=False), 220)
    return raw, parse_json(raw)


def build_question(local, proposition, category, answer):
    payload = {"category": category, "asked_slot": SLOT[category], "answer": answer,
               "proposition": proposition}
    raw = local.ask(
        "Create ONE standalone literary retrieval question FROM the given proposition and asked_slot. "
        "Do not change the predicate, relation direction, or participant roles. "
        "Do not mention the answer in the question. Do not use unresolved pronouns, 'the narrator', "
        "'the speaker', metadata, or outside literary knowledge. If the relation cannot yield a "
        "specific standalone question, return {\"skip_reason\":\"...\"}. "
        "Return only JSON {\"question\":\"...\"}.", json.dumps(payload, ensure_ascii=False), 100)
    return raw, parse_json(raw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--version", default="v2")
    args = ap.parse_args()
    if args.version != "v2" or args.target != 50:
        raise ValueError("This isolated pilot is limited to exactly 50 new attempts, version v2")
    outdir = TRAINING / "luminar"
    paths = {name: outdir / f"domain_qa_{name}_v2.jsonl" for name in
             ("attempts", "candidates", "auto_validated", "rejected")}
    if any(path.exists() for path in paths.values()):
        raise RuntimeError("v2 pilot files already exist; refusing to overwrite or silently resume")
    rows, quality = passage_pool(classifier=classify_passage_v2)
    saved, split, labels = controls()
    eval_queries = [x["question"] for x in labels]
    selected = select_passages(rows, args.seed, args.target)
    if len(selected) != args.target: raise RuntimeError("Unable to select 50 balanced TRAIN passages")
    local = LocalQwen()
    judge = QwenJudge(local)
    counts, by_category, by_book = Counter(), Counter(), Counter()
    seen = []
    summary = {"passages_considered": len(rows), "passages_rejected_by_quality_filter": sum(quality.values()) - len(rows),
               "propositions_extracted": 0, "propositions_rejected": 0,
               "questions_generated": 0, "grounding_failed": 0, "semantic_failed": 0,
               "auto_validated": 0, "auto_checked": 0}
    outdir.mkdir(parents=True, exist_ok=True)
    for i, (row, evidence) in enumerate(selected):
        schedule = [c for c, n in TARGETS.items() for _ in range(n)]
        category = schedule[i]
        by_category[category] += 1
        by_book[row["work_id"]] += 1
        attempt = {"candidate_id": f"DQ2-{i+1:04d}", "stage": "PROPOSITION",
                   "chunk_id": row["chunk_id"], "work_id": row["work_id"],
                   "generator_category": category, "evidence_quote": evidence}
        if category in HINT and not re.search(HINT[category], evidence, re.I):
            attempt.update({"stage": "PROPOSITION_REJECTED", "rejection_codes": ["CATEGORY_NOT_EXPLICIT"],
                            "short_reason": "Required relation cue absent from exact evidence", "generator_output": ""})
            summary["propositions_rejected"] += 1
        else:
            raw, prop = extract(local, evidence, category)
            attempt["generator_output"] = raw
            if not isinstance(prop, dict) or prop.get("skip_reason") or not prop.get(SLOT[category]):
                attempt.update({"stage": "PROPOSITION_REJECTED", "rejection_codes": ["NO_EXPLICIT_PROPOSITION"],
                                "short_reason": str(prop.get("skip_reason", "")) if isinstance(prop, dict) else "Invalid JSON"})
                summary["propositions_rejected"] += 1
            else:
                summary["propositions_extracted"] += 1
                offset = row["text"].index(evidence)
                prop.update({"source_sentence": evidence, "evidence_quote": evidence,
                             "evidence_start": row["source_start_char"] + offset,
                             "evidence_end": row["source_start_char"] + offset + len(evidence),
                             "proof_kind": "LLM_EXTRACTED"})
                answer = prop[SLOT[category]]
                qraw, qobj = build_question(local, prop, category, answer)
                attempt["question_generator_output"] = qraw
                if not isinstance(qobj, dict) or qobj.get("skip_reason") or not qobj.get("question"):
                    attempt.update({"stage": "QUESTION_REJECTED", "rejection_codes": ["QUESTION_GENERATION_FAILED"],
                                    "short_reason": str(qobj.get("skip_reason", "")) if isinstance(qobj, dict) else "Invalid JSON"})
                else:
                    summary["questions_generated"] += 1
                    question = str(qobj["question"])
                    wh = question.split(" ", 1)[0].casefold()
                    answer_type = {"who": "PERSON", "where": "LOCATION", "when": "TIME",
                                   "why": "CAUSE"}.get(wh, TYPE[category])
                    candidate = {"candidate_id": attempt["candidate_id"], "work_id": row["work_id"],
                                 "book_title": row["title"], "chapter": row["chapter"],
                                 "chunk_id": row["chunk_id"], "source_hash": row["source_sha256"],
                                 "source_start": row["source_start_char"], "source_end": row["source_end_char"],
                                 "positive_passage": row["text"], "proposition": prop,
                                 "asked_slot": SLOT[category], "question": question,
                                 "short_answer": answer, "answer_type": answer_type,
                                 "generator_category": category, "validated_category": category,
                                 "category": category, "difficulty": "HARD" if category in {"CAUSAL", "MOTIVATION"}
                                 else "MEDIUM" if category in {"ENTITY_RELATION", "SEMANTIC_PARAPHRASE"} else "EASY",
                                 "split": row["split"], "review_status": "GENERATED", "reviewer": None,
                                 "reviewed_at": None, "question_from_template": False}
                    source = (Path(__file__).resolve().parents[1] /
                              json.loads((Path(__file__).resolve().parents[1] / "rag/evaluation/source_map_v1.json")
                                         .read_text(encoding="utf-8"))["books"][row["work_id"]]["source_file"]).read_text(encoding="utf-8")
                    checked = validate(candidate, source, eval_queries=eval_queries, seen_queries=seen,
                                       test_works=split["protected_test_work_ids"], judge=judge)
                    attempt.update({"stage": checked["review_status"],
                                    "rejection_codes": checked["auto_validation"]["rejection_reasons"],
                                    "short_reason": checked["auto_validation"]["entailment"]["reason"]})
                    with paths["candidates"].open("a", encoding="utf-8") as f:
                        f.write(json.dumps(checked, ensure_ascii=False) + "\n")
                    if checked["review_status"] == "AUTO_VALIDATED":
                        seen.append(checked["question"])
                        with paths["auto_validated"].open("a", encoding="utf-8") as f:
                            f.write(json.dumps(checked, ensure_ascii=False) + "\n")
                    else:
                        with paths["rejected"].open("a", encoding="utf-8") as f:
                            f.write(json.dumps({"candidate_id": checked["candidate_id"], "stage": checked["review_status"],
                                                "rejection_codes": checked["auto_validation"]["rejection_reasons"],
                                                "generator_output": raw, "question_generator_output": qraw,
                                                "chunk_id": row["chunk_id"], "work_id": row["work_id"]},
                                               ensure_ascii=False) + "\n")
                    summary[checked["review_status"].lower()] += 1
        counts.update(attempt.get("rejection_codes", []))
        if attempt["stage"] in {"PROPOSITION_REJECTED", "QUESTION_REJECTED"}:
            with paths["rejected"].open("a", encoding="utf-8") as f:
                f.write(json.dumps({"candidate_id": attempt["candidate_id"], "stage": attempt["stage"],
                                    "rejection_codes": attempt["rejection_codes"],
                                    "short_reason": attempt.get("short_reason", ""),
                                    "generator_output": attempt.get("generator_output", ""),
                                    "question_generator_output": attempt.get("question_generator_output", ""),
                                    "chunk_id": row["chunk_id"], "work_id": row["work_id"]},
                                   ensure_ascii=False) + "\n")
        with paths["attempts"].open("a", encoding="utf-8") as f:
            f.write(json.dumps(attempt, ensure_ascii=False) + "\n")
        if (i + 1) % 5 == 0:
            print(f"{i+1}/50 attempts; extracted {summary['propositions_extracted']}; "
                  f"generated {summary['questions_generated']}; auto {summary['auto_validated']}", flush=True)
    report = {"result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS",
              "model": local.model_id, "seed": args.seed, "requested_new_attempts": args.target,
              "summary": summary, "category_attempts": dict(by_category), "book_attempts": dict(by_book),
              "rejection_reasons": dict(counts), "test_leakage_count": counts["TEST_LEAKAGE"],
              "training_gate": "CLOSED_PENDING_HUMAN_REVIEW"}
    path = TRAINING / "reports" / "rag_domain_qa_generation_audit_v2.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"summary": summary, "report": str(path)}, indent=2))


if __name__ == "__main__": main()
