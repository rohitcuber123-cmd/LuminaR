"""
AstraLib — HNSW Performance Benchmark

Benchmarks the HNSW index in isolation (no model loading, no DuckDB).
Optionally computes recall against the exact IndexFlatIP baseline.
"""

import argparse
import faiss
import numpy as np
import os
import sys
import time
from tqdm import tqdm


def _load_index(index_path: str):
    if not os.path.exists(index_path):
        print(f"Error: Index not found: {index_path}", file=sys.stderr)
        sys.exit(1)
    return faiss.read_index(index_path)


def _prepare_queries(embeddings_path: str, n_queries: int, seed: int = 42):
    if not os.path.exists(embeddings_path):
        print(f"Error: Embeddings not found: {embeddings_path}", file=sys.stderr)
        sys.exit(1)

    embeddings = np.load(embeddings_path, mmap_mode="r")
    rng = np.random.RandomState(seed)
    indices = rng.choice(embeddings.shape[0], size=n_queries, replace=False)

    queries = []
    for idx in indices:
        vec = np.ascontiguousarray(embeddings[idx : idx + 1], dtype=np.float32)
        queries.append(vec)

    return queries


def _benchmark_latency(index, queries, top_k):
    latencies = []
    for q in tqdm(queries, desc=f"  top_k={top_k}", leave=False, unit="q", ncols=80):
        t0 = time.perf_counter()
        index.search(q, top_k)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)  # ms
    return np.array(latencies)


def _print_latency_block(latencies):
    avg = np.mean(latencies)
    print(f"Average     : {avg:.2f} ms")
    print(f"Median      : {np.median(latencies):.2f} ms")
    print(f"P95         : {np.percentile(latencies, 95):.2f} ms")
    print(f"Minimum     : {np.min(latencies):.2f} ms")
    print(f"Maximum     : {np.max(latencies):.2f} ms")
    print(f"QPS         : {1000.0 / avg:.2f}" if avg > 0 else "QPS         : N/A")
    print()


# ── main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Benchmark HNSW FAISS index performance"
    )
    parser.add_argument("--index-dir", required=True, type=str, help="HNSW index directory")
    parser.add_argument("--embeddings", required=True, type=str, help="Embeddings .npy file")
    parser.add_argument("--queries", type=int, default=100, help="Number of queries")
    parser.add_argument("--ef-search", type=int, default=None, help="Override efSearch at search time")
    parser.add_argument("--threads", type=int, default=os.cpu_count(), help="CPU threads")

    # Recall-specific arguments
    parser.add_argument(
        "--exact-index-dir", type=str, default=None,
        help="Directory of the exact IndexFlatIP baseline (enables recall benchmark)",
    )
    parser.add_argument(
        "--top-k", type=int, default=None,
        help="Top-K for recall comparison (used with --exact-index-dir)",
    )

    args = parser.parse_args()

    if args.threads is not None:
        faiss.omp_set_num_threads(args.threads)

    # ── load HNSW index ──────────────────────────────────────────────
    hnsw_path = os.path.join(args.index_dir, "hnsw.index")
    index = _load_index(hnsw_path)

    if args.ef_search is not None:
        index.hnsw.efSearch = args.ef_search

    ef_search = index.hnsw.efSearch

    # ── prepare queries ──────────────────────────────────────────────
    queries = _prepare_queries(args.embeddings, args.queries)

    # ── warm up ──────────────────────────────────────────────────────
    _ = index.search(queries[0], 10)

    # ── header ───────────────────────────────────────────────────────
    print("=" * 70)
    print("ASTRALIB - HNSW PERFORMANCE BENCHMARK")
    print("=" * 70)
    print()
    print("Index:")
    print("  Type       : IndexHNSWFlat")
    print(f"  Vectors    : {index.ntotal:,}")
    print(f"  Dimension  : {index.d}")
    print("  Metric     : Inner Product")
    print(f"  M          : 32")
    print(f"  efSearch   : {ef_search}")
    print()
    print(f"Queries     : {args.queries}")
    print(f"Threads     : {args.threads}")
    print()

    # ── latency benchmark ────────────────────────────────────────────
    top_ks = [10, 50, 100]
    for top_k in top_ks:
        print("=" * 70)
        print(f"TOP-K = {top_k}")
        print("=" * 70)
        print()
        latencies = _benchmark_latency(index, queries, top_k)
        _print_latency_block(latencies)

    # ── recall benchmark (optional) ──────────────────────────────────
    if args.exact_index_dir is not None:
        recall_k = args.top_k if args.top_k is not None else 10

        exact_path = os.path.join(args.exact_index_dir, "faiss.index")
        exact_index = _load_index(exact_path)

        print("=" * 70)
        print("HNSW VS EXACT RECALL")
        print("=" * 70)
        print()
        print(f"Queries : {args.queries}")
        print(f"Top-K   : {recall_k}")
        print()

        recalls = []
        exact_latencies = []
        hnsw_latencies = []

        for q in tqdm(queries, desc="  Recall", leave=False, unit="q", ncols=80):
            # exact
            t0 = time.perf_counter()
            _, exact_ids = exact_index.search(q, recall_k)
            t1 = time.perf_counter()
            exact_latencies.append((t1 - t0) * 1000.0)

            # hnsw
            t0 = time.perf_counter()
            _, hnsw_ids = index.search(q, recall_k)
            t1 = time.perf_counter()
            hnsw_latencies.append((t1 - t0) * 1000.0)

            exact_set = set(exact_ids[0].tolist())
            hnsw_set = set(hnsw_ids[0].tolist())
            recall = len(exact_set & hnsw_set) / recall_k
            recalls.append(recall)

        recalls = np.array(recalls) * 100.0  # percent
        exact_latencies = np.array(exact_latencies)
        hnsw_latencies = np.array(hnsw_latencies)

        print(f"Average Recall : {np.mean(recalls):.2f}%")
        print(f"Minimum Recall : {np.min(recalls):.2f}%")
        print(f"Median Recall  : {np.median(recalls):.2f}%")
        print(f"P95 Recall     : {np.percentile(recalls, 95):.2f}%")
        print()

        exact_avg = np.mean(exact_latencies)
        hnsw_avg = np.mean(hnsw_latencies)
        speedup = exact_avg / hnsw_avg if hnsw_avg > 0 else float("inf")

        print(f"Exact IndexFlatIP : {exact_avg:.2f} ms")
        print(f"HNSW              : {hnsw_avg:.2f} ms")
        print()
        print(f"Speedup           : {speedup:.1f}x")
        print()
        print("=" * 70)


if __name__ == "__main__":
    main()
