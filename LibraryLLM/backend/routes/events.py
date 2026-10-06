from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from backend.dependencies import get_current_user
from backend.services.identity_service import current_identity
from backend.schemas.events import Category, Status, EventCreate, EventPatch, SeenRequest
from backend.services import event_service as service

def account(payload=Depends(get_current_user)):
    try: user=current_identity(payload)
    except (ValueError,KeyError,TypeError): user=None
    if not user:raise HTTPException(401,'Account is unavailable.')
    return user

def staff(user=Depends(account)):
    if user['role'] not in {'ADMIN','LIBRARIAN'}:raise HTTPException(403,'Library staff access required.')
    return user

router=APIRouter(prefix='/events',tags=['Events'])
staff_router=APIRouter(prefix='/staff/events',tags=['Staff events'],dependencies=[Depends(staff)])

@router.get('/unseen')
def unseen(user=Depends(account)):
    return service.unseen(user)

@router.post('/mark-seen')
def mark_seen(body:SeenRequest,user=Depends(account)):
    return service.mark_seen(body.cursor,user)

@router.get('')
def events(view:Literal['upcoming','past']='upcoming',category:Category|None=None,query:str=Query('',max_length=120),
           featured:bool|None=None,page:int=Query(1,ge=1,le=100000),page_size:int=Query(12,ge=1,le=50),user=Depends(account)):
    # Freeze acknowledgement before reading/hydrating the page. A publication
    # arriving during that read must remain unseen, even if absent from its rows.
    snapshot=service.unseen(user)
    result=service.listing(view,category.value if category else None,query,featured,page,page_size)
    result['seen_cursor']=snapshot['seen_cursor']
    return result

@router.get('/{event_id}')
def detail(event_id:UUID,user=Depends(account)):
    row=service.document(event_id)
    if row['status'] not in {'PUBLISHED','CANCELLED'} or not row['published_at']:
        raise HTTPException(404,'Event not found.')
    return service.hydrate([row])[0]

@staff_router.get('')
def manage(status:Status|None=None,category:Category|None=None,query:str=Query('',max_length=120),
           page:int=Query(1,ge=1,le=100000),page_size:int=Query(12,ge=1,le=50),sort:Literal['updated','created','start']='updated'):
    return service.listing(None,category.value if category else None,query,None,page,page_size,
                           status.value if status else None,sort,True)

@staff_router.get('/{event_id}')
def managed_detail(event_id:UUID):
    return service.hydrate([service.document(event_id)],True)[0]

@staff_router.post('',status_code=201)
def create(body:EventCreate,user=Depends(staff)):
    return service.create(body,int(user['sub']))

@staff_router.patch('/{event_id}')
def edit(event_id:UUID,body:EventPatch,user=Depends(staff)):
    return service.edit(event_id,body,int(user['sub']))

@staff_router.post('/{event_id}/publish')
def publish(event_id:UUID,user=Depends(staff)):
    return service.transition(event_id,'publish',int(user['sub']))

@staff_router.post('/{event_id}/cancel')
def cancel(event_id:UUID,user=Depends(staff)):
    return service.transition(event_id,'cancel',int(user['sub']))

@staff_router.post('/{event_id}/archive')
def archive(event_id:UUID,user=Depends(staff)):
    return service.transition(event_id,'archive',int(user['sub']))

@staff_router.delete('/{event_id}')
def delete(event_id:UUID):
    return service.delete_draft(event_id)
