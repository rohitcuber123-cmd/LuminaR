"""Assistant contract tests: fake Qwen/tools, real adapters, no live data mutation."""
import asyncio
import ast
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, RLock
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import httpx
import pytest

from assistant.api import install_assistant
from assistant.orchestrator import AssistantOrchestrator, merge_ranks
from assistant.qwen import AssistantDecodingSchema, QwenGateway, QwenUnavailable
from assistant.schemas import (AssistantIntent, AssistantRequest, Book, Filters, Intent,
                               RecommendationMode)
from assistant.state import ConversationStore
from assistant.tools import AssistantTools, ServiceTransport, ToolFailure
from backend.dependencies import get_current_user

ROOT = Path(__file__).resolve().parents[1]
BOOKS = {
    'OL1W': Book(work_id='OL1W', title='Dracula', authors='Bram Stoker', subjects='Gothic', available_copies=0, total_copies=2),
    'OL2W': Book(work_id='OL2W', title='Frankenstein', authors='Mary Shelley', subjects='Gothic', available_copies=1, total_copies=1),
    'OL3W': Book(work_id='OL3W', title='The Time Machine', authors='H. G. Wells', available_copies=2, total_copies=3),
    'OL4W': Book(work_id='OL4W', title='The Invisible Man', authors='H. G. Wells', available_copies=0),
}


def run(coro):
    return asyncio.run(coro)


class FakeQwen:
    def __init__(self, intent):
        self.intent = intent
        self.calls = []

    async def parse(self, message, context):
        self.calls.append(context)
        return self.intent.model_copy(deep=True)

    async def respond(self, message, response):
        return 'Explanation based on verified results.'


class FakeTools:
    def __init__(self):
        self.calls = []
        self.search = SimpleNamespace(search=AsyncMock(return_value=['OL1W', 'OL2W']))
        self.catalogue = SimpleNamespace(book=self.book, books=self.books, resolve=self.resolve)
        self.recommendation = SimpleNamespace(recommend=self.recommend)
        self.availability = AssistantTools.__new__(AssistantTools)
        from assistant.tools import AssistantAvailabilityTool
        self.availability = AssistantAvailabilityTool()
        self.loans = SimpleNamespace(loans=AsyncMock(return_value={'count': 1, 'issues': [
            {'issue_id': 7, 'work_id': 'OL1W', 'status': 'ISSUED', 'user_id': 17}]}),
            borrow=AsyncMock(return_value={'message': 'Book issued successfully'}),
            return_book=AsyncMock(return_value={'message': 'Book returned successfully'}))
        self.reservations = SimpleNamespace(reserve=AsyncMock(return_value={'message': 'Book reserved successfully'}),
                                             reservations=AsyncMock(return_value={'reservations': []}))
        self.fees = SimpleNamespace(fees=AsyncMock(return_value={'total_unpaid': 5}))
        self.rag = SimpleNamespace(ask=AsyncMock(return_value={'answer': 'Original RAG answer', 'verdict': 'SUPPORTED'}))

    async def book(self, wid):
        if wid not in BOOKS:
            raise ToolFailure('core', 'HTTP_404', 'Book not found')
        return BOOKS[wid].model_copy()

    async def books(self, ids):
        return [await self.book(wid) for wid in dict.fromkeys(ids)]

    async def resolve(self, title, author):
        return [b.model_copy() for b in BOOKS.values() if (not title or b.title == title)
                and (not author or author.casefold() in (b.authors or '').casefold())]

    async def recommend(self, count, seed=None):
        self.calls.append((count, seed))
        return {'OL1W': ['OL1W', 'OL3W', 'OL2W', 'OL3W'],
                'OL2W': ['OL2W', 'OL3W', 'OL4W'],
                None: ['OL4W', 'OL3W']}[seed]


def setup(intent=Intent.RECOMMEND_BOOKS, **fields):
    qwen = FakeQwen(AssistantIntent(intent=intent, confidence=0.95, **fields))
    return AssistantOrchestrator(qwen, ConversationStore()), FakeTools()


