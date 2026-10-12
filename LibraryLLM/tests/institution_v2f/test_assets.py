import hashlib
import json
import os
from datetime import timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from backend.schemas.library_assets import AssetUpdate, LibraryDigitalAsset
from backend.services import library_asset_service as assets
from backend.services.institution_repository import collection, library_mutation, now


def member(client, library_id, user=2):
    response = client.post(f'/libraries/{library_id}/join', headers={'x-test-user': str(user)}, json={})
    assert response.status_code == 200, response.text


def grant(library_id, user, role):
    collection('memberships').insert_one({'membership_id': str(uuid4()), 'library_id': library_id,
        'user_id': user, 'role': role, 'status': 'ACTIVE', 'joined_at': now(), 'created_at': now(), 'updated_at': now()})


def test_library_asset_has_canonical_uuid(library, upload, database):
    lib = library()
    response = upload(lib)
    assert response.status_code == 202, response.text
    row = response.json()
    assert str(UUID(row['asset_id'])) == row['asset_id']
    assert row['library_id'] == lib
    stored = database.institution_library_assets.find_one({'asset_id': row['asset_id']})
    assert LibraryDigitalAsset.model_validate(stored)
    assert 'storage_key' not in row and 'upload_id' not in row and 'active_generation_id' not in row
    assert row['status'] == 'PROCESSING' and row['processing_job']['state'] == 'QUEUED'


@pytest.mark.parametrize('role,user', [('ADMIN', 1), ('LIBRARIAN', 3)])
def test_staff_can_upload(library, upload, role, user):
    lib = library()
    if user != 1:
        grant(lib, user, role)
    response = upload(lib, user=user)
    assert response.status_code == 202


def test_fresh_guard_waits_for_current_authority_snapshot(library):
    lib = library()
    started = Event()
    def check_authority():
        started.set()
        return assets.fresh_guard(lib, {'sub': '1'}, staff=True)
    with ThreadPoolExecutor(max_workers=1) as executor:
        with library_mutation(lib, durable=True):
            pending = executor.submit(check_authority)
            assert started.wait(timeout=2)
            # Revocation commits before the waiting guard reads membership.
            collection('memberships').update_one({'library_id': lib, 'user_id': 1},
                {'$set': {'status': 'REVOKED'}})
        with pytest.raises(HTTPException) as denied:
            pending.result(timeout=5)
        assert denied.value.status_code == 404


def test_fresh_guard_locked_mode_reuses_existing_barrier(library):
    lib = library()
    with library_mutation(lib, durable=True):
        _, membership = assets.fresh_guard(lib, {'sub': '1'}, staff=True, locked=True)
        assert membership['role'] == 'ADMIN'


def test_general_user_cannot_upload(client, library, upload):
    lib = library()
    member(client, lib)
    assert upload(lib, user=2).status_code == 403


@pytest.mark.parametrize('user', [9, 10])
def test_legacy_and_platform_admin_cannot_upload(library, upload, database, user):
    lib = library()
    if user == 10:
        database.platform_role_assignments.insert_one({'user_id': user, 'role': 'PLATFORM_ADMIN', 'status': 'ACTIVE'})
    assert upload(lib, user=user).status_code == 404


@pytest.mark.parametrize('filename,content', [('other.txt', b'hello'), ('empty.pdf', b''),
    ('corrupt.pdf', b'%PDF-1.7\ncorrupt'), ('image.pdf', b'PNG'), ('../leak.pdf', None),
    ('..\\leak.pdf', None), ('/tmp/leak.pdf', None),
    ('hidden\x00.pdf', None), ('.hidden.pdf', None)])
def test_upload_rejects_unsafe_or_unsupported(library, upload, filename, content):
    lib = library()
    response = upload(lib, filename=filename, content=content)
    assert response.status_code in [400, 422], response.text
    assert collection(assets.ASSETS).count_documents({}) == 0


def test_upload_declared_oversize_rejected(client, library):
    response = client.post(f'/libraries/{library()}/assets', headers={'content-length': str(65 * 1024 * 1024)})
    assert response.status_code == 413


