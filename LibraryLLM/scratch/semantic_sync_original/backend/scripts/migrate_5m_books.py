import sqlite3
import time
from pymongo import MongoClient, InsertOne

# ============================================================
# CONFIGURATION
# ============================================================

SQLITE_PATH = r"D:\SDC\LibraryLLM\datasets\library.db"

MONGO_URI = "mongodb://localhost:27017"
MONGO_DATABASE = "luminar_library"
MONGO_COLLECTION = "books"

BATCH_SIZE = 5000

SOURCE_TARGET = 5_000_000

# Existing MongoDB books already occupy 1-10001.
# New IDs therefore start at 10002.
START_BOOK_ID = 10_002


# ============================================================
# MONGODB CONNECTION
# ============================================================

def connect_mongodb():

    client = MongoClient(
        MONGO_URI,
        maxPoolSize=20,
        serverSelectionTimeoutMS=10000
    )

    client.admin.command("ping")

    db = client[MONGO_DATABASE]
    collection = db[MONGO_COLLECTION]

    return client, collection


# ============================================================
# GET EXISTING STATE
# ============================================================

def get_existing_state(collection):

    print()
    print("Checking existing MongoDB catalogue...")

    count = collection.count_documents({})

    max_id_doc = collection.find_one(
        {"book_id": {"$exists": True}},
        sort=[("book_id", -1)],
        projection={"book_id": 1, "_id": 0}
    )

    if max_id_doc:
        max_book_id = max_id_doc["book_id"]
    else:
        max_book_id = START_BOOK_ID - 1

    print(f"Existing MongoDB books : {count:,}")
    print(f"Maximum book_id        : {max_book_id:,}")

    return count, max_book_id


# ============================================================
# MIGRATION
# ============================================================