def chat(orchestrator, tools, message=None, **kwargs):
    if message is None:
        message = {Intent.SEARCH_BOOKS: 'Find library books', Intent.COMPARE_BOOKS: 'Compare the selected books',
                   Intent.CHECK_AVAILABILITY: 'Check availability', Intent.BORROW_BOOK: 'Borrow the selected book',
                   Intent.RETURN_BOOK: 'Return the selected book', Intent.RESERVE_BOOK: 'Reserve the selected book',
                   Intent.BOOK_CONTENT_QUESTION: 'What happens in this book?'}.get(orchestrator.qwen.intent.intent, 'Recommend')
    return run(orchestrator.chat(AssistantRequest(message=message, **kwargs), '17', tools))


@pytest.mark.parametrize('intent', [Intent.SEARCH_BOOKS, Intent.COMPARE_BOOKS, Intent.CHECK_AVAILABILITY, Intent.RECOMMEND_BOOKS])
def test_structured_intents_validate(intent):
    assert AssistantIntent.model_validate_json('{"intent":"' + intent.value + '","confidence":0.9}').intent == intent


def test_intent_search_books():
    orch, tools = setup(Intent.SEARCH_BOOKS, query='neural networks')
    result = chat(orch, tools, 'Find books about neural networks')
    assert result.intent == Intent.SEARCH_BOOKS
    assert result.books[0].work_id == 'OL1W'
    tools.search.search.assert_awaited_once_with('neural networks', 50)


def test_intent_compare_books():
    orch, tools = setup(Intent.COMPARE_BOOKS, mentioned_titles=['Dracula', 'Frankenstein'])
    assert len(chat(orch, tools, 'Compare Dracula and Frankenstein').comparison.books) == 2


def test_intent_availability():
    orch, tools = setup(Intent.CHECK_AVAILABILITY, mentioned_titles=['Dracula'])
    assert chat(orch, tools, 'Is Dracula available?').availability[0].available is False


def test_intent_recommend():
    orch, tools = setup()
    assert chat(orch, tools).intent == Intent.RECOMMEND_BOOKS


def test_selected_work_ids_take_precedence():
    orch, tools = setup(mentioned_titles=['The Time Machine'], resolved_work_ids=['OL3W'])
    result = chat(orch, tools, 'Recommend like OL3W', selected_work_ids=['OL1W'])
    assert result.seed_work_ids == ['OL1W']


def test_zero_selection_recommend_uses_existing_formula():
    orch, tools = setup(requested_result_count=5)
    result = chat(orch, tools, 'Recommend 5 books')
    # One extra authoritative candidate establishes has_more; still the same
    # unseeded recommendation formula, with no invented seeds or result rows.
    assert tools.calls == [(6, None)]
    assert result.recommendation_mode == RecommendationMode.PERSONALIZED_EXISTING_FORMULA


def test_one_selection_uses_seed_recommendation():
    orch, tools = setup()
    result = chat(orch, tools, selected_work_ids=['OL1W'])
    assert tools.calls == [(50, 'OL1W')]
    assert result.recommendation_mode == RecommendationMode.SINGLE_SELECTED_BOOK


@pytest.mark.parametrize('selected', [[], ['OL1W'], ['OL1W', 'OL2W']])
def test_generic_recommend_never_requests_preferences(selected):
    orch, tools = setup(Intent.CLARIFICATION, clarification_needed=True, reference='this')
    result = chat(orch, tools, 'Recommend', selected_work_ids=selected)
    assert not result.clarification
    assert result.recommendation_mode is not None


def test_multi_selection_uses_all_seeds():
    orch, tools = setup()
    result = chat(orch, tools, selected_work_ids=['OL1W', 'OL2W'])
    assert set(tools.calls) == {(50, 'OL1W'), (50, 'OL2W')}
    assert result.recommendation_mode == RecommendationMode.MULTI_SELECTED_BOOKS
    assert result.books[0].work_id == 'OL3W'


def test_multi_selection_overrides_generated_ordinals_and_titles():
    orch, tools = setup(ordinal_references=[1], mentioned_authors=['Stoker'], reference='this')
    result = chat(orch, tools, selected_work_ids=['OL1W', 'OL2W'])
    assert result.seed_work_ids == ['OL1W', 'OL2W']


