from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from backend.services import library_intelligence_store as store
from search.library_intelligence import TenantIntelligence
from search.query_execution import tenant_search
from search.query_expansion import tenant_expansion
from search.query_plan import parse_query
from test_intelligence import encoder,book,build

@pytest.fixture
def query_library(client,library,database):
    assert database.name.startswith('luminar_institution_v2g_test_')
    lid=library(private=True)
    assert client.post(f'/libraries/{lid}/join',headers={'x-test-user':'2'},json={'access_code':'Isolated fixture access code'}).status_code==200
    row=book(client,lid,'Neural networks primer',linked=True)
    second=book(client,lid,'Deep learning handbook')
    for bid,subjects in [(row['library_book_id'],['Neural networks','Deep learning']),(second['library_book_id'],['Deep learning','Romance'])]:
        database.institution_library_books.update_one({'library_book_id':bid},{'$set':{'subjects':subjects}})
    database.books.update_one({'work_id':'OL1W'},{'$set':{'average_rating':4.5,'rating_count':2}})
    rerank=Mock(side_effect=lambda pairs:[1.]*len(pairs))
    worker=TenantIntelligence(encoder,rerank,model_version='all-MiniLM-L6-v2:unit')
    search,_=build(lid,worker=worker);kg,_=build(lid,'KNOWLEDGE_GRAPH',worker)
    return lid,row,second,worker,search,kg

def test_tenant_kg_same_context_bounded_and_canonically_reranked(query_library,monkeypatch):
    lid,row,_,worker,search,kg=query_library
    monkeypatch.setattr('search.query_execution.global_expansion',Mock(side_effect=AssertionError('No global KG in tenant search')))
    result=tenant_search(worker,lid,{'sub':'2'},'books about neural networks',diagnostics=True)
    d=result['diagnostics']
    assert d['kg_used'] and d['hnsw_used'] and d['reranker_used']
    assert d['kg']['concepts']==['Deep learning'] and d['kg']['generation']==kg['artifact_generation_id']
    assert d['generation']==search['artifact_generation_id'] and all(r['library_id']==lid for r in result['results'])
    assert result['results'][0]['library_book_id']==row['library_book_id']
    assert worker.reranker.call_args.args[0][0][0]=='neural networks'

@pytest.mark.parametrize('state',['NOT_BUILT','BUILDING','FAILED','RECOVERY_REQUIRED','STALE'])
def test_tenant_kg_unavailable_search_hnsw_fallback(query_library,state):
    lid,_,_,worker,_,_=query_library
    store.collection('intelligence_targets').update_one({'library_id':lid,'target':'KNOWLEDGE_GRAPH'},{'$set':{'state':state}})
    result=tenant_search(worker,lid,{'sub':'2'},'books about neural networks',diagnostics=True)
    assert result['diagnostics']['hnsw_used'] and not result['diagnostics']['kg_used']
    assert result['results'] and result['interpretation']['related_concepts']==[]

def test_private_outsider_kg_and_search_denied_before_cache(query_library,monkeypatch):
    lid,_,_,worker,_,_=query_library
    from backend.services.library_intelligence_service import graph_cache
    load=Mock(side_effect=AssertionError('Outsider graph lookup'));monkeypatch.setattr(graph_cache,'load',load)
    for fn in [lambda:tenant_expansion(parse_query('books about neural networks'),lid,{'sub':'3'}),lambda:tenant_search(worker,lid,{'sub':'3'},'books about neural networks')]:
        with pytest.raises(HTTPException) as error:fn()
        assert error.value.status_code==404
    load.assert_not_called()

def test_kg_negative_and_rating_cannot_be_overridden(query_library):
    lid,row,_,worker,_,_=query_library
    r=tenant_search(worker,lid,{'sub':'2'},'books about neural networks but not romance rated above 4',diagnostics=True)
    assert [b['library_book_id'] for b in r['results']]==[row['library_book_id']]
    assert r['diagnostics']['plan']['exclude_terms']==['Romance']
    assert all(b['average_rating']>4 for b in r['results'])

def test_soft_learn_intent_reaches_existing_crossencoder(query_library):
    lid,_,_,worker,_,_=query_library
    r=tenant_search(worker,lid,{'sub':'2'},'I want an easy introduction to neural networks')
    assert r['interpretation']['intent']=='LEARN'
    assert worker.reranker.call_args.args[0][0][0]=='introductory beginner guide to neural networks'

def test_foreign_graph_generation_is_never_used(query_library,monkeypatch):
    lid,_,_,worker,_,_=query_library
    from backend.services.library_intelligence_service import graph_cache
    load=graph_cache.load
    def foreign(*args):
        manifest,records,graph=load(*args)
        return {**manifest,'library_id':'foreign-library'},records,graph
    monkeypatch.setattr(graph_cache,'load',foreign)
    result=tenant_search(worker,lid,{'sub':'2'},'books about neural networks',diagnostics=True)
    assert not result['diagnostics']['kg_used'] and result['interpretation']['related_concepts']==[]
    assert all(r['library_id']==lid for r in result['results'])