def test_same_upload_acknowledgement_retry_is_idempotent(library, upload):
    lib = library()
    upload_id = str(uuid4())
    first = upload(lib, upload_id=upload_id)
    repeated = upload(lib, upload_id=upload_id)
    assert first.json()['asset_id'] == repeated.json()['asset_id']
    assert collection(assets.ASSETS).count_documents({}) == 1
    assert collection(assets.JOBS).count_documents({}) == 1
    assert upload(lib, upload_id=upload_id, title='Different').status_code == 409


def test_same_library_duplicates_are_explicit_separate_assets(library, upload):
    lib = library()
    first, second = upload(lib).json(), upload(lib).json()
    assert first['asset_id'] != second['asset_id']
    assert second['duplicate_warning']
    assert first['checksum'] == second['checksum']


def test_identical_cross_library_checksum_namespace_is_separate(library, upload):
    first, second = upload(library()).json(), upload(library(owner=3), user=3).json()
    assert first['checksum'] == second['checksum']
    assert first['asset_id'] != second['asset_id']
    assert not second['duplicate_warning']
    p1 = assets.asset_directory(first['library_id'], first['asset_id'])
    p2 = assets.asset_directory(second['library_id'], second['asset_id'])
    assert p1 != p2 and p1.parent != p2.parent


@pytest.mark.parametrize('visibility,user,expected', [('MEMBERS', 2, 200), ('STAFF_ONLY', 2, 404),
    ('STAFF_ONLY', 1, 200), ('MEMBERS', 8, 404)])
def test_ready_asset_visibility(client, library, upload, ready, visibility, user, expected):
    lib = library()
    member(client, lib)
    asset = upload(lib, visibility=visibility).json()
    ready(asset)
    assert client.get(f"/libraries/{lib}/assets/{asset['asset_id']}", headers={'x-test-user': str(user)}).status_code == expected
    assert client.get(f"/libraries/{lib}/assets/{asset['asset_id']}/file", headers={'x-test-user': str(user)}).status_code == expected


@pytest.mark.parametrize('path_suffix', ['', '/file', '/reprocess'])
def test_cross_tenant_asset_uuid_denied(client, library, upload, ready, path_suffix):
    a, b = library(), library(owner=3)
    asset = upload(b, user=3).json()
    ready(asset)
    url = f"/libraries/{a}/assets/{asset['asset_id']}{path_suffix}"
    response = client.post(url) if path_suffix == '/reprocess' else client.get(url)
    assert response.status_code == 404


def test_patron_cannot_list_processing_or_staff_only(client, library, upload, ready):
    lib = library()
    member(client, lib)
    prepared = upload(lib).json()
    ready(prepared)
    upload(lib, visibility='STAFF_ONLY')
    upload(lib, title='Pending MEMBERS')
    result = client.get(f'/libraries/{lib}/assets', headers={'x-test-user': '2'}).json()
    assert result['total'] == 1 and result['results'][0]['asset_id'] == prepared['asset_id']
    assert client.get(f'/libraries/{lib}/assets?visibility=STAFF_ONLY', headers={'x-test-user': '2'}).json()['total'] == 0


def test_visibility_change_immediately_revokes_patron(client, library, upload, ready):
    lib = library()
    member(client, lib)
    asset = upload(lib).json()
    ready(asset)
    url = f"/libraries/{lib}/assets/{asset['asset_id']}"
    assert client.patch(url, json={'visibility': 'STAFF_ONLY'}).status_code == 200
    assert client.get(url, headers={'x-test-user': '2'}).status_code == 404
    assert client.get(url + '/file', headers={'x-test-user': '2'}).status_code == 404
    assert client.get(url).status_code == 200
    event = collection('audit').find_one({'event': 'ASSET_VISIBILITY_CHANGED'})
    assert event['metadata']['asset_id'] == asset['asset_id']
    assert event['metadata']['visibility'] == 'STAFF_ONLY'


