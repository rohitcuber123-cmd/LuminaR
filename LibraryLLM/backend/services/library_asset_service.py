"""Canonical library-owned PDF metadata, fresh access and fenced durable jobs.

The Core API never imports a model or reads extracted text. The existing RAG
process consumes this small Mongo queue using its accepted document pipeline.
"""
import hashlib
import os
import re
import shutil
import unicodedata
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4
from urllib.parse import unquote

import pymupdf as fitz
from fastapi import HTTPException
from pymongo import ReturnDocument

from backend.institution_dependencies import actor_id
from backend.services.institution_repository import audit, collection, library_mutation, now
from backend.services.library_inventory_access import require_library_membership, require_library_staff
from backend.services.library_asset_upload_limit import MAX_FILE_BYTES

ASSETS = 'library_assets'
JOBS = 'library_asset_jobs'
PUBLIC_FIELDS = ('asset_id', 'library_id', 'uploaded_by_user_id', 'asset_type', 'title',
    'original_filename', 'media_type', 'byte_size', 'checksum', 'status', 'visibility',
    'library_book_id', 'global_work_id', 'extraction_status', 'rag_status', 'created_at',
    'updated_at', 'deleted_at', 'deleted_by_user_id', 'pages', 'chunks', 'error_code',
    'duplicate_warning', 'warnings')
JOB_FIELDS = ('job_id', 'state', 'attempt', 'error_code', 'created_at', 'started_at', 'completed_at')
ARTIFACT_FILES = ('manifest.json', 'extracted.json', 'chunks.json', 'vectors.npy', 'runtime.faiss')


def ensure_indexes():
    collection(ASSETS).create_index('asset_id', unique=True)
    collection(ASSETS).create_index([('library_id', 1), ('uploaded_by_user_id', 1), ('upload_id', 1)], unique=True)
    collection(ASSETS).create_index([('library_id', 1), ('status', 1), ('created_at', -1)])
    collection(ASSETS).create_index([('library_id', 1), ('visibility', 1), ('status', 1)])
    collection(ASSETS).create_index([('library_id', 1), ('library_book_id', 1)])
    collection(ASSETS).create_index([('library_id', 1), ('checksum', 1)])
    collection(JOBS).create_index('job_id', unique=True)
    collection(JOBS).create_index([('state', 1), ('lease_expires_at', 1), ('created_at', 1)])
    collection(JOBS).create_index([('library_id', 1), ('asset_id', 1), ('created_at', -1)])