def test_selected_books_removed_from_recommendations():
    orch, tools = setup()
    result = chat(orch, tools, selected_work_ids=['OL1W', 'OL2W'])
    assert not {'OL1W', 'OL2W'} & {b.work_id for b in result.books}


def test_duplicate_recommendations_removed():
    orch, tools = setup()
    ids = [b.work_id for b in chat(orch, tools, selected_work_ids=['OL1W']).books]
    assert len(ids) == len(set(ids))


def test_explicit_title_can_be_seed():
    orch, tools = setup(Intent.RECOMMEND_FROM_BOOK, mentioned_titles=['Dracula'])
    result = chat(orch, tools, 'Recommend like Dracula')
    assert result.seed_work_ids == ['OL1W']
    assert result.recommendation_mode == RecommendationMode.EXPLICIT_BOOK_SEED


def test_available_only_recommendation_uses_availability():
    orch, tools = setup(filters=Filters(available_only=True))
    result = chat(orch, tools, 'Recommend available books', selected_work_ids=['OL1W', 'OL2W'])
    assert [b.work_id for b in result.books] == ['OL3W']


def test_recommendation_other_author_uses_catalogue_delimiters(monkeypatch):
    monkeypatch.setitem(BOOKS, 'OL1W', BOOKS['OL1W'].model_copy(update={'authors': 'Bram Stoker | Mary Shelley'}))
    orch, tools = setup(filters=Filters(exclude_seed_authors=True))
    result = chat(orch, tools, 'Similar books by another author', selected_work_ids=['OL1W'])
    assert [b.work_id for b in result.books] == ['OL3W']


def test_recent_result_reference_resolution():
    orch, tools = setup(Intent.SEARCH_BOOKS)
    result = chat(orch, tools)
    orch.qwen.intent = AssistantIntent(intent=Intent.COMPARE_BOOKS, confidence=.9, reference='these')
    result = chat(orch, tools, 'Compare these two', conversation_id=result.conversation_id)
    assert [b.work_id for b in result.books] == ['OL1W', 'OL2W']


def test_second_result_reference():
    orch, tools = setup(Intent.CHECK_AVAILABILITY, ordinal_references=[2])
    result = chat(orch, tools, 'Is the second one available?', recent_work_ids=['OL1W', 'OL2W'])
    assert result.books[0].work_id == 'OL2W'


def test_literal_second_reference_survives_qwen_omission():
    orch, tools = setup(Intent.RESERVE_BOOK)
    result = chat(orch, tools, 'Reserve the second one', recent_work_ids=['OL1W', 'OL2W'])
    assert result.pending_action.work_id == 'OL2W'
    tools.reservations.reserve.assert_not_awaited()


def test_explicit_availability_overrides_stale_comparison_intent():
    orch, tools = setup(Intent.COMPARE_BOOKS, reference='previous_recommendation', clarification_needed=True)
    result = chat(orch, tools, 'Is the second one available?', recent_work_ids=['OL1W', 'OL2W'])
    assert result.intent == Intent.CHECK_AVAILABILITY
    assert [b.work_id for b in result.books] == ['OL2W']


def test_this_book_reference():
    orch, tools = setup(Intent.BOOK_DETAILS, reference='this')
    assert chat(orch, tools, 'This book', selected_work_ids=['OL1W']).books[0].title == 'Dracula'
    assert chat(orch, tools, 'This book', selected_work_ids=['OL1W', 'OL2W']).clarification


def test_page_context_reference():
    orch, tools = setup(Intent.BOOK_DETAILS, reference='this')
    assert chat(orch, tools, 'This book', page_context={'work_id': 'OL3W'}).books[0].work_id == 'OL3W'


def test_author_reference_in_recent_results():
    orch, tools = setup(Intent.BOOK_DETAILS, mentioned_authors=['Wells'])
    assert chat(orch, tools, 'the Wells book', recent_work_ids=['OL1W', 'OL3W']).books[0].work_id == 'OL3W'


