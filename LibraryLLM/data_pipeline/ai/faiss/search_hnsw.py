"""
AstraLib -- HNSW Semantic Search

Natural-language search against the HNSW index with DuckDB metadata
enrichment via a persistent MetadataStore connection.

Default HNSW configuration:
    efSearch = 128

The efSearch value can be overridden from the command line without
rebuilding the HNSW index.

Metadata backend:
    Uses datasets/ai/metadata/book_metadata.duckdb exclusively.
    The DuckDB connection is opened ONCE at startup and reused for
    every query -- connection creation overhead (~400 ms) is paid
    only once, not per request.

Benchmark mode (--benchmark):
    Runs the full query pipeline 20 times and reports timing statistics
    without printing the full book result list on every iteration.
"""

import argparse
import faiss
import numpy as np
import os
import statistics
import sys
import time
import warnings
import torch

warnings.filterwarnings("ignore", category=FutureWarning)

from sentence_transformers import SentenceTransformer

# MetadataStore lives in data_pipeline/ai/metadata/
_THIS_DIR    = os.path.dirname(os.path.abspath(__file__))
_META_DIR    = os.path.normpath(os.path.join(_THIS_DIR, "..", "metadata"))
if _META_DIR not in sys.path:
    sys.path.insert(0, _META_DIR)

from metadata_store import MetadataStore


# ======================================================================
# CONFIGURATION
# ======================================================================

PARQUET_PATH = (
    "D:/SDC/LibraryLLM/datasets/ai/search/search_corpus.parquet"
)

MODEL_NAME = "all-MiniLM-L6-v2"

DEFAULT_EF_SEARCH = 128


# ======================================================================
# HNSW SEARCHER
# ======================================================================

class HNSWSearcher:
    """Importable searcher for the AstraLib HNSW index."""

    def __init__(self, index_dir: str, ef_search: int | None = None):

        self.index_path = os.path.join(
            index_dir,
            "hnsw.index"
        )

        self.ids_path = os.path.join(
            index_dir,
            "index_work_ids.npy"
        )

        # --------------------------------------------------------------
        # Validate files
        # --------------------------------------------------------------

        if not os.path.exists(self.index_path):
            raise FileNotFoundError(
                f"HNSW index not found: {self.index_path}"
            )

        if not os.path.exists(self.ids_path):
            raise FileNotFoundError(
                f"Work-IDs mapping not found: {self.ids_path}"
            )

        # --------------------------------------------------------------
        # Load FAISS index
        # --------------------------------------------------------------

        self.index = faiss.read_index(
            self.index_path
        )

        # --------------------------------------------------------------
        # Load work ID mapping
        # --------------------------------------------------------------

        self.work_ids = np.load(
            self.ids_path,
            allow_pickle=True
        )

        # --------------------------------------------------------------
        # Validate mapping
        # --------------------------------------------------------------

        if self.index.ntotal != len(self.work_ids):
            raise ValueError(
                f"Index/work-ID mismatch: "
                f"index has {self.index.ntotal} vectors but "
                f"{len(self.work_ids)} work IDs were found."
            )

        # --------------------------------------------------------------
        # Set HNSW search parameter
        #
        # efSearch is a SEARCH-TIME parameter.
        # Changing this does NOT require rebuilding the index.
        # --------------------------------------------------------------

        if ef_search is None:
            ef_search = DEFAULT_EF_SEARCH

        if ef_search <= 0:
            raise ValueError(
                "efSearch must be greater than 0."
            )

        self.index.hnsw.efSearch = ef_search

    # ------------------------------------------------------------------
    # Current efSearch value
    # ------------------------------------------------------------------

    @property
    def ef_search(self):
        return self.index.hnsw.efSearch

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query_vector,
        top_k: int = 10
    ):

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than 0."
            )

        # --------------------------------------------------------------
        # Convert query to NumPy float32
        # --------------------------------------------------------------

        query_vector = np.array(
            query_vector,
            dtype=np.float32
        )

        # --------------------------------------------------------------
        # Ensure 2D shape
        # --------------------------------------------------------------

        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(
                1,
                -1
            )

        if query_vector.ndim != 2:
            raise ValueError(
                f"Query vector must be 1D or 2D. "
                f"Received shape: {query_vector.shape}"
            )

        # --------------------------------------------------------------
        # Dimension check
        # --------------------------------------------------------------

        if query_vector.shape[1] != self.index.d:
            raise ValueError(
                f"Query dimension ({query_vector.shape[1]}) "
                f"!= index dimension ({self.index.d})"
            )

        # --------------------------------------------------------------
        # Normalize query
        #
        # Our book embeddings are normalized, and the index uses
        # Inner Product, which therefore corresponds to cosine
        # similarity.
        # --------------------------------------------------------------

        faiss.normalize_L2(
            query_vector
        )

        # --------------------------------------------------------------
        # FAISS search
        # --------------------------------------------------------------

        distances, indices = self.index.search(
            query_vector,
            top_k
        )

        # --------------------------------------------------------------
        # Convert FAISS results to application results
        # --------------------------------------------------------------

        results = []

        for rank, (dist, idx) in enumerate(
            zip(
                distances[0],
                indices[0]
            ),
            start=1
        ):

            if idx == -1:
                continue

            results.append(
                {
                    "rank": rank,
                    "work_id": str(
                        self.work_ids[idx]
                    ),
                    "score": float(dist),
                    "faiss_index": int(idx),
                }
            )

        return results


