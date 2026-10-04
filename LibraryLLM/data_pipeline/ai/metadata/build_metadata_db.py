"""
AstraLib — Build 5M Metadata Database (Phases 4–6)

Creates datasets/ai/metadata/book_metadata.duckdb from the 40M-row
search_corpus.parquet source, keeping only the 5M books present in
the production embedding corpus.

Strategy
--------
1. Load work_ids.npy via memory-map (no full copy into Python RAM).
2. Insert the 5M work IDs into a DuckDB temporary table using Arrow /
   numpy chunked batches — heavy lifting stays inside DuckDB.
3. Verify coverage:
     • Total rows and distinct work_ids in the Parquet source
     • How many of the 5M production IDs have matching metadata
     • How many are missing (reported, not silently dropped)
4. Materialise the filtered table via INNER JOIN (avoids a 5M-element
   IN(...) parameter list that would exceed DuckDB's limit):
     CREATE TABLE books AS
     SELECT p.* FROM read_parquet(?) p
     INNER JOIN tmp_work_ids t ON p.work_id = t.work_id
5. Create a UNIQUE INDEX on work_id for O(log n) lookups.

Do NOT use Pandas.
Do NOT load the Parquet file into Python memory.
"""

import io
import numpy as np
import os
import sys
import time
import duckdb
import tempfile

# Force UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf_8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

# ======================================================================
# PATHS
# ======================================================================

BASE_DIR     = "D:/SDC/LibraryLLM"

PARQUET_PATH = f"{BASE_DIR}/datasets/ai/search/search_corpus.parquet"
WORK_IDS_NPY = f"{BASE_DIR}/datasets/ai/embeddings/vectors/work_ids.npy"
OUTPUT_DB    = f"{BASE_DIR}/datasets/ai/metadata/book_metadata.duckdb"

# Production columns to store (matches search_hnsw.py)
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

def _fmt_ms(t_sec: float) -> str:
    return f"{t_sec * 1000:.1f} ms"

def _fmt_sec(t_sec: float) -> str:
    return f"{t_sec:.2f} s"


# ======================================================================
# MAIN
# ======================================================================

