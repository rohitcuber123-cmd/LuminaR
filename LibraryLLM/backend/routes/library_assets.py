"""Tenant metadata and source access; model processing runs in the existing RAG app."""
from uuid import UUID
from threading import BoundedSemaphore

from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from backend.dependencies import get_current_user
from backend.schemas.library_assets import AssetStatus, AssetUpdate, Visibility
from backend.services import library_asset_service as service
from backend.services.library_asset_upload_limit import MAX_FILE_BYTES

_preview_slots = BoundedSemaphore(2)

def private_response(response: Response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'


router = APIRouter(prefix='/libraries/{library_id}/assets', tags=['Library digital assets'],
                   dependencies=[Depends(private_response)])


@router.get('')
def listing(library_id: UUID, search: str = Query('', max_length=150), visibility: Visibility | None = None,
            status: AssetStatus | None = None, library_book_id: UUID | None = None,
            offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100), actor=Depends(get_current_user)):
    return service.listing(str(library_id), actor, search=search, visibility=visibility, status=status,
        library_book_id=str(library_book_id) if library_book_id else None, offset=offset, limit=limit)


@router.post('', status_code=202)
async def upload(library_id: UUID, file: UploadFile = File(...), title: str = Form('', max_length=200),
                 visibility: Visibility = Form('STAFF_ONLY'), library_book_id: UUID | None = Form(None),
                 upload_id: UUID = Header(alias='X-Luminar-Upload'), actor=Depends(get_current_user)):
    try:
        await run_in_threadpool(service.fresh_guard, str(library_id), actor, staff=True)
        content = await file.read(MAX_FILE_BYTES + 1)
        return await run_in_threadpool(service.upload, str(library_id), actor, content, file.filename,
            title, visibility, str(library_book_id) if library_book_id else None, str(upload_id))
    finally:
        await file.close()


@router.get('/{asset_id}')
def detail(library_id: UUID, asset_id: UUID, actor=Depends(get_current_user)):
    return service.detail(str(library_id), str(asset_id), actor)


@router.patch('/{asset_id}')
def update(library_id: UUID, asset_id: UUID, request: AssetUpdate, actor=Depends(get_current_user)):
    return service.update(str(library_id), str(asset_id), actor, request)


@router.delete('/{asset_id}')
def delete(library_id: UUID, asset_id: UUID, actor=Depends(get_current_user)):
    return service.delete(str(library_id), str(asset_id), actor)


@router.post('/{asset_id}/reprocess', status_code=202)
def reprocess(library_id: UUID, asset_id: UUID, actor=Depends(get_current_user)):
    return service.reprocess(str(library_id), str(asset_id), actor)


@router.get('/{asset_id}/file')
def file(library_id: UUID, asset_id: UUID, download: bool = False, actor=Depends(get_current_user)):
    row = service.authorize_asset(str(library_id), str(asset_id), actor, ready=True)
    return FileResponse(service.source_path(row), media_type=row.get('media_type', 'application/pdf'), filename=row['original_filename'],
        content_disposition_type='attachment' if download else 'inline',
        headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
                 'Content-Security-Policy': "sandbox; default-src 'none'"})


@router.get('/{asset_id}/preview')
def preview(library_id: UUID, asset_id: UUID, actor=Depends(get_current_user)):
    row = service.authorize_asset(str(library_id), str(asset_id), actor, ready=True)
    from backend.services.library_asset_text import extract_text
    if row.get('asset_type') not in {'TXT', 'DOCX'}:
        from fastapi import HTTPException
        raise HTTPException(400, 'Use the PDF document viewer for this source.')
    import hashlib
    from fastapi import HTTPException
    source = service.source_path(row).read_bytes()
    if len(source) != row['byte_size'] or hashlib.sha256(source).hexdigest() != row['checksum']:
        raise HTTPException(409, 'Document source integrity could not be verified.')
    return {'library_id': str(library_id), 'asset_id': str(asset_id),
        'text': extract_text(source, row['asset_type']),
        'preview_kind': 'extracted_text' if row['asset_type'] == 'DOCX' else 'plain_text'}


@router.get('/{asset_id}/preview/pages/{page_number}')
def pdf_page(library_id: UUID, asset_id: UUID, page_number: int, actor=Depends(get_current_user)):
    from fastapi import HTTPException
    import hashlib
    import pymupdf as fitz
    row = service.authorize_asset(str(library_id), str(asset_id), actor, ready=True)
    if row.get('asset_type', 'PDF') != 'PDF' or not 1 <= page_number <= 10000:
        raise HTTPException(404, 'PDF page not found.')
    if not _preview_slots.acquire(blocking=False):
        raise HTTPException(503, 'Document preview is busy. Please retry.')
    try:
        source = service.source_path(row).read_bytes()
        if len(source) != row['byte_size'] or hashlib.sha256(source).hexdigest() != row['checksum']:
            raise HTTPException(409, 'Document source integrity could not be verified.')
        with fitz.open(stream=source, filetype='pdf') as document:
            if page_number > document.page_count:
                raise HTTPException(404, 'PDF page not found.')
            page = document[page_number - 1]
            scale = min(2, 1600 / max(page.rect.width, page.rect.height))
            image = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False).tobytes('png')
        service.authorize_asset(str(library_id), str(asset_id), actor, ready=True)
        return Response(image, media_type='image/png', headers={'Cache-Control':'private, no-store', 'X-Content-Type-Options':'nosniff'})
    finally:
        _preview_slots.release()
