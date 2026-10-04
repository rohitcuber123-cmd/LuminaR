"""Repair acceptance: behavior, ownership, continuation and call counts."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_assistant_part3 import FakeTools, FakeQwen, BOOKS, run
from assistant.orchestrator import AssistantOrchestrator
from assistant.schemas import AssistantIntent, AssistantIntentDecision, AssistantRequest, Book, Filters, Intent
from assistant.state import ConversationStore
from assistant.routing import fast_route
from assistant.qwen import validated_intent, CompactAssistantDecodingSchema, QwenGateway
from threading import RLock


def setup(intent=Intent.SEARCH_BOOKS, **fields):
    qwen = FakeQwen(AssistantIntent(intent=intent, confidence=1, **fields))
    return AssistantOrchestrator(qwen, ConversationStore()), FakeTools(), qwen


def chat(orch, tools, message='test', **fields):
    return run(orch.chat(AssistantRequest(message=message, **fields), '17', tools))


def large_pool(tools):
    books = {f'OL{i}W': Book(work_id=f'OL{i}W',title=f'Candidate {i}',authors='Fixture Author',available_copies=1) for i in range(10,40)}
    tools.search.search = AsyncMock(return_value=list(books))
    tools.catalogue.books = AsyncMock(side_effect=lambda ids: [BOOKS.get(wid) or books[wid] for wid in ids])
    tools.recommendation.recommend = AsyncMock(side_effect=lambda count, seed=None: list(books)[:count])
    return books


def test_show_more_search_preserves_query_increments_offset_and_does_not_repeat():
    orch, tools, qwen = setup(query='artificial intelligence')
    large_pool(tools)
    first = chat(orch,tools,'Find AI titles')
    second = chat(orch,tools,'Show more',action='SHOW_MORE',conversation_id=first.conversation_id,
                  selected_work_ids=['untrusted_client_seed'],result_offset=10)
    assert second.result_offset == 10
    assert not set(b.work_id for b in first.books) & set(b.work_id for b in second.books)
    tools.search.search.assert_awaited_once_with('artificial intelligence',50)
    assert len(qwen.calls) == 1
    replay = chat(orch,tools,'Show more',action='SHOW_MORE',conversation_id=first.conversation_id,result_offset=10)
    assert replay.clarification and not replay.books


def test_recommendation_continuation_keeps_seeds_mode_and_fresh_facts():
    orch,tools,qwen=setup()
    books=large_pool(tools)
    first=chat(orch,tools,action='RECOMMEND_SIMILAR',selected_work_ids=['OL1W'])
    books['OL20W'].available_copies=0
    second=chat(orch,tools,action='SHOW_MORE',conversation_id=first.conversation_id)
    assert second.seed_work_ids == ['OL1W'] and second.recommendation_mode == first.recommendation_mode
    assert second.availability[0].available is False
    tools.recommendation.recommend.assert_awaited_once_with(50,'OL1W')
    assert qwen.calls == [] and qwen.respond_calls == 0


def test_default_recommendation_continuation_retains_pool_with_same_formula():
    orch,tools,qwen=setup()
    large_pool(tools)
    first=chat(orch,tools,action='RECOMMEND')
    second=chat(orch,tools,action='SHOW_MORE',conversation_id=first.conversation_id)
    assert second.result_offset == 10 and second.has_more
    assert second.recommendation_mode == 'PERSONALIZED_EXISTING_FORMULA'
    tools.recommendation.recommend.assert_awaited_once_with(50)
    assert qwen.calls == [] and qwen.respond_calls == 0
    assert not set(b.work_id for b in first.books)&set(b.work_id for b in second.books)


def test_explain_recommendation_uses_all_original_seeds_and_one_generation():
    orch,tools,qwen=setup()
    first=chat(orch,tools,action='RECOMMEND_FROM_SELECTION',selected_work_ids=['OL1W','OL2W','OL3W'])
    qwen.generate=AsyncMock(return_value='Verified narrative')
    result=chat(orch,tools,action='EXPLAIN_RECOMMENDATION',conversation_id=first.conversation_id,selected_work_ids=['OL4W'])
    assert result.seed_work_ids == ['OL1W','OL2W','OL3W']
    qwen.generate.assert_awaited_once()
    assert 'Dracula' in qwen.generate.call_args.args[0] and 'Frankenstein' in qwen.generate.call_args.args[0]
    assert qwen.calls == [] and qwen.respond_calls == 0


def test_explain_comparison_preserves_fields_and_targets_after_tray_changes():
    orch,tools,qwen=setup(Intent.COMPARE_BOOKS,comparison_fields=['authors','page_count'])
    first=chat(orch,tools,'Compare',selected_work_ids=['OL1W','OL2W'])
    qwen.generate=AsyncMock(return_value='Verified comparison')
    result=chat(orch,tools,action='EXPLAIN_COMPARISON',conversation_id=first.conversation_id,selected_work_ids=['OL3W','OL4W'])
    assert [b.work_id for b in result.comparison.books] == ['OL1W','OL2W']
    assert result.comparison.requested_fields == ['authors','page_count']
    assert result.comparison.missing_fields == ['page_count']
    qwen.generate.assert_awaited_once()


@pytest.mark.parametrize('action',['EXPLAIN_RECOMMENDATION','EXPLAIN_COMPARISON','SHOW_MORE'])
def test_all_ordinary_special_actions_invalidate_pending_proposal(action,monkeypatch):
    monkeypatch.setenv('ASSISTANT_MUTATING_ACTIONS_ENABLED','true')
    orch,tools,qwen=setup(Intent.RESERVE_BOOK)
    pending=chat(orch,tools,'reserve this',selected_work_ids=['OL1W'])
    chat(orch,tools,action=action,conversation_id=pending.conversation_id)
    replay=chat(orch,tools,action='CONFIRM_ACTION',conversation_id=pending.conversation_id,
                pending_action_id=pending.pending_action.action_id)
    assert replay.clarification
    tools.reservations.reserve.assert_not_awaited()


@pytest.mark.parametrize('rows,expected,message',[
    ([],[], 'no active loans'),
    ([{'work_id':'OL1W'}],['OL1W'],'parseable due dates'),
    ([{'work_id':'OL1W','due_date':'invalid'},{'work_id':'OL2W','due_date':'2026-10-03'},
      {'work_id':'OL3W','due_date':'2026-10-03'}],['OL2W','OL3W','OL1W'],'earliest due loan'),
])
def test_due_first_empty_missing_dates_and_ties(rows,expected,message):
    orch,tools,qwen=setup(Intent.USER_LOANS,comparison_fields=['due_date'])
    tools.loans.loans=AsyncMock(return_value={'issues':rows,'count':len(rows)})
    result=chat(orch,tools,'Which one is due first?')
    assert [r['work_id'] for r in result.account['issues']] == expected
    assert message in result.message
    assert len(qwen.calls) == 1


def test_ordinal_remove_uses_owned_reading_list_not_search_or_tray():
    orch,tools,qwen=setup()
    tools.reading_list._items=[{'work_id':'OL2W'}]
    first=chat(orch,tools,action='USER_READING_LIST')
    state=orch.store.get(first.conversation_id,'17')
    state.recent_result_work_ids=['OL1W']
    qwen.intent=AssistantIntent(intent=Intent.REMOVE_FROM_READING_LIST,ordinal_references=[1])
    chat(orch,tools,'remove the first book from my reading list',conversation_id=first.conversation_id,selected_work_ids=['OL1W'])
    assert tools.reading_list.removed == ['OL2W']
    tools.reading_list._items=[]
    result=chat(orch,tools,'remove the first book from my reading list',conversation_id=first.conversation_id)
    assert result.clarification and tools.reading_list.removed == ['OL2W']


def test_empty_reading_list_clears_stale_book_references():
    orch,tools,qwen=setup()
    first=chat(orch,tools,action='CHECK_AVAILABILITY',selected_work_ids=['OL1W'])
    chat(orch,tools,action='USER_READING_LIST',conversation_id=first.conversation_id)
    assert orch.store.get(first.conversation_id,'17').recent_result_work_ids == []


def test_same_author_refinement_preserves_original_search_query_and_clarifies_ambiguity():
    orch,tools,qwen=setup(query='artificial intelligence')
    large_pool(tools)
    first=chat(orch,tools,'Find AI titles')
    qwen.intent=AssistantIntentDecision(intent=Intent.SEARCH_BOOKS,context_operation='REFINE_RESULTS',filters=Filters(author='Fixture Author'))
    result=chat(orch,tools,'same author',conversation_id=first.conversation_id)
    context=orch.store.get(first.conversation_id,'17').result_context
    assert context.query == 'artificial intelligence' and context.filters.author == 'Fixture Author'
    assert result.books and len(qwen.calls)==2
    tools.search.search.assert_awaited_once()
    other=chat(orch,tools,action='RECOMMEND_FROM_SELECTION',selected_work_ids=['OL1W','OL2W'])
    qwen.intent=AssistantIntentDecision(intent=Intent.SEARCH_BOOKS,context_operation='REFINE_RESULTS',filters=Filters(author='Fixture Author'))
    qwen.intent=AssistantIntent(intent=Intent.CLARIFICATION)
    result=chat(orch,tools,'same author',conversation_id=other.conversation_id)
    assert result.clarification and not result.books


@pytest.mark.parametrize('message,intent',[
    ('Compare the first two',Intent.COMPARE_BOOKS),
    ('Recommend based on the first two',Intent.RECOMMEND_FROM_SELECTION),
    ('Is the third one available?',Intent.CHECK_AVAILABILITY),
])
def test_reading_list_ordinals_are_active_in_order(message,intent):
    orch,tools,qwen=setup(intent,ordinal_references=[3] if intent==Intent.CHECK_AVAILABILITY else [1,2],reference='these')
    tools.reading_list._items=[{'work_id':'OL2W'},{'work_id':'OL1W'},{'work_id':'OL3W'}]
    first=chat(orch,tools,action='USER_READING_LIST')
    result=chat(orch,tools,message,conversation_id=first.conversation_id)
    if intent==Intent.COMPARE_BOOKS:
        assert [b.work_id for b in result.comparison.books]==['OL2W','OL1W']
        assert qwen.respond_calls == 0  # Plain ordinal comparison stays structured.
    elif intent==Intent.RECOMMEND_FROM_SELECTION:
        assert result.seed_work_ids==['OL2W','OL1W']
    else:
        assert [b.work_id for b in result.books]==['OL3W']


@pytest.mark.parametrize('message,query',[
    ('Find books about artificial intelligence','artificial intelligence'),
    ('Search for books about databases','databases'),
    ('Show books about machine learning','machine learning'),
    ('Find Gothic books','Gothic'),
    ('Show science fiction books','science fiction'),
])
def test_simple_search_zero_model_calls_and_exact_semantic_query(message,query):
    orch,tools,qwen=setup(Intent.SEARCH_BOOKS,query=query)
    result=chat(orch,tools,message)
    assert result.intent==Intent.SEARCH_BOOKS and result.books and not result.errors
    tools.search.search.assert_awaited_once_with(query,50)
    assert len(qwen.calls)==1 and qwen.respond_calls==0


@pytest.mark.parametrize('message',[
    'Find books about AI but not depressing',
    'Find books about AI without much math',
    'Find books about AI under 200 pages',
    'Find books about AI published after 2020',
    'Find books about AI by the same author',
    'Find books about AI',
    'Find available books about artificial intelligence by different authors, sorted by title',
    'something atmospheric but not depressing',
    'an accessible book that explains AI without much math',
    'something like Dracula but more modern and available',
])
def test_complex_or_unsupported_search_falls_through(message):
    assert fast_route(AssistantRequest(message=message)) is None
    orch,tools,qwen=setup(Intent.CLARIFICATION)
    result=chat(orch,tools,message)
    assert len(qwen.calls)==1 and result.clarification


def test_simple_search_supported_author_and_available_filters():
    # Semantics arrive from the strict router; the executor applies API filters.
    orch, tools, qwen = setup(Intent.SEARCH_BOOKS, query='Gothic fiction',
        filters=Filters(author='Bram Stoker', available_only=True))
    result = chat(orch, tools, 'Find books about Gothic fiction by Bram Stoker available now')
    assert len(qwen.calls) == 1 and qwen.respond_calls == 0
    assert not result.errors
    assert all(b.authors == 'Bram Stoker' and b.available_copies > 0 for b in result.books)


@pytest.mark.parametrize('message',[
    'What is Gothic fiction?', 'What does dystopian mean?',
    'What is an autobiography?', 'What is magical realism?', 'What is a memoir?',
])
def test_clear_general_concept_has_one_response_and_no_extraction(message):
    orch,tools,qwen=setup(Intent.GENERAL_LIBRARY_HELP)
    result=chat(orch,tools,message)
    assert result.intent==Intent.GENERAL_LIBRARY_HELP
    assert len(qwen.calls)==1 and qwen.respond_calls==1 and not result.errors


def test_explicit_book_context_skips_only_assistant_extraction_and_preserves_rag():
    orch,tools,qwen=setup(Intent.BOOK_CONTENT_QUESTION)
    state=orch.store.get(None,'17'); state.last_intent=Intent.SEARCH_BOOKS
    result=chat(orch,tools,'Who is the main character in this selected book?',
                conversation_id=state.conversation_id,page_context={'work_id':'OL2W'})
    assert result.intent==Intent.BOOK_CONTENT_QUESTION and result.rag
    tools.rag.ask.assert_awaited_once_with('Who is the main character in this selected book?',work_id='OL2W')
    assert len(qwen.calls)==1 and qwen.respond_calls==0


def test_compact_model_intent_preserves_full_validation_defaults_and_supported_filters():
    parsed=validated_intent('{"i":"search","c":1,"q":"artificial intelligence","f":{"v":true,"x":true,"o":"title"}}')
    expected=AssistantIntent(intent=Intent.SEARCH_BOOKS,confidence=1,query='artificial intelligence',
                             filters=Filters(available_only=True,exclude_seed_authors=True,sort_preference='title'))
    assert parsed.model_dump(include=set(AssistantIntent.model_fields)) == expected.model_dump()
    assert parsed.ordinal_references==[] and not parsed.clarification_needed
    schema=CompactAssistantDecodingSchema.model_json_schema()
    assert schema['required']==['i','c','s'] and schema['additionalProperties'] is False
    assert schema['$defs']['Filters']['additionalProperties'] is False
    assert set(schema['$defs']['Intent']['enum'])=={'search','recommend','seed_recommend','selected','compare','availability','details','borrow','return','reserve','loans','reservations','history','fees','list','add_list','remove_list','clear_list','alternatives','help','book_question','document_question','clarify','unknown','graph'}


@pytest.mark.parametrize('raw',[
    '{"i":"search","c":2}', '{"i":"invented","c":1}',
    '{"i":"details","c":1,"w":["../../escape"]}',
    '{"i":"search","c":1,"f":{"v":true,"admin":true}}',
    '{"i":"search","c":1,"admin":true}', '{"i":"search","c":1,"n":100}',
    '{"i":"compare","c":1,"o":[1,2,3,4,5]}',
])
def test_compact_model_intent_cannot_bypass_original_constraints(raw):
    with pytest.raises(ValueError): validated_intent(raw)


def test_compact_generation_is_one_pass_and_enforces_small_budget():
    gateway=QwenGateway(SimpleNamespace(),RLock())
    gateway.generate=AsyncMock(return_value='{"i":"search","c":1,"q":"databases"}')
    result=run(gateway.parse('Find databases',{}))
    assert result.query=='databases' and result.intent==Intent.SEARCH_BOOKS
    gateway.generate.assert_awaited_once()
    assert gateway.generate.call_args.args[1] is CompactAssistantDecodingSchema
    gateway.close()


def test_compact_invalid_ordinal_is_rejected_by_original_resolution_guard():
    orch,tools,qwen=setup(Intent.COMPARE_BOOKS)
    qwen.intent=validated_intent('{"i":"compare","c":1,"o":[0]}')
    result=chat(orch,tools,'Compare a result',recent_work_ids=['OL1W','OL2W'])
    assert result.clarification and result.comparison is None


def test_catalogue_page_background_results_do_not_add_an_intent_pass_to_a_clear_concept():
    orch,tools,qwen=setup(Intent.GENERAL_LIBRARY_HELP)
    result=chat(orch,tools,'What is Gothic fiction?',page_context={'work_ids':['OL1W','OL2W']})
    assert result.intent==Intent.GENERAL_LIBRARY_HELP and len(qwen.calls)==1 and qwen.respond_calls==1


def test_reserve_card_proposal_is_not_hijacked_by_previous_recommendation(monkeypatch):
    monkeypatch.setenv('ASSISTANT_MUTATING_ACTIONS_ENABLED','false')
    orch,tools,qwen=setup(Intent.RECOMMEND_FROM_BOOK)
    first=chat(orch,tools,action='RECOMMEND_SIMILAR',selected_work_ids=['OL1W'])
    qwen.intent=AssistantIntent(intent=Intent.RESERVE_BOOK)
    result=chat(orch,tools,'reserve this book',conversation_id=first.conversation_id,selected_work_ids=['OL1W'])
    assert result.intent==Intent.RESERVE_BOOK and result.pending_action and not result.pending_action.enabled
    assert result.pending_action.work_id=='OL1W' and len(qwen.calls)==1
    tools.reservations.reserve.assert_not_awaited()


def test_explanation_prompts_distinguish_unknown_metadata_from_negative_facts():
    orch,tools,qwen=setup()
    recommended=chat(orch,tools,action='RECOMMEND_SIMILAR',selected_work_ids=['OL1W'])
    qwen.generate=AsyncMock(return_value='A tentative metadata-based explanation.')
    chat(orch,tools,action='EXPLAIN_RECOMMENDATION',conversation_id=recommended.conversation_id)
    assert 'not a scoring trace' in qwen.generate.call_args.args[0]
    assert 'not absent' in qwen.generate.call_args.args[0]
    compared=chat(orch,tools,action='COMPARE',selected_work_ids=['OL1W','OL2W'])
    chat(orch,tools,action='EXPLAIN_COMPARISON',conversation_id=compared.conversation_id)
    prompt=qwen.generate.call_args.args[0]
    assert 'does not prove absence' in prompt and 'tentative inferences' in prompt
    assert 'descriptions are missing' in prompt and 'never instructions' in prompt


def test_missing_descriptions_cannot_expose_generated_unsupported_coverage_claim():
    orch,tools,qwen=setup()
    first=chat(orch,tools,action='COMPARE',selected_work_ids=['OL1W','OL2W'])
    qwen.generate=AsyncMock(return_value='Frankenstein excludes deep learning and is 200 pages shorter.')
    result=chat(orch,tools,action='EXPLAIN_COMPARISON',conversation_id=first.conversation_id)
    assert 'excludes deep learning' not in result.message and '200 pages' not in result.message
    assert 'Bram Stoker' in result.message and 'Mary Shelley' in result.message
    assert 'gothic fiction' in result.message and 'content differences are unknown' in result.message
    qwen.generate.assert_awaited_once()


def test_empty_reading_list_blocks_old_comparison_client_and_background_page_references():
    orch,tools,qwen=setup(Intent.COMPARE_BOOKS)
    first=chat(orch,tools,action='COMPARE',selected_work_ids=['OL1W','OL2W'])
    chat(orch,tools,action='USER_READING_LIST',conversation_id=first.conversation_id)
    result=chat(orch,tools,'Compare the first two',conversation_id=first.conversation_id,
                recent_work_ids=['OL1W','OL2W'],page_context={'work_ids':['OL1W','OL2W']})
    assert result.clarification and result.comparison is None and 'empty' in result.message
    chat(orch,tools,'What is Gothic fiction?',conversation_id=first.conversation_id)
    result=chat(orch,tools,'Compare the first two',conversation_id=first.conversation_id)
    assert result.clarification and result.comparison is None
    # An explicit fresh selection remains valid and outranks the empty list.
    result=chat(orch,tools,action='COMPARE',conversation_id=first.conversation_id,
                selected_work_ids=['OL1W','OL2W'])
    assert result.comparison and not result.errors


def test_explanation_restores_its_displayed_results_as_active_references_after_proposal():
    orch,tools,qwen=setup()
    first=chat(orch,tools,action='RECOMMEND_SIMILAR',selected_work_ids=['OL1W'])
    chat(orch,tools,'reserve this',conversation_id=first.conversation_id,selected_work_ids=['OL1W'])
    qwen.generate=AsyncMock(return_value='A metadata-based explanation.')
    explained=chat(orch,tools,action='EXPLAIN_RECOMMENDATION',conversation_id=first.conversation_id)
    assert orch.store.get(first.conversation_id,'17').active_result_work_ids==[b.work_id for b in explained.books]
    qwen.intent=AssistantIntent(intent=Intent.CHECK_AVAILABILITY,ordinal_references=[1])
    result=chat(orch,tools,'Is the first one available?',conversation_id=first.conversation_id)
    assert result.books[0].work_id==first.books[0].work_id and result.books[0].work_id!='OL1W'
