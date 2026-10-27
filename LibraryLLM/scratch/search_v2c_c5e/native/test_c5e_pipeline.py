"""Real native search contracts with disposable data and bounded retrieval.

No HNSW/model service: global semantic IDs are the declared fixture engine;
tenant semantic queries use the unchanged NOT_BUILT fallback.
"""
import json,time
from uuid import uuid4
from fastapi.encoders import jsonable_encoder
from fastapi import HTTPException
import pytest
from test_native_contract import fixture,SCOPES,scope_actor,collection,save
from search.query_execution import GlobalQuerySearch,tenant_search

def run(fixture,scope,q,**options):
    lid,staff=fixture.scope(scope);who=scope_actor(scope)
    opts=dict(session_id=str(uuid4()),personalized=False,diagnostics=True,kg_enabled=False,**options)
    start=time.perf_counter()
    if lid:result=tenant_search(None,lid,who,q,staff=staff,**opts)
    else:result=GlobalQuerySearch(fixture.engine).search(q,who,**opts)
    encoded=json.dumps(jsonable_encoder(result))
    save({'suite':'C5E_native_pipeline','scope':scope,'query':q,'options':options,'elapsed_ms':(time.perf_counter()-start)*1000,
          'fixture_search_only':True,'serialized_bytes':len(encoded),'response':json.loads(encoded),'result':'PASS'})
    return result

@pytest.mark.parametrize('scope',SCOPES)
@pytest.mark.parametrize('q,kind',[
    ('online onyl','EXECUTABLE_WITH_NOTICE'),
    ('prefer beginer explanations','EXECUTABLE_WITH_NOTICE'),
    ('rated above','INCOMPLETE'),
    ('require at least 300 pages','UNSUPPORTED'),
    ('rated above 4; rated below 3','CONTRADICTORY'),
    ('Fiction 4','AMBIGUOUS')])
def test_native_typed_and_visible_notices(fixture,scope,q,kind):
    result=run(fixture,scope,q)
    plan=result['diagnostics']['plan'];assert plan['decision']['decision_type']==kind
    assert plan['parser_version']=='search-v2c-c5e-disabled-candidate-1'
    if kind=='EXECUTABLE_WITH_NOTICE':
        assert result['interpretation']['notice'] and plan['decision']['repair_notices']
        # Grammar cue repairs are notice-only, not fake facet correction tokens.
        assert not plan['corrections']
    else:
        assert result['results']==[] and result['has_more'] is False
        assert result['diagnostics']['provider']=='GUARDED_QUERY'
        assert result['interpretation']['notice']

@pytest.mark.parametrize('scope',SCOPES)
def test_smart_exact_constraints_and_pagination(fixture,scope,client):
    lid,staff=fixture.scope(scope)
    titles=['C5E Marble Ledger','C5E Cobalt Ledger','C5E Quartz Ledger']
    if lid:
        for title in titles:
            response=client.post(f'/libraries/{lid}/inventory/books',json={
                'title':title,'subjects':['History'],'authors':['C5E Fixture Author'],
                'description':'isolated representative search fixture','create_physical_holding':True,'copies':1,
                'shelf_location':'C5E','idempotency_key':str(uuid4())})
            assert response.status_code==201,response.text
    else:
        fixture.db.books.insert_many([{'work_id':'OLC5E'+str(i)+'W','book_id':i+20,'title':title,
            'subjects':'History','authors':['C5E Fixture Author'],'average_rating':4.2,'active':True}
            for i,title in enumerate(titles)])
        fixture.engine.lexical_store.db.executemany('INSERT INTO lexical_values VALUES(?,?,?)',[
            ('TITLE',title.lower(),'OLC5E'+str(i)+'W') for i,title in enumerate(titles)])
    q='include History; exclude every record containing the text "Cobalt"'
    first=run(fixture,scope,q,offset=0,limit=1);second=run(fixture,scope,q,offset=1,limit=1)
    assert len(first['results'])==len(second['results'])==1 and first['has_more']
    assert first['offset']==0 and second['offset']==1 and first['limit']==second['limit']==1
    if scope=='GLOBAL':assert first['next_offset']==1
    else:assert first['total']==second['total'] and first['total']>=2
    assert first['results'][0]['title']!=second['results'][0]['title']
    assert all('Cobalt' not in x['title'] for x in first['results']+second['results'])
    assert first['diagnostics']['plan']['exclude_terms']==['cobalt']
    exact=run(fixture,scope,titles[0],mode='EXACT')
    assert [x['title'] for x in exact['results']]==[titles[0]]
    assert exact['diagnostics']['plan']['exact_text']==titles[0]
    assert not exact['diagnostics']['plan']['subjects']
    author=run(fixture,scope,'books by C5E Fixture Author')
    assert {x['title'] for x in author['results']}==set(titles)
    absent=run(fixture,scope,'include Astronomy; exclude Astronomy')
    assert not absent['results'] and absent['diagnostics']['plan']['decision']['decision_type']=='CONTRADICTORY'

