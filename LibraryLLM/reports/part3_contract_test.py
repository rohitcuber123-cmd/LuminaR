"""Independent acceptance probes. Failures intentionally expose unmet contracts.

All writes target in-memory fixtures; product code and MongoDB are untouched.
Run: .venv/Scripts/python.exe -m pytest reports/part3_contract_test.py -q
"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException, Header
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('part3_existing_fixtures', ROOT / 'tests/test_assistant_part3.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
from assistant.orchestrator import AssistantOrchestrator
from assistant.schemas import AssistantRequest, AssistantIntent, Intent, Book
from assistant.state import ConversationStore


def setup(intent=Intent.GENERAL_LIBRARY_HELP, items=None):
    qwen = fixtures.FakeQwen(AssistantIntent(intent=intent, confidence=1))
    store = ConversationStore()
    return AssistantOrchestrator(qwen, store), fixtures.FakeTools(items), qwen, store


def chat(orch, tools, message='test', **kwargs):
    return fixtures.run(orch.chat(AssistantRequest(message=message, **kwargs), '17', tools))


def test_pdf_context_beats_stale_search():
    orch, tools, qwen, store = setup(Intent.DOCUMENT_QUESTION)
    state = store.get(None, '17')
    state.last_intent = Intent.SEARCH_BOOKS
    result = chat(orch, tools, 'What does this PDF say about indexing?', conversation_id=state.conversation_id,
                  page_context={'document_id': 'fixture-doc'})
    assert result.intent == Intent.DOCUMENT_QUESTION
    tools.rag.ask.assert_awaited_once()


def test_account_question_beats_stale_search():
    orch, tools, qwen, store = setup(Intent.USER_FEES)
    state = store.get(None, '17')
    state.last_intent = Intent.SEARCH_BOOKS
    result = chat(orch, tools, 'What do I owe?', conversation_id=state.conversation_id)
    assert result.intent == Intent.USER_FEES
    assert result.account['total_unpaid'] == 5


def test_show_more_wire_action_is_valid():
    # The repair contract explicitly forbids intents as actions. The failed
    # audit's original assertion accepted SEARCH_BOOKS, the very broken wire
    # value it discovered. Accept the dedicated action and reject all examples
    # of intent/action confusion; preserve the original in the repair baseline.
    from pydantic import ValidationError
    request = AssistantRequest(message='Show more', action='SHOW_MORE', result_offset=10)
    assert request.action == 'SHOW_MORE'
    for intent in ('SEARCH_BOOKS', 'RECOMMEND_FROM_BOOK', 'RECOMMEND_BOOKS'):
        with pytest.raises(ValidationError):
            AssistantRequest(message='Show more', action=intent, result_offset=10)


def test_alternative_pagination_detects_remaining_results():
    orch, tools, qwen, store = setup()
    books = [Book(work_id=f'OL{i}W', title=f'Book {i}', available_copies=1) for i in range(10,40)]
    tools.recommendation.recommend = AsyncMock(return_value=[b.work_id for b in books])
    tools.catalogue.books = AsyncMock(side_effect=lambda ids: [fixtures.BOOKS.get(i) or next(b for b in books if b.work_id == i) for i in ids])
    result = chat(orch, tools, action='RECOMMEND_AVAILABLE_SIMILAR', selected_work_ids=['OL1W'])
    assert len(result.books) == 10
    assert result.has_more is True


def test_default_recommendations_offer_continuation():
    orch, tools, qwen, store = setup()
    books = [Book(work_id=f'OL{i}W', title=f'Book {i}', available_copies=1) for i in range(10,40)]
    tools.recommendation.recommend = AsyncMock(side_effect=lambda count, seed=None: [b.work_id for b in books[:count]])
    tools.catalogue.books = AsyncMock(side_effect=lambda ids: [next(b for b in books if b.work_id == i) for i in ids])
    result = chat(orch, tools, action='RECOMMEND')
    assert result.has_more is True


def test_explanation_uses_original_seed_when_tray_cleared():
    orch, tools, qwen, store = setup()
    first = chat(orch, tools, action='RECOMMEND_SIMILAR', selected_work_ids=['OL1W'])
    qwen.generate = AsyncMock(return_value='fixture explanation')
    chat(orch, tools, action='EXPLAIN_RECOMMENDATION', conversation_id=first.conversation_id)
    prompt = qwen.generate.call_args.args[0]
    assert "'seeds': [{'title': 'Dracula'" in prompt


def test_explanation_invalidates_previous_mutation_proposal(monkeypatch):
    monkeypatch.setenv('ASSISTANT_MUTATING_ACTIONS_ENABLED', 'true')
    orch, tools, qwen, store = setup(Intent.RESERVE_BOOK)
    proposal = chat(orch, tools, 'reserve this', selected_work_ids=['OL1W'])
    chat(orch, tools, action='EXPLAIN_RECOMMENDATION', conversation_id=proposal.conversation_id)
    result = chat(orch, tools, 'Confirm', action='CONFIRM_ACTION', conversation_id=proposal.conversation_id,
                  pending_action_id=proposal.pending_action.action_id)
    assert result.intent == Intent.CLARIFICATION
    tools.reservations.reserve.assert_not_awaited()


def test_unavailable_book_offers_reserve_and_alternatives():
    orch, tools, qwen, store = setup()
    result = chat(orch, tools, action='CHECK_AVAILABILITY', selected_work_ids=['OL1W'])
    types = {a.type.value for a in result.actions}
    assert 'RECOMMEND_AVAILABLE_SIMILAR' in types
    assert 'RESERVE' in types


def test_reading_list_availability_is_fresh():
    orch, tools, qwen, store = setup(items=[{'work_id':'OL1W','title':'Dracula','available_copies':3,'total_copies':3}])
    result = chat(orch, tools, action='USER_READING_LIST')
    assert result.reading_list[0].available_copies == fixtures.BOOKS['OL1W'].available_copies


def test_reading_list_ids_are_available_to_compare_followup():
    orch, tools, qwen, store = setup(items=[{'work_id':i,'title':b.title} for i,b in list(fixtures.BOOKS.items())[:2]])
    first = chat(orch, tools, action='USER_READING_LIST')
    qwen.intent = AssistantIntent(intent=Intent.COMPARE_BOOKS, confidence=1, ordinal_references=[1,2])
    result = chat(orch, tools, 'Compare the first two', conversation_id=first.conversation_id)
    assert result.intent == Intent.COMPARE_BOOKS
    assert [b.work_id for b in result.comparison.books] == ['OL1W','OL2W']


def test_exact_add_to_reading_list_phrase_uses_canonical_selection():
    orch, tools, qwen, store = setup()
    result = chat(orch, tools, 'add this to my reading list', selected_work_ids=['OL1W'])
    assert result.intent == Intent.ADD_TO_READING_LIST
    assert tools.reading_list.added == ['OL1W']
    assert qwen.calls == []


def test_exact_remove_first_phrase_resolves_owned_reading_list_item():
    orch, tools, qwen, store = setup(items=[{'work_id':'OL1W','title':'Dracula'}])
    first = chat(orch, tools, 'show my reading list')
    qwen.intent = AssistantIntent(intent=Intent.REMOVE_FROM_READING_LIST, confidence=1, ordinal_references=[1])
    result = chat(orch, tools, 'remove the first book from my reading list', conversation_id=first.conversation_id)
    assert result.intent == Intent.REMOVE_FROM_READING_LIST
    assert tools.reading_list.removed == ['OL1W']


def test_search_pages_are_distinct_with_explicit_original_query():
    orch, tools, qwen, store = setup(Intent.SEARCH_BOOKS)
    books = [Book(work_id=f'OL{i}W', title=f'Book {i}', available_copies=1) for i in range(10,40)]
    tools.search.search = AsyncMock(return_value=[b.work_id for b in books])
    tools.catalogue.books = AsyncMock(side_effect=lambda ids: [next(b for b in books if b.work_id == i) for i in ids])
    first = chat(orch, tools, 'Find AI books')
    second = chat(orch, tools, 'Find AI books', result_offset=10, conversation_id=first.conversation_id)
    assert not set(b.work_id for b in first.books) & set(b.work_id for b in second.books)
    assert second.has_more


def test_available_refinement_retains_the_original_search_query():
    from assistant.schemas import Filters
    orch, tools, qwen, store = setup(Intent.SEARCH_BOOKS)
    qwen.intent = AssistantIntent(intent=Intent.SEARCH_BOOKS, confidence=1, query='artificial intelligence')
    first = chat(orch, tools, 'Find books about AI')
    qwen.intent = AssistantIntent(intent=Intent.SEARCH_BOOKS, confidence=1, filters=Filters(available_only=True))
    chat(orch, tools, 'only available ones', conversation_id=first.conversation_id)
    assert tools.search.search.call_args.args[0] == 'artificial intelligence'


def test_due_first_sorts_verified_loans_by_due_date():
    orch, tools, qwen, store = setup(Intent.USER_LOANS)
    tools.loans.loans = AsyncMock(return_value={'count':2,'issues':[
        {'work_id':'OL1W','due_date':'2026-10-10'}, {'work_id':'OL2W','due_date':'2026-10-03'}]})
    result = chat(orch, tools, 'Which one is due first?')
    assert result.account['issues'][0]['work_id'] == 'OL2W'


def test_real_reading_list_routes_use_owned_idempotent_persistence(monkeypatch):
    from backend.routes.reading_list import router
    from backend.dependencies import get_current_user
    from backend.services import reading_list_service as service
    class Cursor(list):
        def sort(self, *args):
            return self
    class Collection:
        rows = []
        def find(self, query):
            return Cursor([dict(r) for r in self.rows if all(r.get(k)==v for k,v in query.items())])
        def update_one(self, query, update, upsert=False):
            if not self.find(query):
                self.rows.append(dict(update['$setOnInsert']))
        def delete_one(self, query):
            for row in self.find(query)[:1]:
                self.rows.remove(row)
    collection = Collection()
    monkeypatch.setattr(service, 'reading_list_collection', collection)
    monkeypatch.setattr(service, 'books_collection', SimpleNamespace(find_one=lambda query: {'work_id':query['work_id'],'book_id':1,'title':'Fixture book','available_copies':1} if query['work_id']=='OL1W' else None))
    def fixture_auth(authorization: str | None = Header(default=None)):
        if authorization not in {'Bearer fixture-17','Bearer fixture-18'}:
            raise HTTPException(401, 'Fixture authentication required')
        return {'sub':authorization.split('-')[-1]}
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = fixture_auth
    with TestClient(app) as client:
        one, two = {'Authorization':'Bearer fixture-17'}, {'Authorization':'Bearer fixture-18'}
        assert client.get('/reading-list/my').status_code == 401
        for _ in range(2):
            assert client.post('/reading-list/', headers=one, json={'work_id':'OL1W'}).status_code == 200
        assert client.get('/reading-list/my', headers=one).json()['count'] == 1
        assert client.get('/reading-list/my', headers=two).json()['count'] == 0
        assert client.post('/reading-list/', headers=one, json={'work_id':'OL_MISSING_W'}).status_code == 404
        assert client.delete('/reading-list/OL1W', headers=two).status_code == 200
        assert client.get('/reading-list/my', headers=one).json()['count'] == 1
        assert client.delete('/reading-list/OL1W', headers=one).status_code == 200
        assert client.get('/reading-list/my', headers=one).json()['count'] == 0
        # Exercise the assistant's actual add/show/remove/clear handlers against
        # the existing Core routes backed only by this in-memory collection.
        orch, tools, qwen, store = setup()
        async def get_list():
            return client.get('/reading-list/my',headers=one).json()
        async def add_book(wid):
            result=client.post('/reading-list/',headers=one,json={'work_id':wid})
            result.raise_for_status()
            return result.json()
        async def remove_book(wid):
            return client.delete('/reading-list/'+wid,headers=one).json()
        async def clear_books(ids):
            for wid in ids:
                await remove_book(wid)
        tools.reading_list=SimpleNamespace(get=get_list,add=add_book,remove=remove_book,clear=clear_books)
        result=chat(orch,tools,action='ADD_TO_READING_LIST',selected_work_ids=['OL1W'])
        assert not result.errors
        shown=chat(orch,tools,action='USER_READING_LIST')
        assert [b.work_id for b in shown.reading_list]==['OL1W']
        chat(orch,tools,action='REMOVE_FROM_READING_LIST',selected_work_ids=['OL1W'])
        assert not chat(orch,tools,action='USER_READING_LIST').reading_list
        chat(orch,tools,action='ADD_TO_READING_LIST',selected_work_ids=['OL1W'])
        chat(orch,tools,action='CLEAR_READING_LIST')
        assert not chat(orch,tools,action='USER_READING_LIST').reading_list
    assert collection.rows == []
