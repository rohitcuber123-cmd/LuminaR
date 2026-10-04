import os
import sys
import time
import re
import logging

from search.catalogue import current_books
from search.index_manager import IndexManager
from search.sync_queue import index_root
from search.lexical_store import default_path
from search.lexical_delta import LexicalDeltaWriter,LexicalOverlayStore
from search.lexical_integration import merge_lexical_candidates,lexical_rank_key
from dotenv import load_dotenv
from pathlib import Path

import faiss
import numpy as np
import torch

from pymongo import MongoClient

from sentence_transformers import (
    SentenceTransformer,
    CrossEncoder
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = str(Path(__file__).resolve().parents[1])

HNSW_DIR = os.path.join(
    BASE_DIR,
    "datasets",
    "ai",
    "faiss",
    "hnsw"
)

# ============================================================
# MONGODB
# ============================================================

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DATABASE = os.getenv("MONGO_DB_NAME", "luminar_library")


# ============================================================
# CONFIGURATION
# ============================================================

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

RERANKER_MODEL = (
    "cross-encoder/ms-marco-MiniLM-L-6-v2"
)

SEMANTIC_MIN_VALID_CANDIDATES = 50

CROSSENCODER_RERANK_DEPTH = 50

SEARCH_MAX_RETURN_RESULTS = 50

EF_SEARCH = 128

RERANK_BATCH_SIZE = 16
LOG = logging.getLogger(__name__)

WARMUP_ITERATIONS = 5


# ============================================================
# SEARCH ENGINE
# ============================================================

class LuminaRSearchEngine:

    @staticmethod
    def _norm_text(value):
        return re.sub(r"[^a-z0-9 ]+", " ", str(value or "").lower()).strip()

    def _author_match_ids(self, query, metadata):
        """Return IDs whose structured authors field exactly names query.

        This is deliberately conservative: it only matches an entire author
        value, never descriptions or arbitrary substrings.
        """
        q = self._norm_text(query)
        if not q or len(q.split()) < 2:
            return set()
        ids = set()
        for wid, book in metadata.items():
            authors = book.get("authors", [])
            if isinstance(authors, str):
                authors = [authors]
            if any(self._norm_text(a) == q for a in (authors or [])):
                ids.add(wid)
        return ids

    def __init__(self):

        print("=" * 60)
        print("LUMINAR SEARCH ENGINE")
        print("=" * 60)

        # ====================================================
        # DEVICE
        # ====================================================

        self.device = (
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )

        print(f"Device : {self.device}")

        if self.device == "cuda":
            print(
                "GPU    : "
                + torch.cuda.get_device_name(0)
            )

        # ====================================================
        # MINILM
        # ====================================================

        print()
        print("Loading MiniLM...")

        start = time.perf_counter()

        self.embedding_model = SentenceTransformer(
            EMBEDDING_MODEL,
            device=self.device,
            local_files_only=True
        )

        self.embedding_model.max_seq_length = 256
        self._sync_cuda()

        self.embedding_load_ms = (
            time.perf_counter() - start
        ) * 1000

        print(
            f"Embedding model load : "
            f"{self.embedding_load_ms:.2f} ms"
        )

        # ====================================================
        # MINILM WARMUP
        # ====================================================

        print("Warming MiniLM...")

        for _ in range(
            WARMUP_ITERATIONS
        ):

            self.embedding_model.encode(
                ["warmup query"],
                convert_to_numpy=True
            )

        self._sync_cuda()

        print(
            "MiniLM warm-up complete."
        )

        # ====================================================
        # L6 RERANKER
        # ====================================================

        print()
        print("Loading L6 reranker...")

        start = time.perf_counter()

        self.reranker = CrossEncoder(
            RERANKER_MODEL,
            device=self.device,
            local_files_only=True
        )

        self._sync_cuda()

        self.reranker_load_ms = (
            time.perf_counter() - start
        ) * 1000

        print(
            f"Reranker load : "
            f"{self.reranker_load_ms:.2f} ms"
        )

        # ====================================================
        # RERANKER WARMUP
        # ====================================================

        print("Warming reranker...")

        warmup_pairs = [
            [
                (
                    "books for learning "
                    "deep learning and "
                    "neural networks"
                ),
                (
                    "Title: Deep Learning\n"
                    "Authors: Test Author\n"
                    "Subjects: Neural networks"
                )
            ]
        ]

        for _ in range(
            WARMUP_ITERATIONS
        ):

            self.reranker.predict(
                warmup_pairs,
                batch_size=1,
                show_progress_bar=False
            )

        self._sync_cuda()

        print(
            "Reranker warm-up complete."
        )

        # ====================================================
        # MONGODB LIBRARY INVENTORY
        # ====================================================

        print()
        print(
            "Opening MongoDB "
            "library inventory..."
        )

        start = time.perf_counter()

        self.mongo_client = MongoClient(
            MONGO_URI
        )

        self.mongo_db = self.mongo_client[
            MONGO_DATABASE
        ]

        self.library_inventory = (
            self.mongo_db[
                "library_inventory"
            ]
        )
        
        # CRITICAL: Add books collection for authoritative availability
        self.books_collection = (
            self.mongo_db[
                "books"
            ]
        )

        self.inventory_load_ms = (
            time.perf_counter() - start
        ) * 1000

        print(
            "Library inventory ready."
        )

        start = time.perf_counter()
        self.index_manager = IndexManager(
            index_root(), self.books_collection, self.embedding_model,
            legacy_dir=Path(BASE_DIR) / "datasets/ai/embeddings")
        self.index_load_ms = (time.perf_counter() - start) * 1000
        self.metadata_load_ms = 0
        self.lexical_store = None
        self.lexical_writer = None
        try:
            self.lexical_store = LexicalOverlayStore(default_path(),
                expected_source_db=MONGO_DATABASE,event_queue=self.index_manager.queue)
            # Live mutation consumption stays opt-in until the full Search/API
            # recovery and bounded overlay tests can run safely.
            if (os.getenv("LUMINAR_LEXICAL_SYNC_ENABLED", "false").lower()=="true"
                    and self.lexical_store.health()["lexical_available"]):
                self.lexical_writer = LexicalDeltaWriter(
                    default_path(),self.books_collection,self.index_manager.queue,
                    expected_source_db=MONGO_DATABASE)
        except Exception as error:
            LOG.error("lexical_worker_unavailable error_type=%s",type(error).__name__)
        print("LuminaR search engine ready.")

    @property
    def index(self):
        # Compatibility for existing local diagnostics; health reports base+delta.
        return self.index_manager.snapshot.base

    @property
    def work_ids(self):
        return self.index_manager.snapshot.work_ids

    # ========================================================
    # CUDA SYNCHRONIZATION
    # ========================================================

    def _sync_cuda(self):

        if self.device == "cuda":
            torch.cuda.synchronize()

    # ========================================================
    # LIBRARY INVENTORY LOOKUP
    # ========================================================

    def _get_library_inventory(
        self,
        work_ids,
        library_id
    ):

        if not work_ids:
            return {}

        # CRITICAL FIX: Use books collection as authoritative source
        # The library_inventory collection only has 3 records
        # The books collection has 5 million records with real availability
        
        inventory_by_work_id = {}
        
        # Fetch from authoritative books collection
        books_cursor = self.books_collection.find(
            {
                "work_id": {
                    "$in": list(work_ids)
                }
            },
            {
                "_id": 0,
                "work_id": 1,
                "total_copies": 1,
                "available_copies": 1,
                "shelf_location": 1
            }
        )
        
        for book in books_cursor:
            inventory_by_work_id[book["work_id"]] = {
                "work_id": book["work_id"],
                "total_copies": book.get("total_copies", 0),
                "available_copies": book.get("available_copies", 0),
                "shelf_location": book.get("shelf_location")
            }
        
        # Fall back to library_inventory for any missing books (rare)
        if library_id:
            missing_work_ids = [wid for wid in work_ids if wid not in inventory_by_work_id]
            
            if missing_work_ids:
                inventory_cursor = self.library_inventory.find(
                    {
                        "library_id": library_id,
                        "work_id": {"$in": missing_work_ids}
                    },
                    {
                        "_id": 0,
                        "work_id": 1,
                        "total_copies": 1,
                        "available_copies": 1,
                        "shelf_location": 1,
                        "isbn": 1
                    }
                )
                
                for item in inventory_cursor:
                    inventory_by_work_id[item["work_id"]] = item

        return inventory_by_work_id

    # ========================================================
    # SEARCH
    # ========================================================

    def search(
        self,
        query,
        top_k=10,
        library_id=None,
        available_at_library=False,
        diagnostics=False
    ):

        query = query.strip()

        if not query:

            raise ValueError(
                "Query cannot be empty."
            )

        final_k = min(
            int(top_k),
            SEARCH_MAX_RETURN_RESULTS
        )

        total_start = (
            time.perf_counter()
        )

        # ====================================================
        # 1. QUERY EMBEDDING
        # ====================================================

        start = time.perf_counter()

        query_vector = self.index_manager.encode([query])

        self._sync_cuda()

        embedding_ms = (
            time.perf_counter()
            - start
        ) * 1000

        query_vector = np.asarray(
            query_vector,
            dtype=np.float32
        )

        faiss.normalize_L2(
            query_vector
        )

        # ====================================================
        # 2. HNSW
        # ====================================================

        start = time.perf_counter()

        # Capture base, delta and identity mappings from ONE immutable generation.
        snapshot = self.index_manager.snapshot
        factor = max(1, int(os.getenv("LUMINAR_SEARCH_OVERFETCH_FACTOR", "2")))
        limit = max(SEMANTIC_MIN_VALID_CANDIDATES, int(os.getenv("LUMINAR_SEARCH_MAX_CANDIDATES", "1000")))
        fetch_k = min(limit, max(SEMANTIC_MIN_VALID_CANDIDATES, top_k * factor))
        target = max(CROSSENCODER_RERANK_DEPTH, top_k)
        hnsw_ms = 0
        mongo_ms = 0
        while True:
            started = time.perf_counter()
            candidates = snapshot.candidates(query_vector, fetch_k)
            if 'raw_candidates' not in locals():
                raw_candidates = list(candidates)
            hnsw_ms += (time.perf_counter() - started) * 1000
            started = time.perf_counter()
            candidate_metadata = current_books(self.books_collection, [c["work_id"] for c in candidates])
            mongo_ms += (time.perf_counter() - started) * 1000
            candidates = [c for c in candidates if c["work_id"] in candidate_metadata]
            if (len(candidates) >= target or fetch_k >= limit
                    or fetch_k >= max(snapshot.base.ntotal, snapshot.delta.ntotal)):
                break
            fetch_k = min(limit, fetch_k * factor if factor > 1 else fetch_k + SEMANTIC_MIN_VALID_CANDIDATES)
        candidates = candidates[:target]
        lexical_ranking = os.getenv('LEXICAL_SEARCH_ENABLED','false').lower()=='true'
        lexical_evidence = {}
        if lexical_ranking:
            try:
                candidates,candidate_metadata,lexical_evidence = merge_lexical_candidates(
                    getattr(self,'lexical_store',None),query,candidates,candidate_metadata,
                    self.books_collection,current_books)
            except Exception as error:
                # Lexical is optional. Keep the already Mongo-validated semantic
                # candidates untouched if any lexical stage fails.
                LOG.warning('lexical_merge_unavailable error_type=%s',type(error).__name__)
                lexical_evidence={candidate['work_id']:{'semantic'} for candidate in candidates}
        author_ids = self._author_match_ids(query, candidate_metadata)
        start = time.perf_counter() - mongo_ms / 1000

        candidate_metadata_ms = (
            time.perf_counter()
            - start
        ) * 1000

        # ====================================================
        # 4. PAIR CONSTRUCTION
        # ====================================================

        start = time.perf_counter()

        pairs = []

        for candidate in candidates:

            metadata = (
                candidate_metadata.get(
                    candidate["work_id"],
                    {}
                )
            )

            book_text = (
                f"Title: "
                f"{str(metadata.get('title', ''))}\n"
                f"Authors: "
                f"{str(metadata.get('authors', ''))}\n"
                f"Subjects: "
                f"{str(metadata.get('subjects', ''))}"
            )

            pairs.append(
                [
                    query,
                    book_text
                ]
            )

        pair_ms = (
            time.perf_counter()
            - start
        ) * 1000

        # ====================================================
        # 5. L6 RERANKING
        # ====================================================

        self._sync_cuda()

        start = time.perf_counter()

        rerank_scores = (
            self.reranker.predict(
                pairs,
                batch_size=RERANK_BATCH_SIZE,
                show_progress_bar=False
            ) if pairs else []
        )

        self._sync_cuda()

        reranking_ms = (
            time.perf_counter()
            - start
        ) * 1000

        # ====================================================
        # 6. SORT
        # ====================================================

        ranked = list(
            zip(
                candidates,
                rerank_scores
            )
        )

        ranked.sort(
            key=lambda x: (-float(x[1]), -float(x[0]["hnsw_score"]), x[0]["work_id"])
        )

        # Structured author intent is a ranking signal only. Semantic matches
        # remain available as fallback and exact-title behavior is untouched.
        if lexical_ranking:
            ranked.sort(key=lambda item: lexical_rank_key(item[0],item[1],
                                                       lexical_evidence,author_ids),reverse=True)
        elif author_ids:
            ranked.sort(key=lambda x: x[0]["work_id"] in author_ids, reverse=True)

        # ====================================================
        # IMPORTANT:
        # For physical-library filtering, DON'T cut to the
        # first 10 before checking inventory.
        #
        # We inspect all 50 reranked candidates first.
        # ====================================================

        ranked_for_metadata = ranked

        # ====================================================
        # 7. FINAL METADATA
        # ====================================================

        final_ids = [
            item[0]["work_id"]
            for item in ranked_for_metadata
        ]

        start = time.perf_counter()

        final_metadata = current_books(self.books_collection, final_ids)
        final_metadata_ms = (time.perf_counter() - start) * 1000

        # ====================================================
        # 8. PHYSICAL LIBRARY INVENTORY
        # ====================================================

        start = time.perf_counter()

        inventory_by_work_id = (
            self._get_library_inventory(
                final_ids,
                library_id
            )
        )

        inventory_ms = (
            time.perf_counter()
            - start
        ) * 1000

        # ====================================================
        # 9. BUILD RESULTS
        # ====================================================

        results = []

        for candidate, score in (
            ranked_for_metadata
        ):

            work_id = candidate[
                "work_id"
            ]

            metadata = (
                final_metadata.get(
                    work_id,
                    {}
                )
            )

            if work_id not in final_metadata:
                continue

            inventory = (
                inventory_by_work_id.get(
                    work_id
                )
            )

            library_available = (
                inventory is not None
            )

            physical_copies = (
                inventory.get(
                    "total_copies",
                    0
                )
                if inventory
                else 0
            )

            available_physical_copies = (
                inventory.get(
                    "available_copies",
                    0
                )
                if inventory
                else 0
            )

            results.append(
                {
                    "work_id": work_id,

                    "rerank_score": float(
                        score
                    ),

                    "hnsw_score": (
                        candidate[
                            "hnsw_score"
                        ]
                    ),

                    "title": (
                        metadata.get(
                            "title"
                        )
                    ),

                    "authors": (
                        metadata.get(
                            "authors"
                        )
                    ),

                    "subjects": (
                        metadata.get(
                            "subjects"
                        )
                    ),

                    "rating": (
                        metadata.get(
                            "average_rating"
                        )
                    ),

                    "rating_count": (
                        metadata.get(
                            "rating_count"
                        )
                    ),

                    "read_logs": (
                        metadata.get(
                            "reading_log_count"
                        )
                    ),

                    "description": metadata.get("description"),

                    # ========================================
                    # PHYSICAL LIBRARY
                    # ========================================

                    "library_id": (
                        library_id
                    ),

                    "library_available": (
                        library_available
                    ),

                    "physical_copies": (
                        physical_copies
                    ),

                    "available_physical_copies": (
                        available_physical_copies
                    ),

                    "shelf_location": (
                        inventory.get(
                            "shelf_location"
                        )
                        if inventory
                        else None
                    ),

                    "isbn": (
                        inventory.get(
                            "isbn"
                        )
                        if inventory
                        else None
                    )
                }
            )

        # Revalidate after reranking/inventory I/O and before cutting to top-k.
        latest = current_books(self.books_collection, [r["work_id"] for r in results])
        results = [r for r in results if r["work_id"] in latest]
        for result in results:
            book = latest[result["work_id"]]
            for field in ("title", "authors", "subjects", "description", "shelf_location"):
                result[field] = book.get(field)
            result["rating"] = book.get("average_rating")
            result["rating_count"] = book.get("rating_count")
            result["read_logs"] = book.get("reading_log_count")
            result["physical_copies"] = book.get("total_copies", 0)
            result["available_physical_copies"] = book.get("available_copies", 0)
        if library_id and available_at_library:
            results = [r for r in results if r["library_available"] and r["available_physical_copies"] > 0]
        results = results[:final_k]

        # ====================================================
        # 11. FINAL RANKING
        # ====================================================

        for rank, result in enumerate(
            results,
            start=1
        ):

            result["rank"] = rank

        # ====================================================
        # TOTAL
        # ====================================================

        total_ms = (
            time.perf_counter()
            - total_start
        ) * 1000

        # ====================================================
        # RETURN
        # ====================================================

        response = {

            "system": "LuminaR",

            "query": query,

            "library_id": library_id,

            "available_at_library": (
                available_at_library
            ),

            "timing_ms": {

                "embedding": round(
                    embedding_ms,
                    2
                ),

                "hnsw": round(
                    hnsw_ms,
                    2
                ),

                "candidate_metadata": round(
                    candidate_metadata_ms,
                    2
                ),

                "pair_construction": round(
                    pair_ms,
                    2
                ),

                "reranking": round(
                    reranking_ms,
                    2
                ),

                "final_metadata": round(
                    final_metadata_ms,
                    2
                ),

                "inventory": round(
                    inventory_ms,
                    2
                ),

                "total": round(
                    total_ms,
                    2
                )
            },

            "results": results
        }
        if diagnostics:
            response["diagnostics"] = {
                "raw_hnsw": raw_candidates,
                "mongo_validated": candidates,
                "reranked": [
                    {"work_id": item[0]["work_id"], "score": float(item[1])}
                    for item in ranked
                ],
                "author_match_ids": sorted(author_ids),
            }
        return response

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        if getattr(self,"lexical_writer",None) is not None:
            self.lexical_writer.close()
        if getattr(self,"lexical_store",None) is not None:
            self.lexical_store.close()

        self.index_manager.close()

        if hasattr(
            self,
            "metadata_store"
        ):

            self.metadata_store.close()

        if hasattr(
            self,
            "mongo_client"
        ):

            self.mongo_client.close()


# ============================================================
# COMMAND LINE SEARCH
# ============================================================

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(
        description="LuminaR semantic search"
    )

    parser.add_argument(
        "--query",
        required=True,
        help="Search query"
    )

    parser.add_argument(
        "--top_k",
        type=int,
        default=10,
        help="Number of results"
    )

    parser.add_argument(
        "--library-id",
        type=str,
        default=None,
        help="Library ID for physical inventory"
    )

    parser.add_argument(
        "--available-at-library",
        action="store_true",
        help=(
            "Only return books that are "
            "physically available at the library"
        )
    )

    args = parser.parse_args()

    engine = LuminaRSearchEngine()

    try:

        result = engine.search(
            query=args.query,
            top_k=args.top_k,
            library_id=args.library_id,
            available_at_library=(
                args.available_at_library
            )
        )

        print()
        print("=" * 70)
        print(
            "LUMINAR — SEMANTIC SEARCH RESULTS"
        )
        print("=" * 70)

        print()

        print(
            "Query :",
            result["query"]
        )

        print(
            "Library :",
            result["library_id"]
        )

        print(
            "Available at library :",
            result[
                "available_at_library"
            ]
        )

        print()

        timing = result[
            "timing_ms"
        ]

        print("-" * 70)

        print(
            f"Embedding          : "
            f"{timing['embedding']:.2f} ms"
        )

        print(
            f"HNSW               : "
            f"{timing['hnsw']:.2f} ms"
        )

        print(
            f"Candidate metadata : "
            f"{timing['candidate_metadata']:.2f} ms"
        )

        print(
            f"Pair construction  : "
            f"{timing['pair_construction']:.2f} ms"
        )

        print(
            f"Reranking          : "
            f"{timing['reranking']:.2f} ms"
        )

        print(
            f"Final metadata     : "
            f"{timing['final_metadata']:.2f} ms"
        )

        print(
            f"Inventory          : "
            f"{timing['inventory']:.2f} ms"
        )

        print(
            f"Total              : "
            f"{timing['total']:.2f} ms"
        )

        print()

        for book in result[
            "results"
        ]:

            print("-" * 70)

            print(
                f"Rank       : "
                f"{book['rank']}"
            )

            print(
                f"Work ID    : "
                f"{book['work_id']}"
            )

            print(
                f"Rerank     : "
                f"{book['rerank_score']:.4f}"
            )

            print(
                f"HNSW       : "
                f"{book['hnsw_score']:.4f}"
            )

            print(
                f"Title      : "
                f"{book['title']}"
            )

            print(
                f"Authors    : "
                f"{book['authors']}"
            )

            print(
                f"Subjects   : "
                f"{book['subjects']}"
            )

            print(
                f"Rating     : "
                f"{book['rating']}"
            )

            print(
                f"Rating cnt : "
                f"{book['rating_count']}"
            )

            print(
                f"Read logs  : "
                f"{book['read_logs']}"
            )

            print()

            print(
                f"Library ID : "
                f"{book['library_id']}"
            )

            print(
                f"Library available : "
                f"{book['library_available']}"
            )

            print(
                f"Physical copies : "
                f"{book['physical_copies']}"
            )

            print(
                f"Available physical copies : "
                f"{book['available_physical_copies']}"
            )

            print(
                f"Shelf location : "
                f"{book['shelf_location']}"
            )

            print(
                f"ISBN : "
                f"{book['isbn']}"
            )

        print("-" * 70)

    finally:

        engine.close()

        print()
        print(
            "LuminaR search engine closed."
        )
