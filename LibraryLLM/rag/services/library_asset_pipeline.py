"""Tenant adapter for the accepted PDF/OCR/chunk/FAISS and document AI pipeline.

No personal registry, global book index, router, or model is modified. Derived
files belong to a fenced library/asset/generation. Authorization precedes every
private read and is repeated before publication and before returning output.
"""
import asyncio
import contextlib
import hashlib
import json
import logging
import os
from pathlib import Path
from threading import Event, Lock, Semaphore, Thread
from time import monotonic, perf_counter, sleep
from uuid import uuid4

import faiss
import numpy as np
from fastapi import HTTPException

from backend.services import library_asset_service as default_repository
from backend.services.library_asset_upload_limit import MAX_FILE_BYTES
from rag.services.document_service import DocumentService
from rag.services import private_document_ocr, document_knowledge, knowledge_algorithms
from rag.services import knowledge_quiz, knowledge_quiz_evidence, knowledge_quiz_relations
from rag.services import knowledge_cloze, cloze_grading, knowledge_encoder
from rag.services.local_document_cache import DIMENSION, MAX_CHUNKS, fingerprint

logger = logging.getLogger('uvicorn.error')
PIPELINE_VERSION = 'library-assets-v1'
MAX_JSON_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
ARTIFACT_TYPES = {'key-concepts': 'KEY_CONCEPTS', 'summary': 'EXTRACTIVE_SUMMARY',
                  'flashcards': 'FLASHCARDS', 'mindmap': 'MIND_MAP', 'quiz': 'QUIZ'}


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for piece in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(piece)
    return value.hexdigest()


def atomic_json(path, payload, limit=None):
    """Publish only JSON that fits the reader's UTF-8 byte safety budget."""
    path = Path(path)
    limit = MAX_JSON_ARTIFACT_BYTES if limit is None else limit
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        written = 0
        encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False)
        with temporary.open('xb') as stream:
            for fragment in encoder.iterencode(payload):
                encoded = fragment.encode('utf-8')
                written += len(encoded)
                if written > limit:
                    raise HTTPException(413, 'ARTIFACT_LIMIT')
                stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def safe_child(directory, *parts):
    """No file or intermediate directory may redirect private reads/writes."""
    directory = Path(directory)
    target = directory.joinpath(*parts)
    if target.resolve() != target or directory not in target.parents:
        raise HTTPException(404, 'Document not found.')
    return target


def bounded_json(path, limit=None):
    limit = MAX_JSON_ARTIFACT_BYTES if limit is None else limit
    if path.stat().st_size > limit:
        raise HTTPException(413, 'This document artifact is too large.')
    return json.loads(path.read_text(encoding='utf-8'))


