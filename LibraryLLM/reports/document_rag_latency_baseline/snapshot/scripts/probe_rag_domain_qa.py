"""Small source-grounded question-generation probe; never emits training pairs."""
from __future__ import annotations

import json
import os
from pathlib import Path
import random
import re
import sys

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "datasets" / "training"
os.environ["HF_HOME"] = str(TRAIN / "hf_cache")
os.environ["HF_DATASETS_CACHE"] = str(TRAIN / "hf_cache" / "datasets")


def main():
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    audit = json.loads((TRAIN / "reports" / "rag_training_decontamination_v1.json").read_text(encoding="utf-8"))
    train_ids = set(audit["train_work_ids"])
    test_ids = set(audit["protected_test_work_ids"])
    spans = {}
    for q in json.loads((ROOT / "rag" / "evaluation" / "rag_retrieval_eval_v1.json").read_text(encoding="utf-8"))["questions"]:
        spans.setdefault(q["work_id"], []).extend(q["accepted_passages"])
    rows = pq.read_table(ROOT / "datasets" / "rag_experiments" / "chunking_v1" / "tokens_220" /
                         "chunks.parquet", columns=["chunk_id", "work_id", "source_start_char",
                                                    "source_end_char", "text"]).to_pylist()
    candidates = [r for r in rows if r["work_id"] in train_ids and r["work_id"] not in test_ids
                  and not any(r["source_start_char"] < p["source_end"] and p["source_start"] < r["source_end_char"]
                              for p in spans.get(r["work_id"], []))
                  and 150 < len(r["text"]) < 1000 and "\ufffd" not in r["text"]]
    sample = random.Random(42).sample(candidates, 20)
    name = "google/flan-t5-base"
    tokenizer = AutoTokenizer.from_pretrained(name, cache_dir=str(TRAIN / "hf_cache"))
    model = AutoModelForSeq2SeqLM.from_pretrained(name, cache_dir=str(TRAIN / "hf_cache"),
                                                  dtype=torch.float16 if torch.cuda.is_available() else torch.float32)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()
    records = []
    for row in sample:
        passage = re.sub(r"\s+", " ", row["text"]).strip()
        prompt = ("Write one specific question about a relationship or event in this passage. "
                  "The question must be answerable from the passage. Give the exact answer after 'Answer:'. "
                  "Format: Question: ... Answer: ... Passage: " + passage)
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=480).to(device)
        with torch.inference_mode():
            output = model.generate(**inputs, max_new_tokens=80, do_sample=False)
        generated = tokenizer.decode(output[0], skip_special_tokens=True)
        answer = generated.split("Answer:", 1)[1].strip() if "Answer:" in generated else ""
        question = generated.split("Question:", 1)[1].split("Answer:", 1)[0].strip() if "Question:" in generated else ""
        answer_visible = bool(answer and re.sub(r"\W+", "", answer).casefold() in
                              re.sub(r"\W+", "", passage).casefold())
        records.append({"chunk_id": row["chunk_id"], "work_id": row["work_id"],
                        "passage": passage, "generated": generated, "question": question,
                        "answer": answer, "answer_visible": answer_visible})
        print(f"{len(records)}/20 answer_visible={answer_visible} {generated[:130]}", flush=True)
    path = TRAIN / "reports" / "domain_qa_generation_probe_v1.json"
    path.write_text(json.dumps({"model": name, "rows": records,
                                "valid_format": sum(bool(r["question"] and r["answer"]) for r in records),
                                "answer_visible": sum(r["answer_visible"] for r in records)},
                               indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
