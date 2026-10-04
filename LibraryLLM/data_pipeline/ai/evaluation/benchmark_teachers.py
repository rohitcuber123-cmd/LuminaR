"""
AstraLib — Local Teacher Model Benchmark

Purpose:
    Benchmark stronger local reranker/teacher models that can be
    used to automatically generate synthetic relevance judgments.

Production model being evaluated:
    cross-encoder/ms-marco-MiniLM-L-6-v2

Teacher candidates:
    BAAI/bge-reranker-base
    BAAI/bge-reranker-large
    cross-encoder/ms-marco-MiniLM-L-12-v2

No AstraLib data is modified by this script.
"""

import gc
import os
import time
import statistics

import numpy as np
import torch
from sentence_transformers import SentenceTransformer, CrossEncoder
import faiss
import duckdb


# ================================================================
# PATHS
# ================================================================

HNSW_DIR = (
    "D:/SDC/LibraryLLM/datasets/ai/faiss/hnsw"
)

METADATA_DB = (
    "D:/SDC/LibraryLLM/datasets/ai/metadata/book_metadata.duckdb"
)


# ================================================================
# MODELS
# ================================================================

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

TEACHER_MODELS = [
    "BAAI/bge-reranker-base",
    "BAAI/bge-reranker-large",
    "cross-encoder/ms-marco-MiniLM-L-12-v2",
]


# ================================================================
# BENCHMARK SETTINGS
# ================================================================

CANDIDATE_K = 50

BATCH_SIZES = [8, 16, 32]

WARMUP_ITERATIONS = 10
BENCHMARK_ITERATIONS = 20


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

def cuda_sync():
    """Synchronize CUDA before accurate timing."""

    if torch.cuda.is_available():
        torch.cuda.synchronize()


def get_percentile(values, percentile):
    return float(
        np.percentile(values, percentile)
    )


def print_statistics(times):

    return {
        "average": statistics.mean(times),
        "median": statistics.median(times),
        "p95": get_percentile(times, 95),
        "minimum": min(times),
        "maximum": max(times),
    }


# ================================================================
# LOAD HNSW
# ================================================================

def load_hnsw():

    index_path = os.path.join(
        HNSW_DIR,
        "hnsw.index"
    )

    ids_path = os.path.join(
        HNSW_DIR,
        "index_work_ids.npy"
    )

    if not os.path.exists(index_path):
        raise FileNotFoundError(
            f"HNSW index not found:\n{index_path}"
        )

    if not os.path.exists(ids_path):
        raise FileNotFoundError(
            f"Work ID mapping not found:\n{ids_path}"
        )

    print("Loading HNSW index...")

    index = faiss.read_index(
        index_path
    )

    work_ids = np.load(
        ids_path,
        allow_pickle=True
    )

    print(
        f"Vectors    : {index.ntotal:,}"
    )

    print(
        f"Dimension  : {index.d}"
    )

    print(
        f"Work IDs   : {len(work_ids):,}"
    )

    print(
        f"efSearch   : {index.hnsw.efSearch}"
    )

    return index, work_ids


# ================================================================
# LOAD MINILM
# ================================================================

