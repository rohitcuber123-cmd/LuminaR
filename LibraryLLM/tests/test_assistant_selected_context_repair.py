"""Production semantic contracts; real Qwen generalization is measured live separately."""
import asyncio
import json
from unittest.mock import AsyncMock
import pytest
from assistant.schemas import AssistantIntentDecision, AssistantRequest, Intent, ReferenceScope, SemanticGoal, ClarificationType, Book
from assistant.semantic import router_context
from assistant.qwen import QwenGateway, QwenUnavailable, CompactAssistantDecodingSchema, SelectedContextDecodingSchema
from assistant.selected_context import metadata_packet, SelectedContextAnswer, evidence_packet, answer_schema, render_answer
from test_assistant_backend import setup, chat

PAIR = ['OL1W','OL2W']


def selected(message='why are these named similarly?', ids=PAIR, **fields):
    orch, tools = setup(Intent.GENERAL_LIBRARY_HELP)
    decision = AssistantIntentDecision(intent=Intent.GENERAL_LIBRARY_HELP, confidence=1,
        reference_scope=ReferenceScope.SELECTED_BOOKS, goal=SemanticGoal.EXPLAIN, **fields)
    orch.qwen.parse = AsyncMock(return_value=decision)
    orch.qwen.respond = AsyncMock(return_value='Dracula and Frankenstein share the recorded Gothic subject. Their metadata does not establish a publication relationship.')
    tools.catalogue.books = AsyncMock(wraps=tools.catalogue.books)
    tools.catalogue.resolve = AsyncMock(side_effect=AssertionError('No fuzzy title resolution'))
    tools.search.search = AsyncMock(side_effect=AssertionError('No unrelated Search'))
    return chat(orch, tools, message, selected_work_ids=ids), orch, tools


def test_selected_pair_freeform_question_uses_selection():
    result, orch, _ = selected()
    assert [book.work_id for book in result.books] == PAIR
    assert orch.qwen.parse.call_args.args[1]['selected_count'] == 2
    assert orch.qwen.parse.call_args.args[1]['current_selection_exists']


def test_router_receives_explicit_empty_selection_status():
    orch, tools = setup(Intent.CLARIFICATION)
    request = AssistantRequest(message='a current question')
    state = orch.store.get(None, 'reader')
    context = asyncio.run(router_context(request, state, tools))
    assert context['selected_count'] == 0 and context['current_selection_exists'] is False


def test_selected_decoding_requires_semantic_goal_without_changing_default_contract():
    assert CompactAssistantDecodingSchema.model_json_schema()['required'] == ['i', 'c', 's']
    assert SelectedContextDecodingSchema.model_json_schema()['required'] == ['i', 'c', 's', 'g']
    gateway = QwenGateway.__new__(QwenGateway)
    gateway.generate = AsyncMock(return_value='{"i":"help","c":1,"s":"selected","g":"explain"}')
    asyncio.run(gateway.parse('a contextual question', {'current_selection_exists': True}))
    assert gateway.generate.call_args.args[1] is SelectedContextDecodingSchema


def test_selected_metadata_is_reused_without_redundant_hydration():
    _, _, tools = selected()
    tools.catalogue.books.assert_awaited_once_with(PAIR)


def test_ordinal_explanation_keeps_all_current_selected_metadata():
    result, orch, _ = selected('an explanation involving multiple positioned works', reference_position='SECOND')
    assert [book.work_id for book in result.books] == PAIR
    assert [book.work_id for book in orch.qwen.respond.call_args.args[1].books] == PAIR


def test_freeform_focus_without_prior_focus_still_has_explicit_selection():
    result, _, _ = selected('reason about the supplied works', reference_position='FOCUS')
    assert not result.clarification and [b.work_id for b in result.books] == PAIR


def test_explanation_without_comparison_fields_uses_selected_fallback():
    _, orch, tools = selected()
    orch.qwen.parse.return_value = AssistantIntentDecision(intent=Intent.COMPARE_BOOKS, confidence=1,
        reference_scope=ReferenceScope.SELECTED_BOOKS, goal=SemanticGoal.EXPLAIN)
    result = chat(orch, tools, 'a relational explanation', selected_work_ids=PAIR)
    assert result.intent == Intent.GENERAL_LIBRARY_HELP and [b.work_id for b in result.books] == PAIR


