"""
LuminaR RAG Retrieval Diagnostic Tool

Offline scoring experiment tool that:
1. Runs retrieval + reranking with current production weights
2. Exposes all three signals (FAISS, CE, Evidence)
3. Shows the production ranking
4. Tests alternative scoring formulas
5. Compares rankings across formulas

Usage:
    python -m rag.diagnose_retrieval \
        --query "Why does Victor create the creature?" \
        --work_id OL45326637W \
        --top_k 20
"""

import argparse
import sys
import time

from rag.reranker import RAGReranker
from rag.evidence import (
    normalize_scores_minmax,
    detect_query_intent,
    CROSSENCODER_WEIGHT,
    EVIDENCE_WEIGHT,
    FAISS_WEIGHT,
)
from rag.llm import LuminaRLLM
import os


def run_diagnostic(query, work_id, top_k, track_chunks):

    print()
    print("=" * 72)
    print("  LUMINAR RETRIEVAL DIAGNOSTIC")
    print("=" * 72)
    print()
    print(f"  Query    : {query}")
    print(f"  Work ID  : {work_id}")
    print(f"  Top K    : {top_k}")
    
    os.environ["LUMINAR_MOCK_LLM"] = "1"
    llm = LuminaRLLM()
    intent_data = llm.analyze_intent(query)
    
    print(f"  Intent Data: {intent_data}")
    print(f"  Weights  : CE={CROSSENCODER_WEIGHT:.0%} "
          f"EV={EVIDENCE_WEIGHT:.0%} "
          f"FAISS={FAISS_WEIGHT:.0%}")

    if track_chunks:
        print(f"  Tracking : {', '.join(track_chunks)}")

    print()

    # ----------------------------------------------------------
    # LOAD RERANKER (loads retriever + crossencoder)
    # ----------------------------------------------------------

    reranker = RAGReranker()

    # ----------------------------------------------------------
    # RUN SEARCH — get candidates with top_k
    # We need all candidates, so request a large top_k
    # ----------------------------------------------------------

    result = reranker.search(
        query=query,
        top_k=50,
        work_id=work_id,
        document_id=None,
        intent_data=intent_data
    )

    candidates = result.get("results", [])

    if not candidates:
        print("\n  No candidates returned.\n")
        return

    print()
    print("-" * 72)
    print(f"  Retrieval queries: {result.get('retrieval_queries', [])}")
    print(f"  Total candidates : {result.get('candidate_count', 0)}")
    print(f"  Returned         : {len(candidates)}")

    weights = result.get("scoring_weights", {})
    print(f"  Production wts   : CE={weights.get('crossencoder', 0):.0%} "
          f"EV={weights.get('evidence', 0):.0%} "
          f"FAISS={weights.get('faiss', 0):.0%}")
    print("-" * 72)

    # ----------------------------------------------------------
    # Ensure FAISS norm is on all items
    # ----------------------------------------------------------

    for item in candidates:
        if "faiss_norm" not in item:
            item["faiss_norm"] = 0.0
        if "faiss_score" not in item:
            item["faiss_score"] = item.get("score", 0.0)

    # ----------------------------------------------------------
    # PRINT PRODUCTION RANKING
    # ----------------------------------------------------------

    print()
    print("=" * 72)
    print(f"  PRODUCTION: CE={CROSSENCODER_WEIGHT:.0%} "
          f"EV={EVIDENCE_WEIGHT:.0%} FAISS={FAISS_WEIGHT:.0%}")
    print("=" * 72)

    _print_ranking(candidates, track_chunks, "final_score")

    # ----------------------------------------------------------
    # COMPARISON TABLE
    # ----------------------------------------------------------

    print()
    print("=" * 72)
    print("  RANKING SUMMARY")
    print("=" * 72)
    print()
    print(f"  {'Chunk ID':<28} {'Rank':>4} {'Final':>7} {'CE_n':>6} "
          f"{'Evid':>6} {'FAISS_n':>7}  Chapter")
    print(f"  {'-'*28} {'----':>4} {'-------':>7} {'------':>6} "
          f"{'------':>6} {'-------':>7}  -------")

    for rank, item in enumerate(candidates, start=1):
        cid = item.get("chunk_id", "?")
        is_tracked = cid in track_chunks
        marker = " ***" if is_tracked else ""
        chapter = item.get("chapter", "?")

        print(
            f"  {cid:<28} {rank:>4} "
            f"{item.get('final_score', 0):>7.4f} "
            f"{item.get('normalized_rerank_score', 0):>6.3f} "
            f"{item.get('evidence_score', 0):>6.3f} "
            f"{item.get('faiss_norm', 0):>7.4f}  "
            f"{chapter}{marker}"
        )

    # Track chunks summary
    if track_chunks:
        print()
        print("  TRACKED CHUNKS:")
        for cid in track_chunks:
            found = False
            for rank, item in enumerate(candidates, start=1):
                if item.get("chunk_id") == cid:
                    print(f"    {cid}: rank={rank} "
                          f"final={item.get('final_score', 0):.4f} "
                          f"CE_n={item.get('normalized_rerank_score', 0):.3f} "
                          f"EV={item.get('evidence_score', 0):.3f} "
                          f"FAISS_n={item.get('faiss_norm', 0):.4f}")
                    found = True
                    break
            if not found:
                print(f"    {cid}: NOT IN TOP {top_k}")

    print()
    print("=" * 72)