def migrate():

    start_time = time.time()

    print("=" * 75)
    print("LUMINAR 5M MONGODB BOOK MIGRATION")
    print("=" * 75)

    # --------------------------------------------------------
    # SQLite
    # --------------------------------------------------------

    sqlite_conn = sqlite3.connect(
        SQLITE_PATH
    )

    sqlite_conn.row_factory = sqlite3.Row

    sqlite_cursor = sqlite_conn.cursor()

    # --------------------------------------------------------
    # MongoDB
    # --------------------------------------------------------

    mongo_client, books_collection = connect_mongodb()

    try:

        existing_count, max_book_id = get_existing_state(
            books_collection
        )

        if existing_count > SOURCE_TARGET:

            raise RuntimeError(
                f"MongoDB already contains {existing_count:,} books, "
                f"which exceeds the target of {SOURCE_TARGET:,}."
            )

        # ----------------------------------------------------
        # Make sure work_id index exists
        # ----------------------------------------------------

        print()
        print("Checking work_id index...")

        indexes = books_collection.index_information()

        work_index_exists = False

        for index_name, index_info in indexes.items():

            keys = index_info.get("key", [])

            if keys == [("work_id", 1)]:

                work_index_exists = True

                if not index_info.get("unique", False):

                    raise RuntimeError(
                        "work_id index exists but is not UNIQUE."
                    )

        if not work_index_exists:

            print("Creating unique work_id index...")

            books_collection.create_index(
                [("work_id", 1)],
                unique=True,
                name="work_id_1"
            )

        else:

            print("Unique work_id index already exists.")

        # ----------------------------------------------------
        # Existing work IDs
        # ----------------------------------------------------

        print()
        print("Loading existing MongoDB work_ids...")

        existing_work_ids = set(
            books_collection.distinct("work_id")
        )

        print(
            f"Existing work_ids loaded : "
            f"{len(existing_work_ids):,}"
        )

        # ----------------------------------------------------
        # Determine next book ID
        # ----------------------------------------------------

        next_book_id = max(
            max_book_id + 1,
            START_BOOK_ID
        )

        print(
            f"Next MongoDB book_id     : "
            f"{next_book_id:,}"
        )

        # ----------------------------------------------------
        # SQLite total
        # ----------------------------------------------------

        sqlite_total = sqlite_cursor.execute(
            "SELECT COUNT(*) FROM books"
        ).fetchone()[0]

        print(
            f"SQLite source books      : "
            f"{sqlite_total:,}"
        )

        if sqlite_total != SOURCE_TARGET:

            raise RuntimeError(
                f"SQLite contains {sqlite_total:,} books, "
                f"expected exactly {SOURCE_TARGET:,}."
            )

        # ----------------------------------------------------
        # Stream SQLite records
        # ----------------------------------------------------

        sqlite_cursor.execute(
            """
            SELECT
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
            FROM books
            ORDER BY book_id
            """
        )

        inserted = 0
        skipped = 0
        processed = 0

        batch = []

        print()
        print("Starting migration...")
        print("-" * 75)

        while True:

            rows = sqlite_cursor.fetchmany(
                BATCH_SIZE
            )

            if not rows:
                break

            for row in rows:

                processed += 1

                work_id = row["work_id"]

                # ------------------------------------------------
                # Existing MongoDB record
                # ------------------------------------------------

                if work_id in existing_work_ids:

                    skipped += 1

                    continue

                # ------------------------------------------------
                # New MongoDB record
                # ------------------------------------------------

                document = {
                    "book_id": next_book_id,

                    "work_id": work_id,

                    "title": row["title"],

                    "authors": row["authors"],

                    "subjects": row["subjects"],

                    "description": row["description"],

                    "average_rating": (
                        row["average_rating"]
                        if row["average_rating"] is not None
                        else 0
                    ),

                    "rating_count": (
                        row["rating_count"]
                        if row["rating_count"] is not None
                        else 0
                    ),

                    "reading_log_count": (
                        row["reading_log_count"]
                        if row["reading_log_count"] is not None
                        else 0
                    ),

                    # ------------------------------------------------
                    # New catalogue records have no assigned physical
                    # shelf yet.
                    # ------------------------------------------------

                    "shelf_location": None,

                    # Default simulated library inventory.
                    "total_copies": 1,

                    "available_copies": 1
                }

                batch.append(
                    InsertOne(document)
                )

                existing_work_ids.add(work_id)

                next_book_id += 1

                inserted += 1

            # ----------------------------------------------------
            # Bulk insert
            # ----------------------------------------------------

            if batch:

                try:

                    result = books_collection.bulk_write(
                        batch,
                        ordered=False
                    )

                    # MongoDB normally reports this count.
                    # `inserted` already tracks our logical count.
                    _ = result

                except Exception as e:

                    print()
                    print("ERROR during MongoDB bulk insert:")
                    print(e)

                    print()
                    print(
                        "Migration stopped safely. "
                        "Run the script again to resume."
                    )

                    raise

                batch.clear()

            # ----------------------------------------------------
            # Progress
            # ----------------------------------------------------

            elapsed = time.time() - start_time

            rate = (
                inserted / elapsed
                if elapsed > 0
                else 0
            )

            remaining = (
                SOURCE_TARGET -
                (existing_count + inserted)
            )

            eta = (
                remaining / rate
                if rate > 0
                else 0
            )

            percentage = (
                (existing_count + inserted)
                / SOURCE_TARGET
            ) * 100

            print(
                f"Processed: {processed:,}/"
                f"{sqlite_total:,} | "
                f"MongoDB: "
                f"{existing_count + inserted:,}/"
                f"{SOURCE_TARGET:,} "
                f"({percentage:.2f}%) | "
                f"Inserted: {inserted:,} | "
                f"Skipped: {skipped:,} | "
                f"Rate: {rate:,.0f}/sec | "
                f"ETA: {eta / 60:.1f} min"
            )

        # --------------------------------------------------------
        # Final validation
        # --------------------------------------------------------

        print()
        print("=" * 75)
        print("MIGRATION FINISHED")
        print("=" * 75)

        final_count = books_collection.count_documents({})

        unique_work_ids = len(
            books_collection.distinct("work_id")
        )

        duplicate_work_ids = list(
            books_collection.aggregate(
                [
                    {
                        "$group": {
                            "_id": "$work_id",
                            "count": {"$sum": 1}
                        }
                    },
                    {
                        "$match": {
                            "count": {"$gt": 1}
                        }
                    },
                    {
                        "$limit": 1
                    }
                ]
            )
        )

        max_id_doc = books_collection.find_one(
            {"book_id": {"$exists": True}},
            sort=[("book_id", -1)],
            projection={"book_id": 1, "_id": 0}
        )

        final_max_id = (
            max_id_doc["book_id"]
            if max_id_doc
            else None
        )

        elapsed = time.time() - start_time

        print()
        print(f"SQLite source       : {sqlite_total:,}")
        print(f"MongoDB final       : {final_count:,}")
        print(f"Unique work_ids     : {unique_work_ids:,}")
        print(
            "Duplicate work_ids  : "
            f"{1 if duplicate_work_ids else 0}"
        )
        print(f"New inserted        : {inserted:,}")
        print(f"Existing skipped    : {skipped:,}")
        print(f"Maximum book_id     : {final_max_id:,}")
        print(f"Total time          : {elapsed / 60:.2f} minutes")

        print()
        print("=" * 75)

        if (
            final_count == SOURCE_TARGET
            and
            unique_work_ids == SOURCE_TARGET
            and
            not duplicate_work_ids
        ):

            print("✓ MIGRATION SUCCESSFUL")
            print("✓ 5,000,000 books present")
            print("✓ 5,000,000 unique work_ids")
            print("✓ No duplicate work_ids")
            print("✓ Existing books preserved")

        else:

            print("⚠ MIGRATION VALIDATION FAILED")
            print("Do NOT continue until the discrepancy is investigated.")

        print("=" * 75)

    finally:

        sqlite_conn.close()
        mongo_client.close()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    migrate()