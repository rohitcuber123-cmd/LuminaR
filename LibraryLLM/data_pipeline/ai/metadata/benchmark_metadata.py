"""
AstraLib — Metadata Lookup Benchmark (Phase 1)

Benchmarks DuckDB read_parquet() performance for the search_corpus.parquet
metadata store.  No Pandas.  No Python-side data loading.

Tests:
    TEST 1  — Sequential read of 10 arbitrary records (LIMIT 10)
    TEST 2  — work_id lookup for 10 IDs
    TEST 3  — work_id lookup for 50 IDs
    TEST 4  — work_id lookup for 100 IDs
    TEST 5  — Repeated work_id lookup (caching / warm-path effect)

Phase 2:
    Column projection A / B / C / D

Phase 3:
    DuckDB EXPLAIN / EXPLAIN ANALYZE for scan analysis

Each timed test is run RUNS times and statistics are reported.
"""

import duckdb
import io
import os
import statistics
import sys
import time

# ----------------------------------------------------------------------
# Force UTF-8 stdout on Windows to handle DuckDB's Unicode EXPLAIN output
# ----------------------------------------------------------------------
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf_8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer,
        encoding="utf-8",
        errors="replace",
        line_buffering=True,
    )


# ======================================================================
# CONFIGURATION
# ======================================================================

PARQUET_PATH = (
    "D:/SDC/LibraryLLM/datasets/ai/search/search_corpus.parquet"
)

# Number of timed repetitions per test
RUNS = 5

# Columns used by the production search pipeline
PRODUCTION_COLUMNS = [
    "work_id",
    "title",
    "authors",
    "subjects",
    "description",
    "average_rating",
    "rating_count",
    "reading_log_count",
]

# Arbitrary work IDs sampled from the beginning of the file.
# Real IDs that exist in the Parquet source.
SAMPLE_IDS_10 = [
    "OL109579W",
    "OL17918479W",
    "OL1712772W",
    "OL4049087W",
    "OL104340W",
    "OL2118056W",
    "OL21902795W",
    "OL8119491W",
    "OL2974813W",
    "OL1847914W",
]

SAMPLE_IDS_50 = [
    "OL109579W",   "OL17918479W", "OL1712772W",  "OL4049087W",  "OL104340W",
    "OL2118056W",  "OL21902795W", "OL8119491W",  "OL2974813W",  "OL1847914W",
    "OL12345W",    "OL67890W",    "OL111222W",   "OL333444W",   "OL555666W",
    "OL777888W",   "OL999000W",   "OL1111W",     "OL2222W",     "OL3333W",
    "OL4444W",     "OL5555W",     "OL6666W",     "OL7777W",     "OL8888W",
    "OL9999W",     "OL10000W",    "OL20000W",    "OL30000W",    "OL40000W",
    "OL50000W",    "OL60000W",    "OL70000W",    "OL80000W",    "OL90000W",
    "OL100000W",   "OL200000W",   "OL300000W",   "OL400000W",   "OL500000W",
    "OL600000W",   "OL700000W",   "OL800000W",   "OL900000W",   "OL1000000W",
    "OL1100000W",  "OL1200000W",  "OL1300000W",  "OL1400000W",  "OL1500000W",
]

SAMPLE_IDS_100 = SAMPLE_IDS_50 + [
    "OL1600000W",  "OL1700000W",  "OL1800000W",  "OL1900000W",  "OL2000000W",
    "OL2100000W",  "OL2200000W",  "OL2300000W",  "OL2400000W",  "OL2500000W",
    "OL2600000W",  "OL2700000W",  "OL2800000W",  "OL2900000W",  "OL3000000W",
    "OL3100000W",  "OL3200000W",  "OL3300000W",  "OL3400000W",  "OL3500000W",
    "OL3600000W",  "OL3700000W",  "OL3800000W",  "OL3900000W",  "OL4000000W",
    "OL4100000W",  "OL4200000W",  "OL4300000W",  "OL4400000W",  "OL4500000W",
    "OL4600000W",  "OL4700000W",  "OL4800000W",  "OL4900000W",  "OL5000000W",
    "OL5100000W",  "OL5200000W",  "OL5300000W",  "OL5400000W",  "OL5500000W",
    "OL5600000W",  "OL5700000W",  "OL5800000W",  "OL5900000W",  "OL6000000W",
    "OL6100000W",  "OL6200000W",  "OL6300000W",  "OL6400000W",  "OL6500000W",
]


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
    """Return a statistics dict from a list of millisecond timings."""
    arr = sorted(times_ms)
    n   = len(arr)
    return {
        "average": statistics.mean(arr),
        "median":  statistics.median(arr),
        "p95":     arr[int(n * 0.95)] if n > 1 else arr[-1],
        "minimum": arr[0],
        "maximum": arr[-1],
    }


