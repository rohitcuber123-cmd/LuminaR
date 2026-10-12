from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from backend.database.mongodb import db
from backend.services import library_lending_service as lending


def command(**fields): return {'idempotency_key': str(uuid4()), **fields}


def call(client, user, method, path, body=None, expected=200):
    result = client.request(method, path, headers={'x-test-user': str(user)}, json=body)
    assert result.status_code == expected, result.text
    return result.json()


@pytest.fixture
def catalogue(client):
    db.books.insert_one({'work_id': 'OL1W', 'book_id': 1, 'title': 'Global Atlas', 'authors': 'Global Author', 'subjects': 'Networking',
        'shelf_location': 'FAKE GLOBAL SHELF', 'total_copies': 999, 'available_copies': 999})
    libraries = []
    for name in ['Library A', 'Library B']:
        library = call(client, 1, 'POST', '/libraries/register', {'name': name, 'slug': uuid4().hex,
            'library_type': 'PUBLIC_LIBRARY', 'access_mode': 'PUBLIC'}, 201)['library']
        base = '/libraries/' + library['library_id']
        for user in (2, 3): call(client, user, 'POST', base + '/join', {})
        # Fresh registration already provisions all canonical subsystems.
        libraries.append({'id': library['library_id'], 'base': base})
    a, b = libraries
    books = []
    for n in range(10):
        row = call(client, 1, 'POST', a['base'] + '/inventory/books', command(title='Global Atlas' if n == 0 else f'A Local Book {n}',
            subjects=['Networking' if n < 4 else 'Mathematics'], authors=['Ada' if n % 2 == 0 else 'Grace'],
            global_work_id='OL1W' if n == 0 else None, copies=2, shelf_location=f'A / Shelf {n}'), 201)
        books.append(row['library_book_id'])
    return a, b, books


def home(client, library): return call(client, 2, 'GET', library['base'] + '/catalogue/home')
def page(client, library, query=''): return call(client, 2, 'GET', library['base'] + '/catalogue/books' + query)
def book(client, library, bid): return call(client, 2, 'GET', library['base'] + '/catalogue/books/' + bid)['book']


def test_library_home_local_catalogue(client, catalogue):
    a, _, _ = catalogue; payload = home(client, a)
    assert payload['source']['library_name'] == 'Library A'
    assert len(payload['featured']) == 10 and all(r['library_id'] == a['id'] for r in payload['featured'])


def test_library_home_global_fallback(client, catalogue):
    _, b, _ = catalogue; payload = home(client, b)
    assert payload['source']['catalogue_source'] == 'GLOBAL_FALLBACK'
    assert payload['featured'] == [] and not payload['source']['capabilities']['physical_actions']


def test_catalogue_source_local_when_books_exist(client, catalogue):
    a, _, _ = catalogue; source = call(client, 2, 'GET', a['base'] + '/catalogue/source')
    assert source['catalogue_source'] == 'LIBRARY_LOCAL' and source['local_book_count'] == 10


def test_catalogue_source_global_when_empty(client, catalogue):
    _, b, _ = catalogue; source = call(client, 2, 'GET', b['base'] + '/catalogue/source')
    assert source['catalogue_source'] == 'GLOBAL_FALLBACK' and source['local_book_count'] == 0


def test_no_manual_has_dataset_dependency(client, catalogue):
    a, b, _ = catalogue
    db.institution_libraries.update_one({'library_id': a['id']}, {'$set': {'has_dataset': False}})
    db.institution_libraries.update_one({'library_id': b['id']}, {'$set': {'has_dataset': True}})
    assert home(client, a)['source']['catalogue_source'] == 'LIBRARY_LOCAL'
    assert home(client, b)['source']['catalogue_source'] == 'GLOBAL_FALLBACK'


def test_local_only_book(client, catalogue):
    a, _, ids = catalogue; record = book(client, a, ids[1])
    assert record['title'] == 'A Local Book 1' and record['global_work_id'] is None and record['owned_by_current_library']


def test_featured_rail_local(client, catalogue):
    a, _, _ = catalogue; first = home(client, a)['featured']; second = home(client, a)['featured']
    assert [r['display_id'] for r in first] == [r['display_id'] for r in second]


def test_small_collection_not_padded(client, catalogue):
    a, _, ids = catalogue
    db.institution_library_books.update_many({'library_id': a['id'], 'library_book_id': {'$in': ids[4:]}}, {'$set': {'status': 'WITHDRAWN'}})
    payload = home(client, a)
    assert payload['source']['local_book_count'] == 4 and len(payload['featured']) == 4
    assert all(r['source'] == 'LIBRARY' for r in payload['featured'])


