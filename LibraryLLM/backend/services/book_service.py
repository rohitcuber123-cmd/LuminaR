from search.catalogue import semantic_change, SEARCH_EMBEDDING_FIELDS, SEARCH_ELIGIBILITY_FIELDS
from search.sync_queue import catalogue_mutation
from contextlib import nullcontext
from datetime import datetime, timezone
from pymongo import ReturnDocument
from pymongo.errors import ExecutionTimeout
import re

from backend.database.mongodb import (
    books_collection,
    issues_collection,
    library_inventory_collection,
    book_categories_collection
)
from backend.services.availability_service import (
    with_authoritative_availability,
    with_batch_availability,
)


# ============================================================
# GET BOOKS
# ============================================================

def get_books(limit=20, offset=0, *, category='', author='', sort='catalogue'):

    query = {}
    if category:
        # Subjects are pipe-delimited catalogue tokens. Match the complete token,
        # not a subset of an already paginated window or unrelated substring.
        query['subjects'] = {'$regex': r'(^|\|)\s*' + re.escape(category.strip()) + r'\s*(\||$)', '$options': 'i'}
    if author:
        query['authors'] = {'$regex': re.escape(author.strip()), '$options': 'i'}
    ordering = [('created_at', -1), ('book_id', 1)] if sort == 'new_arrivals' else [('reading_log_count', -1), ('average_rating', -1), ('rating_count', -1), ('book_id', 1)] if sort == 'popular' else [('book_id', 1)]

    books = list(
        books_collection.find(
            query,
            {
                "_id": 0
            }
        )
        .sort(ordering)
        .skip(offset)
        .limit(limit)
    )

    # Exact filtered counts can scan all five million records. Bound that work;
    # clients paginate by the extra result rather than inventing a total.
    try:
        total_count = books_collection.count_documents(query, maxTimeMS=1000) if query else books_collection.estimated_document_count()
    except ExecutionTimeout:
        total_count = None

    return with_batch_availability(books), total_count


# ============================================================
# GET TOP CATEGORIES
# ============================================================

def get_top_categories(limit=14):

    categories = list(
        book_categories_collection.find(
            {},
            {
                "_id": 0
            }
        )
        .sort(
            "count",
            -1
        )
        .limit(limit)
    )

    return categories


# ============================================================
# GET POPULAR BOOKS
# ============================================================

def get_popular_books(limit=10):

    books = list(
        books_collection.find(
            {
                "title": {
                    "$exists": True,
                    "$ne": ""
                }
            },
            {
                "_id": 0
            }
        )
        .sort([
            ("reading_log_count", -1),
            ("average_rating", -1),
            ("rating_count", -1)
        ])
        .limit(limit)
    )

    return with_batch_availability(books)


# ============================================================
# GET NEW ARRIVALS
# ============================================================

def get_new_arrivals(limit=10):

    books = list(
        books_collection.find(
            {
                "title": {
                    "$exists": True,
                    "$ne": ""
                }
            },
            {
                "_id": 0
            }
        )
        .sort(
            "created_at",
            -1
        )
        .limit(limit)
    )

    return with_batch_availability(books)


# ============================================================
# GET BOOK BY WORK ID
# ============================================================

def get_book_by_work_id(work_id):

    book = books_collection.find_one(
        {
            "work_id": work_id
        },
        {
            "_id": 0
        }
    )

    return with_authoritative_availability(book)


# ============================================================
# CREATE BOOK
# ============================================================

def create_book(data):

    existing_book = books_collection.find_one(
        {
            "work_id": data["work_id"]
        }
    )

    if existing_book is not None:
        raise ValueError(
            "A book with this work_id already exists"
        )

    last_book = books_collection.find_one(
        {},
        sort=[("book_id", -1)]
    )

    if last_book is None:
        book_id = 1
    else:
        book_id = last_book["book_id"] + 1

    total_copies = data.get(
        "total_copies",
        0
    )

    available_copies = data.get(
        "available_copies",
        total_copies
    )

    if total_copies != 0 or available_copies != 0 or data.get("shelf_location"):
        raise ValueError("Physical stock and shelf belong to a library membership workspace.")

    if available_copies < 0:
        raise ValueError(
            "Available copies cannot be negative"
        )

    if available_copies > total_copies:
        raise ValueError(
            "Available copies cannot exceed total copies"
        )

    book = {
        "book_id": book_id,
        "work_id": data["work_id"],
        "title": data["title"],
        "authors": data.get("authors"),
        "subjects": data.get("subjects"),
        "description": data.get("description"),
        "average_rating": data.get(
            "average_rating",
            0
        ),
        "rating_count": data.get(
            "rating_count",
            0
        ),
        "reading_log_count": data.get(
            "reading_log_count",
            0
        ),
        "shelf_location": data.get(
            "shelf_location"
        ),
        "total_copies": total_copies,
        "available_copies": available_copies,
        "created_at": datetime.now(
            timezone.utc
        )
    }

    with catalogue_mutation([book["work_id"]]) as committed:
        books_collection.insert_one(book)
        committed.append(book["work_id"])

    book.pop("_id", None)

    return book


# ============================================================
# UPDATE BOOK
# ============================================================

def update_book(work_id, data):
    if set(data) & {"total_copies", "available_copies", "shelf_location"}:
        raise ValueError("Physical stock and shelf belong to a library membership workspace.")

    if "work_id" in data and data["work_id"] != work_id:
        raise ValueError("work_id cannot be changed")

    existing_book = books_collection.find_one(
        {
            "work_id": work_id
        }
    )

    if existing_book is None:
        return None

    relevant = bool(set(data) & (SEARCH_EMBEDDING_FIELDS | SEARCH_ELIGIBILITY_FIELDS))
    with catalogue_mutation([work_id]) if relevant else nullcontext([]) as committed:
        committed_before = books_collection.find_one_and_update(
            {
                "work_id": work_id
            },
            {
                "$set": data
            },
            return_document=ReturnDocument.BEFORE
        )

        if committed_before is None:
            return None
        # Compare the atomic pre-image, not the earlier validation read: another
        # writer may have changed semantic fields between those two operations.
        if semantic_change(committed_before, {**committed_before, **data}):
            committed.append(work_id)

    return get_book_by_work_id(work_id)


# ============================================================
# DELETE BOOK
# ============================================================

def delete_book(work_id):
    if issues_collection.find_one({"work_id": work_id, "status": "ISSUED"}):
        raise ValueError("Unable to delete this book. The book currently has active loans.")
    if library_inventory_collection.find_one({"work_id": work_id}):
        raise ValueError("Remove this book's physical inventory before deleting its catalogue record.")


    with catalogue_mutation([work_id]) as committed:
        result = books_collection.delete_one({"work_id": work_id})
        if result.deleted_count == 0:
            return None
        committed.append(work_id)

    return True
