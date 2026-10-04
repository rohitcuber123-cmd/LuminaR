from pathlib import Path
import duckdb


BASE = Path(
    r"D:\SDC\LibraryLLM\datasets\cleaned"
)

WORKS = BASE / "works.parquet"
RATINGS = BASE / "ratings.parquet"
READING = BASE / "reading_logs.parquet"

MASTER = Path(
    r"D:\SDC\LibraryLLM\datasets\master\books_master.parquet"
)


con = duckdb.connect()

con.execute("SET threads = 4")


print("=" * 70)
print("ASTRALIB - MASTER INTEGRITY CHECK")
print("=" * 70)


# ============================================================
# RATINGS
# ============================================================

print()
print("=" * 70)
print("1. RATING → WORK MATCHING")
print("=" * 70)

rating_result = con.execute(
    f"""
    SELECT

        COUNT(*) AS total_ratings,

        COUNT(*) FILTER (
            WHERE w.work_id IS NOT NULL
        ) AS matched_ratings,

        COUNT(*) FILTER (
            WHERE w.work_id IS NULL
        ) AS orphan_ratings,

        COUNT(
            DISTINCT r.work_id
        ) AS rating_works,

        COUNT(
            DISTINCT r.work_id
        ) FILTER (
            WHERE w.work_id IS NOT NULL
        ) AS matched_rating_works

    FROM read_parquet('{RATINGS}') r

    LEFT JOIN read_parquet('{WORKS}') w

        ON r.work_id =
           w.work_id
    """
).fetchone()


print(
    f"Total ratings          : {rating_result[0]:,}"
)

print(
    f"Matched ratings        : {rating_result[1]:,}"
)

print(
    f"Orphan ratings         : {rating_result[2]:,}"
)

print(
    f"Unique rated works     : {rating_result[3]:,}"
)

print(
    f"Matched rated works    : {rating_result[4]:,}"
)


# ============================================================
# READING LOGS
# ============================================================

print()
print("=" * 70)
print("2. READING LOG → WORK MATCHING")
print("=" * 70)


reading_result = con.execute(
    f"""
    SELECT

        COUNT(*) AS total_logs,

        COUNT(*) FILTER (
            WHERE w.work_id IS NOT NULL
        ) AS matched_logs,

        COUNT(*) FILTER (
            WHERE w.work_id IS NULL
        ) AS orphan_logs,

        COUNT(
            DISTINCT r.work_id
        ) AS reading_works,

        COUNT(
            DISTINCT r.work_id
        ) FILTER (
            WHERE w.work_id IS NOT NULL
        ) AS matched_reading_works

    FROM read_parquet('{READING}') r

    LEFT JOIN read_parquet('{WORKS}') w

        ON r.work_id =
           w.work_id
    """
).fetchone()


print(
    f"Total reading logs       : {reading_result[0]:,}"
)

print(
    f"Matched reading logs     : {reading_result[1]:,}"
)

print(
    f"Orphan reading logs      : {reading_result[2]:,}"
)

print(
    f"Unique reading works     : {reading_result[3]:,}"
)

print(
    f"Matched reading works    : {reading_result[4]:,}"
)


# ============================================================
# ORPHAN RATING SAMPLE
# ============================================================

print()
print("=" * 70)
print("3. SAMPLE ORPHAN RATINGS")
print("=" * 70)


orphans = con.execute(
    f"""
    SELECT

        r.work_id,
        r.edition_id,
        r.rating,
        r.date

    FROM read_parquet('{RATINGS}') r

    ANTI JOIN read_parquet('{WORKS}') w

        ON r.work_id =
           w.work_id

    LIMIT 20
    """
).fetchall()


if orphans:

    for row in orphans:
        print(row)

else:

    print("None")


# ============================================================
# ORPHAN READING LOG SAMPLE
# ============================================================

print()
print("=" * 70)
print("4. SAMPLE ORPHAN READING LOGS")
print("=" * 70)


orphans = con.execute(
    f"""
    SELECT

        r.work_id,
        r.edition_id,
        r.shelf,
        r.date

    FROM read_parquet('{READING}') r

    ANTI JOIN read_parquet('{WORKS}') w

        ON r.work_id =
           w.work_id

    LIMIT 20
    """
).fetchall()


if orphans:

    for row in orphans:
        print(row)

else:

    print("None")


# ============================================================
# AUTHOR COVERAGE FROM WORK DATA
# ============================================================

print()
print("=" * 70)
print("5. WORK AUTHOR COVERAGE")
print("=" * 70)


author_stats = con.execute(
    f"""
    SELECT

        COUNT(*) AS total,

        COUNT(*) FILTER (
            WHERE author_ids IS NOT NULL
              AND author_ids != ''
        ) AS with_author_ids

    FROM read_parquet('{WORKS}')
    """
).fetchone()


print(
    f"Total works             : {author_stats[0]:,}"
)

print(
    f"Works with author IDs   : {author_stats[1]:,}"
)


# ============================================================
# MASTER AUTHOR COVERAGE
# ============================================================

master_author = con.execute(
    f"""
    SELECT

        COUNT(*) FILTER (
            WHERE authors IS NOT NULL
              AND authors != ''
        )

    FROM read_parquet('{MASTER}')
    """
).fetchone()[0]


print(
    f"Master with authors     : {master_author:,}"
)

print(
    f"Potential author gap    : "
    f"{author_stats[1] - master_author:,}"
)


# ============================================================
# FINISH
# ============================================================

con.close()

print()
print("=" * 70)
print("INTEGRITY CHECK COMPLETE")
print("=" * 70)