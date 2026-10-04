"""
LuminaR — Production Pipeline Benchmark

Measures the exact operations used by the production search pipeline
independently, after all models/indexes are loaded and warmed.

Stages:
    1. MiniLM query embedding
    2. HNSW Top-50 retrieval
    3. Top-50 reranking metadata lookup
    4. Cross-Encoder pair construction
    5. L6 Cross-Encoder reranking
    6. Top-10 final metadata lookup
    7. End-to-end total

Run from:
    D:\SDC\LibraryLLM

Command:
    python data_pipeline\ai\faiss\benchmark_production_pipeline.py
"""

import os
import sys
import time
import statistics

import faiss
import numpy as np
import torch

from sentence_transformers import SentenceTransformer, CrossEncoder


# ================================================================
# PATHS
# ================================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )
    )
)

HNSW_INDEX_DIR = os.path.join(
    BASE_DIR,
    "datasets",
    "ai",
    "faiss",
    "hnsw"
)

METADATA_DB = os.path.join(
    BASE_DIR,
    "datasets",
    "ai",
    "metadata",
    "book_metadata.duckdb"
)

METADATA_DIR = os.path.join(
    BASE_DIR,
    "data_pipeline",
    "ai",
    "metadata"
)

if METADATA_DIR not in sys.path:
    sys.path.insert(0, METADATA_DIR)

from metadata_store import MetadataStore


# ================================================================
# CONFIGURATION
# ================================================================

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

QUERY = "books for learning deep learning and neural networks"

HNSW_TOP_K = 50
FINAL_TOP_K = 10
EF_SEARCH = 128
RERANK_BATCH_SIZE = 16

WARMUP_ITERATIONS = 5
BENCHMARK_ITERATIONS = 20


# ================================================================
# HELPERS
# ================================================================

def cuda_sync():
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def stats(values):
    values = np.asarray(values, dtype=np.float64)

    return {
        "average": float(np.mean(values)),
        "median": float(np.median(values)),
        "p95": float(np.percentile(values, 95)),
        "minimum": float(np.min(values)),
        "maximum": float(np.max(values)),
    }


def print_stats(name, values):
    s = stats(values)

    print(f"\n{name}")
    print(f"  Average : {s['average']:8.2f} ms")
    print(f"  Median  : {s['median']:8.2f} ms")
    print(f"  P95     : {s['p95']:8.2f} ms")
    print(f"  Minimum : {s['minimum']:8.2f} ms")
    print(f"  Maximum : {s['maximum']:8.2f} ms")


# ================================================================
# MAIN
# ================================================================

