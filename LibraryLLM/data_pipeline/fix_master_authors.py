from pathlib import Path
import duckdb
import time


# ============================================================
# PATHS
# ============================================================

BASE = Path(r"D:\SDC\LibraryLLM\datasets\cleaned")

WORKS = BASE / "works.parquet"
AUTHORS = BASE / "authors.parquet"

TEMP_DIR = Path(r"D:\SDC\LibraryLLM\temp_duckdb")
MASTER_DIR = Path(r"D:\SDC\LibraryLLM\datasets\master")

OUTPUT = MASTER_DIR / "books_master.parquet"
DB = TEMP_DIR / "astralib.duckdb"


start = time.time()


print("=" * 70)
print("ASTRALIB - FIX WORK AUTHOR RELATIONSHIPS")
print("=" * 70)

print()
print(f"Database : {DB}")
print(f"Output   : {OUTPUT}")


# ============================================================
# CONNECT
# ============================================================

con = duckdb.connect(str(DB))


# ============================================================
# SETTINGS
# ============================================================

con.execute("SET threads = 4")
con.execute("SET memory_limit = '8GB'")
con.execute("SET preserve_insertion_order = false")

con.execute(
    "SET temp_directory = "
    f"'{TEMP_DIR.as_posix()}'"
)

con.execute(
    "SET max_temp_directory_size = '50GB'"
)

con.execute(
    "SET enable_progress_bar = true"
)

con.execute(
    "SET enable_progress_bar_print = true"
)

con.execute(
    "SET progress_bar_time = 1000"
)


# ============================================================
# CHECK EXISTING TABLES
# ============================================================

print()
print("=" * 70)
print("CHECKING EXISTING AGGREGATIONS")
print("=" * 70)

tables = con.execute(
    """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'main'
    ORDER BY table_name
    """
).fetchall()

for table in tables:
    print(f"✓ {table[0]}")


required = {
    "work_editions",
    "work_ratings",
    "work_reading",
    "work_covers",
}

existing = {
    table[0]
    for table in tables
}

missing = required - existing

if missing:

    print()
    print("ERROR: Required aggregation tables are missing:")

    for table in missing:
        print(f"  - {table}")

    con.close()
    raise SystemExit(1)


# ============================================================
# STAGE 1
# ============================================================

print()
print("=" * 70)
print("STAGE 1/2 - REBUILDING WORK → AUTHOR")
print("=" * 70)

print()
print("Using author_ids directly from works.parquet...")
print()


# ------------------------------------------------------------
# IMPORTANT:
#
# DuckDB-compatible replacement for regexp_split_to_table:
#
# string_split(...)
# +
# UNNEST(...)
# ------------------------------------------------------------

con.execute(
    f"""
    CREATE OR REPLACE TABLE work_authors AS

    WITH work_author_ids AS (

        SELECT

            w.work_id,

            TRIM(
                unnest(
                    string_split(
                        w.author_ids,
                        '|'
                    )
                )
            ) AS author_id

        FROM read_parquet(
            '{WORKS}'
        ) w

        WHERE

            w.author_ids IS NOT NULL

            AND

            w.author_ids != ''

    )

    SELECT

        wai.work_id,

        string_agg(
            DISTINCT a.name,
            ' | '
        ) AS authors

    FROM work_author_ids wai

    INNER JOIN read_parquet(
        '{AUTHORS}'
    ) a

        ON wai.author_id =
           a.author_id

    WHERE

        a.name IS NOT NULL

        AND

        a.name != ''

    GROUP BY

        wai.work_id
    """
)


# ============================================================
# AUTHOR COVERAGE
# ============================================================

print()
print("=" * 70)
print("CHECKING AUTHOR COVERAGE")
print("=" * 70)

author_count = con.execute(
    """
    SELECT COUNT(*)
    FROM work_authors
    """
).fetchone()[0]


print()
print(
    f"Works with authors after fix : "
    f"{author_count:,}"
)


# ============================================================
# STAGE 2
# ============================================================

print()
print("=" * 70)
print("STAGE 2/2 - REBUILDING MASTER")
print("=" * 70)

print()
print("Reusing existing aggregation tables:")

print("  ✓ work_editions")
print("  ✓ work_ratings")
print("  ✓ work_reading")
print("  ✓ work_covers")

print()
print("Only the final master is being rebuilt.")
print()


if OUTPUT.exists():
    OUTPUT.unlink()


