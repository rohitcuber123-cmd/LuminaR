"""
AstraLib — Reranker Evaluation

Compares:

    HNSW Top-10
        VS
    HNSW Top-50 + MiniLM-L6 Cross-Encoder Top-10

Ground-truth relevance:
    Automatically generated from the L12 teacher model.

Metrics:
    Precision@10
    Recall@10
    MRR@10
    NDCG@10

Also measures:
    L6 reranking latency

IMPORTANT:
    This script does NOT modify:
        - HNSW index
        - embeddings
        - work IDs
        - metadata database
        - production search code
"""


import os
import json
import time
import statistics

import numpy as np
import torch
from sentence_transformers import CrossEncoder


# ================================================================
# PATHS
# ================================================================

BASE_DIR = "D:/SDC/LibraryLLM"

EVALUATION_FILE = os.path.join(
    BASE_DIR,
    "datasets/ai/evaluation/labeled_evaluation_dataset.json"
)


# ================================================================
# MODEL
# ================================================================

RERANKER_MODEL = (
    "cross-encoder/ms-marco-MiniLM-L-6-v2"
)


# ================================================================
# SETTINGS
# ================================================================

TOP_K = 10

RERANK_CANDIDATES = 50

BATCH_SIZE = 16

WARMUP_ITERATIONS = 5


# ================================================================
# CUDA
# ================================================================

def cuda_sync():

    if torch.cuda.is_available():
        torch.cuda.synchronize()


# ================================================================
# LOAD DATASET
# ================================================================

