from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import io
import json
from pathlib import Path
import subprocess
import sys
from uuid import UUID, uuid4
import pytest
from openpyxl import Workbook
from pydantic import ValidationError
from backend.schemas.library_catalogue import BookCreate, BookUpdate, HoldingUpdate, normalize_isbn
from backend.services.institution_repository import now
from backend.services.library_catalogue_repository import TenantInventory, ensure_indexes
from scripts.inventory_v2a_migration import plan, apply_plan
from scripts.reconcile_inventory_v2a import reconcile


@pytest.mark.parametrize('body', [{'title': '', 'subjects': ['x']}, {'title': ' ', 'subjects': ['x']}, {'subjects': ['x']},
                                  {'title': 'Manual'}, {'title': 'Manual', 'subjects': []}, {'title': 'Manual', 'subjects': ['  ']},
                                  {'title': 'x' * 501, 'subjects': ['x']}, {'title': 'x', 'subjects': ['s' * 201]}])
def test_library_book_requires_title_and_subject(body):
    with pytest.raises(ValidationError):
        BookCreate.model_validate(body)


@pytest.mark.parametrize('field', ['authors', 'isbn', 'global_work_id', 'publisher', 'publication_year', 'edition', 'language', 'description'])
def test_only_title_subject_required_optional_metadata_and_default_quantity_one(field, client, register, database):
    library_id = register(); response = client.post(f'/libraries/{library_id}/inventory/books', json={'title': '  Local Manual!  ', 'subjects': [' Systems ', 'Lab', 'Systems']})
    assert response.status_code == 201, response.text
    row = response.json(); assert row['title'] == 'Local Manual!' and row['subjects'] == ['Systems', 'Lab']
    assert UUID(row['library_book_id']) and row['accession_number'] == 'AUR-000001'
    assert row['holding']['total_copies'] == row['holding']['available_copies'] == 1
    assert row['global_work_id'] is None and row['isbn_10'] is None and row['isbn_13'] is None and row['authors'] == []
    assert database.books.count_documents({}) == 2 and database.users.find_one({'user_id': 1})['role'] == 'GENERAL_USER'


@pytest.mark.parametrize('isbn,expected', [('0-306-40615-2', '0306406152'), ('978-0-306-40615-7', '9780306406157'), ('0-8044-2957-X', '080442957X'), (None, None), ('', None)])
def test_isbn_optional_check_digits_and_normalization(isbn, expected):
    assert normalize_isbn(isbn) == expected


@pytest.mark.parametrize('isbn', ['1234567890', '9780306406158', '123-abc', '９７８０３０６４０６１５７', '9791234567890', '978030640615X'])
def test_malformed_isbn_not_verified(isbn):
    with pytest.raises(ValueError):
        normalize_isbn(isbn)


@pytest.mark.parametrize('copies,available', [(-1, 0), (1, -1), (1, 2), (1.5, 1), (True, 1)])
def test_quantity_invariants(copies, available):
    with pytest.raises(ValidationError):
        BookCreate(title='x', subjects=['x'], copies=copies, available_copies=available)


def test_zero_quantity_and_optional_fields_without_placeholder(create):
    row = create(copies=0, authors=[], publisher=None, publication_year=None, edition=None, language=None, description=None)
    assert row['holding']['total_copies'] == row['holding']['available_copies'] == 0
    assert row['authors'] == [] and row['publisher'] is None and row['publication_year'] is None


@pytest.mark.parametrize('field,value', [('library_id', str(uuid4())), ('library_book_id', str(uuid4())), ('accession_number', 'FAKE-1'),
                                       ('accession_sequence', 999), ('created_by_user_id', 99), ('holding_id', str(uuid4())), ('role', 'ADMIN')])
def test_client_identity_accession_and_actor_spoof_rejected(client, register, field, value):
    library_id = register()
    response = client.post(f'/libraries/{library_id}/inventory/books', json={'title': 'x', 'subjects': ['x'], field: value})
    assert response.status_code == 422


def test_work_id_link_valid_invalid_and_later_link_stable(client, register, create, database):
    library_id = register(); row = create(library_id, global_work_id='OL-Networks')
    assert row['global_work_id'] == 'OL-Networks' and database.books.count_documents({}) == 2
    bad = client.post(f'/libraries/{library_id}/inventory/books', json={'title': 'Valid Local', 'subjects': ['x'], 'global_work_id': 'NO-WORK'})
    assert bad.status_code == 422
    local = create(library_id, title='Operating Systems')
    path = f'/libraries/{library_id}/inventory/books/{local["library_book_id"]}/global-link'
    linked = client.put(path, json={'global_work_id': 'OL-Systems'}).json()
    assert linked['library_book_id'] == local['library_book_id'] and linked['accession_number'] == local['accession_number']
    assert client.put(path, json={'global_work_id': None}).json()['global_work_id'] is None
    assert client.patch(path.removesuffix('/global-link'), json={'global_work_id': 'OL-Systems'}).status_code == 422


