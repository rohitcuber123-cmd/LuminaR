import re
from pathlib import Path
import time

import torch
from sentence_transformers import CrossEncoder

from rag.retriever import RAGRetriever
from rag.evidence import (
    generate_expanded_queries,
    calculate_evidence_score,
    normalize_scores_minmax,
    CROSSENCODER_WEIGHT,
    EVIDENCE_WEIGHT,
    FAISS_WEIGHT,
)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

DEVICE = (
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)

# Number of candidates retrieved from FAISS
CANDIDATE_K = 15

# Number returned after reranking
FINAL_K = 5


# ============================================================
# RAG RERANKER
# ============================================================

class RAGReranker:

    def __init__(self):

        print()
        print("=" * 70)
        print("LUMINAR RAG RERANKER")
        print("=" * 70)

        print(
            f"Device : {DEVICE}"
        )

        # ----------------------------------------------------
        # LOAD RETRIEVER
        # ----------------------------------------------------

        print()
        print(
            "Loading RAG retriever..."
        )

        self.retriever = RAGRetriever()

        # ----------------------------------------------------
        # LOAD CROSS ENCODER
        # ----------------------------------------------------

        print()
        print(
            "Loading CrossEncoder..."
        )

        start = time.perf_counter()

        self.model = CrossEncoder(
            MODEL_NAME,
            device=DEVICE
        )

        load_time = (
            time.perf_counter()
            - start
        )

        print(
            f"Reranker load : "
            f"{load_time * 1000:.2f} ms"
        )

        # ----------------------------------------------------
        # WARM UP
        # ----------------------------------------------------

        print()
        print(
            "Warming CrossEncoder..."
        )

        self.model.predict(
            [
                (
                    "What is an autoencoder?",
                    "An autoencoder compresses and reconstructs data."
                )
            ]
        )

        print(
            "CrossEncoder warm-up complete."
        )

        print()
        print(
            "RAG reranker ready."
        )

    # ========================================================
    # SEARCH + RERANK
    # ========================================================

    def search(
        self,
        query,
        top_k=FINAL_K,
        document_id=None,
        work_id=None,
        intent_data=None
    ):

        # ----------------------------------------------------
        # NORMALIZE QUERY
        # ----------------------------------------------------

        if query is None:

            query = ""

        query = str(
            query
        ).strip()

        if not query:

            return {
                "query": query,
                "work_id": work_id,
                "results": []
            }

        # ----------------------------------------------------
        # BACKWARDS COMPATIBILITY
        #
        # Existing callers may still send document_id.
        # Retriever already handles document_id as work_id.
        # ----------------------------------------------------

        if (
            not work_id
            and document_id
        ):

            work_id = document_id

        # ----------------------------------------------------
        # NORMALIZE TOP K
        # ----------------------------------------------------

        try:

            top_k = int(
                top_k
            )

        except (
            TypeError,
            ValueError
        ):

            top_k = FINAL_K

        if top_k < 1:

            top_k = 1

        # ----------------------------------------------------
        # EXPAND QUERIES
        #
        # Uses generic concept-aware expansion from
        # evidence.py — no book-specific logic.
        # ----------------------------------------------------
        
        is_book_rag = bool(work_id and work_id != document_id)
        if work_id and not document_id:
            is_book_rag = True

        if is_book_rag:
            retrieval_queries = (
                generate_expanded_queries(query)
            )
        else:
            retrieval_queries = [query]

        # ----------------------------------------------------
        # RETRIEVE CANDIDATES (MULTI-QUERY)
        # ----------------------------------------------------
        
        MAX_MULTIQ_CANDIDATES = 40
        best_scores = {}
        
        total_embedding_ms = 0
        total_faiss_ms = 0
        
        for q in retrieval_queries:
            retrieval = self.retriever.search(
                query=q,
                top_k=CANDIDATE_K,
                document_id=document_id,
                work_id=work_id
            )
            
            timing = retrieval.get("timing_ms", {})
            total_embedding_ms += timing.get("embedding", 0)
            total_faiss_ms += timing.get("faiss", 0)
            
            for item in retrieval.get("results", []):
                chunk_id = item.get("chunk_id")
                # Keep track of which queries matched this chunk
                if chunk_id not in best_scores:
                    item["matched_queries"] = [q]
                    best_scores[chunk_id] = item
                else:
                    if q not in best_scores[chunk_id]["matched_queries"]:
                        best_scores[chunk_id]["matched_queries"].append(q)
                        
        candidates = list(best_scores.values())
        
        # Sort by FAISS score (just to ensure we keep the top ones if we truncate)
        # Higher inner product or lower L2 distance? Usually FAISS results are already sorted by retriever. 
        # We can just take the first MAX_MULTIQ_CANDIDATES as they appeared in order.
        candidates = candidates[:MAX_MULTIQ_CANDIDATES]

        if not candidates:

            return {
                "query": query,
                "retrieval_queries": retrieval_queries,
                "work_id": work_id,
                "candidate_count": 0,
                "final_count": 0,
                "timing_ms": {
                    "embedding": total_embedding_ms,
                    "faiss": total_faiss_ms,
                    "reranking": 0,
                    "evidence": 0,
                },
                "results": []
            }

        # ----------------------------------------------------
        # CREATE QUERY / DOCUMENT PAIRS
        # ----------------------------------------------------

        pairs = []

        for item in candidates:

            text = item.get(
                "text",
                ""
            )

            if not text:
                text = " "

            pairs.append(
                (
                    query,
                    text
                )
            )

        # ----------------------------------------------------
        # CROSSENCODER RERANK
        # ----------------------------------------------------

        start = time.perf_counter()

        scores = self.model.predict(
            pairs
        )

        rerank_time = (
            time.perf_counter()
            - start
        )

        # ----------------------------------------------------
        # ATTACH RAW CROSSENCODER SCORES
        # ----------------------------------------------------

        raw_scores = []

        for item, score in zip(
            candidates,
            scores
        ):

            item["rerank_score"] = float(score)
            raw_scores.append(float(score))

        # ----------------------------------------------------
        # NORMALIZE CROSSENCODER SCORES
        # ----------------------------------------------------

        normalized = normalize_scores_minmax(
            raw_scores
        )

        for item, norm_score in zip(
            candidates,
            normalized
        ):

            item[
                "normalized_rerank_score"
            ] = norm_score

        # ----------------------------------------------------
        # EVIDENCE SCORING
        # ----------------------------------------------------

        evidence_start = time.perf_counter()

        for item in candidates:

            text = item.get("text", "")

            ev_score, ev_signals, ev_metrics = (
                calculate_evidence_score(
                    original_query=query,
                    expanded_queries=(
                        retrieval_queries
                    ),
                    chunk_text=text,
                    chunk_metadata=item,
                    all_chunks_dict=self.retriever.chunk_texts,
                    intent_data=intent_data
                )
            )

            item["evidence_score"] = ev_score
            item["evidence_signals"] = ev_signals
            item.update(ev_metrics)

        evidence_time = (
            time.perf_counter()
            - evidence_start
        )

        # ----------------------------------------------------
        # NORMALIZE FAISS SCORES
        # ----------------------------------------------------

        faiss_raw_scores = []

        for item in candidates:

            fs = float(
                item.get(
                    "score",
                    item.get("faiss_score", 0.0)
                )
            )

            faiss_raw_scores.append(fs)

        faiss_normalized = normalize_scores_minmax(
            faiss_raw_scores
        )

        for item, fn in zip(
            candidates,
            faiss_normalized
        ):

            item["faiss_score"] = float(
                item.get(
                    "score",
                    item.get("faiss_score", 0.0)
                )
            )

            item["faiss_norm"] = fn

        # ----------------------------------------------------
        # HYBRID FINAL SCORE
        #
        # final = CE_weight * CE_norm
        #       + EV_weight * evidence
        #       + FAISS_weight * faiss_norm
        # ----------------------------------------------------

        for item in candidates:

            item["final_score"] = (
                CROSSENCODER_WEIGHT
                * item["normalized_rerank_score"]
                + EVIDENCE_WEIGHT
                * item["evidence_score"]
                + FAISS_WEIGHT
                * item["faiss_norm"]
            )

        # ----------------------------------------------------
        # SORT BY FINAL HYBRID SCORE
        # ----------------------------------------------------

        candidates.sort(
            key=lambda x:
                x["final_score"],
            reverse=True
        )

        # ----------------------------------------------------
        # FINAL RESULTS
        # ----------------------------------------------------

        final_results = []

        for rank, item in enumerate(
            candidates[:top_k],
            start=1
        ):

            item["rank"] = rank

            # Preserve FAISS score under both
            # names for backward compatibility
            if "score" in item:
                item["faiss_score"] = item["score"]

            final_results.append(
                item
            )

        # ----------------------------------------------------
        # RETURN
        # ----------------------------------------------------

        return {
            "query":
                query,
                
            "retrieval_queries":
                retrieval_queries,

            "work_id":
                work_id,

            "candidate_count":
                len(candidates),

            "final_count":
                len(final_results),

            "scoring_weights": {
                "crossencoder":
                    CROSSENCODER_WEIGHT,
                "evidence":
                    EVIDENCE_WEIGHT,
                "faiss":
                    FAISS_WEIGHT,
            },

            "timing_ms": {

                "embedding":
                    total_embedding_ms,

                "faiss":
                    total_faiss_ms,

                "reranking":
                    round(
                        rerank_time
                        * 1000,
                        2
                    ),

                "evidence":
                    round(
                        evidence_time
                        * 1000,
                        2
                    ),

                "total":
                    round(
                        (
                            total_embedding_ms / 1000.0
                            + total_faiss_ms / 1000.0
                            + rerank_time
                            + evidence_time
                        ) * 1000,
                        2
                    )
            },

            "results":
                final_results
        }