def canonical_id(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(404, 'Library resource not found.')


def storage_root():
    default = Path(__file__).resolve().parents[2] / 'local-data' / 'library-assets'
    return Path(os.getenv('LIBRARY_ASSET_ROOT', str(default))).resolve()


def asset_directory(library_id, asset_id):
    root = storage_root()
    path = root / canonical_id(library_id) / canonical_id(asset_id)
    # Reject junction/symlink escapes as well as malformed identifiers.
    resolved = path.resolve()
    if resolved != path or root not in resolved.parents:
        raise HTTPException(404, 'Library resource not found.')
    return path


def source_path(row):
    path = asset_directory(row['library_id'], row['asset_id']) / 'source.pdf'
    if path.resolve() != path:
        raise HTTPException(404, 'Library resource not found.')
    return path


def artifacts_path(row, generation_id=None):
    generation = generation_id or row.get('active_generation_id')
    if not generation:
        raise HTTPException(409, 'Document processing is incomplete.')
    base = asset_directory(row['library_id'], row['asset_id'])
    path = base / 'generation' / canonical_id(generation)
    if path.resolve() != path or base not in path.parents:
        raise HTTPException(404, 'Library resource not found.')
    return path


def fresh_guard(library_id, actor, *, staff=False, locked=False):
    actor_id(actor)
    library_id = canonical_id(library_id)
    guard = require_library_staff if staff else require_library_membership
    if locked:
        return guard(library_id, actor, locked=True)
    # Progress polling takes the same short tenant barrier as mutations. Wait
    # for a coherent authority snapshot rather than rejecting a valid upload
    # because a list request happens to hold it at that instant. Unknown commit
    # outcomes still retain the barrier and remain fail-closed.
    with library_mutation(library_id, wait_seconds=10, durable=True):
        return guard(library_id, actor, locked=True)


def authorize_asset(library_id, asset_id, actor, *, staff=False, ready=False, locked=False):
    _, member = fresh_guard(library_id, actor, staff=staff, locked=locked)
    row = collection(ASSETS).find_one({'library_id': canonical_id(library_id), 'asset_id': canonical_id(asset_id)})
    if not row or row['status'] in {'DELETING', 'DELETED'}:
        raise HTTPException(404, 'Document not found.')
    if member['role'] == 'GENERAL_USER' and (row['visibility'] != 'MEMBERS' or row['status'] != 'READY'):
        raise HTTPException(404, 'Document not found.')
    if ready and row['status'] != 'READY':
        raise HTTPException(409, 'Document is not ready. Check its processing status.')
    if ready:
        directory = artifacts_path(row)
        if not source_path(row).is_file() or not all(
                (directory / name).resolve() == directory / name and (directory / name).is_file()
                for name in ARTIFACT_FILES):
            raise HTTPException(409, 'Document artifacts require reconciliation. Ask library staff to reprocess it.')
    return row


def public(row):
    value = {key: row.get(key) for key in PUBLIC_FIELDS}
    from backend.database.mongodb import users_collection
    uploader = users_collection.find_one({'user_id': row['uploaded_by_user_id']}, {'name': 1})
    book = collection('library_books').find_one({'library_id': row['library_id'],
        'library_book_id': row.get('library_book_id')}, {'title': 1}) if row.get('library_book_id') else None
    value['uploader_name'] = (uploader or {}).get('name')
    value['linked_book_title'] = (book or {}).get('title')
    job = collection(JOBS).find_one({'library_id': row['library_id'], 'asset_id': row['asset_id'],
        'job_id': row.get('active_job_id')})
    value['processing_job'] = {key: job.get(key) for key in JOB_FIELDS} if job else None
    return value


def asset_audit(row, event, actor, *, metadata=None, event_id=None):
    audit(row['library_id'], event, actor, metadata={'asset_id': row['asset_id'], **(metadata or {})},
          event_id=event_id)


def listing(library_id, actor, *, search='', visibility=None, status=None, library_book_id=None, offset=0, limit=20):
    with library_mutation(library_id, wait_seconds=30):
        return _listing_locked(library_id, actor, search=search, visibility=visibility, status=status,
            library_book_id=library_book_id, offset=offset, limit=limit)


def _listing_locked(library_id, actor, *, search='', visibility=None, status=None, library_book_id=None, offset=0, limit=20):
    _, member = fresh_guard(library_id, actor, locked=True)
    query = {'library_id': canonical_id(library_id), 'status': {'$nin': ['DELETING', 'DELETED']}}
    if member['role'] == 'GENERAL_USER':
        query.update(visibility='MEMBERS', status='READY')
        if visibility == 'STAFF_ONLY' or status and status != 'READY':
            return {'results': [], 'total': 0, 'offset': offset, 'limit': limit}
    else:
        if visibility:
            query['visibility'] = visibility
        if status:
            query['status'] = status
    if library_book_id:
        query['library_book_id'] = canonical_id(library_book_id)
    if search.strip():
        phrase = {'$regex': re.escape(search.strip()), '$options': 'i'}
        # Linked book lookup is tenant-bound and capped, never a global scan.
        book_ids = [r['library_book_id'] for r in collection('library_books').find(
            {'library_id': library_id, 'title': phrase}, {'library_book_id': 1}).limit(100)]
        query['$or'] = [{'title': phrase}, {'original_filename': phrase}, {'library_book_id': {'$in': book_ids}}]
    rows = list(collection(ASSETS).find(query).sort([('created_at', -1), ('asset_id', 1)]).skip(offset).limit(limit))
    result = {'results': [public(row) for row in rows], 'total': collection(ASSETS).count_documents(query),
              'offset': offset, 'limit': limit}
    return result


def detail(library_id, asset_id, actor):
    return public(authorize_asset(library_id, asset_id, actor))


def validate_filename(filename):
    filename = unicodedata.normalize('NFC', filename or '')
    decoded = unquote(filename)
    if (not filename or len(filename) > 255 or '/' in filename or '\\' in filename or ':' in filename
            or any(ord(char) < 32 for char in decoded) or any(char in decoded for char in '/\\:')
            or not filename.lower().endswith('.pdf')
            or filename.strip() != filename or filename.startswith('.')):
        raise HTTPException(400, 'Choose a PDF filename under 256 characters without path components.')
    return filename


def validate_pdf(content):
    if not content:
        raise HTTPException(400, 'Empty document.')
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, 'Document exceeds the 64 MiB upload limit.')
    if not content.startswith(b'%PDF-'):
        raise HTTPException(400, 'Only valid PDF documents are supported.')
    try:
        with fitz.open(stream=content, filetype='pdf') as parsed:
            if parsed.is_encrypted or not 0 < parsed.page_count <= 10000:
                raise HTTPException(400, 'Choose an unencrypted PDF with usable pages.')
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, 'The PDF could not be parsed.')


