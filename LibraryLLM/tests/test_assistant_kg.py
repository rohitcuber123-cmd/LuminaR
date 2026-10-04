from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from test_assistant_backend import setup, chat
from assistant.schemas import Intent


@pytest.mark.parametrize('message', ['more like this','show related books','what books are connected to this?',
                                     'show books connected to this','find related books'])
@pytest.mark.parametrize('context', [{'selected_work_ids':['OL1W']},{'page_context':{'work_id':'OL1W'}}])
def test_graph_natural_language_zero_qwen(message,context):
    orch,tools=setup(Intent.MORE_LIKE_THIS)
    orch.qwen.parse=AsyncMock(return_value=orch.qwen.intent)
    orch.qwen.respond=AsyncMock(side_effect=AssertionError('Qwen forbidden'))
    tools.recommendation.recommend=AsyncMock(side_effect=AssertionError('Seeded recommender forbidden'))
    tools.kg=SimpleNamespace(more_like_this=AsyncMock(return_value={'seed_work_id':'OL1W','graph_version':'v1','recommendations':[{'work_id':'OL2W','title':'Live book','available_copies':2,'total_copies':3,'reason_paths':[]}]}))
    response=chat(orch,tools,message,**context)
    assert response.intent=='MORE_LIKE_THIS' and response.seed_work_ids==['OL1W'] and not response.errors
    assert response.books[0].work_id=='OL2W' and response.kg['graph_version']=='v1'
    orch.qwen.parse.assert_awaited_once();orch.qwen.respond.assert_not_awaited()
    tools.recommendation.recommend.assert_not_awaited()


@pytest.mark.parametrize('context', [{},{'selected_work_ids':['OL1W','OL2W']}])
def test_graph_requires_one_current_source_without_qwen(context):
    orch,tools=setup(Intent.MORE_LIKE_THIS)
    orch.qwen.parse=AsyncMock(return_value=orch.qwen.intent)
    response=chat(orch,tools,'more like this',**context)
    assert response.intent=='CLARIFICATION' and not response.errors
    orch.qwen.parse.assert_awaited_once()


def test_structured_more_like_this_action_and_failure_without_fallback():
    from assistant.tools import ToolFailure
    orch,tools=setup();orch.qwen.parse=AsyncMock(side_effect=AssertionError('Qwen forbidden'))
    tools.kg=SimpleNamespace(more_like_this=AsyncMock(side_effect=ToolFailure('core','HTTP_409','Related-book data for this title is being refreshed.')))
    response=chat(orch,tools,'More Like This',action='MORE_LIKE_THIS',page_context={'work_id':'OL1W'})
    assert response.errors[0].code=='HTTP_409' and tools.calls==[]
    orch.qwen.parse.assert_not_awaited()


def test_existing_compact_intent_wire_codes_are_preserved():
    from assistant.qwen import INTENT_CODES, validated_intent
    from assistant.schemas import Intent
    assert INTENT_CODES[Intent.SEARCH_BOOKS]=='search'
    assert INTENT_CODES[Intent.UNKNOWN]=='unknown'
    assert validated_intent('{"i":"search","c":1,"q":"databases"}').intent==Intent.SEARCH_BOOKS
