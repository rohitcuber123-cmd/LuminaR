from backend.platform_dependencies import retirement
from datetime import datetime

from backend.database.mongodb import (
    library_inventory_collection,
    books_collection,
    issues_collection,
)


def add_inventory(
    library_id,
    work_id,
    isbn=None,
    total_copies=1,
    available_copies=1,
    shelf_location=None,
    source="manual",
):
    retirement()


def get_inventory(library_id, limit=20, offset=0):
    records = list(library_inventory_collection.find(
        {"library_id": library_id}, {"_id": 0}
    ).sort("work_id", 1).skip(offset).limit(limit))
    books = {book["work_id"]: book for book in books_collection.find(
        {"work_id": {"$in": [row["work_id"] for row in records]}},
        {"_id": 0, "work_id": 1, "title": 1, "authors": 1}
    )}
    return [{**row, **books.get(row["work_id"], {})} for row in records]


def get_inventory_book(library_id, work_id):
    return library_inventory_collection.find_one(
        {
            "library_id": library_id,
            "work_id": work_id,
        },
        {"_id": 0},
    )


def update_inventory(
    library_id,
    work_id,
    total_copies=None,
    available_copies=None,
    shelf_location=None,
    isbn=None,
):
    retirement()


def delete_inventory(
    library_id,
    work_id,
):
    retirement()