def linked_book(library_id, book_id):
    if not book_id:
        return None, None
    book = collection('library_books').find_one({'library_id': library_id,
        'library_book_id': canonical_id(book_id), 'status': 'ACTIVE'})
    if not book:
        raise HTTPException(404, 'Linked library book not found.')
    return book['library_book_id'], book.get('global_work_id')


def new_job(row, actor):
    previous = collection(JOBS).find_one({'library_id': row['library_id'], 'asset_id': row['asset_id']}, sort=[('attempt', -1)])
    return {'job_id': str(uuid4()), 'library_id': row['library_id'], 'asset_id': row['asset_id'],
        'actor_user_id': actor, 'state': 'QUEUED', 'attempt': (previous or {}).get('attempt', 0) + 1,
        'error_code': None, 'created_at': now(), 'started_at': None, 'completed_at': None,
        'lease_expires_at': now()}


def upload(library_id, actor, content, filename, title, visibility, book_id, upload_id):
    library_id, upload_id = canonical_id(library_id), canonical_id(upload_id)
    fresh_guard(library_id, actor, staff=True)
    filename = validate_filename(filename)
    validate_pdf(content)
    title = (title or Path(filename).stem).strip()
    if not title or len(title) > 200 or any(ord(char) < 32 for char in title):
        raise HTTPException(422, 'A title between 1 and 200 characters is required.')
    checksum = hashlib.sha256(content).hexdigest()
    uid = actor_id(actor)
    with library_mutation(library_id, wait_seconds=30, durable=True):
        fresh_guard(library_id, actor, staff=True, locked=True)
        old = collection(ASSETS).find_one({'library_id': library_id, 'uploaded_by_user_id': uid, 'upload_id': upload_id})
        if old:
            if any(old.get(key) != expected for key, expected in {'checksum': checksum, 'title': title,
                'visibility': visibility, 'library_book_id': str(book_id) if book_id else None}.items()):
                raise HTTPException(409, 'Upload ID was already used for a different document or metadata.')
            return public(old)
        linked_id, work_id = linked_book(library_id, book_id)
        duplicate = collection(ASSETS).find_one({'library_id': library_id, 'checksum': checksum,
            'status': {'$nin': ['DELETING', 'DELETED']}})
        stamp = now()
        asset_id = str(uuid4())
        row = {'asset_id': asset_id, 'library_id': library_id, 'uploaded_by_user_id': uid,
            'upload_id': upload_id, 'asset_type': 'PDF', 'title': title, 'original_filename': filename,
            'media_type': 'application/pdf', 'byte_size': len(content), 'checksum': checksum,
            'storage_key': f'{library_id}/{asset_id}/source.pdf', 'status': 'UPLOADING',
            'visibility': visibility, 'library_book_id': linked_id, 'global_work_id': work_id,
            'extraction_status': 'QUEUED', 'rag_status': 'QUEUED', 'created_at': stamp,
            'updated_at': stamp, 'deleted_at': None, 'deleted_by_user_id': None,
            'pages': 0, 'chunks': 0, 'error_code': None, 'warnings': [],
            'duplicate_warning': 'Identical content already exists in this library; this is a separate document.' if duplicate else None}
        directory = asset_directory(library_id, asset_id)
        job = new_job(row, uid)
        row['active_job_id'] = job['job_id']
        try:
            directory.mkdir(parents=True, exist_ok=False)
            temporary = directory / 'source.part'
            with temporary.open('xb') as source:
                source.write(content)
                source.flush()
                os.fsync(source.fileno())
            collection(ASSETS).insert_one(row)
            temporary.replace(source_path(row))
            collection(JOBS).insert_one(job)
            asset_audit(row, 'ASSET_UPLOADED', uid, metadata={'visibility': visibility, 'job_id': job['job_id']},
                        event_id='asset-upload:' + asset_id)
            if linked_id:
                asset_audit(row, 'ASSET_LINKED_BOOK_CHANGED', uid,
                    metadata={'library_book_id': linked_id, 'global_work_id': work_id}, event_id='asset-initial-link:' + asset_id)
            collection(ASSETS).update_one({'asset_id': asset_id, 'status': 'UPLOADING'},
                {'$set': {'status': 'PROCESSING', 'updated_at': now()}})
            row['status'] = 'PROCESSING'
        except Exception:
            # Preserve uncertain writes/source for explicit reconciliation; never expose them.
            collection(ASSETS).update_one({'asset_id': asset_id}, {'$set': {'status': 'FAILED',
                'extraction_status': 'FAILED', 'rag_status': 'FAILED', 'error_code': 'UPLOAD_PERSISTENCE_FAILED', 'updated_at': now()}})
            collection(JOBS).update_one({'job_id': job['job_id']}, {'$set': {'state': 'FAILED',
                'error_code': 'UPLOAD_PERSISTENCE_FAILED', 'completed_at': now()}})
            raise HTTPException(503, 'Upload could not be committed. Retry the same upload ID or ask staff to reconcile it.')
        return public(row)


