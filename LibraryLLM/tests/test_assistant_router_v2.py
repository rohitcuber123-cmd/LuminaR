"""Structural boundaries and bounded retries, not phrase-routing mocks."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from assistant.router_v2 import (DecisionInvalid,decide,expand,family_model,
    flat_model,make_plan,prompt,strict_family_model)
from assistant.schemas import Intent,ReferenceScope,SemanticGoal


def context(count=2,**changes):
    return {'selected_books':[{'work_id':f'OL_{i}','title':f'Title {i}'} for i in range(count)],**changes}


def decision(data,ctx=None,message='request'):
    plan=make_plan(ctx if ctx is not None else context())
    return expand(flat_model(plan).model_validate(data),plan,message)


def test_ids_are_server_only_and_single_scope_has_no_model_choice():
    plan=make_plan(context())
    assert plan.primary=='S'
    for schema in (flat_model(plan),family_model(plan)):
        encoded=json.dumps(schema.model_json_schema())
        assert 'resolved_work_ids' not in encoded and 'reference_scope' not in encoded
        assert 'reference_handle' not in encoded
    rendered=prompt('compare my picks',plan,True)
    assert 'OL_0' not in rendered and 'OL_1' not in rendered
    assert 'Title 0' in rendered


def test_dynamic_capabilities_do_not_expose_document_or_list_clear():
    plan=make_plan(context())
    assert 'DOCUMENT_QUESTION' not in plan.intents and 'CLEAR_READING_LIST' not in plan.intents
    assert 'DOCUMENT_QUESTION' in make_plan(context(document_id='private')).intents
    assert 'document_id' not in json.dumps(make_plan(context(document_id='private')).context)


@pytest.mark.parametrize('count,positions',[(0,[]),(1,['FOCUS']),
    (2,['ALL','FIRST','SECOND']),(3,['ALL','FIRST','SECOND','THIRD','LAST']),
    (4,['ALL','FIRST','SECOND','THIRD','LAST','FOURTH'])])
def test_cardinality_bounded_positions(count,positions):
    assert make_plan(context(count)).positions==positions


def test_other_requires_a_known_single_focus_and_new_selection_clears_it():
    assert 'OTHER' not in make_plan(context()).positions
    plan=make_plan(context(last_referenced_work_ids=['OL_0']))
    assert 'OTHER' in plan.positions and 'FOCUS' in plan.positions
    output=expand(flat_model(plan).model_validate({'intent':'CHECK_AVAILABILITY','position':'OTHER'}),plan,'other')
    assert output.resolved_work_ids==['OL_1']
    assert 'OTHER' not in make_plan(context(last_referenced_work_ids=['OL_0'],selection_changed=True)).positions


def test_selection_precedes_previous_comparison_and_page():
    plan=make_plan(context(previous_comparison=[{'work_id':'STALE'}],
        active_result_context={'type':'comparison','work_ids':['STALE']},page_books=[{'work_id':'PAGE'}]))
    assert plan.primary=='S'
    result=expand(flat_model(plan).model_validate({'intent':'BOOK_DETAILS','position':'SECOND'}),plan,'request')
    assert result.resolved_work_ids==['OL_1']


def test_previous_comparison_without_selection_prebinds_c():
    ctx={'previous_comparison':[{'work_id':'A'},{'work_id':'B'}],
        'active_result_context':{'type':'comparison','work_ids':['A','B']}}
    plan=make_plan(ctx)
    assert plan.primary=='C' and 'S' not in plan.handles and 'P' not in plan.handles
    result=expand(flat_model(plan).model_validate({'intent':'CHECK_AVAILABILITY','position':'ALL'}),plan,'request')
    assert result.reference_scope==ReferenceScope.PREVIOUS_COMPARISON and result.resolved_work_ids==['A','B']


def test_page_without_selection_prebinds_p():
    result=decision({'intent':'CHECK_AVAILABILITY','position':'FOCUS'},
        {'page_books':[{'work_id':'PAGE','title':'Page title'}]})
    assert result.resolved_work_ids==['PAGE'] and result.reference_scope==ReferenceScope.CURRENT_PAGE_BOOK


@pytest.mark.parametrize('position,expected',[('FIRST','OL_0'),('SECOND','OL_1'),('THIRD','OL_2'),('FOURTH','OL_3'),('LAST','OL_3')])
def test_server_maps_supported_positions(position,expected):
    assert decision({'intent':'BOOK_DETAILS','position':position},context(4)).resolved_work_ids==[expected]


def test_literal_entity_can_override_current_selection():
    result=decision({'intent':'BOOK_DETAILS','entity_text':'Dune'},message='who wrote Dune?')
    assert result.reference_scope==ReferenceScope.EXPLICIT_BOOK and result.mentioned_titles==['Dune']
    assert not result.resolved_work_ids


@pytest.mark.parametrize('entity,message',[('Dune','who wrote this?'),('the other','tell me about the other'),('these','compare these')])
def test_unprovided_or_pronominal_entity_is_rejected(entity,message):
    with pytest.raises(DecisionInvalid):decision({'intent':'BOOK_DETAILS','entity_text':entity},message=message)


def test_account_cannot_reference_selected_books():
    with pytest.raises(DecisionInvalid):decision({'intent':'USER_FEES','position':'ALL'})
    plan=make_plan(context())
    result=expand(family_model(plan).model_validate({'intent_family':'ACCOUNT','action':'FEES'}),plan,'own charges')
    assert result.intent==Intent.USER_FEES and result.reference_scope==ReferenceScope.ACCOUNT and not result.resolved_work_ids
    with pytest.raises(ValueError):family_model(plan).model_validate({'intent_family':'ACCOUNT','action':'FEES','position':'ALL'})


def test_comparison_modes_and_known_criterion_consistency():
    result=decision({'intent':'COMPARE_BOOKS','compare_mode':'PREFERENCE','criterion':'novice reader'})
    assert result.goal==SemanticGoal.PREFERENCE_COMPARE and not result.clarification_needed
    result=decision({'intent':'COMPARE_BOOKS','compare_mode':'PREFERENCE'})
    assert result.clarification_needed and result.clarification_type=='CRITERIA_AMBIGUITY'
    for raw in [{'intent':'COMPARE_BOOKS','compare_mode':'FIELD'},
        {'intent':'COMPARE_BOOKS','compare_mode':'FACTUAL','criterion':'novice'},
        {'intent':'CHECK_AVAILABILITY','criterion':'novice'}]:
        with pytest.raises(DecisionInvalid):decision(raw)


def test_graph_requires_one_seed_and_comparison_requires_two():
    with pytest.raises(DecisionInvalid):decision({'intent':'MORE_LIKE_THIS','position':'ALL'})
    with pytest.raises(DecisionInvalid):decision({'intent':'COMPARE_BOOKS','compare_mode':'FACTUAL'},context(1))


@pytest.mark.parametrize('replies,expected_calls,clarify',[
    ([{'intent':'CHECK_AVAILABILITY','position':'ALL'}],1,False),
    ([{'intent':'MORE_LIKE_THIS','position':'ALL'},{'intent':'MORE_LIKE_THIS','position':'FIRST'}],2,False),
    ([{'intent':'MORE_LIKE_THIS','position':'ALL'},{'intent':'MORE_LIKE_THIS','position':'ALL'}],2,True),
    ([{'bad':'schema'},{'intent':'CHECK_AVAILABILITY','position':'ALL'}],2,False),
])
def test_retry_only_on_invalid_output_and_never_more_than_one(replies,expected_calls,clarify):
    gateway=SimpleNamespace(generate=AsyncMock(side_effect=[json.dumps(r) for r in replies]))
    result,telemetry=asyncio.run(decide(gateway,'request',context(),'D',retry=True))
    assert gateway.generate.await_count==expected_calls
    assert (result.intent==Intent.CLARIFICATION)==clarify
    assert telemetry['retry_used']==(expected_calls==2)
    if expected_calls==2:
        assert gateway.generate.await_args_list[1].args[2]=='semantic_retry'
        assert len(gateway.generate.await_args_list[1].args[0])<len(gateway.generate.await_args_list[0].args[0])


def test_no_retry_when_disabled():
    gateway=SimpleNamespace(generate=AsyncMock(return_value='{"intent":"MORE_LIKE_THIS","position":"ALL"}'))
    result,telemetry=asyncio.run(decide(gateway,'request',context(),'D',retry=False))
    assert gateway.generate.await_count==1 and result.intent==Intent.CLARIFICATION and not telemetry['retry_used']


@pytest.mark.parametrize('data',[
    {'intent_family':'ACCOUNT','action':'FEES'},
    {'intent_family':'COMPARE','compare_mode':'FACTUAL','position':'ALL'},
    {'intent_family':'COMPARE','compare_mode':'PREFERENCE','criterion':'novice','position':'ALL'},
    {'intent_family':'BOOK','action':'AVAILABILITY','position':'SECOND'},
    {'intent_family':'DISCOVER','action':'SEARCH','query':'soil science'},
])
def test_installed_enforcer_accepts_conditional_schema_branches(data):
    from lmformatenforcer import JsonSchemaParser
    parser=JsonSchemaParser(family_model(make_plan(context())).model_json_schema())
    for character in json.dumps(data,separators=(',',':')):
        assert character in parser.get_allowed_characters()
        parser=parser.add_character(character)
    assert parser.can_end()


def test_opt_in_production_gateway_uses_server_binding_and_one_routing_call(monkeypatch):
    from threading import RLock
    from assistant.qwen import QwenGateway
    monkeypatch.setenv('ASSISTANT_ROUTER_V2_VARIANT','E')
    gateway=QwenGateway(None,RLock())
    gateway.generate=AsyncMock(return_value='{"intent_family":"BOOK","action":"AVAILABILITY","position":"SECOND"}')
    try:
        result=asyncio.run(gateway.parse('request',context()))
        assert result.intent==Intent.CHECK_AVAILABILITY and result.resolved_work_ids==['OL_1']
        assert gateway.generate.await_count==1
    finally:gateway.close()


def test_mode_specific_schema_requires_relevant_fields_and_omits_position():
    schema=strict_family_model(make_plan(context()))
    with pytest.raises(ValueError):schema.model_validate({'intent_family':'COMPARE','compare_mode':'PREFERENCE'})
    with pytest.raises(ValueError):schema.model_validate({'intent_family':'COMPARE','compare_mode':'FIELD','fields':[]})
    with pytest.raises(ValueError):schema.model_validate({'intent_family':'COMPARE','compare_mode':'FACTUAL','criterion':'novice'})
    with pytest.raises(ValueError):schema.model_validate({'intent_family':'COMPARE','compare_mode':'FACTUAL','position':'FIRST'})
    parsed=schema.model_validate({'intent_family':'COMPARE','compare_mode':'PREFERENCE','criterion':'novice'})
    result=expand(parsed,make_plan(context()),'request')
    assert result.resolved_work_ids==['OL_0','OL_1'] and not result.clarification_needed


@pytest.mark.parametrize('data',[
    {'intent_family':'COMPARE','compare_mode':'FACTUAL'},
    {'intent_family':'COMPARE','compare_mode':'PREFERENCE','criterion':None},
    {'intent_family':'COMPARE','compare_mode':'PREFERENCE','criterion':'novice'},
    {'intent_family':'COMPARE','compare_mode':'FIELD','fields':['average_rating']},
    {'intent_family':'ACCOUNT','action':'LOANS'},
])
def test_installed_enforcer_accepts_strict_comparison_branches(data):
    from lmformatenforcer import JsonSchemaParser
    parser=JsonSchemaParser(strict_family_model(make_plan(context())).model_json_schema())
    for character in json.dumps(data,separators=(',',':')):
        assert character in parser.get_allowed_characters()
        parser=parser.add_character(character)
    assert parser.can_end()
