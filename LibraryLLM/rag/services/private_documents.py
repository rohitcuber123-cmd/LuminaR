"""Session-owned upload artifacts, isolated from permanent library book assets."""
import contextlib
import hashlib
import json
import logging
import shutil
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

import faiss
import numpy as np
from fastapi import HTTPException

from backend.services.login_sessions import is_revoked, revoke
from rag.services.document_service import DocumentService
from rag.services.local_document_cache import LocalDocumentCache, DIMENSION, MAX_CHUNKS


logger = logging.getLogger('uvicorn.error')

class PrivateDocuments:
    def __init__(self, root, model, retriever=None, latency=None, cache=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.model, self.retriever, self.latency = model, retriever, latency
        self.cache = cache or LocalDocumentCache()
        self.processor = DocumentService.__new__(DocumentService)
        self.processor.model = model
        self.metrics = {'uploads': 0, 'parse_calls': 0, 'chunk_calls': 0, 'embedding_calls': 0, 'faiss_builds': 0, 'ingest_seconds_total': 0.0, 'restore_seconds_total': 0.0, 'export_seconds_total': 0.0}
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, owner TEXT NOT NULL, sid TEXT NOT NULL, expires REAL NOT NULL, state TEXT NOT NULL, cache_id TEXT, metadata TEXT NOT NULL)')
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS restored_session ON documents(owner,sid,cache_id) WHERE cache_id IS NOT NULL')
        if retriever is not None:
            self.clear_runtime()

    @contextlib.contextmanager
    def db(self):
        db = sqlite3.connect(self.root / 'registry.sqlite', timeout=15)
        db.execute('PRAGMA secure_delete=ON')
        db.execute('PRAGMA foreign_keys=ON')
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def identity(self, user):
        if not user or not user.get('sid') or not user.get('sub') or user.get('exp', 0) <= time.time() or is_revoked(user['sid']):
            raise HTTPException(401, 'Sign in again to use private documents.')
        return str(user['sub']), user['sid']

    def directory(self, document_id):
        if len(document_id) != 36 or not document_id.startswith('doc_'):
            raise HTTPException(404, 'Document not found.')
        try:
            int(document_id[4:], 16)
        except ValueError:
            raise HTTPException(404, 'Document not found.')
        path = (self.root / document_id).resolve()
        if path.parent != self.root:
            raise HTTPException(404, 'Document not found.')
        return path

    def owned(self, document_id, user):
        owner, sid = self.identity(user)
        with self.db() as db:
            row = db.execute("SELECT * FROM documents WHERE id=? AND owner=? AND sid=? AND state='ACTIVE' AND expires>?", (document_id, owner, sid, time.time())).fetchone()
        if row is None:
            raise HTTPException(404, 'Document not found.')
        return dict(row)

    def public(self, row):
        meta = json.loads(row['metadata'])
        return {k: meta[k] for k in ('document_id', 'filename', 'pages', 'chunks', 'status')}

    def list(self, user):
        owner, sid = self.identity(user)
        with self.db() as db:
            rows = db.execute("SELECT * FROM documents WHERE owner=? AND sid=? AND state='ACTIVE' AND expires>?", (owner, sid, time.time())).fetchall()
        return [self.public(row) for row in rows]

    def begin(self, user, filename, digest, pages=0, chunks=0, cache_id=None):
        owner, sid = self.identity(user)
        document_id = 'doc_' + uuid4().hex
        meta = {'document_id': document_id, 'filename': filename, 'document_sha256': digest, 'pages': pages,
                'chunks': chunks, 'status': 'ACTIVE', 'owner_user_id': owner, 'owner_session_id': sid,
                'expires_at': user['exp'], 'cache_id': cache_id}
        with self.db() as db:
            db.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?)', (document_id, owner, sid, user['exp'], 'INGESTING', cache_id, json.dumps(meta)))
        self.directory(document_id).mkdir()
        return meta

    def publish(self, meta, chunks, vectors, user):
        self.identity(user)  # Logout during preparation cannot publish data.
        path = self.directory(meta['document_id'])
        chunks = [dict(c, document_id=meta['document_id'], filename=meta['filename']) for c in chunks]
        meta['chunks'] = len(chunks)
        (path / 'chunks.json').write_text(json.dumps(chunks, ensure_ascii=False), encoding='utf-8')
        np.save(path / 'vectors.npy', vectors, allow_pickle=False)
        started = time.perf_counter()
        index = faiss.IndexFlatIP(DIMENSION)
        index.add(vectors)
        faiss.write_index(index, str(path / 'runtime.faiss'))
        self.metrics['faiss_builds'] += 1
        elapsed = time.perf_counter() - started
        with self.db() as db:
            db.execute("UPDATE documents SET state='ACTIVE',metadata=? WHERE id=? AND state='INGESTING'", (json.dumps(meta), meta['document_id']))
        return elapsed

    def ingest(self, content, filename, user):
        started = time.perf_counter()
        meta = self.begin(user, filename, hashlib.sha256(content).hexdigest())
        path = self.directory(meta['document_id'])
        raw = path / (meta['document_id'] + '.pdf')
        try:
            raw.write_bytes(content)
            self.metrics['parse_calls'] += 1
            pages = self.processor.extract_pdf(raw)
            if not 0 < len(pages) <= 10000:
                raise HTTPException(413, 'Document has too many pages.')
            self.metrics['chunk_calls'] += 1
            chunks = self.processor.create_chunks(meta['document_id'], filename, pages)
            if not 0 < len(chunks) <= MAX_CHUNKS:
                raise HTTPException(400, 'No usable text, or document exceeds the chunk limit.')
            meta['pages'] = len(pages)
            (path / 'extracted.json').write_text(json.dumps(pages, ensure_ascii=False), encoding='utf-8')
            self.metrics['embedding_calls'] += 1
            vectors = self.processor.embed_chunks(chunks)
            faiss_time = self.publish(meta, chunks, vectors, user)
            self.metrics['uploads'] += 1
            self.metrics['ingest_seconds_total'] += time.perf_counter() - started
            logger.info('private_document_prepared document_id=%s seconds=%.4f', meta['document_id'], time.perf_counter() - started)
            return {**self.public({'metadata': json.dumps(meta)}), 'preparation_seconds': time.perf_counter() - started,
                    'faiss_seconds': faiss_time}
        except Exception:
            self.purge(meta['document_id'])
            raise

    def prepared(self, document_id, user):
        row = self.owned(document_id, user)
        path = self.directory(document_id)
        chunks = json.loads((path / 'chunks.json').read_text(encoding='utf-8'))
        vectors = np.load(path / 'vectors.npy', allow_pickle=False)
        return row, chunks, vectors

    def export(self, document_id, user):
        started = time.perf_counter()
        row, chunks, vectors = self.prepared(document_id, user)
        meta = json.loads(row['metadata'])
        blob, descriptor = self.cache.export(user['sub'], meta, chunks, vectors)
        # Persist only the opaque cache identity for retry/idempotency, never ciphertext.
        meta['cache_id'] = descriptor['cache_id']
        with self.db() as db:
            db.execute('UPDATE documents SET cache_id=?,metadata=? WHERE id=?', (descriptor['cache_id'], json.dumps(meta), document_id))
        elapsed = time.perf_counter() - started
        self.metrics['export_seconds_total'] += elapsed
        logger.info('device_cache_export cache_id=%s document_id=%s owner_scope=%s format=%s bytes=%s seconds=%.4f', descriptor['cache_id'], document_id, descriptor['owner_scope_id'], descriptor['format_version'], len(blob), elapsed)
        return blob, descriptor

    def restore(self, blob, user):
        started = time.perf_counter()
        owner, sid = self.identity(user)
        self.sweep()
        try:
            header, payload = self.cache.decrypt(owner, blob, 'bundle')
            manifest, chunks, vectors = self.cache.unpack(payload, header['cache_id'])
        except HTTPException as exc:
            self.cache.record_failure(exc)
            raise
        with self.db() as db:
            existing = db.execute("SELECT * FROM documents WHERE owner=? AND sid=? AND cache_id=? AND state='ACTIVE' AND expires>?", (owner, sid, header['cache_id'], time.time())).fetchone()
        if existing:
            return {**self.public(existing), 'already_active': True}
        meta = self.begin(user, manifest['filename'], manifest['document_sha256'], manifest['pages'], len(chunks), header['cache_id'])
        try:
            faiss_time = self.publish(meta, chunks, vectors, user)
            self.cache.metrics['restores'] += 1
            elapsed = time.perf_counter() - started
            self.metrics['restore_seconds_total'] += elapsed
            logger.info('device_cache_restore cache_id=%s document_id=%s owner_scope=%s format=%s bytes=%s seconds=%.4f', header['cache_id'], meta['document_id'], header['owner_scope_id'], header['format_version'], len(blob), elapsed)
            return {**self.public({'metadata': json.dumps(meta)}), 'restore_seconds': time.perf_counter() - started, 'faiss_seconds': faiss_time}
        except Exception:
            self.purge(meta['document_id'])
            raise

    def clear_runtime(self):
        if self.retriever is not None:
            self.retriever.doc_index = None
            self.retriever.doc_metadata = []
            self.retriever.doc_ids = set()
            self.retriever.doc_chunk_texts = {}
        if self.latency is not None:
            self.latency.clear_cache()

    @contextlib.contextmanager
    def selected(self, document_id, user):
        self.owned(document_id, user)
        path = self.directory(document_id)
        chunks = json.loads((path / 'chunks.json').read_text(encoding='utf-8'))
        self.retriever.doc_index = faiss.read_index(str(path / 'runtime.faiss'))
        self.retriever.doc_metadata = [{k: c[k] for k in ('chunk_id', 'document_id', 'filename', 'page')} for c in chunks]
        self.retriever.doc_ids = {document_id}
        self.retriever.doc_chunk_texts = {c['chunk_id']: c['text'] for c in chunks}
        try:
            yield
        finally:
            self.clear_runtime()

    def purge(self, document_id):
        path = self.directory(document_id)
        with self.db() as db:
            db.execute("UPDATE documents SET state='DELETING' WHERE id=?", (document_id,))
        self.clear_runtime()
        try:
            if path.exists():
                shutil.rmtree(path)
            with self.db() as db:
                db.execute('DELETE FROM documents WHERE id=?', (document_id,))
            return True
        except OSError:
            return False  # Access remains disabled; sweeper retries.

    def logout(self, user):
        # Revocation precedes deletion. Even failed cleanup never reopens access.
        owner, sid = self.identity(user)
        revoke(user)
        with self.db() as db:
            ids = [r[0] for r in db.execute('SELECT id FROM documents WHERE owner=? AND sid=?', (owner, sid))]
        result = [self.purge(doc) for doc in ids]
        logger.info('private_document_cleanup reason=logout purged=%s pending=%s', sum(result), result.count(False))
        return {'purged': sum(result), 'pending': result.count(False), 'server_copies_removed': all(result)}

    def sweep(self):
        with self.db() as db:
            rows = db.execute('SELECT id,sid,expires,state FROM documents').fetchall()
        for row in rows:
            if row['expires'] <= time.time() or row['state'] != 'ACTIVE' or is_revoked(row['sid']):
                reason = 'expired' if row['expires'] <= time.time() else ('interrupted' if row['state'] != 'ACTIVE' else 'revoked')
                removed = self.purge(row['id'])
                logger.info('private_document_cleanup document_id=%s reason=%s removed=%s', row['id'], reason, removed)
        # Interrupted writes with no registry record are safe to remove.
        with self.db() as db:
            known = {r[0] for r in db.execute('SELECT id FROM documents')}
        for path in self.root.glob('doc_*'):
            if path.is_dir() and path.name not in known:
                self.purge(path.name)
