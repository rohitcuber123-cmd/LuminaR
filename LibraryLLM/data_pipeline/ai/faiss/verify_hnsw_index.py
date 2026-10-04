"""
AstraLib — Verify HNSW Index

Validates that the HNSW index, work-ID mapping, and metadata file are
present and internally consistent.
"""

import argparse
import faiss
import json
import numpy as np
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Verify HNSW FAISS index")
    parser.add_argument("--index-dir", required=True, type=str, help="HNSW index directory")
    parser.add_argument(
        "--embeddings", type=str, default=None,
        help="Original embeddings .npy for self-search sanity check",
    )

    args = parser.parse_args()

    passed = 0
    failed = 0

    def check(label: str, ok: bool, detail: str = ""):
        nonlocal passed, failed
        status = "PASS" if ok else "FAIL"
        msg = f"  [{status}] {label}"
        if detail:
            msg += f"  —  {detail}"
        print(msg)
        if ok:
            passed += 1
        else:
            failed += 1

    print("=" * 70)
    print("ASTRALIB — VERIFY HNSW INDEX")
    print("=" * 70)
    print()

    index_path = os.path.join(args.index_dir, "hnsw.index")
    ids_path = os.path.join(args.index_dir, "index_work_ids.npy")
    meta_path = os.path.join(args.index_dir, "hnsw_metadata.json")

    # 1 — files exist
    check("hnsw.index exists", os.path.exists(index_path), index_path)
    check("index_work_ids.npy exists", os.path.exists(ids_path), ids_path)
    check("hnsw_metadata.json exists", os.path.exists(meta_path), meta_path)

    if not os.path.exists(index_path):
        print("\nCannot continue without hnsw.index.")
        sys.exit(1)

    # 4 — FAISS loads
    try:
        index = faiss.read_index(index_path)
        check("FAISS index loads", True)
    except Exception as e:
        check("FAISS index loads", False, str(e))
        sys.exit(1)

    # 5 — ntotal
    check("ntotal == 5,000,000", index.ntotal == 5_000_000, f"ntotal={index.ntotal:,}")

    # 6 — dimension
    check("dimension == 384", index.d == 384, f"d={index.d}")

    # 7 — metric
    metric_ok = index.metric_type == faiss.METRIC_INNER_PRODUCT
    check("Metric is inner product", metric_ok, f"metric_type={index.metric_type}")

    # work IDs
    if os.path.exists(ids_path):
        work_ids = np.load(ids_path, allow_pickle=True)

        # 8 — count match
        check(
            "work_id count == ntotal",
            work_ids.shape[0] == index.ntotal,
            f"{work_ids.shape[0]:,} vs {index.ntotal:,}",
        )

        # 9 — no empty IDs
        empty_count = sum(1 for wid in work_ids[:1000] if not str(wid).strip())
        check("No empty work IDs (sample)", empty_count == 0, f"empty={empty_count}")
    else:
        work_ids = None

    # metadata
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        check("Metadata is valid JSON", True)
        check(
            "Metadata index_type",
            meta.get("index_type") == "IndexHNSWFlat",
            meta.get("index_type", "missing"),
        )
        check(
            "Metadata vector_count",
            meta.get("vector_count") == index.ntotal,
            f"{meta.get('vector_count')} vs {index.ntotal}",
        )

    # 10 — self-search sanity
    if args.embeddings is not None and os.path.exists(args.embeddings):
        print()
        print("Self-search sanity check …")
        embeddings = np.load(args.embeddings, mmap_mode="r")
        q = np.ascontiguousarray(embeddings[0:1], dtype=np.float32)
        distances, indices = index.search(q, 10)

        top_indices = indices[0].tolist()
        top_scores = distances[0].tolist()

        if 0 in top_indices:
            rank = top_indices.index(0) + 1
            check("Self-search: index 0 found in top-10", True, f"rank={rank}")
        else:
            check(
                "Self-search: index 0 found in top-10",
                False,
                f"top-10 indices={top_indices}",
            )

        print(f"  Top-10 indices : {top_indices}")
        print(f"  Top-10 scores  : {[f'{s:.4f}' for s in top_scores]}")

    # ── summary ──────────────────────────────────────────────────────
    print()
    print("-" * 70)
    total = passed + failed
    print(f"Results: {passed}/{total} passed, {failed}/{total} failed")
    if failed > 0:
        print("STATUS: ISSUES DETECTED")
        sys.exit(1)
    else:
        print("STATUS: ALL CHECKS PASSED")
    print("-" * 70)


if __name__ == "__main__":
    main()
