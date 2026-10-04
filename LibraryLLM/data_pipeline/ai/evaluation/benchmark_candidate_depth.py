"""
LuminaR — Corrected Candidate Depth Benchmark

Compares:

    HNSW Top-20  -> L6 -> Top-10
    HNSW Top-50  -> L6 -> Top-10

Both are evaluated against the SAME 50 teacher-labeled
candidates.

This makes Recall@10 and NDCG@10 directly comparable.

No production indexes, embeddings, or labels are modified.
"""

import os
import json
import time
import statistics

import numpy as np
import torch
from sentence_transformers import CrossEncoder


# ================================================================
# CONFIGURATION
# ================================================================

BASE_DIR = "D:/SDC/LibraryLLM"

EVALUATION_FILE = os.path.join(
    BASE_DIR,
    "datasets/ai/evaluation/labeled_evaluation_dataset.json"
)

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

CANDIDATE_DEPTHS = [20, 50]

TOP_K = 10

BATCH_SIZE = 16

WARMUP_ITERATIONS = 5


# ================================================================
# CUDA SYNCHRONIZATION
# ================================================================

def cuda_sync():

    if torch.cuda.is_available():
        torch.cuda.synchronize()


# ================================================================
# METRICS
# ================================================================

def precision_at_k(candidates, k=10):

    top = candidates[:k]

    if not top:
        return 0.0

    relevant = sum(
        1
        for candidate in top
        if candidate["relevance"] > 0
    )

    return relevant / len(top)


def recall_at_k(candidates, k=10):

    """
    Recall denominator is calculated from ALL
    teacher-labeled candidates.

    This is why both Top-20 and Top-50 receive
    the same 50-candidate ground truth.
    """

    top = candidates[:k]

    total_relevant = sum(
        1
        for candidate in candidates
        if candidate["relevance"] > 0
    )

    if total_relevant == 0:
        return 0.0

    retrieved_relevant = sum(
        1
        for candidate in top
        if candidate["relevance"] > 0
    )

    return retrieved_relevant / total_relevant


def dcg_at_k(candidates, k=10):

    dcg = 0.0

    for rank, candidate in enumerate(
        candidates[:k],
        start=1
    ):

        relevance = candidate["relevance"]

        gain = (2 ** relevance) - 1

        discount = np.log2(rank + 1)

        dcg += gain / discount

    return dcg


def ndcg_at_k(candidates, k=10):

    """
    NDCG is calculated using the same complete
    50-candidate ground truth for every depth.
    """

    actual = dcg_at_k(
        candidates,
        k
    )

    ideal = sorted(
        candidates,
        key=lambda x: x["relevance"],
        reverse=True
    )

    ideal_dcg = dcg_at_k(
        ideal,
        k
    )

    if ideal_dcg == 0:
        return 0.0

    return actual / ideal_dcg


def mrr_at_k(candidates, k=10):

    for rank, candidate in enumerate(
        candidates[:k],
        start=1
    ):

        if candidate["relevance"] > 0:

            return 1.0 / rank

    return 0.0


def calculate_metrics(candidates):

    return {
        "precision@10": precision_at_k(
            candidates,
            TOP_K
        ),

        "recall@10": recall_at_k(
            candidates,
            TOP_K
        ),

        "mrr@10": mrr_at_k(
            candidates,
            TOP_K
        ),

        "ndcg@10": ndcg_at_k(
            candidates,
            TOP_K
        )
    }


# ================================================================
# LOAD DATASET
# ================================================================

def load_dataset():

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

        return json.load(f)


# ================================================================
# LOAD L6 MODEL
# ================================================================

def load_model():

    device = (
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print("=" * 70)
    print("LOADING L6 RERANKER")
    print("=" * 70)

    print(
        f"Model  : {MODEL_NAME}"
    )

    print(
        f"Device : {device}"
    )

    start = time.perf_counter()

    model = CrossEncoder(
        MODEL_NAME,
        device=device
    )

    cuda_sync()

    load_time = (
        time.perf_counter() - start
    ) * 1000

    print(
        f"Model load : {load_time:.1f} ms"
    )

    print()
    print("Warming reranker...")

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

    print("Warm-up complete.")


    return model


# ================================================================
# RERANK CANDIDATES
# ================================================================

def rerank(
    model,
    query_data,
    candidate_depth
):

    query = query_data["query"]

    # ------------------------------------------------------------
    # Original HNSW ordering
    # ------------------------------------------------------------

    all_candidates = sorted(
        query_data["candidates"],
        key=lambda x: x["rank_hnsw"]
    )

    # ------------------------------------------------------------
    # Only this many candidates are passed
    # to the Cross-Encoder.
    # ------------------------------------------------------------

    rerank_candidates = all_candidates[
        :candidate_depth
    ]

    pairs = []

    for candidate in rerank_candidates:

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
    # Measure ONLY reranking time
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
        time.perf_counter() - start
    ) * 1000

    # ------------------------------------------------------------
    # Attach L6 scores
    # ------------------------------------------------------------

    reranked = []

    for candidate, score in zip(
        rerank_candidates,
        scores
    ):

        item = dict(candidate)

        item["l6_score"] = float(
            score
        )

        reranked.append(item)

    # ------------------------------------------------------------
    # Sort by Cross-Encoder score
    # ------------------------------------------------------------

    reranked.sort(
        key=lambda x: x["l6_score"],
        reverse=True
    )

    return (
        reranked,
        elapsed
    )


