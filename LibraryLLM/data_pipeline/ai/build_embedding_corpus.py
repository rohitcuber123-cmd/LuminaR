from pathlib import Path
import duckdb
import time


# ============================================================
# ASTRALIB - BUILD EMBEDDING CORPUS
# ============================================================

BASE_DIR = Path(r"D:\SDC\LibraryLLM")

INPUT = (
    BASE_DIR
    / "datasets"
    / "ai"
    / "search"
    / "search_corpus.parquet"
)

OUTPUT_DIR = (
    BASE_DIR
    / "datasets"
    / "ai"
    / "embeddings"
)

OUTPUT = OUTPUT_DIR / "embedding_corpus.parquet"

TEMP_DIR = BASE_DIR / "temp_duckdb"


# ============================================================
# SETTINGS
# ============================================================

# Target size.
# We deliberately start with 5 million rather than embedding
# all 40 million books.
TARGET_BOOKS = 5_000_000


start_time = time.time()

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)


print("=" * 70)
print("ASTRALIB - BUILD EMBEDDING CORPUS")
print("=" * 70)

print()
print(f"Input : {INPUT}")
print(f"Output: {OUTPUT}")
print(f"Target: {TARGET_BOOKS:,} books")
print()


# ============================================================
# CHECK INPUT
# ============================================================

if not INPUT.exists():
    raise FileNotFoundError(
        f"Search corpus not found:\n{INPUT}"
    )

input_size = INPUT.stat().st_size / (1024 ** 3)

print(f"Input size: {input_size:.2f} GB")
print()


# ============================================================
# DUCKDB
# ============================================================

con = duckdb.connect(
    str(TEMP_DIR / "astralib.duckdb")
)

con.execute("SET threads = 4")
con.execute("SET memory_limit = '8GB'")
con.execute("SET preserve_insertion_order = false")

con.execute(
    f"SET temp_directory = '{TEMP_DIR.as_posix()}'"
)

con.execute(
    "SET max_temp_directory_size = '100GB'"
)

con.execute("SET enable_progress_bar = true")
con.execute("SET enable_progress_bar_print = true")
con.execute("SET progress_bar_time = 1000")


# ============================================================
# COUNT INPUT
# ============================================================

print("=" * 70)
print("INPUT DATASET")
print("=" * 70)

total = con.execute(
    f"""
    SELECT COUNT(*)
    FROM read_parquet('{INPUT}')
    """
).fetchone()[0]

print(f"Total search records: {total:,}")
print()


# ============================================================
# COUNT HIGH-QUALITY CANDIDATES
# ============================================================

print("=" * 70)
print("ANALYZING BOOK QUALITY")
print("=" * 70)

quality_count = con.execute(
    f"""
    SELECT COUNT(*)
    FROM read_parquet('{INPUT}')
    WHERE
        title IS NOT NULL
        AND TRIM(title) <> ''

        AND (
            (
                description IS NOT NULL
                AND LENGTH(TRIM(description)) >= 50
            )

            OR

            (
                subjects IS NOT NULL
                AND LENGTH(TRIM(subjects)) >= 10
            )

            OR

            (
                authors IS NOT NULL
                AND TRIM(authors) <> ''
            )

            OR

            rating_count > 0

            OR

            reading_log_count > 0
        )
    """
).fetchone()[0]

print(
    f"Quality candidates: {quality_count:,}"
)

print()


# ============================================================
# SHOW QUALITY DISTRIBUTION
# ============================================================

print("=" * 70)
print("QUALITY DISTRIBUTION")
print("=" * 70)

distribution = con.execute(
    f"""
    SELECT

        COUNT(*) FILTER (
            WHERE description IS NOT NULL
            AND LENGTH(TRIM(description)) >= 50
        ) AS descriptions,

        COUNT(*) FILTER (
            WHERE subjects IS NOT NULL
            AND LENGTH(TRIM(subjects)) >= 10
        ) AS subjects,

        COUNT(*) FILTER (
            WHERE authors IS NOT NULL
            AND TRIM(authors) <> ''
        ) AS authors,

        COUNT(*) FILTER (
            WHERE rating_count > 0
        ) AS rated,

        COUNT(*) FILTER (
            WHERE reading_log_count > 0
        ) AS reading_data

    FROM read_parquet('{INPUT}')
    """
).fetchone()

print(f"With useful descriptions : {distribution[0]:,}")
print(f"With useful subjects      : {distribution[1]:,}")
print(f"With authors              : {distribution[2]:,}")
print(f"With ratings              : {distribution[3]:,}")
print(f"With reading data         : {distribution[4]:,}")

print()


# ============================================================
# REMOVE OLD OUTPUT
# ============================================================

