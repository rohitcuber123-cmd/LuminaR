from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import io
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
import pytest
from openpyxl import Workbook
from backend.services.institution_repository import now, audit
from backend.services.library_catalogue_repository import TenantInventory, ensure_indexes
from scripts.inventory_v2a_migration import plan, apply_plan
from scripts.reconcile_inventory_v2a import reconcile


@pytest.mark.parametrize('title_column,subject_column', [('title', 'subject'), ('book_title', 'genre'), ('name', 'category'), ('title', 'subjects')])
def test_minimum_import_column_aliases_no_identifiers_no_preview_accession(register, preview, commit, database, title_column, subject_column):
    library_id = register(); job = preview(library_id, f'{title_column},{subject_column}\nNetworks,Networking\nManual,Operating Systems\n')
    assert job['rows_valid'] == 2 and job['rows_invalid'] == 0
    assert {row['classification'] for row in job['rows']} == {'NEW_LOCAL'}
    assert database.institution_sequences.count_documents({}) == database.institution_library_books.count_documents({}) == 0
    result = commit(library_id, job); assert result['created_records'] == 2
    assert all(row.get('accession_number') for row in result['rows'])
    assert all(row['isbn_13'] is None and row['global_work_id'] is None for row in database.institution_library_books.find({}))
    assert database.institution_copies.count_documents({}) == 0


@pytest.mark.parametrize('count', [100, 1000])
def test_large_minimum_import_auto_numbering_idempotence_and_reconciliation(register, preview, commit, database, count):
    library_id = register()
    text = 'title,subject\n' + ''.join(f'Manual {i},Systems\n' for i in range(count))
    job = preview(library_id, text); assert job['rows_valid'] == count
    result = commit(library_id, job); assert result['created_records'] == count
    assert len({r['accession_number'] for r in result['rows']}) == count
    assert len({r['library_book_id'] for r in result['rows']}) == count
    assert commit(library_id, job) == result
    assert database.institution_sequences.find_one({'library_id': library_id})['value'] == count
    assert reconcile(database, library_id)['status'] == 'PASS'


def test_mixed_identifiers_subject_delimiters_optional_metadata_and_row_error_isolation(register, preview, commit, database):
    library_id = register()
    job = preview(library_id, 'title,genre,work_id,isbn,authors,publisher,year,copies,shelf,call_number,tags\nComputer Networks,Networking,OL-Networks,,Forouzan,,2020,2,S1,QA1,a;b\nPhysics,Physics,,9780306406157,,,,1,,,\nLocal Manual,Systems;Lab,,,,,,,,,\n,Research,,,,,,,,,\nNo Subject,,,,,,,,,,\nBad Year,Research,,,,,not-a-year,,,,\n')
    assert job['rows_valid'] == 3 and job['rows_invalid'] == 3
    assert job['rows'][0]['classification'] == 'GLOBAL_MATCH'
    assert job['rows'][2]['subjects'] == ['Systems', 'Lab']
    result = commit(library_id, job)
    assert result['status'] == 'PARTIAL' and result['created_records'] == result['invalid_rows'] == 3
    assert database.institution_holdings.count_documents({}) == 3
    assert database.books.count_documents({}) == 2


def test_same_title_no_silent_merge_preview_possible_duplicate(register, preview, commit, database):
    library_id = register(); job = preview(library_id, 'title,subject\nAnnual Report,Research\nAnnual Report,Research\nAnnual Report,History\n')
    assert [row['classification'] for row in job['rows']] == ['NEW_LOCAL', 'POSSIBLE_DUPLICATE', 'POSSIBLE_DUPLICATE']
    assert commit(library_id, job)['created_records'] == 3
    assert database.institution_library_books.count_documents({}) == 3


@pytest.mark.parametrize('policy,expected', [('skip', 1), ('increase_quantity', 3)])
def test_strong_verified_identity_import_policy_explicit_and_idempotent(register, create, preview, commit, database, policy, expected):
    library_id = register(); first = create(library_id, global_work_id='OL-Networks')
    job = preview(library_id, 'title,subject,work_id,copies\nImported label,Networking,OL-Networks,2\n')
    assert job['existing_holdings'] == 1
    result = commit(library_id, job, policy)
    assert result['created_records'] == 0
    assert database.institution_holdings.find_one({'library_id': library_id})['total_copies'] == expected
    assert commit(library_id, job, policy) == result
    assert database.institution_sequences.find_one({'library_id': library_id})['value'] == 1


def test_same_work_within_file_detected_and_skipped_without_new_accession(register, preview, commit, database):
    library_id = register(); job = preview(library_id, 'title,subject,work_id\nNetworks,Networking,OL-Networks\nAnother label,Networking,OL-Networks\n')
    assert job['rows'][1]['classification'] == 'EXISTING_HOLDING'
    result = commit(library_id, job)
    assert result['created_records'] == result['skipped_existing'] == 1
    assert database.institution_sequences.find_one({'library_id': library_id})['value'] == 1