def test_title_reference_disambiguates_selected_books():
    orch, tools = setup(Intent.BOOK_DETAILS, mentioned_titles=['Dracula'])
    result = chat(orch, tools, 'the Dracula book', selected_work_ids=['OL1W', 'OL2W'])
    assert [b.work_id for b in result.books] == ['OL1W']


def test_compare_uses_authoritative_metadata():
    orch, tools = setup(Intent.COMPARE_BOOKS, comparison_fields=['page_count', 'availability'])
    result = chat(orch, tools, selected_work_ids=['OL1W', 'OL2W'])
    assert result.comparison.books[0].authors == 'Bram Stoker'
    assert result.comparison.missing_fields == ['page_count']


def test_missing_comparison_values_cannot_be_generated():
    orch, tools = setup(Intent.COMPARE_BOOKS, comparison_fields=['page_count'])
    orch.qwen.respond = AsyncMock(return_value='Both books have 999 pages.')
    result = chat(orch, tools, 'Which is shorter?', selected_work_ids=['OL1W', 'OL2W'])
    assert '999' not in result.message
    assert 'does not record' in result.message


def test_availability_not_generated_by_qwen():
    orch, tools = setup(Intent.CHECK_AVAILABILITY)
    orch.qwen.respond = AsyncMock(return_value='There are 999 copies.')
    result = chat(orch, tools, selected_work_ids=['OL1W'])
    assert result.availability[0].available_copies == 0
    assert result.books[0].available_copies == 0
    assert '999' not in result.message
    assert '0 available copies' in result.message


def test_mutation_requires_confirmation(monkeypatch):
    monkeypatch.setenv('ASSISTANT_MUTATING_ACTIONS_ENABLED', 'true')
    orch, tools = setup(Intent.RESERVE_BOOK)
    proposal = chat(orch, tools, 'Reserve Dracula', selected_work_ids=['OL1W'])
    tools.reservations.reserve.assert_not_awaited()
    result = chat(orch, tools, 'Confirm', conversation_id=proposal.conversation_id,
                  action='CONFIRM_ACTION', pending_action_id=proposal.pending_action.action_id)
    tools.reservations.reserve.assert_awaited_once_with('OL1W')
    assert result.message == 'Book reserved successfully'
    repeated = chat(orch, tools, 'Confirm', conversation_id=proposal.conversation_id,
                    action='CONFIRM_ACTION', pending_action_id=proposal.pending_action.action_id)
    assert repeated.clarification
    assert tools.reservations.reserve.await_count == 1


def test_concrete_ordinal_action_resolves_despite_advisory_clarification():
    orch, tools = setup(Intent.RESERVE_BOOK, ordinal_references=[2], clarification_needed=True)
    result = chat(orch, tools, 'Reserve the second one', recent_work_ids=['OL1W', 'OL2W'])
    assert result.pending_action.work_id == 'OL2W'
    tools.reservations.reserve.assert_not_awaited()


def test_mutation_flag_disabled(monkeypatch):
    monkeypatch.setenv('ASSISTANT_MUTATING_ACTIONS_ENABLED', 'false')
    orch, tools = setup(Intent.BORROW_BOOK)
    proposal = chat(orch, tools, selected_work_ids=['OL1W'])
    result = chat(orch, tools, conversation_id=proposal.conversation_id, action='CONFIRM_ACTION',
                  pending_action_id=proposal.pending_action.action_id)
    assert result.errors[0].code == 'MUTATIONS_DISABLED'
    tools.loans.borrow.assert_not_awaited()


def test_return_binds_owned_issue(monkeypatch):
    monkeypatch.setenv('ASSISTANT_MUTATING_ACTIONS_ENABLED', 'true')
    orch, tools = setup(Intent.RETURN_BOOK)
    proposal = chat(orch, tools, selected_work_ids=['OL1W'])
    chat(orch, tools, conversation_id=proposal.conversation_id, action='CONFIRM_ACTION',
         pending_action_id=proposal.pending_action.action_id)
    tools.loans.return_book.assert_awaited_once_with(7)


