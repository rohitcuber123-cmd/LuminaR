"""Semantic decisions bind current context; no title/search fallbacks for referents.

The original language examples remain here as executor contract cases. Their
semantic interpretation is evaluated separately with real Qwen in the corpus.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from assistant.schemas import (Intent, AssistantIntentDecision, AssistantRequest, ReferenceScope, SemanticGoal)
from assistant.kg_routing import fast_route
from test_assistant_backend import setup, chat, BOOKS
SELECTED = ['OL1W', 'OL2W']
COMPARE = ['compare these books', 'compare them', 'compare the selected books',
    'what are the differences in these books', 'what are the differnces in these books',
    "what's different about these", 'how are these books different', 'differences between them',
    'difference between these books', 'how do these compare', 'compare my selections',
    'which features differ between these', 'compare these by rating', 'compare these by availability',
    'compare their authors', 'compare their subjects', 'Compare these?', 'compare these!!!',
    'compare the books I selected', 'compare all selected books', 'compare both books', 'compare the two books']


def bound(message, selected=SELECTED, intent=Intent.COMPARE_BOOKS, **kwargs):
    orch, tools = setup(intent)
    scope = ReferenceScope.SELECTED_BOOKS if selected else (ReferenceScope.CURRENT_PAGE_BOOK
        if kwargs.get('page_context') else ReferenceScope.AMBIGUOUS)
    decision = AssistantIntentDecision(intent=intent, confidence=1, reference_scope=scope)
    orch.qwen.parse = AsyncMock(return_value=decision)
    orch.qwen.respond = AsyncMock(side_effect=AssertionError('No prose call'))
    tools.catalogue.resolve = AsyncMock(side_effect=AssertionError('No title resolution'))
    tools.search.search = AsyncMock(side_effect=AssertionError('No search'))
    result = chat(orch, tools, message, selected_work_ids=selected, **kwargs)
    assert not result.errors
    assert orch.qwen.parse.await_count == (0 if kwargs.get('action') else 1)
    orch.qwen.respond.assert_not_awaited()
    tools.catalogue.resolve.assert_not_awaited(); tools.search.search.assert_not_awaited()
    return result, orch, tools


@pytest.mark.parametrize('message', COMPARE)
@pytest.mark.parametrize('count', [2, 3, 4])
def test_compare_these_books_uses_selected_work_ids(message, count):
    ids = list(BOOKS)[:count]
    # Cardinality ambiguity is a semantic decision, not a word detector in the executor.
    intent = Intent.CLARIFICATION if count != 2 and ('both' in message or 'the two' in message) else Intent.COMPARE_BOOKS
    result, _, _ = bound(message, ids, intent=intent, page_context={'work_id':'OL4W'})
    if intent == Intent.CLARIFICATION: assert result.clarification and not result.clarification.choices
    else: assert [b.work_id for b in result.comparison.books] == ids


def test_selected_context_overrides_stale_search_and_comparison_and_replaces_selection():
    result, orch, tools = bound('compare these')
    state = orch.store.entries[result.conversation_id]
    state.active_result_work_ids = SELECTED; state.last_comparison_work_ids = SELECTED
    changed = chat(orch, tools, 'compare them', selected_work_ids=['OL3W','OL4W'],
        conversation_id=result.conversation_id, page_context={'work_id':'OL1W'})
    assert [b.work_id for b in changed.comparison.books] == ['OL3W','OL4W']
    assert orch.qwen.parse.call_args.args[1]['selection_changed']


@pytest.mark.parametrize('selected', [[], ['OL1W']])
def test_missing_or_insufficient_selection_never_searches(selected):
    result, _, _ = bound('compare these books', selected)
    assert result.clarification and not result.clarification.choices


@pytest.mark.parametrize('message', ['recommend based on these','recommend from these books',
    'what should I read based on these','find books like these','recommend something from my selections'])
@pytest.mark.parametrize('selected', [['OL1W'],SELECTED,['OL1W','OL2W','OL3W','OL4W']])
def test_selected_recommendation_one_router_call(message, selected):
    orch, tools = setup(Intent.RECOMMEND_BOOKS)
    orch.qwen.respond = AsyncMock(side_effect=AssertionError('No prose'))
    tools.recommendation.recommend = AsyncMock(return_value=['OL3W','OL4W'])
    tools.catalogue.resolve = AsyncMock(side_effect=AssertionError('No title resolution'))
    result = chat(orch, tools, message, selected_work_ids=selected, page_context={'work_id':'OL4W'})
    assert result.seed_work_ids == selected and not result.errors and not result.clarification
    assert len(orch.qwen.calls) == 1
    assert not set(selected) & {b.work_id for b in result.books}
    orch.qwen.respond.assert_not_awaited(); tools.catalogue.resolve.assert_not_awaited()


@pytest.mark.parametrize('message', ['are these available?','availability of these books','which of these are available?','can I borrow these?'])
def test_availability_selected_one_router_call(message):
    result, _, _ = bound(message, intent=Intent.CHECK_AVAILABILITY)
    assert [b.work_id for b in result.books] == SELECTED
    assert [a.available for a in result.availability] == [False,True]


@pytest.mark.parametrize('message', ['tell me about this book','details about this one','who wrote this?','what subjects does this book have?'])
def test_catalogue_details_are_structured(message):
    result, _, _ = bound(message, ['OL1W'], intent=Intent.BOOK_DETAILS)
    assert result.books[0].authors == 'Bram Stoker'


def test_model_pseudo_titles_cannot_contaminate_contextual_resolution():
    orch, tools = setup(Intent.COMPARE_BOOKS, mentioned_titles=SELECTED)
    tools.catalogue.resolve = AsyncMock(side_effect=AssertionError('No title resolution'))
    result = chat(orch, tools, 'Which of these would fit someone new to machine learning?', selected_work_ids=SELECTED)
    assert [b.work_id for b in result.comparison.books] == SELECTED
    tools.catalogue.resolve.assert_not_awaited(); assert len(orch.qwen.calls) == 1


def test_explicit_named_book_can_override_selection():
    orch, tools = setup(Intent.BOOK_DETAILS, mentioned_titles=['The Time Machine'])
    result = chat(orch, tools, 'Tell me about The Time Machine', selected_work_ids=SELECTED)
    assert [b.work_id for b in result.books] == ['OL3W']


def test_explicit_action_argument_overrides_tray_and_page():
    result, _, _ = bound('Is this book available?', SELECTED, action='CHECK_AVAILABILITY',
        action_work_ids=['OL3W'], page_context={'work_id':'OL4W'})
    assert [b.work_id for b in result.books] == ['OL3W']


@pytest.mark.parametrize('message', ['more like this','show related books','books connected to this'])
def test_more_like_this_single_selected_kg_only(message):
    orch, tools = setup(Intent.MORE_LIKE_THIS)
    tools.kg = SimpleNamespace(more_like_this=AsyncMock(return_value={'recommendations':[BOOKS['OL2W'].model_dump()]}))
    tools.recommendation.recommend = AsyncMock(side_effect=AssertionError('No recommender'))
    result = chat(orch, tools, message, selected_work_ids=['OL1W'])
    assert result.intent == Intent.MORE_LIKE_THIS and result.seed_work_ids == ['OL1W']
    assert len(orch.qwen.calls) == 1; tools.recommendation.recommend.assert_not_awaited()


@pytest.mark.parametrize('message,intent', [('show my loans',Intent.USER_LOANS),('what do I owe?',Intent.USER_FEES),
    ('my reservations',Intent.USER_RESERVATIONS),('show my history',Intent.USER_HISTORY)])
def test_account_semantic_routes(message, intent):
    orch, tools = setup(intent); result = chat(orch, tools, message, selected_work_ids=SELECTED)
    assert result.intent == intent and result.account is not None and len(orch.qwen.calls) == 1


@pytest.mark.parametrize('message', ['find books about neural networks','search for gothic horror books','books on personal finance','show me books about databases'])
def test_search_uses_existing_service_after_one_semantic_call(message):
    orch, tools = setup(Intent.SEARCH_BOOKS, query='fixture extracted topic')
    assert chat(orch, tools, message).books and len(orch.qwen.calls) == 1
    tools.search.search.assert_awaited_once_with('fixture extracted topic',50)


@pytest.mark.parametrize('message', COMPARE)
def test_no_typed_language_is_a_fast_route(message):
    assert fast_route(AssistantRequest(message=message, selected_work_ids=SELECTED)) is None
