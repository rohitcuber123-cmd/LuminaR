"""Fast paths must save calls while retaining identity, auth and confirmation gates."""
import asyncio
import ast
from pathlib import Path
from threading import RLock
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from assistant.api import install_assistant
from assistant.profiling import current, observe_model
from assistant.schemas import AssistantRequest, Intent
from test_assistant_backend import setup, chat, run


def guarded(intent=Intent.UNKNOWN, **fields):
    orch, tools = setup(intent, **fields)
    orch.qwen.parse = AsyncMock(side_effect=AssertionError('Intent Qwen must be skipped'))
    orch.qwen.respond = AsyncMock(side_effect=AssertionError('Response Qwen must be skipped'))
    return orch, tools


def test_compare_action_skips_qwen_intent():
    orch, tools = guarded()
    result = chat(orch, tools, 'Compare these books', action='COMPARE', selected_work_ids=['OL1W', 'OL2W'])
    assert len(result.comparison.books) == 2
    assert not result.errors
    orch.qwen.parse.assert_not_awaited()
    orch.qwen.respond.assert_not_awaited()


def test_recommend_similar_action_skips_qwen_intent():
    orch, tools = guarded()
    result = chat(orch, tools, 'Recommend', action='RECOMMEND_SIMILAR', selected_work_ids=['OL1W'])
    assert result.seed_work_ids == ['OL1W'] and not result.errors
    orch.qwen.parse.assert_not_awaited()


def test_recommend_selection_action_skips_qwen_intent():
    orch, tools = guarded()
    result = chat(orch, tools, 'Recommend', action='RECOMMEND_FROM_SELECTION', selected_work_ids=['OL1W', 'OL2W'])
    assert result.seed_work_ids == ['OL1W', 'OL2W'] and not result.errors
    assert 'OL1W' not in [b.work_id for b in result.books]
    orch.qwen.parse.assert_not_awaited()


def test_availability_action_skips_qwen_intent():
    orch, tools = guarded()
    result = chat(orch, tools, 'Availability', action='CHECK_AVAILABILITY', page_context={'work_id': 'OL1W'})
    assert result.availability[0].available is False and not result.errors
    orch.qwen.parse.assert_not_awaited()


def test_default_recommend_explicit_action_skips_qwen_intent_if_supported():
    orch, tools = guarded()
    result = chat(orch, tools, 'Recommend', action='RECOMMEND')
    assert result.recommendation_mode == 'PERSONALIZED_EXISTING_FORMULA' and tools.calls == [(50, None)]
    assert [b.work_id for b in result.books] == ['OL4W', 'OL3W']
    orch.qwen.parse.assert_not_awaited()


@pytest.mark.parametrize('selected', [[], ['OL1W'], ['OL1W', 'OL2W']])
@pytest.mark.parametrize('message', ['recommend', 'recommend something', 'recommend me something'])
def test_obvious_recommend_fast_route(selected, message):
    orch, tools = guarded()
    result = chat(orch, tools, message, selected_work_ids=selected)
    assert not result.errors and result.recommendation_mode is not None
    orch.qwen.parse.assert_not_awaited()


def test_obvious_fees_fast_route():
    orch, tools = guarded()
    result = chat(orch, tools, 'Do I have fines?')
    assert result.account == {'total_unpaid': 5} and '5' in result.message
    orch.qwen.parse.assert_not_awaited()


def test_obvious_loans_fast_route():
    orch, tools = guarded()
    result = chat(orch, tools, 'What books do I have borrowed?')
    assert result.account['count'] == 1 and not result.errors
    orch.qwen.parse.assert_not_awaited()


@pytest.mark.parametrize('message', ['something atmospheric but not too dark',
    'find something like Dracula but more modern', 'is this available and shorter?',
    'show my loans and recommend something', 'recommend me something atmospheric'])
def test_ambiguous_message_falls_back_to_qwen(message):
    orch, tools = setup(Intent.CLARIFICATION)
    chat(orch, tools, message)
    assert len(orch.qwen.calls) == 1