def test_cancellation_and_expiry(monkeypatch):
    orch, tools = setup(Intent.RESERVE_BOOK)
    proposal = chat(orch, tools, selected_work_ids=['OL1W'])
    assert chat(orch, tools, conversation_id=proposal.conversation_id, action='CANCEL_ACTION',
                pending_action_id=proposal.pending_action.action_id).message == 'Action cancelled.'
    proposal = chat(orch, tools, selected_work_ids=['OL1W'])
    orch.store.entries[proposal.conversation_id].pending_deadline = 0
    assert chat(orch, tools, conversation_id=proposal.conversation_id, action='CONFIRM_ACTION',
                pending_action_id=proposal.pending_action.action_id).clarification


def test_invalid_work_id_rejected():
    with pytest.raises(ValueError):
        AssistantRequest(message='Details', selected_work_ids=['../../other'])
    orch, tools = setup(Intent.BOOK_DETAILS)
    assert chat(orch, tools, selected_work_ids=['OL999W']).errors[0].code == 'HTTP_404'


def test_qwen_cannot_invent_work_ids():
    orch, tools = setup(Intent.BOOK_DETAILS, resolved_work_ids=['OL3W'])
    assert chat(orch, tools, 'Tell me about a book').clarification


def test_ambiguous_title_returns_clarification():
    orch, tools = setup(Intent.BOOK_DETAILS, mentioned_titles=['Dracula'])
    tools.catalogue.resolve = AsyncMock(return_value=[BOOKS['OL1W'], BOOKS['OL2W']])
    result = chat(orch, tools, 'Dracula')
    assert len(result.clarification.choices) == 2


def test_malformed_qwen_json_safe_fallback():
    gateway = QwenGateway(SimpleNamespace(), RLock())
    gateway.generate = AsyncMock(return_value='{"invalid":1}')
    result = run(gateway.parse('Find books', {}))
    assert result.intent == Intent.CLARIFICATION
    assert gateway.generate.await_count == 2
    gateway.close()


def test_decoding_schema_compatible_but_validation_strict():
    schema = AssistantDecodingSchema.model_json_schema()
    def check(node):
        if isinstance(node, dict):
            assert not ('pattern' in node and ('minLength' in node or 'maxLength' in node))
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)
    check(schema)
    assert schema['required'] == ['intent', 'confidence']
    with pytest.raises(ValueError):
        AssistantIntent(intent='BOOK_DETAILS', resolved_work_ids=['a' * 129])


