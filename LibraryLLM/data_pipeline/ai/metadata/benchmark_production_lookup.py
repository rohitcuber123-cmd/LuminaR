"""
AstraLib -- Production Metadata Benchmark

Measures the true metadata lookup latency using the same code path
(MetadataStore) that search_hnsw.py now uses.

Uses real work IDs drawn from the production HNSW index mapping so the
benchmark reflects actual query patterns rather than fabricated IDs.

Benchmarks
----------
A. Database connection open time    (one-time cost at startup)
B. SQL execution + fetch time       (per-query cost, persistent conn)
C. Python dict conversion           (included in B -- reported together)

Tests
-----
10 / 50 / 100 work IDs x 20 iterations (after 5 warm-up iterations).

Usage
-----
    python data_pipeline/ai/metadata/benchmark_production_lookup.py
"""

import io
import os
import statistics
import sys
import time

import numpy as np

# Force UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf_8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

# ======================================================================
# PATHS
# ======================================================================

BASE_DIR   = "D:/SDC/LibraryLLM"
DB_PATH    = f"{BASE_DIR}/datasets/ai/metadata/book_metadata.duckdb"
IDS_NPY    = f"{BASE_DIR}/datasets/ai/faiss/hnsw/index_work_ids.npy"

# ======================================================================
# HELPERS
# ======================================================================

def _divider(char="=", width=70):
    print(char * width)

def _section(title: str):
    _divider()
    print(title)
    _divider()
    print()

def _stats(times_ms: list) -> dict:
    arr = sorted(times_ms)
    n   = len(arr)
    return {
        "avg": statistics.mean(arr),
        "med": statistics.median(arr),
        "p95": arr[max(0, int(n * 0.95) - 1)],
        "min": arr[0],
        "max": arr[-1],
    }

def _print_stats(label: str, s: dict):
    print(f"  {label}")
    print(f"    Average : {s['avg']:8.2f} ms")
    print(f"    Median  : {s['med']:8.2f} ms")
    print(f"    P95     : {s['p95']:8.2f} ms")
    print(f"    Minimum : {s['min']:8.2f} ms")
    print(f"    Maximum : {s['max']:8.2f} ms")
    print()

# ======================================================================
# BENCHMARK FUNCTIONS
# ======================================================================

WARMUP_ITERS = 5
BENCH_ITERS  = 20


def benchmark_connection_open(db_path: str, iters: int) -> dict:
    """
    Measure how long it takes to open the DuckDB connection.
    This is a one-time startup cost in production.
    """
    import duckdb
    times = []
    for _ in range(iters):
        t0 = time.perf_counter()
        conn = duckdb.connect(database=db_path, read_only=True)
        t1 = time.perf_counter()
        conn.close()
        times.append((t1 - t0) * 1000.0)
    return _stats(times)


def benchmark_lookup(store, work_ids: list, warmup: int, iters: int) -> dict:
    """
    Measure SQL execution + fetch + dict conversion with a persistent
    connection (same code path as MetadataStore.get_by_work_ids).
    """
    # Warm-up -- results discarded
    for _ in range(warmup):
        store.get_by_work_ids(work_ids)

    times = []
    for _ in range(iters):
        t0 = time.perf_counter()
        result = store.get_by_work_ids(work_ids)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000.0)

    return _stats(times), result


# ======================================================================
# MAIN
# ======================================================================