def update(library_id, asset_id, actor, request):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        row = authorize_asset(library_id, asset_id, actor, staff=True, locked=True)
        changes = request.model_dump(exclude_unset=True)
        if changes.get('title') is None:
            changes.pop('title', None)
        if changes.get('visibility') is None:
            changes.pop('visibility', None)
        if 'library_book_id' in changes:
            changes['library_book_id'], changes['global_work_id'] = linked_book(library_id, changes['library_book_id'])
        if not changes:
            return public(row)
        changes['updated_at'] = now()
        collection(ASSETS).update_one({'library_id': library_id, 'asset_id': asset_id}, {'$set': changes})
        uid = actor_id(actor)
        if 'visibility' in changes and changes['visibility'] != row['visibility']:
            asset_audit(row, 'ASSET_VISIBILITY_CHANGED', uid,
                metadata={'visibility': changes['visibility'], 'previous_visibility': row['visibility']})
        if 'library_book_id' in changes and changes['library_book_id'] != row.get('library_book_id'):
            asset_audit(row, 'ASSET_LINKED_BOOK_CHANGED', uid,
                metadata={'library_book_id': changes['library_book_id'], 'global_work_id': changes['global_work_id']})
        if 'title' in changes:
            asset_audit(row, 'ASSET_METADATA_CHANGED', uid)
        return public({**row, **changes})


def reprocess(library_id, asset_id, actor):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        row = authorize_asset(library_id, asset_id, actor, staff=True, locked=True)
        if row['status'] == 'PROCESSING':
            return public(row)  # Repeated clicks cannot enqueue competing jobs.
        if not source_path(row).is_file():
            raise HTTPException(409, 'Source PDF is missing. Reconciliation is required.')
        uid = actor_id(actor)
        job = new_job(row, uid)
        collection(JOBS).insert_one(job)
        changes = {'status': 'PROCESSING', 'active_job_id': job['job_id'], 'error_code': None,
            'extraction_status': 'QUEUED', 'rag_status': 'QUEUED', 'updated_at': now()}
        collection(ASSETS).update_one({'library_id': library_id, 'asset_id': asset_id}, {'$set': changes})
        asset_audit(row, 'ASSET_REPROCESSED', uid, metadata={'job_id': job['job_id']}, event_id='asset-reprocess:' + job['job_id'])
        return public({**row, **changes})


def delete(library_id, asset_id, actor):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        fresh_guard(library_id, actor, staff=True, locked=True)
        row = collection(ASSETS).find_one({'library_id': library_id, 'asset_id': canonical_id(asset_id)})
        if not row:
            raise HTTPException(404, 'Document not found.')
        if row['status'] == 'DELETED':
            return public(row)
        uid = actor_id(actor)
        changes = {'status': 'DELETING', 'updated_at': now(), 'deleted_by_user_id': uid,
            'extraction_status': 'RETIRED', 'rag_status': 'RETIRED'}
        collection(ASSETS).update_one({'library_id': library_id, 'asset_id': asset_id}, {'$set': changes})
        collection(JOBS).update_many({'library_id': library_id, 'asset_id': asset_id,
            'state': {'$in': ['QUEUED', 'PROCESSING']}}, {'$set': {'state': 'FAILED', 'error_code': 'ASSET_DELETED', 'completed_at': now()}})
        directory = asset_directory(library_id, asset_id)
        try:
            generation = directory / 'generation'
            # Only the checked UUID subtree is removed; originals remain tombstoned.
            if generation.exists():
                if generation.resolve() != generation or directory not in generation.resolve().parents:
                    raise OSError('Unsafe derived artifact path.')
                shutil.rmtree(generation)
            if source_path(row).exists():
                retired = directory / 'retired'
                retired.mkdir(exist_ok=True)
                if retired.resolve() != retired:
                    raise OSError('Unsafe retired source path.')
                source_path(row).replace(retired / 'source.pdf')
            asset_audit(row, 'ASSET_DELETED', uid, event_id='asset-delete:' + asset_id)
            changes.update(status='DELETED', deleted_at=now(), error_code=None)
        except OSError:
            changes['error_code'] = 'DELETE_INCOMPLETE'
        collection(ASSETS).update_one({'library_id': library_id, 'asset_id': asset_id}, {'$set': changes})
        return public({**row, **changes})