@pytest.mark.parametrize('role,user', [('ADMIN', 1), ('LIBRARIAN', 3), ('GENERAL_USER', 2)])
def test_metadata_mutation_uses_membership_role(client, library, upload, role, user):
    lib = library()
    if user != 1:
        grant(lib, user, role)
    asset = upload(lib).json()
    response = client.patch(f"/libraries/{lib}/assets/{asset['asset_id']}",
        headers={'x-test-user': str(user)}, json={'title': 'Updated title'})
    assert response.status_code == (403 if role == 'GENERAL_USER' else 200)


@pytest.mark.parametrize('state', ['SUSPENDED', 'REMOVED'])
def test_library_lifecycle_denies_assets_and_restore_preserves(client, library, upload, ready, state):
    lib = library()
    asset = upload(lib).json()
    ready(asset)
    path = assets.asset_directory(lib, asset['asset_id'])
    before = {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}
    collection('libraries').update_one({'library_id': lib}, {'$set': {'status': state}})
    for suffix in ['', f"/{asset['asset_id']}", f"/{asset['asset_id']}/file"]:
        assert client.get(f'/libraries/{lib}/assets' + suffix).status_code == 404
    assert upload(lib).status_code == 404
    collection('libraries').update_one({'library_id': lib}, {'$set': {'status': 'ACTIVE'}})
    assert client.get(f"/libraries/{lib}/assets/{asset['asset_id']}/file").status_code == 200
    after = {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}
    assert before == after


@pytest.mark.parametrize('change', [{'status': 'REMOVED'}, {'status': 'SUSPENDED'}, {'role': 'LIBRARIAN'}])
def test_next_request_revalidates_membership(client, library, upload, ready, change):
    lib = library()
    member(client, lib)
    asset = upload(lib, visibility='STAFF_ONLY' if change.get('role') else 'MEMBERS').json()
    ready(asset)
    collection('memberships').update_one({'library_id': lib, 'user_id': 2}, {'$set': change})
    expected = 200 if change.get('role') else 404
    assert client.get(f"/libraries/{lib}/assets/{asset['asset_id']}/file", headers={'x-test-user': '2'}).status_code == expected


@pytest.mark.parametrize('field,value', [('is_active', False), ('is_email_verified', False), ('password_setup_required', True)])
def test_next_asset_access_revalidates_account(client, library, upload, ready, database, field, value):
    lib = library()
    asset = upload(lib).json()
    ready(asset)
    database.users.update_one({'user_id': 1}, {'$set': {field: value}})
    assert client.get(f"/libraries/{lib}/assets/{asset['asset_id']}/file").status_code == 401


def test_file_streaming_is_private_and_supports_range(client, library, upload, ready, pdf_bytes):
    lib = library()
    asset = upload(lib).json()
    ready(asset)
    response = client.get(f"/libraries/{lib}/assets/{asset['asset_id']}/file", headers={'Range': 'bytes=0-9'})
    assert response.status_code == 206
    assert response.content == pdf_bytes[:10]
    assert response.headers['cache-control'] == 'private, no-store'
    assert 'source.pdf' not in response.headers['content-disposition']


def test_same_library_book_link_allowed_global_reference_remains_metadata(client, library, upload):
    lib = library()
    book_id = str(uuid4())
    collection('library_books').insert_one({'library_id': lib, 'library_book_id': book_id,
        'title': 'Safe linked book', 'global_work_id': 'OL123W', 'status': 'ACTIVE'})
    asset = upload(lib, book_id=book_id).json()
    assert asset['library_book_id'] == book_id and asset['global_work_id'] == 'OL123W'
    assert asset['linked_book_title'] == 'Safe linked book'
    assert collection('library_assets').count_documents({'library_id': lib}) == 1


def test_cross_library_book_link_denied(client, library, upload):
    a, b = library(), library(owner=3)
    book_id = str(uuid4())
    collection('library_books').insert_one({'library_id': b, 'library_book_id': book_id, 'status': 'ACTIVE'})
    assert upload(a, book_id=book_id).status_code == 404
    asset = upload(a).json()
    assert client.patch(f"/libraries/{a}/assets/{asset['asset_id']}", json={'library_book_id': book_id}).status_code == 404