def test_title_only_does_not_link_or_merge_and_duplicates_are_flagged(client, register, create, database):
    library_id = register(); first = create(library_id, title='Computer Networks'); second = create(library_id, title='Computer Networks')
    assert first['global_work_id'] is None and second['global_work_id'] is None
    assert second['library_book_id'] != first['library_book_id'] and second['needs_review']
    third = create(library_id, title='Computer Networks', subjects=['Literature'])
    assert third['library_book_id'] != second['library_book_id']
    assert database.institution_library_books.count_documents({'library_id': library_id}) == 3


def test_strong_duplicate_work_or_compatible_isbn_detected(client, register, create):
    library_id = register(); first = create(library_id, global_work_id='OL-Networks')
    assert client.post(f'/libraries/{library_id}/inventory/books', json={'title': 'Other local label', 'subjects': ['x'], 'global_work_id': 'OL-Networks'}).status_code == 409
    second = create(library_id, title='Physics', isbn='9780306406157')
    assert client.post(f'/libraries/{library_id}/inventory/books', json={'title': 'Physics', 'subjects': ['Physics'], 'isbn': '9780306406157'}).status_code == 409
    different = create(library_id, title='Separate research record', isbn='9780306406157')
    assert different['library_book_id'] != second['library_book_id']


def test_optional_isbn_lookup_unavailable_keeps_local_and_trusted_match_links(client, register, create, monkeypatch):
    library_id = register(); local = create(library_id, title='Computer Networks', isbn='9780306406157')
    assert local['isbn_13'] == '9780306406157' and local['global_work_id'] is None
    from backend.services import library_catalogue_service as service
    monkeypatch.setattr(service, 'isbn_candidates', lambda values: {'9780804429573': 'OL-Systems'})
    linked = create(library_id, title='Operating Systems', isbn='9780804429573')
    assert linked['global_work_id'] == 'OL-Systems'


def test_accession_independent_stable_prefix_not_reused_beyond_six_digits(client, register, create, database):
    a = register(); b = register(owner=2, name='Orion Institute')
    first = create(a); other = create(b, actor=2)
    assert first['accession_number'] == 'AUR-000001' and other['accession_number'] == 'ORI-000001'
    assert client.delete(f'/libraries/{a}/inventory/books/{first["library_book_id"]}').status_code == 200
    client.patch(f'/libraries/{a}', json={'name': 'Completely Renamed'})
    assert create(a)['accession_number'] == 'AUR-000002'
    database.institution_sequences.update_one({'library_id': a}, {'$set': {'value': 999999}})
    assert create(a)['accession_number'] == 'AUR-1000000'
    assert client.get(f'/libraries/{a}/inventory/books?state=withdrawn').json()['total'] == 1


@pytest.mark.parametrize('workers', [10, 100])
def test_accession_atomic_concurrent_allocation(register, database, workers):
    library_id = register(); library = database.institution_libraries.find_one({'library_id': library_id})
    with ThreadPoolExecutor(max_workers=workers) as pool:
        values = list(pool.map(lambda _: TenantInventory(library_id).accession(library), range(workers)))
    assert len({v[0] for v in values}) == len({v[1] for v in values}) == workers
    assert sorted(v[0] for v in values) == list(range(1, workers + 1))


def test_ten_concurrent_book_creations_unique(client, register, database):
    library_id = register()
    with ThreadPoolExecutor(max_workers=10) as pool:
        rows = list(pool.map(lambda i: client.post(f'/libraries/{library_id}/inventory/books', json={'title': f'Book {i}', 'subjects': ['x']}), range(10)))
    assert all(row.status_code == 201 for row in rows), [r.status_code for r in rows]
    assert len({row.json()['accession_number'] for row in rows}) == 10
    assert database.institution_holdings.count_documents({'library_id': library_id}) == 10


def test_failed_validation_and_duplicate_do_not_reuse_identity_or_sequence(client, register, create, database):
    library_id = register(); create(library_id, global_work_id='OL-Networks')
    assert client.post(f'/libraries/{library_id}/inventory/books', json={'title': 'bad', 'subjects': []}).status_code == 422
    assert client.post(f'/libraries/{library_id}/inventory/books', json={'title': 'duplicate', 'subjects': ['x'], 'global_work_id': 'OL-Networks'}).status_code == 409
    assert database.institution_sequences.find_one({'library_id': library_id})['value'] == 1
    assert create(library_id, title='New')['accession_number'] == 'AUR-000002'


