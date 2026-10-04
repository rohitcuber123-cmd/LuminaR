import json
import os
import time

import numpy as np

from luminar_search import LuminaRSearchEngine


# ============================================================
# PATH
# ============================================================

BASE_DIR = r"D:\SDC\LibraryLLM"

LABEL_PATH = os.path.join(
    BASE_DIR,
    "datasets",
    "ai",
    "evaluation",
    "labeled_evaluation_dataset.json"
)


# ============================================================
# METRICS
# ============================================================

def precision_at_k(retrieved, labels, k=10):

    retrieved = retrieved[:k]

    if not retrieved:
        return 0.0

    hits = sum(
        1
        for work_id in retrieved
        if labels.get(work_id, 0) > 0
    )

    return hits / k


def recall_at_k(retrieved, labels, k=10):

    retrieved = retrieved[:k]

    relevant_ids = {
        work_id
        for work_id, relevance in labels.items()
        if relevance > 0
    }

    if not relevant_ids:
        return 0.0

    hits = sum(
        1
        for work_id in retrieved
        if work_id in relevant_ids
    )

    return hits / len(relevant_ids)


def mrr_at_k(retrieved, labels, k=10):

    retrieved = retrieved[:k]

    for rank, work_id in enumerate(
        retrieved,
        start=1
    ):

        if labels.get(work_id, 0) > 0:
            return 1.0 / rank

    return 0.0


def dcg_at_k(retrieved, labels, k=10):

    retrieved = retrieved[:k]

    score = 0.0

    for rank, work_id in enumerate(
        retrieved,
        start=1
    ):

        relevance = labels.get(
            work_id,
            0
        )

        score += (
            (2 ** relevance - 1)
            / np.log2(rank + 1)
        )

    return score


def ndcg_at_k(retrieved, labels, k=10):

    actual = dcg_at_k(
        retrieved,
        labels,
        k
    )

    ideal_relevances = sorted(
        labels.values(),
        reverse=True
    )[:k]

    ideal = 0.0

    for rank, relevance in enumerate(
        ideal_relevances,
        start=1
    ):

        ideal += (
            (2 ** relevance - 1)
            / np.log2(rank + 1)
        )

    if ideal == 0:
        return 0.0

    return actual / ideal


# ============================================================
# LOAD DATASET
# ============================================================

print("=" * 70)
print("LUMINAR — RETRIEVAL QUALITY EVALUATION")
print("=" * 70)

print()
print("Loading labeled evaluation dataset...")

with open(
    LABEL_PATH,
    "r",
    encoding="utf-8"
) as f:

    dataset = json.load(f)


queries = dataset["queries"]

print(
    f"Queries     : {len(queries)}"
)

print(
    f"Candidates  : "
    f"{sum(q['candidate_count'] for q in queries)}"
)

print(
    f"Teacher     : "
    f"{dataset['configuration']['teacher_model']}"
)

print(
    f"Candidate K : "
    f"{dataset['configuration']['candidate_k']}"
)


# ============================================================
# LOAD LUMINAR
# ============================================================

print()
print("Loading LuminaR search engine...")

engine = LuminaRSearchEngine()


# ============================================================
# STORAGE
# ============================================================

precision_scores = []
recall_scores = []
mrr_scores = []
ndcg_scores = []
latencies = []


# ============================================================
# EVALUATION
# ============================================================

print()
print("=" * 70)
print("EVALUATION")
print("=" * 70)


for query_number, item in enumerate(
    queries,
    start=1
):

    query = item["query"]

    candidates = item["candidates"]


    # --------------------------------------------------------
    # BUILD RELEVANCE LABELS
    # --------------------------------------------------------

    labels = {}

    for candidate in candidates:

        work_id = str(
            candidate["work_id"]
        )

        relevance = int(
            candidate["relevance"]
        )

        labels[work_id] = relevance


    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    start = time.perf_counter()

    result = engine.search(
        query=query,
        top_k=10
    )

    latency = (
        time.perf_counter()
        - start
    ) * 1000

    latencies.append(
        latency
    )


    # --------------------------------------------------------
    # RETRIEVED IDS
    # --------------------------------------------------------

    retrieved = [
        str(result_item["work_id"])
        for result_item
        in result["results"]
    ]


    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    precision = precision_at_k(
        retrieved,
        labels,
        10
    )

    recall = recall_at_k(
        retrieved,
        labels,
        10
    )

    mrr = mrr_at_k(
        retrieved,
        labels,
        10
    )

    ndcg = ndcg_at_k(
        retrieved,
        labels,
        10
    )


    precision_scores.append(
        precision
    )

    recall_scores.append(
        recall
    )

    mrr_scores.append(
        mrr
    )

    ndcg_scores.append(
        ndcg
    )


    print(
        f"[{query_number:02d}/{len(queries)}] "
        f"P@10={precision:.4f} "
        f"R@10={recall:.4f} "
        f"MRR={mrr:.4f} "
        f"NDCG={ndcg:.4f} "
        f"Time={latency:.2f} ms"
    )


# ============================================================
# FINAL RESULTS
# ============================================================

print()
print("=" * 70)
print("LUMINAR RETRIEVAL RESULTS")
print("=" * 70)

print()

print(
    f"Precision@10 : "
    f"{np.mean(precision_scores):.4f}"
)

print(
    f"Recall@10    : "
    f"{np.mean(recall_scores):.4f}"
)

print(
    f"MRR@10       : "
    f"{np.mean(mrr_scores):.4f}"
)

print(
    f"NDCG@10      : "
    f"{np.mean(ndcg_scores):.4f}"
)

print()

print(
    f"Average time : "
    f"{np.mean(latencies):.2f} ms"
)

print(
    f"Median time  : "
    f"{np.median(latencies):.2f} ms"
)

print(
    f"P95 time     : "
    f"{np.percentile(latencies, 95):.2f} ms"
)

print(
    f"Minimum time : "
    f"{np.min(latencies):.2f} ms"
)

print(
    f"Maximum time : "
    f"{np.max(latencies):.2f} ms"
)


# ============================================================
# COMPLETE
# ============================================================

print()
print("=" * 70)
print("EVALUATION COMPLETE")
print("=" * 70)


# ============================================================
# CLEANUP
# ============================================================

engine.close()