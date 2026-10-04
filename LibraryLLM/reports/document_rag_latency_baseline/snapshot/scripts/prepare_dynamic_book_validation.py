"""Create an isolated MongoDB validation catalog from real catalog records."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.database.mongodb import client
from backend.services.auth_service import hash_password


def main():
    snapshot = json.loads((ROOT / "scratch/dynamic_catalog_snapshot.json").read_text(encoding="utf-8"))
    name = "luminar_dynamic_book_validation_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    database = client[name]
    books = [book for book in snapshot["books"] if book["work_id"] != "OL2772007W"]
    database.books.insert_many(books)
    database.books.create_index("work_id", unique=True)
    database.books.create_index("book_id")
    database.issues.create_index([("user_id", 1), ("work_id", 1), ("status", 1)])
    # Local-only test identities; no registration emails or real users' loans.
    password = os.urandom(18).hex()
    for user_id, role in [(1, "GENERAL_USER"), (2, "GENERAL_USER"), (3, "ADMIN")]:
        database.users.insert_one({"user_id": user_id, "name": "Integration Reader",
            "email": f"reader{user_id}@example.com", "role": role,
            "password_hash": hash_password(password), "is_email_verified": True,
            "created_at": datetime.now(timezone.utc)})
    config = {"database": name, "password": password,
              "new_work_id": "OL2772007W", "main_catalog_count": snapshot["catalog_count"]}
    (ROOT / "scratch/dynamic_validation_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(json.dumps({"database": name, "catalog_records": len(books), "new_book_not_registered": True}))


if __name__ == "__main__":
    main()
