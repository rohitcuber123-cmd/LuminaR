"""Real canonical tenant projections and actual recommender plumbing, isolated Mongo."""
from unittest.mock import Mock
from uuid import uuid4
from fastapi.testclient import TestClient
from backend.database.mongodb import db
from backend.services import library_catalogue_experience as catalogue_service
from backend.services.search_history_service import create_search_history
from recommendation import recommendation_service as recommender
from recommendation.ranked_pages import RankedRecommendationPages
from recommendation import api as recommendation_api
from test_catalogue import catalogue,call,command

def recs(client,library,ids=('OL1W',),limit=50):
    return call(client,2,'POST',library['base']+'/catalogue/recommendations',{'work_ids':list(ids),'limit':limit})

def test_global_recommendation_provider_traced(client,catalogue,monkeypatch):
    create_search_history(2,'beginner computer networking',10,[])
    response=Mock(status_code=200);response.json.return_value={'results':[{'work_id':'OL1W','title':'Global Atlas','subjects':'Networking','hnsw_score':.8}]}
    post=Mock(return_value=response);monkeypatch.setattr(recommender.requests,'post',post)
    result=recommender.get_recommendations(2,'Bearer isolated',strict_service_errors=True)
    assert result and result[0]['work_id']=='OL1W'
    args=post.call_args;assert args.args[0]=='http://127.0.0.1:8003/search'
    assert args.kwargs['json']=={'query':'beginner computer networking','query_contract':'MACHINE','top_k':50,'save_history':False}
    assert result[0]['score_breakdown']['semantic_score']==.8

def test_tenant_recommendation_provider_traced(client,catalogue):
    a,_,_=catalogue;result=recs(client,a)
    assert result['ranking']=='GLOBAL_INTERSECTION_AND_LOCAL_DISCOVERY'
    assert result['intersection_count']==1

def test_tenant_recommendations_library_scoped(client,catalogue):
    a,b,ids=catalogue;result=recs(client,a)
    assert all(r['library_id']==a['id'] for r in result['results'])

def test_tenant_recommendations_no_global_filler(client,catalogue):
    a,_,_=catalogue;result=recs(client,a,['OL1W','OL999W'])
    assert result['results'] and all(r['source']=='LIBRARY' and r['owned_by_current_library'] for r in result['results'])

def test_tenant_recommendations_canonical_hydration(client,catalogue,monkeypatch):
    a,_,_=catalogue;hydrate=Mock(wraps=catalogue_service.hydrate);monkeypatch.setattr(catalogue_service,'hydrate',hydrate)
    result=recs(client,a);hydrate.assert_called_once()
    assert result['source']['circulation_state']=='CANONICAL'
    assert all(r['availability'] is not None and r['requestable_count']==r['availability']['requestable'] for r in result['results'])

def test_tenant_recommendations_no_duplicate_global_local_identity(client,catalogue):
    a,_,_=catalogue;result=recs(client,a,['OL1W']*3)
    ids=[r['library_book_id'] for r in result['results']]
    assert len(ids)==len(set(ids)) and sum(r['global_work_id']=='OL1W' for r in result['results'])==1
    assert all(r['source']=='LIBRARY' for r in result['results'])

def test_recommendation_multi_library_isolation(client,catalogue):
    a,b,_=catalogue
    call(client,1,'POST',b['base']+'/inventory/books',command(title='B Community History',subjects=['History'],copies=1),201)
    a_rows=recs(client,a)['results'];b_rows=recs(client,b)['results']
    assert all(r['library_id']==a['id'] for r in a_rows) and all(r['library_id']==b['id'] for r in b_rows)
    assert not set(r['library_book_id'] for r in a_rows)&set(r['library_book_id'] for r in b_rows)
    assert not any(r['global_work_id']=='OL1W' for r in b_rows)

def test_recommendation_cold_start(client,catalogue,monkeypatch):
    a,_,_=catalogue;post=Mock(side_effect=AssertionError('Cold recommender has no semantic query'))
    monkeypatch.setattr(recommender.requests,'post',post)
    assert recommender.get_recommendations(2,'Bearer isolated')==[];post.assert_not_called()
    local=recs(client,a,[])['results'];assert len(local)==10 and all(r['library_id']==a['id'] for r in local)

def test_recommendation_archived_book_filtered(client,catalogue):
    a,_,ids=catalogue
    db.institution_library_books.update_one({'library_book_id':ids[0]},{'$set':{'status':'WITHDRAWN'}})
    assert ids[0] not in [r['library_book_id'] for r in recs(client,a)['results']]

def test_recommendation_deleted_foreign_and_unavailable_filtered(client,catalogue):
    a,_,ids=catalogue
    db.institution_library_books.delete_one({'library_book_id':ids[0]})
    db.institution_library_books.update_one({'library_book_id':ids[1]},{'$set':{'library_id':str(uuid4())}})
    db.institution_holdings.delete_one({'library_book_id':ids[2]})
    assert not set(ids[:3])&set(r['library_book_id'] for r in recs(client,a)['results'])

def test_empty_library_recommendation_explicit_global_fallback(client,catalogue):
    _,b,_=catalogue;result=recs(client,b)
    assert result['source']['catalogue_source']=='GLOBAL_FALLBACK' and result['results']==[]

