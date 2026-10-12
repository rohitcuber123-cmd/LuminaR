"""Parity-matrix regressions using the real HTTP app and disposable Mongo."""
from uuid import uuid4
from backend.database.mongodb import db
from test_catalogue import catalogue, call


def saved(client, user=2):
    return call(client, user, 'GET', '/reading-list/my')['items']


def test_linked_and_global_save_share_identity(client, catalogue):
    a, _, ids = catalogue
    target = f"local:{a['id']}:{ids[0]}"
    assert call(client, 2, 'POST', '/reading-list/', {'work_id': target})['target_key'] == 'OL1W'
    call(client, 2, 'POST', '/reading-list/', {'work_id': 'OL1W'})
    assert len(saved(client)) == 1
    assert saved(client)[0]['target_key'] == 'OL1W'
    call(client, 2, 'DELETE', '/reading-list/OL1W')
    assert saved(client) == []


def test_local_only_save_is_scoped_and_rechecked(client, catalogue):
    a, b, ids = catalogue
    target = f"local:{a['id']}:{ids[1]}"
    call(client, 2, 'POST', '/reading-list/', {'work_id': target})
    item = saved(client)[0]
    assert item['target_type'] == 'LIBRARY_BOOK' and item['work_id'] is None
    assert item['library_book_id'] == ids[1] and item['accessible']
    call(client, 2, 'POST', '/reading-list/', {'work_id': f"local:{b['id']}:{ids[1]}"}, 404)
    db.institution_memberships.update_one({'library_id': a['id'], 'user_id': 2}, {'$set': {'status': 'SUSPENDED'}})
    item = saved(client)[0]
    assert not item['accessible'] and item['title'] == 'Unavailable library book'
    assert not item['authors'] and not item['subjects']
    call(client, 2, 'POST', '/reading-list/', {'work_id': target}, 404)
    call(client, 2, 'DELETE', '/reading-list/' + target)
    assert saved(client) == []


def test_local_saved_owner_isolation_and_staff_cannot_save(client, catalogue):
    a, _, ids = catalogue
    target = f"local:{a['id']}:{ids[2]}"
    call(client, 1, 'POST', '/reading-list/', {'work_id': target}, 403)
    call(client, 2, 'POST', '/reading-list/', {'work_id': target})
    assert saved(client, 3) == []
    call(client, 3, 'DELETE', '/reading-list/' + target)
    assert len(saved(client)) == 1
    db.institution_library_books.update_one({'library_book_id': ids[2]}, {'$set': {'status': 'WITHDRAWN'}})
    assert not saved(client)[0]['accessible']


def test_local_saved_invalid_keys_and_unlinked_record(client, catalogue):
    call(client, 2, 'POST', '/reading-list/', {'work_id': 'local:bad:bad'}, 422)
    a, _, _ = catalogue
    call(client, 2, 'POST', '/reading-list/', {'work_id': f"local:{a['id']}:{uuid4()}"}, 404)


def test_global_category_and_author_filter_before_pagination(client):
    rows = [{'work_id': f'OL{i}W', 'book_id': i, 'title': f'Book {i}',
             'subjects': 'Rare | Science' if i % 3 == 0 else 'Rareness',
             'authors': 'Ada' if i % 2 == 0 else 'Grace'} for i in range(90)]
    db.books.insert_many(rows)
    first = call(client, 2, 'GET', '/books/?category=Rare&author=Ada&limit=5')
    second = call(client, 2, 'GET', '/books/?category=Rare&author=Ada&limit=5&offset=5')
    assert first['count'] == second['count'] == 15
    assert [b['book_id'] for b in first['results']] == [0, 6, 12, 18, 24]
    assert [b['book_id'] for b in second['results']] == [30, 36, 42, 48, 54]
    assert first['has_more'] and second['has_more']
    assert call(client, 2, 'GET', '/books/?category=Rare&author=Ada&limit=5&offset=10')['has_more'] is False
    assert call(client, 2, 'GET', '/books/?category=.*')['results'] == []


def test_linked_detail_metadata_has_no_global_stock_leak(client, catalogue):
    a, _, ids = catalogue
    db.books.update_one({'work_id': 'OL1W'}, {'$set': {'description': 'Shared description', 'average_rating': 4.5}})
    row = call(client, 2, 'GET', a['base'] + '/catalogue/books/' + ids[0])['book']
    assert row['description'] == 'Shared description' and row['average_rating'] == 4.5
    assert row['cover_seed'] == 1
    assert row['shelf_location'] == 'A / Shelf 0' and row['requestable_count'] == 2
    assert row['availability']['total'] == 2