def load_dataset():

    print("=" * 70)
    print("LOADING EVALUATION DATASET")
    print("=" * 70)

    if not os.path.exists(
        EVALUATION_FILE
    ):

        raise FileNotFoundError(
            f"Evaluation dataset not found:\n"
            f"{EVALUATION_FILE}"
        )

    with open(
        EVALUATION_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    queries = data["queries"]

    print(
        f"Queries     : {len(queries)}"
    )

    total_candidates = sum(
        q["candidate_count"]
        for q in queries
    )

    print(
        f"Candidates  : "
        f"{total_candidates:,}"
    )

    print(
        f"Teacher     : "
        f"{data['configuration']['teacher_model']}"
    )

    print(
        f"Labels      : "
        f"{data['configuration']['labeling_method']}"
    )

    return data


# ================================================================
# METRIC: PRECISION@K
# ================================================================

def precision_at_k(
    ranked_candidates,
    k=10
):

    top_k = ranked_candidates[:k]

    if not top_k:
        return 0.0

    relevant = sum(
        1
        for candidate in top_k
        if candidate["relevance"] > 0
    )

    return relevant / len(top_k)


# ================================================================
# METRIC: RECALL@K
# ================================================================

def recall_at_k(
    ranked_candidates,
    k=10
):

    top_k = ranked_candidates[:k]

    total_relevant = sum(
        1
        for candidate in ranked_candidates
        if candidate["relevance"] > 0
    )

    if total_relevant == 0:
        return 0.0

    retrieved_relevant = sum(
        1
        for candidate in top_k
        if candidate["relevance"] > 0
    )

    return (
        retrieved_relevant
        / total_relevant
    )


# ================================================================
# METRIC: MRR@K
# ================================================================

def mrr_at_k(
    ranked_candidates,
    k=10
):

    top_k = ranked_candidates[:k]

    for rank, candidate in enumerate(
        top_k,
        start=1
    ):

        if candidate["relevance"] > 0:

            return 1.0 / rank

    return 0.0


# ================================================================
# METRIC: NDCG@K
# ================================================================

def dcg_at_k(
    ranked_candidates,
    k=10
):

    top_k = ranked_candidates[:k]

    dcg = 0.0

    for rank, candidate in enumerate(
        top_k,
        start=1
    ):

        relevance = candidate[
            "relevance"
        ]

        gain = (
            (2 ** relevance) - 1
        )

        discount = np.log2(
            rank + 1
        )

        dcg += (
            gain / discount
        )

    return dcg


def ndcg_at_k(
    ranked_candidates,
    k=10
):

    actual_dcg = dcg_at_k(
        ranked_candidates,
        k
    )

    ideal_ranking = sorted(
        ranked_candidates,
        key=lambda x:
            x["relevance"],
        reverse=True
    )

    ideal_dcg = dcg_at_k(
        ideal_ranking,
        k
    )

    if ideal_dcg == 0:
        return 0.0

    return (
        actual_dcg
        / ideal_dcg
    )


# ================================================================
# CALCULATE ALL METRICS
# ================================================================

def calculate_metrics(
    ranked_candidates
):

    return {

        "precision@10":
            precision_at_k(
                ranked_candidates,
                TOP_K
            ),

        "recall@10":
            recall_at_k(
                ranked_candidates,
                TOP_K
            ),

        "mrr@10":
            mrr_at_k(
                ranked_candidates,
                TOP_K
            ),

        "ndcg@10":
            ndcg_at_k(
                ranked_candidates,
                TOP_K
            )
    }


# ================================================================
# LOAD L6 RERANKER
# ================================================================

def load_reranker():

    print()
    print("=" * 70)
    print("LOADING PRODUCTION RERANKER")
    print("=" * 70)

    device = (
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print(
        f"Model  : {RERANKER_MODEL}"
    )

    print(
        f"Device : {device}"
    )

    start = time.perf_counter()

    model = CrossEncoder(
        RERANKER_MODEL,
        device=device
    )

    cuda_sync()

    load_time = (
        time.perf_counter()
        - start
    ) * 1000

    print(
        f"Model load : "
        f"{load_time:.1f} ms"
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

    # ------------------------------------------------------------
    # Warm-up
    # ------------------------------------------------------------

    print()
    print(
        f"Warming reranker "
        f"({WARMUP_ITERATIONS} iterations)..."
    )

    warmup_pairs = [
        [
            "books about deep learning",
            "Deep Learning textbook"
        ]
        for _ in range(10)
    ]

    for _ in range(
        WARMUP_ITERATIONS
    ):

        model.predict(
            warmup_pairs,
            batch_size=BATCH_SIZE,
            show_progress_bar=False
        )

    cuda_sync()

    print(
        "Reranker warm-up complete."
    )

    return model


# ================================================================
# HNSW BASELINE
# ================================================================

def evaluate_hnsw(
    query_data
):

    # Dataset candidates are already
    # stored in HNSW rank order.

    ranked = sorted(
        query_data["candidates"],
        key=lambda x:
            x["rank_hnsw"]
    )

    return calculate_metrics(
        ranked
    )


# ================================================================
# RERANK WITH L6
# ================================================================

def rerank_query(
    model,
    query_data
):

    query = query_data[
        "query"
    ]

    candidates = query_data[
        "candidates"
    ]

    # ------------------------------------------------------------
    # Keep HNSW Top-50
    # ------------------------------------------------------------

    candidates = sorted(
        candidates,
        key=lambda x:
            x["rank_hnsw"]
    )[:RERANK_CANDIDATES]

    pairs = []

    for candidate in candidates:

        title = candidate.get(
            "title",
            ""
        )

        authors = candidate.get(
            "authors",
            ""
        )

        subjects = candidate.get(
            "subjects",
            ""
        )

        description = candidate.get(
            "description",
            ""
        )

        book_text = (
            f"Title: {title}\n"
            f"Authors: {authors}\n"
            f"Subjects: {subjects}\n"
            f"Description: {description}"
        )

        pairs.append(
            [
                query,
                book_text
            ]
        )

    # ------------------------------------------------------------
    # Measure L6 latency
    # ------------------------------------------------------------

    cuda_sync()

    start = time.perf_counter()

    scores = model.predict(
        pairs,
        batch_size=BATCH_SIZE,
        show_progress_bar=False
    )

    cuda_sync()

    elapsed = (
        time.perf_counter()
        - start
    ) * 1000

    # ------------------------------------------------------------
    # Attach scores
    # ------------------------------------------------------------

    reranked = []

    for candidate, score in zip(
        candidates,
        scores
    ):

        result = dict(
            candidate
        )

        result[
            "l6_score"
        ] = float(score)

        reranked.append(
            result
        )

    # ------------------------------------------------------------
    # Sort by L6 score
    # ------------------------------------------------------------

    reranked.sort(
        key=lambda x:
            x["l6_score"],
        reverse=True
    )

    for rank, candidate in enumerate(
        reranked,
        start=1
    ):

        candidate[
            "rank_l6"
        ] = rank

    return reranked, elapsed


# ================================================================
# MAIN
# ================================================================

def main():

    print("=" * 70)
    print(
        "ASTRALIB — HNSW VS L6 RERANKER EVALUATION"
    )
    print("=" * 70)

    print()
    print(
        f"Production reranker : "
        f"{RERANKER_MODEL}"
    )

    print(
        f"HNSW candidates     : "
        f"Top-{RERANK_CANDIDATES}"
    )

    print(
        f"Evaluation output   : "
        f"Top-{TOP_K}"
    )

    print(
        f"Batch size          : "
        f"{BATCH_SIZE}"
    )

    # ------------------------------------------------------------
    # Load evaluation dataset
    # ------------------------------------------------------------

    data = load_dataset()

    queries = data[
        "queries"
    ]

    # ------------------------------------------------------------
    # Load L6
    # ------------------------------------------------------------

    reranker = load_reranker()

    # ------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------

    hnsw_results = []

    l6_results = []

    rerank_times = []

    # ------------------------------------------------------------
    # Evaluate every query
    # ------------------------------------------------------------

    print()
    print("=" * 70)
    print("EVALUATING QUERIES")
    print("=" * 70)

    for query_number, query_data in enumerate(
        queries,
        start=1
    ):

        query = query_data[
            "query"
        ]

        # --------------------------------------------------------
        # HNSW
        # --------------------------------------------------------

        hnsw_metrics = evaluate_hnsw(
            query_data
        )

        # --------------------------------------------------------
        # L6
        # --------------------------------------------------------

        reranked, rerank_time = (
            rerank_query(
                reranker,
                query_data
            )
        )

        l6_metrics = calculate_metrics(
            reranked
        )

        rerank_times.append(
            rerank_time
        )

        hnsw_results.append(
            hnsw_metrics
        )

        l6_results.append(
            l6_metrics
        )

        # --------------------------------------------------------
        # Print query result
        # --------------------------------------------------------

        print()
        print(
            f"[{query_number:2d}/"
            f"{len(queries)}] "
            f"{query}"
        )

        print()

        print(
            "  HNSW:"
        )

        print(
            f"    Precision@10 : "
            f"{hnsw_metrics['precision@10']:.4f}"
        )

        print(
            f"    Recall@10    : "
            f"{hnsw_metrics['recall@10']:.4f}"
        )

        print(
            f"    MRR@10       : "
            f"{hnsw_metrics['mrr@10']:.4f}"
        )

        print(
            f"    NDCG@10      : "
            f"{hnsw_metrics['ndcg@10']:.4f}"
        )

        print()

        print(
            "  HNSW + L6:"
        )

        print(
            f"    Precision@10 : "
            f"{l6_metrics['precision@10']:.4f}"
        )

        print(
            f"    Recall@10    : "
            f"{l6_metrics['recall@10']:.4f}"
        )

        print(
            f"    MRR@10       : "
            f"{l6_metrics['mrr@10']:.4f}"
        )

        print(
            f"    NDCG@10      : "
            f"{l6_metrics['ndcg@10']:.4f}"
        )

        print(
            f"    Rerank time   : "
            f"{rerank_time:.2f} ms"
        )

    # ============================================================
    # AGGREGATE RESULTS
    # ============================================================

    def average_metric(
        results,
        metric
    ):

        return statistics.mean(
            result[metric]
            for result in results
        )

    metrics = [
        "precision@10",
        "recall@10",
        "mrr@10",
        "ndcg@10"
    ]

    print()
    print("=" * 70)
    print("FINAL EVALUATION RESULTS")
    print("=" * 70)

    print()

    print(
        f"{'Metric':<18}"
        f"{'HNSW':>12}"
        f"{'HNSW + L6':>15}"
        f"{'Change':>12}"
    )

    print("-" * 57)

    for metric in metrics:

        hnsw_value = average_metric(
            hnsw_results,
            metric
        )

        l6_value = average_metric(
            l6_results,
            metric
        )

        change = (
            l6_value
            - hnsw_value
        )

        print(
            f"{metric:<18}"
            f"{hnsw_value:>12.4f}"
            f"{l6_value:>15.4f}"
            f"{change:>+12.4f}"
        )

    # ============================================================
    # PERCENTAGE IMPROVEMENT
    # ============================================================

    print()
    print("=" * 70)
    print("PERCENTAGE IMPROVEMENT")
    print("=" * 70)

    for metric in metrics:

        hnsw_value = average_metric(
            hnsw_results,
            metric
        )

        l6_value = average_metric(
            l6_results,
            metric
        )

        if hnsw_value != 0:

            improvement = (
                (
                    l6_value
                    - hnsw_value
                )
                / hnsw_value
            ) * 100

        else:

            improvement = 0.0

        print(
            f"{metric:<18}"
            f"{improvement:+.2f}%"
        )

    # ============================================================
    # RERANKING LATENCY
    # ============================================================

    print()
    print("=" * 70)
    print("L6 RERANKING LATENCY")
    print("=" * 70)

    print(
        f"Candidates/query : "
        f"{RERANK_CANDIDATES}"
    )

    print(
        f"Batch size       : "
        f"{BATCH_SIZE}"
    )

    print(
        f"Average          : "
        f"{statistics.mean(rerank_times):.2f} ms"
    )

    print(
        f"Median           : "
        f"{statistics.median(rerank_times):.2f} ms"
    )

    print(
        f"P95              : "
        f"{np.percentile(rerank_times, 95):.2f} ms"
    )

    print(
        f"Minimum          : "
        f"{min(rerank_times):.2f} ms"
    )

    print(
        f"Maximum          : "
        f"{max(rerank_times):.2f} ms"
    )

    print()

    # ============================================================
    # INTERPRETATION
    # ============================================================

    hnsw_ndcg = average_metric(
        hnsw_results,
        "ndcg@10"
    )

    l6_ndcg = average_metric(
        l6_results,
        "ndcg@10"
    )

    hnsw_mrr = average_metric(
        hnsw_results,
        "mrr@10"
    )

    l6_mrr = average_metric(
        l6_results,
        "mrr@10"
    )

    print("=" * 70)
    print("INTERPRETATION")
    print("=" * 70)

    if l6_ndcg > hnsw_ndcg:

        print(
            "[+] L6 improves NDCG@10."
        )

    elif l6_ndcg < hnsw_ndcg:

        print(
            "[-] L6 decreases NDCG@10."
        )

    else:

        print(
            "[=] L6 produces the same NDCG@10."
        )

    if l6_mrr > hnsw_mrr:

        print(
            "[+] L6 improves MRR@10."
        )

    elif l6_mrr < hnsw_mrr:

        print(
            "[-] L6 decreases MRR@10."
        )

    else:

        print(
            "[=] L6 produces the same MRR@10."
        )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "These metrics are evaluated against "
        "synthetic teacher-generated relevance "
        "labels, not manually verified ground truth."
    )

    print()

    print("=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()