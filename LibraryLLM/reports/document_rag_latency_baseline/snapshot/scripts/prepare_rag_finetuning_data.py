"""Prepare bounded, source-grounded QA pairs for the isolated RAG pilot."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import random
import re
import sys

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "datasets" / "training"
CACHE = TRAIN / "hf_cache"
CONTROL = ROOT / "datasets" / "rag_experiments" / "chunking_v1" / "tokens_220"
LABELS = ROOT / "rag" / "evaluation" / "rag_retrieval_eval_v1.json"
SOURCE_MAP = ROOT / "rag" / "evaluation" / "source_map_v1.json"
MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze_control() -> dict:
    manifest = json.loads((CONTROL / "manifest.json").read_text(encoding="utf-8"))
    checks = {
        "chunks_parquet_sha256": sha(CONTROL / "chunks.parquet"),
        "mapping_sha256": sha(CONTROL / "mapping.json"),
        "source_map_sha256": sha(SOURCE_MAP),
        "evaluation_labels_sha256": sha(LABELS),
    }
    for key, actual in checks.items():
        if manifest[key] != actual:
            raise RuntimeError(f"Frozen control mismatch: {key}")
    return {
        **checks,
        "manifest_sha256": sha(CONTROL / "manifest.json"),
        "source_hashes": {wid: book["source_sha256"] for wid, book in manifest["books"].items()},
        "chunk_count": manifest["statistics"]["chunk_count"],
        "model": MODEL,
        "seed": 42,
        "result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS",
    }


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def token_count(tokenizer, text: str) -> int:
    return len(tokenizer.encode(text, add_special_tokens=True))


def sentence_window(context: str, answer_start: int, answer: str, tokenizer) -> str | None:
    """Return an answer-bearing sentence plus neighbors within 220 model tokens."""
    if not answer or answer_start < 0 or context[answer_start:answer_start + len(answer)] != answer:
        return None
    boundaries = [0] + [m.end() for m in re.finditer(r"(?<=[.!?])\s+(?=[A-Z\"'])|\n+", context)] + [len(context)]
    boundaries = sorted(set(boundaries))
    i = next((i for i in range(len(boundaries) - 1)
              if boundaries[i] <= answer_start < boundaries[i + 1]), None)
    if i is None:
        return None
    left, right = i, i + 1
    passage = normalize(context[boundaries[left]:boundaries[right]])
    if token_count(tokenizer, passage) > 220:
        return None
    # Expand symmetrically while retaining the annotated answer.
    for side in ("left", "right", "left", "right"):
        nl, nr = (left - 1, right) if side == "left" else (left, right + 1)
        if nl < 0 or nr >= len(boundaries):
            continue
        candidate = normalize(context[boundaries[nl]:boundaries[nr]])
        if token_count(tokenizer, candidate) <= 220:
            left, right, passage = nl, nr, candidate
    if answer not in passage or token_count(tokenizer, passage) < 15:
        return None
    return passage


def squad_pair(row, tokenizer):
    answers = row.get("answers") or {}
    texts, starts = answers.get("text") or [], answers.get("answer_start") or []
    if not texts or not starts:
        return None
    answer = texts[0]
    passage = sentence_window(row["context"], starts[0], answer, tokenizer)
    query = normalize(row.get("question", ""))
    if not query or passage is None:
        return None
    return {"query": query, "positive": passage, "source": "rajpurkar/squad",
            "source_id": row["id"], "answer": answer,
            "token_count": token_count(tokenizer, passage),
            "source_metadata": row.get("title", "")}


def nq_pair(row, tokenizer):
    anns = row.get("annotations") or {}
    shorts = anns.get("short_answers") or []
    longs = anns.get("long_answer") or []
    if not shorts or not longs:
        return None
    short, long = shorts[0], longs[0]
    starts, ends = short.get("start_token") or [], short.get("end_token") or []
    answers = short.get("text") or []
    if not starts or not ends or not answers or long["start_token"] < 0:
        return None
    start, end, answer = starts[0], ends[0], normalize(answers[0])
    if not answer or not (long["start_token"] <= start < end <= long["end_token"]):
        return None
    doc = row["document"]["tokens"]
    tokens, markup = doc["token"], doc["is_html"]
    if end > len(tokens) or any(markup[start:end]):
        return None
    # A bounded window centered on the annotated answer; do not use a whole webpage.
    lo = max(long["start_token"], start - 75)
    hi = min(long["end_token"], end + 75)
    visible = [html.unescape(t) for t, is_html in zip(tokens[lo:hi], markup[lo:hi]) if not is_html]
    passage = normalize(" ".join(visible))
    if not passage or not re.sub(r"\W+", "", answer).lower() in re.sub(r"\W+", "", passage).lower():
        return None
    if token_count(tokenizer, passage) > 220 or token_count(tokenizer, passage) < 25:
        return None
    query = normalize(row["question"]["text"])
    if not query:
        return None
    return {"query": query, "positive": passage, "source": "google-research-datasets/natural_questions",
            "source_id": row["id"], "answer": answer,
            "token_count": token_count(tokenizer, passage),
            "source_metadata": row["document"].get("title", "")}


def prepare(name: str, target: int, max_inspected: int, tokenizer) -> dict:
    from datasets import load_dataset
    if name == "squad":
        dataset = load_dataset("rajpurkar/squad", split="train", cache_dir=str(CACHE))
        indices = list(range(len(dataset)))
        random.Random(42).shuffle(indices)
        iterator = (dataset[i] for i in indices)
        convert = squad_pair
    else:
        dataset = load_dataset("google-research-datasets/natural_questions", "default",
                               split="train", streaming=True, cache_dir=str(CACHE))
        iterator, convert = iter(dataset), nq_pair
    seen, accepted = set(), []
    reasons = {"conversion_rejected": 0, "duplicate": 0, "evaluation_query_exact": 0}
    evaluation_queries = {normalize(q["question"]).casefold() for q in
                          json.loads(LABELS.read_text(encoding="utf-8"))["questions"]}
    inspected = 0
    for row in iterator:
        inspected += 1
        pair = convert(row, tokenizer)
        if pair is None:
            reasons["conversion_rejected"] += 1
        elif pair["query"].casefold() in evaluation_queries:
            reasons["evaluation_query_exact"] += 1
        else:
            key = (pair["query"].casefold(), pair["positive"].casefold())
            if key in seen:
                reasons["duplicate"] += 1
            else:
                seen.add(key)
                accepted.append(pair)
        if inspected % 1000 == 0:
            print(f"{name}: inspected {inspected}, accepted {len(accepted)}", flush=True)
        if len(accepted) >= target or inspected >= max_inspected:
            break
    output = TRAIN / "processed" / f"{name}_pairs_v1.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(accepted), output, compression="zstd")
    return {"dataset": name, "inspected": inspected, "accepted": len(accepted),
            "target": target, "max_inspected": max_inspected, "rejections": reasons,
            "output": str(output), "sha256": sha(output)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["squad", "nq", "both"], required=True)
    parser.add_argument("--squad-target", type=int, default=1000)
    parser.add_argument("--nq-target", type=int, default=2000)
    parser.add_argument("--nq-max-inspected", type=int, default=15000)
    args = parser.parse_args()
    os.environ["HF_HOME"] = str(CACHE)
    os.environ["HF_DATASETS_CACHE"] = str(CACHE / "datasets")
    from transformers import AutoTokenizer
    for name in ("checkpoints", "manifests", "evaluation_indexes", "reports"):
        (TRAIN / name).mkdir(parents=True, exist_ok=True)
    control = freeze_control()
    (TRAIN / "manifests" / "control_v1.json").write_text(json.dumps(control, indent=2), encoding="utf-8")
    # Reuse the already-cached base tokenizer without duplicating model files in HF_HOME.
    snapshots = sorted((Path.home() / ".cache" / "huggingface" / "hub" /
                        "models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots").glob("*"))
    model_path = os.environ.get("LUMINAR_BASE_MODEL_PATH") or (str(snapshots[-1]) if snapshots else MODEL)
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    results = []
    if args.dataset in ("squad", "both"):
        results.append(prepare("squad", args.squad_target, args.squad_target * 3, tokenizer))
    if args.dataset in ("nq", "both"):
        results.append(prepare("nq", args.nq_target, args.nq_max_inspected, tokenizer))
    path = TRAIN / "reports" / "generic_preparation_v1.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    existing.update({r["dataset"]: r for r in results})
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
