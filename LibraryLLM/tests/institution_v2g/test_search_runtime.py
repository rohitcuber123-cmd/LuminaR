"""Routing/hydration contracts on isolated Mongo and real tiny FAISS indexes.

The deterministic unit encoder is not semantic-quality evidence. The separate
Chromium QA runner measures the resident MiniLM and CrossEncoder models.
"""
from unittest.mock import Mock
from uuid import uuid4
from types import SimpleNamespace
import json
import numpy as np
import pytest
from fastapi import FastAPI
from backend.dependencies import get_current_user
from backend.services import library_intelligence_store as store, library_intelligence_service as service
from backend.services import library_catalogue_experience as catalogue
from search.library_intelligence import TenantIntelligence
from search.library_intelligence_api import install
from fastapi.testclient import TestClient
from test_intelligence import encoder, book, build

def ready(client, library, title='Mobility and transport for elderly and handicapped persons'):
    lid=library(); record=book(client,lid,title)
    reranker=Mock(side_effect=lambda pairs:np.arange(len(pairs),dtype=float))
    worker=TenantIntelligence(encoder,reranker,model_version='all-MiniLM-L6-v2:unit')
    job,_=build(lid,worker=worker)
    return lid,record,job,worker,reranker

def test_tenant_ready_uses_tenant_hnsw(client,library):
    lid,row,job,worker,reranker=ready(client,library)
    load=worker.cache.load;index_search=Mock()
    def observe(*args):
        manifest,records,index=load(*args)
        class Index:
            def search(self,*args): index_search(*args);return index.search(*args)
        return manifest,records,Index()
    worker.cache.load=observe
    result=worker.semantic(lid,{'sub':'1'},'getting around when walking is difficult',staff=True)
    assert index_search.call_count==1 and result['source']['search_source']=='TENANT_SEMANTIC'

@pytest.mark.parametrize('state',['NOT_BUILT','BUILDING','FAILED','STALE'],ids=[
 'test_tenant_not_built_uses_local_fallback','test_tenant_building_uses_local_fallback',
 'test_tenant_failed_uses_local_fallback','test_tenant_stale_safe_behavior'])
def test_fallback_states(client,library,state):
    lid=library();row=book(client,lid)
    if state!='NOT_BUILT':store.collection('intelligence_targets').insert_one({'library_id':lid,'target':'SEARCH_INDEX','state':state})
    fail=Mock(side_effect=AssertionError('Non-READY must not query models'))
    worker=TenantIntelligence(fail,fail)
    result=worker.semantic(lid,{'sub':'1'},'computer',staff=True)
    assert result['source']['search_source']=='LOCAL_FALLBACK' and result['source']['intelligence_status']==state
    assert [r['library_book_id'] for r in result['results']]==[row['library_book_id']]
    fail.assert_not_called()

def test_tenant_hnsw_generation_matches_selected_library(client,library):
    a,row,job,worker,_=ready(client,library);b=library(name='Foreign');book(client,b)
    result=worker.semantic(a,{'sub':'1'},'transport',staff=True)
    assert result['source']['search_generation_id']==job['artifact_generation_id']
    assert all(r['library_id']==a for r in result['results'])
    assert worker.cache.metrics()['keys']==[[a,job['artifact_generation_id'],'SEARCH_INDEX']]

def test_tenant_hnsw_no_global_filler(client,library):
    lid,row,_,worker,_=ready(client,library)
    result=worker.semantic(lid,{'sub':'1'},'public fixture',staff=True)
    assert result['results'] and all(r['source']=='LIBRARY' and r['library_book_id']==row['library_book_id'] for r in result['results'])

def test_tenant_hnsw_no_cross_library_results(client,library):
    lid,row,_,worker,_=ready(client,library);foreign=library(name='Other');book(client,foreign)
    result=worker.semantic(lid,{'sub':'1'},'transport',staff=True)
    assert all(r['library_id']==lid for r in result['results'])

def test_tenant_semantic_nonliteral_query(client,library):
    lid,row,_,worker,_=ready(client,library);q='getting around when walking is difficult'
    assert catalogue.books(lid,{'sub':'1'},search=q,staff=True)['results']==[]
    assert worker.semantic(lid,{'sub':'1'},q,staff=True)['results'][0]['library_book_id']==row['library_book_id']

