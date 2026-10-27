"""Observed Mongo session safety and fresh authority for V2C-B interactions."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock
import pytest
from fastapi import FastAPI,Request,HTTPException
from fastapi.testclient import TestClient
from backend.dependencies import get_current_user
from search.query_plan import parse_query
from search.query_confidence import executable
from search.query_interaction import offer,load_choice,transformer
from search.session_store import collection,resolve,clear
from search.query_execution import GlobalQuerySearch,tenant_search
from search.interaction_api import install
from search import query_suggestions as suggestions
from test_query_v2a import query_library

FACETS=['Fiction','Romance','Mystery','Detective Fiction','Neural Networks']
CAPS={'rating':True,'year':True,'language':True,'availability':True,'formats':['ONLINE','PHYSICAL','BOTH']}
ACTOR={'sub':'2','sid':'v2cb-login'}


def pending(query,*,caps=CAPS,session=None,sid=None,facets=FACETS):
    plan,_=resolve(query,ACTOR,facets,session_id=sid,capabilities=caps)
    public=offer(plan,session,ACTOR,query=query,mode='SMART',filters={},omit=[],session_id=sid,capabilities=caps)
    assert public
    return public


@pytest.mark.parametrize('query,index,value,assertion',[
 ('fiction 4',0,None,lambda p:p.subjects==['Fiction'] and p.rating_min==4 and not p.rating_min_exclusive and not p.semantic_text),
 ('fiction 4',1,None,lambda p:p.exact_text=='fiction 4' and p.mode=='EXACT'),
 ('fiction rating above',0,'3',lambda p:p.subjects==['Fiction'] and p.rating_min==3 and p.rating_min_exclusive and not p.semantic_text),
 ('books rated above 4 and below 3',0,None,lambda p:p.rating_min==4 and p.rating_min_exclusive and p.rating_max is None),
 ('books rated above 4 and below 3',1,None,lambda p:p.rating_max==3 and p.rating_max_exclusive and p.rating_min is None),
 ('books rated above 4 and below 3',2,None,lambda p:p.rating_max is None and p.rating_min is None),
 ('published after 2020 and before 2000',0,None,lambda p:p.year_min==2020 and p.year_min_exclusive and p.year_max is None),
 ('online only and physical only',0,None,lambda p:p.formats==['ONLINE'] and p.exclusive_formats==['ONLINE']),
 ('online only and physical only',1,None,lambda p:p.formats==['PHYSICAL'] and p.exclusive_formats==['PHYSICAL']),
 ('online only and physical only',2,None,lambda p:p.formats==['BOTH'] and not p.exclusive_formats),
 ('include Romance but exclude Romance',0,None,lambda p:p.subjects==['Romance'] and not p.exclude_terms),
 ('include Romance but exclude Romance',1,None,lambda p:not p.subjects and p.exclude_terms==['Romance']),
 ('include Romance but exclude Romance',2,None,lambda p:not p.subjects and not p.exclude_terms),
 ('mystery books under 250 pages',0,None,lambda p:p.subjects==['Mystery'] and not p.semantic_text),
])
def test_choices_reuse_parser_and_validate_before_commit(database,query,index,value,assertion):
    sid=str(uuid4());public=pending(query,sid=sid)
    assert not collection().find_one({'_id':sid})
    row,choice,operand=load_choice(ACTOR,public['clarification_id'],public['candidate_choices'][index]['choice_id'],mode='SMART',query=query,session_id=sid,value=value)
    p,_=resolve(query,ACTOR,FACETS,session_id=sid,capabilities=CAPS,transform=transformer(row,choice,operand),expected_version=0)
    assert executable(p) and assertion(p)
    replay,_=resolve(query,ACTOR,FACETS,session_id=sid,capabilities=CAPS)
    assert assertion(replay)


@pytest.mark.parametrize('value',['nan','inf','-1','5.1','three','3 online only'])
def test_invalid_rating_never_commits(database,value):
    sid=str(uuid4());public=pending('fiction rating above',sid=sid)
    with pytest.raises(HTTPException):
        load_choice(ACTOR,public['clarification_id'],public['candidate_choices'][0]['choice_id'],mode='SMART',query='fiction rating above',session_id=sid,value=value)
    assert not collection().find_one({'_id':sid})


def test_expired_forged_sid_mode_scope_and_clear(database):
    sid=str(uuid4());query='fiction 4';public=pending(query,sid=sid)
    cid=public['clarification_id'];choice=public['candidate_choices'][0]['choice_id']
    common={'mode':'SMART','query':query,'session_id':sid}
    with pytest.raises(HTTPException):load_choice(ACTOR,str(uuid4()),choice,**common)
    for actor,opts,chosen in [({'sub':'3','sid':ACTOR['sid']},{},choice),({'sub':'2','sid':'foreign'},{},choice),(ACTOR,{'mode':'EXACT'},choice),(ACTOR,{'library_id':str(uuid4())},choice),(ACTOR,{'staff':True},choice),(ACTOR,{'query':'other'},choice),(ACTOR,{},str(uuid4()))]:
        with pytest.raises(HTTPException):load_choice(actor,cid,chosen,**{**common,**opts})
    collection().update_one({'_id':'clarification:'+cid},{'$set':{'expires_at':datetime.now(timezone.utc)-timedelta(seconds=1)}})
    with pytest.raises(HTTPException) as error:load_choice(ACTOR,cid,choice,**common)
    assert error.value.status_code==410
    clear(sid,ACTOR);assert not collection().find_one({'_id':'clarification:'+cid})


def test_stale_choices_preserve_latest_context_and_dismissed_query(database):
    sid=str(uuid4());p,s=resolve('books about wizards',ACTOR,FACETS,session_id=sid)
    prior=deepcopy(collection().find_one({'_id':sid}))
    public=pending('fiction 4',session=s,sid=sid)
    assert collection().find_one({'_id':sid})==prior
    row,choice,value=load_choice(ACTOR,public['clarification_id'],public['candidate_choices'][0]['choice_id'],mode='SMART',query='fiction 4',session_id=sid)
    resolve('online only',ACTOR,FACETS,session_id=sid)
    latest=deepcopy(collection().find_one({'_id':sid}))
    with pytest.raises(HTTPException) as error:
        resolve('fiction 4',ACTOR,FACETS,session_id=sid,transform=transformer(row,choice,value),expected_version=row['base_version'])
    assert error.value.status_code==409 and collection().find_one({'_id':sid})==latest


@pytest.mark.parametrize('query',['Python 3','C++','C#','Catch-22','1984','"detectve fiction"','Dune 2','The Three-Body Problem','books by Rare Valid Name'])
def test_protected_queries_do_not_offer_corrections(database,query):
    p=parse_query(query,FACETS)
    from search.query_interaction import choices_for
    _,choices=choices_for(p,CAPS)
    assert not any(c['operation'].startswith('correction_') for c in choices)


@pytest.mark.parametrize('query',['detectve fiction','neurel networks'])
@pytest.mark.parametrize('keep',[False,True])
def test_correction_apply_keep_preserves_strict_constraints(database,query,keep):
    query=query+' rated above 3 available online';sid=str(uuid4())
    plan,session=resolve(query,ACTOR,FACETS,session_id=sid)
    # Stored clean plans omit correction decorations; issue from actual plan.
    public=offer(plan,session,ACTOR,query=query,mode='SMART',filters={},omit=[],session_id=sid,capabilities=CAPS)
    assert public and plan.corrections
    row,choice,value=load_choice(ACTOR,public['clarification_id'],public['candidate_choices'][int(keep)]['choice_id'],mode='SMART',query=query,session_id=sid)
    p,_=resolve(query,ACTOR,FACETS,session_id=sid,transform=transformer(row,choice,value),expected_version=session['version'])
    assert p.rating_min==3 and p.rating_min_exclusive and p.formats==['ONLINE']
    assert (bool(p.semantic_text) and not p.subjects) if keep else bool(p.subjects)


def interaction_client(database,worker=None):
    app=FastAPI();engine=SimpleNamespace(books_collection=database.books,lexical_store=None)
    app.state.tenant_intelligence=worker;install(app,engine)
    def actor(request:Request):return {'sub':request.headers.get('x-user','2'),'sid':request.headers.get('x-sid','v2cb-login')}
    app.dependency_overrides[get_current_user]=actor
    return TestClient(app)


@pytest.mark.parametrize('staff',[False,True])
def test_authorized_prefixes_and_forged_suggestion(query_library,database,staff):
    lid,row,_,worker,_,_=query_library;client=interaction_client(database,worker)
    user='1' if staff else '2';headers={'x-user':user}
    suggestions._projections.clear();suggestions._issued.clear()
    response=client.get('/query/suggestions',params={'q':'neur','library_id':lid,'staff':staff},headers=headers)
    assert response.status_code==200,response.text
    data=response.json();assert any(i['display']=='Neural networks' and i['type']=='SUBJECT' for i in data['suggestions'])
    assert any(i['display']=='Neural networks primer' and i['type']=='TITLE' for i in data['suggestions'])
    assert all(not any(k in i for k in ('user_id','login_session','library_book_id','score')) for i in data['suggestions'])
    item=data['suggestions'][0]
    body={'suggestion_id':item['id'],'q':'neur','mode':'SMART','library_id':lid,'staff':staff}
    assert client.post('/query/suggestions/select',json=body,headers=headers).status_code==200
    assert client.post('/query/suggestions/select',json={**body,'suggestion_id':'forged'},headers=headers).status_code==409
    assert client.post('/query/suggestions/select',json=body,headers={**headers,'x-sid':'other-login'}).status_code==409
    assert not collection().find_one({'current_plan':{'$exists':True}})


@pytest.mark.parametrize('user',['3','9'])
def test_private_denial_before_any_suggestions_cache(query_library,database,monkeypatch,user):
    lid,_,_,worker,_,_=query_library;client=interaction_client(database,worker)
    forbidden=Mock(side_effect=AssertionError('Unauthorized projection lookup'))
    monkeypatch.setattr(suggestions,'projection',forbidden)
    for method,path,kwargs in [('get','/query/suggestions',{'params':{'q':'neural','library_id':lid}}),('post','/query/resolve',{'json':{'clarification_id':str(uuid4()),'choice_id':str(uuid4()),'query':'neural 4','library_id':lid}})]:
        result=getattr(client,method)(path,headers={'x-user':user},**kwargs)
        assert result.status_code==404 and 'Neural' not in result.text
    forbidden.assert_not_called()


def test_revocation_beats_cached_suggestions_and_choices(query_library,database,monkeypatch):
    lid,_,_,worker,_,_=query_library;client=interaction_client(database,worker)
    assert client.get('/query/suggestions',params={'q':'neur','library_id':lid}).status_code==200
    sid=str(uuid4());result=tenant_search(worker,lid,ACTOR,'include Romance but exclude Romance',session_id=sid)
    pending=result['interpretation']['clarification'];assert pending
    database.institution_memberships.update_one({'library_id':lid,'user_id':2},{'$set':{'status':'REVOKED'}})
    forbidden=Mock(side_effect=AssertionError('Revoked cache read'));monkeypatch.setattr(suggestions,'projection',forbidden)
    assert client.get('/query/suggestions',params={'q':'neur','library_id':lid}).status_code==404
    assert client.post('/query/resolve',json={'clarification_id':pending['clarification_id'],'choice_id':pending['candidate_choices'][0]['choice_id'],'query':'include Romance but exclude Romance','session_id':sid,'library_id':lid}).status_code==404
    assert not collection().find_one({'search_session_id':sid})
    forbidden.assert_not_called()


def test_resolve_endpoint_single_use_and_no_plan_patch(query_library,database):
    lid,_,_,worker,_,_=query_library;client=interaction_client(database,worker);sid=str(uuid4());query='include Romance but exclude Romance'
    result=tenant_search(worker,lid,ACTOR,query,session_id=sid);public=result['interpretation']['clarification']
    body={'clarification_id':public['clarification_id'],'choice_id':public['candidate_choices'][0]['choice_id'],'query':query,'session_id':sid,'library_id':lid}
    assert client.post('/query/resolve',json={**body,'plan':{'subjects':['Global secret']}}).status_code==422
    assert client.post('/query/resolve',json={**body,'choice_id':str(uuid4())}).status_code==404
    assert not collection().find_one({'_id':sid})
    response=client.post('/query/resolve',json=body)
    assert response.status_code==200,response.text
    assert response.json()['choice_applied'] and all(r['library_id']==lid for r in response.json()['results'])
    prior=deepcopy(collection().find_one({'_id':sid}))
    assert client.post('/query/resolve',json=body).status_code==409
    assert collection().find_one({'_id':sid})==prior


def test_global_capabilities_suppress_false_year_options(database):
    from search.query_interaction import choices_for
    plan=parse_query('published after 2020 and before 2000',FACETS)
    _,choices=choices_for(plan,{**CAPS,'year':False})
    assert [c['operation'] for c in choices]==['remove']
    p=parse_query('books about Asimov',FACETS)
    assert not choices_for(p,CAPS)[1]


def test_literal_choice_preserves_explicit_controls(database):
    query='fiction 4';p=parse_query(query,FACETS,filters={'rating_min':3,'format':'ONLINE','sort':'RATING'})
    public=offer(p,None,ACTOR,query=query,mode='SMART',filters={'rating_min':3,'format':'ONLINE','sort':'RATING'},omit=[],session_id=None,capabilities=CAPS)
    row,choice,value=load_choice(ACTOR,public['clarification_id'],public['candidate_choices'][-1]['choice_id'],mode='SMART',query=query,session_id=None)
    result,_=resolve(query,ACTOR,FACETS,filters=row['filters'],transform=transformer(row,choice,value),capabilities=CAPS)
    assert result.exact_text==query and result.rating_min==3 and result.formats==['ONLINE'] and result.sort=='RATING'


def test_page_choice_does_not_silently_drop_other_unsupported_requirements(database):
    query='mystery books under 250 pages fourth edition';public=pending(query)
    row,choice,value=load_choice(ACTOR,public['clarification_id'],public['candidate_choices'][0]['choice_id'],mode='SMART',query=query,session_id=None)
    with pytest.raises(HTTPException):resolve(query,ACTOR,FACETS,transform=transformer(row,choice,value),capabilities=CAPS)


def test_removed_subject_rechecked_even_when_projection_warm(query_library,database):
    lid,row,_,worker,_,_=query_library;client=interaction_client(database,worker)
    first=client.get('/query/suggestions',params={'q':'neur','library_id':lid}).json()
    assert any(i['type']=='SUBJECT' for i in first['suggestions'])
    database.institution_library_books.update_one({'library_book_id':row['library_book_id']},{'$set':{'status':'WITHDRAWN'}})
    second=client.get('/query/suggestions',params={'q':'neur','library_id':lid}).json()
    assert second['suggestions']==[]


def test_expired_jwt_and_legacy_sid_cannot_reach_suggestions(database,monkeypatch):
    from jose import jwt
    from backend.utils.jwt_utils import JWT_SECRET_KEY,JWT_ALGORITHM
    client=interaction_client(database);client.app.dependency_overrides.clear()
    forbidden=Mock(side_effect=AssertionError('Invalid token reached projection'));monkeypatch.setattr(suggestions,'projection',forbidden)
    payload={'sub':'2','exp':datetime.now(timezone.utc)-timedelta(seconds=2),'sid':'expired-login'}
    expired=jwt.encode(payload,JWT_SECRET_KEY,algorithm=JWT_ALGORITHM)
    assert client.get('/query/suggestions',params={'q':'neur'},headers={'Authorization':'Bearer '+expired}).status_code==401
    legacy=jwt.encode({'sub':'2','exp':datetime.now(timezone.utc)+timedelta(minutes=1)},JWT_SECRET_KEY,algorithm=JWT_ALGORITHM)
    assert client.get('/query/suggestions',params={'q':'neur'},headers={'Authorization':'Bearer '+legacy}).status_code==401
    forbidden.assert_not_called()


def test_workspace_binding_survives_membership_role_change(query_library,database):
    lid,_,_,worker,_,_=query_library;actor=ACTOR;sid=str(uuid4());query='include Romance but exclude Romance'
    response=tenant_search(worker,lid,actor,query,session_id=sid,staff=False);public=response['interpretation']['clarification']
    database.institution_memberships.update_one({'library_id':lid,'user_id':2},{'$set':{'role':'LIBRARIAN'}})
    client=interaction_client(database,worker)
    result=client.post('/query/resolve',json={'clarification_id':public['clarification_id'],'choice_id':public['candidate_choices'][0]['choice_id'],'query':query,'session_id':sid,'library_id':lid,'staff':True})
    assert result.status_code==404 and not collection().find_one({'_id':sid})


@pytest.mark.parametrize('with_session',[False,True])
def test_one_chip_removal_keeps_other_subjects_and_exclusions(database,with_session):
    from search.query_session import item_edit_key
    from search.query_execution import interpretation
    facets=FACETS+['Biography'];sid=str(uuid4()) if with_session else None
    query='include Fiction and Mystery but exclude Romance and Biography rated above 3'
    plan,_=resolve(query,ACTOR,facets,session_id=sid,filters={'sort':'RATING'})
    chips=interpretation(plan)['chips'];key=next(c['remove_key'] for c in chips if c['label']=='Genre / Subject: Fiction')
    assert key==item_edit_key('subject','Fiction')
    plan,_=resolve(query,ACTOR,facets,session_id=sid,filters={'sort':'RATING'},omit=[key,item_edit_key('exclude','Romance')])
    assert plan.subjects==['Mystery'] and plan.exclude_terms==['Biography'] and plan.exclude_subjects==['Biography']
    assert plan.rating_min==3 and plan.rating_min_exclusive and plan.sort=='RATING' and executable(plan)
