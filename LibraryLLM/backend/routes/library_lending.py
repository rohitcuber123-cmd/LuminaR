from datetime import datetime
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from backend.dependencies import get_current_user
from backend.schemas.library_lending import Command, Borrow, Review, Renew, Stock, Shelf, CopyCondition
from backend.services import library_lending_service as service

router = APIRouter(prefix='/libraries/{library_id}', tags=['Approval circulation'])


@router.get('/lending/resolve')
def resolve(library_id: UUID, global_work_id: str = Query(min_length=1, max_length=100), actor=Depends(get_current_user)):
    from backend.services.institution_repository import collection, library_mutation
    from fastapi import HTTPException
    with library_mutation(str(library_id), wait_seconds=30):
        service.access_locked(str(library_id), actor)
        books = list(collection('library_books').find(service.scoped(str(library_id), global_work_id=global_work_id, status='ACTIVE')).limit(2))
        if len(books) != 1:
            raise HTTPException(409, 'Choose the exact record from your library inventory.')
        return {'library_book_id': books[0]['library_book_id']}


@router.get('/lending/config')
def config(library_id: UUID, actor=Depends(get_current_user)):
    return service.config(str(library_id), actor)


@router.post('/staff/lending/activate')
def activate(library_id: UUID, request: Command, actor=Depends(get_current_user)):
    return service.activate(str(library_id), actor, request)


@router.get('/staff/canonical-defaults/preflight')
def canonical_preflight(library_id: UUID, actor=Depends(get_current_user)):
    from backend.services.library_canonical_defaults import promotion_preflight
    return promotion_preflight(str(library_id), actor)


@router.post('/staff/canonical-defaults/promote')
def promote_empty(library_id: UUID, request: Command, actor=Depends(get_current_user)):
    from backend.services.library_canonical_defaults import promote_empty
    return promote_empty(str(library_id), actor, request)


@router.get('/inventory/{library_book_id}/availability')
def availability(library_id: UUID, library_book_id: UUID, actor=Depends(get_current_user)):
    return service.availability(str(library_id), str(library_book_id), actor)


@router.post('/lending/borrow-requests', status_code=201)
def borrow(library_id: UUID, request: Borrow, actor=Depends(get_current_user)):
    return service.borrow(str(library_id), actor, request)


@router.get('/me/borrow-requests')
def mine(library_id: UUID, offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100), actor=Depends(get_current_user)):
    return service.rows(str(library_id), actor, offset=offset, limit=limit)


@router.get('/me/loans')
def loans(library_id: UUID, offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100), actor=Depends(get_current_user)):
    return service.rows(str(library_id), actor, offset=offset, limit=limit, loans=True)


@router.post('/lending/borrow-requests/{request_id}/cancel')
def cancel(library_id: UUID, request_id: UUID, request: Command, actor=Depends(get_current_user)):
    return service.review_borrow(str(library_id), str(request_id), actor, request, 'cancel')


@router.get('/staff/lending/{kind}-requests')
def queue(library_id: UUID, kind: Literal['borrow', 'return'], status: Literal['all', 'PENDING', 'APPROVED', 'REJECTED', 'CANCELLED', 'EXPIRED', 'COMPLETED'] = 'PENDING',
          search: str = Query('', max_length=150), user_id: int | None = Query(None, ge=1), since: datetime | None = None, until: datetime | None = None,
          offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100), actor=Depends(get_current_user)):
    return service.rows(str(library_id), actor, kind=kind.upper(), staff=True, status=status, search=search, user_id=user_id, since=since, until=until, offset=offset, limit=limit)


@router.get('/staff/loans')
def staff_loans(library_id: UUID, status: Literal['all', 'ACTIVE', 'RETURNED'] = 'all', search: str = Query('', max_length=150),
                user_id: int | None = Query(None, ge=1), since: datetime | None = None, until: datetime | None = None,
                offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100), actor=Depends(get_current_user)):
    """Expose the existing loan projection through staff authority, without personal endpoints."""
    return service.rows(str(library_id), actor, staff=True, loans=True, status=status, search=search,
                        user_id=user_id, since=since, until=until, offset=offset, limit=limit)


@router.post('/staff/lending/borrow-requests/{request_id}/{action}')
def review_borrow(library_id: UUID, request_id: UUID, action: Literal['approve', 'reject'], request: Review, actor=Depends(get_current_user)):
    return service.review_borrow(str(library_id), str(request_id), actor, request, action)


@router.post('/loans/{loan_id}/return-request', status_code=201)
def return_request(library_id: UUID, loan_id: UUID, request: Command, actor=Depends(get_current_user)):
    return service.return_request(str(library_id), str(loan_id), actor, request)


@router.post('/staff/lending/return-requests/{request_id}/{action}')
def review_return(library_id: UUID, request_id: UUID, action: Literal['confirm', 'reject'], request: Review, actor=Depends(get_current_user)):
    return service.review_return(str(library_id), str(request_id), actor, request, action)


@router.post('/loans/{loan_id}/renew')
def renew(library_id: UUID, loan_id: UUID, request: Renew, actor=Depends(get_current_user)):
    return service.renew(str(library_id), str(loan_id), actor, request)


@router.put('/staff/lending/books/{book_id}/stock')
def stock(library_id: UUID, book_id: UUID, request: Stock, actor=Depends(get_current_user)):
    return service.manage(str(library_id), str(book_id), actor, request, 'stock')


@router.put('/staff/lending/books/{book_id}/shelf')
def shelf(library_id: UUID, book_id: UUID, request: Shelf, actor=Depends(get_current_user)):
    return service.manage(str(library_id), str(book_id), actor, request, 'shelf')


@router.put('/staff/lending/books/{book_id}/copies/{copy_id}/condition')
def condition(library_id: UUID, book_id: UUID, copy_id: UUID, request: CopyCondition, actor=Depends(get_current_user)):
    return service.manage(str(library_id), str(book_id), actor, request, 'copy', str(copy_id))


@router.post('/staff/loans/{loan_id}/renew')
def assisted_renew(library_id: UUID, loan_id: UUID, request: Renew, actor=Depends(get_current_user)):
    return service.renew(str(library_id), str(loan_id), actor, request, staff=True)


@router.post('/staff/loans/{loan_id}/receive')
def assisted_receive(library_id: UUID, loan_id: UUID, request: Command, actor=Depends(get_current_user)):
    from uuid import uuid5, NAMESPACE_URL
    # Both stages reuse the canonical durable journal and existing physical receipt service.
    pending = service.return_request(str(library_id), str(loan_id), actor, request, staff=True)
    confirm = Review(idempotency_key=uuid5(NAMESPACE_URL, str(request.idempotency_key) + ':physical-receipt'))
    return service.review_return(str(library_id), pending['lending_request_id'], actor, confirm, 'confirm')