# ============================================================
# CLI TEST
# ============================================================

def main():

    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "LuminaR RAG Retriever + Reranker"
        )
    )

    parser.add_argument(
        "--query",
        required=True
    )

    parser.add_argument(
        "--top_k",
        type=int,
        default=5
    )

    parser.add_argument(
        "--document",
        default=None
    )

    parser.add_argument(
        "--work_id",
        default=None
    )

    args = parser.parse_args()

    reranker = RAGReranker()

    result = reranker.search(
        query=args.query,
        top_k=args.top_k,
        document_id=args.document,
        work_id=args.work_id
    )

    print()
    print("=" * 70)
    print("RAG RERANKED RESULTS")
    print("=" * 70)

    print()
    print(
        f"Query : "
        f"{result['query']}"
    )

    print(
        f"Mode  : "
        f"{'BOOK' if result.get('work_id') else 'GLOBAL'}"
    )

    if result.get("work_id"):

        print(
            f"Work ID : "
            f"{result['work_id']}"
        )

    print(
        f"Candidates : "
        f"{result.get('candidate_count', 0)}"
    )

    print(
        f"Final      : "
        f"{result.get('final_count', 0)}"
    )

    weights = result.get(
        "scoring_weights", {}
    )

    print(
        f"Weights    : "
        f"CE={weights.get('crossencoder', 0):.0%} "
        f"EV={weights.get('evidence', 0):.0%}"
    )

    if "timing_ms" in result:

        print()

        print(
            f"Embedding : "
            f"{result['timing_ms']['embedding']} ms"
        )

        print(
            f"FAISS     : "
            f"{result['timing_ms']['faiss']} ms"
        )

        print(
            f"Reranking : "
            f"{result['timing_ms']['reranking']} ms"
        )

        print(
            f"Evidence  : "
            f"{result['timing_ms']['evidence']} ms"
        )

    print()

    for item in result["results"]:

        print("-" * 70)

        print(
            f"Rank          : "
            f"{item['rank']}"
        )

        print(
            f"Final score   : "
            f"{item.get('final_score', 0):.4f}"
        )

        print(
            f"CE raw        : "
            f"{item.get('rerank_score', 0):.4f}"
        )

        print(
            f"CE normalized : "
            f"{item.get('normalized_rerank_score', 0):.4f}"
        )

        print(
            f"Evidence      : "
            f"{item.get('evidence_score', 0):.4f}"
        )

        print(
            f"FAISS score   : "
            f"{item.get('score', 0):.4f}"
        )

        print(
            f"Title         : "
            f"{item.get('title')}"
        )

        print(
            f"Author        : "
            f"{item.get('author')}"
        )

        print(
            f"Chapter       : "
            f"{item.get('chapter')}"
        )

        print(
            f"Work ID       : "
            f"{item.get('work_id')}"
        )

        print(
            f"Document      : "
            f"{item.get('filename')}"
        )

        print(
            f"Chunk ID      : "
            f"{item.get('chunk_id')}"
        )

        ev_signals = item.get(
            "evidence_signals", []
        )

        if ev_signals:
            print(
                f"Signals       : "
                f"{'; '.join(ev_signals[:5])}"
            )

        print()

        print(
            item["text"]
        )

    print()
    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()