def test_local_new_arrivals(client, catalogue):
    a, _, ids = catalogue; stamp = datetime.now(timezone.utc)
    db.institution_library_books.update_one({'library_book_id': ids[0]}, {'$set': {'created_at': stamp - timedelta(days=200), 'acquisition_date': stamp - timedelta(days=1), 'publication_year': 1800}})
    db.institution_library_books.update_one({'library_book_id': ids[1]}, {'$set': {'created_at': stamp - timedelta(days=10), 'publication_year': 2026}})
    result = page(client, a, '?sort=new_arrivals')['results']
    assert [r['display_id'] for r in result].index(ids[0]) < [r['display_id'] for r in result].index(ids[1])
    db.institution_loans.insert_one({'library_id': a['id'], 'library_book_id': ids[0], 'loan_id': str(uuid4()), 'user_id': 3, 'status': 'RETURNED', 'borrowed_at': stamp, 'returned_at': stamp})
    rail_book = next(r for r in home(client, a)['new_arrivals'] if r['display_id'] == ids[0])
    assert datetime.fromisoformat(rail_book['added_at']).replace(tzinfo=timezone.utc) == (stamp - timedelta(days=1)).replace(microsecond=stamp.microsecond // 1000 * 1000)


def test_new_arrivals_tenant_scoped(client, catalogue):
    a, b, _ = catalogue
    assert all(r['library_id'] == a['id'] for r in page(client, a, '?sort=new_arrivals')['results'])
    assert page(client, b, '?sort=new_arrivals')['results'] == []


def test_new_arrivals_switch_library(client, catalogue):
    a, b, _ = catalogue
    assert page(client, a, '?sort=new_arrivals')['source']['local_book_count'] == 10
    assert page(client, b, '?sort=new_arrivals')['source']['catalogue_source'] == 'GLOBAL_FALLBACK'


def test_local_genres(client, catalogue):
    a, _, _ = catalogue; result = call(client, 2, 'GET', a['base'] + '/catalogue/genres')
    assert {r['subject'] for r in result['results']} == {'Networking', 'Mathematics'}


def test_local_genre_counts(client, catalogue):
    a, _, _ = catalogue; result = home(client, a)['subjects']
    assert {r['subject']: r['count'] for r in result} == {'Networking': 4, 'Mathematics': 6}


def test_genre_current_library_only(client, catalogue):
    a, b, _ = catalogue; result = page(client, a, '?subject=Networking')
    assert result['total'] == 4 and all('Networking' in r['subjects'] for r in result['results'])
    assert call(client, 2, 'GET', b['base'] + '/catalogue/genres')['results'] == []


def test_local_search(client, catalogue):
    a, _, _ = catalogue
    assert page(client, a, '?search=Networking')['total'] == 4
    assert page(client, a, '?author=Ada')['total'] == 5
    assert page(client, a, '?search=A%20Local%20Book%207')['total'] == 1


def test_local_no_result_no_fake_ownership(client, catalogue):
    a, _, _ = catalogue; result = page(client, a, '?search=unmatched')
    assert result['results'] == [] and result['source']['catalogue_source'] == 'LIBRARY_LOCAL'


def test_owned_book_shelf(client, catalogue):
    a, _, ids = catalogue; assert book(client, a, ids[0])['shelf_location'] == 'A / Shelf 0'


def test_global_book_no_fake_ownership(client, catalogue):
    a, b, _ = catalogue
    owned = call(client, 2, 'GET', a['base'] + '/catalogue/global-books/OL1W')['book']
    unowned = call(client, 2, 'GET', b['base'] + '/catalogue/global-books/OL1W')['book']
    assert owned['owned_by_current_library'] and owned['shelf_location'] == 'A / Shelf 0'
    assert unowned is None


def test_canonical_availability(client, catalogue):
    a, _, ids = catalogue
    call(client, 3, 'POST', a['base'] + '/lending/borrow-requests', command(library_book_id=ids[0]), 201)
    db.institution_holdings.update_one({'library_book_id': ids[0]}, {'$set': {'available_copies': 999}})
    actual = book(client, a, ids[0])
    assert actual['requestable_count'] == 1 and actual['availability']['pending_holds'] == 1
    expected = lending.availability(a['id'], ids[0], {'sub': '2'})
    assert actual['availability'] == expected


@pytest.mark.parametrize('status', ['REFERENCE_ONLY', 'TEMPORARILY_UNAVAILABLE'])
def test_circulation_status_action_safety(client, catalogue, status):
    a, _, ids = catalogue
    db.institution_holdings.update_one({'library_book_id': ids[1]}, {'$set': {'circulation_status': status}})
    row = book(client, a, ids[1])
    assert row['requestable_count'] == 0 and not row['actions']['request'] and not row['actions']['reserve']


def test_local_book_request_button(client, catalogue):
    a, _, ids = catalogue; assert book(client, a, ids[0])['actions']['request']


def test_local_book_reservation_button(client, catalogue):
    a, _, ids = catalogue
    db.institution_holdings.update_one({'library_book_id': ids[0]}, {'$set': {'unavailable_stock': 2}})
    row = book(client, a, ids[0]); assert row['actions']['reserve'] and not row['actions']['request']


def test_pending_request_state_is_hydrated(client, catalogue):
    a, _, ids = catalogue
    call(client, 2, 'POST', a['base'] + '/lending/borrow-requests', command(library_book_id=ids[0]), 201)
    row = book(client, a, ids[0]); assert row['user_request_state']['status'] == 'PENDING' and row['actions']['cancel_request']
    assert not row['actions']['request'] and home(client, a)['my_library']['pending_requests'] == 1


def test_reservation_position_and_user_isolation(client, catalogue):
    a, _, ids = catalogue
    db.institution_holdings.update_one({'library_book_id': ids[0]}, {'$set': {'unavailable_stock': 2}})
    call(client, 3, 'POST', a['base'] + '/reservations', command(library_book_id=ids[0]), 201)
    call(client, 2, 'POST', a['base'] + '/reservations', command(library_book_id=ids[0]), 201)
    row = book(client, a, ids[0]); assert row['user_reservation_state']['queue_position'] == 2
    assert row['user_reservation_state']['queue_length'] == 2 and row['actions']['cancel_reservation']
    assert 'borrower' not in row and 'user_id' not in str(row['user_reservation_state'])


def test_popular_from_real_tenant_activity(client, catalogue):
    a, b, ids = catalogue
    request = call(client, 2, 'POST', a['base'] + '/lending/borrow-requests', command(library_book_id=ids[0]), 201)
    call(client, 1, 'POST', a['base'] + '/staff/lending/borrow-requests/' + request['lending_request_id'] + '/approve', command())
    result = home(client, a)['popular']
    assert len(result) == 1 and result[0]['display_id'] == ids[0] and result[0]['popularity']['loans'] == 1
    assert result[0]['popularity']['score'] == 10 and home(client, b)['popular'] == []


def test_popular_no_fake_activity(client, catalogue):
    a, _, _ = catalogue; assert home(client, a)['popular'] == [] and page(client, a, '?sort=popular')['total'] == 0


def test_popular_recent_window_and_tenant_filter(client, catalogue):
    a, b, ids = catalogue; old = datetime.now(timezone.utc) - timedelta(days=100)
    db.institution_loans.insert_one({'library_id': a['id'], 'library_book_id': ids[0], 'loan_id': str(uuid4()), 'user_id': 2,
        'status': 'RETURNED', 'borrowed_at': old})
    db.institution_loans.insert_one({'library_id': b['id'], 'library_book_id': ids[0], 'loan_id': str(uuid4()), 'user_id': 2,
        'status': 'RETURNED', 'borrowed_at': datetime.now(timezone.utc)})
    assert home(client, a)['popular'] == []


def test_copy_mode_bulk_matches_canonical(client, catalogue):
    a, _, ids = catalogue
    db.institution_holdings.update_one({'library_book_id': ids[0]}, {'$set': {'allocation_mode': 'COPY'}})
    db.institution_copies.insert_many([{'library_id': a['id'], 'library_book_id': ids[0], 'copy_id': str(uuid4()), 'holding_id': db.institution_holdings.find_one({'library_book_id': ids[0]})['holding_id'], 'copy_number': i, 'status': 'AVAILABLE'} for i in (1, 2)])
    assert book(client, a, ids[0])['availability'] == lending.availability(a['id'], ids[0], {'sub': '2'})


def test_bad_allocations_fail_closed(client, catalogue):
    a, _, ids = catalogue
    db.institution_holdings.update_one({'library_book_id': ids[0]}, {'$set': {'unavailable_stock': 3}})
    call(client, 2, 'GET', a['base'] + '/catalogue/home', expected=503)


def test_noncanonical_catalogue_has_no_snapshot_actions(client, catalogue):
    a, _, ids = catalogue
    db.institution_lending_config.update_one({'library_id': a['id']}, {'$set': {'state': 'LEGACY'}})
    row = book(client, a, ids[0]); assert row['requestable_count'] is None and not any(row['actions'].values())


def test_staff_catalogue_summary(client, catalogue):
    a, _, _ = catalogue; source = call(client, 1, 'GET', a['base'] + '/catalogue/source')
    assert source['local_book_count'] == 10 and not source['capabilities']['physical_actions']


def test_empty_staff_catalogue_summary(client, catalogue):
    _, b, _ = catalogue; assert call(client, 1, 'GET', b['base'] + '/catalogue/source')['local_book_count'] == 0


def test_staff_cannot_enter_patron_catalogue(client, catalogue):
    a, _, _ = catalogue
    for path in ['/home', '/books', '/genres']: call(client, 1, 'GET', a['base'] + '/catalogue' + path, expected=403)


def test_platform_authority_does_not_change_catalogue_actions(client, catalogue):
    a, _, _ = catalogue
    db.platform_role_assignments.insert_one({'user_id': 1, 'role': 'PLATFORM_ADMIN', 'status': 'ACTIVE', 'approved_by': 'test', 'approval_ref': 'test', 'approved_at': datetime.now(timezone.utc)})
    call(client, 1, 'GET', a['base'] + '/catalogue/home', expected=403)
    db.institution_memberships.update_one({'library_id': a['id'], 'user_id': 1}, {'$set': {'status': 'REMOVED'}})
    call(client, 1, 'GET', a['base'] + '/catalogue/source', expected=404)


def test_revocation_and_disabled_identity_fail_closed(client, catalogue):
    a, _, _ = catalogue
    db.institution_memberships.update_one({'library_id': a['id'], 'user_id': 2}, {'$set': {'status': 'SUSPENDED'}})
    call(client, 2, 'GET', a['base'] + '/catalogue/home', expected=404)
    db.users.update_one({'user_id': 3}, {'$set': {'is_active': False}})
    call(client, 3, 'GET', a['base'] + '/catalogue/source', expected=401)


def test_no_holdings_and_withdrawn_records_do_not_count(client, catalogue):
    a, _, _ = catalogue
    db.institution_holdings.delete_many({'library_id': a['id']})
    assert home(client, a)['source']['catalogue_source'] == 'GLOBAL_FALLBACK'


def test_cross_library_book_and_holding_ids_are_rejected(client, catalogue):
    a, b, ids = catalogue
    call(client, 2, 'GET', b['base'] + '/catalogue/books/' + ids[0], expected=404)
    db.institution_holdings.update_one({'library_book_id': ids[0]}, {'$set': {'library_id': b['id']}})
    assert page(client, a)['total'] == 9


def test_bounded_pagination_filters_and_literal_search(client, catalogue):
    a, _, _ = catalogue
    first = page(client, a, '?limit=3'); second = page(client, a, '?limit=3&offset=3')
    assert first['total'] == 10 and first['has_more'] and len(first['results']) == 3
    assert not {r['display_id'] for r in first['results']} & {r['display_id'] for r in second['results']}
    assert page(client, a, '?search=.*')['total'] == 0
    call(client, 2, 'GET', a['base'] + '/catalogue/books?limit=51', expected=422)


def test_query_count_is_constant_per_book_batch(client, catalogue, monkeypatch):
    a, _, _ = catalogue
    from backend.services import library_catalogue_experience as service
    calls = []
    original = service.collection
    class Tracked:
        def __init__(self, inner, name): self.inner, self.name = inner, name
        def __getattr__(self, key):
            value = getattr(self.inner, key)
            if key in {'find', 'find_one', 'count_documents', 'aggregate'}:
                def record(*args, **kwargs): calls.append((self.name, key)); return value(*args, **kwargs)
                return record
            return value
    monkeypatch.setattr(service, 'collection', lambda name: Tracked(original(name), name))
    page(client, a, '?limit=1'); one = len(calls); calls.clear()
    page(client, a, '?limit=10'); ten = len(calls)
    assert one == ten, (one, ten)
    assert not any(name == 'holdings' and operation == 'find_one' for name, operation in calls)


def test_private_data_never_sent_to_global_services(client, catalogue, monkeypatch):
    a, _, _ = catalogue
    import requests
    monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: pytest.fail('Local catalogue called a global index/service.'))
    assert home(client, a)['source']['catalogue_source'] == 'LIBRARY_LOCAL'
    assert page(client, a, '?search=Ada')['total'] == 5