def test_structured_search_can_skip_response_qwen():
    orch, tools = setup(Intent.SEARCH_BOOKS, query='science')
    orch.qwen.respond = AsyncMock(side_effect=AssertionError('No prose needed'))
    result = chat(orch, tools, 'Find science books')
    assert result.books and '2' in result.message and not result.errors
    # Part 3 repair explicitly requires simple catalogue searches to skip
    # extraction as well. Keep the original verified-result/prose assertions.
    assert len(orch.qwen.calls) == 0
    assert result.intent == Intent.SEARCH_BOOKS
    assert tools.search.search.await_args.args[0] == 'science'
    orch.qwen.respond.assert_not_awaited()


def test_availability_skips_response_qwen():
    orch, tools = guarded()
    result = chat(orch, tools, 'Is this available?', selected_work_ids=['OL1W'])
    assert 'unavailable' in result.message and not result.errors
    orch.qwen.respond.assert_not_awaited()


@pytest.mark.parametrize('message, action, intent', [('Show my loans', 'USER_LOANS', Intent.USER_LOANS),
    ('Show my reservations', 'USER_RESERVATIONS', Intent.USER_RESERVATIONS),
    ('Show my fines', 'USER_FEES', Intent.USER_FEES)])
def test_account_facts_skip_response_qwen(message, action, intent):
    orch, tools = guarded()
    result = chat(orch, tools, message, action=action)
    assert result.intent == intent and result.account is not None and not result.errors
    orch.qwen.respond.assert_not_awaited()


def test_recommendation_cards_do_not_require_response_qwen():
    orch, tools = guarded()
    assert chat(orch, tools, 'Recommend').books
    orch.qwen.respond.assert_not_awaited()


def test_general_help_still_uses_qwen():
    orch, tools = setup(Intent.GENERAL_LIBRARY_HELP)
    orch.qwen.respond = AsyncMock(return_value='Grounded general help')
    result = chat(orch, tools, 'What is Gothic fiction?')
    # Clear conceptual questions now have the required single response pass.
    assert len(orch.qwen.calls) == 0 and result.message == 'Grounded general help'
    assert result.intent == Intent.GENERAL_LIBRARY_HELP
    orch.qwen.respond.assert_awaited_once()


def test_complex_intent_still_uses_qwen():
    orch, tools = setup(Intent.COMPARE_BOOKS, reference='these')
    orch.qwen.respond = AsyncMock(return_value='An inference from these descriptions')
    result = chat(orch, tools, 'Which of these would suit someone new to Gothic literature?', selected_work_ids=['OL1W', 'OL2W'])
    assert len(orch.qwen.calls) == 1 and result.comparison
    orch.qwen.respond.assert_awaited_once()


@pytest.mark.parametrize('action, scope', [('BOOK_CONTENT_QUESTION', {'selected_work_ids': ['OL1W']}),
                                        ('DOCUMENT_QUESTION', {'page_context': {'document_id': 'uploaded'}})])
def test_rag_behavior_unchanged(action, scope):
    orch, tools = guarded()
    result = chat(orch, tools, 'Question about this source', action=action, **scope)
    assert result.rag == {'answer': 'Original RAG answer', 'verdict': 'SUPPORTED'}
    assert result.message == 'Original RAG answer' and not result.errors
    orch.qwen.parse.assert_not_awaited()
    orch.qwen.respond.assert_not_awaited()


def test_confirmation_security_unchanged(monkeypatch):
    monkeypatch.setenv('ASSISTANT_MUTATING_ACTIONS_ENABLED', 'false')
    orch, tools = setup(Intent.RESERVE_BOOK)
    proposal = chat(orch, tools, 'Reserve this book', selected_work_ids=['OL1W'])
    invalid = chat(orch, tools, 'Fees', conversation_id=proposal.conversation_id, action='USER_FEES',
                   pending_action_id=proposal.pending_action.action_id)
    assert invalid.clarification and not invalid.account
    tools.reservations.reserve.assert_not_awaited()


