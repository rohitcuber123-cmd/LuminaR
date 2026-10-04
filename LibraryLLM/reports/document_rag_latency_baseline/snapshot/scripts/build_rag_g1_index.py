"""Embed the frozen tokens_220 corpus with G1 into an isolated FAISS index."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

import faiss
import numpy as np
import psutil
import pyarrow.parquet as pq
import torch
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "datasets" / "training"
CORPUS = ROOT / "datasets" / "rag_experiments" / "chunking_v1" / "tokens_220"
OUT = TRAIN / "evaluation_indexes" / "minilm_g1_msmarco_50k"
MODEL = TRAIN / "models" / "minilm_g1_msmarco_50k_full"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    frozen = json.loads((TRAIN / "manifests" / "control_v1.json").read_text(encoding="utf-8"))
    if sha(CORPUS / "chunks.parquet") != frozen["chunks_parquet_sha256"]:
        raise RuntimeError("Frozen corpus changed")
    full = json.loads((TRAIN / "manifests" / "minilm_g1_msmarco_50k_full.json").read_text(encoding="utf-8"))
    if sha(MODEL / "model.safetensors") != full["model_weights_sha256"]:
        raise RuntimeError("G1 model hash changed")
    if OUT.exists():
        raise FileExistsError("G1 evaluation index exists; will not overwrite")
    rows = pq.read_table(CORPUS / "chunks.parquet", columns=["work_id", "text"]).to_pylist()
    if len(rows) != 16_895:
        raise RuntimeError("Frozen corpus count changed")
    model = SentenceTransformer(str(MODEL), device="cuda" if torch.cuda.is_available() else "cpu",
                                local_files_only=True)
    if model.max_seq_length != 256 or model.get_embedding_dimension() != 384:
        raise RuntimeError("G1 model architecture/window changed")
    vectors = np.empty((len(rows), 384), dtype=np.float32)
    started = time.perf_counter()
    peak_rss = psutil.Process().memory_info().rss
    for start in range(0, len(rows), 32):
        if psutil.virtual_memory().available < 1.5 * 1024**3:
            raise MemoryError("RAM headroom below 1.5 GiB")
        texts = [r["text"] for r in rows[start:start + 32]]
        vectors[start:start + len(texts)] = model.encode(
            texts, batch_size=32, normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False)
        peak_rss = max(peak_rss, psutil.Process().memory_info().rss)
        if start % 3200 == 0:
            print(f"encoded {min(start + 32, len(rows))}/{len(rows)}", flush=True)
    norms = np.linalg.norm(vectors, axis=1)
    if not np.isfinite(vectors).all() or not np.allclose(norms, 1, atol=1e-4):
        raise RuntimeError("G1 embeddings invalid or unnormalized")
    OUT.mkdir(parents=True)
    (OUT / "books").mkdir()
    np.save(OUT / "embeddings.npy", vectors)
    global_index = faiss.IndexFlatIP(384)
    global_index.add(vectors)
    faiss.write_index(global_index, str(OUT / "faiss.index"))
    positions = {}
    for i, row in enumerate(rows):
        positions.setdefault(row["work_id"], []).append(i)
    for wid, locs in positions.items():
        idx = faiss.IndexFlatIP(384)
        idx.add(vectors[np.asarray(locs, dtype=int)])
        faiss.write_index(idx, str(OUT / "books" / f"{wid}.index"))
    manifest = {
        "experiment": "G1_MS_MARCO", "frozen_corpus_sha256": frozen["chunks_parquet_sha256"],
        "model_weights_sha256": full["model_weights_sha256"],
        "embedding_shape": list(vectors.shape), "dimension": 384,
        "faiss_type": "IndexFlatIP", "index_count": global_index.ntotal,
        "book_count": len(positions), "norm_min": float(norms.min()),
        "norm_max": float(norms.max()), "embeddings_sha256": sha(OUT / "embeddings.npy"),
        "index_sha256": sha(OUT / "faiss.index"),
        "build_seconds": time.perf_counter() - started,
        "peak_process_rss_bytes": peak_rss,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
