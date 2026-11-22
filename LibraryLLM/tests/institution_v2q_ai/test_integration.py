"""Real Core ASGI/Mongo authority and production assistant; deterministic parser."""
from uuid import uuid4
from threading import RLock
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials
import httpx
import pytest
from backend.database.mongodb import db
from backend.dependencies import get_current_user,security
from assistant.api import install_assistant
from assistant.schemas import AssistantIntent,Intent

class Parser:
    async def parse(self,message,context):
        if message.startswith('Is the first'):return AssistantIntent(intent=Intent.CHECK_AVAILABILITY,reference='this',ordinal_references=[1],confidence=1)
        return AssistantIntent(intent=Intent.SEARCH_BOOKS,query='UnfindableFixtureTerm' if message.startswith('Find impossible') else 'Python',confidence=1)
    async def respond(self,message,response):return 'Grounded fixture response.'
    async def generate(self,*args,**kwargs):return 'Fixture explanation.'

@pytest.fixture
def fixture(client):
    libraries=[];books=[]
    for letter in ['A','B']:
        response=client.post('/libraries/register',json={'name':'AI Scope '+letter,'slug':'ai-'+uuid4().hex,'library_type':'PRIVATE_INSTITUTION' if letter=='A' else 'PUBLIC_LIBRARY','access_mode':'PRIVATE_CODE' if letter=='A' else 'PUBLIC',**({'access_code':'Disposable fixture secret'} if letter=='A' else {})})
        assert response.status_code==201,response.text
        lib=response.json()['library']['library_id'];libraries.append(lib)
        assert client.post(f'/libraries/{lib}/join',headers={'x-test-user':'2'},json={'access_code':'Disposable fixture secret'} if letter=='A' else {}).status_code==200
        row=client.post(f'/libraries/{lib}/inventory/books',json={'title':letter+' Local Python','authors':['Ada'],'subjects':['Python'],'copies':2,'idempotency_key':str(uuid4())})
        assert row.status_code==201,row.text
        books.append(row.json()['library_book_id'])
    api=FastAPI();install_assistant(api,SimpleNamespace(llm=SimpleNamespace(),inference_lock=RLock()),None,None)
    api.state.assistant.qwen=Parser()
    calls=[]
    def core(request):
        calls.append(request.url.path)
        if request.url.port==8003:return httpx.Response(503,json={'detail':'Owned semantic-unavailable fixture'})
        if request.url.port==8004:return httpx.Response(200,json={'recommendations':[{'work_id':'OL999W'}]})
        response=client.request(request.method,request.url.path+('?' + request.url.query.decode() if request.url.query else ''),headers={'x-test-user':str(getattr(api.state,'fixture_user',2)),**({'content-type':request.headers['content-type']} if 'content-type' in request.headers else {})},content=request.content)
        if getattr(api.state,'flip_membership_role',False) and '/catalogue/books/' in request.url.path:
            db.institution_memberships.update_one({'library_id':libraries[0],'user_id':2},{'$set':{'role':'LIBRARIAN'}})
            api.state.flip_membership_role=False
        return httpx.Response(response.status_code,content=response.content,headers={'content-type':'application/json'})
    api.state.assistant_http_client._transport=httpx.MockTransport(core)
    api.dependency_overrides[get_current_user]=lambda:{'sub':str(getattr(api.state,'fixture_user',2)),'sid':'scope-fixture'}
    api.dependency_overrides[security]=lambda:HTTPAuthorizationCredentials(scheme='Bearer',credentials='owned-fixture')
    with TestClient(api) as assistant:yield assistant,libraries,books,calls

def chat(fixture,library=None,**body):
    api,libs,books,calls=fixture
    return api.post('/assistant/chat',json={'message':'Find Python books',**({'library_id':library} if library else {}),**body})

@pytest.mark.parametrize('index',[0,1])
def test_real_tenant_search_and_local_ids(fixture,index):
    response=chat(fixture,fixture[1][index]);assert response.status_code==200,response.text
    data=response.json();assert data['books'] and not data['errors'],data
    assert {b['work_id'] for b in data['books']}=={fixture[2][index]}
    assert all(b['library_id']==fixture[1][index] for b in data['books'])
    assert all(b['available_copies']==2 for b in data['books'])

