"""Real isolated Mongo, actual miniature FAISS/KG and authorized catalogue guards."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from search.session_store import resolve,collection
from search.query_execution import GlobalQuerySearch,tenant_search
from test_query_v2a import query_library

@pytest.mark.parametrize('query,decision',[
 ('fiction 4','AMBIGUOUS'),('fiction rating above','INCOMPLETE'),
 ('books rated above 4 and below 3','CONTRADICTORY'),
 ('online only and physical only','CONTRADICTORY'),('books under 250 pages','UNSUPPORTED')])
def test_rejected_plan_never_overwrites_or_creates_context(database,query,decision):
    actor={'sub':'2','sid':'v2c-a-safe'};sid=str(uuid4())
    resolve('books about networks',actor,['Fiction'],session_id=sid)
    prior=deepcopy(collection().find_one({'_id':sid}))
    rejected,state=resolve(query,actor,['Fiction'],session_id=sid)
    assert rejected.decision['decision_type']==decision
    assert collection().find_one({'_id':sid})==prior
    fresh=str(uuid4());resolve(query,actor,['Fiction'],session_id=fresh)
    assert not collection().find_one({'_id':fresh})
    valid,_=resolve('online only',actor,['Fiction'],session_id=sid)
    assert valid.semantic_text=='networks' and valid.formats==['ONLINE']

def test_old_scoped_plan_readable_and_new_query_revalidated(database):
    actor={'sub':'2','sid':'old-plan'};sid=str(uuid4())
    resolve('books about networks',actor,[],session_id=sid)
    row=collection().find_one({'_id':sid})
    row['current_plan']={k:v for k,v in row['current_plan'].items() if k not in ('decision','source_spans','constraint_candidates','exclusive_formats','excluded_formats','physical_available_only')}
    row['current_plan']['parser_version']='search-v2a-deterministic-1'
    collection().replace_one({'_id':sid},row)
    restored,_=resolve('',actor,[],session_id=sid)
    assert restored.semantic_text=='networks'
    new,_=resolve('fiction 4',actor,['Fiction'],session_id=sid)
    assert new.decision['decision_type']=='AMBIGUOUS'
    assert collection().find_one({'_id':sid})['current_plan']['semantic_text']=='networks'

def test_global_guard_precedes_retrieval_profile_kg_and_commit(database,monkeypatch):
    database.book_categories.insert_one({'name':'Fiction','count':2})
    forbidden=Mock(side_effect=AssertionError('Rejected query reached expensive or profile IO'))
    engine=SimpleNamespace(books_collection=database.books,search=forbidden)
    monkeypatch.setattr('search.query_execution.global_expansion',forbidden)
    monkeypatch.setattr('search.personalization.safe_profile',forbidden)
    sid=str(uuid4());response=GlobalQuerySearch(engine).search('fiction 4',{'sub':'2','sid':'guard'},session_id=sid,personalized=True,diagnostics=True)
    assert response['results']==[] and response['diagnostics']['provider']=='GUARDED_QUERY'
    assert response['interpretation']['decision']['decision_type']=='AMBIGUOUS'
    assert not collection().find_one({'_id':sid});forbidden.assert_not_called()

def test_authorized_private_guard_and_revocation(query_library,database,monkeypatch):
    lid,_,_,worker,_,_=query_library
    actor={'sub':'2','sid':'private-guard'};sid=str(uuid4())
    first=tenant_search(worker,lid,actor,'books about neural networks',session_id=sid)
    assert first['results']
    prior=deepcopy(collection().find_one({'_id':sid}))
    cache=Mock(side_effect=AssertionError('Guarded plan accessed index'))
    monkeypatch.setattr(worker.cache,'load',cache)
    response=tenant_search(worker,lid,actor,'books rated above 4 and below 3',session_id=sid)
    assert response['results']==[] and response['source']['catalogue_source']=='LIBRARY_LOCAL'
    assert response['interpretation']['decision']['decision_type']=='CONTRADICTORY'
    assert collection().find_one({'_id':sid})==prior;cache.assert_not_called()
    database.institution_memberships.update_one({'library_id':lid,'user_id':2},{'$set':{'status':'REVOKED'}})
    with pytest.raises(HTTPException):tenant_search(worker,lid,actor,'fiction 4',session_id=sid)
    assert not collection().find_one({'_id':sid})

@pytest.mark.parametrize('actor',[{'sub':'3'},{'sub':'9','role':'ADMIN'}])
def test_private_unauthorized_before_vocabulary(query_library,monkeypatch,actor):
    lid,_,_,worker,_,_=query_library
    forbidden=Mock(side_effect=AssertionError('Private vocabulary resolved before authorization'))
    monkeypatch.setattr('backend.services.library_catalogue_experience.subject_rows',forbidden)
    with pytest.raises(HTTPException):tenant_search(worker,lid,actor,'fiction 4')
    forbidden.assert_not_called()

def test_natural_strict_rating_filters_canonical_rows(database,monkeypatch):
    database.book_categories.insert_one({'name':'Fiction','count':3})
    database.books.insert_many([{'work_id':f'OL{i}W','book_id':i,'title':'Fiction fixture','subjects':['Fiction'],'average_rating':rating,'rating_count':2} for i,rating in ((2,3.0),(3,3.01),(4,None))])
    monkeypatch.setattr('backend.services.book_capability_service.with_capabilities',lambda rows:rows)
    engine=SimpleNamespace(books_collection=database.books)
    response=GlobalQuerySearch(engine).search('fiction books above rating of 3',{'sub':'2'})
    assert [b['work_id'] for b in response['results']]==['OL3W']
    assert response['interpretation']['decision']['decision_type']=='EXECUTABLE'

def test_global_unsupported_year_does_not_commit(database):
    engine=SimpleNamespace(books_collection=database.books);sid=str(uuid4())
    response=GlobalQuerySearch(engine).search('books published after 2020',{'sub':'2','sid':'no-year'},session_id=sid)
    assert response['interpretation']['decision']['decision_type']=='UNSUPPORTED'
    assert response['results']==[] and not collection().find_one({'_id':sid})
