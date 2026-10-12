"""Trusted existing global catalogue lookups only; no network or model inference."""
from backend.database.mongodb import books_collection
from backend.services.library_isbn_lookup import isbn_candidates


GLOBAL_FIELDS = {'_id': 0, 'work_id': 1, 'title': 1, 'subjects': 1, 'authors': 1, 'publisher': 1, 'publication_year': 1, 'edition': 1}


def verified_work(work_id):
    if not isinstance(work_id, str) or not work_id.strip() or len(work_id) > 100:
        return None
    return books_collection.find_one({'work_id': work_id.strip(), 'active': {'$ne': False}, 'is_active': {'$ne': False}}, GLOBAL_FIELDS)


