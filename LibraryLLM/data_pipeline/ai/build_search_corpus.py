from pathlib import Path
import duckdb
import time


# ============================================================
# ASTRALIB - BUILD SEARCH CORPUS
# ============================================================

BASE_DIR = Path(r"D:\SDC\LibraryLLM")

INPUT = (
    BASE_DIR
    / "datasets"
    / "master"
    / "books_master.parquet"
)

OUTPUT_DIR = (
    BASE_DIR
    / "datasets"
    / "ai"
    / "search"
)

OUTPUT = OUTPUT_DIR / "search_corpus.parquet"

TEMP_DIR = BASE_DIR / "temp_duckdb"


start_time = time.time()

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)


print("=" * 70)
print("ASTRALIB - BUILD SEARCH CORPUS")
print("=" * 70)

print()
print(f"Input : {INPUT}")
print(f"Output: {OUTPUT}")
print()


# ============================================================
# CHECK INPUT
# ============================================================

if not INPUT.exists():
    raise FileNotFoundError(
        f"Master dataset not found:\n{INPUT}"
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
# INSPECT MASTER
# ============================================================

print("=" * 70)
print("CHECKING MASTER DATASET")
print("=" * 70)

total = con.execute(
    f"""
    SELECT COUNT(*)
    FROM read_parquet('{INPUT}')
    """
).fetchone()[0]

print(f"Total works: {total:,}")
print()


# ============================================================
# COUNT CANDIDATES
# ============================================================

print("=" * 70)
print("SELECTING SEARCH CANDIDATES")
print("=" * 70)

candidate_count = con.execute(
    f"""
    SELECT COUNT(*)
    FROM read_parquet('{INPUT}')
    WHERE
        title IS NOT NULL
        AND TRIM(title) <> ''

        AND (
            (authors IS NOT NULL AND TRIM(authors) <> '')
            OR
            (subjects IS NOT NULL AND TRIM(subjects) <> '')
            OR
            (description IS NOT NULL AND TRIM(description) <> '')
        )
    """
).fetchone()[0]

print(
    f"Search candidates: {candidate_count:,}"
)

percentage = (
    candidate_count / total * 100
    if total
    else 0
)

print(
    f"Percentage of master: {percentage:.2f}%"
)

print()


# ============================================================
# REMOVE OLD OUTPUT
# ============================================================

if OUTPUT.exists():

    print("Removing previous search corpus...")

    OUTPUT.unlink()

    print()


# ============================================================
# BUILD SEARCH CORPUS
# ============================================================

print("=" * 70)
print("BUILDING SEARCH CORPUS")
print("=" * 70)

print()
print("Creating search_text...")
print()
print("This may take several minutes.")
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

        CONCAT_WS(
            ' ',
            
            'Title:',
            NULLIF(TRIM(title), ''),

            'Authors:',
            NULLIF(TRIM(authors), ''),

            'Subjects:',
            NULLIF(TRIM(subjects), ''),

            'Description:',
            NULLIF(TRIM(description), ''),

            'First published:',
            NULLIF(TRIM(first_publish_date), '')
        ) AS search_text

    FROM read_parquet(
        '{INPUT}'
    )

    WHERE

        title IS NOT NULL

        AND TRIM(title) <> ''

        AND (

            (
                authors IS NOT NULL
                AND TRIM(authors) <> ''
            )

            OR

            (
                subjects IS NOT NULL
                AND TRIM(subjects) <> ''
            )

            OR

            (
                description IS NOT NULL
                AND TRIM(description) <> ''
            )

        )

)

TO '{OUTPUT}'

(
    FORMAT PARQUET,
    COMPRESSION ZSTD
)
"""


con.execute(query)


# ============================================================
# VERIFY OUTPUT
# ============================================================

print()
print("=" * 70)
print("VERIFYING SEARCH CORPUS")
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

with_search_text = con.execute(
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
        search_text
    FROM read_parquet('{OUTPUT}')
    LIMIT 5
    """
).fetchall()


for i, row in enumerate(samples, 1):

    print()
    print(f"--- RECORD {i} ---")

    print(f"Work ID : {row[0]}")
    print(f"Title   : {row[1]}")
    print(f"Authors : {row[2]}")
    print(f"Subjects: {row[3]}")

    print(
        f"Search text: {row[4][:500]}"
        if row[4]
        else "Search text: None"
    )


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
print("SEARCH CORPUS COMPLETE")
print("=" * 70)

print()
print(f"Master works          : {total:,}")
print(f"Search candidates     : {count:,}")
print(f"Unique work IDs       : {unique_count:,}")
print(f"With search text      : {with_search_text:,}")

print()
print(f"Output size           : {output_size:.2f} GB")

print()
print(f"Output:")
print(OUTPUT)

print()
print(f"Time                  : {elapsed:.2f} minutes")

print()
print("=" * 70)

con.close()