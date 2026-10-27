"""Real isolated Mongo sessions, canonical tenants, revocation and preference scope."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from search.session_store import resolve, clear, collection, invalidate
from search.query_execution import tenant_search, GlobalQuerySearch
from search.personalization import get_profile, invalidate as invalidate_profile
from test_query_v2a import query_library
from test_intelligence import book

ACTOR = {'sub':'2','sid':'v2b-isolated-login'}

@pytest.fixture(autouse=True)
def profile_isolation():
    for user in range(1,15):
        invalidate_profile({'sub':str(user)})

def test_search_session_persistence_replay_expiry_and_clear(database):
    sid = str(uuid4())
    start = datetime.now(timezone.utc)
    def search(q,**kw):return resolve(q,ACTOR,[],session_id=sid,clock=start,**kw)
    first,_ = search('machine learning')
    plan,state = search('online only')
    assert plan.semantic_text == first.semantic_text and plan.formats == ['ONLINE']
    repeated,same = search('online only')
    assert same['version'] == state['version'] and repeated.semantic_text == 'machine learning'
    replay_expiry = datetime.fromisoformat(same['expires_at'])
    assert replay_expiry.utcoffset() == timedelta(0)
    assert abs((replay_expiry-datetime.fromisoformat(state['expires_at'])).total_seconds()) < .001
    restored,restored_state = search('')
    assert restored.semantic_text == 'machine learning' and restored.formats == ['ONLINE']
    assert datetime.fromisoformat(restored_state['expires_at']).utcoffset() == timedelta(0)
    plan,_ = search('rating above 4')
    assert plan.rating_min_exclusive
    plan,_ = search('rating above 4',omit=['format'])
    assert not plan.formats
    expired,_ = resolve('ancient history',ACTOR,[],session_id=sid,clock=start+timedelta(minutes=31))
    assert expired.semantic_text == 'ancient history' and expired.rating_min is None
    clear(sid,ACTOR)
    assert not collection().find_one({'_id':sid})

@pytest.mark.parametrize('foreign',[
    {'sub':'3','sid':'v2b-isolated-login'}, {'sub':'2','sid':'different-login'}
])
def test_search_session_foreign_user_and_login_denied(database,foreign):
    sid = str(uuid4())
    resolve('secret topic',ACTOR,[],session_id=sid)
    with pytest.raises(HTTPException) as error:
        resolve('online only',foreign,[],session_id=sid)
    assert error.value.status_code == 404
    with pytest.raises(HTTPException):
        clear(sid,foreign)

def test_library_a_b_sessions_and_workspaces_separate(database):
    sid = str(uuid4())
    resolve('private local topic',ACTOR,[],session_id=sid,library_id='A',staff=False)
    for library,staff in [('B',False),('A',True),(None,False)]:
        with pytest.raises(HTTPException):
            resolve('online only',ACTOR,[],session_id=sid,library_id=library,staff=staff)
    plan,_ = resolve('',ACTOR,[],session_id=sid,library_id='A')
    assert plan.semantic_text == 'private local topic'

def test_private_search_session_membership_revoked(query_library,database):
    lid,_,_,worker,_,_ = query_library
    sid = str(uuid4())
    first = tenant_search(worker,lid,ACTOR,'books about neural networks',session_id=sid,personalized=True)
    assert first['interpretation']['session']['active']
    database.institution_memberships.update_one({'library_id':lid,'user_id':2},{'$set':{'status':'REVOKED'}})
    with pytest.raises(HTTPException):
        tenant_search(worker,lid,ACTOR,'online only',session_id=sid,personalized=True)
    assert not collection().find_one({'_id':sid})

def test_private_session_outsider_denied_before_resolution(query_library,monkeypatch):
    lid,_,_,worker,_,_ = query_library
    resolve_mock = Mock(side_effect=AssertionError('Outsider reached session'))
    monkeypatch.setattr('search.query_execution.resolve_session',resolve_mock)
    with pytest.raises(HTTPException):
        tenant_search(worker,lid,{'sub':'3'},'books about neural networks',session_id=str(uuid4()),personalized=True)
    resolve_mock.assert_not_called()

def test_private_session_exclusion_overrides_kg_and_personalization(query_library,database):
    lid,row,second,worker,_,_ = query_library
    database.reading_list.insert_one({'user_id':2,'work_id':f'local:{lid}:{second["library_book_id"]}',
        'target_type':'LIBRARY_BOOK','library_id':lid,'library_book_id':second['library_book_id']})
    sid = str(uuid4())
    tenant_search(worker,lid,ACTOR,'books about neural networks',session_id=sid)
    result = tenant_search(worker,lid,ACTOR,'not deep learning',session_id=sid,personalized=True,diagnostics=True)
    assert result['results'] == []
    assert 'Deep learning' not in result['interpretation']['related_concepts']
    assert result['diagnostics']['plan']['semantic_text'] == 'neural networks'

def test_tenant_profile_cannot_enter_global_or_foreign_tenant(query_library,database,library):
    lid,row,second,worker,_,_ = query_library
    database.institution_library_books.update_one({'library_book_id':second['library_book_id']},{'$set':{'subjects':['Private orchids']}})
    database.reading_list.insert_one({'user_id':2,'work_id':f'local:{lid}:{second["library_book_id"]}',
        'target_type':'LIBRARY_BOOK','library_id':lid,'library_book_id':second['library_book_id'],
        'subjects':'FORGED GLOBAL INTEREST'})
    from backend.services.library_catalogue_experience import read_context
    with read_context(lid,ACTOR) as (_,_,canonical):
        profile,_ = get_profile(ACTOR,database.books,library_id=lid,canonical=canonical)
    global_profile,_ = get_profile(ACTOR,database.books)
    assert 'private orchids' in profile.subjects
    assert not global_profile.subjects and 'forged global interest' not in profile.subjects
    other = library(owner=2)
    with read_context(other,ACTOR,staff=True) as (_,_,canonical):
        foreign,_ = get_profile(ACTOR,database.books,library_id=other,staff=True,canonical=canonical)
    assert not foreign.subjects

def test_public_tenant_fallback_preserves_session_and_boundaries(client,library,database):
    lid = library()
    assert client.post(f'/libraries/{lid}/join',headers={'x-test-user':'2'},json={}).status_code == 200
    row = book(client,lid,'Networks primer')
    fallback = SimpleNamespace(cache=SimpleNamespace(load=Mock(side_effect=AssertionError('No index'))))
    actor = {'sub':'2'}
    sid = str(uuid4())
    result = tenant_search(fallback,lid,actor,'networks',session_id=sid,personalized=True,diagnostics=True)
    assert result['results'] and all(b['library_id']==lid for b in result['results'])
    second = tenant_search(fallback,lid,actor,'physical only',session_id=sid,personalized=True)
    assert second['interpretation']['session']['refined']
    assert all(b['has_physical'] for b in second['results'])

def test_global_opt_in_warm_profile_off_and_reason_contract(database,monkeypatch):
    from search import personalization
    monkeypatch.setattr('backend.services.book_capability_service.with_capabilities',lambda rows:rows)
    monkeypatch.setattr('search.query_execution.global_expansion',lambda *a:{'status':'NOT_USED','concepts':[]})
    database.books.insert_one({'work_id':'OL2W','title':'Networks systems','subjects':['Systems'],'average_rating':4.8})
    database.books.update_one({'work_id':'OL1W'},{'$set':{'title':'Networks primer','subjects':['Other'],'average_rating':4.5}})
    database.reading_list.insert_one({'user_id':2,'work_id':'OL2W','target_type':'GLOBAL_WORK','subjects':'Malicious snapshot'})
    engine = SimpleNamespace(books_collection=database.books,
        search=Mock(return_value={'results':[{'work_id':'OL1W','rerank_score':.01},{'work_id':'OL2W','rerank_score':.009}],'diagnostics':{}}))
    search = GlobalQuerySearch(engine)
    off = search.search('books about networks',ACTOR,personalized=False)
    on = search.search('books about networks',ACTOR,personalized=True,diagnostics=True)
    warm = search.search('books about networks',ACTOR,personalized=True,diagnostics=True)
    assert [r['work_id'] for r in off['results']] == ['OL1W','OL2W']
    assert [r['work_id'] for r in on['results']] == ['OL2W','OL1W']
    assert warm['diagnostics']['profile']['cache'] == 'HIT'
    assert 'Systems' in on['results'][0]['search_reasons'][0]
    assert not any('Reading List' in r for book in off['results'] for r in book['search_reasons'])
    assert all('rerank_score' not in b and 'hnsw_score' not in b for b in on['results'])

def test_empty_public_tenant_session_never_becomes_global_filler(client,library):
    lid=library()
    assert client.post(f'/libraries/{lid}/join',headers={'x-test-user':'2'},json={}).status_code==200
    fallback=SimpleNamespace(cache=SimpleNamespace(load=Mock(side_effect=AssertionError('No index'))))
    result=tenant_search(fallback,lid,{'sub':'2'},'networks',session_id=str(uuid4()),personalized=True)
    assert result['source']['catalogue_source']=='LIBRARY_LOCAL' and result['results']==[]

def test_logout_context_clear_is_user_scoped_and_preserves_saved_books(client,database):
    own,foreign=str(uuid4()),str(uuid4())
    resolve('networks',{'sub':'2'},[],session_id=own)
    resolve('literature',{'sub':'3'},[],session_id=foreign)
    database.reading_list.insert_one({'user_id':2,'work_id':'OL1W'})
    response=client.delete('/search-context',headers={'x-test-user':'2'})
    assert response.status_code==200 and response.json()['cleared']
    assert not collection().find_one({'_id':own}) and collection().find_one({'_id':foreign})
    assert database.reading_list.count_documents({'user_id':2})==1