def test_metadata_edit_holding_invariants_and_no_legacy_dual_write(client, register, create, database):
    library_id = register(); row = create(library_id, copies=3, available_copies=2)
    database.library_inventory.insert_one({'library_id': 'LIB001', 'work_id': 'OL-Networks', 'total_copies': 9, 'available_copies': 7})
    path = f'/libraries/{library_id}/inventory/books/{row["library_book_id"]}'
    updated = client.patch(path, json={'title': 'Edited', 'subjects': ['Lab'], 'shelf_location': 'S2', 'isbn': '9780306406157'}).json()
    assert updated['accession_number'] == row['accession_number'] and updated['holding']['shelf_location'] == 'S2'
    assert client.put(path + '/holding', json={'total_copies': 1, 'available_copies': 2}).status_code == 422
    assert client.put(path + '/holding', json={'total_copies': 0, 'available_copies': 0}).status_code == 200
    assert client.patch(path, json={'title': None}).status_code == 422
    assert database.library_inventory.find_one({})['available_copies'] == 7
    assert database.issues.count_documents({}) == 0


def test_copy_foundation_optional_barcode_and_same_tenant_references(client, register, create, database):
    a = register(); b = register(owner=2)
    row = create(a, copies=3, barcode='A-BAR-1')
    path = f'/libraries/{a}/inventory/books/{row["library_book_id"]}/copies'
    assert len(client.get(path).json()['results']) == 1
    second = client.post(path, json={}).json(); assert second['barcode'] is None and second['copy_number'] == 2
    assert client.post(path, json={'barcode': 'A-BAR-1'}).status_code == 409
    assert client.post(path, json={'status': 'BORROWED'}).status_code == 422
    assert client.post(f'/libraries/{b}/inventory/books/{row["library_book_id"]}/copies', json={}).status_code == 404
    assert client.put(path.removesuffix('/copies') + '/holding', json={'total_copies': 1, 'available_copies': 1}).status_code == 409
    assert database.institution_copies.count_documents({'library_id': a}) == 2


@pytest.mark.parametrize('role', ['ADMIN', 'LIBRARIAN', 'GENERAL_USER'])
def test_current_membership_roles_and_private_cross_library_guards(client, register, create, h, database, role):
    a = register(private=True); b = register(owner=2, private=True)
    row = create(a)
    database.institution_memberships.insert_one({'membership_id': str(uuid4()), 'library_id': a, 'user_id': 3, 'role': role, 'status': 'ACTIVE'})
    path = f'/libraries/{a}/inventory/books'
    assert client.get(path, headers=h(3)).status_code == 200
    assert client.post(path, headers=h(3), json={'title': 'Another', 'subjects': ['x']}).status_code == (403 if role == 'GENERAL_USER' else 201)
    assert client.get(f'/libraries/{b}/inventory/books', headers=h(3)).status_code == 404
    assert client.get(path, headers=h(4, 'ADMIN')).status_code == 404
    assert client.patch(f'/libraries/{b}/inventory/books/{row["library_book_id"]}', headers=h(3), json={'title': 'attack'}).status_code == 404
    assert client.get(f'/libraries/{b}/inventory/books/{row["library_book_id"]}', headers=h(2)).status_code == 404
    assert client.post('/inventory/', headers=h(3), json={'library_id': 'LIB001', 'work_id': 'OL-Networks'}).status_code == 410
    assert client.post('/books/', headers=h(3), json={'title': 'attack'}).status_code in (403, 422, 405, 307)


@pytest.mark.parametrize('status', ['SUSPENDED', 'REMOVED'])
def test_private_inventory_membership_loss_denied(client, register, h, database, status):
    library_id = register(private=True)
    database.institution_memberships.insert_one({'membership_id': str(uuid4()), 'library_id': library_id, 'user_id': 3, 'role': 'LIBRARIAN', 'status': status})
    assert client.get(f'/libraries/{library_id}/inventory/books', headers=h(3)).status_code == 404


def test_tenant_repository_requires_uuid_and_rejects_cross_tenant(register):
    with pytest.raises((TypeError, ValueError)):
        TenantInventory(None)
    repo = TenantInventory(register())
    with pytest.raises(ValueError):
        repo.one('library_books', {'library_id': str(uuid4())})


def test_local_inventory_search_filters_and_safe_text(client, register, create):
    library_id = register(); row = create(library_id, title='<script>alert(1)</script> Networks', subjects=['Networking'], authors=['Forouzan'], isbn='9780306406157', local_call_number='QA-77')
    create(library_id, title='Global work', global_work_id='OL-Systems')
    for query in ['script', 'networking', 'Forouzan', '9780306406157', 'AUR-000001', 'QA-77']:
        result = client.get(f'/libraries/{library_id}/inventory/books', params={'search': query}).json()
        assert len(result['results']) == 1
    assert client.get(f'/libraries/{library_id}/inventory/books?kind=local').json()['total'] == 1
    assert client.get(f'/libraries/{library_id}/inventory/books?kind=global').json()['total'] == 1
    assert client.get(f'/libraries/{library_id}/inventory/books?search=.*').json()['total'] == 0
    assert client.get(f'/libraries/{library_id}/inventory/books?limit=101').status_code == 422
    assert client.get('/libraries/LIB001/inventory/books').status_code == 422