class LibraryAssetPipeline:
    def __init__(self, engine, repository=default_repository, encoder=None):
        self.engine = engine
        self.repository = repository
        self.processor = DocumentService.__new__(DocumentService)
        self.processor.model = engine.reranker.retriever.model
        self.encoder = encoder or knowledge_encoder.encode
        self._worker = Lock()
        self._tools = Semaphore(2)
        self.worker_id = 'rag-assets-' + uuid4().hex
        self.processing_stage = 'IDLE'

    def process_job(self, job):
        self.processing_stage = 'SOURCE_VALIDATION'
        asset = job['asset']
        actor = {'sub': str(job['actor_user_id'])}
        self.authorize_worker(job, actor)
        source = self.repository.source_path(asset)
        if not source.is_file():
            raise HTTPException(409, 'SOURCE_MISSING')
        if source.stat().st_size != asset['byte_size'] or source.stat().st_size > MAX_FILE_BYTES:
            raise HTTPException(409, 'SOURCE_INVALID')
        if digest(source) != asset['checksum']:
            raise HTTPException(409, 'SOURCE_CHECKSUM_MISMATCH')
        directory = self.repository.artifacts_path(asset, generation_id=job['generation_id'])
        directory.mkdir(parents=True, exist_ok=False)
        started = perf_counter()
        self.processing_stage = 'EXTRACTION'
        pages = self.processor.extract_pdf(source)
        if not 0 < len(pages) <= 10000:
            raise HTTPException(413, 'PAGE_LIMIT')
        self.processing_stage = 'OCR'
        pages, ocr = private_document_ocr.prepare(source, pages)
        document_id = self.document_identity(asset, job['generation_id'])
        for page in pages:
            page.update(library_id=job['library_id'], asset_id=job['asset_id'],
                        document_id=document_id, filename=asset['original_filename'])
        self.processing_stage = 'CHUNKING'
        chunks = self.processor.create_chunks(document_id, asset['original_filename'], pages)
        if not 0 < len(chunks) <= MAX_CHUNKS:
            raise HTTPException(400, 'NO_USABLE_TEXT' if not chunks else 'CHUNK_LIMIT')
        offsets = {}
        for chunk in chunks:
            page = pages[chunk['page'] - 1]
            start = page['text'].find(chunk['text'], offsets.get(chunk['page'], 0))
            if start < 0:
                raise HTTPException(409, 'CHUNK_PROVENANCE_INVALID')
            offsets[chunk['page']] = max(start + len(chunk['text']) - 400, start + 1)
            chunk.update(library_id=job['library_id'], asset_id=job['asset_id'],
                         generation_id=job['generation_id'], source_start=start,
                         source_end=start + len(chunk['text']),
                         extraction_method=page['extraction_method'])
        # The resident embedding model/GPU is shared with interactive inference.
        # PDF parsing and bounded OCR above do not hold the interactive lock.
        self.processing_stage = 'EMBEDDING'
        with self.engine.inference_lock:
            vectors = self.processor.embed_chunks(chunks)
        if (vectors.shape != (len(chunks), DIMENSION) or vectors.dtype != np.float32
                or not np.isfinite(vectors).all()):
            raise HTTPException(409, 'EMBEDDING_INVALID')
        self.processing_stage = 'PUBLICATION_AUTHORIZATION'
        self.authorize_worker(job, actor)
        self.processing_stage = 'ARTIFACT_PERSISTENCE'
        atomic_json(directory / 'extracted.json', pages)
        atomic_json(directory / 'chunks.json', chunks)
        np.save(directory / 'vectors.npy', vectors, allow_pickle=False)
        index = faiss.IndexFlatIP(DIMENSION)
        index.add(vectors)
        faiss.write_index(index, str(directory / 'runtime.faiss'))
        files = {name: digest(directory / name) for name in
                 ('extracted.json', 'chunks.json', 'vectors.npy', 'runtime.faiss')}
        manifest = {'library_id': job['library_id'], 'asset_id': job['asset_id'],
                    'generation_id': job['generation_id'], 'checksum': asset['checksum'],
                    'document_id': document_id, 'pages': len(pages), 'chunks': len(chunks),
                    'dimension': DIMENSION, 'pipeline_version': PIPELINE_VERSION,
                    'pipeline_fingerprint': fingerprint(), 'files': files, 'ocr': ocr,
                    'warnings': ['Some scanned pages could not be read.'] if ocr['failed_pages'] else [],
                    'processing_seconds': round(perf_counter() - started, 4)}
        atomic_json(directory / 'manifest.json', manifest, limit=MAX_MANIFEST_BYTES)
        return manifest

    def authorize_worker(self, job, actor):
        # Central metadata/list operations briefly hold the tenant mutation
        # barrier. Wait for its coherent snapshot rather than failing a durable
        # processing job merely because the UI polls progress at that moment.
        deadline = monotonic() + 5
        while True:
            try:
                return self.repository.authorize_asset(job['library_id'], job['asset_id'], actor, staff=True)
            except HTTPException as error:
                if error.status_code != 503 or monotonic() >= deadline:
                    raise
                sleep(.05)

    @staticmethod
    def document_identity(asset, generation_id):
        return f"library:{asset['library_id']}:asset:{asset['asset_id']}:generation:{generation_id}"

    def run_one(self, owner=None):
        if not self._worker.acquire(blocking=False):
            return False
        stop = Event()
        heartbeat = None
        try:
            job = self.repository.claim_job(owner or self.worker_id)
            if job is None:
                return False

            def renew():
                while not stop.wait(30):
                    try:
                        if not self.repository.renew_job(job):
                            break
                    except Exception:
                        logger.warning('library_asset_lease_renewal_failed job_id=%s', job['job_id'])
                        break

            heartbeat = Thread(target=renew, daemon=True)
            heartbeat.start()
            try:
                manifest = self.process_job(job)
                self.processing_stage = 'PUBLICATION_COMMIT'
                if not self.repository.complete_job(job, manifest):
                    self.repository.retire_generation(job)
            except Exception as error:
                codes = {'SOURCE_MISSING', 'SOURCE_INVALID', 'SOURCE_CHECKSUM_MISMATCH',
                         'PAGE_LIMIT', 'CHUNK_LIMIT', 'NO_USABLE_TEXT', 'EMBEDDING_INVALID',
                         'CHUNK_PROVENANCE_INVALID', 'ARTIFACT_LIMIT'}
                code = error.detail if isinstance(error, HTTPException) and isinstance(error.detail, str) and error.detail in codes else (
                    'AUTHORITY_REVOKED' if isinstance(error, HTTPException) and error.status_code in (401, 403, 404)
                    else 'PROCESSING_FAILED')
                self.repository.fail_job(job, code)
                self.repository.retire_generation(job)
                logger.warning('library_asset_processing_failed job_id=%s code=%s stage=%s exception_type=%s',
                               job['job_id'], code, self.processing_stage, type(error).__name__)
            return True
        finally:
            stop.set()
            if heartbeat:
                heartbeat.join(timeout=1)
            self._worker.release()
            self.processing_stage = 'IDLE'

    def prepared(self, library_id, asset_id, actor):
        row = self.repository.authorize_asset(library_id, asset_id, actor, ready=True)
        directory = self.repository.artifacts_path(row)
        try:
            manifest_path, chunks_path = safe_child(directory, 'manifest.json'), safe_child(directory, 'chunks.json')
            if manifest_path.stat().st_size > MAX_MANIFEST_BYTES or chunks_path.stat().st_size > MAX_JSON_ARTIFACT_BYTES:
                raise ValueError('Artifact limit')
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            chunks = json.loads(chunks_path.read_text(encoding='utf-8'))
            expected = {'library_id': library_id, 'asset_id': asset_id,
                        'generation_id': row['active_generation_id'], 'checksum': row['checksum']}
            if (any(manifest.get(key) != value for key, value in expected.items())
                    or manifest.get('document_id') != self.document_identity(row, row['active_generation_id'])
                    or manifest.get('dimension') != DIMENSION or not isinstance(chunks, list)
                    or not 0 < len(chunks) <= MAX_CHUNKS or len(chunks) != manifest['chunks']):
                raise ValueError('Artifact identity')
            if digest(chunks_path) != manifest['files']['chunks.json']:
                raise ValueError('Artifact checksum')
            for chunk in chunks:
                if (not isinstance(chunk, dict) or any(chunk.get(key) != value for key, value in
                    {'library_id': library_id, 'asset_id': asset_id, 'generation_id': row['active_generation_id'],
                     'document_id': manifest['document_id']}.items()) or not isinstance(chunk.get('text'), str)
                        or not isinstance(chunk.get('chunk_id'), str)
                        or not chunk['chunk_id'].startswith(manifest['document_id'] + '_')):
                    raise ValueError('Chunk identity')
            self.recheck(row, actor)
            return row, directory, manifest, chunks
        except (OSError, ValueError, KeyError, TypeError):
            raise HTTPException(409, 'This document needs to be prepared again. Ask library staff to retry.')

    def recheck(self, row, actor):
        current = self.repository.authorize_asset(row['library_id'], row['asset_id'], actor, ready=True)
        if current.get('active_generation_id') != row.get('active_generation_id'):
            raise HTTPException(409, 'This document changed. Open it again.')
        return current

    def clear_runtime(self):
        retriever = self.engine.reranker.retriever
        retriever.doc_index = None
        retriever.doc_metadata = []
        retriever.doc_ids = set()
        retriever.doc_chunk_texts = {}
        latency = getattr(self.engine, '_document_latency', None)
        if latency:
            latency.clear_cache()

    def ask(self, library_id, asset_id, actor, query, depth='normal'):
        # Do not query a shared corpus then filter. Load one authorized artifact.
        with self.engine.inference_lock:
            row, directory, manifest, chunks = self.prepared(library_id, asset_id, actor)
            retriever = self.engine.reranker.retriever
            self.clear_runtime()
            try:
                index_path = safe_child(directory, 'runtime.faiss')
                if digest(index_path) != manifest['files']['runtime.faiss']:
                    raise HTTPException(409, 'This document needs to be prepared again.')
                index = faiss.read_index(str(index_path))
                if index.d != DIMENSION or index.ntotal != len(chunks):
                    raise HTTPException(409, 'This document needs to be prepared again.')
                retriever.doc_index = index
                retriever.doc_metadata = [{key: c[key] for key in
                    ('chunk_id', 'document_id', 'filename', 'page', 'library_id', 'asset_id', 'generation_id')}
                    for c in chunks]
                retriever.doc_ids = {manifest['document_id']}
                retriever.doc_chunk_texts = {c['chunk_id']: c['text'] for c in chunks}
                self.recheck(row, actor)
                result = self.engine.ask(question=query, depth=depth, document_id=manifest['document_id'])
                self.recheck(row, actor)
                valid_ids = {c['chunk_id'] for c in chunks}
                for source in result.get('sources', []):
                    if source.get('chunk_id') not in valid_ids:
                        raise HTTPException(409, 'Document source identity could not be verified.')
                    source.update(library_id=library_id, asset_id=asset_id)
                return {**result, 'library_id': library_id, 'asset_id': asset_id}
            finally:
                self.clear_runtime()

    def _cache_identity(self, row, manifest, kind, options):
        return hashlib.sha256(json.dumps([row['library_id'], row['asset_id'], row['active_generation_id'],
            row['checksum'], manifest['files']['chunks.json'], kind, options,
            document_knowledge.VERSION, knowledge_algorithms.VERSION, knowledge_quiz.VERSION,
            knowledge_quiz_evidence.VERSION, knowledge_quiz_relations.VERSION, knowledge_cloze.VERSION],
            sort_keys=True).encode()).hexdigest()

    @staticmethod
    def valid_artifact(artifact, row, manifest, kind, options):
        if not isinstance(artifact, dict):
            return False
        expected_version = knowledge_quiz.VERSION if kind == 'QUIZ' else knowledge_algorithms.VERSION
        return (artifact.get('libraryId') == row['library_id'] and artifact.get('assetId') == row['asset_id']
            and artifact.get('documentId') == row['asset_id'] and artifact.get('type') == kind
            and artifact.get('options') == options and artifact.get('sourceRevision') == manifest['files']['chunks.json']
            and artifact.get('generatorVersion') == expected_version
            and artifact.get('analysis', {}).get('knowledgeVersion') == document_knowledge.VERSION
            and isinstance(artifact.get('sourceChunkIds'), list)
            and all(isinstance(source, str) and source.startswith(manifest['document_id'] + '_')
                    for source in artifact['sourceChunkIds']))

    def generate(self, library_id, asset_id, actor, slug, mode='quick', question_types=None, question_count=12):
        row, directory, manifest, chunks = self.prepared(library_id, asset_id, actor)
        if slug not in ARTIFACT_TYPES:
            raise HTTPException(422, 'Unknown study tool.')
        if not self._tools.acquire(blocking=False):
            raise HTTPException(429, 'Knowledge Tools is busy. Please retry shortly.')
        try:
            kind = ARTIFACT_TYPES[slug]
            options = {'mode': mode} if kind == 'EXTRACTIVE_SUMMARY' else {}
            if kind == 'QUIZ':
                try:
                    options = knowledge_quiz.quiz_options(question_types, question_count)
                except ValueError as error:
                    raise HTTPException(422, str(error)) from error
            key = self._cache_identity(row, manifest, kind, options)
            cache = safe_child(directory, 'knowledge')
            cache.mkdir(exist_ok=True)
            target = safe_child(directory, 'knowledge', key + '.json')
            if target.is_file():
                artifact = bounded_json(target)
                if not self.valid_artifact(artifact, row, manifest, kind, options):
                    raise HTTPException(409, 'This study artifact needs to be generated again.')
                self.recheck(row, actor)
                return {'artifact': artifact, 'cached': True}
            model_key = self._cache_identity(row, manifest, 'DOCUMENT_KNOWLEDGE', {})
            model_path = safe_child(directory, 'knowledge', model_key + '.model.json')
            if model_path.is_file():
                model = document_knowledge.DocumentKnowledgeModel(**bounded_json(model_path))
                model_cached = True
            else:
                model = document_knowledge.build(chunks, self.encoder)
                knowledge_quiz_evidence.attach(model, self.encoder)
                knowledge_quiz_relations.attach(model)
                self.recheck(row, actor)
                atomic_json(model_path, model.payload())
                model_cached = False
            content = knowledge_algorithms.generate(kind, [], row['title'], options, model)
            references = set()

            def collect(value):
                if isinstance(value, dict):
                    references.update(value.get('sourceChunkIds', []))
                    for item in value.values():
                        collect(item)
                elif isinstance(value, list):
                    for item in value:
                        collect(item)

            collect(content)
            from time import time
            stamp = time()
            artifact = {'id': str(uuid4()), 'documentId': asset_id, 'libraryId': library_id,
                'assetId': asset_id, 'type': kind, 'scope': {'type': 'document'},
                'generator': 'document-knowledge-v3', 'generatorVersion': knowledge_quiz.VERSION if kind == 'QUIZ' else knowledge_algorithms.VERSION,
                'options': options, 'sourceRevision': manifest['files']['chunks.json'],
                'content': content, 'sourceChunkIds': sorted(references), 'createdAt': stamp, 'updatedAt': stamp,
                'analysis': {'sampled': bool(model.metrics.get('sampled')), 'knowledgeVersion': model.version,
                    'knowledgeCached': model_cached, 'metrics': model.metrics}}
            self.recheck(row, actor)
            atomic_json(target, artifact)
            self.recheck(row, actor)
            return {'artifact': artifact, 'cached': False}
        except (OSError, ValueError, TypeError):
            raise HTTPException(409, 'Knowledge Tools could not read this document. Ask library staff to retry.')
        finally:
            self._tools.release()

    def list_artifacts(self, library_id, asset_id, actor):
        row, directory, manifest, _ = self.prepared(library_id, asset_id, actor)
        items = []
        for target in sorted(safe_child(directory, 'knowledge').glob('*.json'))[:256]:
            target = safe_child(directory, 'knowledge', target.name)
            if target.name.endswith('.model.json'):
                continue
            try:
                artifact = bounded_json(target)
                kind = artifact['type']
                key = self._cache_identity(row, manifest, kind, artifact['options'])
                if target.stem == key and self.valid_artifact(artifact, row, manifest, kind, artifact['options']):
                    items.append(artifact)
            except (OSError, ValueError, KeyError, TypeError):
                continue
        self.recheck(row, actor)
        return {'artifacts': sorted(items, key=lambda item: item['updatedAt'], reverse=True)}

    def get_artifact(self, library_id, asset_id, actor, artifact_id):
        for artifact in self.list_artifacts(library_id, asset_id, actor)['artifacts']:
            if artifact['id'] == artifact_id:
                return artifact
        raise HTTPException(404, 'Study artifact not found. Generate it again.')

    def delete_artifact(self, library_id, asset_id, actor, artifact_id):
        # Derived shared tenant output is an asset mutation, restricted to staff.
        self.repository.authorize_asset(library_id, asset_id, actor, staff=True, ready=True)
        artifact = self.get_artifact(library_id, asset_id, actor, artifact_id)
        row, directory, manifest, _ = self.prepared(library_id, asset_id, actor)
        key = self._cache_identity(row, manifest, artifact['type'], artifact['options'])
        safe_child(directory, 'knowledge', key + '.json').unlink(missing_ok=True)
        self.recheck(row, actor)
        return {'removed': True}

    def source(self, library_id, asset_id, actor, chunk_id):
        row, _, _, chunks = self.prepared(library_id, asset_id, actor)
        for chunk in chunks:
            if chunk['chunk_id'] == chunk_id:
                self.recheck(row, actor)
                return {'chunkId': chunk_id, 'documentId': asset_id, 'libraryId': library_id,
                    'assetId': asset_id, 'filename': row['original_filename'], 'text': chunk['text'][:12000],
                    **knowledge_algorithms.provenance(chunk)}
        raise HTTPException(404, 'Source chunk not found.')

    def grade(self, library_id, asset_id, actor, artifact_id, item_id, answer):
        artifact = self.get_artifact(library_id, asset_id, actor, artifact_id)
        item = next((q for q in artifact['content'].get('questions', [])
                     if q['id'] == item_id and q['type'] == 'fill_blank'), None)
        if artifact['type'] != 'QUIZ' or item is None:
            raise HTTPException(404, 'Quiz item not found.')
        if not knowledge_cloze.validate(item):
            raise HTTPException(409, 'Generate this quiz again before checking answers.')
        try:
            result = cloze_grading.grade(item, answer, self.encoder)
        except (RuntimeError, ValueError, TimeoutError):
            raise HTTPException(503, 'Answer checking is temporarily unavailable. Keep your answer and retry.')
        self.get_artifact(library_id, asset_id, actor, artifact_id)
        return result


def install_worker(app, service):
    async def loop():
        from starlette.concurrency import run_in_threadpool
        while True:
            try:
                worked = await run_in_threadpool(service.run_one)
            except Exception:
                logger.warning('library_asset_worker_unavailable; retrying')
                worked = False
            await asyncio.sleep(.1 if worked else 2)

    @app.on_event('startup')
    async def startup():
        if os.environ.get('LIBRARY_ASSET_WORKER_ENABLED', '1') == '1':
            from starlette.concurrency import run_in_threadpool
            await run_in_threadpool(service.repository.ensure_indexes)
            app.state.library_asset_worker = asyncio.create_task(loop())

    @app.on_event('shutdown')
    async def shutdown():
        task = getattr(app.state, 'library_asset_worker', None)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