# (Metadata lookup is now handled by MetadataStore in
#  data_pipeline/ai/metadata/metadata_store.py)


# ======================================================================
# MAIN
# ======================================================================

def main():

    parser = argparse.ArgumentParser(
        description="AstraLib HNSW Semantic Search"
    )

    # --------------------------------------------------------------
    # CLI arguments
    # --------------------------------------------------------------

    parser.add_argument(
        "--index-dir",
        required=True,
        type=str,
        help="Directory containing hnsw.index"
    )

    parser.add_argument(
        "--query",
        required=True,
        type=str,
        help="Natural language search query"
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of results to return (default: 10)"
    )

    parser.add_argument(
        "--k",
        type=int,
        dest="top_k",
        help="Alias for --top-k"
    )

    parser.add_argument(
        "--ef-search",
        type=int,
        default=DEFAULT_EF_SEARCH,
        help=(
            "HNSW search effort "
            "(default: 128)"
        )
    )

    parser.add_argument(
        "--with-metadata",
        action="store_true",
        help="Fetch book metadata from book_metadata.duckdb"
    )

    parser.add_argument(
        "--metadata-db",
        type=str,
        default="D:/SDC/LibraryLLM/datasets/ai/metadata/book_metadata.duckdb",
        help="Path to book_metadata.duckdb"
    )

    parser.add_argument(
        "--benchmark",
        action="store_true",
        help=(
            "Run the query 20 times and report avg/median/P95/min/max "
            "for each pipeline stage. Does not print the full result list "
            "on every iteration."
        )
    )

    args = parser.parse_args()

    # --------------------------------------------------------------
    # Validate arguments
    # --------------------------------------------------------------

    if args.top_k <= 0:

        print(
            "Error: --top-k must be greater than 0.",
            file=sys.stderr
        )

        sys.exit(1)

    if args.ef_search <= 0:

        print(
            "Error: --ef-search must be greater than 0.",
            file=sys.stderr
        )

        sys.exit(1)

    # ==============================================================
    # LOAD HNSW INDEX
    # ==============================================================

    try:

        searcher = HNSWSearcher(
            args.index_dir,
            ef_search=args.ef_search
        )

    except (FileNotFoundError, ValueError) as e:

        print(
            f"Error: {e}",
            file=sys.stderr
        )

        sys.exit(1)

    # ==============================================================
    # LOAD SENTENCE TRANSFORMER
    # ==============================================================

    device = (
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print("=" * 60)
    print("ASTRA LIB - HNSW SEMANTIC SEARCH")
    print("=" * 60)
    print()

    print(
        f"Query      : {args.query}"
    )

    print(
        f"Model      : {MODEL_NAME}"
    )

    print(
        f"Device     : {device}"
    )

    print(
        f"Index      : IndexHNSWFlat"
    )

    print(
        f"efSearch   : {searcher.ef_search}"
    )

    print(
        f"Top-K      : {args.top_k}"
    )

    print()

    # --------------------------------------------------------------
    # Load model
    # --------------------------------------------------------------

    model_load_start = time.perf_counter()

    model = SentenceTransformer(
        MODEL_NAME,
        device=device
    )

    model_load_time = (
        time.perf_counter()
        - model_load_start
    ) * 1000.0

    print("Warming up MiniLM...")

    warmup_queries = [
        "warmup query",
        "book on artificial intelligence",
        "a book about good habits",
    ]

    for text in warmup_queries:
        model.encode(
            [text],
            batch_size=1,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    if device == "cuda":
        torch.cuda.synchronize()

    print("MiniLM warm-up complete.")

    # --------------------------------------------------------------
    # Open MetadataStore (persistent read-only DuckDB connection)
    # Opened ONCE -- reused for every query.
    # --------------------------------------------------------------

    metadata_store = None

    if args.with_metadata or args.benchmark:

        if not os.path.exists(args.metadata_db):
            print(
                f"Error: Production metadata database not found: "
                f"{args.metadata_db}",
                file=sys.stderr
            )
            sys.exit(1)

        metadata_store = MetadataStore(args.metadata_db)
        print(f"Metadata store opened: {args.metadata_db}")

    print()

    # ==============================================================
    # ENCODE QUERY
    # ==============================================================

    t0 = time.perf_counter()

    query_vector = model.encode(
        args.query,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    t_encode = (
        time.perf_counter()
        - t0
    ) * 1000.0

    # ==============================================================
    # HNSW SEARCH
    # ==============================================================

    t0 = time.perf_counter()

    try:

        results = searcher.search(
            query_vector,
            top_k=args.top_k
        )

    except ValueError as e:

        print(
            f"Error: {e}",
            file=sys.stderr
        )

        sys.exit(1)

    t_search = (
        time.perf_counter()
        - t0
    ) * 1000.0

    # ==============================================================
    # METADATA LOOKUP  (persistent MetadataStore connection)
    # ==============================================================

    t_meta = 0.0
    metadata_by_id = {}

    if args.with_metadata and metadata_store is not None:

        work_ids = [
            result["work_id"]
            for result in results
        ]

        # Timer covers ONLY SQL execution + fetch + dict conversion.
        # Connection creation is NOT included -- it was paid at startup.
        t0 = time.perf_counter()
        metadata_by_id = metadata_store.get_by_work_ids(work_ids)
        t_meta = (time.perf_counter() - t0) * 1000.0

    # Attach metadata to results
    for result in results:
        result["metadata"] = metadata_by_id.get(result["work_id"], {})

    # ==============================================================
    # BENCHMARK MODE
    # ==============================================================

    if args.benchmark:

        BENCH_ITERS = 20

        print("=" * 60)
        print("BENCHMARK MODE")
        print("=" * 60)
        print(f"Query      : {args.query}")
        print(f"Top-K      : {args.top_k}")
        print(f"Iterations : {BENCH_ITERS}")
        print()

        enc_times   = []
        srch_times  = []
        meta_times  = []
        total_times = []

        for i in range(BENCH_ITERS):

            # -- Encode --
            if device == "cuda":
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            qv = model.encode(
                args.query,
                batch_size=1,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            if device == "cuda":
                torch.cuda.synchronize()
            enc_t = (time.perf_counter() - t0) * 1000.0

            # -- HNSW search --
            t0 = time.perf_counter()
            res = searcher.search(qv, top_k=args.top_k)
            srch_t = (time.perf_counter() - t0) * 1000.0

            # -- Metadata --
            meta_t = 0.0
            if metadata_store is not None:
                wids = [r["work_id"] for r in res]
                t0 = time.perf_counter()
                metadata_store.get_by_work_ids(wids)
                meta_t = (time.perf_counter() - t0) * 1000.0

            enc_times.append(enc_t)
            srch_times.append(srch_t)
            meta_times.append(meta_t)
            total_times.append(enc_t + srch_t + meta_t)

        def _bstats(vals):
            s = sorted(vals)
            n = len(s)
            return {
                "avg": statistics.mean(s),
                "med": statistics.median(s),
                "p95": s[max(0, int(n * 0.95) - 1)],
                "min": s[0],
                "max": s[-1],
            }

        def _print_bstats(label, s):
            print(f"  {label}")
            print(f"    Average : {s['avg']:8.2f} ms")
            print(f"    Median  : {s['med']:8.2f} ms")
            print(f"    P95     : {s['p95']:8.2f} ms")
            print(f"    Minimum : {s['min']:8.2f} ms")
            print(f"    Maximum : {s['max']:8.2f} ms")
            print()

        _print_bstats("Query embedding:", _bstats(enc_times))
        _print_bstats("HNSW search:",    _bstats(srch_times))
        if metadata_store is not None:
            _print_bstats("Metadata lookup:", _bstats(meta_times))
        _print_bstats("Warm query total:", _bstats(total_times))

        # Comparison vs old implementation
        print("=" * 60)
        print("METADATA PERFORMANCE")
        print("=" * 60)
        new_avg = statistics.mean(meta_times) if metadata_store else 0.0
        old_ms  = 462.0
        speedup = old_ms / new_avg if new_avg > 0 else float("inf")
        print(f"  Old search_hnsw.py : ~{old_ms:.0f} ms")
        print(f"  New MetadataStore  : ~{new_avg:.2f} ms")
        print(f"  Speedup            : {speedup:.1f}x")
        print()

        print("=" * 60)
        print("FULL WARM QUERY")
        print("=" * 60)
        ts = _bstats(total_times)
        print(f"  MiniLM   : {statistics.mean(enc_times):.1f} ms")
        print(f"  HNSW     : {statistics.mean(srch_times):.1f} ms")
        if metadata_store is not None:
            print(f"  Metadata : {statistics.mean(meta_times):.1f} ms")
        print(f"  Total    : {ts['avg']:.1f} ms  (avg)")
        print(f"  Total    : {ts['med']:.1f} ms  (median)")
        print()

        if metadata_store is not None:
            metadata_store.close()

        return

    # ==============================================================
    # TIMING OUTPUT  (single-query mode)
    # ==============================================================

    t_total = t_encode + t_search + t_meta

    print(
        f"Model load       : {model_load_time:.1f} ms"
    )
    print(
        f"Query embedding  : {t_encode:.1f} ms"
    )
    print(
        f"HNSW search      : {t_search:.1f} ms"
    )

    if args.with_metadata:
        print(
            f"Metadata lookup  : {t_meta:.1f} ms"
        )

    print("-" * 30)
    print(
        f"Warm query total : {t_total:.1f} ms"
    )
    print()

    # ==============================================================
    # RESULTS
    # ==============================================================

    for result in results:

        print("-" * 60)
        print(f"Rank {result['rank']}")
        print(f"Work ID    : {result['work_id']}")
        print(f"Similarity : {result['score']:.4f}")

        if args.with_metadata:

            metadata = result.get("metadata", {})

            print(f"Title      : {metadata.get('title', 'N/A')}")
            print(f"Authors    : {metadata.get('authors', 'N/A')}")
            print(f"Subjects   : {metadata.get('subjects', 'N/A')}")
            print(f"Rating     : {metadata.get('average_rating', 'N/A')}")
            print(f"Rating cnt : {metadata.get('rating_count', 'N/A')}")
            print(f"Read logs  : {metadata.get('reading_log_count', 'N/A')}")

    print("-" * 60)

    if metadata_store is not None:
        metadata_store.close()


# ======================================================================
# ENTRY POINT
# ======================================================================

if __name__ == "__main__":
    main()