def test_semantic_result_not_dependent_on_exact_keyword(client,library,monkeypatch):
    lid,row,_,worker,_=ready(client,library)
    monkeypatch.setattr(catalogue,'books',Mock(side_effect=AssertionError('READY must not fall through to lexical')))
    assert worker.semantic(lid,{'sub':'1'},'nonliteral concept',staff=True)['source']['search_source']=='TENANT_SEMANTIC'

def test_hnsw_candidates_are_reranked(client,library):
    lid,row,_,worker,reranker=ready(client,library)
    worker.semantic(lid,{'sub':'1'},'transport',staff=True)
    reranker.assert_called_once();assert reranker.call_args.args[0][0][0]=='transport'
    assert row['title'] in reranker.call_args.args[0][0][1]

def test_final_results_are_canonical_hydrated(client,library,monkeypatch):
    lid,row,_,worker,_=ready(client,library)
    hydrate=Mock(wraps=catalogue.hydrate);monkeypatch.setattr(catalogue,'hydrate',hydrate)
    result=worker.semantic(lid,{'sub':'1'},'transport',staff=True)
    hydrate.assert_called_once();assert 'availability' in result['results'][0]

def test_archived_record_removed_after_hydration(client,library):
    lid,row,_,worker,_=ready(client,library)
    store.collection('library_books').update_one({'library_book_id':row['library_book_id']},{'$set':{'status':'WITHDRAWN'}})
    result=worker.semantic(lid,{'sub':'1'},'Mobility',staff=True)
    assert result['results']==[] and result['source']['search_source']=='LOCAL_FALLBACK'

@pytest.mark.parametrize('change',['delete','foreign','no_format'])
def test_stale_excludes_now_ineligible(client,library,change):
    lid,row,_,worker,_=ready(client,library)
    if change=='delete':store.collection('library_books').delete_one({'library_book_id':row['library_book_id']})
    elif change=='foreign':store.collection('library_books').update_one({'library_book_id':row['library_book_id']},{'$set':{'library_id':str(uuid4())}})
    else:
        store.collection('holdings').delete_many({'library_id':lid})
        store.collection('memberships').insert_one({'library_id':lid,'user_id':2,'role':'GENERAL_USER','status':'ACTIVE','membership_id':str(uuid4())})
    result=worker.semantic(lid,{'sub':'2' if change=='no_format' else '1'},'Mobility',staff=change!='no_format')
    assert result['results']==[]

@pytest.mark.parametrize('kg_state',['NOT_BUILT','FAILED'])
def test_hnsw_ready_kg_unavailable_search_still_works(client,library,kg_state,monkeypatch):
    lid,row,_,worker,_=ready(client,library)
    if kg_state=='FAILED':store.collection('intelligence_targets').insert_one({'library_id':lid,'target':'KNOWLEDGE_GRAPH','state':'FAILED'})
    monkeypatch.setattr(service,'graph',Mock(side_effect=AssertionError('Search must not require KG')))
    assert worker.semantic(lid,{'sub':'1'},'transport',staff=True)['source']['search_source']=='TENANT_SEMANTIC'

def test_search_kg_usage_classified(client,library,monkeypatch):
    lid,row,_,worker,_=ready(client,library)
    graph=Mock(side_effect=AssertionError('KG exploration is independent'))
    monkeypatch.setattr(service.graph_cache,'load',graph)
    worker.semantic(lid,{'sub':'1'},'transport',staff=True);graph.assert_not_called()

def test_search_does_not_require_kg(client,library):
    lid,row,_,worker,_=ready(client,library)
    assert not store.collection('intelligence_targets').find_one({'library_id':lid,'target':'KNOWLEDGE_GRAPH'})
    assert worker.semantic(lid,{'sub':'1'},'transport',staff=True)['results']

def test_catalogue_exact_title_still_works(client,library):
    lid,row,_,worker,_=ready(client,library)
    assert worker.semantic(lid,{'sub':'1'},row['title'],staff=True)['results'][0]['title']==row['title']

