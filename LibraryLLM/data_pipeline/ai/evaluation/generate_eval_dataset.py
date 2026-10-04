"""
LuminaR — Generate Automatic Reranker Evaluation Dataset

Pipeline:

    Evaluation Queries
            ↓
    MiniLM-L6 Embedding
            ↓
    HNSW Top-50 Retrieval
            ↓
    DuckDB Metadata
            ↓
    Cross-Encoder L12 Teacher
            ↓
    Raw Teacher Scores
            ↓
    JSON Evaluation Dataset

IMPORTANT:
    This script generates RAW teacher scores only.

    It does NOT convert scores into:
        0 = irrelevant
        1 = somewhat relevant
        2 = highly relevant

    We will inspect the score distribution first and then
    determine appropriate relevance thresholds.

Models:

    Retrieval:
        all-MiniLM-L6-v2

    Teacher:
        cross-encoder/ms-marco-MiniLM-L-12-v2
"""

import os
import gc
import json
import time

import faiss
import duckdb
import numpy as np
import torch

from sentence_transformers import SentenceTransformer, CrossEncoder


# ================================================================
# PATH CONFIGURATION
# ================================================================

BASE_DIR = "D:/SDC/LibraryLLM"

HNSW_DIR = os.path.join(
    BASE_DIR,
    "datasets/ai/faiss/hnsw"
)

METADATA_DB = os.path.join(
    BASE_DIR,
    "datasets/ai/metadata/book_metadata.duckdb"
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "datasets/ai/evaluation"
)

OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "raw_teacher_judgments.json"
)


# ================================================================
# MODELS
# ================================================================

EMBEDDING_MODEL_NAME = (
    "all-MiniLM-L6-v2"
)

TEACHER_MODEL_NAME = (
    "cross-encoder/ms-marco-MiniLM-L-12-v2"
)


# ================================================================
# EVALUATION SETTINGS
# ================================================================

NUM_QUERIES = 30

CANDIDATE_K = 50

TEACHER_BATCH_SIZE = 16

WARMUP_ITERATIONS = 5


# ================================================================
# EVALUATION QUERIES
# ================================================================

EVALUATION_QUERIES = [
    "books for learning deep learning and neural networks",

    "a book about good habits",

    "magic and wizards",

    "science fiction books about space exploration",

    "books for learning Python",

    "machine learning for beginners",

    "books about psychology and human behavior",

    "Victorian mystery novels",

    "books about artificial intelligence",

    "database management books",

    "books about computer networks",

    "operating systems textbooks",

    "books about data structures and algorithms",

    "books for learning Java",

    "books about web development",

    "books about cybersecurity",

    "books about human anatomy",

    "books about astronomy",

    "books about economics",

    "books about business management",

    "historical fiction novels",

    "books about World War II",

    "romance novels",

    "detective mystery books",

    "books about philosophy",

    "books about programming for beginners",

    "books about neural networks",

    "books about natural language processing",

    "books about computer vision",

    "books about entrepreneurship",
]


# ================================================================
# CUDA HELPERS
# ================================================================

def cuda_sync():

    if torch.cuda.is_available():
        torch.cuda.synchronize()


# ================================================================
# LOAD HNSW
# ================================================================

