"""Real Mongo lifecycle integrity; no authoritative catalogue mutations."""
from copy import deepcopy
from collections.abc import Mapping
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
import json,os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock
import pytest
from search.query_execution import tenant_search
from search.session_store import collection
from search.session_store import resolve as resolve_plan
from search.query_confidence import executable
from fastapi import HTTPException
from test_query_v2a import query_library
from test_query_v2c_b import interaction_client,ACTOR


def cache_snapshot(value):
    """Copy cache contents, including immutable vocabulary mapping proxies."""
    if isinstance(value,Mapping):return {k:cache_snapshot(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return tuple(cache_snapshot(v) for v in value)
    if hasattr(value,'__dict__'):return (type(value).__name__,cache_snapshot(vars(value)))
    return deepcopy(value)


def setup_choice(query_library,database,query='include Romance but exclude Romance'):
    lid,_,_,worker,_,_=query_library;sid=str(uuid4())
    tenant_search(worker,lid,ACTOR,'books about neural networks',session_id=sid)
    accepted=deepcopy(collection().find_one({'_id':sid}))
    result=tenant_search(worker,lid,ACTOR,query,session_id=sid)
    public=result['interpretation']['clarification'];pending=collection().find_one({'_id':'clarification:'+public['clarification_id']})
    assert collection().find_one({'_id':sid})==accepted
    body={'clarification_id':public['clarification_id'],'choice_id':public['candidate_choices'][0]['choice_id'],'query':query,'session_id':sid,'library_id':lid}
    return lid,sid,accepted,pending,body,interaction_client(database,worker)


def test_forgery_then_valid_preserves_full_mongo_state(query_library,database):
    from search import personalization,query_suggestions
    lid,sid,before,pending,body,client=setup_choice(query_library,database)
    side_before={'memberships':list(database.institution_memberships.find({})),
                 'reading_list':list(database.reading_list.find({}))}
    caches_before=cache_snapshot((personalization._cache,query_suggestions._projections,query_suggestions._issued))
    result=client.post('/query/resolve',json={**body,'choice_id':str(uuid4())})
    after=collection().find_one({'_id':sid});pending_after=collection().find_one({'_id':pending['_id']})
    report={'database':database.name,'http_status':result.status_code,'before_accepted':before,'after_accepted':after,
            'before_pending':pending,'after_pending':pending_after,'accepted_unchanged':after==before,'pending_unchanged':pending_after==pending,
            'membership_unchanged':list(database.institution_memberships.find({}))==side_before['memberships'],
            'reading_list_unchanged':list(database.reading_list.find({}))==side_before['reading_list'],
            'personalization_and_suggestion_caches_unchanged':cache_snapshot((personalization._cache,query_suggestions._projections,query_suggestions._issued))==caches_before}
    name='prepatch_reproducer' if os.getenv('V2CB1_PREPATCH')=='1' else 'forged_choice'
    report_dir=Path(os.getenv('LUMINAR_SECURITY_REPORT_DIR',str(Path(__file__).resolve().parents[2]/'reports')))
    (report_dir/f'search_v2c_b1_{name}.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf8')
    assert result.status_code==404 and after==before and pending_after==pending
    assert report['personalization_and_suggestion_caches_unchanged']
    response=client.post('/query/resolve',json=body)
    assert response.status_code==200,response.text
    committed=collection().find_one({'_id':sid})
    assert committed['version']==before['version']+1
    assert committed['current_plan']['subjects']==['Romance'] and not committed['current_plan']['exclude_terms']
    assert client.post('/query/resolve',json=body).status_code==409
    assert collection().find_one({'_id':sid})==committed


@pytest.mark.parametrize('status',[404,409,422])
def test_downstream_status_does_not_invalidate(query_library,database,monkeypatch,status):
    from search.interaction_api import authorized
    lid,sid,before,pending,_,_=setup_choice(query_library,database)
    forbidden=Mock(side_effect=AssertionError('Operation error invalidated Search state'))
    monkeypatch.setattr('search.session_store.invalidate',forbidden)
    with pytest.raises(HTTPException) as error:
        with authorized(ACTOR,lid):raise HTTPException(status,'Expected operation failure')
    assert error.value.status_code==status
    assert collection().find_one({'_id':sid})==before
    assert collection().find_one({'_id':pending['_id']})==pending
    forbidden.assert_not_called()


def test_expiry_and_bad_operand_do_not_mutate_context(query_library,database):
    _,sid,before,pending,body,client=setup_choice(query_library,database,'Neural networks rating above')
    assert client.post('/query/resolve',json={**body,'value':'6'}).status_code==422
    assert collection().find_one({'_id':sid})==before and collection().find_one({'_id':pending['_id']})==pending
    collection().update_one({'_id':pending['_id']},{'$set':{'expires_at':datetime.now(timezone.utc)-timedelta(seconds=1)}})
    expired=collection().find_one({'_id':pending['_id']})
    assert client.post('/query/resolve',json={**body,'value':'3'}).status_code==410
    assert collection().find_one({'_id':sid})==before
    assert collection().find_one({'_id':pending['_id']}) in (expired,None)  # Mongo TTL may remove ONLY the expired pending record.


def test_cross_clarification_and_newer_accepted_version(query_library,database):
    lid,sid,before,a,body,client=setup_choice(query_library,database)
    worker=query_library[3];q='books rated above 4 and below 3'
    b=tenant_search(worker,lid,ACTOR,q,session_id=sid)['interpretation']['clarification']
    bdoc=collection().find_one({'_id':'clarification:'+b['clarification_id']})
    wrong={**body,'query':q,'clarification_id':b['clarification_id']}
    assert client.post('/query/resolve',json=wrong).status_code==404
    assert collection().find_one({'_id':sid})==before and collection().find_one({'_id':a['_id']})==a and collection().find_one({'_id':bdoc['_id']})==bdoc
    assert client.post('/query/resolve',json=body).status_code==200
    latest=collection().find_one({'_id':sid})
    stale={**wrong,'choice_id':b['candidate_choices'][0]['choice_id']}
    assert client.post('/query/resolve',json=stale).status_code==409
    assert collection().find_one({'_id':sid})==latest and collection().find_one({'_id':bdoc['_id']})==bdoc


def test_foreign_user_sid_scope_and_workspace_cannot_damage_either_context(query_library,database,client,library):
    lid,sid,before,pending,body,api=setup_choice(query_library,database)
    worker=query_library[3]
    assert client.post(f'/libraries/{lid}/join',headers={'x-test-user':'4'},json={'access_code':'Isolated fixture access code'}).status_code==200
    other_actor={'sub':'4','sid':'other-user-login'};other_sid=str(uuid4())
    tenant_search(worker,lid,other_actor,'books about neural networks',session_id=other_sid)
    other_before=collection().find_one({'_id':other_sid})
    other_library=library(private=False)
    assert client.post(f'/libraries/{other_library}/join',headers={'x-test-user':'2'},json={}).status_code==200
    other_library_sid=str(uuid4());tenant_search(worker,other_library,ACTOR,'books about physics',session_id=other_library_sid)
    other_library_before=collection().find_one({'_id':other_library_sid})
    for payload,headers in [(body,{'x-user':'4','x-sid':'other-user-login'}),(body,{'x-sid':'another-login'}),
                            ({**body,'library_id':other_library},{}),({k:v for k,v in body.items() if k!='library_id'}, {})]:
        response=api.post('/query/resolve',json=payload,headers=headers)
        assert response.status_code==404,response.text
        assert collection().find_one({'_id':sid})==before and collection().find_one({'_id':other_sid})==other_before
        assert collection().find_one({'_id':other_library_sid})==other_library_before and collection().find_one({'_id':pending['_id']})==pending
    # A public clarification cannot be paired with the private scope either.
    q='books rated above 4 and below 3'
    public=tenant_search(worker,other_library,ACTOR,q,session_id=other_library_sid)['interpretation']['clarification']
    assert api.post('/query/resolve',json={**body,'clarification_id':public['clarification_id'],'choice_id':public['candidate_choices'][0]['choice_id'],'query':q,'session_id':other_library_sid}).status_code==404
    assert collection().find_one({'_id':other_library_sid})==other_library_before
    # A role change grants a different workspace, never ownership of old choices.
    database.institution_memberships.update_one({'library_id':lid,'user_id':2},{'$set':{'role':'LIBRARIAN'}})
    assert api.post('/query/resolve',json={**body,'staff':True}).status_code==404
    assert collection().find_one({'_id':sid})==before and collection().find_one({'_id':pending['_id']})==pending


def pause_before_pipeline(monkeypatch):
    import search.query_execution as execution
    original=execution.tenant_search;entered=Event();release=Event()
    def paused(*args,**kwargs):
        if kwargs.get('resolution'):
            entered.set();assert release.wait(10),'Test interleaving did not release the resolution'
        return original(*args,**kwargs)
    monkeypatch.setattr(execution,'tenant_search',paused)
    return entered,release


@pytest.mark.parametrize('second',['forged','duplicate','expired','revoked','newer'])
def test_interleaved_resolution_never_rolls_back_or_double_commits(query_library,database,monkeypatch,second):
    lid,sid,before,pending,body,api=setup_choice(query_library,database)
    global_sid=str(uuid4());other_sid=str(uuid4())
    resolve_plan('books about stars',ACTOR,[],session_id=global_sid)
    resolve_plan('books about planets',ACTOR,[],session_id=other_sid,library_id=str(uuid4()))
    independent={key:collection().find_one({'_id':key}) for key in [global_sid,other_sid]}
    entered,release=pause_before_pipeline(monkeypatch)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future=executor.submit(api.post,'/query/resolve',json=body)
        assert entered.wait(10)
        claimed=collection().find_one({'_id':pending['_id']});assert claimed.get('resolution_claim') and not claimed.get('used')
        try:
            if second=='forged':
                assert api.post('/query/resolve',json={**body,'choice_id':str(uuid4())}).status_code==404
                assert collection().find_one({'_id':pending['_id']})==claimed and collection().find_one({'_id':sid})==before
            elif second=='duplicate':
                assert api.post('/query/resolve',json=body).status_code==409
                assert collection().find_one({'_id':pending['_id']})==claimed and collection().find_one({'_id':sid})==before
            elif second=='expired':collection().update_one({'_id':pending['_id']},{'$set':{'expires_at':datetime.now(timezone.utc)-timedelta(seconds=1)}})
            elif second=='revoked':database.institution_memberships.update_one({'library_id':lid,'user_id':2},{'$set':{'status':'REMOVED'}})
            else:
                tenant_search(query_library[3],lid,ACTOR,'rating above 3',session_id=sid)
                newer=collection().find_one({'_id':sid})
        finally:release.set()
        response=future.result(timeout=15)
    after=collection().find_one({'_id':sid});p=collection().find_one({'_id':pending['_id']})
    if second in ('forged','duplicate'):
        assert response.status_code==200,response.text
        assert after['version']==before['version']+1 and after['current_plan']['subjects']==['Romance']
        assert p.get('used') and not p.get('resolution_claim')
    elif second=='expired':
        assert response.status_code==410 and after==before and not (p or {}).get('used')
        assert api.post('/query/resolve',json=body).status_code in (404,410)
    elif second=='revoked':assert response.status_code==404 and after is None and p is None
    else:assert response.status_code==409 and after==newer and not p.get('used') and not p.get('resolution_claim')
    assert all(collection().find_one({'_id':key})==value for key,value in independent.items())


def test_failure_before_context_commit_releases_pending_without_consuming(query_library,database,monkeypatch):
    _,sid,before,pending,body,api=setup_choice(query_library,database)
    from search.session_store import resolve as original
    def busy(*args,**kwargs):raise HTTPException(503,'A transient Search error')
    with monkeypatch.context() as patch:
        patch.setattr('search.query_execution.resolve_session',busy)
        assert api.post('/query/resolve',json=body).status_code==503
    assert collection().find_one({'_id':sid})==before and collection().find_one({'_id':pending['_id']})==pending
    assert api.post('/query/resolve',json=body).status_code==200


def test_error_after_commit_does_not_make_pending_reusable(query_library,database,monkeypatch):
    _,sid,before,pending,body,api=setup_choice(query_library,database)
    from search.session_store import resolve as original
    def committed_then_unavailable(*args,**kwargs):
        original(*args,**kwargs)
        raise HTTPException(503,'Ranking temporarily unavailable')
    monkeypatch.setattr('search.query_execution.resolve_session',committed_then_unavailable)
    assert api.post('/query/resolve',json=body).status_code==503
    after=collection().find_one({'_id':sid});assert after['version']==before['version']+1
    assert collection().find_one({'_id':pending['_id']}).get('used')
    assert api.post('/query/resolve',json=body).status_code==409
    assert collection().find_one({'_id':sid})==after


def test_forged_chip_addresses_cannot_inject_or_change_ownership(query_library,database):
    from search.query_session import item_edit_key
    lid=query_library[0];worker=query_library[3];sid=str(uuid4())
    query='include Deep learning but exclude Romance rated above 3'
    tenant_search(worker,lid,ACTOR,query,session_id=sid)
    before=collection().find_one({'_id':sid})
    keys=['year_min','subject=Private Orchid',item_edit_key('subject','Another tenant subject'),
          'library_id=foreign','user_id=4','generation=foreign','personalization_owner=4','current_plan',
          'subject@arbitrary','exclude@arbitrary']
    tenant_search(worker,lid,ACTOR,query,session_id=sid,omit=keys)
    after=collection().find_one({'_id':sid})
    assert after['current_plan']==before['current_plan']
    for key in ('user_id','login_session','scope','library_id','workspace'):assert after[key]==before[key]
    # Ordinary unknown remove addresses are ignored; there is no plan patch API.
    api=interaction_client(database,worker)
    assert api.post('/query/resolve',json={'clarification_id':str(uuid4()),'choice_id':str(uuid4()),'query':query,
        'session_id':sid,'library_id':lid,'plan':{'subjects':['Another tenant subject']}}).status_code==422
    assert collection().find_one({'_id':sid})==after


def test_each_displayed_template_is_executable_and_enforced(query_library,database):
    from search.query_suggestions import suggest
    from search.query_plan import parse_query
    from search.query_confidence import validate,executable
    from search.query_suggestions import projection
    lid=query_library[0];worker=query_library[3]
    facets=projection(worker,ACTOR,lid)[0]['facets']
    seen=[]
    for prefix in ['rated','available','physical','published','exclude']:
        result=suggest(worker,ACTOR,prefix,library_id=lid)
        for item in result['suggestions']:
            if item['type']!='TEMPLATE':continue
            plan=validate(parse_query(item['insert_text'],facets),facets['capabilities'])
            assert executable(plan),item
            seen.append(item['insert_text'])
            if item['insert_text'].startswith('rated'):assert plan.rating_min==4
            elif item['insert_text']=='available now':assert plan.availability=='AVAILABLE_NOW'
            elif item['insert_text']=='available online':assert plan.formats==['ONLINE']
            elif item['insert_text']=='physical only':assert plan.exclusive_formats==['PHYSICAL']
            elif item['insert_text'].startswith('published'):assert plan.year_min==2020 and plan.year_min_exclusive
    assert set(seen)=={'rated above 4','rated at least 4','available online','available now','physical only','published after 2020'}


def test_late_expiry_before_first_context_insert_cannot_evict_another_context(database):
    for _ in range(32):resolve_plan('books about stars',ACTOR,[],session_id=str(uuid4()))
    before=list(collection().find({'current_plan':{'$exists':True}}).sort('_id'))
    class LateExpiry:
        receipt={'clarification_id':'isolated-late-expiry','claim':'test'}
        committed=False
        calls=0
        def check(self):
            self.calls+=1
            if self.calls==2:raise HTTPException(410,'Choice expired before insertion')
            return datetime.now(timezone.utc)+timedelta(seconds=30)
    guard=LateExpiry()
    with pytest.raises(HTTPException) as error:
        resolve_plan('books about planets',ACTOR,[],session_id=str(uuid4()),commit_guard=guard)
    assert error.value.status_code==410 and not guard.committed
    assert list(collection().find({'current_plan':{'$exists':True}}).sort('_id'))==before
