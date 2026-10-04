from pathlib import Path
import duckdb
import time


# ============================================================
# PATHS
# ============================================================

BASE = Path(
    r"D:\SDC\LibraryLLM\datasets\cleaned"
)

MASTER_DIR = Path(
    r"D:\SDC\LibraryLLM\datasets\master"
)

TEMP_DIR = Path(
    r"D:\SDC\LibraryLLM\temp_duckdb"
)

MASTER_DIR.mkdir(
    parents=True,
    exist_ok=True
)

TEMP_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT = MASTER_DIR / "books_master.parquet"


# ============================================================
# INPUT FILES
# ============================================================

WORKS = BASE / "works.parquet"
AUTHORS = BASE / "authors.parquet"
EDITIONS = BASE / "editions.parquet"

EDITION_WORK = BASE / "edition_work.parquet"
EDITION_AUTHOR = BASE / "edition_author.parquet"
EDITION_COVER = BASE / "edition_cover.parquet"

RATINGS = BASE / "ratings.parquet"
READING_LOGS = BASE / "reading_logs.parquet"

COVERS = BASE / "covers.parquet"


# ============================================================
# START
# ============================================================

start = time.time()

print("=" * 70)
print("ASTRALIB - OPTIMIZED MASTER DATASET")
print("=" * 70)

print()
print(f"Output : {OUTPUT}")
print(f"Temp   : {TEMP_DIR}")
print()
print("ONE ROW PER WORK")
print()


# ============================================================
# DUCKDB CONNECTION
# ============================================================

con = duckdb.connect(
    str(TEMP_DIR / "astralib.duckdb")
)


# ============================================================
# DUCKDB PERFORMANCE SETTINGS
# ============================================================

# Use a reasonable number of CPU threads.
con.execute(
    "SET threads = 4"
)

# Prevent excessive RAM usage.
con.execute(
    "SET memory_limit = '8GB'"
)

# Reduces memory overhead.
con.execute(
    "SET preserve_insertion_order = false"
)

# Where DuckDB stores temporary spill files.
con.execute(
    "SET temp_directory = "
    f"'{TEMP_DIR.as_posix()}'"
)

# NEVER allow the temporary directory to consume
# the entire D: drive.
con.execute(
    "SET max_temp_directory_size = '50GB'"
)

# ------------------------------------------------------------
# REAL DUCKDB PROGRESS BAR
# ------------------------------------------------------------

con.execute(
    "SET enable_progress_bar = true"
)

con.execute(
    "SET enable_progress_bar_print = true"
)

# Show progress after approximately 1 second.
con.execute(
    "SET progress_bar_time = 1000"
)


# ============================================================
# STAGE 1 - AUTHORS
# ============================================================

print()
print("=" * 70)
print("STAGE 1/6 - AUTHORS")
print("=" * 70)

print("Aggregating authors by work...")
print()

con.execute(
    f"""
    CREATE OR REPLACE TABLE work_authors AS

    SELECT

        ew.work_id,

        string_agg(
            DISTINCT a.name,
            ' | '
        ) AS authors

    FROM read_parquet(
        '{EDITION_WORK}'
    ) ew

    INNER JOIN read_parquet(
        '{EDITION_AUTHOR}'
    ) ea

        ON ew.edition_id =
           ea.edition_id

    INNER JOIN read_parquet(
        '{AUTHORS}'
    ) a

        ON ea.author_id =
           a.author_id

    WHERE
        a.name IS NOT NULL

        AND a.name != ''

    GROUP BY
        ew.work_id
    """
)

print()
print("✓ Authors complete")


# ============================================================
# STAGE 2 - EDITION SUMMARY
# ============================================================

print()
print("=" * 70)
print("STAGE 2/6 - EDITION SUMMARY")
print("=" * 70)

print(
    "Aggregating 56.6M editions..."
)

print(
    "This is expected to be the longest stage."
)

print()

