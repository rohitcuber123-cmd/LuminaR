"""
AstraLib — Cross-Encoder Reranker Benchmark

Pipeline:

User Query
    ↓
MiniLM embedding
    ↓
HNSW retrieval
    ↓
Top-50 candidates
    ↓
Cross-Encoder reranker
    ↓
Benchmark latency

This script DOES NOT modify:
- embeddings
- HNSW index
- FAISS index
- DuckDB database

It is benchmark-only.
"""

import os
import time
import statistics
import argparse

import faiss
import duckdb
import numpy as np
import torch

from sentence_transformers import SentenceTransformer, CrossEncoder


# ================================================================
# PATHS
# ================================================================

DEFAULT_HNSW_DIR = (
    "D:/SDC/LibraryLLM/datasets/ai/faiss/hnsw"
)

DEFAULT_METADATA_DB = (
    "D:/SDC/LibraryLLM/datasets/ai/metadata/book_metadata.duckdb"
)

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

RERANKER_MODELS = [
    "cross-encoder/ms-marco-MiniLM-L-6-v2",
    "cross-encoder/ms-marco-MiniLM-L-12-v2",
]


# ================================================================
# BENCHMARK SETTINGS
# ================================================================

CANDIDATE_K = 50

WARMUP_ITERATIONS = 10
BENCHMARK_ITERATIONS = 20

BATCH_SIZES = [16, 32, 64]

QUERIES = [
    "books for learning deep learning and neural networks",
    "a book about good habits",
    "magic and wizards",
    "books about psychology and human behavior",
    "science fiction books about space exploration",
]


# ================================================================
# HELPERS
# ================================================================

def percentile(values, p):
    return float(np.percentile(values, p))


def print_stats(times):
    return {
        "average": statistics.mean(times),
        "median": statistics.median(times),
        "p95": percentile(times, 95),
        "minimum": min(times),
        "maximum": max(times),
    }


# ================================================================
# LOAD HNSW
# ================================================================

def load_hnsw(index_dir):
    index_path = os.path.join(index_dir, "hnsw.index")
    ids_path = os.path.join(index_dir, "index_work_ids.npy")

    if not os.path.exists(index_path):
        raise FileNotFoundError(
            f"HNSW index not found: {index_path}"
        )

    if not os.path.exists(ids_path):
        raise FileNotFoundError(
            f"Work ID mapping not found: {ids_path}"
        )

    print("Loading HNSW index...")

    index = faiss.read_index(index_path)

    work_ids = np.load(
        ids_path,
        allow_pickle=True
    )

    print(f"Vectors    : {index.ntotal:,}")
    print(f"Dimension  : {index.d}")
    print(f"Work IDs   : {len(work_ids):,}")
    print(f"efSearch   : {index.hnsw.efSearch}")

    return index, work_ids


# ================================================================
# LOAD METADATA
# ================================================================

def load_metadata(db_path, work_ids):
    """
    Retrieve metadata for the HNSW candidate IDs.

    We only load metadata needed to construct reranker documents.
    """

    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Metadata DB not found: {db_path}"
        )

    print("Loading candidate metadata...")

    conn = duckdb.connect(
        db_path,
        read_only=True
    )

    unique_ids = list(dict.fromkeys(
        str(x) for x in work_ids
    ))

    placeholders = ", ".join(
        ["?"] * len(unique_ids)
    )

    query = f"""
        SELECT
            work_id,
            title,
            authors,
            subjects,
            description
        FROM books
        WHERE work_id IN ({placeholders})
    """

    try:
        rows = conn.execute(
            query,
            unique_ids
        ).fetchall()

        columns = [
            "work_id",
            "title",
            "authors",
            "subjects",
            "description"
        ]

        metadata = {}

        for row in rows:
            record = dict(zip(columns, row))

            metadata[str(record["work_id"])] = record

    finally:
        conn.close()

    print(
        f"Metadata records loaded: {len(metadata):,}"
    )

    return metadata


# ================================================================
# CREATE DOCUMENT TEXT
# ================================================================

def build_document(metadata):
    """
    Construct the text that the cross-encoder sees.

    More useful than using title alone.
    """

    title = metadata.get("title") or ""
    authors = metadata.get("authors") or ""
    subjects = metadata.get("subjects") or ""
    description = metadata.get("description") or ""

    return (
        f"Title: {title}\n"
        f"Authors: {authors}\n"
        f"Subjects: {subjects}\n"
        f"Description: {description}"
    )


# ================================================================
# GET HNSW CANDIDATES
# ================================================================