# ================================================================
# BUILD COMMON EVALUATION RANKING
# ================================================================

def build_evaluation_ranking(
    all_candidates,
    reranked
):

    """
    Creates a complete 50-candidate ranking.

    Reranked candidates appear according to their
    L6 ranking.

    Candidates that were NOT reranked remain after
    the reranked candidates, preserving their original
    HNSW order.

    Therefore:

        Top-20:
            L6 ranks 20 candidates
            remaining 30 stay behind them

        Top-50:
            L6 ranks all 50 candidates

    Both are evaluated over the SAME 50 documents.
    """

    reranked_ids = {
        candidate["work_id"]
        for candidate in reranked
    }

    # ------------------------------------------------------------
    # Reranked portion
    # ------------------------------------------------------------

    ranking = list(reranked)

    # ------------------------------------------------------------
    # Candidates not reranked
    # ------------------------------------------------------------

    remaining = [
        candidate
        for candidate in all_candidates
        if candidate["work_id"]
        not in reranked_ids
    ]

    # Preserve HNSW order for untouched candidates
    remaining.sort(
        key=lambda x: x["rank_hnsw"]
    )

    # ------------------------------------------------------------
    # Complete 50-document ranking
    # ------------------------------------------------------------

    ranking.extend(
        remaining
    )

    return ranking


# ================================================================
# MAIN
# ================================================================

