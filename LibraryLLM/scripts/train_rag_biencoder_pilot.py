"""Run the isolated, bounded generic MiniLM pilot after data quality gates pass."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import time

import numpy as np
import pyarrow.parquet as pq
import psutil

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "datasets" / "training"
CACHE = TRAIN / "hf_cache"
os.environ["HF_HOME"] = str(CACHE)
os.environ["HF_DATASETS_CACHE"] = str(CACHE / "datasets")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-steps", type=int, default=60)
    args = parser.parse_args()
    import torch
    from datasets import Dataset
    from sentence_transformers import SentenceTransformer, SentenceTransformerTrainer, SentenceTransformerTrainingArguments
    from sentence_transformers.sentence_transformer.losses import MultipleNegativesRankingLoss
    from sentence_transformers.sentence_transformer.training_args import BatchSamplers

    control = json.loads((TRAIN / "manifests" / "control_v1.json").read_text(encoding="utf-8"))
    if sha(ROOT / "datasets" / "rag_experiments" / "chunking_v1" / "tokens_220" / "chunks.parquet") != control["chunks_parquet_sha256"]:
        raise RuntimeError("Frozen corpus changed")
    review = json.loads((TRAIN / "reports" / "rag_generic_training_data_review.json").read_text(encoding="utf-8"))
    leakage_path = TRAIN / "reports" / "rag_generic_test_leakage_v1.json"
    if not leakage_path.exists() or json.loads(leakage_path.read_text(encoding="utf-8"))["status"] != "PASS":
        raise RuntimeError("Protected TEST text leakage audit has not passed")
    for name in ("nq", "squad"):
        if review[name]["automated_failures"] or review[name]["near_evaluation_queries"]:
            raise RuntimeError(f"Unresolved pair quality issues: {name}")
    source = []
    data_hashes = {}
    for name, expected in (("nq", 2000), ("squad", 1000)):
        path = TRAIN / "processed" / f"{name}_pairs_v1.parquet"
        rows = pq.read_table(path, columns=["query", "positive"]).to_pylist()
        if len(rows) != expected:
            raise RuntimeError(f"Expected {expected} {name} pilot pairs; got {len(rows)}")
        data_hashes[name] = sha(path)
        source.extend(rows)
    random.Random(42).shuffle(source)
    dataset = Dataset.from_list(source)
    snapshots = sorted((Path.home() / ".cache" / "huggingface" / "hub" /
                        "models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots").glob("*"))
    if not snapshots:
        raise RuntimeError("Base model snapshot unavailable locally")
    model = SentenceTransformer(str(snapshots[-1]), device="cuda" if torch.cuda.is_available() else "cpu",
                                local_files_only=True)
    if model.max_seq_length != 256 or model.get_embedding_dimension() != 384:
        raise RuntimeError("Base model architecture/window changed")
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)
        torch.cuda.reset_peak_memory_stats()
    output = TRAIN / "models" / "minilm_generic_pilot_v1"
    checkpoints = TRAIN / "checkpoints" / "minilm_generic_pilot_v1"
    if output.exists() or checkpoints.exists():
        raise RuntimeError("Pilot output already exists; will not overwrite")
    args_train = SentenceTransformerTrainingArguments(
        output_dir=str(checkpoints), per_device_train_batch_size=8,
        gradient_accumulation_steps=1, max_steps=args.max_steps,
        learning_rate=2e-5, warmup_steps=max(1, args.max_steps // 10),
        weight_decay=0.01, lr_scheduler_type="linear", bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
        fp16=False, seed=42, data_seed=42, batch_sampler=BatchSamplers.NO_DUPLICATES,
        save_strategy="steps", save_steps=max(1, args.max_steps // 2), save_total_limit=2,
        logging_steps=10, report_to="none", dataloader_num_workers=0,
    )
    trainer = SentenceTransformerTrainer(model=model, args=args_train, train_dataset=dataset,
                                         loss=MultipleNegativesRankingLoss(model))
    started = time.perf_counter()
    train_result = trainer.train()
    duration = time.perf_counter() - started
    output.mkdir(parents=True)
    model.save(str(output))
    del trainer, model
    loaded = SentenceTransformer(str(output), device="cpu", local_files_only=True)
    vectors = loaded.encode(["A test query", "A test passage"], normalize_embeddings=True,
                            convert_to_numpy=True)
    if vectors.shape != (2, 384) or not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-4):
        raise RuntimeError("Pilot model save/load/embedding verification failed")
    manifest = {
        "result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS",
        "variant": "B_GENERIC_PILOT", "base_model": str(snapshots[-1]),
        "control_sha256": control["chunks_parquet_sha256"], "data_sha256": data_hashes,
        "nq_pairs": 2000, "squad_pairs": 1000,
        "loss": "MultipleNegativesRankingLoss", "columns_received": ["query", "positive"],
        "explicit_hard_negatives": False, "max_seq_length": 256,
        "hyperparameters": args_train.to_dict(),
        "training_seconds": duration, "train_loss": train_result.training_loss,
        "peak_process_rss_bytes": psutil.Process().memory_info().rss,
        "peak_gpu_allocated_bytes": torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None,
        "model_path": str(output),
    }
    (TRAIN / "manifests" / "minilm_generic_pilot_v1.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("variant", "training_seconds", "train_loss", "peak_gpu_allocated_bytes", "model_path")}, indent=2))


if __name__ == "__main__":
    main()