def test_no_duplicate_qwen_load():
    root = Path(__file__).resolve().parents[1]
    for filename in ('assistant/api.py', 'assistant/qwen.py', 'assistant/profiling.py'):
        source = (root / filename).read_text()
        assert 'from_pretrained(' not in source and 'LuminaRLLM(' not in source


def test_fast_path_never_bypasses_auth():
    app = FastAPI()
    orch = install_assistant(app, SimpleNamespace(llm=SimpleNamespace(), inference_lock=RLock()), lambda *a: {}, lambda **kw: kw)
    orch.qwen.parse = AsyncMock()
    with TestClient(app) as client:
        for payload in ({'message': 'Show my fines', 'action': 'USER_FEES'},
                        {'message': 'Compare', 'action': 'COMPARE', 'selected_work_ids': ['OL1W', 'OL2W']}):
            assert client.post('/assistant/chat', json=payload).status_code in (401, 403)
    orch.qwen.parse.assert_not_awaited()


def test_fast_path_never_invents_work_id():
    orch, tools = guarded()
    result = chat(orch, tools, 'Check availability', action='CHECK_AVAILABILITY', selected_work_ids=['made_up_id'])
    assert result.errors[0].code == 'HTTP_404' and not result.books
    orch.qwen.parse.assert_not_awaited()


def test_explicit_action_wins_over_conflicting_message():
    orch, tools = guarded()
    result = chat(orch, tools, 'Recommend', action='COMPARE', selected_work_ids=['OL1W', 'OL2W'])
    assert result.comparison and result.intent == Intent.COMPARE_BOOKS and not result.errors


def test_page_availability_is_not_redirected_to_prior_results():
    orch, tools = guarded()
    first = chat(orch, tools, 'Recommend')
    result = chat(orch, tools, 'Is this available?', conversation_id=first.conversation_id,
                  page_context={'work_id': 'OL1W'})
    assert [b.work_id for b in result.books] == ['OL1W'] and not result.errors


@pytest.mark.parametrize('action, ids', [('COMPARE', []), ('COMPARE', ['OL1W']),
    ('RECOMMEND_SIMILAR', ['OL1W', 'OL2W']), ('RECOMMEND_FROM_SELECTION', ['OL1W']),
    ('RECOMMEND', ['OL1W']), ('CHECK_AVAILABILITY', ['OL1W', 'OL2W'])])
def test_invalid_action_count_rejected(action, ids):
    orch, tools = guarded()
    result = chat(orch, tools, 'Read only', action=action, selected_work_ids=ids)
    assert result.clarification and not result.books and not tools.calls
    orch.qwen.parse.assert_not_awaited()


@pytest.mark.parametrize('action', ['BORROW', 'RESERVE', 'RETURN', 'VIEW_BOOK', 'ADMIN'])
def test_unapproved_structured_action_rejected(action):
    with pytest.raises(ValueError):
        AssistantRequest(message='Read only', action=action)


def test_profile_counts_exact_tokens_without_private_text():
    class Tensor:
        def __init__(self, length): self.shape = (1, length)
    model = SimpleNamespace(generate=lambda **kw: Tensor(13))
    llm = SimpleNamespace(model=model)
    observe_model(llm)
    wrapped = model.generate
    observe_model(llm)
    assert model.generate is wrapped
    data = {'qwen_calls': []}
    token = current.set(data)
    try:
        assert model.generate(input_ids=Tensor(10), max_new_tokens=20).shape == (1, 13)
    finally:
        current.reset(token)
    assert data['qwen_calls'][0]['input_tokens'] == 10
    assert data['qwen_calls'][0]['generated_tokens'] == 3
    assert set(data['qwen_calls'][0]) == {'stage','input_tokens','generated_tokens','max_new_tokens','generation_ms'}