def main():

    print("=" * 70)
    print("LUMINAR — PRODUCTION PIPELINE BENCHMARK")
    print("=" * 70)

    device = (
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print()
    print(f"Device       : {device}")

    if device == "cuda":
        print(
            f"GPU          : "
            f"{torch.cuda.get_device_name(0)}"
        )

    print(f"Query        : {QUERY}")
    print(f"HNSW Top-K   : {HNSW_TOP_K}")
    print(f"Final Top-K  : {FINAL_TOP_K}")
    print(f"efSearch     : {EF_SEARCH}")
    print(f"Iterations   : {BENCHMARK_ITERATIONS}")

    # ------------------------------------------------------------
    # Load HNSW
    # ------------------------------------------------------------

    index_path = os.path.join(
        HNSW_INDEX_DIR,
        "hnsw.index"
    )

    ids_path = os.path.join(
        HNSW_INDEX_DIR,
        "index_work_ids.npy"
    )

    print()
    print("Loading HNSW index...")

    start = time.perf_counter()

    index = faiss.read_index(index_path)

    work_ids = np.load(
        ids_path,
        allow_pickle=True
    )

    index.hnsw.efSearch = EF_SEARCH

    index_load_time = (
        time.perf_counter() - start
    ) * 1000

    print(
        f"Vectors      : {index.ntotal:,}"
    )
    print(
        f"Dimension    : {index.d}"
    )
    print(
        f"efSearch     : {index.hnsw.efSearch}"
    )
    print(
        f"Index load   : {index_load_time:.2f} ms"
    )

    # ------------------------------------------------------------
    # Load MiniLM
    # ------------------------------------------------------------

    print()
    print("Loading MiniLM...")

    start = time.perf_counter()

    embedding_model = SentenceTransformer(
        EMBEDDING_MODEL,
        device=device
    )

    cuda_sync()

    print(
        f"Model load   : "
        f"{(time.perf_counter() - start) * 1000:.2f} ms"
    )

    print("Warming MiniLM...")

    for _ in range(WARMUP_ITERATIONS):
        embedding_model.encode(
            [QUERY],
            convert_to_numpy=True
        )

    cuda_sync()

    print("MiniLM warm-up complete.")

    # ------------------------------------------------------------
    # Load reranker
    # ------------------------------------------------------------

    print()
    print("Loading L6 reranker...")

    start = time.perf_counter()

    reranker = CrossEncoder(
        RERANKER_MODEL,
        device=device
    )

    cuda_sync()

    print(
        f"Model load   : "
        f"{(time.perf_counter() - start) * 1000:.2f} ms"
    )

    print("Warming reranker...")

    warmup_pairs = [
        [
            QUERY,
            "Title: Deep Learning\n"
            "Authors: Test Author\n"
            "Subjects: Neural networks"
        ]
    ]

    for _ in range(WARMUP_ITERATIONS):
        reranker.predict(
            warmup_pairs,
            batch_size=1,
            show_progress_bar=False
        )

    cuda_sync()

    print("Reranker warm-up complete.")

    # ------------------------------------------------------------
    # MetadataStore
    # ------------------------------------------------------------

    print()
    print("Opening MetadataStore...")

    metadata_store = MetadataStore(
        METADATA_DB
    )

    print("MetadataStore ready.")

    # ------------------------------------------------------------
    # Warm complete pipeline
    # ------------------------------------------------------------

    print()
    print("=" * 70)
    print("PIPELINE WARM-UP")
    print("=" * 70)

    for _ in range(WARMUP_ITERATIONS):

        query_vector = embedding_model.encode(
            [QUERY],
            convert_to_numpy=True
        )

        query_vector = np.asarray(
            query_vector,
            dtype=np.float32
        )

        faiss.normalize_L2(query_vector)

        distances, indices = index.search(
            query_vector,
            HNSW_TOP_K
        )

        candidates = []

        for score, idx in zip(
            distances[0],
            indices[0]
        ):

            if idx < 0:
                continue

            candidates.append(
                {
                    "work_id": str(work_ids[idx]),
                    "hnsw_score": float(score)
                }
            )

        candidate_ids = [
            c["work_id"]
            for c in candidates
        ]

        text_metadata = (
            metadata_store
            .get_rerank_text_by_work_ids(
                candidate_ids
            )
        )

        pairs = []

        for candidate in candidates:

            meta = text_metadata.get(
                candidate["work_id"],
                {}
            )

            book_text = (
                f"Title: {str(meta.get('title', ''))}\n"
                f"Authors: {str(meta.get('authors', ''))}\n"
                f"Subjects: {str(meta.get('subjects', ''))}"
            )

            pairs.append(
                [QUERY, book_text]
            )

        rerank_scores = reranker.predict(
            pairs,
            batch_size=RERANK_BATCH_SIZE,
            show_progress_bar=False
        )

        ranked = list(
            zip(
                candidates,
                rerank_scores
            )
        )

        ranked.sort(
            key=lambda x: float(x[1]),
            reverse=True
        )

        final_ids = [
            item[0]["work_id"]
            for item in ranked[:FINAL_TOP_K]
        ]

        metadata_store.get_by_work_ids(
            final_ids
        )

    cuda_sync()

    print("Pipeline warm-up complete.")

    # ------------------------------------------------------------
    # Benchmark arrays
    # ------------------------------------------------------------

    embedding_times = []
    hnsw_times = []
    candidate_metadata_times = []
    pair_build_times = []
    reranking_times = []
    final_metadata_times = []
    total_times = []

    # ------------------------------------------------------------
    # Benchmark
    # ------------------------------------------------------------

    print()
    print("=" * 70)
    print("BENCHMARK")
    print("=" * 70)

    for iteration in range(
        BENCHMARK_ITERATIONS
    ):

        # ========================================================
        # 1. Embedding
        # ========================================================

        cuda_sync()

        start_total = time.perf_counter()

        start = time.perf_counter()

        query_vector = embedding_model.encode(
            [QUERY],
            convert_to_numpy=True
        )

        cuda_sync()

        embedding_time = (
            time.perf_counter() - start
        ) * 1000

        query_vector = np.asarray(
            query_vector,
            dtype=np.float32
        )

        faiss.normalize_L2(
            query_vector
        )

        # ========================================================
        # 2. HNSW
        # ========================================================

        start = time.perf_counter()

        distances, indices = index.search(
            query_vector,
            HNSW_TOP_K
        )

        hnsw_time = (
            time.perf_counter() - start
        ) * 1000

        candidates = []

        for score, idx in zip(
            distances[0],
            indices[0]
        ):

            if idx < 0:
                continue

            candidates.append(
                {
                    "work_id": str(
                        work_ids[idx]
                    ),
                    "hnsw_score": float(score)
                }
            )

        candidate_ids = [
            c["work_id"]
            for c in candidates
        ]

        # ========================================================
        # 3. Candidate metadata
        # ========================================================

        start = time.perf_counter()

        text_metadata = (
            metadata_store
            .get_rerank_text_by_work_ids(
                candidate_ids
            )
        )

        candidate_metadata_time = (
            time.perf_counter() - start
        ) * 1000

        # ========================================================
        # 4. Pair construction
        # ========================================================

        start = time.perf_counter()

        pairs = []

        for candidate in candidates:

            meta = text_metadata.get(
                candidate["work_id"],
                {}
            )

            book_text = (
                f"Title: {str(meta.get('title', ''))}\n"
                f"Authors: {str(meta.get('authors', ''))}\n"
                f"Subjects: {str(meta.get('subjects', ''))}"
            )

            pairs.append(
                [QUERY, book_text]
            )

        pair_build_time = (
            time.perf_counter() - start
        ) * 1000

        # ========================================================
        # 5. Reranking
        # ========================================================

        cuda_sync()

        start = time.perf_counter()

        rerank_scores = reranker.predict(
            pairs,
            batch_size=RERANK_BATCH_SIZE,
            show_progress_bar=False
        )

        cuda_sync()

        reranking_time = (
            time.perf_counter() - start
        ) * 1000

        ranked = list(
            zip(
                candidates,
                rerank_scores
            )
        )

        ranked.sort(
            key=lambda x: float(x[1]),
            reverse=True
        )

        # ========================================================
        # 6. Final metadata
        # ========================================================

        final_ids = [
            item[0]["work_id"]
            for item in ranked[:FINAL_TOP_K]
        ]

        start = time.perf_counter()

        metadata_store.get_by_work_ids(
            final_ids
        )

        final_metadata_time = (
            time.perf_counter() - start
        ) * 1000

        # ========================================================
        # Total
        # ========================================================

        total_time = (
            time.perf_counter()
            - start_total
        ) * 1000

        embedding_times.append(
            embedding_time
        )
        hnsw_times.append(
            hnsw_time
        )
        candidate_metadata_times.append(
            candidate_metadata_time
        )
        pair_build_times.append(
            pair_build_time
        )
        reranking_times.append(
            reranking_time
        )
        final_metadata_times.append(
            final_metadata_time
        )
        total_times.append(
            total_time
        )

        print(
            f"[{iteration + 1:02d}/"
            f"{BENCHMARK_ITERATIONS}] "
            f"Total: {total_time:8.2f} ms"
        )

    # ------------------------------------------------------------
    # Results
    # ------------------------------------------------------------

    print()
    print("=" * 70)
    print("PRODUCTION PIPELINE RESULTS")
    print("=" * 70)

    print_stats(
        "1. Query Embedding",
        embedding_times
    )

    print_stats(
        "2. HNSW Top-50",
        hnsw_times
    )

    print_stats(
        "3. Candidate Metadata Top-50",
        candidate_metadata_times
    )

    print_stats(
        "4. Pair Construction",
        pair_build_times
    )

    print_stats(
        "5. L6 Reranking Top-50",
        reranking_times
    )

    print_stats(
        "6. Final Metadata Top-10",
        final_metadata_times
    )

    print_stats(
        "7. COMPLETE PIPELINE",
        total_times
    )

    # ------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(
        f"Embedding        : "
        f"{np.mean(embedding_times):8.2f} ms"
    )

    print(
        f"HNSW             : "
        f"{np.mean(hnsw_times):8.2f} ms"
    )

    print(
        f"Candidate Meta    : "
        f"{np.mean(candidate_metadata_times):8.2f} ms"
    )

    print(
        f"Pair Build        : "
        f"{np.mean(pair_build_times):8.2f} ms"
    )

    print(
        f"Reranking         : "
        f"{np.mean(reranking_times):8.2f} ms"
    )

    print(
        f"Final Meta        : "
        f"{np.mean(final_metadata_times):8.2f} ms"
    )

    print(
        f"TOTAL             : "
        f"{np.mean(total_times):8.2f} ms"
    )

    print()
    print(
        "The component timings above are measured independently."
    )
    print(
        "Startup/model/index loading is excluded from query latency."
    )

    metadata_store.close()

    print()
    print("Benchmark complete.")


if __name__ == "__main__":
    main()