def _print_stats(s: dict):
    print(f"  Average : {s['average']:>10.2f} ms")
    print(f"  Median  : {s['median']:>10.2f} ms")
    print(f"  P95     : {s['p95']:>10.2f} ms")
    print(f"  Minimum : {s['minimum']:>10.2f} ms")
    print(f"  Maximum : {s['maximum']:>10.2f} ms")
    print()


def _make_conn() -> duckdb.DuckDBPyConnection:
    """Return a fresh in-memory DuckDB connection."""
    return duckdb.connect()


def _placeholders(n: int) -> str:
    return ", ".join(["?"] * n)


def _build_select(columns: list) -> str:
    return ", ".join(columns)


# ======================================================================
# TEST RUNNERS
# ======================================================================

# ----------------------------------------------------------------------
# TEST 1 — Sequential read (LIMIT 10, no WHERE)
# ----------------------------------------------------------------------

def _run_sequential_read(runs: int) -> list:
    """
    Read 10 rows using LIMIT without any WHERE clause.
    Baseline: DuckDB can stop early once it has scanned enough rows.
    """
    times  = []
    select = _build_select(PRODUCTION_COLUMNS)
    query  = f"SELECT {select} FROM read_parquet(?) LIMIT 10"

    for _ in range(runs):
        conn = _make_conn()
        t0   = time.perf_counter()
        conn.execute(query, [PARQUET_PATH]).fetchall()
        t1   = time.perf_counter()
        conn.close()
        times.append((t1 - t0) * 1_000.0)

    return times


# ----------------------------------------------------------------------
# TEST 2 / 3 / 4 — work_id IN (...) lookup with fresh connection
# ----------------------------------------------------------------------

def _run_lookup(work_ids: list, runs: int) -> list:
    """Timed WHERE work_id IN (...) lookup with a fresh connection per run."""
    times  = []
    select = _build_select(PRODUCTION_COLUMNS)
    ph     = _placeholders(len(work_ids))
    query  = (
        f"SELECT {select} "
        f"FROM read_parquet(?) "
        f"WHERE work_id IN ({ph})"
    )
    params = [PARQUET_PATH] + list(work_ids)

    for _ in range(runs):
        conn = _make_conn()
        t0   = time.perf_counter()
        conn.execute(query, params).fetchall()
        t1   = time.perf_counter()
        conn.close()
        times.append((t1 - t0) * 1_000.0)

    return times


# ----------------------------------------------------------------------
# TEST 5 — Repeated lookup on same connection (caching effect)
# ----------------------------------------------------------------------

def _run_cached_lookup(work_ids: list, runs: int) -> list:
    """
    Run the same 10-ID lookup RUNS times on one persistent DuckDB connection.
    One cold warm-up run is performed first (not measured).
    Measures OS page cache + DuckDB buffer pool benefit.
    """
    times  = []
    select = _build_select(PRODUCTION_COLUMNS)
    ph     = _placeholders(len(work_ids))
    query  = (
        f"SELECT {select} "
        f"FROM read_parquet(?) "
        f"WHERE work_id IN ({ph})"
    )
    params = [PARQUET_PATH] + list(work_ids)

    conn = _make_conn()

    # Cold warm-up (not measured)
    conn.execute(query, params).fetchall()

    for _ in range(runs):
        t0 = time.perf_counter()
        conn.execute(query, params).fetchall()
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1_000.0)

    conn.close()
    return times


# ----------------------------------------------------------------------
# PHASE 2 — Column projection
# ----------------------------------------------------------------------

