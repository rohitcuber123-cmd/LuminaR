from pathlib import Path
import duckdb
import time

DB = Path(r"D:\SDC\LibraryLLM\temp_duckdb\astralib.duckdb")

WORKS = Path(r"D:\SDC\LibraryLLM\datasets\cleaned\works.parquet")

OUTPUT = Path(
    r"D:\SDC\LibraryLLM\datasets\master\books_master.parquet"
)

TEMP = Path(r"D:\SDC\LibraryLLM\temp_duckdb")

start = time.time()

print("=" * 70)
print("ASTRALIB - REBUILD MASTER WITH FIXED AUTHORS")
print("=" * 70)

print()
print(f"Database : {DB}")
print(f"Output   : {OUTPUT}")
print()

con = duckdb.connect(str(DB))

# ------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------

con.execute("SET threads = 4")
con.execute("SET memory_limit = '8GB'")
con.execute("SET preserve_insertion_order = false")

con.execute(
    f"SET temp_directory = '{TEMP.as_posix()}'"
)

con.execute(
    "SET max_temp_directory_size = '50GB'"
)

con.execute("SET enable_progress_bar = true")
con.execute("SET enable_progress_bar_print = true")
con.execute("SET progress_bar_time = 1000")


# ------------------------------------------------------------
# VERIFY TABLES
# ------------------------------------------------------------

print("=" * 70)
print("CHECKING AGGREGATIONS")
print("=" * 70)

required = [
    "work_authors",
    "work_covers",
    "work_editions",
    "work_ratings",
    "work_reading",
]

for table in required:

    exists = con.execute(
        f"""
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'main'
        AND table_name = '{table}'
        """
    ).fetchone()[0]

    if not exists:

        raise RuntimeError(
            f"Missing DuckDB table: {table}"
        )

    print(f"✓ {table}")


# ------------------------------------------------------------
# AUTHOR STATISTICS
# ------------------------------------------------------------

print()
print("=" * 70)
print("AUTHOR COVERAGE")
print("=" * 70)

author_count = con.execute(
    """
    SELECT COUNT(*)
    FROM work_authors
    """
).fetchone()[0]

print(
    f"Works with authors : {author_count:,}"
)

print(
    f"Original Works     : 39,220,246"
)

print(
    f"Gap                : "
    f"{39_220_246 - author_count:,}"
)


# ------------------------------------------------------------
# REBUILD MASTER
# ------------------------------------------------------------

print()
print("=" * 70)
print("REBUILDING BOOKS MASTER")
print("=" * 70)

print()
print("Using existing aggregation tables.")
print("The 56.6M-edition aggregation will NOT be repeated.")
print()

if OUTPUT.exists():
    print("Removing previous master...")
    OUTPUT.unlink()


con.execute(
    f"""
    COPY (

        SELECT

            -- ================================================
            -- WORK
            -- ================================================

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


            -- ================================================
            -- EDITIONS
            -- ================================================

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


            -- ================================================
            -- COVER
            -- ================================================

            wc.cover_id,


            -- ================================================
            -- RATINGS
            -- ================================================

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


            -- ================================================
            -- READING
            -- ================================================

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


# ------------------------------------------------------------
# VALIDATION
# ------------------------------------------------------------

print()
print("=" * 70)
print("VALIDATING MASTER")
print("=" * 70)

stats = con.execute(
    f"""
    SELECT

        COUNT(*) AS total_works,

        COUNT(
            DISTINCT work_id
        ) AS unique_works,

        COUNT(*) FILTER (
            WHERE authors IS NOT NULL
            AND authors != ''
        ) AS with_authors,

        COUNT(*) FILTER (
            WHERE title IS NOT NULL
            AND title != ''
        ) AS with_titles,

        COUNT(*) FILTER (
            WHERE description IS NOT NULL
            AND description != ''
        ) AS with_descriptions,

        COUNT(*) FILTER (
            WHERE subjects IS NOT NULL
            AND subjects != ''
        ) AS with_subjects,

        COUNT(*) FILTER (
            WHERE average_rating > 0
        ) AS with_ratings,

        COUNT(*) FILTER (
            WHERE reading_log_count > 0
        ) AS with_reading,

        COUNT(*) FILTER (
            WHERE cover_id IS NOT NULL
        ) AS with_covers

    FROM read_parquet(
        '{OUTPUT}'
    )
    """
).fetchone()


print()
print(
    f"Total works         : {stats[0]:,}"
)

print(
    f"Unique work IDs     : {stats[1]:,}"
)

print(
    f"With titles         : {stats[3]:,}"
)

print(
    f"With authors        : {stats[2]:,}"
)

print(
    f"With descriptions   : {stats[4]:,}"
)

print(
    f"With subjects       : {stats[5]:,}"
)

print(
    f"With ratings        : {stats[6]:,}"
)

print(
    f"With reading data   : {stats[7]:,}"
)

print(
    f"With covers         : {stats[8]:,}"
)


# ------------------------------------------------------------
# DUPLICATES
# ------------------------------------------------------------

print()
print("DUPLICATE WORK IDs")
print("-" * 70)

duplicates = con.execute(
    f"""
    SELECT work_id, COUNT(*)
    FROM read_parquet('{OUTPUT}')
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


# ------------------------------------------------------------
# FILE SIZE
# ------------------------------------------------------------

size_gb = OUTPUT.stat().st_size / (1024 ** 3)

elapsed = (time.time() - start) / 60

print()
print("=" * 70)
print("MASTER REBUILD COMPLETE")
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