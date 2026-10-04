"""
AstraLib — Automatic Relevance Label Generation

Converts raw teacher scores into query-relative relevance labels.

For every query with 50 candidates:

    Top 20%  -> 2 (Highly Relevant)
    Next 30% -> 1 (Somewhat Relevant)
    Bottom 50% -> 0 (Irrelevant)

This avoids using a global teacher-score threshold because
teacher score distributions vary significantly between queries.
"""

import json
import os
from collections import Counter


BASE_DIR = "D:/SDC/LibraryLLM"

INPUT_FILE = os.path.join(
    BASE_DIR,
    "datasets/ai/evaluation/raw_teacher_judgments.json"
)

OUTPUT_FILE = os.path.join(
    BASE_DIR,
    "datasets/ai/evaluation/labeled_evaluation_dataset.json"
)


def create_labels(candidates):

    # Sort by teacher score, highest first
    ranked = sorted(
        candidates,
        key=lambda x: x["teacher_score"],
        reverse=True
    )

    total = len(ranked)

    highly_relevant_count = round(
        total * 0.20
    )

    somewhat_relevant_count = round(
        total * 0.30
    )

    for i, candidate in enumerate(ranked):

        if i < highly_relevant_count:

            candidate["relevance"] = 2

        elif i < (
            highly_relevant_count
            + somewhat_relevant_count
        ):

            candidate["relevance"] = 1

        else:

            candidate["relevance"] = 0

    # Restore original HNSW order
    ranked.sort(
        key=lambda x: x["rank_hnsw"]
    )

    return ranked


def main():

    print("=" * 70)
    print(
        "ASTRALIB — AUTOMATIC RELEVANCE LABEL GENERATION"
    )
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

    labeled_queries = []

    total_counts = Counter()

    print()

    for query_number, query_data in enumerate(
        data["queries"],
        start=1
    ):

        query = query_data["query"]

        candidates = query_data[
            "candidates"
        ]

        labeled_candidates = create_labels(
            candidates
        )

        counts = Counter(
            candidate["relevance"]
            for candidate in labeled_candidates
        )

        total_counts.update(counts)

        labeled_queries.append(
            {
                "query": query,

                "candidate_count":
                    len(labeled_candidates),

                "candidates":
                    labeled_candidates
            }
        )

        print(
            f"Query {query_number:2d}/"
            f"{len(data['queries'])}: "
            f"{query}"
        )

        print(
            f"  Relevance 2 : "
            f"{counts[2]}"
        )

        print(
            f"  Relevance 1 : "
            f"{counts[1]}"
        )

        print(
            f"  Relevance 0 : "
            f"{counts[0]}"
        )

    # ============================================================
    # SAVE
    # ============================================================

    output = {

        "configuration": {

            "source":
                "raw_teacher_judgments.json",

            "teacher_model":
                data[
                    "configuration"
                ]["teacher_model"],

            "candidate_k":
                data[
                    "configuration"
                ]["candidate_k"],

            "labeling_method":
                "query-relative-percentile",

            "highly_relevant":
                "top 20%",

            "somewhat_relevant":
                "next 30%",

            "irrelevant":
                "bottom 50%"
        },

        "queries":
            labeled_queries
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            indent=2,
            ensure_ascii=False
        )

    # ============================================================
    # SUMMARY
    # ============================================================

    print()
    print("=" * 70)
    print("LABELING COMPLETE")
    print("=" * 70)

    total = sum(
        total_counts.values()
    )

    print(
        f"Queries      : "
        f"{len(labeled_queries)}"
    )

    print(
        f"Candidates   : "
        f"{total:,}"
    )

    print()

    for label in [2, 1, 0]:

        count = total_counts[label]

        percentage = (
            count / total
        ) * 100

        name = {
            2: "Highly Relevant",
            1: "Somewhat Relevant",
            0: "Irrelevant"
        }[label]

        print(
            f"{label} = {name:<18} "
            f"{count:4d} "
            f"({percentage:.2f}%)"
        )

    print()

    print(
        "Output:"
    )

    print(
        OUTPUT_FILE
    )

    print()
    print(
        "The dataset is now ready for "
        "retrieval evaluation."
    )

    print("=" * 70)


if __name__ == "__main__":
    main()