@pytest.mark.parametrize('service', ['search', 'recommendation'])
def test_adapter_timeout_safe(service):
    async def exercise():
        def fail(request):
            raise httpx.ReadTimeout('private detail', request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
            adapter = ServiceTransport(client, 'Bearer private-token')
            with pytest.raises(ToolFailure) as error:
                await adapter.call(service, 'GET', '/test')
            assert error.value.error.code == 'TIMEOUT'
            assert 'private' not in error.value.error.message
    run(exercise())


def test_search_timeout_safe():
    orch, tools = setup(Intent.SEARCH_BOOKS)
    tools.search.search.side_effect = ToolFailure('search', 'TIMEOUT')
    assert chat(orch, tools).errors[0].service == 'search'


def test_recommendation_timeout_safe():
    orch, tools = setup()
    tools.recommendation.recommend = AsyncMock(side_effect=ToolFailure('recommendation', 'TIMEOUT'))
    assert chat(orch, tools).errors[0].service == 'recommendation'


def test_qwen_timeout_safe():
    orch, tools = setup()
    orch.qwen.parse = AsyncMock(side_effect=QwenUnavailable('Assistant service unavailable'))
    result = chat(orch, tools, 'Recommend something atmospheric')
    assert result.errors[0].code == 'QWEN_UNAVAILABLE'
    assert not tools.calls


def test_confidence_is_advisory_entities_still_validated():
    gateway = QwenGateway(SimpleNamespace(), RLock())
    gateway.generate = AsyncMock(return_value='{"intent":"SEARCH_BOOKS","confidence":0,"query":"neural networks"}')
    parsed = run(gateway.parse('Find books about neural networks', {}))
    assert parsed.confidence == 0
    assert not parsed.clarification_needed
    gateway.close()


def test_qwen_timeout_retains_worker_slot():
    gate = Event()
    llm = SimpleNamespace(generate=lambda *a, **kw: (gate.wait(1), 'done')[1])
    gateway = QwenGateway(llm, RLock(), timeout=.02)
    async def exercise():
        with pytest.raises(QwenUnavailable):
            await gateway.generate('test')
        with pytest.raises(QwenUnavailable):
            await gateway.generate('test2')
        gate.set()
        await asyncio.sleep(.02)
    run(exercise())
    gateway.close()


def test_existing_qwen_reused():
    engine = SimpleNamespace(llm=SimpleNamespace(), inference_lock=RLock())
    app = FastAPI()
    orch = install_assistant(app, engine, lambda *args: {}, lambda **kw: kw)
    assert orch.qwen.llm is engine.llm
    assert orch.qwen.inference_lock is engine.inference_lock
    orch.qwen.close()


def test_qwen_not_loaded_twice():
    for path in (ROOT / 'assistant').glob('*.py'):
        tree = ast.parse(path.read_text())
        assert not any(isinstance(n, ast.Call) and (
            isinstance(n.func, ast.Name) and n.func.id in {'LuminaRLLM', 'LuminaRAG'}
            or isinstance(n.func, ast.Attribute) and n.func.attr == 'from_pretrained') for n in ast.walk(tree))


def test_existing_rag_route_untouched():
    baseline = ast.parse((ROOT / 'reports/assistant_backend_baseline/rag_api.py').read_text(encoding='utf-8'))
    current = ast.parse((ROOT / 'rag/api.py').read_text(encoding='utf-8'))
    functions = {n.name: ast.dump(n) for n in baseline.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    assert all(ast.dump(n) == functions[n.name] for n in current.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))


def test_protected_rag_files_match_original_hashes():
    import hashlib
    import json
    rows = json.loads((ROOT / 'reports/assistant_backend_baseline/hashes.json').read_text(encoding='utf-8-sig'))
    for row in rows:
        if Path(row['Path']).name != 'api.py':
            assert hashlib.sha256(Path(row['Path']).read_bytes()).hexdigest().upper() == row['Hash']


def test_confirmation_cannot_move_between_users():
    orch, tools = setup(Intent.RESERVE_BOOK)
    proposal = chat(orch, tools, selected_work_ids=['OL1W'])
    with pytest.raises(HTTPException):
        run(orch.chat(AssistantRequest(message='Confirm', conversation_id=proposal.conversation_id,
                                      action='CONFIRM_ACTION', pending_action_id=proposal.pending_action.action_id), '18', tools))
    tools.reservations.reserve.assert_not_awaited()


def test_timeout_confirmation_consumed_no_retry(monkeypatch):
    monkeypatch.setenv('ASSISTANT_MUTATING_ACTIONS_ENABLED', 'true')
    orch, tools = setup(Intent.RESERVE_BOOK)
    proposal = chat(orch, tools, selected_work_ids=['OL1W'])
    tools.reservations.reserve.side_effect = ToolFailure('core', 'TIMEOUT')
    result = chat(orch, tools, conversation_id=proposal.conversation_id, action='CONFIRM_ACTION',
                  pending_action_id=proposal.pending_action.action_id)
    assert result.errors[0].code == 'TIMEOUT'
    result = chat(orch, tools, conversation_id=proposal.conversation_id, action='CONFIRM_ACTION',
                  pending_action_id=proposal.pending_action.action_id)
    assert result.clarification
    assert tools.reservations.reserve.await_count == 1


def test_unsupported_filters_clarify_without_tools():
    orch, tools = setup(Intent.RECOMMEND_BOOKS, unsupported_filters=['publication_year_min'])
    assert chat(orch, tools, 'Recommend books after 2000').clarification
    assert not tools.calls


def test_existing_rag_dispatch_and_document_scope():
    orch, tools = setup(Intent.BOOK_CONTENT_QUESTION)
    result = chat(orch, tools, selected_work_ids=['OL1W'])
    assert result.message == 'Original RAG answer'
    tools.rag.ask.assert_awaited_once_with('What happens in this book?', work_id='OL1W')
    orch, tools = setup(Intent.DOCUMENT_QUESTION)
    result = chat(orch, tools, 'PDF question', page_context={'document_id': 'uploaded'})
    tools.rag.ask.assert_awaited_once_with('PDF question', document_id='uploaded')


def test_account_routes_use_authenticated_user():
    async def exercise():
        observed = []
        def handler(request):
            observed.append((request.url.path, request.headers['Authorization']))
            if request.url.path == '/issues/my':
                return httpx.Response(200, json={'issues': [{'status': 'ISSUED'}, {'status': 'RETURNED'}]})
            return httpx.Response(200, json={'count': 0})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            tools = AssistantTools(client, 'Bearer authenticated-user', AsyncMock())
            assert (await tools.loans.loans())['count'] == 1
            assert (await tools.loans.loans(history=True))['count'] == 2
            await tools.reservations.reservations()
            await tools.fees.fees()
        assert {path for path, auth in observed} == {'/issues/my', '/reservations/my', '/fines/my'}
        assert all(auth == 'Bearer authenticated-user' for path, auth in observed)
        with pytest.raises(ValueError):
            AssistantRequest(message='Fees', user_id=123)
    run(exercise())


def test_conversation_ownership_and_ttl():
    store = ConversationStore(ttl=1)
    state = store.get(None, '17')
    with pytest.raises(HTTPException):
        store.get(state.conversation_id, '18')
    state.touched -= 2
    with pytest.raises(HTTPException):
        store.get(state.conversation_id, '17')


def test_endpoint_contract_and_auth(monkeypatch):
    app = FastAPI()
    orch = install_assistant(app, SimpleNamespace(llm=SimpleNamespace(), inference_lock=RLock()),
                             lambda *a: {}, lambda **kw: kw)
    orch.qwen.parse = AsyncMock(return_value=AssistantIntent(intent=Intent.GENERAL_LIBRARY_HELP, confidence=.9))
    orch.qwen.respond = AsyncMock(return_value='Gothic fiction uses suspense.')
    with TestClient(app) as client:
        assert client.post('/assistant/chat', json={'message': 'What is Gothic fiction?'}).status_code in (401, 403)
        app.dependency_overrides[get_current_user] = lambda: {'sub': '17', 'role': 'GENERAL_USER'}
        headers = {'Authorization': 'Bearer authenticated'}
        result = client.post('/assistant/chat', json={'message': 'What is Gothic fiction?'}, headers=headers)
        assert result.status_code == 200
        assert result.json()['intent'] == 'GENERAL_LIBRARY_HELP'
        assert 'conversation_id' in result.json()
        assert client.post('/assistant/chat', json={'message': 'Fees', 'user_id': 2}, headers=headers).status_code == 422
        monkeypatch.setenv('ASSISTANT_ENABLED', 'false')
        assert client.post('/assistant/chat', json={'message': 'Hello'}, headers=headers).status_code == 503


def test_rank_fusion_deterministic():
    assert merge_ranks([['a', 'b', 'a'], ['b', 'c']], {'a'}) == ['b', 'c']


def test_catalogue_adapter_rejects_mismatched_identity():
    async def exercise():
        def handler(request):
            return httpx.Response(200, json=BOOKS['OL2W'].model_dump())
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            tools = AssistantTools(client, 'Bearer current', AsyncMock())
            with pytest.raises(ToolFailure) as error:
                await tools.catalogue.book('OL1W')
            assert error.value.error.code == 'INVALID_CATALOGUE_RESULT'
    run(exercise())


def test_core_exact_resolution_escapes_query_and_reuses_availability(monkeypatch):
    from backend.routes import assistant_catalogue as route
    observed = []
    class Cursor(list):
        def limit(self, count):
            assert count == 6
            return self[:count]
    def find(query, projection):
        observed.append(query)
        return Cursor([BOOKS['OL1W'].model_dump()])
    monkeypatch.setattr(route, 'books_collection', SimpleNamespace(find=find))
    monkeypatch.setattr(route, 'with_authoritative_availability', lambda b: dict(b, available_copies=7))
    result = route.resolve(route.EntityRequest(title='Dracula.*', author='Stoker'), {'sub': '17'})
    assert observed[0]['title']['$regex'] == r'^Dracula\.\*$'
    assert result['books'][0]['available_copies'] == 7


def test_service_errors_do_not_expose_internal_details():
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(500, json={'detail': 'private database credential'}))) as client:
            with pytest.raises(ToolFailure) as error:
                await ServiceTransport(client, 'Bearer current').call('core', 'GET', '/books/OL1W')
            assert 'private' not in error.value.error.message
    run(exercise())


