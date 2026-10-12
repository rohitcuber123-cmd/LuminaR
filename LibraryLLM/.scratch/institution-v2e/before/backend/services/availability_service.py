from backend.database.mongodb import (
    library_inventory_collection,
)


# The borrower-facing API and issue endpoint both operate against this library.
DEFAULT_LIBRARY_ID = "LIB001"


def _as_non_negative_int(value):
    """Normalize persisted availability values without exposing invalid data."""
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def get_availability_context(
    book,
    library_id=DEFAULT_LIBRARY_ID,
):
    """
    Return the availability source used by the borrower-facing issue flow.

    A physical inventory record takes precedence for that library; otherwise the
    catalogue record remains the source of truth.
    """
    inventory = library_inventory_collection.find_one(
        {
            "library_id": library_id,
            "work_id": book["work_id"],
        }
    )

    if inventory is not None:
        return {
            "source": "physical",
            "inventory": inventory,
            "available_copies": _as_non_negative_int(
                inventory.get("available_copies")
            ),
            "total_copies": _as_non_negative_int(
                inventory.get("total_copies")
            ),
        }

    return {
        "source": "catalogue",
        "inventory": None,
        "available_copies": _as_non_negative_int(
            book.get("available_copies")
        ),
        "total_copies": _as_non_negative_int(
            book.get("total_copies")
        ),
    }


def with_authoritative_availability(
    book,
    library_id=DEFAULT_LIBRARY_ID,
):
    """Copy a catalogue book with the availability used for actual borrowing."""
    if book is None:
        return None

    context = get_availability_context(book, library_id)
    result = dict(book)
    result["available_copies"] = context["available_copies"]
    result["total_copies"] = context["total_copies"]
    return result


def with_batch_availability(books, library_id=DEFAULT_LIBRARY_ID):
    """Preserve read-only legacy fields with one query per bounded result batch."""
    if not books:
        return []
    inventory = {row['work_id']: row for row in library_inventory_collection.find(
        {'library_id': library_id, 'work_id': {'$in': [book['work_id'] for book in books]}},
        {'_id': 0, 'work_id': 1, 'available_copies': 1, 'total_copies': 1})}
    return [{**book, 'available_copies': _as_non_negative_int(inventory.get(book['work_id'], book).get('available_copies')),
             'total_copies': _as_non_negative_int(inventory.get(book['work_id'], book).get('total_copies'))} for book in books]
