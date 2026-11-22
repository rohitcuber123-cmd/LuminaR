"""Prompt/context isolation without changing semantic validation or adding model retries."""
import asyncio
import pytest
from assistant.qwen import QwenGateway

@pytest.mark.parametrize('context,scope',[
 ({'selected_books':[{'work_id':'OL1W'}],'active_result_context':{'work_ids':['OL2W']}},'selected'),
 ({'active_result_context':{'work_ids':['OL2W']}},'recent'),
 ({'page_books':[{'work_id':'OL3W'}]},'page'),
 ({},'ambiguous'),
])
def test_actual_context_examples_and_single_call(context,scope):
 gateway=object.__new__(QwenGateway);calls=[]
 async def generate(prompt,*args,**kwargs):
  calls.append(prompt)
  # Deliberately emit a scope inconsistent with the prompt. Parse must not
  # rewrite it or invoke a second generation to make the assertion pass.
  return '{"i":"availability","c":1,"s":"page","e":"SECOND","g":"status"}'
 gateway.generate=generate
 decision=asyncio.run(gateway.parse('Is the second one available?',context))
 assert len(calls)==1
 assert decision.reference_scope.value=='CURRENT_PAGE_BOOK'
 if not context.get('selected_books') and scope!='ambiguous':
  assert 'Examples (with a selected pair' not in calls[0]
 if scope!='ambiguous':assert '"populated_scope":"'+scope+'"' in calls[0]
 else:assert 'Find books about astronomy' in calls[0]
