"""Actual MiniLM/CE plumbing with controlled catalogue/model; no index mutation."""
from types import SimpleNamespace
import numpy as np
import pytest
from search.luminar_search import LuminaRSearchEngine
from search.ranked_pages import RankedSearchPages
from backend.services.ranked_result_cache import RankedResultCache

class Books:
    def __init__(self, count=60):
        self.rows={f'OL{i:03}W':{'work_id':f'OL{i:03}W','title':f'Book {i}','authors':f'Author {i}',
                   'subjects':f'Subject {i}','total_copies':2,'available_copies':1} for i in range(count)}
    def find(self, query, projection=None):
        return [dict(row) for wid,row in self.rows.items() if wid in query['work_id']['$in']]

@pytest.fixture
def system(monkeypatch):
    monkeypatch.setenv('LEXICAL_SEARCH_ENABLED','false')
    books=Books();calls=[]
    def candidates(vector,count):
        calls.append(('semantic',count))
        return [{'work_id':wid,'hnsw_score':1-i/100} for i,wid in enumerate(books.rows)][:count]
    def predict(pairs,**kw):
        calls.append(('rerank',len(pairs)))
        return np.arange(len(pairs),0,-1,dtype=float)
    engine=LuminaRSearchEngine.__new__(LuminaRSearchEngine);engine.device='cpu'
    snapshot=SimpleNamespace(base=SimpleNamespace(ntotal=60),delta=SimpleNamespace(ntotal=0),manifest={'version':'v1','semantic_generation':1},candidates=candidates)
    engine.index_manager=SimpleNamespace(snapshot=snapshot,encode=lambda texts:np.ones((1,8),dtype=np.float32))
    engine.books_collection=books;engine.library_inventory=books;engine.reranker=SimpleNamespace(predict=predict)
    return SimpleNamespace(pages=RankedSearchPages(engine),engine=engine,books=books,calls=calls,snapshot=snapshot)

def ids(response):return [row['work_id'] for row in response['results']]

@pytest.mark.parametrize('limit',[10,20,50])
def test_search_limit_honored_and_requested_depth_reaches_reranker(system,limit):
    result=system.pages.search('query',limit)
    assert len(ids(result))==limit
    assert ('rerank',50) in system.calls
    assert next(count for kind,count in system.calls if kind=='semantic')>=50
    assert result['ranking']['reranked_count']==50

def test_search_pages_1_2_3_and_no_duplicates(system):
    pages=[system.pages.search('query',10,offset) for offset in (0,10,20)]
    assert [r['rank'] for r in pages[1]['results']]==list(range(11,21))
    assert [r['rank'] for r in pages[2]['results']]==list(range(21,31))
    assert len(set(sum((ids(page) for page in pages),[])))==30
    assert system.calls.count(('rerank',50))==1
    assert ids(system.pages.search('query',10))==ids(pages[0])
    assert pages[0]['next_offset']==10 and pages[2]['has_more']
    assert not system.pages.search('query',10,40)['has_more']

@pytest.mark.parametrize('limit,offset',[(0,0),(51,0),(5000000,0),(10,-1),(10,50),(1,1000000)])
def test_safe_max_limit(system,limit,offset):
    with pytest.raises(ValueError):system.pages.search('query',limit,offset)
    assert system.calls==[]

def test_cached_pages_rehydrate_metadata_and_availability(system):
    system.pages.search('query')
    system.books.rows['OL000W'].update(title='Fresh title',available_copies=0)
    result=system.pages.search('query')
    assert result['ranking']['cache_hit'] and result['results'][0]['title']=='Fresh title'
    assert result['results'][0]['available_physical_copies']==0
    filtered=system.pages.search('query',library_id='LIB001',available_at_library=True)
    assert 'OL000W' not in ids(filtered)
    assert len(filtered['results'])==10 and filtered['next_offset']==10

def test_generation_and_query_invalidate_ranked_pool(system):
    system.pages.search('query');system.pages.search('query')
    system.snapshot.manifest.update(version='v2',semantic_generation=2)
    assert not system.pages.search('query')['ranking']['cache_hit']
    assert not system.pages.search('new query')['ranking']['cache_hit']
    assert system.calls.count(('rerank',50))==3

def test_crossencoder_tie_break_is_deterministic(system):
    system.engine.reranker.predict=lambda pairs,**kw:np.ones(len(pairs))
    system.snapshot.candidates=lambda vector,count:[{'work_id':wid,'hnsw_score':.9} for wid in reversed(list(system.books.rows))][:50]
    result=system.engine.search('query',50)
    assert ids(result)==sorted(ids(result))

