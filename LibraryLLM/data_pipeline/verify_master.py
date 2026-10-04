from pathlib import Path
import duckdb


# ============================================================
# PATH
# ============================================================

MASTER = Path(
    r"D:\SDC\LibraryLLM\datasets\master\books_master.parquet"
)


# ============================================================
# START
# ============================================================

print("=" * 70)
print("ASTRALIB - VERIFY MASTER DATASET")
print("=" * 70)

print()
print(f"File: {MASTER}")


if not MASTER.exists():
    print("\nERROR: Master dataset not found.")
    raise SystemExit(1)


size_gb = MASTER.stat().st_size / (1024 ** 3)

print(f"Size: {size_gb:.2f} GB")


# ============================================================
# DUCKDB
# ============================================================

con = duckdb.connect()

con.execute("SET threads = 4")
con.execute("SET enable_progress_bar = true")
con.execute("SET enable_progress_bar_print = true")
con.execute("SET progress_bar_time = 1000")


# ============================================================
# SCHEMA
# ============================================================

print()
print("=" * 70)
print("1. SCHEMA")
print("=" * 70)

schema = con.execute(
    f"""
    DESCRIBE
    SELECT *
    FROM read_parquet('{MASTER}')
    """
).fetchall()


print()

for row in schema:

    column_name = row[0]
    data_type = row[1]

    print(
        f"{column_name:<30} {data_type}"
    )


# ============================================================
# BASIC STATISTICS
# ============================================================

print()
print("=" * 70)
print("2. BASIC STATISTICS")
print("=" * 70)

stats = con.execute(
    f"""
    SELECT

        COUNT(*) AS total,

        COUNT(
            DISTINCT work_id
        ) AS unique_work_ids,

        COUNT(*) FILTER (
            WHERE title IS NOT NULL
        ) AS titles,

        COUNT(*) FILTER (
            WHERE authors IS NOT NULL
        ) AS authors,

        COUNT(*) FILTER (
            WHERE description IS NOT NULL
        ) AS descriptions,

        COUNT(*) FILTER (
            WHERE subjects IS NOT NULL
        ) AS subjects,

        COUNT(*) FILTER (
            WHERE average_rating > 0
        ) AS rated,

        COUNT(*) FILTER (
            WHERE reading_log_count > 0
        ) AS reading,

        COUNT(*) FILTER (
            WHERE cover_id IS NOT NULL
        ) AS covers

    FROM read_parquet('{MASTER}')
    """
).fetchone()


print()
print(
    f"Total works       : {stats[0]:,}"
)

print(
    f"Unique work IDs   : {stats[1]:,}"
)

print(
    f"With titles       : {stats[2]:,}"
)

print(
    f"With authors      : {stats[3]:,}"
)

print(
    f"With descriptions : {stats[4]:,}"
)

print(
    f"With subjects     : {stats[5]:,}"
)

print(
    f"With ratings      : {stats[6]:,}"
)

print(
    f"With reading data : {stats[7]:,}"
)

print(
    f"With covers       : {stats[8]:,}"
)


# ============================================================
# MISSING VALUES
# ============================================================

print()
print("=" * 70)
print("3. MISSING VALUE ANALYSIS")
print("=" * 70)


missing = con.execute(
    f"""
    SELECT

        COUNT(*) FILTER (
            WHERE title IS NULL
               OR title = ''
        ) AS missing_title,

        COUNT(*) FILTER (
            WHERE authors IS NULL
               OR authors = ''
        ) AS missing_authors,

        COUNT(*) FILTER (
            WHERE description IS NULL
               OR description = ''
        ) AS missing_description,

        COUNT(*) FILTER (
            WHERE subjects IS NULL
               OR subjects = ''
        ) AS missing_subjects,

        COUNT(*) FILTER (
            WHERE first_publish_date IS NULL
               OR first_publish_date = ''
        ) AS missing_publish_date,

        COUNT(*) FILTER (
            WHERE edition_count = 0
        ) AS no_editions,

        COUNT(*) FILTER (
            WHERE publisher IS NULL
               OR publisher = ''
        ) AS missing_publisher,

        COUNT(*) FILTER (
            WHERE isbn10 IS NULL
               OR isbn10 = ''
        ) AS missing_isbn10,

        COUNT(*) FILTER (
            WHERE isbn13 IS NULL
               OR isbn13 = ''
        ) AS missing_isbn13,

        COUNT(*) FILTER (
            WHERE cover_id IS NULL
        ) AS missing_cover

    FROM read_parquet('{MASTER}')
    """
).fetchone()


