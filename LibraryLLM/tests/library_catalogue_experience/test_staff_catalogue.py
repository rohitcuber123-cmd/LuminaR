"""Staff catalogue uses canonical tenant identity and explicit membership only."""
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from backend.database.mongodb import db


def call(client, user, method, path, body=None, expected=200):
    response = client.request(method, path, headers={'x-test-user': str(user)}, json=body)
    assert response.status_code == expected, response.text
    return response.json()


@pytest.fixture
def staff_catalogue(client):
    libraries = []
    for name in ('Staff A', 'Staff B'):
        row = call(client, 1, 'POST', '/libraries/register', {'name': name, 'slug': uuid4().hex,
            'library_type': 'PUBLIC_LIBRARY', 'access_mode': 'PUBLIC'}, 201)['library']
        base = '/libraries/' + row['library_id']
        for uid in (2, 3): call(client, uid, 'POST', base + '/join', {})
        # Isolated database fixture: the librarian has an independently assigned membership.
        db.institution_memberships.update_one({'library_id': row['library_id'], 'user_id': 3}, {'$set': {'role': 'LIBRARIAN'}})
        libraries.append(base)
    a, b = libraries
    books = []
    for title, physical in [('Physical Atlas', True), ('Staff Online Atlas', False), ('Processing Atlas', False)]:
        book = call(client, 1, 'POST', a + '/inventory/books', {'idempotency_key': str(uuid4()),
            'title': title, 'subjects': ['Reference'], 'authors': ['Ada'], 'copies': 2 if physical else 0,
            'create_physical_holding': physical, 'shelf_location': 'A-1' if physical else None, 'local_call_number': 'REF-A' if physical else None}, 201)
        books.append(book)
    stamp = datetime.now(timezone.utc)
    for book, status in [(books[1], 'READY'), (books[2], 'PROCESSING')]:
        db.institution_library_assets.insert_one({'asset_id': str(uuid4()), 'library_id': book['library_id'],
            'library_book_id': book['library_book_id'], 'status': status, 'visibility': 'STAFF_ONLY',
            'title': 'Safe isolated asset', 'asset_type': 'PDF', 'uploaded_by_user_id': 1, 'upload_id': str(uuid4()), 'created_at': stamp, 'updated_at': stamp})
    db.books.insert_one({'work_id': 'OL1W', 'book_id': 1, 'title': 'Global filler must not appear'})
    return a, b, books


@pytest.mark.parametrize('user', [1, 3])
def test_staff_catalogue_explicit_admin_and_librarian_membership(client, staff_catalogue, user):
    a, _, books = staff_catalogue
    result = call(client, user, 'GET', a + '/catalogue/books?staff=true')
    assert result['source']['catalogue_source'] == 'LIBRARY_LOCAL' and result['total'] == 3
    assert {r['library_book_id'] for r in result['results']} == {b['library_book_id'] for b in books}
    assert all(not any(r['actions'].values()) and r['user_loan_state'] is None for r in result['results'])


@pytest.mark.parametrize('suffix', ['/source', '/books', '/genres'])
def test_staff_flag_does_not_grant_patron_authority(client, staff_catalogue, suffix):
    a, _, _ = staff_catalogue
    call(client, 2, 'GET', a + '/catalogue' + suffix + '?staff=true', expected=403)


def test_legacy_admin_without_membership_denied_staff_catalogue(client, staff_catalogue):
    a, _, _ = staff_catalogue
    db.institution_memberships.delete_one({'library_id': a.split('/')[-1], 'user_id': 1})
    call(client, 1, 'GET', a + '/catalogue/books?staff=true', expected=404)


def test_platform_role_without_membership_denied_staff_catalogue(client, staff_catalogue):
    a, _, _ = staff_catalogue
    db.institution_memberships.delete_one({'library_id': a.split('/')[-1], 'user_id': 1})
    db.platform_role_assignments.insert_one({'user_id': 1, 'role': 'PLATFORM_ADMIN', 'status': 'ACTIVE',
        'approval_ref': 'ISOLATED-STAFF-BOUNDARY-QA', 'approved_by': 'test-operator', 'approved_at': datetime.now(timezone.utc)})
    assert call(client, 1, 'GET', '/me/platform-access')['roles'] == ['PLATFORM_ADMIN']
    call(client, 1, 'GET', a + '/catalogue/books?staff=true', expected=404)