def test_short_pool_has_no_false_more(system):
    system.books.rows=dict(list(system.books.rows.items())[:7])
    result=system.pages.search('query')
    assert result['returned']==7 and not result['has_more'] and result['next_offset'] is None

def test_ttl_and_bounded_cache():
    clock=[0];cache=RankedResultCache(ttl=10,maximum=2,clock=lambda:clock[0])
    assert cache.get_or_create('a',lambda:1)==(1,False)
    assert cache.get_or_create('a',lambda:2)==(1,True)
    cache.get_or_create('b',lambda:2);cache.get_or_create('c',lambda:3)
    assert len(cache.entries)==2 and 'a' not in cache.entries
    clock[0]=11
    assert cache.get_or_create('b',lambda:4)==(4,False)

def test_recommendation_search_depth_request_receives_fifty(monkeypatch):
    from recommendation import recommendation_service as service
    seen=[]
    class Response:
        status_code=200
        def json(self):return {'results':[{'work_id':f'OL{i}W','hnsw_score':.9,'title':str(i)} for i in range(50)]}
    def post(url,**kw):seen.append(kw['json']);return Response()
    monkeypatch.setattr(service.requests,'post',post)
    result=service.generate_semantic_candidates(['query'],'Bearer controlled',50)
    assert seen[0]['top_k']==50 and len(result)==50

def test_recommendation_stable_pages_mode_seed_and_fresh_availability():
    from recommendation.ranked_pages import RankedRecommendationPages
    books=Books();calls=[]
    def compute(uid,auth,**kw):
        calls.append((uid,kw))
        return [{'work_id':wid,'score':1-i/100,'score_breakdown':{'semantic_score':1-i/100}} for i,wid in enumerate(books.rows)][:50]
    service=RankedRecommendationPages(compute,hydrate=lambda ids:books.rows,exclude=lambda uid:set(),version=lambda:'v1')
    user={'sub':'1','sid':'session'}
    first=service.page(user,'Bearer controlled',10)
    second=service.page(user,'Bearer controlled',10,10)
    assert not set(r['work_id'] for r in first['recommendations'])&set(r['work_id'] for r in second['recommendations'])
    assert len(calls)==1 and calls[0][1]['limit']==50 and second['has_more']
    assert second['recommendation_mode']=='PERSONALIZED_EXISTING_FORMULA' and second['seed_work_ids']==[]
    books.rows['OL010W']['available_copies']=0
    assert service.page(user,'Bearer controlled',10,10)['recommendations'][0]['available_copies']==0
    seed='OL059W'
    first=service.page(user,'Bearer controlled',10,seed_work_id=seed)
    second=service.page(user,'Bearer controlled',10,10,seed_work_id=seed)
    assert first['seed_work_ids']==second['seed_work_ids']==[seed]
    assert second['recommendation_mode']=='SINGLE_SELECTED_BOOK' and len(calls)==2
    assert not service.page(user,'Bearer controlled',10,40,seed_work_id=seed)['has_more']


def test_lexical_availability_invalidates_cache(system,monkeypatch):
    monkeypatch.setenv('LEXICAL_SEARCH_ENABLED','true')
    health={'lexical_available':True,'lexical_version':'v1'}
    system.engine.lexical_store=SimpleNamespace(health=lambda:health)
    system.pages.search('query')
    assert system.pages.search('query')['ranking']['cache_hit']
    health['lexical_available']=False
    assert not system.pages.search('query')['ranking']['cache_hit']


def test_recommendation_cache_ttl_generation_and_exclusions():
    from recommendation.ranked_pages import RankedRecommendationPages
    books=Books();clock=[0];version=['v1'];blocked=set();calls=[]
    def compute(uid,auth,**kw):
        calls.append(kw)
        return [{'work_id':wid,'score':1,'score_breakdown':{}} for wid in books.rows][:50]
    cache=RankedResultCache(ttl=10,clock=lambda:clock[0])
    pages=RankedRecommendationPages(compute,cache=cache,hydrate=lambda ids:books.rows,exclude=lambda uid:blocked,version=lambda:version[0])
    user={'sub':'1','sid':'session'}
    first=pages.page(user,'Bearer controlled')
    blocked.add('OL000W')
    second=pages.page(user,'Bearer controlled')
    assert second['ranking']['cache_hit'] and second['recommendations'][0]['work_id']=='OL001W'
    version[0]='v2'
    assert not pages.page(user,'Bearer controlled')['ranking']['cache_hit']
    clock[0]=11
    assert not pages.page(user,'Bearer controlled')['ranking']['cache_hit']
    assert len(calls)==3