con.execute(
    f"""
    COPY (

        SELECT

            -- =================================================
            -- WORK
            -- =================================================

            w.work_id,

            w.title,

            NULLIF(
                w.description,
                ''
            ) AS description,

            NULLIF(
                w.subjects,
                ''
            ) AS subjects,

            wa.authors,

            w.first_publish_date,


            -- =================================================
            -- EDITIONS
            -- =================================================

            COALESCE(
                we.edition_count,
                0
            ) AS edition_count,

            we.earliest_publish_date,

            we.latest_publish_date,

            we.publisher,

            we.physical_format,

            we.isbn10,

            we.isbn13,

            we.max_pages,


            -- =================================================
            -- COVER
            -- =================================================

            wc.cover_id,


            -- =================================================
            -- RATINGS
            -- =================================================

            COALESCE(
                wr.average_rating,
                0
            ) AS average_rating,

            COALESCE(
                wr.rating_count,
                0
            ) AS rating_count,

            COALESCE(
                wr.five_star_count,
                0
            ) AS five_star_count,

            COALESCE(
                wr.four_star_count,
                0
            ) AS four_star_count,

            COALESCE(
                wr.three_star_count,
                0
            ) AS three_star_count,

            COALESCE(
                wr.two_star_count,
                0
            ) AS two_star_count,

            COALESCE(
                wr.one_star_count,
                0
            ) AS one_star_count,


            -- =================================================
            -- READING
            -- =================================================

            COALESCE(
                rr.reading_log_count,
                0
            ) AS reading_log_count,

            COALESCE(
                rr.want_to_read_count,
                0
            ) AS want_to_read_count,

            COALESCE(
                rr.already_read_count,
                0
            ) AS already_read_count,

            COALESCE(
                rr.currently_reading_count,
                0
            ) AS currently_reading_count,

            COALESCE(
                rr.stopped_reading_count,
                0
            ) AS stopped_reading_count


        FROM read_parquet(
            '{WORKS}'
        ) w

        LEFT JOIN work_authors wa
            ON w.work_id = wa.work_id

        LEFT JOIN work_editions we
            ON w.work_id = we.work_id

        LEFT JOIN work_ratings wr
            ON w.work_id = wr.work_id

        LEFT JOIN work_reading rr
            ON w.work_id = rr.work_id

        LEFT JOIN work_covers wc
            ON w.work_id = wc.work_id

    )

    TO '{OUTPUT}'

    (
        FORMAT PARQUET,
        COMPRESSION ZSTD
    )
    """
)


# ============================================================
# VALIDATE
# ============================================================

print()
print("=" * 70)
print("VALIDATING FIXED MASTER")
print("=" * 70)

result = con.execute(
    f"""
    SELECT

        COUNT(*) AS total_works,

        COUNT(
            DISTINCT work_id
        ) AS unique_works,

        COUNT(*) FILTER (
            WHERE
                authors IS NOT NULL

                AND

                authors != ''
        ) AS with_authors

    FROM read_parquet(
        '{OUTPUT}'
    )
    """
).fetchone()


print()
print(
    f"Total works       : {result[0]:,}"
)

print(
    f"Unique work IDs   : {result[1]:,}"
)

print(
    f"With authors      : {result[2]:,}"
)

print(
    "Original author coverage : 39,220,246"
)

print(
    f"Remaining gap     : "
    f"{39_220_246 - result[2]:,}"
)


# ============================================================
# DUPLICATE CHECK
# ============================================================

print()
print("DUPLICATE WORK IDs")
print("-" * 70)

duplicates = con.execute(
    f"""
    SELECT

        work_id,

        COUNT(*) AS count

    FROM read_parquet(
        '{OUTPUT}'
    )

    GROUP BY work_id

    HAVING COUNT(*) > 1

    LIMIT 10
    """
).fetchall()


if duplicates:

    for row in duplicates:
        print(row)

else:

    print("None found")


# ============================================================
# FILE SIZE
# ============================================================

size_gb = (
    OUTPUT.stat().st_size
    / (1024 ** 3)
)

elapsed = (
    time.time() - start
) / 60


print()
print("=" * 70)
print("AUTHOR FIX COMPLETE")
print("=" * 70)

print()
print(
    f"File size : {size_gb:.2f} GB"
)

print(
    f"Location  : {OUTPUT}"
)

print(
    f"Time      : {elapsed:.2f} minutes"
)


con.close()