def test_staff_catalogue_empty_library_never_falls_back_to_global(client, staff_catalogue):
    _, b, _ = staff_catalogue
    result = call(client, 1, 'GET', b + '/catalogue/books?staff=true')
    assert result['source']['catalogue_source'] == 'LIBRARY_LOCAL'
    assert result['source']['local_book_count'] == result['total'] == 0 and result['results'] == []


def test_staff_catalogue_search_subject_and_bounded_paging(client, staff_catalogue):
    a, _, _ = staff_catalogue
    result = call(client, 1, 'GET', a + '/catalogue/books?staff=true&search=online&subject=Reference&limit=1')
    assert result['total'] == 1 and result['results'][0]['title'] == 'Staff Online Atlas'
    result = call(client, 1, 'GET', a + '/catalogue/books?staff=true&offset=1&limit=1')
    assert result['total'] == 3 and len(result['results']) == 1 and result['has_more']
    call(client, 1, 'GET', a + '/catalogue/books?staff=true&limit=10000', expected=422)


def test_staff_online_visibility_and_processing_capability(client, staff_catalogue):
    a, _, books = staff_catalogue
    online = call(client, 1, 'GET', a + '/catalogue/books/' + books[1]['library_book_id'] + '?staff=true')['book']
    assert online['book_format'] == 'DIGITAL_ONLY' and online['has_online'] and not online['has_physical']
    processing = call(client, 3, 'GET', a + '/catalogue/books/' + books[2]['library_book_id'] + '?staff=true')['book']
    assert processing['book_format'] == 'UNAVAILABLE' and not processing['has_online']
    # A ready staff-only PDF cannot become a Patron resource through the reused renderer.
    call(client, 2, 'GET', a + '/catalogue/books/' + books[1]['library_book_id'], expected=404)


def test_staff_default_catalogue_still_denies_same_library_patron_mode(client, staff_catalogue):
    a, _, _ = staff_catalogue
    call(client, 1, 'GET', a + '/catalogue/books', expected=403)
    call(client, 3, 'GET', a + '/catalogue/books', expected=403)


def test_staff_book_detail_is_scoped_to_library_book_identity(client, staff_catalogue):
    a, b, books = staff_catalogue
    bid = books[0]['library_book_id']
    call(client, 1, 'PUT', a + '/staff/lending/books/' + bid + '/shelf', {'idempotency_key':str(uuid4()), 'shelf_location':'A-1', 'call_number':'REF-UPDATED'})
    result = call(client, 1, 'GET', a + '/catalogue/books/' + bid + '?staff=true')['book']
    assert result['library_book_id'] == bid and result['shelf_location'] == 'A-1'
    assert result['status'] == 'ACTIVE' and result['availability']['requestable'] == 2
    assert result['local_call_number'] == 'REF-UPDATED'
    call(client, 1, 'GET', b + '/catalogue/books/' + bid + '?staff=true', expected=404)


def test_staff_historical_withdrawn_detail_preserved(client, staff_catalogue):
    a, _, books = staff_catalogue
    bid = books[0]['library_book_id']
    db.institution_library_books.update_one({'library_book_id': bid}, {'$set': {'status': 'WITHDRAWN'}})
    assert call(client, 1, 'GET', a + '/catalogue/books/' + bid + '?staff=true')['book']['status'] == 'WITHDRAWN'
    assert call(client, 1, 'GET', a + '/catalogue/books?staff=true')['total'] == 2
    call(client, 2, 'GET', a + '/catalogue/books/' + bid, expected=404)


def test_staff_catalogue_membership_revocation_applies_immediately(client, staff_catalogue):
    a, _, _ = staff_catalogue
    call(client, 3, 'GET', a + '/catalogue/books?staff=true')
    db.institution_memberships.update_one({'library_id': a.split('/')[-1], 'user_id': 3}, {'$set': {'status': 'INACTIVE'}})
    call(client, 3, 'GET', a + '/catalogue/books?staff=true', expected=404)
