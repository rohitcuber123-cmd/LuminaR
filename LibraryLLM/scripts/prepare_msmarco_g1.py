"""Materialize a bounded, reproducible MS MARCO hard-negative pilot."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "datasets" / "training" / "hf_cache"
os.environ.setdefault("HF_HOME", str(CACHE))
os.environ.setdefault("HF_DATASETS_CACHE", str(CACHE / "datasets"))

import datasets
from datasets import load_dataset
from huggingface_hub import HfApi
import pyarrow as pa
import pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer
import sentence_transformers
import torch
import transformers
import accelerate
import faiss

DATASET = "sentence-transformers/msmarco-co-condenser-margin-mse-sym-mnrl-mean-v1"
CONFIG = "triplet"
OUT = ROOT / "datasets" / "training" / "generic" / "msmarco_g1"
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EXPECTED = ("query", "positive", "negative")


def local_base_model() -> Path:
    prior = json.loads((ROOT / "datasets" / "training" / "manifests" /
                        "minilm_generic_pilot_v1.json").read_text(encoding="utf-8"))
    path = Path(prior["base_model"])
    if not (path / "config.json").exists():
        raise FileNotFoundError(f"Frozen base model cache missing: {path}")
    return path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def lengths(tokenizer, values: list[str]) -> dict:
    counts = []
    for i in range(0, len(values), 512):
        counts.extend(len(ids) for ids in tokenizer(
            values[i:i + 512], add_special_tokens=True, truncation=False,
            padding=False)["input_ids"])
    ordered = sorted(counts)
    def pct(p):
        return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * p))]
    return {"min": ordered[0], "median": pct(.5), "p90": pct(.9),
            "p95": pct(.95), "p99": pct(.99), "max": ordered[-1],
            "over_256": sum(n > 256 for n in counts)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=50_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--buffer", type=int, default=10_000)
    parser.add_argument("--prefer-hard-negatives", action="store_true")
    parser.add_argument("--stream", action="store_true")
    args = parser.parse_args()
    if args.rows != 50_000 or args.seed != 42 or not args.stream:
        raise ValueError("G1 requires 50,000 streamed rows and seed 42")
    if (OUT / "manifest.json").exists():
        raise FileExistsError("G1 dataset already materialized")
    if not args.prefer_hard_negatives:
        raise ValueError("G1 requires mined explicit hard negatives")
    info = HfApi().dataset_info(DATASET)
    stream = load_dataset(DATASET, CONFIG, split="train", streaming=True,
                          revision=info.sha)
    if tuple(stream.features) != EXPECTED or any(
            not isinstance(stream.features[c], datasets.Value)
            or stream.features[c].dtype != "string" for c in EXPECTED):
        raise ValueError(f"Unexpected dataset schema: {stream.features}")
    stream = stream.shuffle(seed=args.seed, buffer_size=args.buffer)
    selected = []
    inspected = Counter()
    for row in stream:
        inspected["raw"] += 1
        vals = tuple(row.get(c) for c in EXPECTED)
        if not all(isinstance(v, str) and v.strip() for v in vals):
            inspected["empty_or_nontext"] += 1
            continue
        q, p, n = (v.strip() for v in vals)
        if p == n:
            inspected["positive_equals_negative"] += 1
            continue
        if not (3 <= len(q) <= 2048 and 10 <= len(p) <= 10000
                and 10 <= len(n) <= 10000):
            inspected["length_rejected"] += 1
            continue
        selected.append({"query": q, "positive": p, "negative": n})
        if len(selected) == args.rows:
            break
    if len(selected) != args.rows:
        raise RuntimeError(f"Only found {len(selected)} usable rows")
    rng = random.Random(args.seed)
    rng.shuffle(selected)
    train, validation = selected[:45_000], selected[45_000:]
    model = SentenceTransformer(str(local_base_model()), device="cpu", local_files_only=True)
    if model.max_seq_length != 256 or model.get_embedding_dimension() != 384:
        raise RuntimeError("Baseline model contract changed")
    token_stats = {c: lengths(model.tokenizer, [r[c] for r in selected])
                   for c in EXPECTED}
    triplets = Counter(tuple(r[c] for c in EXPECTED) for r in selected)
    queries = Counter(r["query"] for r in selected)
    positives = Counter(r["positive"] for r in selected)
    quality = {
        "exact_duplicate_triplets": sum(v - 1 for v in triplets.values()),
        "duplicate_queries": sum(v - 1 for v in queries.values()),
        "duplicate_positives": sum(v - 1 for v in positives.values()),
        "positive_equals_negative": 0,
        "train_validation_query_overlap": len({r["query"] for r in train}
                                              & {r["query"] for r in validation}),
    }
    if quality["train_validation_query_overlap"]:
        raise RuntimeError("Query leakage between generic train and validation")
    del model
    OUT.mkdir(parents=True, exist_ok=True)
    schema = pa.schema([(c, pa.string()) for c in EXPECTED])
    files = {}
    for name, rows in (("train", train), ("validation", validation)):
        target = OUT / f"msmarco_g1_{name}.parquet"
        if target.exists():
            raise FileExistsError(target)
        table = pa.Table.from_pylist(rows, schema=schema)
        pq.write_table(table, target, compression="zstd")
        files[name] = {"path": str(target), "rows": len(rows),
                       "sha256": sha256(target)}
    manifest = {
        "experiment": "G1_MS_MARCO", "dataset_id": DATASET,
        "config": CONFIG, "revision": info.sha, "split": "train",
        "selection": {"stream": True, "shuffle_seed": args.seed,
                      "shuffle_buffer": args.buffer,
                      "take_usable_rows": args.rows,
                      "post_selection_shuffle_seed": args.seed,
                      "split_rule": "first 45000 train; last 5000 validation"},
        "negative_provenance": "triplet config: publisher mines the most query-similar passage per query-positive pair as an explicit hard negative",
        "cache_location": str(CACHE), "raw_rows_inspected": inspected["raw"],
        "rejected_rows": dict(inspected), "selected_rows": len(selected),
        "schema": {c: "string" for c in EXPECTED}, "files": files,
        "quality": quality, "token_lengths": token_stats,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "versions": {"python": sys.version.split()[0], "torch": torch.__version__,
                     "transformers": transformers.__version__,
                     "datasets": datasets.__version__,
                     "sentence_transformers": sentence_transformers.__version__,
                     "accelerate": accelerate.__version__, "faiss": faiss.__version__},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("dataset_id", "config", "revision",
                                               "raw_rows_inspected", "selected_rows",
                                               "quality", "token_lengths", "files")}, indent=2))


if __name__ == "__main__":
    main()
