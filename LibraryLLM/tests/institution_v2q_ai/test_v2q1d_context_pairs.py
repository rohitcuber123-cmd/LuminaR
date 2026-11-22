"""Canonical contextual pairs remain bound to one existing authorized pool."""
import asyncio,json
from types import SimpleNamespace
import pytest
from assistant.qwen import QwenGateway,validated_intent
from assistant.schemas import AssistantRequest
from assistant.semantic import contextual_ids

def test_recent_pair_demonstration_copies_only_ordered_context_ids():
 context={'active_result_context':{'work_ids':['OL1W','OL2W','OL3W']}}
 examples=QwenGateway._reference_examples(context)
 assert examples['Compare the first and third.']['w']==['OL1W','OL3W']
 assert examples['Compare the first and third.']['s']=='recent'
 assert 'e' not in examples['Compare the first and third.']

@pytest.mark.parametrize('ids,accepted',[(['OL1W','OL3W'],True),(['OL999W','OL3W'],False)])
def test_canonical_pair_still_enforces_the_original_pool(ids,accepted):
 request=AssistantRequest(message='Compare the first and third.',recent_work_ids=['OL1W','OL2W','OL3W'])
 state=SimpleNamespace(active_result_work_ids=None,recent_result_work_ids=[],last_comparison_work_ids=[],last_recommendation_work_ids=[],last_referenced_work_ids=[],awaiting_criteria=False)
 decision=validated_intent(json.dumps({'i':'compare','c':1,'s':'recent','w':ids,'g':'facts'}))
 if accepted:assert contextual_ids(request,decision,state)==ids
 else:
  with pytest.raises(ValueError):contextual_ids(request,decision,state)


def test_id_decoding_is_finite_without_weakening_full_validation():
    from assistant.qwen import CompactAssistantDecodingSchema,contextual_decoding_schema
    context={'active_result_context':{'work_ids':['OL1W','OL2W','OL3W']}}
    schema=contextual_decoding_schema(CompactAssistantDecodingSchema,'Compare these with OL9W',context).model_json_schema()
    assert set(schema['properties']['w']['items']['enum'])=={'OL1W','OL2W','OL3W','OL9W'}
    assert schema['properties']['w']['maxItems']==4
    assert 'o' not in schema['properties']
    assert 'pattern' in CompactAssistantDecodingSchema.model_json_schema()['properties']['w']['items']
    with pytest.raises(ValueError):validated_intent('{"i":"compare","c":1,"s":"recent","w":["bad id"]}')


def test_empty_context_keeps_existing_literal_title_resolution_schema():
    from assistant.qwen import CompactAssistantDecodingSchema,contextual_decoding_schema
    assert contextual_decoding_schema(CompactAssistantDecodingSchema,'Tell me about a named title',{}) is CompactAssistantDecodingSchema


def test_unbound_pronoun_is_rejected_after_one_model_call():
    from assistant.schemas import Intent
    gateway=object.__new__(QwenGateway);calls=[]
    async def generate(*args,**kwargs):
        calls.append(args)
        return '{"i":"availability","s":"recent","c":1,"e":"THIRD"}'
    gateway.generate=generate
    result=asyncio.run(gateway.parse('Is that book available?',{'active_result_context':{'work_ids':['OL1W','OL2W','OL3W']}}))
    assert result.intent==Intent.CLARIFICATION
    assert result.reference_scope.value=='AMBIGUOUS'
    assert len(calls)==1


def test_local_seed_discovery_and_unspecified_choice_use_existing_routes():
    ids=['11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222']
    context={'active_result_context':{'work_ids':ids}}
    examples=QwenGateway._reference_examples(context)
    assert examples['Show books similar to the last one.']=={'i':'seed_recommend','c':1,'s':'recent','e':'LAST','g':'discover'}
    assert examples['Which recommendation should I choose?']['d']=='criteria'
    assert examples['Which recommendation should I choose?']['g']=='preference'


@pytest.mark.parametrize('focus,position,blocked',[
    ([], 'THIRD', True),(['OL2W'],'THIRD',True),(['OL2W'],'SECOND',False),(['OL2W'],'FOCUS',False)])
def test_deictic_binding_cannot_invent_a_position(focus,position,blocked):
    from assistant.qwen import ambiguous_deictic_reference
    context={'active_result_context':{'work_ids':['OL1W','OL2W','OL3W']},'last_referenced_work_ids':focus}
    decision=validated_intent(json.dumps({'i':'availability','s':'recent','c':1,'e':position,'g':'status'}))
    assert ambiguous_deictic_reference('Is that book available?',context,decision) is blocked
    assert not ambiguous_deictic_reference('Is that book, the third one, available?',context,decision)


def test_deictic_single_page_and_explicit_title_remain_supported():
    from assistant.qwen import ambiguous_deictic_reference
    decision=validated_intent('{"i":"availability","s":"page","c":1,"e":"ALL"}')
    assert not ambiguous_deictic_reference('Is this book available?',{'page_books':[{'work_id':'OL1W'}]},decision)
    decision=validated_intent('{"i":"availability","s":"explicit","c":1,"t":["Dune"]}')
    assert not ambiguous_deictic_reference('Is that book Dune available?',{},decision)


def test_literal_id_remains_explicit_even_when_model_uses_recent_scope():
    from assistant.qwen import ambiguous_deictic_reference
    context={'active_result_context':{'work_ids':['OL1W','OL2W','OL3W']}}
    decision=validated_intent('{"i":"availability","s":"recent","c":1,"w":["OL2W"]}')
    assert not ambiguous_deictic_reference('Is that book OL2W available?',context,decision)
    assert ambiguous_deictic_reference('Is that book available?',context,decision)


def test_unseeded_topic_discovery_is_not_a_singular_book_binding():
    from assistant.qwen import ambiguous_deictic_reference
    decision=validated_intent('{"i":"search","s":"none","c":1,"q":"algorithms","g":"discover"}')
    assert not ambiguous_deictic_reference('Show books about this one algorithm',{},decision)


def test_existing_none_scope_single_book_fallback_is_not_rejected():
    from assistant.qwen import ambiguous_deictic_reference
    decision=validated_intent('{"i":"availability","s":"none","c":1,"e":"FIRST"}')
    assert not ambiguous_deictic_reference('Is that book available?',{'active_result_context':{'work_ids':['OL1W']}},decision)
    assert ambiguous_deictic_reference('Is that book available?',{'active_result_context':{'work_ids':['OL1W','OL2W']}},decision)


def test_deictic_safety_uses_the_resolvers_existing_selection_precedence():
    from assistant.qwen import ambiguous_deictic_reference
    decision=validated_intent('{"i":"availability","s":"page","c":1,"e":"ALL"}')
    context={'selected_books':[{'work_id':'OL1W'},{'work_id':'OL2W'}],'page_books':[{'work_id':'OL3W'}]}
    assert ambiguous_deictic_reference('Is this book available?',context,decision)