def main():

    # ------------------------------------------------------------------
    # Validate inputs
    # ------------------------------------------------------------------

    for path, label in [
        (PARQUET_PATH, "search_corpus.parquet"),
        (WORK_IDS_NPY, "work_ids.npy"),
    ]:
        if not os.path.exists(path):
            print(f"ERROR: {label} not found:\n  {path}", file=sys.stderr)
            sys.exit(1)

    if os.path.exists(OUTPUT_DB):
        print(f"WARNING: Output database already exists:\n  {OUTPUT_DB}")
        print("  Removing existing database to rebuild from scratch …")
        os.remove(OUTPUT_DB)
        # DuckDB also writes a .wal file
        wal = OUTPUT_DB + ".wal"
        if os.path.exists(wal):
            os.remove(wal)
        print()

    # ==================================================================
    # HEADER
    # ==================================================================

    print()
    _section("ASTRALIB — BUILD 5M METADATA DATABASE")

    src_size_gb = os.path.getsize(PARQUET_PATH) / (1024 ** 3)
    npy_size_mb = os.path.getsize(WORK_IDS_NPY) / (1024 ** 2)

    print(f"  Source Parquet : {PARQUET_PATH}")
    print(f"  Source size    : {src_size_gb:.2f} GB")
    print(f"  work_ids.npy   : {WORK_IDS_NPY}")
    print(f"  work_ids size  : {npy_size_mb:.1f} MB")
    print(f"  Output DB      : {OUTPUT_DB}")
    print()

    # ==================================================================
    # STEP 1 — Load work_ids.npy via mmap
    # ==================================================================

    _section("STEP 1 — Load production work IDs (mmap)")

    t0 = time.perf_counter()
    work_ids_arr = np.load(WORK_IDS_NPY, allow_pickle=True)
    t_load = time.perf_counter() - t0

    n_production = len(work_ids_arr)
    print(f"  work_ids.npy loaded  : {_fmt_ms(t_load)}")
    print(f"  Production work IDs  : {n_production:,}")
    print(f"  dtype                : {work_ids_arr.dtype}")
    print(f"  Sample IDs           : {list(work_ids_arr[:5])}")
    print()

    if n_production == 0:
        print("ERROR: work_ids.npy is empty.", file=sys.stderr)
        sys.exit(1)

    # ==================================================================
    # STEP 2 — Open DuckDB and register work IDs
    # ==================================================================

    _section("STEP 2 — Register work IDs in DuckDB temporary table")

    # Open the persistent output database
    conn = duckdb.connect(OUTPUT_DB)

    # ----------------------------------------------------------------
    # Write to a temporary CSV and load via DuckDB's native fast CSV reader.
    # This avoids all executemany / connection pooling / appender issues.
    # ----------------------------------------------------------------

    t0 = time.perf_counter()

    print(f"  Exporting {n_production:,} IDs to temp CSV and loading …")
    
    # Pre-convert to python strings
    work_id_strings = [str(x) for x in work_ids_arr]
    
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", encoding="utf-8") as f:
        temp_csv = f.name
        f.write("work_id\n")
        f.write("\n".join(work_id_strings))

    conn.execute(f"""
        CREATE TEMPORARY TABLE tmp_work_ids AS 
        SELECT CAST(work_id AS VARCHAR) as work_id 
        FROM read_csv('{temp_csv}', header=True)
    """)
    
    os.remove(temp_csv)

    t_insert = time.perf_counter() - t0

    verify = conn.execute("SELECT COUNT(*) FROM tmp_work_ids").fetchone()[0]
    print(f"  Inserted             : {verify:,} rows  ({_fmt_sec(t_insert)})")
    print()

    if verify != n_production:
        print(
            f"ERROR: Expected {n_production:,} rows in tmp_work_ids, "
            f"got {verify:,}.",
            file=sys.stderr,
        )
        conn.close()
        sys.exit(1)

    # ==================================================================
    # STEP 3 — Verify coverage
    # ==================================================================

    _section("STEP 3 — Verify coverage (40M Parquet vs 5M production IDs)")

    print("  Counting total rows in Parquet (this will take a moment) …")
    t0 = time.perf_counter()
    total_parquet = conn.execute(
        "SELECT COUNT(*) FROM read_parquet(?)", [PARQUET_PATH]
    ).fetchone()[0]
    t_count = time.perf_counter() - t0
    print(f"  Parquet total rows   : {total_parquet:,}  ({_fmt_sec(t_count)})")

    print("  Counting distinct work_ids in Parquet …")
    t0 = time.perf_counter()
    distinct_parquet = conn.execute(
        "SELECT COUNT(DISTINCT work_id) FROM read_parquet(?)", [PARQUET_PATH]
    ).fetchone()[0]
    t_distinct = time.perf_counter() - t0
    print(f"  Parquet distinct IDs : {distinct_parquet:,}  ({_fmt_sec(t_distinct)})")

    print("  Counting matching IDs (INNER JOIN) …")
    t0 = time.perf_counter()
    matches = conn.execute("""
        SELECT COUNT(*)
        FROM tmp_work_ids t
        INNER JOIN read_parquet(?) p ON t.work_id = p.work_id
    """, [PARQUET_PATH]).fetchone()[0]
    t_match = time.perf_counter() - t0
    print(f"  Matches              : {matches:,}  ({_fmt_sec(t_match)})")

    missing = n_production - matches
    print()
    print(f"  Production work IDs  : {n_production:,}")
    print(f"  Metadata matches     : {matches:,}")
    print(f"  Missing metadata     : {missing:,}")
    print()

    if missing > 0:
        print(
            f"  WARNING: {missing:,} production work IDs have no metadata "
            f"in the Parquet source.\n"
            f"  These IDs will be absent from the metadata database.\n"
            f"  They will return empty metadata in search results.\n"
        )
        # Show a sample of missing IDs
        sample_missing = conn.execute("""
            SELECT t.work_id
            FROM tmp_work_ids t
            LEFT JOIN read_parquet(?) p ON t.work_id = p.work_id
            WHERE p.work_id IS NULL
            LIMIT 10
        """, [PARQUET_PATH]).fetchall()
        print("  Sample missing IDs:")
        for row in sample_missing:
            print(f"    {row[0]}")
        print()
    else:
        print("  All 5M production work IDs have matching metadata.")
        print()

    # ==================================================================
    # STEP 4 — Materialise the 5M books table
    # ==================================================================

    _section("STEP 4 — CREATE TABLE books (5M records via INNER JOIN)")

    col_select = ", ".join(f"p.{c}" for c in PRODUCTION_COLUMNS)

    print("  Running:")
    print(f"    CREATE TABLE books AS")
    print(f"    SELECT {col_select}")
    print(f"    FROM read_parquet(?) p")
    print(f"    INNER JOIN tmp_work_ids t ON p.work_id = t.work_id")
    print()
    print("  This may take 5–15 minutes (full Parquet scan with JOIN) …")
    print()

    t0 = time.perf_counter()

    conn.execute(f"""
        CREATE TABLE books AS
        SELECT {col_select}
        FROM read_parquet(?) p
        INNER JOIN tmp_work_ids t ON p.work_id = t.work_id
    """, [PARQUET_PATH])

    t_create = time.perf_counter() - t0

    book_count = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    print(f"  Table created        : {book_count:,} rows  ({_fmt_sec(t_create)})")
    print()

    if book_count != matches:
        print(
            f"  WARNING: book_count ({book_count:,}) != match count ({matches:,}). "
            f"Possible duplicate work_ids in the Parquet file."
        )

    # ==================================================================
    # STEP 5 — Create index
    # ==================================================================

    _section("STEP 5 — CREATE UNIQUE INDEX on work_id")

    # Verify uniqueness before attempting UNIQUE index
    print("  Verifying work_id uniqueness …")
    dup_count = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT work_id FROM books
            GROUP BY work_id HAVING COUNT(*) > 1
        )
    """).fetchone()[0]

    if dup_count > 0:
        print(f"  WARNING: {dup_count:,} duplicate work_ids found.")
        print("  Creating non-unique index instead …")
        index_sql = "CREATE INDEX idx_books_work_id ON books(work_id)"
        index_type = "non-unique"
    else:
        print(f"  work_id is unique across all {book_count:,} rows.")
        index_sql = "CREATE UNIQUE INDEX idx_books_work_id ON books(work_id)"
        index_type = "UNIQUE"

    t0 = time.perf_counter()
    conn.execute(index_sql)
    t_index = time.perf_counter() - t0

    print(f"  Index created ({index_type}): {_fmt_sec(t_index)}")
    print()

    # ==================================================================
    # STEP 6 — Quick smoke test
    # ==================================================================

    _section("STEP 6 — Smoke test (10-ID lookup from new database)")

    # Use the first 10 IDs from work_ids_arr that we know should exist
    test_ids = [str(x) for x in work_ids_arr[:10]]
    ph = ", ".join(["?"] * len(test_ids))

    t0 = time.perf_counter()
    rows = conn.execute(
        f"SELECT work_id, title FROM books WHERE work_id IN ({ph})",
        test_ids,
    ).fetchall()
    t_smoke = time.perf_counter() - t0

    print(f"  Query : SELECT work_id, title FROM books WHERE work_id IN (...10...)")
    print(f"  Time  : {_fmt_ms(t_smoke)}  (rows returned: {len(rows)})")
    print()
    for row in rows:
        print(f"    {row[0]:<20}  {(row[1] or 'N/A')[:60]}")
    print()

    # ==================================================================
    # DONE
    # ==================================================================

    conn.close()

    db_size_mb = os.path.getsize(OUTPUT_DB) / (1024 ** 2)

    _section("BUILD COMPLETE")

    print(f"  Output DB            : {OUTPUT_DB}")
    print(f"  Database size        : {db_size_mb:.1f} MB  ({db_size_mb/1024:.2f} GB)")
    print(f"  Rows in books table  : {book_count:,}")
    print(f"  Index                : idx_books_work_id ({index_type})")
    print()
    print(f"  Timing summary:")
    print(f"    Load work_ids.npy  : {_fmt_ms(t_load)}")
    print(f"    Insert to tmp      : {_fmt_sec(t_insert)}")
    print(f"    Count Parquet rows : {_fmt_sec(t_count)}")
    print(f"    Count distinct IDs : {_fmt_sec(t_distinct)}")
    print(f"    Coverage match     : {_fmt_sec(t_match)}")
    print(f"    CREATE TABLE books : {_fmt_sec(t_create)}")
    print(f"    CREATE INDEX       : {_fmt_sec(t_index)}")
    print()
    print("  Next step: run benchmark_metadata_db.py to compare performance.")
    _divider()
    print()


# ======================================================================
# ENTRY POINT
# ======================================================================

if __name__ == "__main__":
    main()