def get_candidates(
    query,
    embedding_model,
    hnsw_index,
    work_ids,
    metadata,
    top_k=50
):
    """
    Embed the query and retrieve Top-K candidates
    from HNSW.
    """

    query_vector = embedding_model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    query_vector = np.ascontiguousarray(
        query_vector.astype(np.float32)
    )

    if torch.cuda.is_available():
        torch.cuda.synchronize()

    distances, indices = hnsw_index.search(
        query_vector,
        top_k
    )

    candidates = []

    for score, idx in zip(
        distances[0],
        indices[0]
    ):
        if idx == -1:
            continue

        work_id = str(work_ids[idx])

        record = metadata.get(work_id)

        if record is None:
            continue

        document = build_document(record)

        candidates.append({
            "work_id": work_id,
            "hnsw_score": float(score),
            "text": document
        })

    return candidates


# ================================================================
# RERANK
# ================================================================

def rerank(
    model,
    query,
    candidates,
    batch_size
):
    """
    Run cross-encoder on query/document pairs.
    """

    pairs = [
        [query, candidate["text"]]
        for candidate in candidates
    ]

    scores = model.predict(
        pairs,
        batch_size=batch_size,
        show_progress_bar=False
    )

    scores = np.asarray(scores)

    for candidate, score in zip(
        candidates,
        scores
    ):
        candidate["rerank_score"] = float(score)

    ranked = sorted(
        candidates,
        key=lambda x: x["rerank_score"],
        reverse=True
    )

    return ranked


# ================================================================
# BENCHMARK ONE MODEL
# ================================================================