def test_local_only_book_link_and_unlink(client, library, upload):
    lib = library()
    book_id = str(uuid4())
    collection('library_books').insert_one({'library_id': lib, 'library_book_id': book_id, 'title': 'Local', 'status': 'ACTIVE'})
    asset = upload(lib, book_id=book_id).json()
    assert asset['global_work_id'] is None
    changed = client.patch(f"/libraries/{lib}/assets/{asset['asset_id']}", json={'library_book_id': None}).json()
    assert changed['library_book_id'] is None and changed['global_work_id'] is None


def test_bounded_search_filter_pagination(client, library, upload):
    lib = library()
    for title, visibility in [('Needle', 'MEMBERS'), ('Other', 'STAFF_ONLY'), ('Needle Two', 'MEMBERS')]:
        assert upload(lib, title=title, visibility=visibility).status_code == 202
    result = client.get(f'/libraries/{lib}/assets?search=needle&visibility=MEMBERS&status=PROCESSING&limit=1').json()
    assert result['total'] == 2 and len(result['results']) == 1
    other = client.get(f'/libraries/{lib}/assets?search=needle&limit=1&offset=1').json()
    assert result['results'][0]['asset_id'] != other['results'][0]['asset_id']
    assert client.get(f'/libraries/{lib}/assets?limit=101').status_code == 422
    assert client.get(f'/libraries/{lib}/assets?search=.%2A').json()['total'] == 0


def test_upload_db_insert_failure_keeps_orphan_non_public(library, upload, monkeypatch):
    lib = library()
    original = assets.collection
    class FailedInsert:
        def __getattr__(self, key):
            if key == 'insert_one':
                def fail(*args, **kwargs):
                    raise OSError('isolated persistence fault')
                return fail
            return getattr(original(assets.ASSETS), key)
    monkeypatch.setattr(assets, 'collection', lambda name: FailedInsert() if name == assets.ASSETS else original(name))
    assert upload(lib).status_code == 503
    assert original(assets.ASSETS).count_documents({}) == 0
    assert list(assets.storage_root().rglob('source.part'))
    assert not original('locks').find_one({'_id': lib})


def test_source_move_failure_is_failed_and_recoverable(library, upload, monkeypatch):
    lib = library()
    def fail(*args):
        raise OSError('isolated source move fault')
    monkeypatch.setattr(Path, 'replace', fail)
    assert upload(lib).status_code == 503
    row = collection(assets.ASSETS).find_one({})
    assert row['status'] == 'FAILED' and row['error_code'] == 'UPLOAD_PERSISTENCE_FAILED'
    assert (assets.asset_directory(lib, row['asset_id']) / 'source.part').exists()


def test_source_write_failure_never_publishes(library, upload, monkeypatch):
    lib = library()
    original = Path.open
    def fail_source(path, mode='r', *args, **kwargs):
        if path.name == 'source.part' and mode == 'xb':
            raise OSError('isolated disk write fault')
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', fail_source)
    assert upload(lib).status_code == 503
    assert collection(assets.ASSETS).count_documents({}) == 0
    assert collection(assets.JOBS).count_documents({}) == 0


def test_job_persistence_failure_keeps_nonpublic_source_for_reprocess(client, library, upload, monkeypatch):
    lib = library()
    original = assets.collection
    class FailedJobInsert:
        def __getattr__(self, name):
            if name == 'insert_one':
                def fail(*args, **kwargs):
                    raise OSError('isolated queue persistence fault')
                return fail
            return getattr(original(assets.JOBS), name)
    monkeypatch.setattr(assets, 'collection', lambda name: FailedJobInsert() if name == assets.JOBS else original(name))
    assert upload(lib).status_code == 503
    row = original(assets.ASSETS).find_one({})
    assert row['status'] == 'FAILED' and assets.source_path(row).is_file()
    monkeypatch.setattr(assets, 'collection', original)
    response = client.post(f"/libraries/{lib}/assets/{row['asset_id']}/reprocess")
    assert response.status_code == 202 and response.json()['status'] == 'PROCESSING'


