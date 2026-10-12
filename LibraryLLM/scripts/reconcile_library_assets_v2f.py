"""Read-only by default. Diagnose only explicit canonical library asset namespaces.

--repair-metadata revokes inconsistent READY metadata or resumes a completely
persisted interrupted upload. It never deletes or assigns ownership to files.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.services import library_asset_service as assets
from backend.services.institution_repository import collection, library_mutation, now


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for piece in iter(lambda: source.read(1024 * 1024), b''):
            value.update(piece)
    return value.hexdigest()


def safe_child(directory, name):
    path = directory / name
    if path.resolve() != path or directory not in path.parents:
        raise ValueError('Artifact path escapes canonical namespace.')
    return path


def bounded_json(path, limit=128 * 1024 * 1024):
    if path.stat().st_size > limit:
        raise ValueError('Artifact exceeds the accepted document safety budget.')
    return json.loads(path.read_text(encoding='utf-8'))


def scan(library_id=None, *, repair_metadata=False, repair_source=False):
    query = {'library_id': str(UUID(library_id))} if library_id else {}
    findings = []
    known = set()
    checked = 0
    job_diagnostics = {'READY_ASSET_JOB_MISSING', 'READY_ASSET_JOB_STATE_MISMATCH',
                       'READY_ASSET_JOB_GENERATION_MISMATCH'}
    for row in collection(assets.ASSETS).find(query):
        checked += 1
        identity = {'library_id': row['library_id'], 'asset_id': row['asset_id']}
        known.add((row['library_id'], row['asset_id']))
        codes = []
        source_repaired = False
        if row['status'] == 'READY':
            job = collection(assets.JOBS).find_one({**identity, 'job_id': row.get('active_job_id')})
            if job is None:
                codes.append('READY_ASSET_JOB_MISSING')
            else:
                if job.get('state') != 'READY':
                    codes.append('READY_ASSET_JOB_STATE_MISMATCH')
                if job.get('generation_id') != row.get('active_generation_id'):
                    codes.append('READY_ASSET_JOB_GENERATION_MISMATCH')
        try:
            directory = assets.asset_directory(row['library_id'], row['asset_id'])
            expected = f"{row['library_id']}/{row['asset_id']}/source.pdf"
            if row.get('storage_key') != expected:
                codes.append('STORAGE_NAMESPACE_MISMATCH')
            source = assets.source_path(row)
            if row['status'] not in {'DELETING', 'DELETED'}:
                if not source.is_file():
                    codes.append('MISSING_SOURCE')
                    if (directory / 'source.part').is_file():
                        codes.append('INTERRUPTED_SOURCE_MOVE')
                        temporary = directory / 'source.part'
                        if (repair_source and temporary.resolve() == temporary
                                and temporary.stat().st_size == row['byte_size'] and digest(temporary) == row['checksum']):
                            with library_mutation(row['library_id'], wait_seconds=30, durable=True):
                                unchanged = collection(assets.ASSETS).find_one({**identity,
                                    'status': row['status'], 'updated_at': row['updated_at']})
                                if unchanged and not source.exists():
                                    temporary.replace(source)
                                    assets.asset_audit(row, 'ASSET_RECONCILED', 0, metadata={'error_code': 'SOURCE_MOVE_RECOVERED'})
                                    source_repaired = True
                elif digest(source) != row['checksum']:
                    codes.append('SOURCE_CHECKSUM_MISMATCH')
            if row['status'] == 'READY':
                try:
                    generated = assets.artifacts_path(row)
                    files = {name: safe_child(generated, name) for name in assets.ARTIFACT_FILES}
                    absent = [name for name, path in files.items() if not path.is_file()]
                    if absent:
                        codes.append('MISSING_READY_ARTIFACT')
                    else:
                        manifest = bounded_json(files['manifest.json'], 64 * 1024)
                        if any(manifest.get(key) != row.get(key) for key in ['library_id', 'asset_id', 'checksum']):
                            codes.append('ARTIFACT_IDENTITY_MISMATCH')
                        if manifest.get('generation_id') != row.get('active_generation_id'):
                            codes.append('ARTIFACT_GENERATION_MISMATCH')
                        if set(manifest.get('files', {})) != set(assets.ARTIFACT_FILES) - {'manifest.json'}:
                            codes.append('ARTIFACT_CHECKSUM_MANIFEST_INCOMPLETE')
                        for name, expected_checksum in manifest.get('files', {}).items():
                            if name not in assets.ARTIFACT_FILES or name == 'manifest.json':
                                codes.append('UNSAFE_MANIFEST_FILENAME')
                                break
                            if digest(files[name]) != expected_checksum:
                                codes.append('ARTIFACT_CHECKSUM_MISMATCH')
                                break
                        chunks = bounded_json(files['chunks.json'])
                        pages = bounded_json(files['extracted.json'])
                        if not isinstance(chunks, list) or not isinstance(pages, list):
                            codes.append('INVALID_EXTRACTED_ARTIFACT')
                        else:
                            document_id = f"library:{row['library_id']}:asset:{row['asset_id']}:generation:{row['active_generation_id']}"
                            if (len(chunks) != manifest.get('chunks') or len(pages) != manifest.get('pages')
                                    or manifest.get('document_id') != document_id):
                                codes.append('ARTIFACT_PROVENANCE_MISMATCH')
                            if any(page.get('library_id') != row['library_id'] or page.get('asset_id') != row['asset_id']
                                   or page.get('document_id') != document_id for page in pages):
                                codes.append('EXTRACTION_OWNERSHIP_MISMATCH')
                            if any(chunk.get('library_id') != row['library_id'] or chunk.get('asset_id') != row['asset_id']
                                   or chunk.get('generation_id') != row['active_generation_id']
                                   or not str(chunk.get('chunk_id', '')).startswith(document_id + '_') for chunk in chunks):
                                codes.append('CHUNK_OWNERSHIP_MISMATCH')
                except Exception:
                    codes.append('INVALID_READY_MANIFEST')
            if row['status'] == 'UPLOADING':
                codes.append('INTERRUPTED_UPLOAD')
            if row['status'] == 'DELETING':
                codes.append('INCOMPLETE_DELETE')
            active = row.get('active_generation_id')
            generation_root = directory / 'generation'
            if generation_root.is_dir():
                live_job = collection(assets.JOBS).find_one({'job_id': row.get('active_job_id'),
                    'state': 'PROCESSING', 'lease_expires_at': {'$gt': now()}})
                if generation_root.resolve() != generation_root:
                    raise ValueError('Derived namespace escapes asset identity.')
                for child in generation_root.iterdir():
                    if child.name != active and child.name != (live_job or {}).get('generation_id'):
                        findings.append({**identity, 'generation_id': child.name, 'codes': ['ORPHAN_OR_RETIRED_GENERATION'], 'repaired': False})
        except Exception:
            codes.append('INVALID_STORAGE_IDENTITY')
        if codes:
            repaired = source_repaired
            if (repair_metadata and row['status'] in {'READY', 'UPLOADING'}
                    and any(code not in job_diagnostics for code in codes)
                    and not any(code in codes for code in ('INVALID_STORAGE_IDENTITY', 'STORAGE_NAMESPACE_MISMATCH'))):
                with library_mutation(row['library_id'], wait_seconds=30, durable=True):
                    old = collection(assets.ASSETS).find_one({**identity, 'status': row['status'], 'updated_at': row['updated_at']})
                    if old:
                        job = collection(assets.JOBS).find_one({'job_id': row.get('active_job_id'), 'state': 'QUEUED'})
                        resume = row['status'] == 'UPLOADING' and job and codes == ['INTERRUPTED_UPLOAD']
                        collection(assets.ASSETS).update_one({**identity, 'status': row['status']}, {'$set': {
                            'status': 'PROCESSING' if resume else 'FAILED',
                            'extraction_status': 'QUEUED' if resume else 'FAILED',
                            'rag_status': 'QUEUED' if resume else 'FAILED',
                            'error_code': None if resume else 'RECONCILIATION_REQUIRED', 'updated_at': now()}})
                        assets.asset_audit(row, 'ASSET_RECONCILED', 0, metadata={'error_code': 'RESUMED_UPLOAD' if resume else 'RECONCILIATION_REQUIRED'})
                        repaired = True
            findings.append({**identity, 'codes': sorted(set(codes)), 'repaired': repaired})
    root = assets.storage_root()
    library_dirs = [root / str(UUID(library_id))] if library_id else list(root.iterdir()) if root.is_dir() else []
    for lib_dir in library_dirs:
        if lib_dir.resolve() != lib_dir:
            findings.append({'library_id': lib_dir.name, 'asset_id': None,
                'codes': ['STORAGE_NAMESPACE_ESCAPE'], 'repaired': False})
            continue
        if not lib_dir.is_dir():
            continue
        for directory in lib_dir.iterdir():
            if directory.resolve() != directory:
                findings.append({'library_id': lib_dir.name, 'asset_id': directory.name,
                    'codes': ['STORAGE_NAMESPACE_ESCAPE'], 'repaired': False})
                continue
            if not directory.is_dir():
                continue
            if (lib_dir.name, directory.name) not in known:
                findings.append({'library_id': lib_dir.name, 'asset_id': directory.name,
                    'codes': ['ORPHAN_SOURCE_OR_ARTIFACT_NAMESPACE'], 'repaired': False})
    return {'mode': 'REPAIR' if repair_metadata or repair_source else 'DRY_RUN', 'assets_checked': checked,
        'findings': findings, 'ownership_inferred': False, 'files_deleted': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library-id')
    parser.add_argument('--repair-metadata', action='store_true')
    parser.add_argument('--repair-source', action='store_true', help='Complete only a checksummed source.part move backed by unchanged canonical metadata.')
    parser.add_argument('--output', type=Path)
    options = parser.parse_args()
    report = scan(options.library_id, repair_metadata=options.repair_metadata, repair_source=options.repair_source)
    body = json.dumps(report, indent=2, default=str)
    if options.output:
        options.output.write_text(body + '\n', encoding='utf-8')
    else:
        print(body)


if __name__ == '__main__':
    main()
