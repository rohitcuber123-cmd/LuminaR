"""Book capability and entitlement checks.

``work_id`` is the canonical identifier across catalogue, circulation, reader,
and RAG.  Asset discovery never grants access by itself: catalogue existence
and a current issue are checked from MongoDB for every protected request.
"""
from datetime import datetime, timezone
from fastapi import HTTPException

from backend.database.mongodb import books_collection, issues_collection
from rag.book_assets import capabilities, readable_path


def active_borrow_query(user_id):
    # Overdue ISSUED records remain returnable but their Know More access expires.
    return {"user_id": int(user_id), "status": "ISSUED", "returned_at": None,
            "due_date": {"$gt": datetime.now(timezone.utc)}}


def active_borrow_ids(user_id):
    return set(issues_collection.distinct("work_id", active_borrow_query(user_id)))


def has_active_borrow(user_id, work_id):
    return issues_collection.find_one(
        {**active_borrow_query(user_id), "work_id": work_id}, {"_id": 1}
    ) is not None


def with_capabilities(books):
    flags = capabilities([book["work_id"] for book in books])
    return [{**book, **flags[book["work_id"]]} for book in books]


def catalog_capabilities(work_ids):
    books = list(books_collection.find({"work_id": {"$in": work_ids}},
                                      {"_id": 0, "work_id": 1}))
    return with_capabilities(books)


def with_issue_capabilities(issues, user_id):
    """Enrich a user's issue records in one asset/catalogue pass.

    The returned booleans are safe UI hints.  Protected endpoints repeat the
    entitlement check, so stale browser state can never authorize access.
    """
    work_ids = list({issue.get("work_id") for issue in issues if issue.get("work_id")})
    existing = set(books_collection.distinct("work_id", {"work_id": {"$in": work_ids}}))
    flags = capabilities(work_ids)
    active = active_borrow_ids(user_id)
    enriched = []
    for issue in issues:
        work_id = issue.get("work_id")
        capability = flags.get(work_id, {"readable": False, "rag_available": False})
        borrowed = work_id in active and work_id in existing
        enriched.append({
            **issue,
            "exists": work_id in existing,
            "borrowed": borrowed,
            "loan_status": issue.get("status"),
            **capability,
            "can_read": borrowed and capability["readable"],
            "can_know_more": borrowed and capability["rag_available"],
        })
    return enriched


def authors_list(authors):
    if isinstance(authors, list):
        return [str(author) for author in authors if author]
    return [author.strip() for author in (authors or "").split(",") if author.strip()]


def get_know_more_books(user_id):
    borrowed = active_borrow_ids(user_id)
    if not borrowed:
        return []
    books = list(books_collection.find({"work_id": {"$in": list(borrowed)}},
                                      {"_id": 0, "work_id": 1, "title": 1, "authors": 1}))
    return sorted([
        {**book, "authors": authors_list(book.get("authors")), "borrowed": True}
        for book in with_capabilities(books) if book["rag_available"]
    ], key=lambda book: (book.get("title") or "").casefold())


def _catalogue_capability(work_id):
    if not books_collection.find_one({"work_id": work_id}, {"_id": 1}):
        raise HTTPException(404, "Book not found.")
    return capabilities([work_id])[work_id]


def authorize_reader(user_id, work_id):
    flags = _catalogue_capability(work_id)
    if not flags["readable"]:
        raise HTTPException(404, "Readable text is not available for this book.")
    if not has_active_borrow(user_id, work_id):
        raise HTTPException(403, "You need an active borrow to read this book.")
    return flags


def authorize_know_more(user_id, work_id):
    flags = _catalogue_capability(work_id)
    if not flags["rag_available"]:
        raise HTTPException(404, "Know More is not available for this title.")
    if not has_active_borrow(user_id, work_id):
        raise HTTPException(403, "You need an active borrow to use Know More for this book.")
    return flags


# Backwards-compatible name used by the RAG service.
authorize_book = authorize_know_more


def get_readable_book(user_id, work_id):
    authorize_reader(user_id, work_id)
    book = books_collection.find_one({"work_id": work_id},
                                     {"_id": 0, "work_id": 1, "title": 1, "authors": 1})
    path = readable_path(work_id)
    if path is None:
        raise HTTPException(404, "Readable full text is not available for this book.")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise HTTPException(404, "Readable full text is not available for this book.")
    return {**book, "authors": authors_list(book.get("authors")), "text": text}