def main():

    # ------------------------------------------------------------------
    # Pre-flight checks
    # ------------------------------------------------------------------

    if not os.path.exists(DB_PATH):
        print(f"ERROR: Metadata database not found: {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(IDS_NPY):
        print(f"ERROR: Work-ID mapping not found: {IDS_NPY}", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Load real work IDs from the production HNSW index mapping
    # ------------------------------------------------------------------

    all_ids = np.load(IDS_NPY, allow_pickle=True)
    all_ids = [str(x) for x in all_ids]

    # Sample IDs from spread positions across the index so they are
    # representative of real search results rather than all from the start.
    total = len(all_ids)

    def sample_ids(n: int) -> list:
        step = max(1, total // n)
        return [all_ids[i * step] for i in range(n)]

    ids_10  = sample_ids(10)
    ids_50  = sample_ids(50)
    ids_100 = sample_ids(100)

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    _section("ASTRALIB -- PRODUCTION METADATA BENCHMARK")

    print(f"  Database   : {DB_PATH}")
    print(f"  IDs source : {IDS_NPY}")
    print(f"  Total IDs  : {total:,}")
    print(f"  Warm-up    : {WARMUP_ITERS} iterations (excluded from stats)")
    print(f"  Bench      : {BENCH_ITERS} iterations per test")
    print()

    # ------------------------------------------------------------------
    # A. Connection open time
    # ------------------------------------------------------------------

    _section("A. DATABASE CONNECTION OPEN TIME  (one-time startup cost)")

    print(f"  Measuring how long duckdb.connect(read_only=True) takes...")
    print(f"  Iterations : {BENCH_ITERS}")
    print()

    conn_stats = benchmark_connection_open(DB_PATH, BENCH_ITERS)
    _print_stats("Connection open time:", conn_stats)

    print("  NOTE: In production this cost is paid ONCE at startup,")
    print("  not per query. MetadataStore keeps the connection alive.")
    print()

    # ------------------------------------------------------------------
    # Import MetadataStore after confirming DB exists
    # ------------------------------------------------------------------

    # Allow running from any working directory
    sys.path.insert(0, os.path.dirname(__file__))
    from metadata_store import MetadataStore

    # ------------------------------------------------------------------
    # B/C/D. SQL + fetch + conversion with persistent connection
    # ------------------------------------------------------------------

    with MetadataStore(DB_PATH) as store:

        for label, ids in [("10", ids_10), ("50", ids_50), ("100", ids_100)]:

            _section(f"{label} WORK IDs -- SQL + FETCH + CONVERSION")

            print(f"  Sample IDs : {ids[:3]} ...")
            print(f"  Warm-up    : {WARMUP_ITERS} iterations")
            print(f"  Bench      : {BENCH_ITERS} iterations")
            print()

            stats, last_result = benchmark_lookup(
                store, ids, WARMUP_ITERS, BENCH_ITERS
            )

            _print_stats(
                f"Total lookup time ({label} IDs, persistent connection):",
                stats
            )

            # Result validation
            hits   = len(last_result)
            misses = len(ids) - hits
            print(f"  Result validation:")
            print(f"    IDs requested : {len(ids)}")
            print(f"    Rows returned : {hits}")
            print(f"    Misses        : {misses}  "
                  f"(IDs not in metadata DB -- expected for sampled IDs)")
            if hits > 0:
                sample_key = next(iter(last_result))
                sample_row = last_result[sample_key]
                print(f"    Sample title  : {sample_row.get('title', 'N/A')!r}")
            print()

    # ------------------------------------------------------------------
    # Summary table
    # ------------------------------------------------------------------

    _section("SUMMARY")

    print(f"  {'Batch':>5}  {'Avg (ms)':>10}  {'Median (ms)':>12}  "
          f"{'P95 (ms)':>10}  {'Min (ms)':>10}  {'Max (ms)':>10}")
    print("  " + "-" * 60)

    with MetadataStore(DB_PATH) as store:
        rows_summary = []
        for label, ids in [("10", ids_10), ("50", ids_50), ("100", ids_100)]:
            s, _ = benchmark_lookup(store, ids, WARMUP_ITERS, BENCH_ITERS)
            rows_summary.append((label, s))

    for label, s in rows_summary:
        print(f"  {label:>5}  {s['avg']:>10.2f}  {s['med']:>12.2f}  "
              f"{s['p95']:>10.2f}  {s['min']:>10.2f}  {s['max']:>10.2f}")

    print()

    # ------------------------------------------------------------------
    # Comparison: old search_hnsw.py vs MetadataStore
    # ------------------------------------------------------------------

    _section("PERFORMANCE COMPARISON")

    old_ms = 462.0
    new_10_avg = rows_summary[0][1]["avg"]

    speedup = old_ms / new_10_avg if new_10_avg > 0 else float("inf")

    print(f"  Old search_hnsw.py (new conn per query) : ~{old_ms:.0f} ms")
    print(f"  New MetadataStore  (persistent conn)    : "
          f"~{new_10_avg:.2f} ms  (10 IDs, avg)")
    print(f"  Speedup                                 : {speedup:.1f}x")
    print()
    print("  NOTE: The old 462 ms was almost entirely DuckDB connection")
    print("  open overhead, NOT SQL execution time.")
    print()

    _divider()
    print("BENCHMARK COMPLETE")
    _divider()


if __name__ == "__main__":
    main()