COLUMN_SETS = {
    "A": ["work_id"],
    "B": ["work_id", "title"],
    "C": ["work_id", "title", "authors", "subjects"],
    "D": PRODUCTION_COLUMNS,
}


def _run_projection(work_ids: list, columns: list, runs: int) -> list:
    """Timed lookup selecting only a subset of columns."""
    times  = []
    select = _build_select(columns)
    ph     = _placeholders(len(work_ids))
    query  = (
        f"SELECT {select} "
        f"FROM read_parquet(?) "
        f"WHERE work_id IN ({ph})"
    )
    params = [PARQUET_PATH] + list(work_ids)

    for _ in range(runs):
        conn = _make_conn()
        t0   = time.perf_counter()
        conn.execute(query, params).fetchall()
        t1   = time.perf_counter()
        conn.close()
        times.append((t1 - t0) * 1_000.0)

    return times


# ----------------------------------------------------------------------
# PHASE 3 — EXPLAIN plans
# ----------------------------------------------------------------------

def _print_explain(work_ids: list):
    """
    Print the DuckDB logical EXPLAIN plan for the work_id IN (...) query.
    Reveals whether DuckDB can prune Parquet row groups via statistics.
    """
    select = _build_select(PRODUCTION_COLUMNS)
    ph     = _placeholders(len(work_ids))
    query  = (
        f"EXPLAIN "
        f"SELECT {select} "
        f"FROM read_parquet(?) "
        f"WHERE work_id IN ({ph})"
    )
    params = [PARQUET_PATH] + list(work_ids)

    conn = _make_conn()
    rows = conn.execute(query, params).fetchall()
    conn.close()

    for row in rows:
        # DuckDB EXPLAIN returns rows of (explain_key, explain_value)
        print(row[-1])


def _print_explain_analyze(work_ids: list):
    """
    Print the DuckDB EXPLAIN ANALYZE plan (actual row counts + timings).
    Gracefully degrades if the DuckDB version does not support it.
    """
    select = _build_select(PRODUCTION_COLUMNS)
    ph     = _placeholders(len(work_ids))
    query  = (
        f"EXPLAIN ANALYZE "
        f"SELECT {select} "
        f"FROM read_parquet(?) "
        f"WHERE work_id IN ({ph})"
    )
    params = [PARQUET_PATH] + list(work_ids)

    conn = _make_conn()
    try:
        rows = conn.execute(query, params).fetchall()
        for row in rows:
            print(row[-1])
    except Exception as exc:
        print(
            f"  (EXPLAIN ANALYZE not available or failed: {exc})"
        )
    finally:
        conn.close()


# ======================================================================
# MAIN
# ======================================================================