@pytest.mark.parametrize('index',[0,1])
def test_real_for_you_local_supplement(fixture,index):
    response=chat(fixture,fixture[1][index],action='RECOMMEND');assert response.status_code==200,response.text
    data=response.json();assert data['books'] and not data['errors'],data
    assert {b['library_book_id'] for b in data['books']}=={fixture[2][index]}
    assert not any(b['work_id']=='OL999W' for b in data['books'])


def test_pick_one_local_book_cold_start_and_scoped_followup(fixture):
    from assistant.schemas import AssistantIntentDecision, ReferenceScope

    class PickParser(Parser):
        async def parse(self, message, context):
            if message.startswith('Pick'):
                return AssistantIntentDecision(intent=Intent.RECOMMEND_BOOKS, confidence=1)
            return AssistantIntentDecision(intent=Intent.BOOK_DETAILS, confidence=1,
                reference_scope=ReferenceScope.PREVIOUS_RECOMMENDATIONS, reference_position='FOCUS')

    api, libraries, books, _ = fixture
    api.app.state.assistant.qwen = PickParser()
    result = chat(fixture, libraries[0], message='Pick a book for me.')
    assert result.status_code == 200
    picked = result.json()
    assert not picked['errors'] and not picked['pending_action']
    assert [book['library_book_id'] for book in picked['books']] == [books[0]]
    assert picked['books'][0]['global_work_id'] is None
    assert not picked['has_more']
    followup = {'message': 'Tell me about your selection.', 'conversation_id': picked['conversation_id']}
    details = chat(fixture, libraries[0], **followup)
    assert details.status_code == 200
    assert [book['library_book_id'] for book in details.json()['books']] == [books[0]]
    assert chat(fixture, libraries[1], **followup).status_code == 404

@pytest.mark.parametrize('destination',['foreign','global'])
def test_http_conversation_cross_scope_denied(fixture,destination):
    first=chat(fixture,fixture[1][0]);assert first.status_code==200,first.text
    response=chat(fixture,fixture[1][1] if destination=='foreign' else None,conversation_id=first.json()['conversation_id'])
    assert response.status_code==404,response.text
    assert fixture[2][0] not in response.text

def test_revocation_denies_existing_conversation(fixture):
    first=chat(fixture,fixture[1][0]);assert first.status_code==200
    db.institution_memberships.update_one({'library_id':fixture[1][0],'user_id':2},{'$set':{'status':'REMOVED'}})
    response=chat(fixture,fixture[1][0],conversation_id=first.json()['conversation_id'])
    assert response.status_code==404 and fixture[2][0] not in response.text

def test_foreign_book_reference_cannot_load_metadata(fixture):
    response=chat(fixture,fixture[1][0],action='CHECK_AVAILABILITY',selected_work_ids=[fixture[2][1]])
    assert response.status_code==200,response.text
    assert not response.json()['books'] and fixture[2][1] not in str(response.json()['availability'])

def test_forged_circulation_context_rejected(fixture):
    response=chat(fixture,fixture[1][0],lending_context={'library_id':fixture[1][1]})
    assert response.status_code==404

def test_followup_uses_current_library_result_mapping(fixture):
    first=chat(fixture,fixture[1][0]);assert first.status_code==200
    second=chat(fixture,fixture[1][0],message='Is the first book available?',conversation_id=first.json()['conversation_id'])
    assert second.status_code==200,second.text
    data=second.json();assert not data['errors'],data
    assert data['availability'][0]['work_id']==fixture[2][0]
    assert data['availability'][0]['available_copies']==2

def test_foreign_asset_is_denied_before_rag_callback(fixture):
    response=chat(fixture,fixture[1][0],action='DOCUMENT_QUESTION',page_context={'document_id':f'library:{fixture[1][1]}:asset:{uuid4()}'})
    assert response.status_code==200,response.text
    assert any(e['code']=='SCOPED_DOCUMENT_REQUIRED' for e in response.json()['errors'])

def test_revocation_during_model_routing_cannot_release_results(fixture):
    class RevokingParser(Parser):
        async def parse(self,message,context):
            db.institution_memberships.update_one({'library_id':fixture[1][0],'user_id':2},{'$set':{'status':'REMOVED'}})
            return await super().parse(message,context)
    fixture[0].app.state.assistant.qwen=RevokingParser()
    response=chat(fixture,fixture[1][0]);assert response.status_code==404,response.text
    assert 'Local Python' not in response.text

