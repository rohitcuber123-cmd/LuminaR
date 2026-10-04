"""Shared catalogue semantics. No models, database connections or index writes."""
import hashlib
import logging

SEARCH_EMBEDDING_FIELDS = frozenset({
    "title", "authors", "subjects", "description", "first_publish_date",
})
# Existing catalogue has no activation flag. Honor explicit flags if introduced.
SEARCH_ELIGIBILITY_FIELDS = frozenset({"active", "is_active", "searchable"})
LOG = logging.getLogger(__name__)


def text_value(value):
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "; ".join(text_value(item) for item in value)
    return str(value).strip()


def semantic_text(book):
    # Matches build_search_corpus.py's CONCAT_WS, including empty field labels.
    parts = []
    for label, field in (("Title:", "title"), ("Authors:", "authors"),
                         ("Subjects:", "subjects"), ("Description:", "description"),
                         ("First published:", "first_publish_date")):
        parts.append(label)
        value = text_value(book.get(field))
        if value:
            parts.append(value)
    return " ".join(parts)


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def searchable(book):
    return (isinstance(book.get("work_id"), str) and bool(book["work_id"].strip())
            and bool(text_value(book.get("title")))
            and all(book.get(field) is not False for field in SEARCH_ELIGIBILITY_FIELDS))


def semantic_change(before, after):
    return (semantic_text(before) != semantic_text(after)
            or searchable(before) != searchable(after))


def current_books(collection, work_ids):
    """Fail closed on Mongo errors; never fall back to cached catalogue metadata."""
    ids = list(dict.fromkeys(wid for wid in work_ids if isinstance(wid, str) and wid))
    if not ids:
        return {}
    books = {book["work_id"]: book for book in collection.find(
        {"work_id": {"$in": ids}}, {"_id": 0}) if searchable(book)}
    if len(books) < len(ids):
        LOG.info("hnsw_candidate_filtered_missing_mongo count=%d", len(ids) - len(books))
    return books
