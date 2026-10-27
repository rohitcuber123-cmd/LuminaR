from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Path, Response
from pydantic import BaseModel, Field
from backend.dependencies import get_current_user
from backend.services import library_catalogue_experience as service

router = APIRouter(prefix='/libraries/{library_id}/catalogue', tags=['Library catalogue experience'])


@router.get('/facets')
def facets(library_id:UUID,response:Response,staff:bool=False,actor=Depends(get_current_user)):
    response.headers['Cache-Control']='private, no-store'
    from search.query_execution import tenant_facets
    return tenant_facets(str(library_id),actor,staff)


@router.get('/discovery')
def discovery(library_id:UUID,response:Response,search:str=Query('',max_length=150),staff:bool=False,
              mode:Literal['SMART','GENRE_SUBJECT','TITLE_AUTHOR','EXACT']='SMART',
              offset:int=Query(0,ge=0,le=100000),limit:int=Query(20,ge=1,le=100),
              subject:str=Query('',max_length=200),author:str=Query('',max_length=150),
              rating_min:float|None=Query(None,ge=0,le=5),rating_max:float|None=Query(None,ge=0,le=5),
              year_min:int|None=Query(None,ge=1000,le=2100),year_max:int|None=Query(None,ge=1000,le=2100),
              format:Literal['','ONLINE','PHYSICAL','BOTH']='',availability:Literal['','AVAILABLE_NOW','REQUESTABLE']='',
              language:str=Query('',max_length=60),sort:str=Query('RELEVANCE',max_length=30),
              circulation_status:str=Query('',max_length=40),omit:str=Query('',max_length=200),session_id:str|None=Query(None,max_length=36),personalized:bool=False,actor=Depends(get_current_user)):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from search.query_execution import tenant_search
    response.headers['Cache-Control']='private, no-store'
    def unavailable(*args):raise HTTPException(503,'Semantic service unavailable.')
    fallback=SimpleNamespace(cache=SimpleNamespace(load=unavailable))
    filters={key:value for key,value in locals().items() if key in ('subject','author','rating_min','rating_max','year_min','year_max','format','availability','language','circulation_status')}
    filters['sort']=sort.upper() if sort.upper() in ('RELEVANCE','RATING','NEWEST','TITLE') else 'RELEVANCE'
    try:return tenant_search(fallback,str(library_id),actor,search,staff=staff,mode=mode,filters=filters,omit=omit.split(','),offset=offset,limit=limit,session_id=session_id,personalized=personalized)
    except ValueError as error:raise HTTPException(422,str(error)) from error


@router.get('/source')
def source(library_id: UUID, staff: bool = False, actor=Depends(get_current_user)):
    return service.source(str(library_id), actor, staff=staff)


@router.get('/home')
def home(library_id: UUID, actor=Depends(get_current_user)):
    return service.home(str(library_id), actor)


class RecommendationCandidates(BaseModel):
    work_ids: list[str] = Field(default_factory=list, max_length=200)
    limit: int = Field(default=10, ge=1, le=50)


@router.post('/recommendations')
def recommendations(library_id: UUID, body: RecommendationCandidates, actor=Depends(get_current_user)):
    # Read-only candidate scoping. No recommendation training, feedback or global writes.
    return service.recommendations(str(library_id), actor, body.work_ids, body.limit)


@router.get('/books')
def books(library_id: UUID, search: str = Query('', max_length=150), subject: str = Query('', max_length=200),
          author: str = Query('', max_length=150), circulation_status: Literal['', 'CIRCULATING', 'REFERENCE_ONLY', 'TEMPORARILY_UNAVAILABLE'] = '',
          sort: Literal['title', 'new_arrivals', 'popular'] = 'title', offset: int = Query(0, ge=0, le=100000),
          limit: int = Query(20, ge=1, le=50), staff: bool = False, actor=Depends(get_current_user)):
    return service.books(str(library_id), actor, search=search, subject=subject, author=author,
        circulation_status=circulation_status, sort=sort, offset=offset, limit=limit, staff=staff)


@router.get('/genres')
def genres(library_id: UUID, offset: int = Query(0, ge=0, le=100000), limit: int = Query(50, ge=1, le=100), staff: bool = False, actor=Depends(get_current_user)):
    return service.genres(str(library_id), actor, offset, limit, staff=staff)


@router.get('/books/{library_book_id}')
def detail(library_id: UUID, library_book_id: UUID, staff: bool = False, actor=Depends(get_current_user)):
    return service.detail(str(library_id), str(library_book_id), actor, staff=staff)


@router.get('/global-books/{work_id}')
def global_context(library_id: UUID, work_id: str = Path(pattern=r'^OL\d+W$', max_length=100), actor=Depends(get_current_user)):
    return service.global_context(str(library_id), work_id, actor)
