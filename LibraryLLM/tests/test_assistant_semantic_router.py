"""Schema, scope, memory and safety contracts independent of wording rules."""
import asyncio
from threading import RLock
from unittest.mock import AsyncMock
from types import SimpleNamespace
import pytest

from assistant.schemas import (AssistantIntentDecision, AssistantRequest, Intent, ReferenceScope,
    SemanticGoal, ClarificationType, Filters)
from assistant.qwen import QwenGateway, validated_intent
from assistant.semantic import router_context
from test_assistant_backend import setup, chat, BOOKS


def semantic(intent, **fields):
    orch, tools = setup(intent)
    orch.qwen.parse = AsyncMock(return_value=AssistantIntentDecision(intent=intent, confidence=1, **fields))
    orch.qwen.respond = AsyncMock(side_effect=AssertionError('Structured results never need prose'))
    tools.catalogue.resolve = AsyncMock(side_effect=AssertionError('No fuzzy title lookup'))
    tools.search.search = AsyncMock(side_effect=AssertionError('No catalogue search'))
    return orch, tools


def test_preference_clarification_keeps_known_pair_and_pending_criterion():
    orch, tools = semantic(Intent.COMPARE_BOOKS, reference_scope=ReferenceScope.SELECTED_BOOKS,
        goal=SemanticGoal.PREFERENCE_COMPARE, clarification_needed=True,
        clarification_type=ClarificationType.CRITERIA_AMBIGUITY)
    first = chat(orch, tools, 'which one would be better', selected_work_ids=['OL1W','OL2W'])
    assert first.intent == Intent.COMPARE_BOOKS
    assert first.clarification.type == ClarificationType.CRITERIA_AMBIGUITY
    assert not first.clarification.choices
    assert [b.work_id for b in first.comparison.books] == ['OL1W','OL2W']
    assert orch.store.entries[first.conversation_id].awaiting_criteria
    orch.qwen.parse.return_value = AssistantIntentDecision(intent=Intent.COMPARE_BOOKS,
        reference_scope=ReferenceScope.PREVIOUS_COMPARISON, goal=SemanticGoal.PREFERENCE_COMPARE,
        criterion='someone new to Gothic fiction')
    second = chat(orch, tools, 'for someone new to Gothic fiction', conversation_id=first.conversation_id)
    assert not second.clarification and 'cannot establish' in second.message
    assert [b.work_id for b in second.comparison.books] == ['OL1W','OL2W']
    assert orch.qwen.parse.call_args.args[1]['awaiting_criteria']
    assert orch.qwen.parse.await_count == 2
    orch.qwen.respond.assert_not_awaited()


def test_ordinal_then_other_then_graph_use_safe_subsets():
    orch, tools = semantic(Intent.CHECK_AVAILABILITY, reference_scope=ReferenceScope.SELECTED_BOOKS,
        resolved_work_ids=['OL1W'])
    first = chat(orch, tools, 'is the first one available', selected_work_ids=['OL1W','OL2W'])
    assert first.books[0].work_id == 'OL1W'
    orch.qwen.parse.return_value = AssistantIntentDecision(intent=Intent.CHECK_AVAILABILITY,
        reference_scope=ReferenceScope.SELECTED_BOOKS, resolved_work_ids=['OL2W'])
    second = chat(orch, tools, 'and the other?', selected_work_ids=['OL1W','OL2W'], conversation_id=first.conversation_id)
    assert second.books[0].work_id == 'OL2W'
    assert orch.qwen.parse.call_args.args[1]['last_referenced_work_ids'] == ['OL1W']
    tools.kg = SimpleNamespace(more_like_this=AsyncMock(return_value={'recommendations': [BOOKS['OL3W'].model_dump()]}))
    orch.qwen.parse.return_value = AssistantIntentDecision(intent=Intent.MORE_LIKE_THIS,
        reference_scope=ReferenceScope.SELECTED_BOOKS, resolved_work_ids=['OL2W'])
    third = chat(orch, tools, 'anything similar to that one', selected_work_ids=['OL1W','OL2W'], conversation_id=first.conversation_id)
    assert third.seed_work_ids == ['OL2W'] and not third.errors
    tools.kg.more_like_this.assert_awaited_once_with('OL2W',10)


@pytest.mark.parametrize('scope', [ReferenceScope.PREVIOUS_COMPARISON, ReferenceScope.RECENT_RESULTS])
def test_changed_selection_rejects_stale_model_subset(scope):
    orch, tools = semantic(Intent.BOOK_DETAILS, reference_scope=scope, resolved_work_ids=['OL1W'])
    state = orch.store.get(None,'17'); state.selected_work_ids = ['OL1W','OL2W']
    state.last_comparison_work_ids = ['OL1W','OL2W']; state.active_result_work_ids = ['OL1W','OL2W']
    result = chat(orch, tools, 'tell me about that one', selected_work_ids=['OL3W','OL4W'], conversation_id=state.conversation_id)
    assert result.clarification and not result.books and not result.errors
    assert orch.qwen.parse.call_args.args[1]['selection_changed']


