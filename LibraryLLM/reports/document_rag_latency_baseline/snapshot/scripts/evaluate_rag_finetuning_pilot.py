"""Build an isolated IndexFlatIP for a trained encoder and compare DEV raw dense."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time

import faiss
import numpy as np
import psutil
import pyarrow.parquet as pq
import torch
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evaluate_rag_chunk_variants import evaluate_variant

TRAIN = ROOT / "datasets" / "training"
CONTROL = ROOT / "datasets" / "rag_experiments" / "chunking_v1" / "tokens_220"
LABELS = ROOT / "rag" / "evaluation" / "rag_retrieval_eval_v1.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(model, folder, control):
    if folder.exists():
        raise RuntimeError("Isolated index already exists; will not overwrite")
    folder.mkdir(parents=True)
    (folder / "books").mkdir()
    rows = pq.read_table(CONTROL / "chunks.parquet", columns=["work_id", "text"]).to_pylist()
    vectors = np.empty((len(rows), 384), dtype="float32")
    started = time.perf_counter()
    peak_rss = psutil.Process().memory_info().rss
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    for first in range(0, len(rows), 32):
        if psutil.virtual_memory().available < 1.5 * 1024**3:
            raise MemoryError("RAM safety threshold reached")
        batch = [r["text"] for r in rows[first:first + 32]]
        vectors[first:first + len(batch)] = model.encode(batch, batch_size=32,
                                                        normalize_embeddings=True,
                                                        convert_to_numpy=True,
                                                        show_progress_bar=False)
        peak_rss = max(peak_rss, psutil.Process().memory_info().rss)
        if first // 32 % 100 == 0:
            print(f"embedded {min(first+32, len(rows))}/{len(rows)}", flush=True)
    norms = np.linalg.norm(vectors, axis=1)
    if not np.isfinite(vectors).all() or not np.allclose(norms, 1, atol=1e-4):
        raise RuntimeError("Invalid embedding normalization")
    global_index = faiss.IndexFlatIP(384)
    global_index.add(vectors)
    faiss.write_index(global_index, str(folder / "faiss.index"))
    positions = {}
    for i, row in enumerate(rows):
        positions.setdefault(row["work_id"], []).append(i)
    for wid, subset in positions.items():
        index = faiss.IndexFlatIP(384)
        index.add(vectors[np.asarray(subset, dtype=int)])
        faiss.write_index(index, str(folder / "books" / f"{wid}.index"))
    manifest = {"control_sha256": control["chunks_parquet_sha256"],
                "model_path": str(TRAIN / "models" / "minilm_generic_pilot_v1"),
                "model_manifest_sha256": sha(TRAIN / "manifests" / "minilm_generic_pilot_v1.json"),
                "embedding_count": len(rows), "dimension": 384,
                "faiss_type": "IndexFlatIP", "normalized_min": float(norms.min()),
                "normalized_max": float(norms.max()), "book_count": len(positions),
                "index_sha256": sha(folder / "faiss.index"),
                "build_seconds": time.perf_counter() - started,
                "peak_process_rss_bytes": peak_rss,
                "peak_gpu_allocated_bytes": torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main():
    control = json.loads((TRAIN / "manifests" / "control_v1.json").read_text(encoding="utf-8"))
    if sha(CONTROL / "chunks.parquet") != control["chunks_parquet_sha256"] or sha(LABELS) != control["evaluation_labels_sha256"]:
        raise RuntimeError("Frozen corpus or labels changed")
    model_path = TRAIN / "models" / "minilm_generic_pilot_v1"
    model = SentenceTransformer(str(model_path), device="cuda" if torch.cuda.is_available() else "cpu",
                                local_files_only=True)
    if model.max_seq_length != 256 or model.get_embedding_dimension() != 384:
        raise RuntimeError("Model window or dimension changed")
    folder = TRAIN / "evaluation_indexes" / "minilm_generic_pilot_v1"
    manifest = build(model, folder, control)
    questions = json.loads(LABELS.read_text(encoding="utf-8"))["questions"]
    dev = [q for q in questions if q["split"] == "DEV"]
    output = folder / "dense_dev_evaluation.json"
    summary = evaluate_variant("tokens_220", model, dev, index_folder=folder, output_file=output)
    baseline = json.loads((TRAIN / "reports" / "baseline_a_previous.json").read_text(encoding="utf-8"))
    old = {q["query_id"]: q for q in baseline["queries"]}
    current = json.loads(output.read_text(encoding="utf-8"))
    changes = []
    for row in current["queries"]:
        prior = old[row["query_id"]]["metrics"]
        now = row["metrics"]
        if prior is None or now is None:
            continue
        before, after = prior["first_rank"], now["first_rank"]
        a = before if before is not None else float("inf")
        b = after if after is not None else float("inf")
        changes.append({"query_id": row["query_id"], "before_rank": before,
                        "after_rank": after,
                        "status": "IMPROVED" if b < a else "REGRESSED" if b > a else "UNCHANGED"})
    report = {"result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS",
              "pilot": True, "split": "DEV", "model": "B_GENERIC_PILOT",
              "baseline_dev_mrr": sum((1 / q["metrics"]["first_rank"] if q["metrics"]["first_rank"] else 0)
                                      for q in baseline["queries"] if q["split"] == "DEV" and q["metrics"])
                                  / sum(1 for q in baseline["queries"] if q["split"] == "DEV" and q["metrics"]),
              "model_metrics": summary["metrics"],
              "improved": sum(c["status"] == "IMPROVED" for c in changes),
              "regressed": sum(c["status"] == "REGRESSED" for c in changes),
              "unchanged": sum(c["status"] == "UNCHANGED" for c in changes),
              "recovered_top50": sum(c["before_rank"] is None and c["after_rank"] is not None for c in changes),
              "lost_top50": sum(c["before_rank"] is not None and c["after_rank"] is None for c in changes),
              "per_query": changes, "index": manifest}
    path = TRAIN / "reports" / "minilm_generic_pilot_dev_v1.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("baseline_dev_mrr", "model_metrics", "improved", "regressed", "unchanged", "recovered_top50", "lost_top50")}, indent=2))


if __name__ == "__main__":
    main()