def test_confirmation_serialized_once(monkeypatch):
    monkeypatch.setenv('ASSISTANT_MUTATING_ACTIONS_ENABLED', 'true')
    async def exercise():
        orch, tools = setup(Intent.RESERVE_BOOK)
        proposal = await orch.chat(AssistantRequest(message='Reserve', selected_work_ids=['OL1W']), '17', tools)
        request = AssistantRequest(message='Confirm', conversation_id=proposal.conversation_id,
                                   action='CONFIRM_ACTION', pending_action_id=proposal.pending_action.action_id)
        results = await asyncio.gather(orch.chat(request, '17', tools), orch.chat(request, '17', tools))
        assert tools.reservations.reserve.await_count == 1
        assert sum(r.clarification is not None for r in results) == 1
    run(exercise())


def test_seed_reuses_existing_algorithm(monkeypatch):
    from recommendation import recommendation_service as service
    from collections import Counter
    profile = {'queries': ['personal interest'], 'subjects': Counter(), 'authors': Counter(),
               'active_issue_work_ids': set(), 'active_reservation_work_ids': set()}
    monkeypatch.setattr(service, 'build_user_profile', lambda uid: profile)
    monkeypatch.setattr(service, 'get_book_by_work_id', lambda wid: BOOKS[wid].model_dump())
    seen = []
    def candidates(queries, auth, count):
        seen.append(queries)
        return [{'work_id': 'OL1W', 'semantic_score': .9}, {'work_id': 'OL2W', 'semantic_score': .8}]
    monkeypatch.setattr(service, 'generate_semantic_candidates', candidates)
    original_score = service.calculate_recommendation_score
    scores = []
    def score(*args):
        scores.append(args[2])
        return original_score(*args)
    monkeypatch.setattr(service, 'calculate_recommendation_score', score)
    results = service.get_recommendations(17, 'Bearer current', seed_work_id='OL1W')
    assert [r['work_id'] for r in results] == ['OL2W']
    assert 'Dracula' in seen[0][0]
    assert set(scores[0]['subjects']) == {'Gothic'}
    assert profile['queries'] == ['personal interest']
    assert profile['active_issue_work_ids'] == set()


