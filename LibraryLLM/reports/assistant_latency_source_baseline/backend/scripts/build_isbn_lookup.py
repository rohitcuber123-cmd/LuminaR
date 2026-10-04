import os
import duckdb


MASTER = r"D:\SDC\LibraryLLM\datasets\master\books_master.parquet"
SQLITE_DB = r"D:\SDC\LibraryLLM\datasets\library.db"
OUTPUT_DB = r"D:\SDC\LibraryLLM\datasets\ai\mappings\isbn_lookup.duckdb"


def main():

    os.makedirs(
        os.path.dirname(OUTPUT_DB),
        exist_ok=True
    )

    print("=" * 70)
    print("BUILDING ISBN LOOKUP")
    print("=" * 70)

    con = duckdb.connect(OUTPUT_DB)

    # Enable SQLite access
    con.execute("INSTALL sqlite")
    con.execute("LOAD sqlite")

    print("\nReading exact 5M catalogue IDs from SQLite...")

    catalogue_count = con.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_scan(?, 'books')
        """,
        [SQLITE_DB]
    ).fetchone()[0]

    print("Catalogue works:", catalogue_count)

    if catalogue_count != 5_000_000:
        raise RuntimeError(
            f"Expected 5,000,000 catalogue works, "
            f"found {catalogue_count}"
        )

    # ---------------------------------------------------------
    # ISBN-13
    # ---------------------------------------------------------

    print("\nBuilding ISBN-13 mapping...")

    con.execute(
        """
        CREATE OR REPLACE TABLE isbn_lookup AS

        SELECT DISTINCT
            regexp_replace(
                trim(isbn),
                '[^0-9Xx]',
                '',
                'g'
            ) AS isbn,

            m.work_id,
            m.title,
            m.authors

        FROM read_parquet(?) m

        INNER JOIN sqlite_scan(?, 'books') b
            ON m.work_id = b.work_id

        CROSS JOIN LATERAL
            unnest(
                string_split(
                    coalesce(m.isbn13, ''),
                    '|'
                )
            ) AS t(isbn)

        WHERE trim(isbn) <> ''
        """,
        [MASTER, SQLITE_DB]
    )

    # ---------------------------------------------------------
    # ISBN-10
    # ---------------------------------------------------------

    print("Adding ISBN-10 mappings...")

    con.execute(
        """
        INSERT INTO isbn_lookup

        SELECT DISTINCT
            regexp_replace(
                trim(isbn),
                '[^0-9Xx]',
                '',
                'g'
            ) AS isbn,

            m.work_id,
            m.title,
            m.authors

        FROM read_parquet(?) m

        INNER JOIN sqlite_scan(?, 'books') b
            ON m.work_id = b.work_id

        CROSS JOIN LATERAL
            unnest(
                string_split(
                    coalesce(m.isbn10, ''),
                    '|'
                )
            ) AS t(isbn)

        WHERE trim(isbn) <> ''
        """,
        [MASTER, SQLITE_DB]
    )

    # ---------------------------------------------------------
    # Index
    # ---------------------------------------------------------

    print("Creating ISBN index...")

    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_isbn
        ON isbn_lookup(isbn)
        """
    )

    # ---------------------------------------------------------
    # Statistics
    # ---------------------------------------------------------

    total_rows = con.execute(
        """
        SELECT COUNT(*)
        FROM isbn_lookup
        """
    ).fetchone()[0]

    unique_isbns = con.execute(
        """
        SELECT COUNT(DISTINCT isbn)
        FROM isbn_lookup
        """
    ).fetchone()[0]

    unique_works = con.execute(
        """
        SELECT COUNT(DISTINCT work_id)
        FROM isbn_lookup
        """
    ).fetchone()[0]

    print("\n" + "=" * 70)
    print("ISBN LOOKUP COMPLETE")
    print("=" * 70)

    print("Lookup rows :", total_rows)
    print("Unique ISBNs:", unique_isbns)
    print("Unique works:", unique_works)

    print("\nSample:")

    sample = con.execute(
        """
        SELECT *
        FROM isbn_lookup
        LIMIT 10
        """
    ).fetchdf()

    print(sample.to_string(index=False))

    print("\nOutput:")
    print(OUTPUT_DB)

    con.close()


if __name__ == "__main__":
    main()