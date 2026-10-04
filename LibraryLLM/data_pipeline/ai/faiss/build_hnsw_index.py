"""
AstraLib — Build HNSW FAISS Index

Builds an IndexHNSWFlat from pre-computed, normalized all-MiniLM-L6-v2
embeddings.  The resulting index is written to a *separate* directory so
the production IndexFlatIP baseline is never touched.

Memory:  embeddings are memory-mapped; only one 100 000-vector chunk
         is materialised at a time (~146 MB).
"""

import argparse
import faiss
import json
import numpy as np
import os
import sys
import time
from datetime import datetime, timezone
from tqdm import tqdm


# ── helpers ──────────────────────────────────────────────────────────

def _validate_inputs(embeddings_path: str, work_ids_path: str):
    """Run all pre-build sanity checks.  Returns (embeddings_mmap, work_ids)."""

    # 1 & 2 — existence
    if not os.path.exists(embeddings_path):
        print(f"Error: Embeddings file not found: {embeddings_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(work_ids_path):
        print(f"Error: Work-IDs file not found: {work_ids_path}", file=sys.stderr)
        sys.exit(1)

    # 3 — mmap load
    embeddings = np.load(embeddings_path, mmap_mode="r")
    work_ids = np.load(work_ids_path, allow_pickle=True)

    # 4 — shape / dtype
    if embeddings.ndim != 2:
        print(f"Error: embeddings.ndim == {embeddings.ndim}, expected 2", file=sys.stderr)
        sys.exit(1)
    if embeddings.shape[1] != 384:
        print(f"Error: embeddings dimension == {embeddings.shape[1]}, expected 384", file=sys.stderr)
        sys.exit(1)
    if embeddings.dtype != np.float32:
        print(f"Error: embeddings dtype == {embeddings.dtype}, expected float32", file=sys.stderr)
        sys.exit(1)

    # 5 — count match
    if embeddings.shape[0] != work_ids.shape[0]:
        print(
            f"Error: embeddings count ({embeddings.shape[0]:,}) != "
            f"work_ids count ({work_ids.shape[0]:,})",
            file=sys.stderr,
        )
        sys.exit(1)

    # 6 — NaN / Inf sample check (first + last 1000)
    sample_indices = list(range(min(1000, embeddings.shape[0]))) + list(
        range(max(0, embeddings.shape[0] - 1000), embeddings.shape[0])
    )
    sample = np.ascontiguousarray(embeddings[sample_indices], dtype=np.float32)
    if np.any(np.isnan(sample)):
        print("Error: NaN detected in embedding sample", file=sys.stderr)
        sys.exit(1)
    if np.any(np.isinf(sample)):
        print("Error: Inf detected in embedding sample", file=sys.stderr)
        sys.exit(1)

    # 7 — normalization sample check
    norms = np.linalg.norm(sample, axis=1)
    if not np.allclose(norms, 1.0, atol=1e-4):
        print(
            f"Warning: Embeddings may not be normalized. "
            f"Norm range: [{norms.min():.6f}, {norms.max():.6f}]"
        )

    # 8 & 9 — work IDs integrity
    if work_ids.size == 0:
        print("Error: work_ids array is empty", file=sys.stderr)
        sys.exit(1)

    first_ids = work_ids[:5]
    last_ids = work_ids[-5:]
    print(f"  First work IDs : {list(first_ids)}")
    print(f"  Last work IDs  : {list(last_ids)}")

    for wid in list(first_ids) + list(last_ids):
        if not str(wid).strip():
            print("Error: Found empty work ID", file=sys.stderr)
            sys.exit(1)

    return embeddings, work_ids


# ── main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Build an HNSW FAISS index from pre-computed embeddings"
    )
    parser.add_argument(
        "--embeddings", required=True, type=str,
        help="Path to embeddings .npy file",
    )
    parser.add_argument(
        "--work-ids", required=True, type=str,
        help="Path to work_ids .npy file",
    )
    parser.add_argument(
        "--output-dir", required=True, type=str,
        help="Directory for HNSW output files",
    )
    parser.add_argument("--m", type=int, default=32, help="HNSW M parameter (default: 32)")
    parser.add_argument(
        "--ef-construction", type=int, default=200,
        help="HNSW efConstruction (default: 200)",
    )
    parser.add_argument(
        "--ef-search", type=int, default=64,
        help="HNSW efSearch default (default: 64)",
    )
    parser.add_argument(
        "--chunk-size", type=int, default=100_000,
        help="Vectors per insertion chunk (default: 100000)",
    )

    args = parser.parse_args()

    # Legacy offline builder may only create a new corpus directory. The live
    # manager treats its base as immutable and publishes versioned snapshots.
    if any(os.path.exists(os.path.join(args.output_dir, name)) for name in
           ("hnsw.index", "active_index.json", "sync_queue.sqlite3")):
        parser.error("Output already contains a catalogue index. Use a fresh output directory, "
                     "or python -m search.maintenance rebuild for the live index.")

    print("=" * 70)
    print("ASTRALIB — BUILD HNSW INDEX")
    print("=" * 70)
    print()

    # ── validate ─────────────────────────────────────────────────────
    print("Validating inputs …")
    embeddings, work_ids = _validate_inputs(args.embeddings, args.work_ids)

    n_vectors = embeddings.shape[0]
    dimension = embeddings.shape[1]

    print(f"  Vectors    : {n_vectors:,}")
    print(f"  Dimension  : {dimension}")
    print(f"  Dtype      : {embeddings.dtype}")
    print()

    # ── create index ─────────────────────────────────────────────────
    print("Creating IndexHNSWFlat …")
    print(f"  M              : {args.m}")
    print(f"  efConstruction : {args.ef_construction}")
    print(f"  efSearch       : {args.ef_search}")
    print()

    index = faiss.IndexHNSWFlat(dimension, args.m, faiss.METRIC_INNER_PRODUCT)
    index.hnsw.efConstruction = args.ef_construction
    index.hnsw.efSearch = args.ef_search

    # ── add vectors in chunks ────────────────────────────────────────
    print("Adding vectors …")
    t_start = time.perf_counter()

    chunk_size = args.chunk_size
    n_chunks = (n_vectors + chunk_size - 1) // chunk_size

    for i in tqdm(range(n_chunks), desc="Chunks", unit="chunk", ncols=80):
        start = i * chunk_size
        end = min(start + chunk_size, n_vectors)
        chunk = np.ascontiguousarray(embeddings[start:end], dtype=np.float32)
        index.add(chunk)

    t_build = time.perf_counter() - t_start
    print(f"\nBuild time: {t_build:.1f}s  ({t_build / 60:.1f} min)")
    print(f"Index ntotal: {index.ntotal:,}")
    print()

    if index.ntotal != n_vectors:
        print(
            f"Error: index.ntotal ({index.ntotal:,}) != expected ({n_vectors:,})",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── save ─────────────────────────────────────────────────────────
    os.makedirs(args.output_dir, exist_ok=True)

    index_path = os.path.join(args.output_dir, "hnsw.index")
    ids_path = os.path.join(args.output_dir, "index_work_ids.npy")
    meta_path = os.path.join(args.output_dir, "hnsw_metadata.json")

    print(f"Saving index   → {index_path}")
    faiss.write_index(index, index_path)

    print(f"Saving work IDs → {ids_path}")
    np.save(ids_path, work_ids)

    metadata = {
        "index_type": "IndexHNSWFlat",
        "metric": "inner_product",
        "dimension": dimension,
        "vector_count": int(n_vectors),
        "m": args.m,
        "ef_construction": args.ef_construction,
        "ef_search": args.ef_search,
        "model_name": "all-MiniLM-L6-v2",
        "normalized": True,
        "source_embeddings": os.path.abspath(args.embeddings),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "build_time_seconds": round(t_build, 2),
    }
    print(f"Saving metadata → {meta_path}")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print()

    # ── reload verification ──────────────────────────────────────────
    print("Reload verification …")
    reloaded = faiss.read_index(index_path)

    assert reloaded.ntotal == n_vectors, (
        f"Reloaded ntotal {reloaded.ntotal:,} != {n_vectors:,}"
    )
    assert reloaded.d == dimension, (
        f"Reloaded dimension {reloaded.d} != {dimension}"
    )

    # Quick search sanity
    q = np.ascontiguousarray(embeddings[0:1], dtype=np.float32)
    distances, indices = reloaded.search(q, 10)
    print(f"  ntotal   : {reloaded.ntotal:,}")
    print(f"  dimension: {reloaded.d}")
    print(f"  Search OK: top-10 indices = {indices[0].tolist()}")
    print()

    index_size_mb = os.path.getsize(index_path) / (1024 * 1024)
    print(f"Index size : {index_size_mb:,.1f} MB")
    print()
    print("=" * 70)
    print("HNSW INDEX BUILD COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
