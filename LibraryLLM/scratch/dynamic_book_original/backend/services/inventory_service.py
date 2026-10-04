from datetime import datetime

from backend.database.mongodb import (
    library_inventory_collection,
    books_collection,
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
    book = books_collection.find_one(
        {"work_id": work_id},
        {"_id": 0, "work_id": 1},
    )

    if not book:
        raise ValueError(
            f"Work {work_id} does not exist in the LuminaR catalogue"
        )

    if total_copies < 1:
        raise ValueError(
            "total_copies must be at least 1"
        )

    if available_copies < 0:
        raise ValueError(
            "available_copies cannot be negative"
        )

    if available_copies > total_copies:
        raise ValueError(
            "available_copies cannot exceed total_copies"
        )

    existing = library_inventory_collection.find_one(
        {
            "library_id": library_id,
            "work_id": work_id,
        }
    )

    if existing:
        raise ValueError(
            "This book already exists in this library's inventory"
        )

    now = datetime.utcnow()

    document = {
        "library_id": library_id,
        "work_id": work_id,
        "isbn": isbn,
        "total_copies": total_copies,
        "available_copies": available_copies,
        "shelf_location": shelf_location,
        "source": source,
        "created_at": now,
        "updated_at": now,
    }

    library_inventory_collection.insert_one(
        document
    )

    document.pop("_id", None)

    return document


def get_inventory(library_id):
    return list(
        library_inventory_collection.find(
            {"library_id": library_id},
            {"_id": 0},
        )
    )


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
):
    existing = get_inventory_book(
        library_id,
        work_id,
    )

    if not existing:
        raise ValueError(
            "Inventory record not found"
        )

    new_total = (
        total_copies
        if total_copies is not None
        else existing["total_copies"]
    )

    new_available = (
        available_copies
        if available_copies is not None
        else existing["available_copies"]
    )

    if new_total < 1:
        raise ValueError(
            "total_copies must be at least 1"
        )

    if new_available < 0:
        raise ValueError(
            "available_copies cannot be negative"
        )

    if new_available > new_total:
        raise ValueError(
            "available_copies cannot exceed total_copies"
        )

    update = {
        "total_copies": new_total,
        "available_copies": new_available,
        "updated_at": datetime.utcnow(),
    }

    if shelf_location is not None:
        update["shelf_location"] = shelf_location

    library_inventory_collection.update_one(
        {
            "library_id": library_id,
            "work_id": work_id,
        },
        {
            "$set": update,
        },
    )

    return get_inventory_book(
        library_id,
        work_id,
    )


def delete_inventory(
    library_id,
    work_id,
):
    result = library_inventory_collection.delete_one(
        {
            "library_id": library_id,
            "work_id": work_id,
        }
    )

    if result.deleted_count == 0:
        raise ValueError(
            "Inventory record not found"
        )

    return {
        "message": "Inventory record deleted",
        "library_id": library_id,
        "work_id": work_id,
    }