def test_causal_explanation_purpose_does_not_become_preference_comparison():
    _, orch, tools = selected()
    orch.qwen.parse.return_value = AssistantIntentDecision(intent=Intent.COMPARE_BOOKS, confidence=1,
        reference_scope=ReferenceScope.SELECTED_BOOKS, goal=SemanticGoal.EXPLAIN, criterion='publication influence')
    result = chat(orch, tools, 'a causal relation question', selected_work_ids=PAIR)
    assert result.intent == Intent.GENERAL_LIBRARY_HELP and [b.work_id for b in result.books] == PAIR


def test_positioned_discovery_retains_graph_route():
    _, orch, tools = selected()
    orch.qwen.parse.return_value = AssistantIntentDecision(intent=Intent.COMPARE_BOOKS, confidence=1,
        reference_scope=ReferenceScope.SELECTED_BOOKS, goal=SemanticGoal.DISCOVER, reference_position='SECOND')
    result = chat(orch, tools, 'discover other related works', selected_work_ids=PAIR)
    assert result.intent == Intent.MORE_LIKE_THIS and not result.clarification


def test_group_relation_without_objective_fields_uses_metadata():
    _, orch, tools = selected()
    orch.qwen.parse.return_value = AssistantIntentDecision(intent=Intent.COMPARE_BOOKS, confidence=1,
        reference_scope=ReferenceScope.SELECTED_BOOKS, goal=SemanticGoal.DISCOVER,
        reference_position='ALL', criterion='relationship')
    result = chat(orch, tools, 'a relation across the supplied set', selected_work_ids=PAIR)
    assert result.intent == Intent.GENERAL_LIBRARY_HELP and [b.work_id for b in result.books] == PAIR


def test_semantic_catalogue_overview_retains_details_tool():
    _, orch, tools = selected()
    orch.qwen.parse.return_value = AssistantIntentDecision(intent=Intent.BOOK_CONTENT_QUESTION, confidence=1,
        reference_scope=ReferenceScope.SELECTED_BOOKS, goal=SemanticGoal.DETAIL)
    result = chat(orch, tools, 'a catalogue overview', selected_work_ids=['OL1W'])
    assert result.intent == Intent.BOOK_DETAILS and [b.work_id for b in result.books] == ['OL1W']
    tools.rag.ask.assert_not_awaited()


def test_semantic_content_analysis_cannot_enter_metadata_fallback():
    _, orch, tools = selected()
    orch.qwen.parse.return_value = AssistantIntentDecision(intent=Intent.GENERAL_LIBRARY_HELP, confidence=1,
        reference_scope=ReferenceScope.SELECTED_BOOKS, goal=SemanticGoal.CONTENT_QUESTION)
    result = chat(orch, tools, 'specific content analysis', selected_work_ids=['OL1W'])
    assert result.intent == Intent.BOOK_CONTENT_QUESTION and result.rag
    tools.rag.ask.assert_awaited_once()


def test_explanation_cannot_invent_literal_entity_from_selected_metadata():
    _, orch, tools = selected()
    orch.qwen.parse.return_value = AssistantIntentDecision(intent=Intent.GENERAL_LIBRARY_HELP,
        confidence=1, reference_scope=ReferenceScope.EXPLICIT_BOOK, goal=SemanticGoal.EXPLAIN, mentioned_titles=['Dracula'])
    result = chat(orch, tools, 'explain the current work', selected_work_ids=['OL2W'])
    assert [b.work_id for b in result.books] == ['OL2W'] and not result.clarification
    tools.catalogue.resolve.assert_not_awaited()


def test_selected_pair_freeform_question_no_title_search():
    _, _, tools = selected(); tools.catalogue.resolve.assert_not_awaited(); tools.search.search.assert_not_awaited()


def test_selected_pair_freeform_question_no_clarification():
    result, orch, _ = selected()
    assert not result.clarification and not result.errors
    orch.qwen.parse.assert_awaited_once(); orch.qwen.respond.assert_awaited_once()


@pytest.mark.parametrize('message', ['what connects these two?','why do they sound alike?', 'what do these share?',
    'is there a reason their titles are so similar?', 'how are these related?', 'what is the main difference between them?',
    'which seems more focused on practical habits?'])
def test_selected_pair_freeform_generalizes(message):
    result, _, _ = selected(message)
    assert [b.work_id for b in result.books] == PAIR and not result.clarification


