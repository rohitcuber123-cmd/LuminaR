import duckdb
import pytest
from backend.services.library_isbn_lookup import isbn_candidates
from backend.services.library_catalogue_identity import compatible
from scripts.inventory_v2a_migration import plan, apply_plan
from scripts.reconcile_inventory_v2a import reconcile


def test_real_read_only_isbn_lookup_unique_and_ambiguous(tmp_path, monkeypatch):
    path = tmp_path / 'isbn.duckdb'
    with duckdb.connect(str(path)) as connection:
        connection.execute('CREATE TABLE isbn_lookup (isbn VARCHAR, work_id VARCHAR)')
        connection.execute("INSERT INTO isbn_lookup VALUES ('9780306406157','OL1'),('0306406152','OL1'),('0306406152','OL2')")
    monkeypatch.setenv('ISBN_LOOKUP_DB', str(path))
    assert isbn_candidates(['9780306406157', '0306406152']) == {'9780306406157': 'OL1'}
    assert not compatible({'title': 'Physics', 'authors': ['Alpha']}, {'title': 'Physics', 'authors': ['Beta']})
    assert compatible({'title': '  Physics ', 'authors': []}, {'title': 'physics', 'authors': ['Beta']})


def test_migration_known_barcode_unverified_and_existing_quantity_policy(register, database, create):
    library_id = register()
    first = create(library_id, global_work_id='OL-Networks')
    database.library_inventory.insert_one({'library_id': 'LIB001', 'work_id': 'OL-Networks', 'total_copies': 2, 'available_copies': 1, 'barcode': 'KNOWN-OLD-001'})
    proposed = plan(database, library_id, [f'LIB001={library_id}'])
    result = apply_plan(database, proposed, 'increase_quantity')
    assert result['counts']['increased_holdings'] == 1
    copy = database.institution_copies.find_one({'library_id': library_id})
    assert copy['barcode'] == 'KNOWN-OLD-001' and copy['status'] == 'UNVERIFIED'
    assert copy['library_book_id'] == first['library_book_id']
    assert reconcile(database, library_id)['status'] == 'PASS'
    assert apply_plan(database, plan(database, library_id), 'increase_quantity')['counts']['increased_holdings'] == 0


def test_reconciliation_malformed_accession_reports_without_crashing(register, create, database):
    library_id = register(); create(library_id)
    database.institution_library_books.update_one({'library_id': library_id}, {'$set': {'accession_sequence': 'broken'}})
    result = reconcile(database, library_id)
    assert result['status'] == 'FAIL'
    assert 'ACCESSION_FORMAT_OR_PREFIX_MISMATCH' in {e['reason'] for e in result['errors']}


@pytest.mark.parametrize('change', [{'is_active': False}, {'is_email_verified': False}, {'password_setup_required': True}])
def test_inventory_current_account_revocation_blocks_read_write_and_apply(register, create, preview, client, database, change):
    library_id = register(); create(library_id)
    job = preview(library_id, 'title,subject\nRevocation Test,Systems\n')
    database.users.update_one({'user_id': 1}, {'$set': change})
    base = f'/libraries/{library_id}/inventory'
    assert client.get(base + '/books').status_code == 401
    assert client.post(base + '/books', json={'title': 'Denied', 'subjects': ['Systems']}).status_code == 401
    assert client.post(base + f'/imports/{job["import_id"]}/apply', json={}).status_code == 401
    assert database.institution_library_books.count_documents({'library_id': library_id}) == 1


def test_migration_invalid_list_metadata_is_quarantined_per_row(register, database):
    library_id = register()
    database.library_inventory.insert_many([
        {'library_id': 'LIB001', 'title': 'Invalid subject', 'subjects': [123]},
        {'library_id': 'LIB001', 'title': 'Invalid author', 'subjects': ['Systems'], 'authors': [456]},
        {'library_id': 'LIB001', 'title': 'Valid local record', 'subject': 'Systems'}])
    result = plan(database, library_id, [f'LIB001={library_id}'])
    assert result['counts']['errors'] == 2
    assert [r['status'] for r in result['rows']] == ['INVALID_METADATA', 'INVALID_METADATA', 'READY']
    assert database.institution_library_books.count_documents({}) == 0
