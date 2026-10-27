"""Scoped include/exclude rejection, real Mongo state and existing retrieval guards."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from search.query_execution import GlobalQuerySearch, tenant_search
from search.query_plan import parse_query
from search.session_store import clear, collection, resolve
from test_query_v2a import query_library


def test_global_contradiction_preserves_context_and_skips_retrieval(database, monkeypatch):
    actor = {'sub':'2','sid':'a1-global'}
    database.book_categories.insert_many([{'name':'Fiction','count':2},{'name':'Romance','count':1}])
    sid = str(uuid4())
    resolve('books about wizards', actor, ['Fiction','Romance'], session_id=sid)
    prior = deepcopy(collection().find_one({'_id':sid}))
    forbidden = Mock(side_effect=AssertionError('Rejected input reached retrieval/profile'))
    engine = SimpleNamespace(books_collection=database.books, search=forbidden)
    monkeypatch.setattr('search.query_execution.global_expansion', forbidden)
    monkeypatch.setattr('search.personalization.safe_profile', forbidden)
    result = GlobalQuerySearch(engine).search('include Romance but exclude Romance', actor,
        session_id=sid, personalized=True, diagnostics=True)
    assert result['interpretation']['decision']['decision_type'] == 'CONTRADICTORY'
    assert result['results'] == [] and result['diagnostics']['provider'] == 'GUARDED_QUERY'
    assert collection().find_one({'_id':sid}) == prior
    forbidden.assert_not_called()
    p,_ = resolve('rating above 3', actor, ['Fiction','Romance'], session_id=sid)
    assert p.semantic_text == 'wizards' and p.rating_min == 3 and p.rating_min_exclusive
    clear(sid, actor)
    p,_ = resolve('include Fiction but exclude Romance', actor, ['Fiction','Romance'], session_id=sid)
    assert p.subjects == ['Fiction'] and p.exclude_subjects == ['Romance'] and p.semantic_text is None


@pytest.fixture
def indexed_work_ids(database):
    name=database.books.create_index('work_id')
    yield
    database.books.drop_index(name)


def test_multi_subject_global_uses_rarest_bounded_ids_and_all_predicates(database,monkeypatch,indexed_work_ids):
    database.book_categories.insert_many([{'name':'Fiction','count':400000},{'name':'Mystery','count':4000}])
    database.books.insert_many([
        {'work_id':'OL2W','book_id':2,'title':'Both','subjects':'Fiction|Mystery'},
        {'work_id':'OL3W','book_id':3,'title':'Only mystery','subjects':'Mystery'}])
    candidates=Mock(return_value=['OL2W','OL3W'])
    monkeypatch.setattr('search.structured_subjects.candidate_ids',candidates)
    monkeypatch.setattr('backend.services.book_capability_service.with_capabilities',lambda rows:rows)
    engine=SimpleNamespace(books_collection=database.books)
    result=GlobalQuerySearch(engine).search('include Fiction and Mystery',{'sub':'2'})
    candidates.assert_called_once_with('Mystery',1000)
    assert [r['work_id'] for r in result['results']]==['OL2W']
    candidates.return_value=None
    with pytest.raises(HTTPException) as error:
        GlobalQuerySearch(engine).search('include Fiction and Mystery',{'sub':'2'})
    assert error.value.status_code==503


@pytest.mark.parametrize('staff', [False,True])
def test_private_canonical_clause_session_pipeline(query_library, database, monkeypatch, staff):
    lid,_,_,worker,_,_ = query_library
    actor = {'sub':'1' if staff else '2', 'sid':'a1-private-'+str(staff)}
    sid = str(uuid4())
    tenant_search(worker,lid,actor,'books about neural networks',staff=staff,session_id=sid)
    prior = deepcopy(collection().find_one({'_id':sid}))
    with monkeypatch.context() as patch:
        forbidden = Mock(side_effect=AssertionError('Contradiction reached tenant index'))
        patch.setattr(worker.cache,'load',forbidden)
        result = tenant_search(worker,lid,actor,'include Romance but exclude Romance',staff=staff,session_id=sid)
        assert result['results'] == []
        assert result['interpretation']['decision']['decision_type'] == 'CONTRADICTORY'
        assert collection().find_one({'_id':sid}) == prior
        forbidden.assert_not_called()
    result = tenant_search(worker,lid,actor,'rating above 3',staff=staff,session_id=sid)
    assert result['interpretation']['session']['refined']
    assert any(c['label']=='Topic: neural networks' for c in result['interpretation']['chips'])
    assert all(r['library_id']==lid for r in result['results'])
    clear(sid,actor,lid,staff)
    assert not collection().find_one({'_id':sid})


@pytest.mark.parametrize('actor', [{'sub':'3','sid':'outsider'}, {'sub':'9','role':'ADMIN','sid':'platform'}])
def test_private_clause_vocabulary_not_read_before_auth(query_library,monkeypatch,actor):
    lid,_,_,worker,_,_ = query_library
    forbidden=Mock(side_effect=AssertionError('Unauthorized vocabulary read'))
    monkeypatch.setattr('backend.services.library_catalogue_experience.subject_rows', forbidden)
    with pytest.raises(HTTPException):
        tenant_search(worker,lid,actor,'include Private Orchid but exclude Private Orchid')
    forbidden.assert_not_called()


def test_revocation_precedes_contradiction_resolution(query_library,database,monkeypatch):
    lid,_,_,worker,_,_=query_library
    actor={'sub':'2','sid':'a1-revoked'};sid=str(uuid4())
    tenant_search(worker,lid,actor,'books about neural networks',session_id=sid)
    database.institution_memberships.update_one({'library_id':lid,'user_id':2},{'$set':{'status':'REVOKED'}})
    forbidden=Mock(side_effect=AssertionError('Revoked vocabulary read'))
    monkeypatch.setattr('backend.services.library_catalogue_experience.subject_rows',forbidden)
    with pytest.raises(HTTPException):
        tenant_search(worker,lid,actor,'include Romance but exclude Romance',session_id=sid)
    assert not collection().find_one({'_id':sid})
    forbidden.assert_not_called()


def test_missing_tenant_subject_not_imported_from_global(query_library):
    lid,_,_,worker,_,_=query_library
    result=tenant_search(worker,lid,{'sub':'2'},'include Fiction but exclude Fiction')
    assert result['interpretation']['decision']['decision_type']=='UNSUPPORTED'
    assert not any(c['key']=='subject' for c in result['interpretation']['chips'])
    assert result['results']==[]


@pytest.mark.parametrize('staff',[False,True])
def test_public_session_clause_guard(client,library,database,staff):
    from test_intelligence import book,encoder,build
    from search.library_intelligence import TenantIntelligence
    lid=library(private=False)
    assert client.post(f'/libraries/{lid}/join',headers={'x-test-user':'2'},json={}).status_code==200
    row=book(client,lid,'Wizards Fiction primer',linked=True)
    database.institution_library_books.update_one({'library_book_id':row['library_book_id']},{'$set':{'subjects':['Fiction','Romance']}})
    worker=TenantIntelligence(encoder,lambda pairs:[1.]*len(pairs),model_version='all-MiniLM-L6-v2:unit')
    build(lid,worker=worker)
    actor={'sub':'1' if staff else '2','sid':'a1-public-'+str(staff)};sid=str(uuid4())
    tenant_search(worker,lid,actor,'books about wizards',staff=staff,session_id=sid)
    prior=deepcopy(collection().find_one({'_id':sid}))
    result=tenant_search(worker,lid,actor,'include Romance but exclude Romance',staff=staff,session_id=sid)
    assert result['interpretation']['decision']['decision_type']=='CONTRADICTORY'
    assert result['results']==[] and collection().find_one({'_id':sid})==prior
    result=tenant_search(worker,lid,actor,'physical only',staff=staff,session_id=sid)
    assert result['interpretation']['session']['refined']
    assert any(c['label']=='Topic: wizards' for c in result['interpretation']['chips'])
    clear(sid,actor,lid,staff)
    assert not collection().find_one({'_id':sid})