@pytest.mark.parametrize('message', ['which one', 'the other', 'these', 'both', 'either', 'the first one'])
def test_pseudo_titles_never_cross_fuzzy_gate(message):
    orch, tools = semantic(Intent.BOOK_DETAILS, reference_scope=ReferenceScope.EXPLICIT_BOOK,
        mentioned_titles=[message])
    result = chat(orch, tools, message)
    assert result.clarification and not result.errors
    tools.catalogue.resolve.assert_not_awaited(); tools.search.search.assert_not_awaited()


def test_unprovided_model_id_is_not_authoritative():
    orch, tools = semantic(Intent.BOOK_DETAILS, reference_scope=ReferenceScope.SELECTED_BOOKS,
        resolved_work_ids=['OL4W'])
    assert chat(orch, tools, 'that one', selected_work_ids=['OL1W']).clarification
    tools.catalogue.resolve.assert_not_awaited()


def test_model_cannot_label_an_old_reference_as_explicit_to_override_selection():
    orch, tools = semantic(Intent.BOOK_DETAILS, reference_scope=ReferenceScope.EXPLICIT_BOOK,
        resolved_work_ids=['OL1W'])
    state = orch.store.get(None,'17'); state.last_comparison_work_ids = ['OL1W','OL2W']
    result = chat(orch, tools, 'tell me about that book', selected_work_ids=['OL3W'], conversation_id=state.conversation_id)
    assert result.clarification and not result.books


def test_low_confidence_unresolved_entity_does_not_search():
    orch, tools = semantic(Intent.BOOK_DETAILS, reference_scope=ReferenceScope.EXPLICIT_BOOK,
        mentioned_titles=['Dracula'])
    orch.qwen.parse.return_value.confidence = .2
    result = chat(orch, tools, 'tell me about Dracula')
    assert result.clarification
    tools.catalogue.resolve.assert_not_awaited(); tools.search.search.assert_not_awaited()


def test_context_has_only_identity_metadata_and_two_semantic_turns():
    orch, tools = semantic(Intent.COMPARE_BOOKS)
    state = orch.store.get(None,'17')
    state.semantic_turns = [{'intent':'COMPARE_BOOKS','referenced_work_ids':['OL1W','OL2W']}] * 3
    context = asyncio.run(router_context(AssistantRequest(message='compare them',selected_work_ids=['OL1W','OL2W']),state,tools))
    assert len(context['previous_turns']) == 2
    assert context['selected_books'][0]['title'] == 'Dracula'
    assert set(context['selected_books'][0]) == {'work_id','title','authors'}
    assert 'description' not in str(context) and 'prompt' not in str(context)


def test_schema_rejects_untrusted_scope_goal_and_unknown_fields():
    for raw in ['{"i":"compare","c":1,"s":"ADMIN"}', '{"i":"compare","c":1,"g":"INVENT_WINNER"}',
                '{"i":"compare","c":1,"owner":99}', '{"i":"details","c":1,"w":["../escape"]}']:
        with pytest.raises(ValueError): validated_intent(raw)


def test_invalid_router_output_is_one_call_and_safe_clarification():
    gateway = QwenGateway(SimpleNamespace(), RLock())
    gateway.generate = AsyncMock(return_value='malformed')
    parsed = asyncio.run(gateway.parse('which should I read', {}))
    assert parsed.intent == Intent.CLARIFICATION and parsed.clarification_needed
    gateway.generate.assert_awaited_once(); gateway.close()


def test_numeric_field_comparison_is_api_grounded(monkeypatch):
    monkeypatch.setitem(BOOKS,'OL1W',BOOKS['OL1W'].model_copy(update={'average_rating':4.2}))
    monkeypatch.setitem(BOOKS,'OL2W',BOOKS['OL2W'].model_copy(update={'average_rating':4.8}))
    orch, tools = semantic(Intent.COMPARE_BOOKS, reference_scope=ReferenceScope.SELECTED_BOOKS,
        goal=SemanticGoal.COMPARE_BY_FIELD, comparison_fields=['average_rating'])
    result = chat(orch, tools, 'whose star score is stronger', selected_work_ids=['OL1W','OL2W'])
    assert 'Frankenstein' in result.message and '4.8' in result.message and not result.clarification


def test_typed_mutation_uses_same_confirmation_gate(monkeypatch):
    monkeypatch.setenv('ASSISTANT_MUTATING_ACTIONS_ENABLED','true')
    orch, tools = semantic(Intent.RESERVE_BOOK, reference_scope=ReferenceScope.SELECTED_BOOKS,
        resolved_work_ids=['OL1W'], goal=SemanticGoal.ACTION)
    result = chat(orch, tools, 'place a hold for the first', selected_work_ids=['OL1W','OL2W'])
    assert result.pending_action.work_id == 'OL1W' and result.pending_action.requires_confirmation
    tools.reservations.reserve.assert_not_awaited()


def test_selected_pair_takes_precedence_over_page_scope():
    orch, tools = semantic(Intent.COMPARE_BOOKS, reference_scope=ReferenceScope.CURRENT_PAGE_BOOK)
    result = chat(orch, tools, 'contrast these', selected_work_ids=['OL1W','OL2W'],
        page_context={'work_id':'OL3W'})
    assert [b.work_id for b in result.comparison.books] == ['OL1W','OL2W']


