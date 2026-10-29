"""Authenticated interaction routes; scope authority precedes stored data IO."""
from contextlib import contextmanager,ExitStack
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from backend.dependencies import get_current_user
from backend.services.identity_service import current_identity

Mode=Literal['SMART','GENRE_SUBJECT','TITLE_AUTHOR','EXACT']


@contextmanager
def authorized(actor,library_id=None,staff=False):
    if not current_identity(actor):
        from search.scope_authorization import invalidate_if_access_lost
        invalidate_if_access_lost(actor,library_id,staff=staff)
        raise HTTPException(401,'Active account required.')
    if not actor.get('sid'):raise HTTPException(401,'Sign in again to use search interactions.')
    if staff and not library_id:raise HTTPException(422,'Choose a library workspace.')
    if library_id:
        from backend.services import library_catalogue_experience as catalogue
        with ExitStack() as stack:
            try:
                context=stack.enter_context(catalogue.read_context(library_id,actor,staff=staff))
            except HTTPException as error:
                if error.status_code in (403,404):
                    from search.scope_authorization import invalidate_if_access_lost
                    invalidate_if_access_lost(actor,library_id,staff=staff)
                raise
            # Endpoint errors raised after yield are OUTSIDE the authorization
            # handler. ExitStack still releases the existing catalogue lock.
            yield context
    else:yield


class ChoiceRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    clarification_id:UUID
    choice_id:UUID
    query:str=Field(max_length=150)
    mode:Mode='SMART'
    session_id:UUID|None=None
    library_id:UUID|None=None
    staff:bool=False
    value:str|None=Field(default=None,max_length=100)
    personalized:bool=False


class SuggestionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    suggestion_id:str=Field(max_length=4000)
    q:str=Field(min_length=2,max_length=150)
    mode:Mode='SMART'
    library_id:UUID|None=None
    staff:bool=False


def install(app,engine):
    router=APIRouter(prefix='/query',tags=['Search interactions'])
    from search import query_suggestions as suggestions
    @router.get('/suggestions')
    def suggest(response:Response,q:str=Query('',max_length=150),mode:Mode='SMART',limit:int=Query(8,ge=1,le=8),library_id:UUID|None=None,staff:bool=False,actor=Depends(get_current_user)):
        response.headers['Cache-Control']='private, no-store'
        lid=str(library_id) if library_id else None
        with authorized(actor,lid,staff):
            return suggestions.suggest(engine,actor,q,mode=mode,limit=limit,library_id=lid,staff=staff)

    @router.post('/suggestions/select')
    def select(request:SuggestionRequest,response:Response,actor=Depends(get_current_user)):
        response.headers['Cache-Control']='private, no-store'
        lid=str(request.library_id) if request.library_id else None;q=suggestions.normalize_structured(request.q)
        with authorized(actor,lid,request.staff):
            _,gen,_=suggestions.projection(engine,actor,lid,request.staff)
            item=suggestions.verify(request.suggestion_id,actor,q,request.mode,gen,lid,request.staff)
            fresh=suggestions.suggest(engine,actor,q,mode=request.mode,library_id=lid,staff=request.staff)
            if not any(all(candidate.get(k)==v for k,v in item.items()) for candidate in fresh['suggestions']):
                raise HTTPException(409,'Suggestion is no longer available. Type again to refresh.')
            return {'insert_text':item['insert_text'],'type':item['type']}

    @router.post('/resolve')
    def resolve(request:ChoiceRequest,response:Response,actor=Depends(get_current_user)):
        from search.query_execution import global_facets,GlobalQuerySearch,tenant_search
        from search.query_interaction import load_choice,transformer,reservation
        from search.session_store import resolve as resolve_plan
        response.headers['Cache-Control']='private, no-store'
        lid=str(request.library_id) if request.library_id else None;sid=str(request.session_id) if request.session_id else None
        with authorized(actor,lid,request.staff):
            row,choice,value=load_choice(actor,str(request.clarification_id),str(request.choice_id),mode=request.mode,query=request.query,session_id=sid,library_id=lid,staff=request.staff,value=request.value)
            if lid:
                from backend.services import library_catalogue_experience as catalogue
                facets={**catalogue.subject_rows(lid,limit=2048,staff=request.staff),'capabilities':{'rating':True,'year':True,'language':True,'availability':True,'formats':['ONLINE','PHYSICAL','BOTH']}}
            else:facets=global_facets(engine)
            transform=transformer(row,choice,value)
            options={'mode':row['mode'],'filters':row['filters'],'omit':row['omit'],'session_id':sid}
            edit={'transform':transform,'expected_version':row['base_version']}
            # Operation errors stay outside authorization handling. Preview is
            # read-only and must pass before acquiring a one-use pending claim.
            resolve_plan(row['query'],actor,[r['subject'] for r in facets['results']],**options,library_id=lid,staff=request.staff,capabilities=facets['capabilities'],preview=True,**edit)
        # Release the catalogue read lock before the existing pipeline obtains
        # its own fresh authority/lock. Never nest durable mutation locks.
        with reservation(row) as commit:
            edit['commit_guard']=commit
            if lid:result=tenant_search(app.state.tenant_intelligence,lid,actor,row['query'],staff=request.staff,personalized=request.personalized,resolution=edit,**options)
            else:result=GlobalQuerySearch(engine).search(row['query'],actor,personalized=request.personalized,resolution=edit,**options)
        result['choice_applied']=True
        return result

    @router.delete('/clarifications/{clarification_id}')
    def dismiss(clarification_id:UUID,response:Response,library_id:UUID|None=None,staff:bool=False,actor=Depends(get_current_user)):
        from search.session_store import collection,identity
        lid=str(library_id) if library_id else None
        response.headers['Cache-Control']='private, no-store'
        with authorized(actor,lid,staff):
            collection().delete_one({'_id':'clarification:'+str(clarification_id),**identity(actor,lid,staff)})
            return {'dismissed':True}
    app.include_router(router)
    from search.preview_api import install as install_preview,configured_store
    install_preview(app,engine,store=configured_store())