def test_default_recommender_function_body_preserved():
    baseline = ast.parse((ROOT / 'reports/assistant_backend_baseline/recommendation_service.py').read_text(encoding='utf-8'))
    current = ast.parse((ROOT / 'recommendation/recommendation_service.py').read_text(encoding='utf-8'))
    old = next(n for n in baseline.body if isinstance(n, ast.FunctionDef) and n.name == 'get_recommendations')
    new = next(n for n in current.body if isinstance(n, ast.FunctionDef) and n.name == 'get_recommendations')
    new.body = [n for n in new.body if not (isinstance(n, ast.If) and 'seed_work_id' in ast.unparse(n.test))]
    # The opt-in failure propagation adds no keyword on the default path.
    for node in ast.walk(new):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'generate_semantic_candidates':
            node.keywords = []
    assert [ast.dump(n) for n in old.body] == [ast.dump(n) for n in new.body]


def test_recommender_dependency_failure_opt_in(monkeypatch):
    from recommendation import recommendation_service as service
    import requests
    def fail(*args, **kwargs):
        raise requests.Timeout('private internal detail')
    monkeypatch.setattr(service.requests, 'post', fail)
    assert service.generate_semantic_candidates(['Gothic fiction'], 'Bearer current') == []
    with pytest.raises(RuntimeError, match='dependency unavailable'):
        service.generate_semantic_candidates(['Gothic fiction'], 'Bearer current', strict_service_errors=True)
