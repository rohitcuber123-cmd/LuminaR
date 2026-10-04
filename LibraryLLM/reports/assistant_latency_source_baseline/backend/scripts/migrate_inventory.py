import sqlite3
from pymongo import MongoClient


SQLITE_PATH = r"D:\SDC\LibraryLLM\datasets\library.db"

MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "luminar_library"

BATCH_SIZE = 1000


def migrate_inventory():
    print("=" * 70)
    print("LUMINAR INVENTORY MIGRATION")
    print("=" * 70)

    # ---------------------------------------------------------
    # SQLite
    # ---------------------------------------------------------
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_cursor = sqlite_conn.cursor()

    sqlite_cursor.execute("""
        SELECT
            book_id,
            work_id,
            total_copies,
            available_copies,
            shelf_location
        FROM books
        ORDER BY book_id
    """)

    # ---------------------------------------------------------
    # MongoDB
    # ---------------------------------------------------------
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client[MONGO_DB]
    inventory = db["inventory"]

    # Make sure work_id is unique
    inventory.create_index(
        [("work_id", 1)],
        unique=True
    )

    # ---------------------------------------------------------
    # Read all original physical-library records
    # ---------------------------------------------------------
    rows = sqlite_cursor.fetchall()

    print(f"SQLite physical records: {len(rows)}")

    if len(rows) != 10001:
        raise RuntimeError(
            f"Expected 10001 original library records, "
            f"found {len(rows)}"
        )

    # ---------------------------------------------------------
    # Prepare documents
    # ---------------------------------------------------------
    documents = []

    for (
        book_id,
        work_id,
        total_copies,
        available_copies,
        shelf_location
    ) in rows:

        documents.append({
            "catalogue_book_id": book_id,
            "work_id": work_id,
            "total_copies": int(total_copies),
            "available_copies": int(available_copies),
            "shelf_location": shelf_location
        })

    # ---------------------------------------------------------
    # Insert in batches
    # ---------------------------------------------------------
    inserted = 0

    for start in range(0, len(documents), BATCH_SIZE):

        batch = documents[start:start + BATCH_SIZE]

        result = inventory.insert_many(
            batch,
            ordered=False
        )

        inserted += len(result.inserted_ids)

        print(
            f"Inserted {inserted}/{len(documents)}"
        )

    # ---------------------------------------------------------
    # Verification
    # ---------------------------------------------------------
    count = inventory.count_documents({})

    unique_work_ids = len(
        inventory.distinct("work_id")
    )

    print()
    print("=" * 70)
    print("MIGRATION COMPLETE")
    print("=" * 70)
    print(f"MongoDB inventory records : {count}")
    print(f"Unique work_ids           : {unique_work_ids}")

    if count != 10001:
        raise RuntimeError(
            f"Inventory count mismatch: expected 10001, got {count}"
        )

    if unique_work_ids != 10001:
        raise RuntimeError(
            "Duplicate work_id detected in inventory"
        )

    # ---------------------------------------------------------
    # Sample
    # ---------------------------------------------------------
    sample = inventory.find_one(
        {"work_id": "OL19545719W"},
        {"_id": 0}
    )

    print()
    print("SAMPLE:")
    print(sample)

    sqlite_conn.close()
    mongo_client.close()


if __name__ == "__main__":
    migrate_inventory()