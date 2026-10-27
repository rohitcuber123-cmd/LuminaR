from uuid import UUID
from typing import Literal
from fastapi import APIRouter,Depends,Query,Response
from pydantic import BaseModel,ConfigDict
from backend.dependencies import get_current_user
from backend.services import library_intelligence_store as store,library_intelligence_service as service

def private(response:Response):response.headers['Cache-Control']='private, no-store'
router=APIRouter(prefix='/libraries/{library_id}/intelligence',tags=['Library catalogue intelligence'],dependencies=[Depends(private)])
class BuildRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    target:Literal['SEARCH_INDEX','KNOWLEDGE_GRAPH']
    generation_id:UUID|None=None
@router.get('')
def status(library_id:UUID,actor=Depends(get_current_user)):return service.status(str(library_id),actor)
@router.post('/builds',status_code=202)
def build(library_id:UUID,request:BuildRequest,actor=Depends(get_current_user)):return store.request_build(str(library_id),actor,request.target,str(request.generation_id) if request.generation_id else None,require_nonempty=True)
@router.get('/jobs/{job_id}')
def job(library_id:UUID,job_id:UUID,actor=Depends(get_current_user)):return store.scoped_job(str(library_id),str(job_id),actor)
@router.get('/generations/{generation_id}')
def generation(library_id:UUID,generation_id:UUID,actor=Depends(get_current_user)):return store.scoped_generation(str(library_id),str(generation_id),actor)
@router.get('/reconciliation')
def reconcile(library_id:UUID,actor=Depends(get_current_user)):return service.reconcile(str(library_id),actor)
@router.post('/jobs/{job_id}/recover')
def recover(library_id:UUID,job_id:UUID,actor=Depends(get_current_user)):return service.recover(str(library_id),actor,str(job_id))
@router.get('/graph')
def graph(library_id:UUID,staff:bool=False,query:str=Query('',max_length=150),limit:int=Query(50,ge=1,le=100),actor=Depends(get_current_user)):return service.graph(str(library_id),actor,staff=staff,query=query,limit=limit)
