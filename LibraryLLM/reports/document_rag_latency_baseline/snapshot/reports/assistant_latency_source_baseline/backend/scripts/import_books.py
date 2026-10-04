import sqlite3
import duckdb
import time
import os

DUCKDB_PATH = r"D:\SDC\LibraryLLM\datasets\ai\metadata\book_metadata.duckdb"
SQLITE_PATH = r"D:\SDC\LibraryLLM\datasets\library.db"

BATCH_SIZE = 5000
TARGET_COUNT = 5_000_000


def import_books():

    start_time = time.time()

    duck = duckdb.connect(
        DUCKDB_PATH,
        read_only=True
    )

    sqlite = sqlite3.connect(SQLITE_PATH)

    try:

        sqlite.execute("PRAGMA journal_mode=WAL")
        sqlite.execute("PRAGMA synchronous=NORMAL")
        sqlite.execute("PRAGMA temp_store=MEMORY")

        # Find how many books are already present.
        existing = sqlite.execute(
            "SELECT COUNT(*) FROM books"
        ).fetchone()[0]

        print("=" * 70)
        print("LUMINAR 5M BOOK IMPORT")
        print("=" * 70)
        print(f"Existing SQLite books : {existing:,}")
        print(f"Target books          : {TARGET_COUNT:,}")

        if existing >= TARGET_COUNT:
            print("Target already reached.")
            return

        # We use OFFSET based on the number already imported.
        # This assumes the DuckDB source ordering remains stable.
        query = """
            SELECT
                work_id,
                title,
                authors,
                subjects,
                description,
                average_rating,
                rating_count,
                reading_log_count
            FROM books
            LIMIT ? OFFSET ?
        """

        offset = existing
        imported = 0
        skipped = 0

        while offset < TARGET_COUNT:

            remaining = TARGET_COUNT - offset
            fetch_size = min(BATCH_SIZE, remaining)

            rows = duck.execute(
                query,
                [fetch_size, offset]
            ).fetchall()

            if not rows:
                break

            for row in rows:

                (
                    work_id,
                    title,
                    authors,
                    subjects,
                    description,
                    average_rating,
                    rating_count,
                    reading_log_count
                ) = row

                try:

                    cursor = sqlite.execute(
                        """
                        INSERT OR IGNORE INTO books
                        (
                            work_id,
                            title,
                            authors,
                            subjects,
                            description,
                            average_rating,
                            rating_count,
                            reading_log_count,
                            shelf_location,
                            total_copies,
                            available_copies
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            work_id,
                            title,
                            authors,
                            subjects,
                            description,
                            average_rating or 0,
                            rating_count or 0,
                            reading_log_count or 0,
                            None,
                            1,
                            1
                        )
                    )

                    if cursor.rowcount == 1:
                        imported += 1
                    else:
                        skipped += 1

                except sqlite3.IntegrityError:
                    skipped += 1

            sqlite.commit()

            offset += len(rows)

            processed = imported + skipped
            percentage = (offset / TARGET_COUNT) * 100

            elapsed = time.time() - start_time

            rate = processed / elapsed if elapsed > 0 else 0

            remaining_books = TARGET_COUNT - offset

            eta = (
                remaining_books / rate
                if rate > 0
                else 0
            )

            print(
                f"Processed: {offset:,}/{TARGET_COUNT:,} "
                f"({percentage:.2f}%) | "
                f"Imported: {imported:,} | "
                f"Skipped: {skipped:,} | "
                f"Rate: {rate:,.0f}/sec | "
                f"ETA: {eta / 60:.1f} min"
            )

        elapsed = time.time() - start_time

        final_count = sqlite.execute(
            "SELECT COUNT(*) FROM books"
        ).fetchone()[0]

        print()
        print("=" * 70)
        print("BOOK IMPORT COMPLETE")
        print("=" * 70)
        print(f"SQLite books : {final_count:,}")
        print(f"New imports  : {imported:,}")
        print(f"Skipped      : {skipped:,}")
        print(f"Time         : {elapsed / 60:.2f} minutes")

    finally:

        duck.close()
        sqlite.close()


if __name__ == "__main__":
    import_books()