labels = [
    "Missing title",
    "Missing authors",
    "Missing description",
    "Missing subjects",
    "No editions",
    "Missing publisher",
    "Missing ISBN-10",
    "Missing ISBN-13",
    "Missing cover",
]


for label, value in zip(labels, missing):

    print(
        f"{label:<25}: {value:,}"
    )


# ============================================================
# RATING VALIDATION
# ============================================================

print()
print("=" * 70)
print("4. RATING VALIDATION")
print("=" * 70)


rating_stats = con.execute(
    f"""
    SELECT

        MIN(average_rating),

        MAX(average_rating),

        AVG(
            average_rating
        ),

        SUM(
            rating_count
        ),

        SUM(
            five_star_count
        ),

        SUM(
            four_star_count
        ),

        SUM(
            three_star_count
        ),

        SUM(
            two_star_count
        ),

        SUM(
            one_star_count
        )

    FROM read_parquet('{MASTER}')
    """
).fetchone()


print(
    f"Minimum average rating : {rating_stats[0]}"
)

print(
    f"Maximum average rating : {rating_stats[1]}"
)

print(
    f"Average of averages    : {rating_stats[2]:.3f}"
)

print(
    f"Total rating records   : {rating_stats[3]:,}"
)

print(
    f"5-star records         : {rating_stats[4]:,}"
)

print(
    f"4-star records         : {rating_stats[5]:,}"
)

print(
    f"3-star records         : {rating_stats[6]:,}"
)

print(
    f"2-star records         : {rating_stats[7]:,}"
)

print(
    f"1-star records         : {rating_stats[8]:,}"
)


invalid_ratings = con.execute(
    f"""
    SELECT COUNT(*)

    FROM read_parquet('{MASTER}')

    WHERE
        average_rating < 0

        OR

        average_rating > 5
    """
).fetchone()[0]


print()
print(
    f"Invalid average ratings : {invalid_ratings:,}"
)


# ============================================================
# EDITION VALIDATION
# ============================================================

print()
print("=" * 70)
print("5. EDITION VALIDATION")
print("=" * 70)


edition_stats = con.execute(
    f"""
    SELECT

        MIN(edition_count),

        MAX(edition_count),

        AVG(edition_count),

        SUM(edition_count),

        COUNT(*) FILTER (
            WHERE edition_count > 0
        )

    FROM read_parquet('{MASTER}')
    """
).fetchone()


print(
    f"Minimum editions/work : {edition_stats[0]}"
)

print(
    f"Maximum editions/work : {edition_stats[1]:,}"
)

print(
    f"Average editions/work : {edition_stats[2]:.2f}"
)

print(
    f"Total edition links   : {edition_stats[3]:,}"
)

print(
    f"Works with editions   : {edition_stats[4]:,}"
)


# ============================================================
# READING LOG VALIDATION
# ============================================================

print()
print("=" * 70)
print("6. READING ACTIVITY")
print("=" * 70)


reading = con.execute(
    f"""
    SELECT

        SUM(reading_log_count),

        SUM(want_to_read_count),

        SUM(already_read_count),

        SUM(currently_reading_count),

        SUM(stopped_reading_count)

    FROM read_parquet('{MASTER}')
    """
).fetchone()


print(
    f"Total reading logs       : {reading[0]:,}"
)

print(
    f"Want to Read             : {reading[1]:,}"
)

print(
    f"Already Read             : {reading[2]:,}"
)

print(
    f"Currently Reading        : {reading[3]:,}"
)

print(
    f"Stopped Reading          : {reading[4]:,}"
)


# ============================================================
# COVER VALIDATION
# ============================================================

print()
print("=" * 70)
print("7. COVER VALIDATION")
print("=" * 70)


cover_stats = con.execute(
    f"""
    SELECT

        COUNT(*)
            FILTER (
                WHERE cover_id IS NOT NULL
            ),

        COUNT(
            DISTINCT cover_id
        )

    FROM read_parquet('{MASTER}')
    """
).fetchone()


