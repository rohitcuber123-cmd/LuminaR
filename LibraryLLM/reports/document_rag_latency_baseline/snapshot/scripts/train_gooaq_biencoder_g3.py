"""Isolated G3 MiniLM training with explicit GooAQ hard negatives."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "datasets" / "training"
os.environ.setdefault("HF_HOME", str(TRAIN / "hf_cache"))
os.environ.setdefault("HF_DATASETS_CACHE", str(TRAIN / "hf_cache" / "datasets"))

import numpy as np
import psutil
import pyarrow.parquet as pq
import torch
from datasets import Dataset
from sentence_transformers import (
    SentenceTransformer, SentenceTransformerTrainer, SentenceTransformerTrainingArguments,
)
from sentence_transformers.sentence_transformer.losses import MultipleNegativesRankingLoss
from sentence_transformers.sentence_transformer.training_args import BatchSamplers

DATA = TRAIN / "generic" / "gooaq_g3"
BASE = "sentence-transformers/all-MiniLM-L6-v2"
CONTROL = TRAIN / "manifests" / "control_v1.json"
CORPUS = ROOT / "datasets" / "rag_experiments" / "chunking_v1" / "tokens_220" / "chunks.parquet"
LABELS = ROOT / "rag" / "evaluation" / "rag_retrieval_eval_v1.json"
PRODUCTION = ROOT / "datasets" / "rag_experiments" / "chunking_v1" / "reports" / "production_before_sha256.json"


def local_base_model() -> Path:
    prior = json.loads((TRAIN / "manifests" / "minilm_generic_pilot_v1.json").read_text(encoding="utf-8"))
    path = Path(prior["base_model"])
    if not (path / "config.json").exists():
        raise FileNotFoundError(f"Frozen base model cache missing: {path}")
    return path


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def preflight() -> tuple[dict, dict]:
    from gooaq_g3_controls import verify
    verify()
    frozen = json.loads(CONTROL.read_text(encoding="utf-8"))
    if sha(CORPUS) != frozen["chunks_parquet_sha256"] or sha(LABELS) != frozen["evaluation_labels_sha256"]:
        raise RuntimeError("Frozen corpus/labels changed")
    production = json.loads(PRODUCTION.read_text(encoding="utf-8"))
    changed = [path for path, digest in production.items()
               if not (ROOT / path).exists() or sha(ROOT / path) != digest]
    if changed:
        raise RuntimeError(f"Production snapshot changed: {changed}")
    dataset = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    if dataset["dataset_id"] != "sentence-transformers/gooaq" or dataset["config"] != "pair":
        raise RuntimeError("Unexpected G3 data source")
    if dataset["train_validation_normalized_query_overlap"]:
        raise RuntimeError("Generic validation query leakage")
    for split, expected in (("train", 45_000), ("validation", 5_000)):
        path = Path(dataset["files"][split]["path"])
        if sha(path) != dataset["files"][split]["sha256"] or pq.read_metadata(path).num_rows != expected:
            raise RuntimeError(f"G3 {split} dataset hash/count changed")
    if not (TRAIN / "reports" / "rag_g3_baseline_reproduction.json").exists():
        raise RuntimeError("Baseline A reproduction absent")
    historical = json.loads((TRAIN / 'reports/baseline_a_previous.json').read_text(encoding='utf-8'))
    reproduced = json.loads((TRAIN / 'reports/rag_g3_baseline_reproduction.json').read_text(encoding='utf-8'))
    old = {q['query_id']:[c['chunk_id'] for c in q['top50']] for q in historical['queries'] if q['split']=='DEV'}
    new = {q['query_id']:[c['chunk_id'] for c in q['top50']] for q in reproduced['queries']}
    if old != new: raise RuntimeError('Baseline A failed exact DEV Top50 reproduction; STOP')
    source = json.loads((DATA / 'source_manifest.json').read_text(encoding='utf-8'))
    freeze = json.loads((DATA / 'pair_freeze_sha256.json').read_text(encoding='utf-8'))
    if sha(DATA / 'source_manifest.json') != freeze['source_manifest_sha256']:
        raise RuntimeError('Frozen source manifest drift; STOP')
    for item in source['files'].values():
        if sha(Path(item['path'])) != item['sha256']: raise RuntimeError('Frozen pair/source artifact drift; STOP')
    initial = pq.read_table(DATA / 'gooaq_g3_pairs_train.parquet', columns=['question','positive']).to_pylist()
    final = pq.read_table(DATA / 'gooaq_g3_train_triplets.parquet', columns=['question','positive']).to_pylist()
    if initial != final: raise RuntimeError('Frozen TRAIN questions/positives changed; STOP')
    if dataset['mining']['random_fallback_fraction'] > .05: raise RuntimeError('Fallback >5%; STOP')
    return frozen, dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke", action="store_true")
    mode.add_argument("--train", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    if args.seed != 42 or args.epochs != 1 or args.batch_size not in (8, 16):
        raise ValueError("G3 permits seed=42, one epoch, batch size 8 or 16")
    frozen, data_manifest = preflight()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable")
    if psutil.virtual_memory().available < 2 * 1024**3:
        raise MemoryError("Less than 2 GiB RAM available before training")
    available_vram_before = torch.cuda.mem_get_info()[0]
    if available_vram_before < 5.5 * 1024**3:
        raise MemoryError("Less than 5.5 GiB VRAM available before training")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    split = "smoke" if args.smoke else "full"
    if args.train:
        smoke = json.loads((TRAIN / 'manifests/minilm_g3_gooaq_50k_smoke.json').read_text(encoding='utf-8'))
        if not np.isfinite(smoke['final_training_loss']) or smoke['embedding_dimension'] != 384:
            raise RuntimeError('Smoke verification failed; STOP')
    model_dir = TRAIN / "models" / f"minilm_g3_gooaq_50k_{split}"
    checkpoint_dir = TRAIN / "checkpoints" / f"minilm_g3_gooaq_50k_{split}"
    manifest_path = TRAIN / "manifests" / f"minilm_g3_gooaq_50k_{split}.json"
    if model_dir.exists() or checkpoint_dir.exists() or manifest_path.exists():
        raise FileExistsError("G3 output already exists; inspect before resuming")
    rows = pq.read_table(DATA / "gooaq_g3_train_triplets.parquet", columns=["question", "positive", "negative"]).slice(
        0, 1024 if args.smoke else 45_000).to_pylist()
    if not all(set(row) == {"question", "positive", "negative"} for row in rows):
        raise ValueError("Triplet columns missing")
    dataset = Dataset.from_list(rows)
    base_path = local_base_model()
    assert "models--sentence-transformers--all-MiniLM-L6-v2" in str(base_path) and not any(x in str(base_path).lower() for x in ("g1", "g2"))
    model = SentenceTransformer(str(base_path), device="cuda", local_files_only=True)
    if model.max_seq_length != 256 or model.get_embedding_dimension() != 384:
        raise RuntimeError("Base model architecture changed")
    bf16 = bool(torch.cuda.is_bf16_supported())
    args_train = SentenceTransformerTrainingArguments(
        output_dir=str(checkpoint_dir), per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=1, num_train_epochs=1,
        learning_rate=2e-5, weight_decay=0.01, lr_scheduler_type="linear",
        warmup_ratio=0.05, bf16=bf16, fp16=False,
        seed=42, data_seed=42, batch_sampler=BatchSamplers.NO_DUPLICATES,
        save_strategy="no", logging_steps=20, logging_nan_inf_filter=False,
        report_to="none", dataloader_num_workers=0,
    )
    loss = MultipleNegativesRankingLoss(model)
    class FiniteLossTrainer(SentenceTransformerTrainer):
        def compute_loss(self, *call_args, **call_kwargs):
            value = super().compute_loss(*call_args, **call_kwargs)
            loss_value = value[0] if isinstance(value, tuple) else value
            if not torch.isfinite(loss_value.detach()).all():
                raise RuntimeError('NaN/Inf loss; STOP before backward')
            return value
    trainer = FiniteLossTrainer(model=model, args=args_train,
                                         train_dataset=dataset, loss=loss)
    from transformers import TrainerCallback
    class SafetyCallback(TrainerCallback):
        def on_step_end(self, args, state, control, **kwargs):
            if torch.cuda.mem_get_info()[0] < 1.5 * 1024**3:
                raise MemoryError('Unsafe GPU headroom; STOP')
        def on_log(self, args, state, control, logs=None, **kwargs):
            if logs and any(not np.isfinite(logs[k]) for k in ('loss', 'grad_norm') if k in logs):
                raise RuntimeError('NaN/Inf loss or gradient; STOP')
    trainer.add_callback(SafetyCallback())
    # Inspect a real trainer batch before any optimization step.
    batch = next(iter(trainer.get_train_dataloader()))
    if not {"question_input_ids", "positive_input_ids", "negative_input_ids"} <= set(batch):
        raise RuntimeError("Explicit negative dropped by trainer collation")
    torch.cuda.reset_peak_memory_stats()
    stop = threading.Event()
    peak_rss = [psutil.Process().memory_info().rss]
    min_global_free_vram = [available_vram_before]
    def monitor():
        while not stop.wait(0.25):
            peak_rss[0] = max(peak_rss[0], psutil.Process().memory_info().rss)
            min_global_free_vram[0] = min(min_global_free_vram[0], torch.cuda.mem_get_info()[0])
    watcher = threading.Thread(target=monitor, daemon=True)
    watcher.start()
    started = time.perf_counter()
    try:
        result = trainer.train()
    finally:
        stop.set()
        watcher.join(timeout=2)
    duration = time.perf_counter() - started
    peak_gpu = torch.cuda.max_memory_reserved()
    total_gpu = torch.cuda.get_device_properties(0).total_memory
    headroom = min_global_free_vram[0]
    if not np.isfinite(result.training_loss):
        raise RuntimeError("Nonfinite training loss")
    if headroom < 1.5 * 1024**3:
        raise MemoryError("Training exceeded 1.5 GiB global VRAM headroom")
    model_dir.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(model_dir))
    saved = SentenceTransformer(str(model_dir), device="cpu", local_files_only=True)
    v = saved.encode(["test query", "test passage"], convert_to_numpy=True,
                     normalize_embeddings=True)
    if v.shape != (2, 384) or not np.isfinite(v).all() or not np.allclose(np.linalg.norm(v, axis=1), 1, atol=1e-4):
        raise RuntimeError("Saved model failed encode verification")
    state = trainer.state
    manifest = {
        "experiment": "G3_GOOAQ", "phase": split,
        "base_model": BASE, "base_snapshot": str(base_path), "base_weights_sha256": sha(base_path / "model.safetensors"), "model_path": str(model_dir),
        "model_weights_sha256": sha(model_dir / "model.safetensors"),
        "dataset_manifest_sha256": sha(DATA / "manifest.json"),
        "train_parquet_sha256": data_manifest["files"]["train"]["sha256"],
        "frozen_corpus_sha256": frozen["chunks_parquet_sha256"],
        "loss": "MultipleNegativesRankingLoss", "explicit_negative_column": "negative",
        "batch_sampler": "NO_DUPLICATES", "physical_batch": args.batch_size,
        "effective_contrastive_batch": args.batch_size,
        "gradient_accumulation_steps": 1,
        "explicit_hard_negatives_per_query": 1,
        "full_batch_document_candidate_count": 2 * args.batch_size,
        "bf16": bf16, "fp16": False, "rows": len(rows), "epochs": 1,
        "learning_rate": 2e-5, "weight_decay": .01,
        "scheduler": "linear", "warmup_ratio": .05,
        "training_steps": state.global_step, "training_seconds": duration,
        "final_training_loss": result.training_loss,
        "peak_vram_reserved_bytes": peak_gpu,
        "peak_vram_allocated_bytes": torch.cuda.max_memory_allocated(),
        "available_vram_before_bytes": available_vram_before,
        "total_vram_bytes": total_gpu,
        "vram_headroom_bytes": headroom, "peak_ram_rss_bytes": peak_rss[0],
        "model_max_seq_length": saved.max_seq_length,
        "embedding_dimension": saved.get_embedding_dimension(),
        "software_versions": json.loads((TRAIN / 'reports/rag_g3_gooaq_preflight.json').read_text(encoding='utf-8'))['versions'],
        "base_snapshot_file_sha256": json.loads((TRAIN / 'reports/rag_g3_gooaq_preflight.json').read_text(encoding='utf-8'))['base_snapshot_sha256'],
        "last_logged_batch_loss": next((row['loss'] for row in reversed(state.log_history) if 'loss' in row), None),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
