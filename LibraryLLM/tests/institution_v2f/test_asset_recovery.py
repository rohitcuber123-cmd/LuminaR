import hashlib
import json
from pathlib import Path
from uuid import uuid4

from backend.services import library_asset_service as assets
from backend.services.institution_repository import collection
from scripts import reconcile_library_assets_v2f as reconcile
from scripts import migrate_library_assets_v2f as migration


def valid_artifacts(asset, job):
    row = collection(assets.ASSETS).find_one({'asset_id': asset['asset_id']})
    directory = assets.artifacts_path(row)
    document_id = f"library:{row['library_id']}:asset:{row['asset_id']}:generation:{job['generation_id']}"
    pages = [{'library_id': row['library_id'], 'asset_id': row['asset_id'], 'document_id': document_id, 'text': 'Safe fixture text'}]
    chunks = [{'library_id': row['library_id'], 'asset_id': row['asset_id'], 'generation_id': job['generation_id'],
               'chunk_id': document_id + f'_{index}', 'text': 'Safe fixture text'} for index in [1, 2]]
    (directory / 'extracted.json').write_text(json.dumps(pages), encoding='utf-8')
    (directory / 'chunks.json').write_text(json.dumps(chunks), encoding='utf-8')
    manifest = {'library_id': row['library_id'], 'asset_id': row['asset_id'], 'checksum': row['checksum'],
        'generation_id': job['generation_id'], 'document_id': document_id, 'pages': 1, 'chunks': 2,
        'files': {name: reconcile.digest(directory / name) for name in assets.ARTIFACT_FILES if name != 'manifest.json'}}
    (directory / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    return row, directory


def test_reconcile_default_read_only_consistent(library, upload, ready):
    asset = upload(library()).json()
    row, directory = valid_artifacts(asset, ready(asset))
    before = collection(assets.ASSETS).find_one({'asset_id': asset['asset_id']})
    report = reconcile.scan()
    assert report['mode'] == 'DRY_RUN' and report['findings'] == []
    assert collection(assets.ASSETS).find_one({'asset_id': asset['asset_id']}) == before


def test_reconcile_missing_source_and_artifact_no_auto_deletion(library, upload, ready):
    asset = upload(library()).json()
    row, directory = valid_artifacts(asset, ready(asset))
    assets.source_path(row).unlink()
    (directory / 'runtime.faiss').unlink()
    report = reconcile.scan()
    codes = report['findings'][0]['codes']
    assert 'MISSING_SOURCE' in codes and 'MISSING_READY_ARTIFACT' in codes
    assert report['files_deleted'] == 0 and report['ownership_inferred'] is False
    assert collection(assets.ASSETS).find_one({'asset_id': asset['asset_id']})['status'] == 'READY'


def test_reconcile_revokes_invalid_ready_only_with_flag(library, upload, ready):
    asset = upload(library()).json()
    row, directory = valid_artifacts(asset, ready(asset))
    (directory / 'runtime.faiss').unlink()
    report = reconcile.scan(repair_metadata=True)
    assert report['findings'][0]['repaired']
    assert collection(assets.ASSETS).find_one({'asset_id': asset['asset_id']})['status'] == 'FAILED'
    assert assets.source_path(row).is_file()


def test_reconcile_reports_partial_publication_job_ack_without_retiring_ready(library, upload, ready):
    asset = upload(library()).json()
    job = ready(asset)
    row, directory = valid_artifacts(asset, job)
    collection(assets.JOBS).update_one({'job_id': job['job_id']}, {'$set': {'state': 'PROCESSING'}})
    report = reconcile.scan(repair_metadata=True)
    finding = next(item for item in report['findings'] if item['asset_id'] == row['asset_id'])
    assert finding['codes'] == ['READY_ASSET_JOB_STATE_MISMATCH'] and not finding['repaired']
    assert collection(assets.ASSETS).find_one({'asset_id': row['asset_id']})['status'] == 'READY'
    assert all((directory / name).is_file() for name in assets.ARTIFACT_FILES)
    assert collection(assets.JOBS).find_one({'job_id': job['job_id']})['state'] == 'PROCESSING'


def test_reconcile_ready_job_identity_mismatch_never_guesses_or_republishes(library, upload, ready):
    asset = upload(library()).json()
    job = ready(asset)
    row, directory = valid_artifacts(asset, job)
    collection(assets.JOBS).update_one({'job_id': job['job_id']}, {'$set': {'generation_id': str(uuid4())}})
    assert reconcile.scan()['findings'][0]['codes'] == ['READY_ASSET_JOB_GENERATION_MISMATCH']
    collection(assets.JOBS).delete_one({'job_id': job['job_id']})
    report = reconcile.scan(repair_metadata=True)
    assert report['findings'][0]['codes'] == ['READY_ASSET_JOB_MISSING']
    assert not report['findings'][0]['repaired'] and directory.exists()
    assert collection(assets.ASSETS).find_one({'asset_id': row['asset_id']})['status'] == 'READY'


def test_reconcile_source_checksum_and_chunk_identity(library, upload, ready):
    asset = upload(library()).json()
    row, directory = valid_artifacts(asset, ready(asset))
    with assets.source_path(row).open('ab') as file:
        file.write(b'tampered')
    chunks = json.loads((directory / 'chunks.json').read_text())
    chunks[0]['library_id'] = str(uuid4())
    (directory / 'chunks.json').write_text(json.dumps(chunks))
    report = reconcile.scan()
    codes = report['findings'][0]['codes']
    assert 'SOURCE_CHECKSUM_MISMATCH' in codes
    assert 'ARTIFACT_CHECKSUM_MISMATCH' in codes
    assert 'CHUNK_OWNERSHIP_MISMATCH' in codes


def test_reconcile_orphan_source_and_index_no_guess(library, upload, ready):
    lib = library()
    asset = upload(lib).json()
    row, directory = valid_artifacts(asset, ready(asset))
    orphan = assets.asset_directory(lib, str(uuid4()))
    orphan.mkdir()
    (orphan / 'source.pdf').write_bytes(b'not assigned')
    (directory.parent / str(uuid4())).mkdir()
    report = reconcile.scan()
    codes = [code for finding in report['findings'] for code in finding['codes']]
    assert 'ORPHAN_SOURCE_OR_ARTIFACT_NAMESPACE' in codes and 'ORPHAN_OR_RETIRED_GENERATION' in codes
    assert report['ownership_inferred'] is False and orphan.exists()


def test_reconcile_interrupted_source_move_requires_explicit_verified_repair(library, upload, monkeypatch):
    lib = library()
    original = Path.replace
    def fail(*args):
        raise OSError('isolated move fault')
    monkeypatch.setattr(Path, 'replace', fail)
    assert upload(lib).status_code == 503
    monkeypatch.setattr(Path, 'replace', original)
    row = collection(assets.ASSETS).find_one({})
    temporary = assets.asset_directory(lib, row['asset_id']) / 'source.part'
    assert 'INTERRUPTED_SOURCE_MOVE' in reconcile.scan()['findings'][0]['codes']
    assert temporary.exists() and not assets.source_path(row).exists()
    result = reconcile.scan(repair_source=True)
    assert result['findings'][0]['repaired'] and assets.source_path(row).is_file()
    assert collection(assets.ASSETS).find_one({'asset_id': row['asset_id']})['status'] == 'FAILED'
    assert assets.reprocess(lib, row['asset_id'], {'sub': '1'})['status'] == 'PROCESSING'


def test_reconcile_wrong_checksum_part_never_moves(library, upload, monkeypatch):
    lib = library()
    original = Path.replace
    monkeypatch.setattr(Path, 'replace', lambda *args: (_ for _ in ()).throw(OSError('fixture')))
    upload(lib)
    monkeypatch.setattr(Path, 'replace', original)
    row = collection(assets.ASSETS).find_one({})
    temporary = assets.asset_directory(lib, row['asset_id']) / 'source.part'
    temporary.write_bytes(b'other file')
    result = reconcile.scan(repair_source=True)
    assert not result['findings'][0]['repaired']
    assert temporary.exists() and not assets.source_path(row).exists()


def test_migration_personal_history_remains_separate(library, database):
    lib = library()
    database.historical_documents.insert_one({'document_id': 'doc_' + uuid4().hex, 'owner_user_id': 1, 'owner_session_id': 'fixture'})
    database.historical_documents.insert_one({'document_id': 'legacy-upload', 'uploaded_by_user_id': 1})
    report = migration.audit_documents()
    assert report['mode'] == 'DRY_RUN' and report['automatic_library_assignments'] == 0
    assert report['personal_documents_modified'] == 0
    assert {d['classification'] for d in report['documents']} == {'PERSONAL_PRIVATE', 'AMBIGUOUS_DOCUMENT_OWNERSHIP'}
    assert collection(assets.ASSETS).count_documents({}) == 0
    assert database.historical_documents.count_documents({}) == 2


def test_explicit_mapping_requires_library_evidence_owner_consent(library):
    lib = library()
    mappings = [{'source_id': 'legacy', 'library_id': lib},
        {'source_id': 'personal', 'library_id': lib, 'ownership_evidence': 'Approved local fixture', 'source_owner_consent': True},
        {'source_id': 'other', 'library_id': 'LIB001', 'ownership_evidence': 'Unproven', 'source_owner_consent': True}]
    result = migration.inspect_mappings(mappings)
    assert [r['eligible_for_review'] for r in result] == [False, True, False]
    assert not any(r['applied'] for r in result)
