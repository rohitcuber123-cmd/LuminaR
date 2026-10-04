"""Probe locally cached Qwen on filtered non-TEST passages; no training admission."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from rag_domain_common import CATEGORIES, TRAINING, controls, passage_pool, validate_candidate


def pick(rows, count):
    by_book = {}
    for row in rows:
        if row["split"] == "TRAIN":
            by_book.setdefault(row["work_id"], []).append(row)
    rng = random.Random(42)
    for group in by_book.values():
        rng.shuffle(group)
    books = sorted(by_book)
    return [by_book[wid][i // len(books)] for i, wid in enumerate((books * ((count // len(books)) + 1))[:count])]


def parse_json(text):
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def evidence_sentence(text):
    choices = []
    for match in re.finditer(r"[^.!?]+[.!?]", text, re.S):
        sentence = match.group().strip()
        words = sentence.split()
        if not 14 <= len(words) <= 55 or "\ufffd" in sentence or sentence.count("\n") > 5:
            continue
        if re.match(r"^(?:[“\"'\[]|(?:I|He|She|They|We|It|His|Her|Their|This|That)\b)", sentence, re.I):
            continue
        proper = [name for name in re.findall(r"\b[A-Z][a-z]{2,}\b", sentence[:100])
                  if name not in {"The", "And", "But", "For", "Then", "When", "What", "This", "That",
                                  "Next", "After", "Before", "From", "Although", "Yet", "However", "There"}]
        if not proper:
            continue
        names = len(proper)
        actions = len(re.findall(r"\b(?:was|were|had|said|went|came|left|found|told|gave|made|"
                                 r"decided|feared|refused|because|so that|therefore|after|before)\b",
                                 sentence, re.I))
        score = names * 2 + actions * 2 - abs(len(words) - 30) / 10
        choices.append((score, sentence))
    return max(choices)[1] if choices else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=12)
    args = parser.parse_args()
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    rows, quality = passage_pool()
    selected = pick(rows, args.count)
    labels = controls()[2]
    eval_queries = [q["question"] for q in labels]
    snapshots = sorted((Path.home() / ".cache" / "huggingface" / "hub" /
                        "models--Qwen--Qwen2.5-3B-Instruct" / "snapshots").glob("*"))
    if not snapshots:
        raise RuntimeError("No locally cached instruction model")
    path = snapshots[-1]
    tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(str(path), dtype=torch.float16,
                                                 device_map="cuda", low_cpu_mem_usage=True,
                                                 local_files_only=True, attn_implementation="sdpa")
    system = ("You create high-quality retrieval QA from one literary passage. Return exactly one JSON object "
              "with keys question, short_answer, difficulty. The answer must be copied exactly from the supplied "
              "EVIDENCE SENTENCE, including its spelling and punctuation. Ask a specific, self-contained question "
              "about a named person, event, place, cause, or relationship. No outside knowledge, passage metadata, "
              "vague pronouns, or title questions. If the requested category lacks clear evidence, return JSON with "
              "skip_reason only. Do not include markdown or explanations.")
    output = []
    for i, row in enumerate(selected):
        category = CATEGORIES[i % len(CATEGORIES)]
        evidence = evidence_sentence(row["text"])
        if evidence is None:
            output.append({"chunk_id": row["chunk_id"], "work_id": row["work_id"],
                           "requested_category": category, "raw": "", "auto_validated": False,
                           "rejections": ["NO_SUITABLE_EVIDENCE_SENTENCE"], "candidate": None})
            continue
        prompt = (f"Requested category: {category}\n"
                  f"EVIDENCE SENTENCE (the only permitted source for the answer):\n{evidence}")
        encoded = tokenizer.apply_chat_template([{"role": "system", "content": system},
                                                    {"role": "user", "content": prompt}],
                                                   tokenize=True, add_generation_prompt=True,
                                                   return_tensors="pt")
        input_ids = (encoded["input_ids"] if hasattr(encoded, "keys") else encoded).to(model.device)
        with torch.inference_mode():
            generated = model.generate(input_ids, max_new_tokens=100, do_sample=False,
                                       pad_token_id=tokenizer.eos_token_id)
        raw = tokenizer.decode(generated[0][input_ids.shape[1]:], skip_special_tokens=True).strip()
        obj = parse_json(raw)
        if isinstance(obj, dict) and "skip_reason" not in obj:
            obj = {**obj, "evidence_quote": evidence, "category": category}
        candidate, reasons = validate_candidate(row, obj, eval_queries)
        output.append({"chunk_id": row["chunk_id"], "work_id": row["work_id"],
                       "requested_category": category, "raw": raw,
                       "auto_validated": candidate is not None, "rejections": reasons,
                       "candidate": candidate})
        print(f"{i+1}/{args.count} {row['work_id']} {category}: {'PASS' if candidate else reasons} | {raw[:140]}", flush=True)
    report = {"model": str(path), "passage_quality_counts": quality,
              "requested": args.count, "auto_validated": sum(r["auto_validated"] for r in output),
              "rows": output}
    out = TRAINING / "reports" / "qwen_domain_qa_probe_v4.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