@pytest.mark.parametrize('scope',SCOPES)
def test_issued_literal_clarification_one_use(fixture,scope):
    lid,staff=fixture.scope(scope);who=scope_actor(scope);sid=str(uuid4());query='Fiction 4'
    result=fixture.search(query,who,lid,staff,sid,personalized=False)
    public=result['interpretation']['clarification'];assert public
    pending=collection().find_one({'_id':'clarification:'+public['clarification_id']})
    choice=next(x for x in pending['choices'] if x['operation']=='literal')
    body={'query':query,'session_id':sid,'library_id':lid,'staff':staff,
          'clarification_id':public['clarification_id'],'choice_id':choice['choice_id']}
    headers={'x-user':who['sub'],'x-sid':who['sid']}
    resolved=fixture.api.post('/query/resolve',json=body,headers=headers)
    assert resolved.status_code==200,resolved.text
    assert resolved.json()['interpretation']['mode']=='EXACT'
    assert resolved.json()['choice_applied']
    assert collection().find_one({'_id':'clarification:'+public['clarification_id']})['used']
    assert fixture.api.post('/query/resolve',json=body,headers=headers).status_code==409
    save({'suite':'C5E_literal_choice','scope':scope,'result':'PASS','issued_choices':public,'resolved':resolved.json()})

@pytest.mark.parametrize('scope',SCOPES)
def test_source_owned_canonical_correction(fixture,scope):
    lid,staff=fixture.scope(scope);who=scope_actor(scope);sid=str(uuid4());query='include subject "Detectve Fiction"'
    result=fixture.search(query,who,lid,staff,sid,personalized=False)
    public=result['interpretation']['clarification'];assert public
    pending=collection().find_one({'_id':'clarification:'+public['clarification_id']})
    choice=next(x for x in pending['choices'] if x['operation']=='correction_apply')
    body={'query':query,'session_id':sid,'library_id':lid,'staff':staff,
          'clarification_id':public['clarification_id'],'choice_id':choice['choice_id']}
    response=fixture.api.post('/query/resolve',json=body,headers={'x-user':who['sub'],'x-sid':who['sid']})
    assert response.status_code==200,response.text
    assert {'key':'subject','label':'Genre / Subject: Detective Fiction'} in response.json()['interpretation']['chips']
    assert collection().find_one({'_id':sid})['current_plan']['subjects']==['Detective Fiction']
    assert fixture.api.post('/query/resolve',json=body,headers={'x-user':who['sub'],'x-sid':who['sid']}).status_code==409
    save({'suite':'C5E_scoped_canonical_choice','scope':scope,'result':'PASS','issuance':result,'resolution':response.json()})

def test_native_provider_failure_not_success(fixture,monkeypatch):
    class Busy:
        database=fixture.db
        def find(self,*a,**k):raise RuntimeError('C5E disposable fixture provider unavailable')
    monkeypatch.setattr(fixture.engine,'books_collection',Busy())
    with pytest.raises(HTTPException) as caught:
        run(fixture,'GLOBAL','include History')
    assert caught.value.status_code==503