if OUTPUT.exists():

    print("Removing previous embedding corpus...")

    OUTPUT.unlink()

    print()


# ============================================================
# BUILD EMBEDDING CORPUS
# ============================================================

print("=" * 70)
print("BUILDING EMBEDDING CORPUS")
print("=" * 70)

print()
print(
    f"Selecting up to {TARGET_BOOKS:,} high-quality books..."
)

print()


query = f"""
COPY (

    SELECT

        work_id,

        title,

        authors,

        subjects,

        description,

        first_publish_date,

        edition_count,

        average_rating,

        rating_count,

        reading_log_count,

        cover_id,

        search_text

    FROM read_parquet('{INPUT}')

    WHERE

        title IS NOT NULL
        AND TRIM(title) <> ''

        AND (

            (
                description IS NOT NULL
                AND LENGTH(TRIM(description)) >= 50
            )

            OR

            (
                subjects IS NOT NULL
                AND LENGTH(TRIM(subjects)) >= 10
            )

            OR

            (
                authors IS NOT NULL
                AND TRIM(authors) <> ''
            )

            OR

            rating_count > 0

            OR

            reading_log_count > 0
        )

    ORDER BY

        (
            CASE
                WHEN description IS NOT NULL
                     AND LENGTH(TRIM(description)) >= 50
                THEN 5
                ELSE 0
            END

            +

            CASE
                WHEN subjects IS NOT NULL
                     AND LENGTH(TRIM(subjects)) >= 10
                THEN 3
                ELSE 0
            END

            +

            CASE
                WHEN authors IS NOT NULL
                     AND TRIM(authors) <> ''
                THEN 2
                ELSE 0
            END

            +

            CASE
                WHEN rating_count > 0
                THEN 2
                ELSE 0
            END

            +

            CASE
                WHEN reading_log_count > 0
                THEN 2
                ELSE 0
            END

        ) DESC,

        rating_count DESC NULLS LAST,

        reading_log_count DESC NULLS LAST,

        edition_count DESC NULLS LAST,

        work_id

    LIMIT {TARGET_BOOKS}

)

TO '{OUTPUT}'

(
    FORMAT PARQUET,
    COMPRESSION ZSTD
)
"""


con.execute(query)


# ============================================================
# VERIFY
# ============================================================

print()
print("=" * 70)
print("VERIFYING EMBEDDING CORPUS")
print("=" * 70)

count = con.execute(
    f"""
    SELECT COUNT(*)
    FROM read_parquet('{OUTPUT}')
    """
).fetchone()[0]

unique_count = con.execute(
    f"""
    SELECT COUNT(DISTINCT work_id)
    FROM read_parquet('{OUTPUT}')
    """
).fetchone()[0]

with_text = con.execute(
    f"""
    SELECT COUNT(*)
    FROM read_parquet('{OUTPUT}')
    WHERE
        search_text IS NOT NULL
        AND TRIM(search_text) <> ''
    """
).fetchone()[0]


# ============================================================
# SAMPLE
# ============================================================

print()
print("=" * 70)
print("SAMPLE RECORDS")
print("=" * 70)

samples = con.execute(
    f"""
    SELECT
        work_id,
        title,
        authors,
        subjects,
        description,
        average_rating,
        rating_count,
        reading_log_count
    FROM read_parquet('{OUTPUT}')
    LIMIT 10
    """
).fetchall()


for i, row in enumerate(samples, 1):

    print()
    print(f"--- RECORD {i} ---")

    print(f"Work ID       : {row[0]}")
    print(f"Title         : {row[1]}")
    print(f"Authors       : {row[2]}")
    print(f"Subjects      : {row[3]}")

    if row[4]:
        description = row[4].replace("\n", " ")
        print(
            f"Description   : {description[:200]}"
        )
    else:
        print("Description   : None")

    print(f"Rating        : {row[5]}")
    print(f"Rating count  : {row[6]}")
    print(f"Reading logs  : {row[7]}")


# ============================================================
# FILE SIZE
# ============================================================

output_size = OUTPUT.stat().st_size / (1024 ** 3)

elapsed = (time.time() - start_time) / 60


# ============================================================
# FINAL REPORT
# ============================================================

print()
print("=" * 70)
print("EMBEDDING CORPUS COMPLETE")
print("=" * 70)

print()
print(f"Input records        : {total:,}")
print(f"Quality candidates    : {quality_count:,}")
print(f"Embedding records    : {count:,}")
print(f"Unique work IDs      : {unique_count:,}")
print(f"With search text     : {with_text:,}")

print()
print(f"Output size          : {output_size:.2f} GB")

print()
print("Output:")
print(OUTPUT)

print()
print(f"Time                 : {elapsed:.2f} minutes")

print()
print("=" * 70)

con.close()