def test_scoped_reading_list_add_confirm_and_visibility(fixture):
    lib=fixture[1][0];identity=fixture[2][0]
    proposal=chat(fixture,lib,action='ADD_TO_READING_LIST',selected_work_ids=[identity])
    assert proposal.status_code==200,proposal.text
    pending=proposal.json()['pending_action'];assert pending
    confirmed=chat(fixture,lib,conversation_id=proposal.json()['conversation_id'],action='CONFIRM_ACTION',pending_action_id=pending['action_id'])
    assert confirmed.status_code==200 and not confirmed.json()['errors'],confirmed.text
    own=chat(fixture,lib,action='USER_READING_LIST');assert own.status_code==200,own.text
    assert [row['work_id'] for row in own.json()['reading_list']]==[identity],own.text
    other=chat(fixture,fixture[1][1],action='USER_READING_LIST')
    assert other.status_code==200 and other.json()['reading_list']==[],other.text

def test_not_built_graph_does_not_expand_global_or_trigger_build(fixture):
    response=chat(fixture,fixture[1][0],action='MORE_LIKE_THIS',selected_work_ids=[fixture[2][0]])
    assert response.status_code==200,response.text
    assert not response.json()['books']
    assert any(e['code']=='TENANT_GRAPH_UNAVAILABLE' for e in response.json()['errors']),response.text
    assert not any('/builds' in path for path in fixture[3])

def test_saved_public_reference_only_survives_when_owned_here(fixture):
    lib=fixture[1][0];identity=fixture[2][0]
    db.books.insert_one({'work_id':'OL42W','book_id':42,'title':'Public reference','authors':'Ada','total_copies':999,'available_copies':999})
    db.institution_library_books.update_one({'library_id':lib,'library_book_id':identity},{'$set':{'global_work_id':'OL42W'}})
    db.reading_list.insert_one({'user_id':2,'work_id':'OL42W','target_type':'GLOBAL_WORK'})
    own=chat(fixture,lib,action='USER_READING_LIST');assert own.status_code==200,own.text
    rows=own.json()['reading_list'];assert len(rows)==1,own.text
    assert rows[0]['work_id']==identity and rows[0]['available_copies']==2
    other=chat(fixture,fixture[1][1],action='USER_READING_LIST');assert other.status_code==200 and not other.json()['reading_list'],other.text

def test_single_local_seed_does_not_pad_similar_results(fixture):
    response=chat(fixture,fixture[1][0],action='RECOMMEND_SIMILAR',selected_work_ids=[fixture[2][0]])
    assert response.status_code==200,response.text
    assert not response.json()['errors'],response.text
    assert not response.json()['books']

def test_role_change_after_metadata_lookup_suppresses_response(fixture):
    fixture[0].app.state.flip_membership_role=True
    response=chat(fixture,fixture[1][0])
    assert response.status_code==404,response.text
    assert 'Local Python' not in response.text

@pytest.mark.parametrize('count',[1,5,20])
def test_small_collections_and_pagination_remain_owned(fixture,count):
    lib=fixture[1][0]
    from backend.main import app
    core=TestClient(app)
    for number in range(1,count):
        response=core.post(f'/libraries/{lib}/inventory/books',json={'title':f'A Python acquisition {number}','authors':['Ada'],'subjects':['Python'],'copies':2,'idempotency_key':str(uuid4())})
        assert response.status_code==201,response.text
    first=chat(fixture,lib,action='RECOMMEND');assert first.status_code==200,first.text
    rows=first.json()['books'];assert len(rows)==min(count,10),first.text
    assert all(row['library_id']==lib for row in rows)
    if count>10:
        second=chat(fixture,lib,action='SHOW_MORE',conversation_id=first.json()['conversation_id'],result_offset=10)
        assert second.status_code==200,second.text
        assert len(second.json()['books'])==10,second.text
        assert not {row['work_id'] for row in rows}&{row['work_id'] for row in second.json()['books']}
    core.close()

def test_no_matching_local_books_never_substitutes_global(fixture):
    response=chat(fixture,fixture[1][0],message='Find impossible topic')
    assert response.status_code==200,response.text
    assert response.json()['books']==[] and not response.json()['errors'],response.text

def test_empty_collection_for_you_is_truthfully_empty(fixture):
    db.institution_library_books.update_many({'library_id':fixture[1][0]},{'$set':{'status':'WITHDRAWN'}})
    response=chat(fixture,fixture[1][0],action='RECOMMEND')
    assert response.status_code==200,response.text
    assert not response.json()['books'] and not response.json()['errors'],response.text

