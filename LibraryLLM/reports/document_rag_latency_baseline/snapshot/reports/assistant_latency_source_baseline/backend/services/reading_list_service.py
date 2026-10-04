from datetime import datetime, timezone
from typing import List, Dict, Any
from fastapi import HTTPException
from backend.database.mongodb import reading_list_collection, books_collection

def get_user_reading_list(user_id: int) -> List[Dict[str, Any]]:
    """Returns the user's reading list documents."""
    records = reading_list_collection.find({"user_id": user_id}).sort("added_at", -1)
    return [
        {
            "work_id": record["work_id"],
            "book_id": record["book_id"],
            "title": record.get("title", ""),
            "authors": record.get("authors", ""),
            "added_at": record.get("added_at"),
            "available_copies": record.get("available_copies", 0),
            "total_copies": record.get("total_copies", 0),
        }
        for record in records
    ]

def add_to_reading_list(user_id: int, work_id: str) -> None:
    """Adds a work to the user's reading list as a new document."""
    # Check if book exists
    book = books_collection.find_one({"work_id": work_id})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Add individual document (unique index handles duplicates)
    reading_list_collection.update_one(
        {
            "user_id": user_id,
            "work_id": work_id
        },
        {
            "$setOnInsert": {
                "user_id": user_id,
                "work_id": work_id,
                "book_id": book.get("book_id"),
                "title": book.get("title", ""),
                "authors": book.get("authors", ""),
                "available_copies": book.get("available_copies", 0),
                "total_copies": book.get("total_copies", 0),
                "added_at": datetime.now(timezone.utc)
            }
        },
        upsert=True
    )

def remove_from_reading_list(user_id: int, work_id: str) -> None:
    """Removes a work from the user's reading list."""
    reading_list_collection.delete_one({
        "user_id": user_id,
        "work_id": work_id
    })