def assert_selection_count(count):
    ids = ['OL1W','OL2W','OL3W','OL4W'][:count]
    result, orch, _ = selected('what theme connects this selection?', ids)
    assert [b.work_id for b in result.books] == ids
    assert len(orch.qwen.parse.call_args.args[1]['selected_books']) == count


def test_single_selected_freeform_question(): assert_selection_count(1)
def test_three_selected_freeform_question(): assert_selection_count(3)
def test_four_selected_freeform_question(): assert_selection_count(4)


def test_new_chat_selection_payload_contract():
    result, orch, tools = selected()
    fresh = chat(orch, tools, 'a fresh selection question', conversation_id=None, selected_work_ids=PAIR)
    assert fresh.conversation_id != result.conversation_id and [b.work_id for b in fresh.books] == PAIR


def test_no_visible_selection_payload_mismatch():
    result, orch, _ = selected(ids=['OL2W','OL1W'])
    assert [b.work_id for b in result.books] == ['OL2W','OL1W']
    assert [b['work_id'] for b in orch.qwen.parse.call_args.args[1]['selected_books']] == ['OL2W','OL1W']


def test_selection_change_uses_current_selection():
    result, orch, tools = selected()
    state = orch.store.entries[result.conversation_id]; state.last_comparison_work_ids = PAIR
    changed = chat(orch, tools, 'what connects this selection?', selected_work_ids=['OL3W','OL4W'], conversation_id=result.conversation_id, page_context={'work_id':'OL1W'})
    assert [b.work_id for b in changed.books] == ['OL3W','OL4W']


def test_selection_remove_updates_context():
    result, orch, tools = selected()
    single = chat(orch, tools, 'what stands out about this?', selected_work_ids=['OL1W'], conversation_id=result.conversation_id)
    assert [b.work_id for b in single.books] == ['OL1W']


def test_clear_selection_allows_clarification():
    orch, tools = setup(Intent.CLARIFICATION)
    orch.qwen.parse = AsyncMock(return_value=AssistantIntentDecision(intent=Intent.CLARIFICATION,
        reference_scope=ReferenceScope.AMBIGUOUS, clarification_type=ClarificationType.REFERENCE_AMBIGUITY))
    result = chat(orch, tools, 'what connects these two?', selected_work_ids=[])
    assert result.clarification and not result.books


def test_empty_selection_cannot_generate_selected_context_answer():
    _, orch, tools = selected()
    result = chat(orch, tools, 'a current selection question', selected_work_ids=[])
    assert result.clarification and not result.books
    orch.qwen.respond.assert_awaited_once()  # Only the initial selected helper turn.


def test_selected_semantic_explanation_clarification_guard():
    _, orch, tools = selected()
    orch.qwen.parse.return_value = AssistantIntentDecision(intent=Intent.CLARIFICATION,
        reference_scope=ReferenceScope.SELECTED_BOOKS, goal=SemanticGoal.EXPLAIN,
        clarification_type=ClarificationType.REFERENCE_AMBIGUITY)
    result = chat(orch, tools, 'explain the selection', selected_work_ids=PAIR)
    assert not result.clarification and [b.work_id for b in result.books] == PAIR


def test_missing_third_position_still_clarifies():
    result, orch, _ = selected('what stands out about the third?', reference_position='THIRD')
    assert result.clarification and not result.books
    orch.qwen.respond.assert_not_awaited()


def test_fallback_does_not_trust_model_invented_work_ids():
    result, _, _ = selected(resolved_work_ids=['INVENTED'])
    assert [b.work_id for b in result.books] == PAIR


def test_explicit_title_overrides_selection():
    orch, tools = setup(Intent.BOOK_DETAILS, mentioned_titles=['Frankenstein'])
    result = chat(orch, tools, 'tell me about Frankenstein', selected_work_ids=['OL3W','OL4W'])
    assert [b.work_id for b in result.books] == ['OL2W']


def test_literal_title_precedes_inconsistent_semantic_selection_scope():
    orch, tools = setup(Intent.BOOK_DETAILS)
    orch.qwen.parse = AsyncMock(return_value=AssistantIntentDecision(intent=Intent.BOOK_DETAILS,
        confidence=1,reference_scope=ReferenceScope.SELECTED_BOOKS,reference_position='FOCUS',mentioned_titles=['Frankenstein']))
    result = chat(orch, tools, 'tell me about Frankenstein', selected_work_ids=['OL3W','OL4W'])
    assert not result.clarification and [b.work_id for b in result.books] == ['OL2W']