con.execute(
    f"""
    CREATE OR REPLACE TABLE work_editions AS

    SELECT

        ew.work_id,

        COUNT(
            DISTINCT e.edition_id
        ) AS edition_count,

        MIN(
            NULLIF(
                e.publish_date,
                ''
            )
        ) AS earliest_publish_date,

        MAX(
            NULLIF(
                e.publish_date,
                ''
            )
        ) AS latest_publish_date,

        MAX(
            e.number_of_pages
        ) AS max_pages,

        MAX(
            NULLIF(
                e.publishers,
                ''
            )
        ) AS publisher,

        MAX(
            NULLIF(
                e.physical_format,
                ''
            )
        ) AS physical_format,

        MAX(
            NULLIF(
                e.isbn10,
                ''
            )
        ) AS isbn10,

        MAX(
            NULLIF(
                e.isbn13,
                ''
            )
        ) AS isbn13

    FROM read_parquet(
        '{EDITION_WORK}'
    ) ew

    INNER JOIN read_parquet(
        '{EDITIONS}'
    ) e

        ON ew.edition_id =
           e.edition_id

    GROUP BY
        ew.work_id
    """
)

print()
print("✓ Edition summary complete")


# ============================================================
# STAGE 3 - RATINGS
# ============================================================

print()
print("=" * 70)
print("STAGE 3/6 - RATINGS")
print("=" * 70)

print(
    "Aggregating ratings..."
)

print()

con.execute(
    f"""
    CREATE OR REPLACE TABLE work_ratings AS

    SELECT

        work_id,

        ROUND(
            AVG(rating),
            3
        ) AS average_rating,

        COUNT(*) AS rating_count,

        COUNT(*) FILTER (
            WHERE rating = 5
        ) AS five_star_count,

        COUNT(*) FILTER (
            WHERE rating = 4
        ) AS four_star_count,

        COUNT(*) FILTER (
            WHERE rating = 3
        ) AS three_star_count,

        COUNT(*) FILTER (
            WHERE rating = 2
        ) AS two_star_count,

        COUNT(*) FILTER (
            WHERE rating = 1
        ) AS one_star_count

    FROM read_parquet(
        '{RATINGS}'
    )

    GROUP BY
        work_id
    """
)

print()
print("✓ Ratings complete")


# ============================================================
# STAGE 4 - READING LOGS
# ============================================================

print()
print("=" * 70)
print("STAGE 4/6 - READING LOGS")
print("=" * 70)

print(
    "Aggregating reading activity..."
)

print()

con.execute(
    f"""
    CREATE OR REPLACE TABLE work_reading AS

    SELECT

        work_id,

        COUNT(*) AS reading_log_count,

        COUNT(*) FILTER (
            WHERE shelf =
                  'Want to Read'
        ) AS want_to_read_count,

        COUNT(*) FILTER (
            WHERE shelf =
                  'Already Read'
        ) AS already_read_count,

        COUNT(*) FILTER (
            WHERE shelf =
                  'Currently Reading'
        ) AS currently_reading_count,

        COUNT(*) FILTER (
            WHERE shelf =
                  'Stopped Reading'
        ) AS stopped_reading_count

    FROM read_parquet(
        '{READING_LOGS}'
    )

    GROUP BY
        work_id
    """
)

print()
print("✓ Reading logs complete")


# ============================================================
# STAGE 5 - COVERS
# ============================================================

print()
print("=" * 70)
print("STAGE 5/6 - COVERS")
print("=" * 70)

print(
    "Selecting representative covers..."
)

print()

con.execute(
    f"""
    CREATE OR REPLACE TABLE work_covers AS

    SELECT

        ew.work_id,

        arg_max(
            ec.cover_id,

            CASE

                WHEN
                    c.width IS NOT NULL

                    AND

                    c.height IS NOT NULL

                THEN
                    c.width *
                    c.height

                ELSE
                    0

            END

        ) AS cover_id

    FROM read_parquet(
        '{EDITION_WORK}'
    ) ew

    INNER JOIN read_parquet(
        '{EDITION_COVER}'
    ) ec

        ON ew.edition_id =
           ec.edition_id

    LEFT JOIN read_parquet(
        '{COVERS}'
    ) c

        ON ec.cover_id =
           c.cover_id

    GROUP BY
        ew.work_id
    """
)

print()
print("✓ Covers complete")


# ============================================================
# STAGE 6 - FINAL MASTER DATASET
# ============================================================