def test_literal_work_id_with_punctuation_is_canonical_not_fuzzy():
    orch, tools = semantic(Intent.BOOK_DETAILS, reference_scope=ReferenceScope.EXPLICIT_BOOK,
        resolved_work_ids=['OL1W'])
    result = chat(orch, tools, 'show OL1W?')
    assert [b.work_id for b in result.books] == ['OL1W'] and not result.clarification


def test_decoder_uses_canonical_ids_instead_of_numeric_model_positions():
    from assistant.qwen import CompactAssistantDecodingSchema
    properties = CompactAssistantDecodingSchema.model_json_schema()['properties']
    assert 'w' in properties and 'o' not in properties


@pytest.mark.parametrize('position,ids',[('FIRST',['OL1W']),('SECOND',['OL2W']),('LAST',['OL2W']),('ALL',['OL1W','OL2W'])])
def test_semantic_position_binds_only_to_authoritative_pool(position,ids):
    orch, tools = semantic(Intent.BOOK_DETAILS, reference_scope=ReferenceScope.SELECTED_BOOKS,
        reference_position=position)
    result=chat(orch,tools,'contextual details',selected_work_ids=['OL1W','OL2W'])
    assert [b.work_id for b in result.books]==ids


def test_semantic_other_then_focus_remain_in_pair():
    orch, tools=semantic(Intent.CHECK_AVAILABILITY,reference_scope=ReferenceScope.SELECTED_BOOKS,
        reference_position='FIRST')
    first=chat(orch,tools,'first stock',selected_work_ids=['OL1W','OL2W'])
    orch.qwen.parse.return_value=AssistantIntentDecision(intent=Intent.CHECK_AVAILABILITY,
        reference_scope=ReferenceScope.SELECTED_BOOKS,reference_position='OTHER')
    second=chat(orch,tools,'remaining stock',selected_work_ids=['OL1W','OL2W'],conversation_id=first.conversation_id)
    assert [b.work_id for b in second.books]==['OL2W']
    orch.qwen.parse.return_value=AssistantIntentDecision(intent=Intent.BOOK_DETAILS,
        reference_scope=ReferenceScope.SELECTED_BOOKS,reference_position='FOCUS')
    third=chat(orch,tools,'focused details',selected_work_ids=['OL1W','OL2W'],conversation_id=first.conversation_id)
    assert [b.work_id for b in third.books]==['OL2W']



def test_pending_reading_goal_preserves_comparison_pair_if_model_marks_one_position():
    orch, tools=semantic(Intent.COMPARE_BOOKS,reference_scope=ReferenceScope.SELECTED_BOOKS,
        goal=SemanticGoal.PREFERENCE_COMPARE,clarification_type=ClarificationType.CRITERIA_AMBIGUITY)
    first=chat(orch,tools,'help choose',selected_work_ids=['OL1W','OL2W'])
    orch.qwen.parse.return_value=AssistantIntentDecision(intent=Intent.COMPARE_BOOKS,
        reference_scope=ReferenceScope.SELECTED_BOOKS,reference_position='FIRST',
        goal=SemanticGoal.PREFERENCE_COMPARE,criterion='a literature course')
    second=chat(orch,tools,'for a literature course',selected_work_ids=['OL1W','OL2W'],conversation_id=first.conversation_id)
    assert [b.work_id for b in second.comparison.books]==['OL1W','OL2W']
    assert not second.clarification and 'cannot establish' in second.message



def test_account_list_position_checks_current_ownership_before_removal():
    orch,tools=semantic(Intent.REMOVE_FROM_READING_LIST,reference_scope=ReferenceScope.ACCOUNT,
        reference_position='SECOND')
    state=orch.store.get(None,'17');state.last_reading_list_work_ids=['OL1W','OL2W']
    tools.reading_list=SimpleNamespace(get=AsyncMock(return_value={'items':[{'work_id':'OL1W'}]}),remove=AsyncMock())
    result=chat(orch,tools,'remove a saved item',conversation_id=state.conversation_id)
    assert result.clarification and 'no longer' in result.message
    tools.reading_list.remove.assert_not_awaited()
    tools.reading_list.get.return_value={'items':[{'work_id':'OL1W'},{'work_id':'OL2W'}]}
    result=chat(orch,tools,'remove a saved item',conversation_id=state.conversation_id)
    tools.reading_list.remove.assert_awaited_once_with('OL2W')
    assert [b.work_id for b in result.books]==['OL2W']



def test_model_only_clear_decision_cannot_erase_reading_list():
    orch,tools=semantic(Intent.CLEAR_READING_LIST,reference_scope=ReferenceScope.ACCOUNT)
    tools.reading_list=SimpleNamespace(get=AsyncMock(),clear=AsyncMock())
    result=chat(orch,tools,'open my saved reading list')
    assert result.clarification and 'Clear reading list button' in result.message
    tools.reading_list.get.assert_not_awaited();tools.reading_list.clear.assert_not_awaited()
