"""Canonical institution inventory; legacy /inventory remains a separate compatibility API."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, File, Query, UploadFile, Header
from starlette.concurrency import run_in_threadpool
from backend.dependencies import get_current_user
from backend.schemas.library_catalogue import BookCreate, BookUpdate, HoldingUpdate, LinkGlobal, CopyCreate, ImportApply
from backend.services import library_catalogue_service as service, library_inventory_import as importer

router = APIRouter(prefix='/libraries/{library_id}/inventory', tags=['Institution inventory'])


@router.get('/books')
def listing(library_id: UUID, search: str = Query('', max_length=150), kind: Literal['all', 'global', 'local', 'review'] = 'all',
            state: Literal['active', 'withdrawn', 'all'] = 'active', offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100),
            actor=Depends(get_current_user)):
    return service.list_books(str(library_id), actor, search=search, kind=kind, state=state, offset=offset, limit=limit)


@router.post('/books', status_code=201)
def create(library_id: UUID, request: BookCreate, actor=Depends(get_current_user)):
    return service.create_book(str(library_id), request, actor)


@router.get('/books/{library_book_id}')
def detail(library_id: UUID, library_book_id: UUID, actor=Depends(get_current_user)):
    return service.get_book(str(library_id), str(library_book_id), actor)


@router.patch('/books/{library_book_id}')
def update(library_id: UUID, library_book_id: UUID, request: BookUpdate, actor=Depends(get_current_user)):
    return service.update_book(str(library_id), str(library_book_id), request, actor)


@router.put('/books/{library_book_id}/holding')
def holding(library_id: UUID, library_book_id: UUID, request: HoldingUpdate, actor=Depends(get_current_user)):
    return service.update_holding(str(library_id), str(library_book_id), request, actor)


@router.put('/books/{library_book_id}/global-link')
def link(library_id: UUID, library_book_id: UUID, request: LinkGlobal, actor=Depends(get_current_user)):
    return service.link_global(str(library_id), str(library_book_id), request, actor)


@router.delete('/books/{library_book_id}')
def withdraw(library_id: UUID, library_book_id: UUID, idempotency_key: UUID | None = Header(None), actor=Depends(get_current_user)):
    return service.withdraw(str(library_id), str(library_book_id), actor, str(idempotency_key) if idempotency_key else None)


@router.get('/books/{library_book_id}/copies')
def copies(library_id: UUID, library_book_id: UUID, offset: int = Query(0, ge=0, le=100000), limit: int = Query(100, ge=1, le=100), actor=Depends(get_current_user)):
    return service.copies(str(library_id), str(library_book_id), actor, offset, limit)


@router.post('/books/{library_book_id}/copies', status_code=201)
def copy(library_id: UUID, library_book_id: UUID, request: CopyCreate, actor=Depends(get_current_user)):
    return service.create_copy(str(library_id), str(library_book_id), request, actor)


@router.post('/imports/preview', status_code=201)
async def preview(library_id: UUID, file: UploadFile = File(...), actor=Depends(get_current_user)):
    # Authenticate tenant before reading the file or performing catalogue lookups.
    from backend.services.library_inventory_access import require_library_staff
    await run_in_threadpool(require_library_staff, str(library_id), actor)
    try:
        content = await file.read(importer.MAX_BYTES + 1)
        return await run_in_threadpool(importer.preview, str(library_id), file.filename, content, actor)
    finally:
        await file.close()


@router.post('/imports/{import_id}/apply')
def apply(library_id: UUID, import_id: UUID, request: ImportApply, actor=Depends(get_current_user)):
    return importer.apply(str(library_id), str(import_id), request, actor)


@router.get('/imports/{import_id}')
def status(library_id: UUID, import_id: UUID, actor=Depends(get_current_user)):
    return importer.job_status(str(library_id), str(import_id), actor)
