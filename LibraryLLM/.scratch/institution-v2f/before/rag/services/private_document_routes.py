"""Authenticated lifecycle endpoints; heavy operations share the engine lock."""
import asyncio
import contextlib
import json
import logging
import re
import time
from threading import Lock
from pathlib import Path

from fastapi import Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend.dependencies import get_current_user
from rag.services.local_document_cache import MAX_BYTES, fingerprint


class InspectRequest(BaseModel):
    descriptors: list[str] = Field(max_length=20)


def install_private_documents(app, service, engine):
    preparations = {}
    preparation_lock = Lock()

    def preparation_key(user, key):
        owner, sid = service.identity(user)
        if not re.fullmatch(r'[a-fA-F0-9-]{36}', key):
            raise HTTPException(422, 'Invalid preparation ID.')
        return owner, sid, key

    @app.get('/rag/preparation/{preparation_id}')
    def preparation(preparation_id: str, user=Depends(get_current_user)):
        key = preparation_key(user, preparation_id)
        with preparation_lock:
            row = preparations.get(key)
            if not row:
                raise HTTPException(404, 'Preparation not found.')
            return {'stage': row['stage']}

    def locked(operation, *args):
        with engine.inference_lock:
            return operation(*args)

    async def bounded(stream):
        content = bytearray()
        async for piece in stream:
            if len(content) + len(piece) > MAX_BYTES:
                raise HTTPException(413, 'Document exceeds the upload/cache size limit.')
            content.extend(piece)
        if not content:
            raise HTTPException(400, 'Empty document.')
        return bytes(content)

    async def pieces(file):
        while piece := await file.read(1024 * 1024):
            yield piece

    @app.post('/rag/upload')
    async def upload(request: Request, file: UploadFile = File(...), user=Depends(get_current_user)):
        key = None
        registered = False
        def progress(stage):
            if key:
                with preparation_lock:
                    if key in preparations:
                        preparations[key]['stage'] = stage
        try:
            service.identity(user)
            filename = Path((file.filename or '').replace('\\', '/')).name
            if not filename.lower().endswith('.pdf') or len(filename) > 255:
                raise HTTPException(400, 'Choose a PDF with a filename under 256 characters.')
            preparation_id = request.headers.get('X-Luminar-Preparation')
            key = preparation_key(user, preparation_id) if preparation_id else None
            if key:
                with preparation_lock:
                    for expired in [k for k,v in preparations.items() if v['created'] < time.time()-600]:
                        del preparations[expired]
                    if len(preparations)>=32 or key in preparations:
                        raise HTTPException(429, 'Document preparation is busy. Please retry shortly.')
                    preparations[key] = {'stage':'PREPARING_DOCUMENT','created':time.time()}
                    registered = True
            content = await bounded(pieces(file))
            if not content.startswith(b'%PDF-'):
                raise HTTPException(400, 'Invalid PDF.')
            # CPU extraction/OCR must not hold the interactive RAG/GPU lock.
            result = await run_in_threadpool(service.ingest, content, filename, user, engine.inference_lock, progress)
            return {'message': 'PDF prepared for this session.', 'document': result}
        finally:
            if registered:
                with preparation_lock:
                    preparations.pop(key, None)
            await file.close()

    @app.get('/rag/documents')
    def documents(user=Depends(get_current_user)):
        rows = service.list(user)
        return {'count': len(rows), 'documents': rows}

    @app.get('/rag/documents/{document_id}')
    def document(document_id: str, user=Depends(get_current_user)):
        return service.public(service.owned(document_id, user))

    @app.delete('/rag/documents/{document_id}')
    def delete(document_id: str, user=Depends(get_current_user)):
        with engine.inference_lock:
            service.owned(document_id, user)
            return {'removed': service.purge(document_id)}

    @app.post('/rag/session/logout')
    def logout(user=Depends(get_current_user)):
        with engine.inference_lock:
            result = service.logout(user)
            orchestrator = getattr(app.state, 'assistant', None)
            if orchestrator:
                owner = f"{user['sub']}:{user.get('sid', 'legacy')}"
                for key, value in list(orchestrator.store.entries.items()):
                    if value.owner == owner:
                        del orchestrator.store.entries[key]
            return result

    @app.get('/rag/local-cache/scope')
    def scope(user=Depends(get_current_user)):
        service.identity(user)
        if not service.cache.enabled:
            return {'enabled': False}
        return {'enabled': True, 'owner_scope_id': service.cache.scope(user['sub']),
                'pipeline_fingerprint': fingerprint(), 'max_bundle_bytes': MAX_BYTES, 'format_version': 1}

    @app.post('/rag/documents/{document_id}/cache/export')
    def export(document_id: str, user=Depends(get_current_user)):
        with engine.inference_lock:
            blob, metadata = service.export(document_id, user)
        return Response(blob, media_type='application/octet-stream', headers={
            'X-Luminar-Cache': json.dumps(metadata, separators=(',', ':')), 'Cache-Control': 'no-store'})

    @app.post('/rag/local-cache/inspect')
    def inspect(request: InspectRequest, user=Depends(get_current_user)):
        service.identity(user)
        # Per-entry errors keep one damaged descriptor from hiding other copies.
        results = []
        for descriptor in request.descriptors:
            try:
                results.append({'descriptor': service.cache.inspect(user['sub'], descriptor)})
            except HTTPException as exc:
                results.append({'error': exc.detail})
        return {'items': results}

    @app.post('/rag/local-cache/restore')
    async def restore(request: Request, user=Depends(get_current_user)):
        service.identity(user)
        service.cache.require_enabled()
        blob = await bounded(request.stream())
        try:
            result = await run_in_threadpool(locked, service.restore, blob, user)
            return {'document': result}
        except HTTPException:
            raise

    async def sweep_loop():
        while True:
            await asyncio.sleep(60)
            try:
                await run_in_threadpool(locked, service.sweep)
            except Exception:
                logging.getLogger('uvicorn.error').warning('private_document_cleanup reason=sweeper_failed; retrying next interval')

    @app.on_event('startup')
    async def startup():
        await run_in_threadpool(locked, service.sweep)
        app.state.document_sweeper = asyncio.create_task(sweep_loop())

    @app.on_event('shutdown')
    async def shutdown():
        task = getattr(app.state, 'document_sweeper', None)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