def load_embedding_model():

    print()
    print("Loading MiniLM...")

    model = SentenceTransformer(
        EMBEDDING_MODEL,
        device="cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print("Warming MiniLM...")

    for _ in range(5):

        model.encode(
            ["warmup query"],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )

    cuda_sync()

    print("MiniLM warm-up complete.")

    return model


# ================================================================
# LOAD METADATA
# ================================================================

def load_metadata(
    db_path,
    work_ids
):

    print()
    print(
        f"Loading metadata for "
        f"{len(work_ids)} candidates..."
    )

    if not os.path.exists(db_path):

        raise FileNotFoundError(
            f"Metadata database not found:\n{db_path}"
        )

    conn = duckdb.connect(
        db_path,
        read_only=True
    )

    placeholders = ", ".join(
        ["?"] * len(work_ids)
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
            work_ids
        ).fetchall()

    finally:

        conn.close()

    metadata = {}

    for row in rows:

        work_id = str(row[0])

        metadata[work_id] = {
            "title": row[1] or "",
            "authors": row[2] or "",
            "subjects": row[3] or "",
            "description": row[4] or "",
        }

    print(
        f"Metadata records loaded: "
        f"{len(metadata)}"
    )

    return metadata


# ================================================================
# BUILD BOOK TEXT
# ================================================================

def build_book_text(record):

    return (
        f"Title: {record['title']}\n"
        f"Authors: {record['authors']}\n"
        f"Subjects: {record['subjects']}\n"
        f"Description: {record['description']}"
    )


# ================================================================
# RETRIEVE CANDIDATES
# ================================================================

def retrieve_candidates(
    query,
    embedding_model,
    hnsw_index,
    work_ids,
    metadata
):

    query_vector = embedding_model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    query_vector = np.ascontiguousarray(
        query_vector.astype(np.float32)
    )

    cuda_sync()

    distances, indices = hnsw_index.search(
        query_vector,
        CANDIDATE_K
    )

    candidates = []

    for score, index_position in zip(
        distances[0],
        indices[0]
    ):

        if index_position == -1:
            continue

        work_id = str(
            work_ids[index_position]
        )

        record = metadata.get(
            work_id
        )

        if record is None:
            continue

        candidates.append(
            {
                "work_id": work_id,
                "hnsw_score": float(score),
                "text": build_book_text(record),
            }
        )

    return candidates


# ================================================================
# BUILD QUERY / DOCUMENT PAIRS
# ================================================================

def build_pairs(
    query,
    candidates
):

    return [
        [
            query,
            candidate["text"]
        ]
        for candidate in candidates
    ]


# ================================================================
# LOAD TEACHER
# ================================================================

def load_teacher(model_name):

    print()
    print(
        f"Loading teacher:"
    )

    print(
        f"  {model_name}"
    )

    start = time.perf_counter()

    model = CrossEncoder(
        model_name,
        device="cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    cuda_sync()

    elapsed = (
        time.perf_counter()
        - start
    ) * 1000

    print(
        f"Model load : {elapsed:.1f} ms"
    )

    if torch.cuda.is_available():

        allocated = (
            torch.cuda.memory_allocated()
            / 1024**2
        )

        reserved = (
            torch.cuda.memory_reserved()
            / 1024**2
        )

        print(
            f"GPU allocated : "
            f"{allocated:.1f} MB"
        )

        print(
            f"GPU reserved  : "
            f"{reserved:.1f} MB"
        )

    return model


# ================================================================
# BENCHMARK TEACHER
# ================================================================

def benchmark_teacher(
    model_name,
    candidates,
    query
):

    print()
    print("=" * 70)
    print(
        f"TEACHER MODEL: {model_name}"
    )
    print("=" * 70)

    print(
        f"Candidates : {len(candidates)}"
    )

    model = load_teacher(
        model_name
    )

    pairs = build_pairs(
        query,
        candidates
    )

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
            f"Warm-up: "
            f"{WARMUP_ITERATIONS} iterations..."
        )

        for _ in range(
            WARMUP_ITERATIONS
        ):

            model.predict(
                pairs,
                batch_size=batch_size,
                show_progress_bar=False
            )

        cuda_sync()

        print(
            "Warm-up complete."
        )

        # --------------------------------------------------------
        # Benchmark
        # --------------------------------------------------------

        times = []

        for _ in range(
            BENCHMARK_ITERATIONS
        ):

            cuda_sync()

            start = time.perf_counter()

            model.predict(
                pairs,
                batch_size=batch_size,
                show_progress_bar=False
            )

            cuda_sync()

            elapsed = (
                time.perf_counter()
                - start
            ) * 1000

            times.append(
                elapsed
            )

        stats = print_statistics(
            times
        )

        candidates_per_second = (
            len(candidates)
            * BENCHMARK_ITERATIONS
            / (sum(times) / 1000)
        )

        ms_per_candidate = (
            statistics.mean(times)
            / len(candidates)
        )

        print()
        print(
            f"Average : "
            f"{stats['average']:.2f} ms"
        )

        print(
            f"Median  : "
            f"{stats['median']:.2f} ms"
        )

        print(
            f"P95     : "
            f"{stats['p95']:.2f} ms"
        )

        print(
            f"Minimum : "
            f"{stats['minimum']:.2f} ms"
        )

        print(
            f"Maximum : "
            f"{stats['maximum']:.2f} ms"
        )

        print()
        print(
            f"ms/candidate   : "
            f"{ms_per_candidate:.3f}"
        )

        print(
            f"Candidates/sec : "
            f"{candidates_per_second:.1f}"
        )

    # ------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------

    print()
    print(
        "Releasing teacher model..."
    )

    del model

    gc.collect()

    if torch.cuda.is_available():

        torch.cuda.empty_cache()

        cuda_sync()

    print(
        "Teacher model released."
    )


# ================================================================
# MAIN
# ================================================================

def main():

    print("=" * 70)
    print(
        "ASTRALIB — LOCAL TEACHER MODEL BENCHMARK"
    )
    print("=" * 70)

    print()
    print(
        f"Device : "
        f"{'CUDA' if torch.cuda.is_available() else 'CPU'}"
    )

    if torch.cuda.is_available():

        print(
            f"GPU    : "
            f"{torch.cuda.get_device_name(0)}"
        )

        print(
            f"CUDA   : "
            f"{torch.version.cuda}"
        )

    # ------------------------------------------------------------
    # Load HNSW
    # ------------------------------------------------------------

    hnsw_index, work_ids = load_hnsw()

    # ------------------------------------------------------------
    # Load MiniLM
    # ------------------------------------------------------------

    embedding_model = (
        load_embedding_model()
    )

    # ------------------------------------------------------------
    # Use one representative query
    # ------------------------------------------------------------

    query = (
        "books for learning deep learning "
        "and neural networks"
    )

    print()
    print(
        f"Evaluation query:\n{query}"
    )

    # ------------------------------------------------------------
    # Retrieve Top-50
    # ------------------------------------------------------------

    print()
    print(
        "Retrieving Top-50 candidates..."
    )

    # First retrieve IDs without metadata.
    query_vector = embedding_model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    query_vector = np.ascontiguousarray(
        query_vector.astype(np.float32)
    )

    cuda_sync()

    distances, indices = hnsw_index.search(
        query_vector,
        CANDIDATE_K
    )

    candidate_ids = []

    for index_position in indices[0]:

        if index_position == -1:
            continue

        candidate_ids.append(
            str(work_ids[index_position])
        )

    print(
        f"Retrieved: "
        f"{len(candidate_ids)} candidates"
    )

    # ------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------

    metadata = load_metadata(
        METADATA_DB,
        candidate_ids
    )

    candidates = []

    for score, index_position in zip(
        distances[0],
        indices[0]
    ):

        if index_position == -1:
            continue

        work_id = str(
            work_ids[index_position]
        )

        record = metadata.get(
            work_id
        )

        if record is None:
            continue

        candidates.append(
            {
                "work_id": work_id,
                "hnsw_score": float(score),
                "text": build_book_text(
                    record
                ),
            }
        )

    print(
        f"Valid candidates: "
        f"{len(candidates)}"
    )

    # ------------------------------------------------------------
    # Benchmark teachers
    # ------------------------------------------------------------

    for model_name in TEACHER_MODELS:

        try:

            benchmark_teacher(
                model_name,
                candidates,
                query
            )

        except Exception as e:

            print()
            print(
                "ERROR while benchmarking:"
            )

            print(
                model_name
            )

            print(
                str(e)
            )

            print(
                "Continuing to next model..."
            )

            gc.collect()

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    # ------------------------------------------------------------
    # Final
    # ------------------------------------------------------------

    del embedding_model

    gc.collect()

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    print()
    print("=" * 70)
    print(
        "TEACHER BENCHMARK COMPLETE"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()