def benchmark_model(
    model_name,
    query,
    candidates
):

    print()
    print("=" * 70)
    print(f"MODEL: {model_name}")
    print("=" * 70)

    device = (
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print(f"Device     : {device}")
    print(f"Candidates : {len(candidates)}")

    # ------------------------------------------------------------
    # Load model
    # ------------------------------------------------------------

    print()
    print("Loading reranker...")

    load_start = time.perf_counter()

    model = CrossEncoder(
        model_name,
        device=device
    )

    if device == "cuda":
        torch.cuda.synchronize()

    load_time = (
        time.perf_counter() - load_start
    ) * 1000

    print(
        f"Model load : {load_time:.1f} ms"
    )

    # ------------------------------------------------------------
    # GPU memory
    # ------------------------------------------------------------

    if device == "cuda":

        allocated = (
            torch.cuda.memory_allocated()
            / 1024**2
        )

        reserved = (
            torch.cuda.memory_reserved()
            / 1024**2
        )

        print(
            f"GPU allocated : {allocated:.1f} MB"
        )

        print(
            f"GPU reserved  : {reserved:.1f} MB"
        )

    # ------------------------------------------------------------
    # Benchmark each batch size
    # ------------------------------------------------------------

    for batch_size in BATCH_SIZES:

        print()
        print("-" * 70)
        print(
            f"BATCH SIZE = {batch_size}"
        )
        print("-" * 70)

        # --------------------------------------------------------
        # Warm-up
        # --------------------------------------------------------

        print(
            f"Warm-up: {WARMUP_ITERATIONS} iterations..."
        )

        for _ in range(
            WARMUP_ITERATIONS
        ):

            rerank(
                model,
                query,
                candidates,
                batch_size
            )

        if device == "cuda":
            torch.cuda.synchronize()

        print("Warm-up complete.")

        # --------------------------------------------------------
        # Timed benchmark
        # --------------------------------------------------------

        times = []

        for _ in range(
            BENCHMARK_ITERATIONS
        ):

            if device == "cuda":
                torch.cuda.synchronize()

            start = time.perf_counter()

            rerank(
                model,
                query,
                candidates,
                batch_size
            )

            if device == "cuda":
                torch.cuda.synchronize()

            elapsed = (
                time.perf_counter() - start
            ) * 1000

            times.append(elapsed)

        stats = print_stats(times)

        total_candidates = (
            len(candidates)
            * BENCHMARK_ITERATIONS
        )

        total_seconds = (
            sum(times) / 1000
        )

        candidates_per_sec = (
            total_candidates
            / total_seconds
        )

        ms_per_candidate = (
            statistics.mean(times)
            / len(candidates)
        )

        print()
        print(
            f"Average : {stats['average']:.2f} ms"
        )

        print(
            f"Median  : {stats['median']:.2f} ms"
        )

        print(
            f"P95     : {stats['p95']:.2f} ms"
        )

        print(
            f"Minimum : {stats['minimum']:.2f} ms"
        )

        print(
            f"Maximum : {stats['maximum']:.2f} ms"
        )

        print()
        print(
            f"Candidates/run : {len(candidates)}"
        )

        print(
            f"ms/candidate   : {ms_per_candidate:.3f}"
        )

        print(
            f"Candidates/sec : {candidates_per_sec:.1f}"
        )

        # --------------------------------------------------------
        # Show example results
        # --------------------------------------------------------

        ranked = rerank(
            model,
            query,
            candidates,
            batch_size
        )

        print()
        print("Top 5 reranked candidates:")

        for rank, result in enumerate(
            ranked[:5],
            start=1
        ):

            print(
                f"{rank}. "
                f"{result['rerank_score']:.4f} "
                f"{result['work_id']}"
            )

    return model


# ================================================================
# MAIN
# ================================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "AstraLib Cross-Encoder "
            "Reranker Benchmark"
        )
    )

    parser.add_argument(
        "--hnsw-dir",
        default=DEFAULT_HNSW_DIR
    )

    parser.add_argument(
        "--metadata-db",
        default=DEFAULT_METADATA_DB
    )

    parser.add_argument(
        "--query",
        default=QUERIES[0]
    )

    parser.add_argument(
        "--candidates",
        type=int,
        default=CANDIDATE_K
    )

    args = parser.parse_args()

    print("=" * 70)
    print(
        "ASTRALIB — CROSS-ENCODER RERANKER BENCHMARK"
    )
    print("=" * 70)

    print()
    print(
        f"Query      : {args.query}"
    )

    print(
        f"Candidates : Top-{args.candidates}"
    )

    print(
        f"Device     : "
        f"{'CUDA' if torch.cuda.is_available() else 'CPU'}"
    )

    if torch.cuda.is_available():

        print(
            f"GPU        : "
            f"{torch.cuda.get_device_name(0)}"
        )

        print(
            f"CUDA       : "
            f"{torch.version.cuda}"
        )

    # ------------------------------------------------------------
    # Load HNSW
    # ------------------------------------------------------------

    hnsw_index, work_ids = load_hnsw(
        args.hnsw_dir
    )

    # ------------------------------------------------------------
    # Load embedding model
    # ------------------------------------------------------------

    print()
    print(
        "Loading MiniLM..."
    )

    embedding_model = SentenceTransformer(
        EMBEDDING_MODEL,
        device=(
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )
    )

    # ------------------------------------------------------------
    # Warm MiniLM
    # ------------------------------------------------------------

    print(
        "Warming MiniLM..."
    )

    for _ in range(5):

        embedding_model.encode(
            ["warmup query"],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )

    if torch.cuda.is_available():
        torch.cuda.synchronize()

    print(
        "MiniLM warm-up complete."
    )

    # ------------------------------------------------------------
    # Get candidate IDs
    # ------------------------------------------------------------

    print()
    print(
        f"Retrieving Top-{args.candidates} HNSW candidates..."
    )

    candidate_ids = []

    query_vector = embedding_model.encode(
        [args.query],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    query_vector = np.ascontiguousarray(
        query_vector.astype(np.float32)
    )

    if torch.cuda.is_available():
        torch.cuda.synchronize()

    distances, indices = hnsw_index.search(
        query_vector,
        args.candidates
    )

    for idx in indices[0]:

        if idx != -1:

            candidate_ids.append(
                str(work_ids[idx])
            )

    print(
        f"Retrieved candidates: "
        f"{len(candidate_ids)}"
    )

    # ------------------------------------------------------------
    # Load metadata
    # ------------------------------------------------------------

    metadata = load_metadata(
        args.metadata_db,
        candidate_ids
    )

    # ------------------------------------------------------------
    # Build candidate documents
    # ------------------------------------------------------------

    candidates = []

    for score, idx in zip(
        distances[0],
        indices[0]
    ):

        if idx == -1:
            continue

        work_id = str(
            work_ids[idx]
        )

        record = metadata.get(
            work_id
        )

        if record is None:
            continue

        candidates.append({
            "work_id": work_id,
            "hnsw_score": float(score),
            "text": build_document(record)
        })

    print(
        f"Valid reranking candidates: "
        f"{len(candidates)}"
    )

    # ------------------------------------------------------------
    # Benchmark every reranker
    # ------------------------------------------------------------

    for model_name in RERANKER_MODELS:

        benchmark_model(
            model_name,
            args.query,
            candidates
        )

    # ------------------------------------------------------------
    # Final
    # ------------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "ASTRALIB — RERANKER BENCHMARK COMPLETE"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()