def test_upload_response_loss_keeps_one_durable_submission(library, upload, monkeypatch):
    lib = library()
    original = assets.upload
    def lose_response(*args, **kwargs):
        original(*args, **kwargs)
        raise HTTPException(503, 'Isolated lost response')
    monkeypatch.setattr(assets, 'upload', lose_response)
    upload_id = str(uuid4())
    assert upload(lib, upload_id=upload_id).status_code == 503
    row = collection(assets.ASSETS).find_one({})
    assert row['status'] == 'PROCESSING'
    monkeypatch.setattr(assets, 'upload', original)
    recovered = upload(lib, upload_id=upload_id)
    assert recovered.status_code == 202 and recovered.json()['asset_id'] == row['asset_id']
    assert collection(assets.ASSETS).count_documents({}) == 1
    assert collection(assets.JOBS).count_documents({}) == 1


def test_processing_failure_retry_and_repeat_are_bounded(client, library, upload):
    lib = library()
    asset = upload(lib).json()
    first = assets.claim_job('worker')
    assert assets.fail_job(first, 'OCR_FAILED')
    failed = client.get(f"/libraries/{lib}/assets/{asset['asset_id']}").json()
    assert failed['status'] == 'FAILED' and failed['error_code'] == 'OCR_FAILED'
    repeated = client.post(f"/libraries/{lib}/assets/{asset['asset_id']}/reprocess").json()
    again = client.post(f"/libraries/{lib}/assets/{asset['asset_id']}/reprocess").json()
    assert repeated['processing_job']['attempt'] == 2
    assert repeated['processing_job']['job_id'] == again['processing_job']['job_id']
    assert collection(assets.JOBS).count_documents({}) == 2


def test_expired_claim_is_fenced_and_generation_isolated(library, upload):
    asset = upload(library()).json()
    old = assets.claim_job('worker-a')
    collection(assets.JOBS).update_one({'job_id': old['job_id']}, {'$set': {'lease_expires_at': now() - timedelta(seconds=1)}})
    new = assets.claim_job('worker-b')
    assert new['job_id'] == old['job_id'] and new['generation_id'] != old['generation_id']
    assert not assets.renew_job(old) and not assets.fail_job(old, 'STALE_WORKER')
    assert not assets.complete_job(old, {})
    assert assets.renew_job(new)
    assert assets.artifacts_path(old['asset'], old['generation_id']) != assets.artifacts_path(new['asset'], new['generation_id'])


def test_processing_publication_revalidates_uploader_membership(library, upload):
    lib = library()
    grant(lib, 3, 'LIBRARIAN')
    asset = upload(lib, user=3).json()
    job = assets.claim_job('worker')
    collection('memberships').update_one({'library_id': lib, 'user_id': 3}, {'$set': {'status': 'REMOVED'}})
    assert not assets.complete_job(job, {})
    row = collection(assets.ASSETS).find_one({'asset_id': asset['asset_id']})
    assert row['status'] == 'FAILED' and row['error_code'] == 'PROCESSING_AUTHORITY_UNAVAILABLE'


def test_deleted_asset_cannot_be_resurrected_by_worker(client, library, upload):
    lib = library()
    asset = upload(lib).json()
    job = assets.claim_job('worker')
    deleted = client.delete(f"/libraries/{lib}/assets/{asset['asset_id']}")
    assert deleted.json()['status'] == 'DELETED'
    assert not assets.complete_job(job, {})
    assert not assets.fail_job(job, 'LATE_ERROR')
    assert collection(assets.ASSETS).find_one({'asset_id': asset['asset_id']})['status'] == 'DELETED'


def test_delete_revokes_read_retires_source_removes_rag_audits(client, library, upload, ready):
    lib = library()
    member(client, lib)
    asset = upload(lib).json()
    job = ready(asset)
    url = f"/libraries/{lib}/assets/{asset['asset_id']}"
    deleted = client.delete(url).json()
    assert deleted['status'] == 'DELETED'
    assert client.get(url).status_code == 404
    assert client.get(url + '/file', headers={'x-test-user': '2'}).status_code == 404
    assert client.get(f'/libraries/{lib}/assets').json()['total'] == 0
    directory = assets.asset_directory(lib, asset['asset_id'])
    assert not (directory / 'generation').exists()
    assert (directory / 'retired' / 'source.pdf').is_file()
    assert collection(assets.ASSETS).find_one({'asset_id': asset['asset_id']})
    assert collection('audit').find_one({'event': 'ASSET_DELETED', 'metadata.asset_id': asset['asset_id']})
    assert client.delete(url).json()['status'] == 'DELETED'


