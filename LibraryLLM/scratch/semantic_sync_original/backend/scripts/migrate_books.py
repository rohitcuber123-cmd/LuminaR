import sqlite3

from backend.database.mongodb import books_collection


SQLITE_PATH = r"D:\SDC\LibraryLLM\datasets\library.db"

BATCH_SIZE = 1000


def migrate_books():

    sqlite = sqlite3.connect(SQLITE_PATH)

    try:

        cursor = sqlite.execute(
            """
            SELECT
                book_id,
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
                available_copies,
                created_at
            FROM books
            ORDER BY book_id
            """
        )

        total = 0

        while True:

            rows = cursor.fetchmany(BATCH_SIZE)

            if not rows:
                break

            documents = []

            for row in rows:

                (
                    book_id,
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
                    available_copies,
                    created_at
                ) = row

                documents.append({
                    "book_id": book_id,
                    "work_id": work_id,
                    "title": title,
                    "authors": authors,
                    "subjects": subjects,
                    "description": description,
                    "average_rating": average_rating or 0,
                    "rating_count": rating_count or 0,
                    "reading_log_count": reading_log_count or 0,
                    "shelf_location": shelf_location,
                    "total_copies": total_copies,
                    "available_copies": available_copies,
                    "created_at": created_at
                })

            if documents:

                books_collection.insert_many(
                    documents,
                    ordered=False
                )

                total += len(documents)

                print(
                    f"Migrated: {total:,} books"
                )

        print()
        print("=" * 50)
        print("BOOK MIGRATION COMPLETE")
        print("=" * 50)
        print(f"Total migrated: {total:,}")

    finally:

        sqlite.close()


if __name__ == "__main__":
    migrate_books()