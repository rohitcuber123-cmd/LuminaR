"""Tenant metadata and source access; model processing runs in the existing RAG app."""
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from backend.dependencies import get_current_user
from backend.schemas.library_assets import AssetStatus, AssetUpdate, Visibility
from backend.services import library_asset_service as service
from backend.services.library_asset_upload_limit import MAX_FILE_BYTES

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
    return FileResponse(service.source_path(row), media_type='application/pdf', filename=row['original_filename'],
        content_disposition_type='attachment' if download else 'inline',
        headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
                 'Content-Security-Policy': "sandbox; default-src 'none'"})