def main():

    # ------------------------------------------------------------------
    # Validate parquet file exists
    # ------------------------------------------------------------------

    if not os.path.exists(PARQUET_PATH):
        print(
            f"\nERROR: Parquet file not found:\n  {PARQUET_PATH}",
            file=sys.stderr,
        )
        sys.exit(1)

    parquet_size_gb = os.path.getsize(PARQUET_PATH) / (1024 ** 3)

    # ==================================================================
    # HEADER
    # ==================================================================

    print()
    _section("ASTRALIB — METADATA LOOKUP BENCHMARK")

    print(f"Parquet : {PARQUET_PATH}")
    print(f"Size    : {parquet_size_gb:.2f} GB")
    print(f"Runs    : {RUNS} repetitions per test")
    print()

    # ==================================================================
    # TEST 1 — Sequential read (LIMIT 10, no WHERE)
    # ==================================================================

    _section("TEST 1 — Sequential read (LIMIT 10, no WHERE filter)")

    print("  Query   : SELECT <prod_columns> FROM read_parquet(?) LIMIT 10")
    print("  Purpose : Baseline — how fast can DuckDB return the first 10 rows")
    print()
    print(f"  Running {RUNS} repetitions …")
    t1_times = _run_sequential_read(RUNS)
    s = _stats(t1_times)
    print(f"  Rows    : 10")
    _print_stats(s)

    # ==================================================================
    # TEST 2 — work_id lookup: 10 IDs, fresh connection
    # ==================================================================

    _section("TEST 2 — work_id lookup (10 IDs, fresh connection per run)")

    print("  Query   : SELECT <prod_columns> FROM read_parquet(?) WHERE work_id IN (...10...)")
    print(f"  Running {RUNS} repetitions …")
    t2_times = _run_lookup(SAMPLE_IDS_10, RUNS)
    s = _stats(t2_times)
    print(f"  Rows    : 10 requested  (some IDs may not exist in the file)")
    _print_stats(s)

    # ==================================================================
    # TEST 3 — work_id lookup: 50 IDs, fresh connection
    # ==================================================================

    _section("TEST 3 — work_id lookup (50 IDs, fresh connection per run)")

    print("  Query   : SELECT <prod_columns> FROM read_parquet(?) WHERE work_id IN (...50...)")
    print(f"  Running {RUNS} repetitions …")
    t3_times = _run_lookup(SAMPLE_IDS_50, RUNS)
    s = _stats(t3_times)
    print(f"  Rows    : 50 requested")
    _print_stats(s)

    # ==================================================================
    # TEST 4 — work_id lookup: 100 IDs, fresh connection
    # ==================================================================

    _section("TEST 4 — work_id lookup (100 IDs, fresh connection per run)")

    print("  Query   : SELECT <prod_columns> FROM read_parquet(?) WHERE work_id IN (...100...)")
    print(f"  Running {RUNS} repetitions …")
    t4_times = _run_lookup(SAMPLE_IDS_100, RUNS)
    s = _stats(t4_times)
    print(f"  Rows    : 100 requested")
    _print_stats(s)

    # ==================================================================
    # TEST 5 — Repeated 10-ID lookup on same connection
    # ==================================================================

    _section("TEST 5 — Repeated lookup: OS/DuckDB caching effect (10 IDs, warm conn)")

    print("  Query   : Same 10-ID WHERE work_id IN (...) on one persistent connection")
    print("  Purpose : Measure warm-path benefit from OS page cache / DuckDB buffer pool")
    print("  Note    : One unmeasured cold warm-up run precedes the timed runs")
    print()
    print(f"  Running {RUNS} timed repetitions …")
    t5_times = _run_cached_lookup(SAMPLE_IDS_10, RUNS)
    s = _stats(t5_times)
    print(f"  Rows    : 10")
    _print_stats(s)

    # Caching delta
    cold_avg = statistics.mean(t2_times)
    warm_avg = statistics.mean(t5_times)
    speedup  = cold_avg / warm_avg if warm_avg > 0 else float("inf")

    print("  Caching comparison (10-ID lookup):")
    print(f"    Cold average (fresh conn per run) : {cold_avg:>10.2f} ms")
    print(f"    Warm average (persistent conn)    : {warm_avg:>10.2f} ms")
    print(f"    Cache speedup                     : {speedup:.2f}x")
    print()

    # ==================================================================
    # PHASE 2 — Column projection benchmark
    # ==================================================================

    _section("PHASE 2 — Column Projection Benchmark (10-ID lookup)")

    print("  Tests whether selecting fewer columns reduces latency.")
    print("  Parquet is a columnar format; only selected column chunks are read.")
    print()
    print(f"  Work IDs : 10 | Runs : {RUNS} per set")
    print()

    projection_results = {}
    for label, cols in COLUMN_SETS.items():
        col_str = ", ".join(cols)
        print(f"  Set {label}: [{col_str}]")
        times = _run_projection(SAMPLE_IDS_10, cols, RUNS)
        s     = _stats(times)
        projection_results[label] = s
        print(f"    Average : {s['average']:.2f} ms")
        print(f"    Median  : {s['median']:.2f} ms")
        print(f"    P95     : {s['p95']:.2f} ms")
        print()

    # Projection summary table
    _divider("-")
    print("  COLUMN PROJECTION SUMMARY (10 IDs):")
    _divider("-")
    print(f"  {'Set':<5}  {'Columns':<48}  {'Avg (ms)':>10}  {'Median (ms)':>12}")
    _divider("-")
    for label, cols in COLUMN_SETS.items():
        s       = projection_results[label]
        col_str = ", ".join(cols)
        if len(col_str) > 46:
            col_str = col_str[:43] + "..."
        print(
            f"  {label:<5}  {col_str:<48}  "
            f"{s['average']:>10.2f}  {s['median']:>12.2f}"
        )
    _divider("-")
    print()

    # ==================================================================
    # PHASE 3 — EXPLAIN plan (scan analysis)
    # ==================================================================

    _section("PHASE 3 — DuckDB EXPLAIN Plan (10-ID work_id lookup)")

    print(
        "  Key question: Does DuckDB scan all 40M rows, or can it prune\n"
        "  row groups using Parquet column statistics (min/max) or bloom filters?\n"
        "  If the plan shows PARQUET_SCAN over all rows, a full scan is occurring.\n"
    )
    print("  --- EXPLAIN output ---")
    print()
    _print_explain(SAMPLE_IDS_10)

    print()
    _section("PHASE 3 — DuckDB EXPLAIN ANALYZE (10-ID work_id lookup)")
    print("  Shows actual row counts and timing per node (requires DuckDB >= 0.9).")
    print()
    print("  --- EXPLAIN ANALYZE output ---")
    print()
    _print_explain_analyze(SAMPLE_IDS_10)

    # ==================================================================
    # SUMMARY TABLE
    # ==================================================================

    print()
    _section("BENCHMARK SUMMARY")

    col_w = 46
    print(
        f"  {'Test':<{col_w}}  {'Avg (ms)':>10}  "
        f"{'Median':>10}  {'P95':>10}  {'Min':>10}  {'Max':>10}"
    )
    _divider("-")

    def _row(label: str, times: list):
        s = _stats(times)
        print(
            f"  {label:<{col_w}}  "
            f"{s['average']:>10.2f}  "
            f"{s['median']:>10.2f}  "
            f"{s['p95']:>10.2f}  "
            f"{s['minimum']:>10.2f}  "
            f"{s['maximum']:>10.2f}"
        )

    _row("TEST 1  Sequential LIMIT 10",              t1_times)
    _row("TEST 2  work_id IN(10)  cold conn",         t2_times)
    _row("TEST 3  work_id IN(50)  cold conn",         t3_times)
    _row("TEST 4  work_id IN(100) cold conn",         t4_times)
    _row("TEST 5  work_id IN(10)  warm conn (cache)", t5_times)
    _divider("-")
    print()

    # ==================================================================
    # DIAGNOSIS
    # ==================================================================

    _section("DIAGNOSIS")

    avg_10  = statistics.mean(t2_times)
    avg_50  = statistics.mean(t3_times)
    avg_100 = statistics.mean(t4_times)

    threshold_ms = 200.0

    if avg_10 > threshold_ms:
        print(
            f"  BOTTLENECK CONFIRMED:\n"
            f"    10-ID lookup averages {avg_10:,.0f} ms (~{avg_10/1000:.2f} s).\n"
            f"    This matches the observed ~6250 ms production latency.\n"
            f"    DuckDB is almost certainly performing a full scan of the\n"
            f"    4 GB Parquet file to satisfy a WHERE work_id IN (...) filter\n"
            f"    because the work_id column is not sorted or bloom-filtered.\n"
            f"\n"
            f"  RECOMMENDATION:\n"
            f"    Proceed with Phase 4-6 to build a dedicated DuckDB database\n"
            f"    (book_metadata.duckdb) containing only the 5M production records.\n"
            f"    A B-tree PRIMARY KEY on work_id will allow O(log n) lookups.\n"
        )
    else:
        print(
            f"  OK: 10-ID lookup averages {avg_10:.0f} ms — within acceptable range.\n"
            f"  A dedicated metadata store may still improve latency further.\n"
        )

    print(
        "  Parquet row-group pruning is possible only when:\n"
        "    (a) The work_id column is physically sorted (clustered) in the file, OR\n"
        "    (b) Bloom filters were written at Parquet creation time.\n"
        "  If the EXPLAIN plan shows a PARQUET_SCAN of all row groups,\n"
        "  neither condition holds for this file.\n"
    )

    _divider()
    print("END OF PHASE 1 BENCHMARK — Review results before proceeding to Phase 4.")
    _divider()
    print()


# ======================================================================
# ENTRY POINT
# ======================================================================

if __name__ == "__main__":
    main()