def test_partial_delete_denies_immediately_and_retries(client, library, upload, ready, monkeypatch):
    lib = library()
    asset = upload(lib).json()
    ready(asset)
    original = assets.shutil.rmtree
    def fail(*args):
        raise OSError('isolated delete failure')
    monkeypatch.setattr(assets.shutil, 'rmtree', fail)
    url = f"/libraries/{lib}/assets/{asset['asset_id']}"
    assert client.delete(url).json()['status'] == 'DELETING'
    assert client.get(url + '/file').status_code == 404
    monkeypatch.setattr(assets.shutil, 'rmtree', original)
    assert client.delete(url).json()['status'] == 'DELETED'


def test_delete_audit_failure_remains_denied_then_retries(client, library, upload, ready, monkeypatch):
    lib = library()
    asset = upload(lib).json()
    ready(asset)
    original = assets.asset_audit
    def fail_audit(row, event, *args, **kwargs):
        if event == 'ASSET_DELETED':
            raise OSError('isolated audit acknowledgement fault')
        return original(row, event, *args, **kwargs)
    monkeypatch.setattr(assets, 'asset_audit', fail_audit)
    url = f"/libraries/{lib}/assets/{asset['asset_id']}"
    assert client.delete(url).json()['status'] == 'DELETING'
    assert client.get(url + '/file').status_code == 404
    assert (assets.asset_directory(lib, asset['asset_id']) / 'retired' / 'source.pdf').is_file()
    monkeypatch.setattr(assets, 'asset_audit', original)
    assert client.delete(url).json()['status'] == 'DELETED'


@pytest.mark.parametrize('kind', ['source', 'artifact'])
def test_missing_ready_artifact_fails_closed(client, library, upload, ready, kind):
    lib = library()
    asset = upload(lib).json()
    job = ready(asset)
    row = collection(assets.ASSETS).find_one({'asset_id': asset['asset_id']})
    missing = assets.source_path(row) if kind == 'source' else assets.artifacts_path(row) / 'runtime.faiss'
    missing.unlink()
    assert client.get(f"/libraries/{lib}/assets/{asset['asset_id']}/file").status_code == 409


@pytest.mark.parametrize('value', ['../../private', '/tmp/private', 'LIB001', 'book.pdf'])
def test_storage_ids_cannot_escape_uuid_namespace(value):
    with pytest.raises(HTTPException):
        assets.asset_directory(value, str(uuid4()))
    with pytest.raises(HTTPException):
        assets.asset_directory(str(uuid4()), value)


@pytest.mark.parametrize('filename', ['C:\\leak.pdf', '\\\\host\\share\\leak.pdf', '../leak.pdf', '/tmp/leak.pdf'])
def test_original_filename_path_injection_denied(filename):
    with pytest.raises(HTTPException):
        assets.validate_filename(filename)


def test_personal_records_never_auto_promote(library, database, client):
    lib = library()
    database.private_documents.insert_one({'document_id': 'personal-fixture', 'owner_user_id': 1, 'filename': 'mine.pdf'})
    assert client.get(f'/libraries/{lib}/assets').json()['total'] == 0
    assert database.private_documents.find_one({'document_id': 'personal-fixture'})


def test_asset_indexes_scope_queries_and_upload_identity(database):
    indexes = list(database.institution_library_assets.list_indexes())
    assert any(dict(i['key']) == {'library_id': 1, 'uploaded_by_user_id': 1, 'upload_id': 1} and i.get('unique') for i in indexes)
    assert any(dict(i['key']) == {'library_id': 1, 'checksum': 1} for i in indexes)