print()
print("=" * 70)
print("STAGE 6/6 - WRITING MASTER DATASET")
print("=" * 70)

print()
print(
    "Joining all datasets..."
)

print(
    "Writing books_master.parquet..."
)

print(
    "DuckDB progress bar will appear below."
)

print()


# Remove an existing incomplete output.
if OUTPUT.exists():

    OUTPUT.unlink()


con.execute(
    f"""
    COPY (

        SELECT

            -- =================================================
            -- CORE WORK INFORMATION
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
            -- EDITION INFORMATION
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
            -- READING ACTIVITY
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


        -- =====================================================
        -- AUTHORS
        -- =====================================================

        LEFT JOIN work_authors wa

            ON w.work_id =
               wa.work_id


        -- =====================================================
        -- EDITIONS
        -- =====================================================

        LEFT JOIN work_editions we

            ON w.work_id =
               we.work_id


        -- =====================================================
        -- RATINGS
        -- =====================================================

        LEFT JOIN work_ratings wr

            ON w.work_id =
               wr.work_id


        -- =====================================================
        -- READING LOGS
        -- =====================================================

        LEFT JOIN work_reading rr

            ON w.work_id =
               rr.work_id


        -- =====================================================
        -- COVERS
        -- =====================================================

        LEFT JOIN work_covers wc

            ON w.work_id =
               wc.work_id

    )

    TO '{OUTPUT}'

    (
        FORMAT PARQUET,

        COMPRESSION ZSTD
    )
    """
)


# ============================================================
# VALIDATION
# ============================================================

print()
print("=" * 70)
print("VALIDATION")
print("=" * 70)

print()
print(
    "Checking master dataset..."
)

stats = con.execute(
    f"""
    SELECT

        COUNT(*) AS total,

        COUNT(
            DISTINCT work_id
        ) AS unique_work_ids,

        COUNT(*) FILTER (
            WHERE
                title IS NOT NULL

                AND

                title != ''
        ) AS with_title,

        COUNT(*) FILTER (
            WHERE
                authors IS NOT NULL

                AND

                authors != ''
        ) AS with_authors,

        COUNT(*) FILTER (
            WHERE
                description IS NOT NULL

                AND

                description != ''
        ) AS with_description,

        COUNT(*) FILTER (
            WHERE
                average_rating > 0
        ) AS with_ratings,

        COUNT(*) FILTER (
            WHERE
                reading_log_count > 0
        ) AS with_reading_activity,

        COUNT(*) FILTER (
            WHERE
                cover_id IS NOT NULL
        ) AS with_covers

    FROM read_parquet(
        '{OUTPUT}'
    )
    """
).fetchone()


print()
print("MASTER DATASET STATISTICS")
print("-" * 70)

print(
    f"Total works         : "
    f"{stats[0]:,}"
)

print(
    f"Unique work IDs     : "
    f"{stats[1]:,}"
)

print(
    f"With title          : "
    f"{stats[2]:,}"
)

print(
    f"With authors        : "
    f"{stats[3]:,}"
)

print(
    f"With description    : "
    f"{stats[4]:,}"
)

print(
    f"With ratings        : "
    f"{stats[5]:,}"
)

print(
    f"With reading data   : "
    f"{stats[6]:,}"
)

print(
    f"With covers         : "
    f"{stats[7]:,}"
)


# ============================================================
# DUPLICATE WORK CHECK
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

    GROUP BY
        work_id

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
# OUTPUT FILE
# ============================================================

output_size = (
    OUTPUT.stat().st_size
    / (1024 ** 3)
)

elapsed = (
    time.time() - start
) / 60


print()
print("=" * 70)
print("MASTER DATASET COMPLETE")
print("=" * 70)

print()
print(
    f"File size : "
    f"{output_size:.2f} GB"
)

print(
    f"Location  : "
    f"{OUTPUT}"
)

print(
    f"Time      : "
    f"{elapsed:.2f} minutes"
)


# ============================================================
# CLOSE
# ============================================================

con.close()


print()
print("=" * 70)
print("ASTRALIB MASTER BUILD FINISHED")
print("=" * 70)