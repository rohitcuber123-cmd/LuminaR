import os
import sys
import time

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

BASE_DIR = r"D:\SDC\LibraryLLM"

HNSW_DIR = os.path.join(
    BASE_DIR,
    "datasets",
    "ai",
    "faiss",
    "hnsw"
)

METADATA_DB = os.path.join(
    BASE_DIR,
    "datasets",
    "ai",
    "metadata",
    "book_metadata.duckdb"
)

METADATA_DIR = os.path.join(
    BASE_DIR,
    "data_pipeline",
    "ai",
    "metadata"
)

if METADATA_DIR not in sys.path:
    sys.path.insert(0, METADATA_DIR)

from metadata_store import MetadataStore


# ============================================================
# MONGODB
# ============================================================

MONGO_URI = "mongodb://localhost:27017"
MONGO_DATABASE = "luminar_library"


# ============================================================
# CONFIGURATION
# ============================================================

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

RERANKER_MODEL = (
    "cross-encoder/ms-marco-MiniLM-L-6-v2"
)

HNSW_TOP_K = 50

FINAL_TOP_K = 10

EF_SEARCH = 128

RERANK_BATCH_SIZE = 16

WARMUP_ITERATIONS = 5


# ============================================================
# SEARCH ENGINE
# ============================================================

