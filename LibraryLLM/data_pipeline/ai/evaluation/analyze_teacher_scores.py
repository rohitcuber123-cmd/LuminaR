"""
AstraLib — Analyze Teacher Score Distribution

Reads raw teacher judgments and analyzes the score distribution
before relevance thresholds are selected.
"""

import json
import os
import numpy as np


BASE_DIR = "D:/SDC/LibraryLLM"

INPUT_FILE = os.path.join(
    BASE_DIR,
    "datasets/ai/evaluation/raw_teacher_judgments.json"
)


def main():

    print("=" * 70)
    print("ASTRALIB — TEACHER SCORE DISTRIBUTION")
    print("=" * 70)

    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"Input file not found:\n{INPUT_FILE}"
        )

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    queries = data["queries"]

    scores = []

    for query_data in queries:

        for candidate in query_data["candidates"]:

            scores.append(
                candidate["teacher_score"]
            )

    scores = np.array(
        scores,
        dtype=np.float32
    )

    print()
    print("Dataset:")
    print(
        f"Queries       : {len(queries)}"
    )

    print(
        f"Candidates    : {len(scores):,}"
    )

    print()

    # ============================================================
    # BASIC STATISTICS
    # ============================================================

    print("=" * 70)
    print("BASIC STATISTICS")
    print("=" * 70)

    print(
        f"Minimum       : {scores.min():.4f}"
    )

    print(
        f"Maximum       : {scores.max():.4f}"
    )

    print(
        f"Mean          : {scores.mean():.4f}"
    )

    print(
        f"Median        : {np.median(scores):.4f}"
    )

    print(
        f"Std deviation : {scores.std():.4f}"
    )

    print()

    # ============================================================
    # PERCENTILES
    # ============================================================

    print("=" * 70)
    print("PERCENTILES")
    print("=" * 70)

    percentiles = [
        1,
        5,
        10,
        20,
        25,
        50,
        75,
        80,
        90,
        95,
        99
    ]

    for p in percentiles:

        value = np.percentile(
            scores,
            p
        )

        print(
            f"P{p:<2}          : {value:.4f}"
        )

    print()

    # ============================================================
    # SCORE RANGES
    # ============================================================

    print("=" * 70)
    print("SCORE DISTRIBUTION")
    print("=" * 70)

    ranges = [
        ("< 2", -np.inf, 2),
        ("2 - 3", 2, 3),
        ("3 - 4", 3, 4),
        ("4 - 5", 4, 5),
        ("5 - 6", 5, 6),
        ("6 - 7", 6, 7),
        ("7 - 8", 7, 8),
        ("8 - 9", 8, 9),
        (">= 9", 9, np.inf),
    ]

    for name, low, high in ranges:

        count = np.sum(
            (scores >= low) &
            (scores < high)
        )

        percentage = (
            count / len(scores)
        ) * 100

        print(
            f"{name:<8} : "
            f"{count:4d} "
            f"({percentage:6.2f}%)"
        )

    print()

    # ============================================================
    # TOP SCORES
    # ============================================================

    print("=" * 70)
    print("TOP 20 TEACHER SCORES")
    print("=" * 70)

    flat_candidates = []

    for query_data in queries:

        query = query_data["query"]

        for candidate in query_data["candidates"]:

            flat_candidates.append(
                {
                    "query": query,
                    "work_id":
                        candidate["work_id"],
                    "score":
                        candidate["teacher_score"],
                    "title":
                        candidate.get(
                            "title",
                            ""
                        )
                }
            )

    flat_candidates.sort(
        key=lambda x:
            x["score"],
        reverse=True
    )

    for i, item in enumerate(
        flat_candidates[:20],
        start=1
    ):

        print(
            f"{i:2d}. "
            f"{item['score']:.4f}  "
            f"{item['work_id']}  "
            f"{item['title']}"
        )

    print()

    # ============================================================
    # LOWEST SCORES
    # ============================================================

    print("=" * 70)
    print("BOTTOM 20 TEACHER SCORES")
    print("=" * 70)

    for i, item in enumerate(
        flat_candidates[-20:],
        start=1
    ):

        print(
            f"{i:2d}. "
            f"{item['score']:.4f}  "
            f"{item['work_id']}  "
            f"{item['title']}"
        )

    print()

    # ============================================================
    # QUERY-LEVEL STATISTICS
    # ============================================================

    print("=" * 70)
    print("QUERY-LEVEL SCORE STATISTICS")
    print("=" * 70)

    for query_data in queries:

        query = query_data["query"]

        query_scores = np.array(
            [
                c["teacher_score"]
                for c in query_data["candidates"]
            ],
            dtype=np.float32
        )

        print()
        print(
            f"Query: {query}"
        )

        print(
            f"  Min    : {query_scores.min():.4f}"
        )

        print(
            f"  Median : {np.median(query_scores):.4f}"
        )

        print(
            f"  Max    : {query_scores.max():.4f}"
        )

    print()
    print("=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)

    print()
    print(
        "No relevance labels have been created."
    )

    print(
        "Use these statistics to select "
        "appropriate thresholds."
    )


if __name__ == "__main__":
    main()