def test_csv_encoding_bom_xlsx_and_formula_not_executed(register, preview, commit, database):
    library_id = register(); job = preview(library_id, '\ufefftitle,genre\n=HYPERLINK("x"),Research\n')
    assert commit(library_id, job)['created_records'] == 1
    assert database.institution_library_books.find_one({})['title'].startswith('=')
    workbook = Workbook(); sheet = workbook.active; sheet.append(['title', 'subject', 'year']); sheet.append(['XLSX Manual', 'Systems', 2020]); sheet.append(['=1+1', 'Research', None])
    content = io.BytesIO(); workbook.save(content)
    job = preview(library_id, content.getvalue(), filename='inventory.xlsx')
    assert job['rows_valid'] == 1 and job['rows_invalid'] == 1


@pytest.mark.parametrize('text', ['title,subject,library_id\nx,y,spoof\n', 'title,name,subject\nx,y,z\n', 'title,title,subject\nx,y,z\n',
                                'title,subject,accession_number\nx,y,FAKE1\n', 'title\nx\n'])
def test_spoofing_and_ambiguous_or_missing_columns_rejected(client, register, text):
    library_id = register()
    response = client.post(f'/libraries/{library_id}/inventory/imports/preview', files={'file': ('inventory.csv', text, 'text/csv')})
    assert response.status_code == 422


def test_file_row_column_and_encoding_bounds(client, register, database):
    library_id = register(); path = f'/libraries/{library_id}/inventory/imports/preview'
    for text, status in [(b'\xff\xfe', 422), (b'x' * (5 * 1024 * 1024 + 200000), 413),
                         (('title,subject\n' + 'x,y\n' * 2001).encode(), 413),
                         ((','.join('c' + str(i) for i in range(41)) + '\n').encode(), 422)]:
        assert client.post(path, files={'file': ('inventory.csv', text, 'text/csv')}).status_code == status
    assert database.institution_library_books.count_documents({}) == 0


def test_preview_is_bound_to_library_account_expiry_and_rechecks_staff(client, register, preview, h, database):
    a = register(); b = register(owner=2); job = preview(a, 'title,subject\nx,y\n')
    path = f'/libraries/{a}/inventory/imports/{job["import_id"]}/apply'
    database.institution_memberships.insert_one({'membership_id': str(uuid4()), 'library_id': a, 'user_id': 3, 'role': 'LIBRARIAN', 'status': 'ACTIVE'})
    assert client.post(path, headers=h(3), json={}).status_code == 404
    assert client.post(path.replace(a, b), headers=h(2), json={}).status_code == 404
    assert client.get(path.removesuffix('/apply').replace(a, b), headers=h(2)).status_code == 404
    database.institution_memberships.update_one({'library_id': a, 'user_id': 1}, {'$set': {'role': 'GENERAL_USER'}})
    assert client.post(path, json={}).status_code == 403
    database.institution_memberships.update_one({'library_id': a, 'user_id': 1}, {'$set': {'role': 'ADMIN'}})
    database.institution_inventory_imports.update_one({'import_id': job['import_id']}, {'$set': {'expires_at': now() - timedelta(seconds=1)}})
    assert client.post(path, json={}).status_code == 410


def test_apply_revalidates_global_link_and_duplicate_changes_since_preview(client, register, preview, create, commit, database):
    library_id = register(); job = preview(library_id, 'title,subject,work_id\nNetworks,Networking,OL-Networks\n')
    create(library_id, global_work_id='OL-Networks')
    assert commit(library_id, job)['skipped_existing'] == 1
    job = preview(library_id, 'title,subject,work_id\nSystems,Systems,OL-Systems\n')
    database.books.delete_one({'work_id': 'OL-Systems'})
    result = commit(library_id, job); assert result['status'] == 'PARTIAL' and result['invalid_rows'] == 1 and result['created_records'] == 0


def test_concurrent_import_two_libraries_independent_sequences(register, preview, commit, database, h):
    a = register(); b = register(owner=2, name='Orion Institute')
    text = 'title,subject\n' + ''.join(f'Book {i},Systems\n' for i in range(100))
    jobs = [(a, preview(a, text), None), (b, preview(b, text, headers=h(2)), h(2))]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda item: commit(item[0], item[1], headers=item[2]), jobs))
    assert all(r['created_records'] == 100 for r in results)
    assert all(row['accession_number'].startswith('AUR-') for row in results[0]['rows'])
    assert all(row['accession_number'].startswith('ORI-') for row in results[1]['rows'])
    assert reconcile(database, a)['status'] == reconcile(database, b)['status'] == 'PASS'


def test_concurrent_two_imports_same_library_no_duplicate_numbers(register, preview, commit, database):
    library_id = register(); jobs = [preview(library_id, f'title,subject\nManual {i},Systems\n') for i in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda job: commit(library_id, job), jobs))
    assert all(r['created_records'] == 1 for r in results)
    assert len({r['rows'][0]['accession_number'] for r in results}) == 2


