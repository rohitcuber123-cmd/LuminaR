from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from backend.dependencies import get_current_user
from backend.schemas.events import Category, Status, TenantEventCreate, TenantEventPatch, EventCancellation
from backend.services import library_event_service as service

router = APIRouter(prefix='/libraries/{library_id}', tags=['Library events'])


@router.get('/events')
def events(library_id: UUID, view: Literal['upcoming', 'past', 'cancelled'] = 'upcoming',
           category: Category | None = None, query: str = Query('', max_length=120),
           page: int = Query(1, ge=1, le=20000), page_size: int = Query(12, ge=1, le=50), actor=Depends(get_current_user)):
    return service.listing(str(library_id), actor, view, category.value if category else None, query, page, page_size)


@router.get('/staff/events')
def staff_events(library_id: UUID, view: Literal['upcoming', 'past', 'cancelled'] | None = None,
                 status: Status | None = None, category: Category | None = None, query: str = Query('', max_length=120),
                 page: int = Query(1, ge=1, le=20000), page_size: int = Query(12, ge=1, le=50), actor=Depends(get_current_user)):
    return service.listing(str(library_id), actor, view, category.value if category else None, query, page, page_size,
                           staff=True, status=status.value if status else None)


@router.get('/events/{event_id}')
def detail(library_id: UUID, event_id: UUID, actor=Depends(get_current_user)):
    return service.detail(str(library_id), str(event_id), actor)


@router.get('/staff/events/{event_id}')
def staff_detail(library_id: UUID, event_id: UUID, actor=Depends(get_current_user)):
    return service.detail(str(library_id), str(event_id), actor, staff=True)


@router.post('/events', status_code=201)
def create(library_id: UUID, body: TenantEventCreate, actor=Depends(get_current_user)):
    return service.mutate(str(library_id), actor, 'create', body=body)


@router.patch('/events/{event_id}')
def edit(library_id: UUID, event_id: UUID, body: TenantEventPatch, actor=Depends(get_current_user)):
    return service.mutate(str(library_id), actor, 'edit', body=body, event_id=str(event_id))


@router.post('/events/{event_id}/publish')
def publish(library_id: UUID, event_id: UUID, actor=Depends(get_current_user)):
    return service.mutate(str(library_id), actor, 'publish', event_id=str(event_id))


@router.post('/events/{event_id}/cancel')
def cancel(library_id: UUID, event_id: UUID, body: EventCancellation, actor=Depends(get_current_user)):
    return service.mutate(str(library_id), actor, 'cancel', event_id=str(event_id), body=body)


@router.post('/events/{event_id}/archive')
def archive(library_id: UUID, event_id: UUID, actor=Depends(get_current_user)):
    return service.mutate(str(library_id), actor, 'archive', event_id=str(event_id))


@router.delete('/events/{event_id}')
def delete_draft(library_id: UUID, event_id: UUID, actor=Depends(get_current_user)):
    return service.mutate(str(library_id), actor, 'delete', event_id=str(event_id))


@router.get('/notifications/{notification_id}')
def scoped_notification(library_id: UUID, notification_id: str, actor=Depends(get_current_user)):
    from backend.services import notification_service as ns
    from backend.services.library_inventory_access import eligible_actor
    from fastapi import HTTPException
    user = eligible_actor(actor)
    try:
        return ns.get_own(int(user['sub']), notification_id, str(library_id))
    except LookupError as error:
        raise HTTPException(404, str(error))