def test_catalogue_subject_filter_still_works(client,library):
    lid,row,_,worker,_=ready(client,library)
    assert worker.semantic(lid,{'sub':'1'},'transport',staff=True,subject='Computer networks')['results']
    assert not worker.semantic(lid,{'sub':'1'},'transport',staff=True,subject='Foreign subject')['results']

@pytest.mark.parametrize('field',['accession_number','isbn_13','shelf_location','barcode'])
def test_inventory_deterministic_lookup(client,library,field):
    lid=library();body={'title':'Operational fixture','subjects':['History'],'authors':['QA'],
      'create_physical_holding':True,'copies':1,'shelf_location':'SPECIAL-SHELF','barcode':'COPY-EXACT-QA',
      'isbn_13':'9780306406157','idempotency_key':str(uuid4())}
    created=client.post(f'/libraries/{lid}/inventory/books',json=body);assert created.status_code==201,created.text
    row=created.json();q=row['accession_number'] if field=='accession_number' else body[field]
    result=client.get(f'/libraries/{lid}/inventory/books',params={'search':q});assert result.status_code==200
    assert [r['library_book_id'] for r in result.json()['results']]==[row['library_book_id']]

def test_tenant_real_http_route_selects_semantic(client,library):
    lid,row,_,worker,_=ready(client,library)
    class Model(list):
        def encode(self,texts,**kwargs):return encoder(texts)
    model=Model([SimpleNamespace(auto_model=SimpleNamespace(config=SimpleNamespace(_commit_hash='unit')))])
    engine=SimpleNamespace(embedding_model=model,reranker=SimpleNamespace(predict=lambda pairs,**kwargs:[1.]*len(pairs)))
    app=FastAPI();install(app,engine);app.dependency_overrides[get_current_user]=lambda:{'sub':'1'}
    app.state.tenant_intelligence.model_version=worker.model_version
    result=TestClient(app).get(f'/libraries/{lid}/catalogue/search?search=transport&staff=true')
    assert result.status_code==200 and result.json()['source']['search_source']=='TENANT_SEMANTIC'

def test_inventory_barcode_lookup_is_tenant_scoped(client,library):
    own=library();other=library(name='Other');book(client,own)
    created=client.post(f'/libraries/{other}/inventory/books',json={'title':'Foreign barcode fixture',
        'subjects':['History'],
        'create_physical_holding':True,'copies':1,'barcode':'FOREIGN-ONLY','shelf_location':'FOREIGN-SHELF',
        'idempotency_key':str(uuid4())})
    assert created.status_code==201,created.text
    result=client.get(f'/libraries/{own}/inventory/books',params={'search':'FOREIGN-ONLY'})
    assert result.status_code==200 and result.json()['results']==[]

def test_inventory_current_shelf_not_stale_search_text(client,library):
    lid=library();row=book(client,lid)
    store.collection('holdings').update_one({'library_book_id':row['library_book_id']},{'$set':{'shelf_location':'NEW-SHELF'}})
    result=client.get(f'/libraries/{lid}/inventory/books',params={'search':'new-shelf'})
    assert result.status_code==200 and result.json()['results'][0]['library_book_id']==row['library_book_id']

def test_global_discovery_uses_global_semantic_provider(monkeypatch):
    from search.ranked_pages import RankedSearchPages
    from search import ranked_pages
    engine=SimpleNamespace(index_manager=SimpleNamespace(snapshot=SimpleNamespace(manifest={'version':'global','semantic_generation':7})),
       search=Mock(return_value={'results':[{'work_id':'OL1W','rerank_score':2.,'hnsw_score':.8}],
          'diagnostics':{'raw_hnsw':[{}],'reranked':[{}]},'timing_ms':{}}),
       books_collection=None,_get_library_inventory=lambda *args:{})
    monkeypatch.setattr(ranked_pages,'current_books',lambda *args:{'OL1W':{'title':'Global canonical','subjects':'History','authors':'QA'}})
    result=RankedSearchPages(engine).search(query='history')
    engine.search.assert_called_once_with(query='history',top_k=50,library_id=None,available_at_library=False,diagnostics=True)
    assert result['ranking']['index_generation']==7 and result['results'][0]['title']=='Global canonical'
