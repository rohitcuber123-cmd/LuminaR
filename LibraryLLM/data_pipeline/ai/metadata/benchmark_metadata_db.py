"""
AstraLib — Metadata Database Benchmark (Phase 7)

Benchmarks the dedicated DuckDB database against the original Parquet file.
Tests 10, 50, and 100 work IDs and compares the latency.
"""

import duckdb
import io
import os
import statistics
import sys
import time

# Force UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf_8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

# ======================================================================
# CONFIGURATION
# ======================================================================

BASE_DIR     = "D:/SDC/LibraryLLM"
PARQUET_PATH = f"{BASE_DIR}/datasets/ai/search/search_corpus.parquet"
DB_PATH      = f"{BASE_DIR}/datasets/ai/metadata/book_metadata.duckdb"

RUNS = 5

PRODUCTION_COLUMNS = [
    "work_id", "title", "authors", "subjects",
    "description", "average_rating", "rating_count", "reading_log_count",
]

# Arbitrary valid IDs (same as Phase 1)
SAMPLE_IDS_10 = [
    "OL109579W", "OL17918479W", "OL1712772W", "OL4049087W", "OL104340W",
    "OL2118056W", "OL21902795W", "OL8119491W", "OL2974813W", "OL1847914W",
]

SAMPLE_IDS_50 = SAMPLE_IDS_10 + [
    "OL12345W", "OL67890W", "OL111222W", "OL333444W", "OL555666W",
    "OL777888W", "OL999000W", "OL1111W", "OL2222W", "OL3333W",
    "OL4444W", "OL5555W", "OL6666W", "OL7777W", "OL8888W",
    "OL9999W", "OL10000W", "OL20000W", "OL30000W", "OL40000W",
    "OL50000W", "OL60000W", "OL70000W", "OL80000W", "OL90000W",
    "OL100000W", "OL200000W", "OL300000W", "OL400000W", "OL500000W",
    "OL600000W", "OL700000W", "OL800000W", "OL900000W", "OL1000000W",
    "OL1100000W", "OL1200000W", "OL1300000W", "OL1400000W", "OL1500000W",
]

SAMPLE_IDS_100 = SAMPLE_IDS_50 + [
    "OL1600000W", "OL1700000W", "OL1800000W", "OL1900000W", "OL2000000W",
    "OL2100000W", "OL2200000W", "OL2300000W", "OL2400000W", "OL2500000W",
    "OL2600000W", "OL2700000W", "OL2800000W", "OL2900000W", "OL3000000W",
    "OL3100000W", "OL3200000W", "OL3300000W", "OL3400000W", "OL3500000W",
    "OL3600000W", "OL3700000W", "OL3800000W", "OL3900000W", "OL4000000W",
    "OL4100000W", "OL4200000W", "OL4300000W", "OL4400000W", "OL4500000W",
    "OL4600000W", "OL4700000W", "OL4800000W", "OL4900000W", "OL5000000W",
    "OL5100000W", "OL5200000W", "OL5300000W", "OL5400000W", "OL5500000W",
    "OL5600000W", "OL5700000W", "OL5800000W", "OL5900000W", "OL6000000W",
    "OL6100000W", "OL6200000W", "OL6300000W", "OL6400000W", "OL6500000W",
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
    arr = sorted(times_ms)
    n = len(arr)
    return {
        "average": statistics.mean(arr),
        "median":  statistics.median(arr),
        "p95":     arr[int(n * 0.95)] if n > 1 else arr[-1],
        "minimum": arr[0],
        "maximum": arr[-1],
    }

# ======================================================================
# RUNNERS
# ======================================================================

def run_parquet(work_ids: list, runs: int) -> dict:
    times = []
    select = ", ".join(PRODUCTION_COLUMNS)
    ph = ", ".join(["?"] * len(work_ids))
    query = f"SELECT {select} FROM read_parquet(?) WHERE work_id IN ({ph})"
    params = [PARQUET_PATH] + list(work_ids)

    for _ in range(runs):
        conn = duckdb.connect()
        t0 = time.perf_counter()
        conn.execute(query, params).fetchall()
        t1 = time.perf_counter()
        conn.close()
        times.append((t1 - t0) * 1000.0)

    return _stats(times)

def run_duckdb_db(work_ids: list, runs: int) -> dict:
    times = []
    select = ", ".join(PRODUCTION_COLUMNS)
    ph = ", ".join(["?"] * len(work_ids))
    query = f"SELECT {select} FROM books WHERE work_id IN ({ph})"
    params = list(work_ids)

    # Note: Using persistent connection like we would in the API
    conn = duckdb.connect(DB_PATH)
    
    # Warmup to match realistic API state
    conn.execute(query, params).fetchall()

    for _ in range(runs):
        t0 = time.perf_counter()
        conn.execute(query, params).fetchall()
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000.0)
    
    conn.close()
    return _stats(times)

# ======================================================================
# MAIN
# ======================================================================

def main():
    if not os.path.exists(PARQUET_PATH):
        print(f"ERROR: {PARQUET_PATH} not found.", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found. Run build script first.", file=sys.stderr)
        sys.exit(1)

    _section("ASTRALIB — METADATA PERFORMANCE COMPARISON (Parquet vs DuckDB DB)")

    print(f"  Runs per test : {RUNS}")
    print()

    tests = [
        (10, SAMPLE_IDS_10),
        (50, SAMPLE_IDS_50),
        (100, SAMPLE_IDS_100),
    ]

    results = []

    for rows, ids in tests:
        print(f"  Testing {rows} IDs...")
        stat_p = run_parquet(ids, RUNS)
        stat_d = run_duckdb_db(ids, RUNS)
        results.append((rows, stat_p, stat_d))

    print()
    _divider()
    print("METADATA PERFORMANCE COMPARISON")
    _divider()
    print(f"Rows    {'Parquet':>15}    {'DuckDB DB':>15}    {'Speedup':>15}")
    print("-" * 70)

    for rows, stat_p, stat_d in results:
        p_avg = stat_p['average']
        d_avg = stat_d['average']
        speedup = (p_avg / d_avg) if d_avg > 0 else float('inf')
        
        print(f"{rows:<4}    {p_avg:>12.2f} ms    {d_avg:>12.2f} ms    {speedup:>14.2f}x")
    
    _divider()
    print()
    
    print("Detailed stats (DuckDB DB):")
    for rows, stat_p, stat_d in results:
        print(f"  Rows {rows}:")
        print(f"    Avg : {stat_d['average']:.2f} ms")
        print(f"    Med : {stat_d['median']:.2f} ms")
        print(f"    P95 : {stat_d['p95']:.2f} ms")
        print(f"    Min : {stat_d['minimum']:.2f} ms")
        print(f"    Max : {stat_d['maximum']:.2f} ms")
        print()

if __name__ == "__main__":
    main()