def test_explicit_literal_work_id_survives_title_precedence_guard():
    orch, tools = setup(Intent.BOOK_DETAILS)
    orch.qwen.parse = AsyncMock(return_value=AssistantIntentDecision(intent=Intent.BOOK_DETAILS,
        confidence=1,reference_scope=ReferenceScope.SELECTED_BOOKS,mentioned_titles=['Frankenstein'],resolved_work_ids=['OL2W']))
    tools.catalogue.resolve = AsyncMock(side_effect=AssertionError('Literal canonical ID needs no title lookup'))
    result = chat(orch, tools, 'tell me about Frankenstein OL2W', selected_work_ids=['OL3W','OL4W'])
    assert not result.clarification and [b.work_id for b in result.books] == ['OL2W']


def test_named_work_help_with_selection_uses_catalogue_override():
    orch, tools = setup(Intent.GENERAL_LIBRARY_HELP)
    orch.qwen.parse = AsyncMock(return_value=AssistantIntentDecision(intent=Intent.GENERAL_LIBRARY_HELP,
        confidence=1,reference_scope=ReferenceScope.EXPLICIT_BOOK,mentioned_titles=['Frankenstein'],goal=SemanticGoal.DETAIL))
    orch.qwen.respond = AsyncMock(side_effect=AssertionError('Named work uses catalogue authority'))
    result = chat(orch, tools, 'tell me about Frankenstein', selected_work_ids=['OL3W','OL4W'])
    assert result.intent == Intent.BOOK_DETAILS and [b.work_id for b in result.books] == ['OL2W']


def assert_structured_operation(intent):
    orch, tools = setup(intent, query='databases' if intent==Intent.SEARCH_BOOKS else None)
    orch.qwen.respond = AsyncMock(side_effect=AssertionError('No conversational answer on a structured route'))
    selected_ids = ['OL2W'] if intent in {Intent.BOOK_CONTENT_QUESTION,Intent.BORROW_BOOK} else PAIR
    result = chat(orch, tools, 'structured operation', selected_work_ids=selected_ids)
    assert not result.errors and result.intent == intent
    if intent==Intent.USER_LOANS: assert result.account is not None
    if intent==Intent.SEARCH_BOOKS: tools.search.search.assert_awaited_once()
    if intent==Intent.COMPARE_BOOKS: assert result.comparison is not None
    if intent==Intent.CHECK_AVAILABILITY: assert result.availability
    if intent==Intent.BOOK_CONTENT_QUESTION: tools.rag.ask.assert_awaited_once(); assert result.rag
    if intent in {Intent.BORROW_BOOK,Intent.ADD_TO_READING_LIST}: assert result.pending_action
    orch.qwen.respond.assert_not_awaited()


def test_account_query_ignores_selection_when_unrelated(): assert_structured_operation(Intent.USER_LOANS)
def test_search_query_ignores_selection_when_unrelated(): assert_structured_operation(Intent.SEARCH_BOOKS)
def test_structured_comparison_still_uses_tool(): assert_structured_operation(Intent.COMPARE_BOOKS)
def test_availability_still_uses_core(): assert_structured_operation(Intent.CHECK_AVAILABILITY)
def test_selected_content_question_does_not_bypass_rag(): assert_structured_operation(Intent.BOOK_CONTENT_QUESTION)
def test_selected_recommendation_still_uses_tools(): assert_structured_operation(Intent.RECOMMEND_FROM_SELECTION)
def test_selected_borrow_keeps_confirmation(): assert_structured_operation(Intent.BORROW_BOOK)
def test_selected_reading_list_keeps_confirmation(): assert_structured_operation(Intent.ADD_TO_READING_LIST)


def test_metadata_packet_is_bounded_and_excludes_private_stock_and_content_data():
    book=Book(work_id='OL1W',title='t'*2000,authors=['a'*1000]*50,subjects=['s'*1000]*50,
              description='d'*20000,available_copies=10,shelf_location='Private note')
    packet=metadata_packet([book]*10)
    assert len(packet)==4 and len(json.dumps(packet))<10000
    assert set(packet[0])=={'position','title','authors','subjects','description'}
    assert len(packet[0]['title'])==200 and len(packet[0]['description'])==1200
    assert len(packet[0]['subjects'])==8 and len(packet[0]['authors'])==4