def _print_ranking(items, track_chunks, score_key):

    print()
    print(f"  {'Rk':>3}  {'Chunk ID':<28} {'Score':>7} "
          f"{'CE_raw':>8} {'CE_n':>6} {'Evid':>6} "
          f"{'FAISS_r':>7} {'FAISS_n':>7}  Chapter")
    print(f"  {'---':>3}  {'-'*28} {'-------':>7} "
          f"{'--------':>8} {'------':>6} {'------':>6} "
          f"{'-------':>7} {'-------':>7}  -------")

    for rank, item in enumerate(items, start=1):

        cid = item.get("chunk_id", "?")
        is_tracked = cid in track_chunks
        marker = " ***" if is_tracked else ""
        chapter = item.get("chapter", "?")

        score = item.get(score_key, 0)
        ce_raw = item.get("rerank_score", 0)
        ce_n = item.get("normalized_rerank_score", 0)
        ev = item.get("evidence_score", 0)
        faiss_r = item.get("faiss_score", item.get("score", 0))
        faiss_n = item.get("faiss_norm", 0)

        signals = item.get("evidence_signals", [])
        sig_str = "; ".join(signals[:4]) if signals else ""

        print(
            f"  {rank:>3}  {cid:<28} {score:>7.4f} "
            f"{ce_raw:>8.3f} {ce_n:>6.3f} {ev:>6.3f} "
            f"{faiss_r:>7.4f} {faiss_n:>7.4f}  {chapter}{marker}"
        )

        if sig_str:
            print(f"       Signals: {sig_str}")

    print()


def main():

    parser = argparse.ArgumentParser(
        description="LuminaR Retrieval Diagnostic"
    )

    parser.add_argument(
        "--query",
        required=True,
        help="Query to diagnose"
    )

    parser.add_argument(
        "--work_id",
        default=None,
        help="Work ID to search within"
    )

    parser.add_argument(
        "--top_k",
        type=int,
        default=20,
        help="Number of candidates to show"
    )

    parser.add_argument(
        "--track",
        nargs="*",
        default=[],
        help="Chunk IDs to highlight in results"
    )

    args = parser.parse_args()

    run_diagnostic(
        query=args.query,
        work_id=args.work_id,
        top_k=args.top_k,
        track_chunks=args.track or []
    )


if __name__ == "__main__":
    main()