def load_hnsw():

    index_path = os.path.join(
        HNSW_DIR,
        "hnsw.index"
    )

    work_ids_path = os.path.join(
        HNSW_DIR,
        "index_work_ids.npy"
    )

    print("=" * 70)
    print("LOADING HNSW INDEX")
    print("=" * 70)

    if not os.path.exists(index_path):

        raise FileNotFoundError(
            f"HNSW index not found:\n{index_path}"
        )

    if not os.path.exists(work_ids_path):

        raise FileNotFoundError(
            f"Work ID mapping not found:\n"
            f"{work_ids_path}"
        )

    index = faiss.read_index(
        index_path
    )

    work_ids = np.load(
        work_ids_path,
        allow_pickle=True
    )

    print(
        f"Index type : {type(index).__name__}"
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
# LOAD EMBEDDING MODEL
# ================================================================

def load_embedding_model():

    print()
    print("=" * 70)
    print("LOADING EMBEDDING MODEL")
    print("=" * 70)

    device = (
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print(
        f"Model  : {EMBEDDING_MODEL_NAME}"
    )

    print(
        f"Device : {device}"
    )

    model = SentenceTransformer(
        EMBEDDING_MODEL_NAME,
        device=device
    )

    print(
        "Warming MiniLM..."
    )

    for _ in range(
        WARMUP_ITERATIONS
    ):

        model.encode(
            ["warmup query"],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )

    cuda_sync()

    print(
        "MiniLM warm-up complete."
    )

    return model


# ================================================================
# LOAD METADATA
# ================================================================

def load_metadata(
    work_ids
):

    print()
    print("=" * 70)
    print("LOADING BOOK METADATA")
    print("=" * 70)

    if not os.path.exists(
        METADATA_DB
    ):

        raise FileNotFoundError(
            f"Metadata database not found:\n"
            f"{METADATA_DB}"
        )

    conn = duckdb.connect(
        METADATA_DB,
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
            description,
            average_rating,
            rating_count,
            reading_log_count
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

        work_id = str(
            row[0]
        )

        metadata[work_id] = {

            "title": (
                row[1]
                if row[1] is not None
                else ""
            ),

            "authors": (
                row[2]
                if row[2] is not None
                else ""
            ),

            "subjects": (
                row[3]
                if row[3] is not None
                else ""
            ),

            "description": (
                row[4]
                if row[4] is not None
                else ""
            ),

            "average_rating": row[5],

            "rating_count": row[6],

            "reading_log_count": row[7],
        }

    print(
        f"Metadata records loaded: "
        f"{len(metadata)}"
    )

    return metadata


# ================================================================
# BUILD BOOK TEXT
# ================================================================

def build_book_text(
    metadata
):

    parts = []

    if metadata["title"]:
        parts.append(
            f"Title: {metadata['title']}"
        )

    if metadata["authors"]:
        parts.append(
            f"Authors: {metadata['authors']}"
        )

    if metadata["subjects"]:
        parts.append(
            f"Subjects: {metadata['subjects']}"
        )

    if metadata["description"]:
        parts.append(
            f"Description: {metadata['description']}"
        )

    return "\n".join(parts)


# ================================================================
# RETRIEVE TOP-50
# ================================================================

def retrieve_candidates(
    query,
    embedding_model,
    hnsw_index,
    work_ids
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

    distances, indices = (
        hnsw_index.search(
            query_vector,
            CANDIDATE_K
        )
    )

    candidates = []

    for rank, (
        score,
        index_position
    ) in enumerate(
        zip(
            distances[0],
            indices[0]
        ),
        start=1
    ):

        if index_position == -1:
            continue

        work_id = str(
            work_ids[index_position]
        )

        candidates.append({

            "rank_hnsw": rank,

            "work_id": work_id,

            "hnsw_score": float(
                score
            ),
        })

    return candidates


# ================================================================
# BUILD TEACHER PAIRS
# ================================================================

def build_teacher_pairs(
    query,
    candidates,
    metadata
):

    pairs = []

    valid_candidates = []

    for candidate in candidates:

        work_id = candidate[
            "work_id"
        ]

        record = metadata.get(
            work_id
        )

        if record is None:
            continue

        book_text = build_book_text(
            record
        )

        pairs.append(
            [
                query,
                book_text
            ]
        )

        valid_candidates.append(
            candidate
        )

    return pairs, valid_candidates


# ================================================================
# LOAD TEACHER
# ================================================================

def load_teacher():

    print()
    print("=" * 70)
    print("LOADING TEACHER MODEL")
    print("=" * 70)

    device = (
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print(
        f"Model  : {TEACHER_MODEL_NAME}"
    )

    print(
        f"Device : {device}"
    )

    start = time.perf_counter()

    teacher = CrossEncoder(
        TEACHER_MODEL_NAME,
        device=device
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

        print(
            f"GPU allocated : "
            f"{torch.cuda.memory_allocated() / 1024**2:.1f} MB"
        )

        print(
            f"GPU reserved  : "
            f"{torch.cuda.memory_reserved() / 1024**2:.1f} MB"
        )

    return teacher


# ================================================================
# GENERATE TEACHER SCORES
# ================================================================

def score_candidates(
    teacher,
    pairs
):

    if not pairs:
        return []

    scores = teacher.predict(
        pairs,
        batch_size=TEACHER_BATCH_SIZE,
        show_progress_bar=False
    )

    return [
        float(score)
        for score in scores
    ]


# ================================================================
# PROCESS ONE QUERY
# ================================================================

def process_query(
    query,
    query_number,
    embedding_model,
    hnsw_index,
    work_ids,
    teacher
):

    print()
    print("=" * 70)
    print(
        f"QUERY {query_number}/{NUM_QUERIES}"
    )
    print("=" * 70)

    print(
        f"Query: {query}"
    )

    # ------------------------------------------------------------
    # HNSW
    # ------------------------------------------------------------

    candidates = retrieve_candidates(
        query,
        embedding_model,
        hnsw_index,
        work_ids
    )

    print(
        f"HNSW candidates: "
        f"{len(candidates)}"
    )

    # ------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------

    candidate_ids = [
        candidate["work_id"]
        for candidate in candidates
    ]

    metadata = load_metadata(
        candidate_ids
    )

    # ------------------------------------------------------------
    # Teacher pairs
    # ------------------------------------------------------------

    pairs, valid_candidates = (
        build_teacher_pairs(
            query,
            candidates,
            metadata
        )
    )

    print(
        f"Valid teacher candidates: "
        f"{len(valid_candidates)}"
    )

    # ------------------------------------------------------------
    # Teacher scoring
    # ------------------------------------------------------------

    start = time.perf_counter()

    scores = score_candidates(
        teacher,
        pairs
    )

    cuda_sync()

    elapsed = (
        time.perf_counter()
        - start
    ) * 1000

    print(
        f"Teacher scoring: "
        f"{elapsed:.1f} ms"
    )

    # ------------------------------------------------------------
    # Build output
    # ------------------------------------------------------------

    results = []

    for candidate, score in zip(
        valid_candidates,
        scores
    ):

        work_id = candidate[
            "work_id"
        ]

        record = metadata[
            work_id
        ]

        results.append({

            "rank_hnsw":
                candidate[
                    "rank_hnsw"
                ],

            "work_id":
                work_id,

            "hnsw_score":
                candidate[
                    "hnsw_score"
                ],

            "teacher_score":
                score,

            "title":
                record[
                    "title"
                ],

            "authors":
                record[
                    "authors"
                ],

            "subjects":
                record[
                    "subjects"
                ],

            "description":
                record[
                    "description"
                ],

            "average_rating":
                record[
                    "average_rating"
                ],

            "rating_count":
                record[
                    "rating_count"
                ],

            "reading_log_count":
                record[
                    "reading_log_count"
                ],
        })

    # ------------------------------------------------------------
    # Sort by teacher score
    # ------------------------------------------------------------

    results.sort(
        key=lambda x:
            x["teacher_score"],
        reverse=True
    )

    for rank, result in enumerate(
        results,
        start=1
    ):

        result[
            "rank_teacher"
        ] = rank

    # Restore HNSW order for
    # easier comparison later.

    results.sort(
        key=lambda x:
            x["rank_hnsw"]
    )

    # ------------------------------------------------------------
    # Print top teacher results
    # ------------------------------------------------------------

    print()
    print(
        "Top 5 by teacher score:"
    )

    teacher_sorted = sorted(
        results,
        key=lambda x:
            x["teacher_score"],
        reverse=True
    )

    for result in teacher_sorted[:5]:

        print(
            f"{result['rank_teacher']:2d}. "
            f"{result['teacher_score']:.4f}  "
            f"{result['work_id']}  "
            f"{result['title']}"
        )

    return {

        "query": query,

        "candidate_count":
            len(results),

        "candidates":
            results,
    }


# ================================================================
# MAIN
# ================================================================

def main():

    print("=" * 70)
    print(
        "ASTRALIB — AUTOMATIC EVALUATION DATASET GENERATION"
    )
    print("=" * 70)

    print()
    print(
        f"Queries       : {NUM_QUERIES}"
    )

    print(
        f"Candidates    : Top-{CANDIDATE_K}"
    )

    print(
        f"Teacher       : "
        f"{TEACHER_MODEL_NAME}"
    )

    print(
        f"Batch size    : "
        f"{TEACHER_BATCH_SIZE}"
    )

    print(
        f"Device        : "
        f"{'CUDA' if torch.cuda.is_available() else 'CPU'}"
    )

    # ------------------------------------------------------------
    # Validate query count
    # ------------------------------------------------------------

    if len(EVALUATION_QUERIES) != NUM_QUERIES:

        raise ValueError(
            "Number of evaluation queries "
            "does not match NUM_QUERIES."
        )

    # ------------------------------------------------------------
    # Create output directory
    # ------------------------------------------------------------

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    # ------------------------------------------------------------
    # Load HNSW
    # ------------------------------------------------------------

    hnsw_index, work_ids = (
        load_hnsw()
    )

    # ------------------------------------------------------------
    # Load MiniLM
    # ------------------------------------------------------------

    embedding_model = (
        load_embedding_model()
    )

    # ------------------------------------------------------------
    # Load teacher
    # ------------------------------------------------------------

    teacher = load_teacher()

    # ------------------------------------------------------------
    # Process queries
    # ------------------------------------------------------------

    all_results = []

    start_total = time.perf_counter()

    for query_number, query in enumerate(
        EVALUATION_QUERIES,
        start=1
    ):

        result = process_query(
            query,
            query_number,
            embedding_model,
            hnsw_index,
            work_ids,
            teacher
        )

        all_results.append(
            result
        )

        # Save after every query so
        # progress is not lost if the
        # process is interrupted.

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                {
                    "configuration": {

                        "embedding_model":
                            EMBEDDING_MODEL_NAME,

                        "teacher_model":
                            TEACHER_MODEL_NAME,

                        "hnsw_index":
                            "IndexHNSWFlat",

                        "candidate_k":
                            CANDIDATE_K,

                        "teacher_batch_size":
                            TEACHER_BATCH_SIZE,

                        "num_queries":
                            NUM_QUERIES,
                    },

                    "queries":
                        all_results,

                },
                f,
                indent=2,
                ensure_ascii=False
            )

        print()
        print(
            f"Saved progress: "
            f"{query_number}/{NUM_QUERIES}"
        )

    total_time = (
        time.perf_counter()
        - start_total
    )

    # ------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------

    del teacher
    del embedding_model

    gc.collect()

    if torch.cuda.is_available():

        torch.cuda.empty_cache()

        cuda_sync()

    # ------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------

    total_candidates = sum(
        item["candidate_count"]
        for item in all_results
    )

    print()
    print("=" * 70)
    print(
        "DATASET GENERATION COMPLETE"
    )
    print("=" * 70)

    print(
        f"Queries generated : "
        f"{len(all_results)}"
    )

    print(
        f"Candidate judgments: "
        f"{total_candidates}"
    )

    print(
        f"Total time        : "
        f"{total_time / 60:.2f} minutes"
    )

    print()
    print(
        f"Output:"
    )

    print(
        OUTPUT_FILE
    )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "Raw teacher scores were saved."
    )

    print(
        "No 0/1/2 relevance thresholds "
        "have been applied yet."
    )

    print(
        "The next step is to inspect the "
        "teacher-score distribution."
    )

    print("=" * 70)


if __name__ == "__main__":
    main()