print(
    f"Works with covers : {cover_stats[0]:,}"
)

print(
    f"Unique cover IDs  : {cover_stats[1]:,}"
)


# ============================================================
# DUPLICATE WORK IDS
# ============================================================

print()
print("=" * 70)
print("8. DUPLICATE WORK IDs")
print("=" * 70)


duplicates = con.execute(
    f"""
    SELECT

        work_id,

        COUNT(*) AS count

    FROM read_parquet('{MASTER}')

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
# SUSPICIOUS RECORDS
# ============================================================

print()
print("=" * 70)
print("9. SUSPICIOUS RECORDS")
print("=" * 70)


suspicious = con.execute(
    f"""
    SELECT

        work_id,
        title,
        edition_count,
        average_rating,
        rating_count,
        reading_log_count

    FROM read_parquet('{MASTER}')

    WHERE

        title IS NULL

        OR title = ''

        OR edition_count < 0

        OR rating_count < 0

        OR reading_log_count < 0

        OR average_rating < 0

        OR average_rating > 5

    LIMIT 20
    """
).fetchall()


if suspicious:

    print(
        f"Found {len(suspicious)} suspicious records:"
    )

    for row in suspicious:
        print(row)

else:

    print(
        "No suspicious records found."
    )


# ============================================================
# SAMPLE RECORDS
# ============================================================

print()
print("=" * 70)
print("10. SAMPLE MASTER RECORDS")
print("=" * 70)


samples = con.execute(
    f"""
    SELECT

        work_id,
        title,
        authors,
        subjects,
        edition_count,
        average_rating,
        rating_count,
        reading_log_count,
        cover_id

    FROM read_parquet('{MASTER}')

    WHERE
        title IS NOT NULL

    ORDER BY work_id

    LIMIT 10
    """
).fetchall()


for row in samples:

    print()
    print("-" * 70)

    print(
        f"Work ID       : {row[0]}"
    )

    print(
        f"Title         : {row[1]}"
    )

    print(
        f"Authors       : {row[2]}"
    )

    print(
        f"Subjects      : {row[3]}"
    )

    print(
        f"Editions      : {row[4]}"
    )

    print(
        f"Rating        : {row[5]}"
    )

    print(
        f"Rating count  : {row[6]}"
    )

    print(
        f"Reading logs  : {row[7]}"
    )

    print(
        f"Cover ID      : {row[8]}"
    )


# ============================================================
# AI DATASET COVERAGE
# ============================================================

print()
print("=" * 70)
print("11. AI SEARCH DATASET COVERAGE")
print("=" * 70)


ai_stats = con.execute(
    f"""
    SELECT

        COUNT(*)
        FILTER (
            WHERE
                title IS NOT NULL
                AND title != ''
        ) AS title_only,

        COUNT(*)
        FILTER (
            WHERE
                title IS NOT NULL
                AND title != ''

                AND

                (
                    authors IS NOT NULL
                    AND authors != ''
                )
        ) AS title_author,

        COUNT(*)
        FILTER (
            WHERE
                title IS NOT NULL
                AND title != ''

                AND

                (
                    description IS NOT NULL
                    AND description != ''
                )
        ) AS title_description,

        COUNT(*)
        FILTER (
            WHERE
                title IS NOT NULL
                AND title != ''

                AND

                (
                    (
                        description IS NOT NULL
                        AND description != ''
                    )

                    OR

                    (
                        subjects IS NOT NULL
                        AND subjects != ''
                    )
                )
        ) AS semantic_candidates

    FROM read_parquet('{MASTER}')
    """
).fetchone()


print(
    f"Books with title              : "
    f"{ai_stats[0]:,}"
)

print(
    f"Books with title + author     : "
    f"{ai_stats[1]:,}"
)

print(
    f"Books with title + description: "
    f"{ai_stats[2]:,}"
)

print(
    f"Semantic search candidates    : "
    f"{ai_stats[3]:,}"
)


# ============================================================
# COMPLETE
# ============================================================

con.close()

print()
print("=" * 70)
print("MASTER VERIFICATION COMPLETE")
print("=" * 70)