"""Current-selection correctness and conservative routing, with forbidden fallbacks."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from assistant.schemas import Book, Intent, AssistantIntent, AssistantRequest
from assistant.contextual import selected_command
from test_assistant_backend import setup, chat, BOOKS
from test_assistant_latency import guarded

SELECTED = ['OL1W', 'OL2W']
COMPARE = ['compare these books', 'compare them', 'compare the selected books',
    'what are the differences in these books', 'what are the differnces in these books',
    "what's different about these", 'how are these books different', 'differences between them',
    'difference between these books', 'how do these compare', 'compare my selections',
    'which features differ between these', 'compare these by rating', 'compare these by availability',
    'compare their authors', 'compare their subjects', 'Compare these?', 'compare these!!!',
    'compare the books I selected', 'compare all selected books', 'compare both books', 'compare the two books']


def bound(message, selected=SELECTED, **kwargs):
    orch, tools = guarded()
    tools.catalogue.resolve = AsyncMock(side_effect=AssertionError('No title resolution'))
    tools.search.search = AsyncMock(side_effect=AssertionError('No search'))
    result = chat(orch, tools, message, selected_work_ids=selected, **kwargs)
    assert not result.errors
    orch.qwen.parse.assert_not_awaited()
    orch.qwen.respond.assert_not_awaited()
    tools.catalogue.resolve.assert_not_awaited()
    tools.search.search.assert_not_awaited()
    return result, orch, tools


@pytest.mark.parametrize('message', COMPARE)
@pytest.mark.parametrize('count', [2, 3, 4])
def test_compare_these_books_uses_selected_work_ids(message, count):
    ids=list(BOOKS)[:count]
    result,_,_=bound(message,ids,page_context={'work_id':'OL4W'})
    if ('both' in message or 'the two' in message) and count != 2:
        assert result.clarification and not result.clarification.choices
    else:
        assert result.intent==Intent.COMPARE_BOOKS and not result.clarification
        assert [b.work_id for b in result.comparison.books]==ids


def test_selected_context_overrides_stale_search_and_comparison_and_replaces_selection():
    result,orch,tools=bound('compare these')
    state=orch.store.entries[result.conversation_id]
    state.active_result_work_ids=['OL1W','OL2W']
    state.last_search_work_ids=['OL1W','OL2W']
    state.last_comparison_work_ids=['OL1W','OL2W']
    changed=chat(orch,tools,'compare them',selected_work_ids=['OL3W','OL4W'],conversation_id=result.conversation_id,page_context={'work_id':'OL1W'})
    assert [b.work_id for b in changed.comparison.books]==['OL3W','OL4W']


@pytest.mark.parametrize('selected,reason', [([], 'Select a book'), (['OL1W'],'one more'), (['OL1W','OL2W','OL3W'],'Which two')])
def test_missing_or_ambiguous_cardinality_never_searches(selected,reason):
    phrase='compare both books' if len(selected)==3 else 'compare these books'
    result,_,_=bound(phrase,selected)
    assert result.intent==Intent.CLARIFICATION and reason in result.message
    assert not result.clarification.choices


@pytest.mark.parametrize('message', ['recommend based on these','recommend from these books',
    'what should I read based on these','find books like these','recommend something from my selections'])
@pytest.mark.parametrize('selected', [['OL1W'],SELECTED,['OL1W','OL2W','OL3W','OL4W']])
def test_selected_recommendation_zero_qwen(message,selected):
    orch,tools=guarded()
    tools.catalogue.resolve=AsyncMock(side_effect=AssertionError('No title resolution'))
    original_recommend = tools.recommendation.recommend
    async def recommend(count, seed=None):
        return await original_recommend(count, seed) if seed in ('OL1W', 'OL2W', None) else []
    tools.recommendation.recommend = recommend
    result=chat(orch,tools,message,selected_work_ids=selected,page_context={'work_id':'OL4W'})
    assert result.seed_work_ids==selected and not result.errors and not result.clarification
    assert result.recommendation_mode==('SINGLE_SELECTED_BOOK' if len(selected)==1 else 'MULTI_SELECTED_BOOKS')
    assert not set(selected)&{b.work_id for b in result.books}
    orch.qwen.parse.assert_not_awaited();orch.qwen.respond.assert_not_awaited()


@pytest.mark.parametrize('message', ['are these available?','availability of these books','which of these are available?','can I borrow these?'])
def test_availability_selected_zero_qwen(message):
    result,_,_=bound(message)
    assert result.intent==Intent.CHECK_AVAILABILITY
    assert [b.work_id for b in result.books]==SELECTED
    assert [a.work_id for a in result.availability]==SELECTED
    assert [a.available for a in result.availability]==[False,True]


@pytest.mark.parametrize('message', ['tell me about this book','details about this one','who wrote this?','what subjects does this book have?'])
def test_catalogue_details_are_structured(message):
    result,_,_=bound(message,['OL1W'])
    assert result.intent==Intent.BOOK_DETAILS and result.books[0].authors=='Bram Stoker'


def test_model_work_ids_in_titles_cannot_contaminate_deictic_resolution():
    orch,tools=setup(Intent.COMPARE_BOOKS, mentioned_titles=SELECTED)
    tools.catalogue.resolve=AsyncMock(side_effect=AssertionError('No title resolution'))
    tools.search.search=AsyncMock(side_effect=AssertionError('No search'))
    # Complex comparison keeps the semantic parser, but not its bogus titles.
    result=chat(orch,tools,'Which of these would fit someone new to machine learning?',selected_work_ids=SELECTED)
    assert [b.work_id for b in result.comparison.books]==SELECTED
    tools.catalogue.resolve.assert_not_awaited();tools.search.search.assert_not_awaited()
    assert len(orch.qwen.calls)==1


def test_explicit_named_book_can_override_selection():
    orch,tools=setup(Intent.BOOK_DETAILS,mentioned_titles=['The Time Machine'])
    result=chat(orch,tools,'Tell me about The Time Machine',selected_work_ids=SELECTED)
    assert [b.work_id for b in result.books]==['OL3W']


def test_page_precedes_empty_retained_context():
    result,orch,tools=bound('compare these')
    state=orch.store.entries[result.conversation_id]
    state.active_result_work_ids=[]
    current=chat(orch,tools,'are these books available?',conversation_id=result.conversation_id,
        page_context={'work_ids':['OL3W','OL4W']})
    assert not current.clarification and [b.work_id for b in current.books]==['OL3W','OL4W']


def test_explicit_action_argument_overrides_tray_and_page():
    result,_,_=bound('Is this book available?',SELECTED,action='CHECK_AVAILABILITY',action_work_ids=['OL3W'],page_context={'work_id':'OL4W'})
    assert [b.work_id for b in result.books]==['OL3W']


@pytest.mark.parametrize('message', ['more like this','show related books','books connected to this'])
def test_more_like_this_single_selected_kg_only(message):
    orch,tools=guarded()
    tools.kg=SimpleNamespace(more_like_this=AsyncMock(return_value={'recommendations':[BOOKS['OL2W'].model_dump()]}))
    tools.recommendation.recommend=AsyncMock(side_effect=AssertionError('KG must not use recommender'))
    result=chat(orch,tools,message,selected_work_ids=['OL1W'])
    assert result.intent==Intent.MORE_LIKE_THIS and result.seed_work_ids==['OL1W']
    tools.kg.more_like_this.assert_awaited_once_with('OL1W',10)
    orch.qwen.parse.assert_not_awaited();orch.qwen.respond.assert_not_awaited()
    ambiguous=chat(orch,tools,message,selected_work_ids=SELECTED,page_context={'work_id':'OL4W'})
    assert ambiguous.clarification and len(tools.kg.more_like_this.await_args_list)==1


@pytest.mark.parametrize('message,intent', [('show my loans',Intent.USER_LOANS),('what do I owe?',Intent.USER_FEES),('my reservations',Intent.USER_RESERVATIONS),('show my history',Intent.USER_HISTORY)])
def test_account_fast_routes(message,intent):
    orch,tools=guarded()
    tools.history=SimpleNamespace(history=AsyncMock(return_value={'activity':[]}))
    result=chat(orch,tools,message)
    assert result.intent==intent and not result.errors
    orch.qwen.parse.assert_not_awaited()


@pytest.mark.parametrize('message', ['find books about neural networks','search for gothic horror books', 'books on personal finance','show me books about databases'])
def test_simple_search_uses_existing_service_zero_qwen(message):
    orch,tools=guarded()
    result=chat(orch,tools,message)
    assert result.intent==Intent.SEARCH_BOOKS and not result.errors
    orch.qwen.parse.assert_not_awaited()


@pytest.mark.parametrize('message', [
    'I want something about money but not a textbook and preferably useful for someone starting a business',
    'Which of these would fit someone who already understands calculus but is new to machine learning?',
    'Explain why the author approaches this topic differently',
    'compare Dracula with these', 'compare these and show my loans',
])
def test_complex_language_falls_back_to_qwen(message):
    orch,tools=setup(Intent.GENERAL_LIBRARY_HELP)
    result=chat(orch,tools,message,selected_work_ids=SELECTED)
    assert len(orch.qwen.calls)==1
    assert selected_command(message) is None

