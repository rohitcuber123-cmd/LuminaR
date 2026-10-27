"""Only tenant routes are added; existing global handlers/ranking are untouched."""
from uuid import UUID
from fastapi import APIRouter,Depends,Query,Response,HTTPException
from backend.dependencies import get_current_user
from search.library_intelligence import TenantIntelligence

def install(app,engine):
    model=getattr(engine,'embedding_model',None)
    module=model[0] if model is not None else None
    revision=getattr(getattr(module,'auto_model',None),'config',None)
    version='all-MiniLM-L6-v2:'+str(getattr(revision,'_commit_hash',None) or 'local-accepted-v1')+':normalized384-v1'
    def encode(texts):
        if model is None:raise HTTPException(503,'Resident catalogue embedding model is unavailable.')
        return model.encode(texts,normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)
    reranker=getattr(engine,'reranker',None)
    service=TenantIntelligence(encode,(lambda pairs:reranker.predict(pairs,show_progress_bar=False)) if reranker is not None else None,version)
    app.state.tenant_intelligence=service
    router=APIRouter(prefix='/libraries/{library_id}/catalogue',tags=['Tenant semantic catalogue'])
    @router.get('/search')
    def search(library_id:UUID,response:Response,search:str=Query('',max_length=150),staff:bool=False,
               offset:int=Query(0,ge=0,le=100000),limit:int=Query(20,ge=1,le=100),subject:str=Query('',max_length=200),author:str=Query('',max_length=150),circulation_status:str=Query('',max_length=40),sort:str=Query('RELEVANCE',max_length=30),
               mode:str=Query('SMART',pattern='^(SMART|GENRE_SUBJECT|TITLE_AUTHOR|EXACT)$'),rating_min:float|None=Query(None,ge=0,le=5),rating_max:float|None=Query(None,ge=0,le=5),year_min:int|None=Query(None,ge=1000,le=2100),year_max:int|None=Query(None,ge=1000,le=2100),format:str=Query('',pattern='^(|ONLINE|PHYSICAL|BOTH)$'),availability:str=Query('',pattern='^(|AVAILABLE_NOW|REQUESTABLE)$'),language:str=Query('',max_length=60),omit:str=Query('',max_length=1000),session_id:str|None=Query(None,max_length=36),personalized:bool=False,actor=Depends(get_current_user)):
        response.headers['Cache-Control']='private, no-store'
        from search.query_execution import tenant_search
        filters={**{key:value for key,value in locals().items() if key in ('subject','author','rating_min','rating_max','year_min','year_max','format','availability','language','circulation_status')},'sort':sort.upper() if sort.upper() in ('RELEVANCE','RATING','NEWEST','TITLE') else 'RELEVANCE'}
        try:return tenant_search(service,str(library_id),actor,search,staff=staff,mode=mode,filters=filters,omit=omit.split(','),offset=offset,limit=limit,session_id=session_id,personalized=personalized)
        except ValueError as error:raise HTTPException(422,str(error)) from error
    app.include_router(router)
    # A degraded lexical-only process can still serve safe local fallbacks.
    # It must not claim semantic builds without the accepted resident models.
    if model is not None and reranker is not None:app.router.add_event_handler('startup',service.start)
    app.router.add_event_handler('shutdown',service.close)
