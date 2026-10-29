"""Single gated V11 endpoint for native search and issued source operations."""
from contextlib import contextmanager
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Response
from pydantic import BaseModel,ConfigDict,Field
from search.smart_preview import require_preview,preview_allowed,VERSION,PreparedRuntime,RELEASE_DECISION
from search.preview_service import PreviewService


def configured_store():
    """Explicit operator configuration, default none; no database IO here."""
    import os
    from search.preview_state import MemoryStateStore,MongoStateStore
    backend=os.getenv('LUMINAR_SMART_SEARCH_STATE','')
    if backend=='memory' and os.getenv('LUMINAR_DEPLOYMENT_MODE') in ('development','test'):return MemoryStateStore()
    if backend=='mongo' and os.getenv('LUMINAR_SMART_SEARCH_PREVIEW')=='1':
        def collection():
            from backend.database.mongodb import db
            return db.search_preview_v11
        return MongoStateStore(collection_factory=collection)
    return None


class Filters(BaseModel):
    model_config=ConfigDict(extra='forbid')
    subject:str|None=Field(default=None,max_length=200)
    author:str|None=Field(default=None,max_length=150)
    rating_min:float|None=Field(default=None,ge=0,le=5)
    rating_max:float|None=Field(default=None,ge=0,le=5)
    year_min:int|None=Field(default=None,ge=1000,le=2100)
    year_max:int|None=Field(default=None,ge=1000,le=2100)
    format:Literal['ONLINE','PHYSICAL','BOTH']|None=None
    availability:Literal['AVAILABLE_NOW','REQUESTABLE']|None=None
    language:str|None=Field(default=None,max_length=60)
    sort:Literal['RELEVANCE','RATING','NEWEST','TITLE']|None=None


class PreviewRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    query:str=Field(max_length=500)
    mode:Literal['SMART','EXACT','TITLE_AUTHOR','GENRE_SUBJECT']='SMART'
    library_id:UUID|None=None
    staff:bool=False
    state_id:UUID|None=None
    version:int|None=Field(default=None,ge=1)
    operation_id:UUID|None=None
    value:str|None=Field(default=None,max_length=100)
    filters:Filters|None=None
    offset:int=Field(default=0,ge=0,le=4999)
    limit:int=Field(default=10,ge=1,le=50)


def install(app,engine,*,actor_dependency=None,authorize=None,facets=None,execute=None,store=None):
    if actor_dependency is None:
        from backend.dependencies import get_current_user
        actor_dependency=get_current_user
    if authorize is None:
        from search.interaction_api import authorized
        authorize=authorized
    if facets is None:
        def facets(actor,lid,staff):
            from search.query_execution import global_facets,tenant_facets
            return tenant_facets(lid,actor,staff) if lid else global_facets(engine)
    if execute is None:
        def execute(plan,actor,lid,staff,offset,limit):
            from search.query_execution import GlobalQuerySearch,tenant_search
            runtime=PreparedRuntime(plan,actor,lid,staff)
            options=dict(mode=plan.mode,offset=offset,limit=limit,kg_enabled=False,personalized=False,runtime=runtime)
            response=tenant_search(app.state.tenant_intelligence,lid,actor,plan.raw_query,staff=staff,**options) if lid else GlobalQuerySearch(engine).search(plan.raw_query,actor,**options)
            return runtime.finish(response)
    # A deployment must explicitly install its state store; the default feature
    # cannot write production Mongo just because an environment flag was toggled.
    service=PreviewService(store) if store is not None else None
    app.state.smart_preview_service=service
    router=APIRouter(prefix='/query',tags=['Disabled Smart Search preview'])
    @router.get('/features')
    def features(response:Response,actor=Depends(actor_dependency)):
        response.headers['Cache-Control']='private, no-store'
        return dict(smart_preview=preview_allowed(actor) and service is not None,version=VERSION,max_query_length=500,
                    default='C4',advanced_qualification='NOT_QUALIFIED',release_decision=RELEASE_DECISION)
    @router.post('/preview')
    def preview(body:PreviewRequest,response:Response,actor=Depends(actor_dependency)):
        response.headers['Cache-Control']='private, no-store'
        require_preview(actor)
        if service is None:raise HTTPException(503,'Search preview state storage has not been configured.')
        lid=str(body.library_id) if body.library_id else None
        if body.staff and not lid:raise HTTPException(422,'Choose a library workspace.')
        if not lid and body.offset+body.limit>50:raise HTTPException(422,'The global ranked window is limited to 50 results.')
        if lid and body.offset+body.limit>5000:raise HTTPException(422,'The library candidate window is limited to 5000 records.')
        # All authorization/facet IO precedes state access. Normalize UUID to
        # string only after Pydantic validation; interpreter never chooses scope.
        body=body.model_copy(update={'library_id':lid})
        try:
            with authorize(actor,lid,body.staff):
                f=facets(actor,lid,body.staff)
                plan,row,old=service.prepare(body,actor,[r['subject'] for r in f['results']],f['capabilities'])
            result=execute(plan,actor,lid,body.staff,body.offset,body.limit)
            with authorize(actor,lid,body.staff):pass
            service.commit(row,old)
            return service.response(row,result)
        except ValueError as error:raise HTTPException(422,str(error)) from error
        except (TimeoutError,OSError) as error:raise HTTPException(503,'Search is temporarily unavailable. Retry the accepted query.') from error
    app.include_router(router)