def test_selected_context_prompt_only_metadata_and_one_response_generation():
    gateway=QwenGateway.__new__(QwenGateway); gateway.generate=AsyncMock(return_value='{"facts":["1_title","2_title"],"limitation":"NOT_ESTABLISHED"}')
    _, orch, tools = selected()
    result = chat(orch, tools, 'current question', selected_work_ids=PAIR)
    answer = asyncio.run(gateway.respond('current question',result))
    assert 'Dracula' in answer and 'Frankenstein' in answer and 'does not establish' in answer
    gateway.generate.assert_awaited_once()
    prompt=gateway.generate.call_args.args[0]
    assert 'ONLY factual source' in prompt and 'Dracula' in prompt and 'Frankenstein' in prompt
    assert 'do not claim to have read' in prompt and 'publication' not in json.dumps(metadata_packet(result.books))
    assert gateway.generate.call_args.kwargs['max_new_tokens']==128
    schema = gateway.generate.call_args.kwargs['schema'].model_json_schema()
    assert '1_title' in schema['properties']['facts']['items']['enum']


def test_invalid_selected_prose_envelope_fails_closed():
    gateway=QwenGateway.__new__(QwenGateway); gateway.generate=AsyncMock(return_value='{"facts":["1_title"],"limitation":"NONE","invented":true}')
    result, _, _ = selected()
    with pytest.raises(QwenUnavailable): asyncio.run(gateway.respond('current question', result))


def test_missing_field_cannot_be_selected_as_answer_evidence():
    books = [Book(work_id='A',title='Atomic Habits',authors='James Clear'),
             Book(work_id='B',title='Atomic Habits, Other Titles Collection',authors='James Clear | Another Writer')]
    _, facts = evidence_packet(books)
    assert '2_description' not in facts and '1_2_title_overlap' in facts and '1_2_shared_authors' in facts
    allowed = answer_schema(facts).model_json_schema()['properties']['facts']['items']['enum']
    assert '2_description' not in allowed
    with pytest.raises(ValueError):
        render_answer(SelectedContextAnswer(facts=['2_description'],limitation='NONE'),books,facts)


def test_answer_facts_are_copied_from_current_authoritative_metadata():
    books = [Book(work_id='A',title='Alpha',authors='One'),Book(work_id='B',title='Beta',authors='Two')]
    _, facts = evidence_packet(books)
    answer = render_answer(SelectedContextAnswer(facts=['1_authors','2_authors'],limitation='INFERENCE'),books,facts)
    assert 'One' in answer and 'Two' in answer and 'Alpha' in answer and 'Beta' in answer
    assert 'inference' in answer


def test_contrast_observations_distinguish_metadata_without_inventing_content():
    books = [Book(work_id='A', title='Alpha', authors='One', description='Recorded overview'),
             Book(work_id='B', title='Beta', authors='One | Two')]
    _, facts = evidence_packet(books)
    assert '1_2_different_authors' in facts and '1_2_description_coverage' in facts
    answer = render_answer(SelectedContextAnswer(facts=['1_2_different_authors', '1_2_description_coverage'], limitation='NONE'), books, facts)
    assert 'One | Two' in answer and 'has no recorded description' in answer
    assert 'does not establish a difference' in answer


def test_empty_metadata_has_bounded_unknown_answer_without_title_search():
    books = [Book(work_id='A')]
    _, facts = evidence_packet(books)
    assert list(facts) == ['metadata_absent']
    assert 'About “A”' in render_answer(SelectedContextAnswer(facts=['metadata_absent'],limitation='NOT_ESTABLISHED'), books, facts)


def test_router_prompt_uses_semantic_contract_not_reported_sentence():
    gateway=QwenGateway.__new__(QwenGateway);gateway.generate=AsyncMock(return_value='{"i":"help","c":1,"s":"selected","g":"explain"}')
    result=asyncio.run(gateway.parse('an unseen free-form question',{'selected_count':2,'selected_books':[]}))
    assert result.intent==Intent.GENERAL_LIBRARY_HELP and result.reference_scope==ReferenceScope.SELECTED_BOOKS
    prompt=gateway.generate.call_args.args[0]
    assert 'explicit user-provided book context' in prompt and 'why are these named similarly' not in prompt
    assert prompt.endswith('CURRENT REQUEST: "an unseen free-form question"')
