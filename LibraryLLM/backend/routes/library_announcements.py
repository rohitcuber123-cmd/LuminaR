"""Institution communications; UUID paths and backend-derived identities only."""
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from backend.dependencies import get_current_user
from backend.schemas.library_announcements import DraftCreate, DraftUpdate, Revision, Status
from backend.services import library_announcement_service as service

router = APIRouter(prefix='/libraries/{library_id}', tags=['Library announcements'])

@router.get('/staff/announcement-recipients')
def recipients(library_id:UUID,q:str=Query(min_length=2,max_length=120),limit:int=Query(10,ge=1,le=20),actor=Depends(get_current_user)):
    return service.search_recipients(str(library_id),actor,q,limit)

@router.get('/announcements')
def listing(library_id:UUID, limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0,le=10000),actor=Depends(get_current_user)):
    return service.listing(str(library_id),actor,limit=limit,offset=offset)

@router.get('/staff/announcements')
def staff_listing(library_id:UUID,status:Status|None=None,limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0,le=10000),actor=Depends(get_current_user)):
    return service.listing(str(library_id),actor,staff=True,status=status,limit=limit,offset=offset)

@router.get('/announcements/{announcement_id}')
def detail(library_id:UUID,announcement_id:UUID,actor=Depends(get_current_user)):
    return service.detail(str(library_id),str(announcement_id),actor)

@router.get('/staff/announcements/{announcement_id}')
def staff_detail(library_id:UUID,announcement_id:UUID,actor=Depends(get_current_user)):
    return service.detail(str(library_id),str(announcement_id),actor,staff=True)

@router.post('/announcements',status_code=201)
def create(library_id:UUID,body:DraftCreate,actor=Depends(get_current_user)):
    return service.create(str(library_id),actor,body)

@router.patch('/announcements/{announcement_id}')
def update(library_id:UUID,announcement_id:UUID,body:DraftUpdate,actor=Depends(get_current_user)):
    return service.update(str(library_id),str(announcement_id),actor,body)

@router.post('/announcements/{announcement_id}/publish')
def publish(library_id:UUID,announcement_id:UUID,body:Revision,actor=Depends(get_current_user)):
    return service.publish(str(library_id),str(announcement_id),actor,body)

@router.post('/announcements/{announcement_id}/withdraw')
def withdraw(library_id:UUID,announcement_id:UUID,body:Revision,actor=Depends(get_current_user)):
    return service.withdraw(str(library_id),str(announcement_id),actor,body)

@router.post('/announcements/{announcement_id}/delivery/retry')
def retry(library_id:UUID,announcement_id:UUID,actor=Depends(get_current_user)):
    return service.retry_delivery(str(library_id),str(announcement_id),actor)