def main():

    print()
    print("=" * 70)
    print(
        "LUMINAR — CORRECTED CANDIDATE DEPTH BENCHMARK"
    )
    print("=" * 70)

    print()
    print(
        "Model      : "
        f"{MODEL_NAME}"
    )

    print(
        "Evaluation : Same 50 teacher-labeled "
        "candidates"
    )

    print(
        "Output     : Top-10"
    )

    print(
        "Depths     : Top-20 / Top-50"
    )

    # ============================================================
    # LOAD DATA
    # ============================================================

    data = load_dataset()

    queries = data["queries"]

    print()
    print(
        f"Queries : {len(queries)}"
    )

    # ------------------------------------------------------------
    # Verify candidate count
    # ------------------------------------------------------------

    candidate_counts = [
        len(query["candidates"])
        for query in queries
    ]

    min_candidates = min(
        candidate_counts
    )

    max_candidates = max(
        candidate_counts
    )

    print(
        f"Candidates/query : "
        f"{min_candidates}-{max_candidates}"
    )

    if min_candidates < 50:

        raise ValueError(
            "The evaluation dataset does not "
            "contain 50 candidates for every query."
        )

    # ============================================================
    # LOAD MODEL
    # ============================================================

    model = load_model()

    results_by_depth = {}

    # ============================================================
    # TEST EACH DEPTH
    # ============================================================

    for depth in CANDIDATE_DEPTHS:

        print()
        print("=" * 70)

        print(
            f"CANDIDATE DEPTH = TOP-{depth}"
        )

        print("=" * 70)

        metric_results = []

        times = []

        # --------------------------------------------------------
        # Each query
        # --------------------------------------------------------

        for query_number, query_data in enumerate(
            queries,
            start=1
        ):

            # ----------------------------------------------------
            # Complete 50-candidate ground truth
            # ----------------------------------------------------

            all_candidates = sorted(
                query_data["candidates"],
                key=lambda x: x["rank_hnsw"]
            )

            # ----------------------------------------------------
            # L6 reranking
            # ----------------------------------------------------

            reranked, elapsed = rerank(
                model,
                query_data,
                depth
            )

            # ----------------------------------------------------
            # Build complete 50-document ranking
            # ----------------------------------------------------

            evaluation_ranking = (
                build_evaluation_ranking(
                    all_candidates,
                    reranked
                )
            )

            # ----------------------------------------------------
            # Calculate metrics against SAME
            # 50-document ground truth.
            # ----------------------------------------------------

            metrics = calculate_metrics(
                evaluation_ranking
            )

            metric_results.append(
                metrics
            )

            times.append(
                elapsed
            )

            print(
                f"[{query_number:2d}/"
                f"{len(queries)}] "
                f"{elapsed:7.2f} ms"
            )

        # ========================================================
        # AGGREGATE
        # ========================================================

        avg_metrics = {}

        for metric in [
            "precision@10",
            "recall@10",
            "mrr@10",
            "ndcg@10"
        ]:

            avg_metrics[metric] = statistics.mean(
                result[metric]
                for result in metric_results
            )

        avg_time = statistics.mean(
            times
        )

        median_time = statistics.median(
            times
        )

        p95_time = np.percentile(
            times,
            95
        )

        results_by_depth[depth] = {
            "metrics": avg_metrics,
            "average_ms": avg_time,
            "median_ms": median_time,
            "p95_ms": p95_time
        }

        # ========================================================
        # PRINT RESULTS
        # ========================================================

        print()
        print(
            f"TOP-{depth} RESULTS"
        )

        print(
            f"Precision@10 : "
            f"{avg_metrics['precision@10']:.4f}"
        )

        print(
            f"Recall@10    : "
            f"{avg_metrics['recall@10']:.4f}"
        )

        print(
            f"MRR@10       : "
            f"{avg_metrics['mrr@10']:.4f}"
        )

        print(
            f"NDCG@10      : "
            f"{avg_metrics['ndcg@10']:.4f}"
        )

        print()

        print(
            f"Average time : "
            f"{avg_time:.2f} ms"
        )

        print(
            f"Median time  : "
            f"{median_time:.2f} ms"
        )

        print(
            f"P95 time     : "
            f"{p95_time:.2f} ms"
        )

    # ============================================================
    # FINAL COMPARISON
    # ============================================================

    print()
    print("=" * 70)
    print(
        "FINAL CANDIDATE DEPTH COMPARISON"
    )
    print("=" * 70)

    print()

    print(
        f"{'Depth':<10}"
        f"{'Precision':>12}"
        f"{'Recall':>12}"
        f"{'MRR':>12}"
        f"{'NDCG':>12}"
        f"{'Avg ms':>12}"
    )

    print("-" * 70)

    for depth in CANDIDATE_DEPTHS:

        result = results_by_depth[
            depth
        ]

        metrics = result[
            "metrics"
        ]

        print(
            f"Top-{depth:<6}"
            f"{metrics['precision@10']:>12.4f}"
            f"{metrics['recall@10']:>12.4f}"
            f"{metrics['mrr@10']:>12.4f}"
            f"{metrics['ndcg@10']:>12.4f}"
            f"{result['average_ms']:>12.2f}"
        )

    # ============================================================
    # COMPARE
    # ============================================================

    print()
    print("=" * 70)
    print("DEPTH TRADE-OFF")
    print("=" * 70)

    top20 = results_by_depth[20]
    top50 = results_by_depth[50]

    ndcg20 = top20["metrics"]["ndcg@10"]
    ndcg50 = top50["metrics"]["ndcg@10"]

    time20 = top20["average_ms"]
    time50 = top50["average_ms"]

    print()

    print(
        f"Top-20 NDCG@10 : {ndcg20:.4f}"
    )

    print(
        f"Top-50 NDCG@10 : {ndcg50:.4f}"
    )

    print()

    print(
        f"Top-20 latency : {time20:.2f} ms"
    )

    print(
        f"Top-50 latency : {time50:.2f} ms"
    )

    latency_saving = (
        (time50 - time20)
        / time50
        * 100
    )

    print()

    print(
        f"Top-20 latency saving : "
        f"{latency_saving:.2f}%"
    )

    # ============================================================
    # RECOMMENDATION
    # ============================================================

    print()
    print("=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)

    print()

    ndcg_difference = abs(
        ndcg20 - ndcg50
    )

    if ndcg20 >= ndcg50:

        print(
            "Top-20 currently provides "
            "the better NDCG@10."
        )

    else:

        print(
            "Top-50 currently provides "
            "the better NDCG@10."
        )

    print()

    if ndcg_difference < 0.02:

        print(
            "The NDCG difference is small "
            "(< 0.02)."
        )

        if time20 < time50:

            print(
                "Recommendation: TOP-20"
            )

            print(
                "Reason: Similar ranking quality "
                "with significantly lower latency."
            )

        else:

            print(
                "Recommendation: TOP-50"
            )

    else:

        best_depth = (
            20
            if ndcg20 > ndcg50
            else 50
        )

        print(
            f"Recommendation: TOP-{best_depth}"
        )

        print(
            "Reason: It provides the higher "
            "NDCG@10."
        )

    print()
    print("=" * 70)
    print(
        "CORRECTED CANDIDATE DEPTH "
        "BENCHMARK COMPLETE"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()