def test_new_inventory_audit_whitelist_does_not_dump_rows_or_nested_secrets(register, create, preview, commit, database):
    library_id = register(); create(library_id); commit(library_id, preview(library_id, 'title,subject\nOther,Lab\n'))
    audit(library_id, 'TEST', 1, metadata={'counts': {'created': 1, 'access_code': 'SECRET'}, 'dataset': 'SECRET'})
    records = list(database.institution_audit.find({'library_id': library_id}, {'_id': 0}))
    text = json.dumps(records, default=str)
    assert 'SECRET' not in text and 'dataset' not in text
    events = {r['event'] for r in records}
    assert {'LIBRARY_BOOK_CREATED', 'HOLDING_CREATED', 'INVENTORY_IMPORT_STARTED', 'INVENTORY_IMPORT_COMPLETED'} <= events
    assert any(r['metadata'].get('library_book_id') for r in records)


def legacy_rows(database):
    database.library_inventory.insert_many([
        {'library_id': 'LIB001', 'work_id': 'OL-Networks', 'total_copies': 3, 'available_copies': 2},
        {'library_id': 'LIB001', 'title': 'Physics', 'subject': 'Physics', 'isbn': '9780306406157', 'total_copies': 1, 'available_copies': 1},
        {'library_id': 'LIB001', 'title': 'Local Proceedings', 'genre': 'Research', 'quantity': 2},
        {'library_id': 'LIB001', 'title': 'Missing subject'}, {'library_id': 'LIB001', 'subject': 'Research'},
        {'library_id': 'AMBIG', 'title': 'Ambiguous', 'subject': 'Research'}])


def test_migration_explicit_alias_missing_fields_dry_apply_repeat_preserve_legacy(register, database):
    library_id = register(); legacy_rows(database)
    original = list(database.library_inventory.find({})); collections = database.list_collection_names()
    proposed = plan(database, library_id, [f'LIB001={library_id}'])
    assert database.list_collection_names() == collections and list(database.library_inventory.find({})) == original
    assert proposed['counts']['missing_title'] == proposed['counts']['missing_subject'] == proposed['counts']['ambiguous_library'] == 1
    assert sum(row['status'] == 'READY' for row in proposed['rows']) == 3
    result = apply_plan(database, proposed)
    assert result['counts']['created_records'] == result['counts']['accession_numbers_generated'] == 3
    assert list(database.library_inventory.find({})) == original
    assert database.institution_library_aliases.find_one({'legacy_library_id': 'LIB001'})['canonical_library_id'] == library_id
    repeated = apply_plan(database, plan(database, library_id))
    assert repeated['counts']['created_records'] == 0 and database.institution_sequences.find_one({'library_id': library_id})['value'] == 3
    assert reconcile(database, library_id)['status'] == 'PASS'
    assert database.issues.count_documents({}) == database.fines.count_documents({}) == 0


def test_migration_alias_ambiguous_and_cross_library_not_guessed(register, database):
    a = register(); b = register(owner=2); legacy_rows(database)
    assert plan(database, a)['counts']['ambiguous_library'] == 6
    ambiguous = plan(database, a, [f'LIB001={a}', f'LIB001={b}'])
    assert ambiguous['counts']['ambiguous_library'] == 6
    scoped = plan(database, b, [f'LIB001={a}'])
    assert not any(row['status'] == 'READY' for row in scoped['rows'])
    assert apply_plan(database, scoped)['counts']['created_records'] == 0


def test_real_cli_dry_run_no_collection_or_index_side_effects_and_assignment_idempotence(register, database):
    library_id = register(); legacy_rows(database)
    before = {name: list(database[name].list_indexes()) for name in database.list_collection_names()}
    command = [sys.executable, 'scripts/assign_library_book_ids.py', '--database', database.name, '--library-id', library_id, '--alias', f'LIB001={library_id}']
    run = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)['mode'] == 'DRY_RUN'
    assert {name: list(database[name].list_indexes()) for name in database.list_collection_names()} == before
    run = subprocess.run(command + ['--apply'], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)['counts']['created_records'] == 3
    repeated = subprocess.run(command + ['--apply'], capture_output=True, text=True, timeout=30)
    assert repeated.returncode == 0 and json.loads(repeated.stdout)['counts']['created_records'] == 0


def test_reconciliation_detects_foreign_refs_invalid_quantity_and_sequence(register, create, database):
    a = register(); b = register(owner=2); first = create(a); second = create(b, actor=2)
    database.institution_holdings.update_one({'library_id': a}, {'$set': {'library_book_id': second['library_book_id'], 'available_copies': 99}})
    database.institution_sequences.update_one({'library_id': a}, {'$set': {'value': 0}})
    result = reconcile(database, a)
    assert result['status'] == 'FAIL'
    reasons = {row['reason'] for row in result['errors']}
    assert {'MISSING_OR_CROSS_LIBRARY_BOOK', 'INVALID_QUANTITIES', 'SEQUENCE_BELOW_ISSUED_ACCESSIONS'} <= reasons


def test_indexes_unique_idempotent_without_dropping_existing(register, database):
    ensure_indexes(); before = {name: list(database[name].list_indexes()) for name in database.list_collection_names()}
    ensure_indexes()
    assert {name: list(database[name].list_indexes()) for name in database.list_collection_names()} == before
    assert any(i.get('unique') and dict(i['key']) == {'library_id': 1, 'accession_number': 1} for i in database.institution_library_books.list_indexes())
