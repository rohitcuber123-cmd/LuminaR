"""Controlled V7R1 rerun on the original V7 passage set."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import random
import re
from pathlib import Path

from build_rag_domain_qa_candidates_v2 import LocalQwen
from rag_domain_common import ROOT, SOURCE_MAP, TRAINING, controls, passage_pool
from rag_domain_qa_v2 import classify_passage_v2
from rag_domain_qa_assisted_v7 import (candidate_record, decontamination_reasons,
                                       parse_judge, strict_json)
from rag_domain_qa_assisted_v7r1 import candidate_record_v7r1

SYSTEM = ("You author source-grounded literary retrieval QA. Output ONLY a JSON object with exactly "
          "one key, candidates, whose value is a list of zero, one, or two objects. Each candidate must "
          "have exactly six string keys: question, short_answer, evidence_quote, category, difficulty, "
          "support_explanation. Do not add Markdown or commentary. "
          "Allowed category values ONLY: FACTUAL_DIRECT, ENTITY_RELATION, EVENT, MOTIVATION, CAUSAL, "
          "LOCATION, TEMPORAL, SEMANTIC_PARAPHRASE, QUOTE_OR_PHRASE. Do not invent or paraphrase "
          "category labels. Do not use character_action, relationship, direct_fact, causal_reason, "
          "event_fact, quote, or location_fact. Allowed difficulty values ONLY: EASY, MEDIUM, HARD. "
          "Do not invent or paraphrase difficulty labels. "
          "evidence_quote MUST be copied character-for-character as a CONTIGUOUS substring of "
          "TARGET_PASSAGE only. Do not summarize, paraphrase, normalize grammar, replace names or "
          "pronouns, or rewrite punctuation or whitespace. Prefer a short complete source sentence. "
          "short_answer MUST be an exact contiguous substring of evidence_quote and semantically "
          "complete for the question. Never paraphrase the short answer. "
          "AUTHORING_CONTEXT only clarifies nearby identity; never copy evidence from context "
          "outside TARGET_PASSAGE. The positive passage alone must answer the question. "
          "Questions must stand alone with named supported referents. Do not invent names, use book "
          "knowledge, ask metadata questions, or use unresolved he/she/they/it/this/that/the man/" 
          "the woman/the narrator/the news/the matter. "
          "FACTUAL_DIRECT requires an explicit fact; ENTITY_RELATION requires both endpoints; "
          "EVENT an explicit action; MOTIVATION or CAUSAL an explicit reason; LOCATION an explicit "
          "place; TEMPORAL a complete explicit time; SEMANTIC_PARAPHRASE permits paraphrase in "
          "the question only; QUOTE_OR_PHRASE requires a meaningful complete phrase. "
          "Do not ask WHY without explicit reason, WHEN without explicit complete time, WHO without "
          "explicit person/entity, or WHERE without explicit location. "
          "If TARGET_PASSAGE does not support a clear self-contained pair meeting every rule, "
          "return {\"candidates\":[]}. Zero candidates is valid; do not force two.")
JUDGE_SYSTEM = ("Audit a proposed QA against TARGET PASSAGE ONLY. Do not use book knowledge or "
                "authoring context. Output only one JSON object with exactly: label "
                "SUPPORTED|UNSUPPORTED|UNCERTAIN; question_answered_by_passage, answer_supported, "
                "question_self_contained, requires_outside_context, wrong_semantic_role booleans; "
                "reason string; supporting_quote exact substring of EVIDENCE. If unsure, UNCERTAIN.")


def source_score(row):
    text = row["text"]
    names = len(re.findall(r"\b(?:Mr\.|Mrs\.|Miss|Dr\.|Lord|Lady)\s+[A-Z][a-z]+|"
                           r"\b[A-Z][a-z]{3,}\s+(?:[A-Z][a-z]{3,})?", text))
    content = len(re.findall(r"\b(?:said|told|asked|went|came|left|found|gave|opened|"
                             r"because|wanted|hoped|sister|brother|father|mother|wife|husband)\b", text, re.I))
    pronouns = len(re.findall(r"\b(?:he|she|they|it|this|that)\b", text, re.I))
    return min(names, 8) * 2 + min(content, 8) - min(pronouns, 15) / 3


def overlaps(a, b):
    return a["work_id"] == b["work_id"] and a["source_start_char"] < b["source_end_char"] and (
        b["source_start_char"] < a["source_end_char"])


def select_passages(rows, count, seed):
    rng = random.Random(seed)
    groups = defaultdict(list)
    for row in rows:
        if row["split"] == "TRAIN": groups[row["work_id"]].append(row)
    books = sorted(groups)
    rng.shuffle(books)
    for book in books:
        rng.shuffle(groups[book])
        groups[book].sort(key=source_score, reverse=True)
    chosen = []
    while len(chosen) < count:
        progress = False
        for book in books:
            if len(chosen) >= count: break
            while groups[book]:
                row = groups[book].pop(0)
                if any(overlaps(row, prior) for prior in chosen): continue
                chosen.append(row); progress = True; break
        if not progress: raise RuntimeError("Not enough nonoverlapping TRAIN passages")
    return chosen


def authoring_context(row, source, accepted, tokenizer, max_tokens=600):
    start, end = row["source_start_char"], row["source_end_char"]
    left, right = max(0, start - 350), min(len(source), end + 350)
    # Never show accepted evaluation evidence even as surrounding context.
    for span in accepted:
        if span["source_end"] <= start and span["source_end"] > left:
            left = span["source_end"]
        if span["source_start"] >= end and span["source_start"] < right:
            right = span["source_start"]
    context = source[left:right]
    if len(tokenizer.encode(context, add_special_tokens=False)) > max_tokens:
        left, right = start, end
        context = row["text"]
    if len(tokenizer.encode(context, add_special_tokens=False)) > max_tokens:
        raise RuntimeError("Positive passage exceeds V7 authoring context token limit")
    return context, left


def _ask_json(local, system, user, *, judge=False, max_tokens=400):
    raw = local.ask(system, user, max_tokens=max_tokens)
    obj = strict_json(raw, judge=judge)
    if obj is None:
        raw = local.ask(system + " Return only valid JSON matching the required schema. "
                        "Do not add Markdown or commentary.", user, max_tokens=max_tokens)
        obj = strict_json(raw, judge=judge)
    return raw, obj


def generation_prompt(row, context):
    return (f"Book: {row['title']}\nChapter: {row['chapter']}\n"
            f"<TARGET_PASSAGE>\n{row['text']}\n</TARGET_PASSAGE>\n"
            f"<AUTHORING_CONTEXT>\n{context}\n</AUTHORING_CONTEXT>\n"
            "Evidence and answer MUST be exact substrings of TARGET_PASSAGE. "
            "Return zero, one, or two candidates as the strict JSON schema requires.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-manifest", type=Path, required=True)
    ap.add_argument("--max-per-passage", type=int, default=2)
    ap.add_argument("--version", default="v7r1")
    ap.add_argument("--deterministic", action="store_true")
    args = ap.parse_args()
    if (args.max_per_passage, args.version, args.deterministic) != (2, "v7r1", True):
        raise ValueError("V7R1 requires max 2, version v7r1, and deterministic generation")
    outdir = TRAINING / "luminar"
    report_dir = TRAINING / "reports"
    outputs = [outdir / f"domain_qa_assisted_v7r1_{kind}.jsonl" for kind in ("raw", "auto_checked", "rejected")]
    outputs.append(report_dir / "rag_domain_qa_assisted_v7r1_generation.json")
    if any(path.exists() for path in outputs):
        raise RuntimeError("V7R1 artifacts already exist; refusing overwrite")
    _, split, labels = controls()
    rows, quality = passage_pool(classifier=classify_passage_v2)
    manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    if manifest.get("version") != "v7r1" or len(manifest.get("passages", [])) != 50:
        raise RuntimeError("Expected the audited original 50-passage V7R1 manifest")
    original_raw_path = outdir / "domain_qa_assisted_v7_raw.jsonl"
    if hashlib.sha256(original_raw_path.read_bytes()).hexdigest() != manifest.get("original_raw_sha256"):
        raise RuntimeError("Original V7 raw artifact changed after V7R1 manifest freeze")
    original = [json.loads(line) for line in original_raw_path.read_text(encoding="utf-8").splitlines()]
    if len(original) != 50 or any((old["passage_index"], old["work_id"], old["chunk_id"],
                                   old["source_start"], old["source_end"]) !=
                                  (saved["passage_index"], saved["work_id"], saved["chunk_id"],
                                   saved["source_start"], saved["source_end"])
                                  for old, saved in zip(original, manifest["passages"])):
        raise RuntimeError("V7R1 manifest does not exactly reproduce original 50-passages")
    lookup = {(r["work_id"], r["chunk_id"]): r for r in rows}
    selected = []
    for saved in manifest["passages"]:
        row = lookup[(saved["work_id"], saved["chunk_id"])]
        if (row["source_start_char"], row["source_end_char"], row["source_sha256"]) != (
                saved["source_start"], saved["source_end"], saved["source_hash"]):
            raise RuntimeError("Original V7 passage/source hash drifted")
        selected.append(row)
    if any(r["work_id"] in split["protected_test_work_ids"] or r["split"] != "TRAIN" for r in selected):
        raise RuntimeError("TRAIN/TEST boundary violated")
    source_map = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    sources = {wid: (ROOT / source_map[wid]["source_file"]).read_text(encoding="utf-8")
               for wid in {r["work_id"] for r in selected}}
    accepted = defaultdict(list)
    for q in labels:
        accepted[q["work_id"]].extend(p for p in q["accepted_passages"] if p["relevance_grade"] == 2)
    import psutil
    import subprocess
    available = psutil.virtual_memory().available
    if available < int(1.5 * 2**30):
        raise RuntimeError(f"Insufficient available RAM to safely load local Qwen: {available/2**30:.2f} GiB")
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, check=True)
    if int(gpu.stdout.strip().splitlines()[0]) < 6500:
        raise RuntimeError("Insufficient free VRAM for local Qwen FP16")
    local = LocalQwen()
    model_path = local.model_id
    model_index = __import__("pathlib").Path(model_path) / "model.safetensors.index.json"
    model_fingerprint = hashlib.sha256(model_index.read_bytes()).hexdigest()
    eval_queries = [q["question"] for q in labels]
    seen_questions, seen_facts = [], set()
    raw_rows, auto_rows, rejected = [], [], []
    count = Counter()
    for i, row in enumerate(selected, 1):
        source = sources[row["work_id"]]
        context, context_start = authoring_context(row, source, accepted[row["work_id"]], local.tokenizer)
        generated_text, parsed = _ask_json(local, SYSTEM, generation_prompt(row, context), max_tokens=430)
        record = {"passage_index": i, "work_id": row["work_id"], "chunk_id": row["chunk_id"],
                  "source_start": row["source_start_char"], "source_end": row["source_end_char"],
                  "source_hash": row["source_sha256"],
                  "generator_raw": generated_text, "candidate_ids": [], "candidate_diagnostics": []}
        if parsed is None:
            count["format_failures"] += 1
            record["status"] = "FORMAT_FAILED"
            rejected.append({**record, "rejection_reasons": ["INVALID_GENERATOR_JSON"]})
        else:
            if not parsed["candidates"]: count["zero_candidate_passages"] += 1
            for j, generated in enumerate(parsed["candidates"]):
                count["raw_generated_QA"] += 1
                candidate_id = f"AQA7R1-{i:03d}-{j+1}"
                record["candidate_ids"].append(candidate_id)
                c, reasons, diag = candidate_record_v7r1(row, generated, context=context,
                                                         context_start=context_start,
                                                         generator_model=model_path, source=source)
                record["candidate_diagnostics"].append({"candidate_id": candidate_id, **diag,
                                                        "rejection_reasons": reasons})
                if c is None:
                    status = ("GROUNDING_FAILED" if any(x.startswith(("EVIDENCE_", "ANSWER_NOT_EXACT", "SOURCE_", "EMPTY_EVIDENCE", "AMBIGUOUS_EVIDENCE"))
                              for x in reasons) else "AUTO_REJECTED")
                    count[status] += 1
                    for reason in reasons: count[f"reason_{reason}"] += 1
                    rejected.append({"candidate_id": candidate_id, "work_id": row["work_id"],
                                     "chunk_id": row["chunk_id"], "review_status": status,
                                     "rejection_reasons": reasons, "generated": generated, **diag})
                    continue
                count["deterministic_passes"] += 1
                c["candidate_id"] = candidate_id
                reasons, fact = decontamination_reasons(c, eval_queries, seen_questions, seen_facts)
                if reasons:
                    count["AUTO_REJECTED"] += 1
                    for reason in reasons: count[f"reason_{reason}"] += 1
                    rejected.append({"candidate_id": candidate_id, "work_id": row["work_id"],
                                     "chunk_id": row["chunk_id"], "review_status": "AUTO_REJECTED",
                                     "rejection_reasons": reasons, "generated": generated, **diag})
                    continue
                judge_payload = {"question": c["question"], "short_answer": c["short_answer"],
                                 "evidence_quote": c["evidence_quote"], "positive_passage": c["positive_passage"]}
                judge_text, judge_obj = _ask_json(local, JUDGE_SYSTEM, json.dumps(judge_payload, ensure_ascii=False),
                                                  judge=True, max_tokens=210)
                judgment = parse_judge(judge_text, c["evidence_quote"])
                c["semantic_audit"] = judgment
                if judgment["label"] == "SUPPORTED":
                    c["review_status"] = "AUTO_CHECKED"
                    auto_rows.append(c)
                    count["AUTO_CHECKED"] += 1
                    seen_questions.append(c["question"])
                    seen_facts.add(fact)
                else:
                    c["review_status"] = "AUTO_REJECTED"
                    count[f"semantic_{judgment['label']}"] += 1
                    rejected.append(c)
        raw_rows.append(record)
        if i % 5 == 0:
            print(f"{i}/50 passages; raw {count['raw_generated_QA']}; AUTO_CHECKED {count['AUTO_CHECKED']}", flush=True)
        if psutil.virtual_memory().available < int(.75 * 2**30):
            raise RuntimeError("V7 generation stopped: available RAM fell below 0.75 GiB")
    report = {"result_label": "EXPERIMENTAL ONLY — NOT HUMAN REVIEWED", "seed": 503,
              "passages": 50, "max_candidates_per_passage": 2,
              "version": "v7r1", "source_manifest": str(args.source_manifest),
              "source_manifest_sha256": hashlib.sha256(args.source_manifest.read_bytes()).hexdigest(),
              "generator_model": model_path, "generator_model_index_sha256": model_fingerprint,
              "dtype": "float16", "device": "cuda", "do_sample": False,
              "max_new_tokens_generator": 430, "max_new_tokens_judge": 210,
              "same_model_generator_and_judge": True,
              "authoring_context_max_tokens": 600, "summary": dict(count),
              "selected_books": dict(Counter(r["work_id"] for r in selected)),
              "quality_filter_counts": quality,
              "test_leakage": 0, "evaluation_span_leakage": 0,
              "human_review_status": "NOT_REVIEWED"}
    for path, items in zip(outputs[:3], (raw_rows, auto_rows, rejected)):
        path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in items), encoding="utf-8")
    outputs[3].write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"passages": 50, "summary": dict(count), "model": model_path}, indent=2))


if __name__ == "__main__": main()
