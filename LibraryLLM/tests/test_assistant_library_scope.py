"""Deterministic adapter/security checks; no model-accuracy claim or live writes."""
import asyncio
import json
from types import SimpleNamespace
from uuid import UUID
import httpx
import pytest
from fastapi import HTTPException
from assistant.state import ConversationStore
from assistant.library_scope import LibraryCatalogue, LibrarySearch, LibraryRecommendations, LibraryTransport
from assistant.tools import ServiceTransport, ToolFailure

A='11111111-1111-4111-8111-111111111111'
B='22222222-2222-4222-8222-222222222222'
ID='33333333-3333-4333-8333-333333333333'
def run(coro):return asyncio.run(coro)

@pytest.mark.parametrize('original,target',[('GLOBAL','LIBRARY:'+A),('LIBRARY:'+A,'GLOBAL'),('LIBRARY:'+A,'LIBRARY:'+B)])
def test_conversations_cannot_change_scope(original,target):
    store=ConversationStore();state=store.get(None,'owner:session',original)
    with pytest.raises(HTTPException) as error:store.get(state.conversation_id,'owner:session',target)
    assert error.value.status_code==404
    assert store.get(state.conversation_id,'owner:session',original) is state

@pytest.mark.parametrize('owner',['other:session','owner:new-session'])
def test_scope_does_not_replace_owner_authority(owner):
    store=ConversationStore();state=store.get(None,'owner:session','LIBRARY:'+A)
    with pytest.raises(HTTPException):store.get(state.conversation_id,owner,'LIBRARY:'+A)

def row(**changes):return {'library_id':A,'library_book_id':ID,'global_work_id':None,'source':'LIBRARY',
    'owned_by_current_library':True,'title':'Fresh local Python','authors':['Local Author'],
    'availability':{'requestable':0,'total':2},**changes}

def test_local_only_book_identity_and_authoritative_unavailability():
    book=LibraryCatalogue(None,A).project(row())
    assert book.work_id==ID and book.library_book_id==ID and book.global_work_id is None
    assert book.available_copies==0 and book.total_copies==2

@pytest.mark.parametrize('change',[{'library_id':B},{'source':'GLOBAL'},{'owned_by_current_library':False}])
def test_foreign_tool_outputs_fail_before_model_input(change):
    with pytest.raises(ToolFailure):LibraryCatalogue(None,A).project(row(**change))

@pytest.mark.parametrize('service,path',[('core','/books/OL1W'),('core',f'/libraries/{B}/catalogue/books'),
    ('search','/search'),('core','/reading-list/my'),('core','/issues/issue')])
def test_scoped_transport_has_no_global_or_foreign_escape(service,path):
    with pytest.raises(ToolFailure):run(LibraryTransport(None,A).call(service,'GET',path))

def test_search_projects_local_ids_and_never_falls_back_to_global():
    calls=[]
    class Transport:
        async def call(self,service,method,path,**kwargs):
            calls.append((service,method,path,kwargs));return {'results':[row()]}
    catalogue=LibraryCatalogue(Transport(),A)
    assert run(LibrarySearch(catalogue).search('Python',10))==[ID]
    assert calls[0][0]=='search' and calls[0][2]==f'/libraries/{A}/catalogue/search'

def test_empty_library_is_truthfully_empty():
    class Transport:
        async def call(self,*args,**kwargs):return {'results':[]}
    assert run(LibrarySearch(LibraryCatalogue(Transport(),A)).search('Python',10))==[]

def test_recommendations_reuse_existing_intersection_and_local_supplement():
    calls=[]
    class Raw:
        async def call(self,*args,**kwargs):return {'recommendations':[{'work_id':'OL9W'}]}
    class Core:
        async def call(self,service,method,path,**kwargs):
            calls.append((path,kwargs));return {'results':[row()]}
    assert run(LibraryRecommendations(LibraryCatalogue(Core(),A),Raw()).recommend(5))==[ID]
    assert calls==[(f'/libraries/{A}/catalogue/recommendations',{'json':{'work_ids':['OL9W'],'limit':5}})]

def test_global_provider_failure_keeps_local_acquisition_supplement():
    class Raw:
        async def call(self,*args,**kwargs):raise ToolFailure('recommendation')
    class Core:
        async def call(self,*args,**kwargs):
            assert kwargs['json']['work_ids']==[];return {'results':[row()]}
    assert run(LibraryRecommendations(LibraryCatalogue(Core(),A),Raw()).recommend(5))==[ID]

def test_semantic_service_failure_reuses_authorized_catalogue_fallback():
    calls=[]
    class Transport:
        async def call(self,service,method,path,**kwargs):
            calls.append((service,path))
            if service=='search':raise ToolFailure('search','HTTP_503')
            return {'results':[row()]}
    assert run(LibrarySearch(LibraryCatalogue(Transport(),A)).search('Python',10))==[ID]
    assert calls==[('search',f'/libraries/{A}/catalogue/search'),('core',f'/libraries/{A}/catalogue/discovery')]

def test_bound_private_tools_cannot_be_reused_as_global_tools():
    from assistant.orchestrator import AssistantOrchestrator
    from assistant.schemas import AssistantRequest
    tools=SimpleNamespace(effective_scope='LIBRARY:'+A)
    with pytest.raises(HTTPException) as error:
        run(AssistantOrchestrator(None,ConversationStore()).chat(AssistantRequest(message='Global search'),'owner',tools))
    assert error.value.status_code==404

@pytest.mark.parametrize('foreign',[False,True])
def test_ready_graph_rehydrates_every_candidate_in_current_library(foreign):
    from assistant.library_scope import LibraryGraph
    neighbor='44444444-4444-4444-8444-444444444444'
    class Transport:
        staff=False
        async def call(self,service,method,path,**kwargs):
            if path.endswith('/intelligence/graph'):
                return {'library_id':A,'status':'READY','generation_id':'owned-generation',
                    'nodes':[{'id':'seed','type':'Book','library_book_id':ID},{'id':'other','type':'Book','library_book_id':neighbor}],
                    'edges':[{'source':'seed','target':'subject-python'},{'source':'other','target':'subject-python'}]}
            identity=path.rsplit('/',1)[-1]
            return {'book':row(library_book_id=identity,library_id=B if foreign and identity==neighbor else A)}
    graph=LibraryGraph(LibraryCatalogue(Transport(),A))
    if foreign:
        with pytest.raises(ToolFailure):run(graph.more_like_this(ID))
    else:
        value=run(graph.more_like_this(ID))
        assert value['source']=='TENANT_KG' and len(value['recommendations'])==1
        assert value['recommendations'][0]['work_id']==neighbor
        assert value['recommendations'][0]['score']==1