def test_recommendation_next_page_same_provider(client,catalogue):
    metadata={f'OL{i}W':{'title':f'Canonical {i}'} for i in range(30)};compute=Mock(return_value=[{'work_id':wid,'score':.5,'score_breakdown':{}} for wid in metadata])
    pages=RankedRecommendationPages(compute,hydrate=lambda ids:metadata,exclude=lambda uid:set(),version=lambda:'global1')
    one=pages.page({'sub':'2','sid':'session'},'Bearer isolated',10,0);two=pages.page({'sub':'2','sid':'session'},'Bearer isolated',10,10)
    assert compute.call_count==1 and two['ranking']['cache_hit']
    assert not set(r['work_id'] for r in one['recommendations'])&set(r['work_id'] for r in two['recommendations'])

def test_recommendation_previous_page_same_provider(client,catalogue):
    metadata={f'OL{i}W':{'title':f'Canonical {i}'} for i in range(30)}
    compute=Mock(return_value=[{'work_id':wid,'score':.5,'score_breakdown':{}} for wid in metadata])
    pages=RankedRecommendationPages(compute,hydrate=lambda ids:metadata,exclude=lambda uid:set(),version=lambda:'global1')
    one=pages.page({'sub':'2','sid':'session'},'Bearer isolated',10,0);pages.page({'sub':'2','sid':'session'},'Bearer isolated',10,10)
    previous=pages.page({'sub':'2','sid':'session'},'Bearer isolated',10,0)
    assert previous['recommendations']==one['recommendations'] and compute.call_count==1

def test_global_recommendation_deleted_work_removed_from_cached_pool(client,catalogue):
    metadata={'OL1W':{'title':'Live'}};compute=Mock(return_value=[{'work_id':'OL1W','score':.5,'score_breakdown':{}}])
    pages=RankedRecommendationPages(compute,hydrate=lambda ids:dict(metadata),exclude=lambda uid:set(),version=lambda:'global1')
    assert pages.page({'sub':'2'},'Bearer isolated')['recommendations']
    metadata.clear();assert pages.page({'sub':'2'},'Bearer isolated')['recommendations']==[]

def test_recommendation_profiles_and_cache_are_user_session_scoped(client,catalogue):
    compute=Mock(side_effect=lambda uid,*args,**kwargs:[{'work_id':f'OL{uid}W','score':.5,'score_breakdown':{}}])
    metadata={'OL2W':{'title':'User 2'},'OL3W':{'title':'User 3'}}
    pages=RankedRecommendationPages(compute,hydrate=lambda ids:metadata,exclude=lambda uid:set(),version=lambda:'global1')
    assert pages.page({'sub':'2','sid':'a'},'Bearer isolated')['recommendations'][0]['work_id']=='OL2W'
    assert pages.page({'sub':'3','sid':'b'},'Bearer isolated')['recommendations'][0]['work_id']=='OL3W'
    assert compute.call_count==2

def test_recommendation_search_unavailable_is_safe_api_503_not_500(client,catalogue,monkeypatch):
    create_search_history(2,'networking',10,[])
    monkeypatch.setattr(recommender.requests,'post',Mock(side_effect=recommender.requests.ConnectionError('isolated')))
    monkeypatch.setattr(recommendation_api,'get_user_from_token',lambda token:{'sub':'2','sid':'fixture'})
    monkeypatch.setattr(recommendation_api,'ranked_recommendations',RankedRecommendationPages(recommender.get_recommendations,version=lambda:'isolated'))
    response=TestClient(recommendation_api.app).get('/recommendations',headers={'Authorization':'Bearer isolated'})
    assert response.status_code==503 and 'isolated' not in response.text,response.text

def test_recommendation_does_not_read_tenant_hnsw_or_kg(client,catalogue,monkeypatch):
    a,_,_=catalogue
    from backend.services.library_intelligence_artifacts import ArtifactCache
    load=Mock(side_effect=AssertionError('Projection must not load tenant artifact'))
    monkeypatch.setattr(ArtifactCache,'load',load)
    for target in ['SEARCH_INDEX','KNOWLEDGE_GRAPH']:
        db.institution_intelligence_targets.insert_one({'library_id':a['id'],'target':target,'state':'FAILED'})
    assert recs(client,a)['results'];load.assert_not_called()

def test_recommendation_tenant_index_states_do_not_change_provider(client,catalogue):
    a,_,_=catalogue;before=recs(client,a)['results']
    for state in ['NOT_BUILT','BUILDING','FAILED','STALE','READY']:
        db.institution_intelligence_targets.update_one({'library_id':a['id'],'target':'SEARCH_INDEX'},{'$set':{'state':state}},upsert=True)
        result=recs(client,a);assert result['ranking']=='GLOBAL_INTERSECTION_AND_LOCAL_DISCOVERY' and result['results']==before

def test_new_arrivals_and_popular_are_distinct_from_for_you(client,catalogue):
    a,_,_=catalogue;home=call(client,2,'GET',a['base']+'/catalogue/home')
    assert home['new_arrivals'] and home['popular']==[]
    assert recs(client,a,[])['ranking']=='GLOBAL_INTERSECTION_AND_LOCAL_DISCOVERY'