def test_sparse_seed_does_not_invent_similarity(fixture):
    db.institution_library_books.update_one({'library_id':fixture[1][0]},{'$set':{'subjects':[],'authors':[]}})
    response=chat(fixture,fixture[1][0],action='RECOMMEND_SIMILAR',selected_work_ids=[fixture[2][0]])
    assert response.status_code==200,response.text
    assert not response.json()['books'] and not response.json()['errors'],response.text

def test_member_in_a_only_cannot_discover_b(fixture):
    from backend.main import app
    core=TestClient(app)
    joined=core.post(f'/libraries/{fixture[1][0]}/join',headers={'x-test-user':'3'},json={'access_code':'Disposable fixture secret'})
    assert joined.status_code==200,joined.text
    fixture[0].app.state.fixture_user=3
    assert chat(fixture,fixture[1][0]).status_code==200
    foreign=chat(fixture,fixture[1][1]);assert foreign.status_code==404,foreign.text
    assert 'B Local Python' not in foreign.text
    core.close()

def test_foreign_owner_cannot_read_same_library_conversation(fixture):
    first=chat(fixture,fixture[1][0]);assert first.status_code==200
    db.institution_memberships.insert_one({'membership_id':str(uuid4()),'library_id':fixture[1][0],'user_id':3,'role':'GENERAL_USER','status':'ACTIVE'})
    fixture[0].app.state.fixture_user=3
    response=chat(fixture,fixture[1][0],conversation_id=first.json()['conversation_id'])
    assert response.status_code==404 and 'A Local Python' not in response.text

def test_matching_asset_scope_calls_existing_callback(fixture):
    asset=str(uuid4());calls=[]
    def ask(library_id,asset_id,actor,message,mode):
        calls.append((library_id,asset_id,actor['sub'],mode))
        return {'answer':'Authorized callback fixture','sources':[]}
    fixture[0].app.state.library_assets=SimpleNamespace(ask=ask)
    response=chat(fixture,fixture[1][0],action='DOCUMENT_QUESTION',page_context={'document_id':f'library:{fixture[1][0]}:asset:{asset}'})
    assert response.status_code==200 and not response.json()['errors'],response.text
    assert calls==[(fixture[1][0],asset,'2','normal')]


def test_ready_graph_through_real_core_projection(fixture,monkeypatch,client):
    from backend.services import library_intelligence_service as intelligence
    lib=fixture[1][0];seed=fixture[2][0]
    acquired=client.post(f'/libraries/{lib}/inventory/books',json={'title':'A Python graph neighbor','subjects':['Python'],'copies':1,'idempotency_key':str(uuid4())})
    assert acquired.status_code==201,acquired.text
    other=acquired.json()['library_book_id']
    payload={'nodes':[{'id':'seed','type':'Book','label':'A Local Python','library_book_id':seed},
                      {'id':'other','type':'Book','label':'A Python graph neighbor','library_book_id':other},
                      {'id':'python','type':'Subject','label':'Python'}],
             'edges':[{'source':'seed','target':'python'},{'source':'other','target':'python'}]}
    monkeypatch.setattr(intelligence,'target_status',lambda *args:{'status':'READY','active_generation_id':'owned-graph-fixture','manifest_checksum':'owned-fixture'})
    monkeypatch.setattr(intelligence.graph_cache,'load',lambda *args:({},[],payload))
    response=chat(fixture,lib,action='MORE_LIKE_THIS',selected_work_ids=[seed])
    assert response.status_code==200,response.text
    data=response.json();assert not data['errors'],data
    assert [row['library_book_id'] for row in data['books']]==[other],data
    assert data['books'][0]['library_id']==lib


@pytest.mark.parametrize('role',['ADMIN','LIBRARIAN'])
@pytest.mark.parametrize('action',[None,'RECOMMEND'])
def test_staff_scope_uses_current_server_role(fixture,role,action):
    lib=fixture[1][0]
    db.institution_memberships.update_one({'library_id':lib,'user_id':2},{'$set':{'role':role}})
    response=chat(fixture,lib,**({'action':action} if action else {}))
    assert response.status_code==200,response.text
    data=response.json();assert not data['errors'],data
    assert [row['library_book_id'] for row in data['books']]==[fixture[2][0]],data
    assert all(row['library_id']==lib for row in data['books'])
