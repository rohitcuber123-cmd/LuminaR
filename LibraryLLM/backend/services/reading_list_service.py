from datetime import datetime, timezone
from typing import List, Dict, Any
from fastapi import HTTPException
from backend.database.mongodb import reading_list_collection, books_collection
from uuid import UUID
from backend.services.institution_repository import collection, require_readable
from backend.services.library_inventory_access import require_library_patron
from backend.services import library_catalogue_experience as catalogue


def local_target(value):
    """Local-only personal identities cannot be confused with global work IDs."""
    if not value.startswith('local:'):
        return None
    try:
        kind, library_id, book_id = value.split(':')
        return str(UUID(library_id)), str(UUID(book_id))
    except (ValueError, AttributeError):
        raise HTTPException(422, 'Invalid library reading-list target.')

def get_user_reading_list(user_id: int) -> List[Dict[str, Any]]:
    """Returns the user's reading list documents."""
    records = reading_list_collection.find({"user_id": user_id}).sort("added_at", -1)
    items = [
        {
            "target_key": record["work_id"],
            "work_id": None if record.get('target_type') == 'LIBRARY_BOOK' else record["work_id"],
            "library_id": record.get('library_id'),
            "library_book_id": record.get('library_book_id'),
            "target_type": record.get('target_type', 'GLOBAL_WORK'),
            "book_id": record.get("book_id", 0),
            "title": record.get("title", ""),
            "authors": record.get("authors", ""),
            "subjects": record.get('subjects', ''),
            "added_at": record.get("added_at"),
            "available_copies": record.get("available_copies", 0),
            "total_copies": record.get("total_copies", 0),
        }
        for record in records
    ]
    # Resolve saved local identities through the same current-user catalogue as cards.
    # Saved metadata must never grant a capability after withdrawal or revocation.
    groups = {}
    for item in items:
        if item['target_type'] == 'LIBRARY_BOOK':
            groups.setdefault(item['library_id'], []).append(item)
    for library_id, saved in groups.items():
        try:
            actor = {'sub': str(user_id)}
            current = {}
            with catalogue.read_context(library_id, actor) as (_, _, canonical):
                for start in range(0, len(saved), 200):
                    ids = [item['library_book_id'] for item in saved[start:start + 200]]
                    rows = list(collection('library_books').aggregate([
                        {'$match': {'library_id': library_id, 'library_book_id': {'$in': ids}}},
                        *catalogue.usable(library_id), {'$limit': 200}]))
                    current.update({row['library_book_id']: row for row in
                        catalogue.hydrate(library_id, actor, rows, canonical)})
        except HTTPException:
            current = {}
        for item in saved:
            row = current.get(item['library_book_id'])
            item['accessible'] = bool(row)
            item['library_book'] = row
            item.update({'title': row['title'] if row else 'Unavailable library book',
                'authors': '; '.join(row.get('authors') or []) if row else '',
                'subjects': '|'.join(row.get('subjects') or []) if row else '',
                'cover_url': row.get('cover_url') if row else None})
    return items

def add_to_reading_list(user_id: int, work_id: str) -> str:
    """Adds a work to the user's reading list as a new document."""
    local = local_target(work_id)
    target_fields = {'target_type': 'GLOBAL_WORK'}
    if local:
        library_id, book_id = local
        work_id = f'local:{library_id}:{book_id}'
        require_library_patron(library_id, {'sub': str(user_id)})
        row = collection('library_books').find_one({'library_id': library_id, 'library_book_id': book_id, 'status': 'ACTIVE'})
        require_readable(library_id)
        if not row:
            raise HTTPException(404, 'Book is not held by this library.')
        if row.get('global_work_id'):
            # Linked representations converge to the same existing unique user/work key.
            work_id = row['global_work_id']
            book = books_collection.find_one({'work_id': work_id})
        else:
            book = {'title': row['title'], 'authors': '; '.join(row.get('authors') or []), 'subjects': '|'.join(row.get('subjects') or [])}
            target_fields = {'target_type': 'LIBRARY_BOOK', 'library_id': library_id, 'library_book_id': book_id}
    else:
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
                "subjects": book.get('subjects', ''),
                **target_fields,
                "available_copies": book.get("available_copies", 0),
                "total_copies": book.get("total_copies", 0),
                "added_at": datetime.now(timezone.utc)
            }
        },
        upsert=True
    )
    return work_id

def remove_from_reading_list(user_id: int, work_id: str) -> None:
    """Removes a work from the user's reading list."""
    reading_list_collection.delete_one({
        "user_id": user_id,
        "work_id": work_id
    })
