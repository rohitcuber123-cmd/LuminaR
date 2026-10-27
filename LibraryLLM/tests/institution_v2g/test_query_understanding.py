from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from search.query_execution import tenant_search, tenant_facets
from search.library_intelligence import TenantIntelligence
from test_intelligence import encoder, book, build

def test_global_shared_plan_strict_filters_and_no_hnsw_for_facets(database):
    from search.query_execution import GlobalQuerySearch
    database.book_categories.insert_one({'name':'Fiction','count':2})
    database.books.delete_many({})
    database.books.insert_many([
      {'book_id':1,'work_id':'OL1W','title':'Wizard world','subjects':'Fiction','average_rating':4.8,'rating_count':1},
      {'book_id':2,'work_id':'OL2W','title':'Fiction title only','subjects':'History','average_rating':5,'rating_count':2},
      {'book_id':3,'work_id':'OL3W','title':'Wizard other','subjects':'Fiction','average_rating':3.9,'rating_count':10}])
    calls=[]
    def semantic(**kwargs):
        calls.append(kwargs)
        predicate=kwargs['metadata_predicate']
        rows=[r for r in database.books.find({}) if predicate(r)]
        return {'results':rows,'diagnostics':{'raw_hnsw':[{}, {}, {}]}}
    engine=SimpleNamespace(books_collection=database.books,search=semantic)
    facade=GlobalQuerySearch(engine)
    pure=facade.search('fiction',{'sub':'1'},mode='GENRE_SUBJECT')
    assert {r['work_id'] for r in pure['results']}=={'OL1W','OL3W'} and calls==[]
    mixed=facade.search('fiction books about wizards rated above 4',{'sub':'1'},diagnostics=True)
    assert [r['work_id'] for r in mixed['results']]==['OL1W']
    assert calls[0]['query']=='wizards' and mixed['diagnostics']['hnsw_used']

def test_query_hnsw_cache_generation_isolated_between_libraries(client,library):
    a=library();ar=book(client,a);b=library(private=True,name='Private second');br=book(client,b)
    worker=TenantIntelligence(encoder,lambda pairs:[1.]*len(pairs),model_version='all-MiniLM-L6-v2:unit')
    aj,_=build(a,worker=worker);bj,_=build(b,worker=worker)
    for lid,row,job in [(a,ar,aj),(b,br,bj),(a,ar,aj)]:
        result=tenant_search(worker,lid,{'sub':'1'},'books about networking',staff=True,diagnostics=True)
        assert result['diagnostics']['generation']==job['artifact_generation_id']
        assert [r['library_book_id'] for r in result['results']]==[row['library_book_id']]
    assert {key[0] for key in worker.cache.metrics()['keys']}=={a,b}

def test_tenant_semantic_rating_filtered_before_rerank(client,library,database):
    lid=library();record=book(client,lid,linked=True)
    database.books.update_one({'work_id':'OL1W'},{'$set':{'average_rating':4.8,'rating_count':1}})
    reranker=Mock(return_value=[1.])
    worker=TenantIntelligence(encoder,reranker,model_version='all-MiniLM-L6-v2:unit')
    build(lid,worker=worker)
    response=tenant_search(worker,lid,{'sub':'1'},'books about networking rating above 4',staff=True,diagnostics=True)
    assert response['diagnostics']['hnsw_used'] and response['diagnostics']['reranker_used']
    assert response['results'][0]['library_book_id']==record['library_book_id']
    assert all(r['average_rating']>4 for r in response['results'])
    reranker.reset_mock()
    response=tenant_search(worker,lid,{'sub':'1'},'books about networking rating above 4.9',staff=True)
    assert response['results']==[];reranker.assert_not_called()

def test_private_facets_and_search_authorize_before_cache(client,library):
    lid=library(private=True);book(client,lid)
    assert tenant_facets(lid,{'sub':'1'},True)['results']
    cache=Mock(side_effect=AssertionError('Unauthorized cache access'))
    worker=SimpleNamespace(cache=SimpleNamespace(load=cache))
    for operation in (lambda:tenant_facets(lid,{'sub':'2'}),lambda:tenant_search(worker,lid,{'sub':'2'},'books about networking')):
        with pytest.raises(HTTPException) as exc:operation()
        assert exc.value.status_code in (403,404)
    cache.assert_not_called()

def test_library_vocabulary_isolation_and_fallback(client,library):
    a=library();row=book(client,a);b=library(name='Empty other library')
    worker=SimpleNamespace(cache=SimpleNamespace(load=Mock(side_effect=AssertionError('No index'))))
    result=tenant_search(worker,a,{'sub':'1'},'Computer networks',staff=True,mode='GENRE_SUBJECT',diagnostics=True)
    assert result['results'][0]['library_book_id']==row['library_book_id'] and not result['diagnostics']['hnsw_used']
    assert tenant_search(worker,b,{'sub':'1'},'Computer networks',staff=True,mode='GENRE_SUBJECT')['results']==[]
    assert tenant_search(worker,a,{'sub':'1'},'books about networking',staff=True)['source']['search_source']=='LOCAL_FALLBACK'

def test_core_fallback_privacy_headers_and_exact_mode(client,library):
    lid=library();row=book(client,lid)
    for path in ('facets','discovery?staff=true&search='+row['title'].replace(' ','%20')+'&mode=EXACT'):
        response=client.get(f'/libraries/{lid}/catalogue/{path}'+('?staff=true' if path=='facets' else ''))
        assert response.status_code==200,response.text
        assert response.headers['cache-control']=='private, no-store'
        if path.startswith('discovery'):assert response.json()['results'][0]['library_book_id']==row['library_book_id']

def test_patron_online_filter_excludes_staff_only_and_uses_canonical_year(client,library,upload,ready,database):
    lid=library(private=True)
    joined=client.post(f'/libraries/{lid}/join',headers={'x-test-user':'2'},json={'access_code':'Isolated fixture access code'})
    assert joined.status_code==200
    readable=book(client,lid,'Online networking',physical=False)
    secret=book(client,lid,'Staff networking',physical=False)
    a=upload(lid,book_id=readable['library_book_id']).json();ready(a)
    b=upload(lid,book_id=secret['library_book_id'],visibility='STAFF_ONLY').json();ready(b)
    database.institution_library_books.update_one({'library_book_id':readable['library_book_id']},{'$set':{'publication_year':2021}})
    worker=SimpleNamespace(cache=SimpleNamespace(load=Mock(side_effect=AssertionError('No index'))))
    result=tenant_search(worker,lid,{'sub':'2'},'online books about networking after 2020')
    assert [r['library_book_id'] for r in result['results']]==[readable['library_book_id']]
    assert result['results'][0]['has_online'] is True and result['results'][0]['publication_year']==2021
    assert tenant_search(worker,lid,{'sub':'2'},'online books about networking after 2021')['results']==[]
    assert tenant_search(worker,lid,{'sub':'2'},'online books about networking available to request')['results']==[]