def _claim_filter(job):
    return {'job_id': job['job_id'], 'state': 'PROCESSING', 'lease_id': job['lease_id'],
        'generation_id': job['generation_id']}


def claim_job(owner, lease_seconds=300):
    stamp = now()
    candidates = list(collection(JOBS).find({'$or': [{'state': 'QUEUED'},
        {'state': 'PROCESSING', 'lease_expires_at': {'$lte': stamp}}]}).sort('created_at', 1).limit(20))
    for candidate in candidates:
        library_id = candidate['library_id']
        try:
            with library_mutation(library_id, wait_seconds=3, durable=True):
                asset = collection(ASSETS).find_one({'library_id': library_id, 'asset_id': candidate['asset_id']})
                if not asset or asset.get('active_job_id') != candidate['job_id'] or asset['status'] not in {'PROCESSING', 'UPLOADING'}:
                    # Publication may have committed before its acknowledgement/job update.
                    state = 'READY' if asset and asset['status'] == 'READY' and asset.get('active_job_id') == candidate['job_id'] else 'FAILED'
                    collection(JOBS).update_one({'job_id': candidate['job_id'], 'state': candidate['state']},
                        {'$set': {'state': state, 'completed_at': now(), 'error_code': None if state == 'READY' else 'ASSET_UNAVAILABLE'}})
                    continue
                try:
                    fresh_guard(library_id, {'sub': str(candidate['actor_user_id'])}, staff=True, locked=True)
                except HTTPException as error:
                    if error.status_code == 503:
                        continue
                    code = 'PROCESSING_AUTHORITY_UNAVAILABLE'
                    collection(JOBS).update_one({'job_id': candidate['job_id']}, {'$set': {'state': 'FAILED', 'error_code': code, 'completed_at': now()}})
                    collection(ASSETS).update_one({'asset_id': asset['asset_id'], 'status': {'$in': ['PROCESSING', 'UPLOADING']}}, {'$set': {
                        'status': 'FAILED', 'error_code': code, 'extraction_status': 'FAILED', 'rag_status': 'FAILED', 'updated_at': now()}})
                    asset_audit(asset, 'ASSET_PROCESSING_FAILED', candidate['actor_user_id'], metadata={'error_code': code, 'job_id': candidate['job_id']})
                    continue
                lease = {'state': 'PROCESSING', 'lease_owner': str(owner)[:100], 'lease_id': str(uuid4()),
                    'generation_id': str(uuid4()), 'lease_expires_at': now() + timedelta(seconds=lease_seconds), 'started_at': now()}
                match = {'job_id': candidate['job_id'], 'state': candidate['state']}
                if candidate['state'] == 'PROCESSING':
                    match['lease_id'] = candidate.get('lease_id')
                    match['lease_expires_at'] = {'$lte': stamp}
                job = collection(JOBS).find_one_and_update(match, {'$set': lease}, return_document=ReturnDocument.AFTER)
                if job:
                    collection(ASSETS).update_one({'asset_id': asset['asset_id'], 'active_job_id': job['job_id']},
                        {'$set': {'status': 'PROCESSING', 'extraction_status': 'PROCESSING', 'rag_status': 'PROCESSING', 'updated_at': now()}})
                    asset_audit(asset, 'ASSET_PROCESSING_STARTED', job['actor_user_id'],
                        metadata={'job_id': job['job_id']}, event_id='asset-start:' + job['lease_id'])
                    job['asset'] = asset
                    return job
        except HTTPException as error:
            if error.status_code != 503:
                raise
    return None


def renew_job(job, lease_seconds=300):
    result = collection(JOBS).update_one({**_claim_filter(job), 'lease_expires_at': {'$gt': now()}},
        {'$set': {'lease_expires_at': now() + timedelta(seconds=lease_seconds)}})
    return bool(result.matched_count)