class LuminaRSearchEngine:

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
        # HNSW
        # ====================================================

        print()
        print("Loading HNSW index...")

        start = time.perf_counter()

        index_path = os.path.join(
            HNSW_DIR,
            "hnsw.index"
        )

        work_ids_path = os.path.join(
            HNSW_DIR,
            "index_work_ids.npy"
        )

        self.index = faiss.read_index(
            index_path
        )

        self.work_ids = np.load(
            work_ids_path,
            allow_pickle=True
        )

        self.index.hnsw.efSearch = EF_SEARCH

        self.index_load_ms = (
            time.perf_counter() - start
        ) * 1000

        print(
            f"Vectors    : "
            f"{self.index.ntotal:,}"
        )

        print(
            f"Dimension  : "
            f"{self.index.d}"
        )

        print(
            f"efSearch   : "
            f"{self.index.hnsw.efSearch}"
        )

        print(
            f"Index load : "
            f"{self.index_load_ms:.2f} ms"
        )

        # ====================================================
        # MINILM
        # ====================================================

        print()
        print("Loading MiniLM...")

        start = time.perf_counter()

        self.embedding_model = SentenceTransformer(
            EMBEDDING_MODEL,
            device=self.device
        )

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
            device=self.device
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
        # METADATA
        # ====================================================

        print()
        print("Opening MetadataStore...")

        start = time.perf_counter()

        self.metadata_store = MetadataStore(
            METADATA_DB
        )

        self.metadata_load_ms = (
            time.perf_counter() - start
        ) * 1000

        print(
            "MetadataStore ready."
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

        # ====================================================
        # FULL PIPELINE WARMUP
        # ====================================================

        print()
        print("=" * 60)
        print(
            "Warming complete "
            "LuminaR pipeline..."
        )
        print("=" * 60)

        warmup_query = (
            "books for learning "
            "deep learning and "
            "neural networks"
        )

        for i in range(
            WARMUP_ITERATIONS
        ):

            # ------------------------------------------------
            # 1. EMBEDDING
            # ------------------------------------------------

            query_vector = (
                self.embedding_model.encode(
                    [warmup_query],
                    convert_to_numpy=True
                )
            )

            self._sync_cuda()

            query_vector = np.asarray(
                query_vector,
                dtype=np.float32
            )

            faiss.normalize_L2(
                query_vector
            )

            # ------------------------------------------------
            # 2. HNSW
            # ------------------------------------------------

            distances, indices = (
                self.index.search(
                    query_vector,
                    HNSW_TOP_K
                )
            )

            # ------------------------------------------------
            # 3. CANDIDATES
            # ------------------------------------------------

            candidates = []

            for score, idx in zip(
                distances[0],
                indices[0]
            ):

                if idx < 0:
                    continue

                candidates.append(
                    {
                        "work_id": str(
                            self.work_ids[idx]
                        ),

                        "hnsw_score": float(
                            score
                        )
                    }
                )

            candidate_ids = [
                candidate["work_id"]
                for candidate in candidates
            ]

            # ------------------------------------------------
            # 4. CANDIDATE METADATA
            # ------------------------------------------------

            text_metadata = (
                self.metadata_store
                .get_rerank_text_by_work_ids(
                    candidate_ids
                )
            )

            # ------------------------------------------------
            # 5. PAIR CONSTRUCTION
            # ------------------------------------------------

            pairs = []

            for candidate in candidates:

                metadata = (
                    text_metadata.get(
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
                        warmup_query,
                        book_text
                    ]
                )

            # ------------------------------------------------
            # 6. RERANK
            # ------------------------------------------------

            rerank_scores = (
                self.reranker.predict(
                    pairs,
                    batch_size=RERANK_BATCH_SIZE,
                    show_progress_bar=False
                )
            )

            self._sync_cuda()

            # ------------------------------------------------
            # 7. SORT
            # ------------------------------------------------

            ranked = list(
                zip(
                    candidates,
                    rerank_scores
                )
            )

            ranked.sort(
                key=lambda x: float(x[1]),
                reverse=True
            )

            # ------------------------------------------------
            # 8. FINAL METADATA
            # ------------------------------------------------

            final_ids = [
                item[0]["work_id"]
                for item in ranked[:FINAL_TOP_K]
            ]

            self.metadata_store.get_by_work_ids(
                final_ids
            )

            print(
                f"Warm-up "
                f"{i + 1}/"
                f"{WARMUP_ITERATIONS} "
                f"complete"
            )

        self._sync_cuda()

        print(
            "Full pipeline "
            "warm-up complete."
        )

        # ====================================================
        # READY
        # ====================================================

        print()
        print(
            "LuminaR search engine ready."
        )

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
        available_at_library=False
    ):

        query = query.strip()

        if not query:

            raise ValueError(
                "Query cannot be empty."
            )

        final_k = min(
            int(top_k),
            FINAL_TOP_K
        )

        total_start = (
            time.perf_counter()
        )

        # ====================================================
        # 1. QUERY EMBEDDING
        # ====================================================

        start = time.perf_counter()

        query_vector = (
            self.embedding_model.encode(
                [query],
                convert_to_numpy=True
            )
        )

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

        distances, indices = (
            self.index.search(
                query_vector,
                HNSW_TOP_K
            )
        )

        hnsw_ms = (
            time.perf_counter()
            - start
        ) * 1000

        candidates = []

        for score, idx in zip(
            distances[0],
            indices[0]
        ):

            if idx < 0:
                continue

            candidates.append(
                {
                    "work_id": str(
                        self.work_ids[idx]
                    ),

                    "hnsw_score": float(
                        score
                    )
                }
            )

        candidate_ids = [
            item["work_id"]
            for item in candidates
        ]

        # ====================================================
        # 3. CANDIDATE METADATA
        # ====================================================

        start = time.perf_counter()

        candidate_metadata = (
            self.metadata_store
            .get_rerank_text_by_work_ids(
                candidate_ids
            )
        )

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
            )
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
            key=lambda x: float(x[1]),
            reverse=True
        )

        # ====================================================
        # IMPORTANT:
        # For physical-library filtering, DON'T cut to the
        # first 10 before checking inventory.
        #
        # We inspect all 50 reranked candidates first.
        # ====================================================

        if (
            library_id
            and available_at_library
        ):

            ranked_for_metadata = ranked

        else:

            ranked_for_metadata = (
                ranked[:final_k]
            )

        # ====================================================
        # 7. FINAL METADATA
        # ====================================================

        final_ids = [
            item[0]["work_id"]
            for item in ranked_for_metadata
        ]

        start = time.perf_counter()

        final_metadata = (
            self.metadata_store
            .get_by_work_ids(
                final_ids
            )
        )

        final_metadata_ms = (
            time.perf_counter()
            - start
        ) * 1000

        # ====================================================
        # 7.5. MONGODB FALLBACK FOR MISSING METADATA
        # ====================================================
        
        # Find work_ids with missing title or authors from DuckDB
        missing_metadata_ids = [
            wid for wid in final_ids
            if not final_metadata.get(wid, {}).get("title")
            or not final_metadata.get(wid, {}).get("authors")
        ]
        
        if missing_metadata_ids:
            print(f"[Search] Enriching {len(missing_metadata_ids)} results with MongoDB fallback")
            
            # Batch fetch from MongoDB books collection
            mongo_books = self.books_collection.find(
                {"work_id": {"$in": missing_metadata_ids}},
                {
                    "_id": 0,
                    "work_id": 1,
                    "title": 1,
                    "authors": 1,
                    "subjects": 1,
                    "average_rating": 1,
                    "rating_count": 1,
                    "reading_log_count": 1
                }
            )
            
            # Merge MongoDB data into final_metadata
            for book in mongo_books:
                work_id = book["work_id"]
                existing = final_metadata.get(work_id, {})
                
                # Only fill in missing fields, preserve DuckDB data if exists
                final_metadata[work_id] = {
                    "title": existing.get("title") or book.get("title"),
                    "authors": existing.get("authors") or book.get("authors"),
                    "subjects": existing.get("subjects") or book.get("subjects"),
                    "rating": existing.get("rating") or book.get("average_rating"),
                    "rating_count": existing.get("rating_count") or book.get("rating_count"),
                    "read_logs": existing.get("read_logs") or book.get("reading_log_count", 0)
                }

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
                            "rating"
                        )
                    ),

                    "rating_count": (
                        metadata.get(
                            "rating_count"
                        )
                    ),

                    "read_logs": (
                        metadata.get(
                            "read_logs"
                        )
                    ),

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

        # ====================================================
        # 10. OPTIONAL LIBRARY FILTER
        # ====================================================

        if (
            library_id
            and available_at_library
        ):

            results = [
                result
                for result in results

                if (
                    result[
                        "library_available"
                    ]
                    and
                    result[
                        "available_physical_copies"
                    ] > 0
                )
            ]

            # Keep only the requested number of results
            # AFTER the physical-library filter.

            results = results[
                :final_k
            ]

        else:

            results = results[
                :final_k
            ]

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

        return {

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

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

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