def complete_job(job, manifest):
    library_id = job['library_id']
    with library_mutation(library_id, wait_seconds=30, durable=True):
        current = collection(JOBS).find_one({**_claim_filter(job), 'lease_expires_at': {'$gt': now()}})
        if not current:
            return False
        row = collection(ASSETS).find_one({'library_id': library_id, 'asset_id': job['asset_id'],
            'active_job_id': job['job_id'], 'status': 'PROCESSING'})
        if not row:
            return False
        try:
            fresh_guard(library_id, {'sub': str(job['actor_user_id'])}, staff=True, locked=True)
        except HTTPException:
            _fail_locked(job, row, 'PROCESSING_AUTHORITY_UNAVAILABLE')
            return False
        if (manifest.get('library_id') != library_id or manifest.get('asset_id') != row['asset_id']
                or manifest.get('checksum') != row['checksum'] or manifest.get('generation_id') != job['generation_id']
                or not all((artifacts_path(row, job['generation_id']) / name).resolve() == artifacts_path(row, job['generation_id']) / name
                    and (artifacts_path(row, job['generation_id']) / name).is_file() for name in ARTIFACT_FILES)):
            _fail_locked(job, row, 'ARTIFACT_IDENTITY_INVALID')
            return False
        changes = {'status': 'READY', 'active_generation_id': job['generation_id'],
            'extraction_status': 'READY', 'rag_status': 'READY', 'pages': manifest.get('pages', 0),
            'chunks': manifest.get('chunks', 0), 'warnings': manifest.get('warnings', [])[:10],
            'error_code': None, 'updated_at': now()}
        asset_audit(row, 'ASSET_READY', job['actor_user_id'], metadata={'job_id': job['job_id']},
            event_id='asset-ready:' + job['job_id'] + ':' + job['generation_id'])
        result = collection(ASSETS).update_one({'asset_id': row['asset_id'], 'status': 'PROCESSING',
            'active_job_id': job['job_id']}, {'$set': changes})
        if not result.matched_count:
            return False
        collection(JOBS).update_one(_claim_filter(job), {'$set': {'state': 'READY', 'completed_at': now(), 'error_code': None}})
        return True


def _fail_locked(job, row, errorcode):
    code = errorcode if re.fullmatch(r'[A-Z0-9_]{1,80}', errorcode or '') else 'PROCESSING_FAILED'
    result = collection(JOBS).update_one(_claim_filter(job), {'$set': {'state': 'FAILED', 'error_code': code, 'completed_at': now()}})
    if not result.matched_count:
        return False
    if row and row.get('active_job_id') == job['job_id'] and row['status'] == 'PROCESSING':
        collection(ASSETS).update_one({'asset_id': row['asset_id'], 'status': 'PROCESSING', 'active_job_id': job['job_id']}, {'$set': {
            'status': 'FAILED', 'extraction_status': 'FAILED', 'rag_status': 'FAILED', 'error_code': code, 'updated_at': now()}})
        asset_audit(row, 'ASSET_PROCESSING_FAILED', job['actor_user_id'], metadata={'job_id': job['job_id'], 'error_code': code},
            event_id='asset-fail:' + job['job_id'] + ':' + job['lease_id'])
    return True


def fail_job(job, errorcode):
    with library_mutation(job['library_id'], wait_seconds=30, durable=True):
        row = collection(ASSETS).find_one({'library_id': job['library_id'], 'asset_id': job['asset_id']})
        return _fail_locked(job, row, errorcode)


def retire_generation(job):
    """Remove only a known unpublishable claim's UUID generation, never a READY one.

    Ambiguous Mongo outcomes preserve files for reconciliation. A committed
    publication whose response was lost is detected from the active asset.
    """
    try:
        with library_mutation(job['library_id'], wait_seconds=30, durable=True):
            row = collection(ASSETS).find_one({'library_id': job['library_id'], 'asset_id': job['asset_id']})
            if row is None or row.get('active_generation_id') == job['generation_id']:
                return False
            current = collection(JOBS).find_one({'job_id': job['job_id']})
            if current is None or (current['state'] == 'PROCESSING'
                    and current.get('lease_id') == job['lease_id'] and current.get('generation_id') == job['generation_id']):
                return False
            directory = artifacts_path(row, job['generation_id'])
            if directory.exists():
                shutil.rmtree(directory)
            return True
    except (HTTPException, OSError):
        return False
