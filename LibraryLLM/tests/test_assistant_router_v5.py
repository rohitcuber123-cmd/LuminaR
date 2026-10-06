"""Authority, one-call fallback, transport reuse and worker ownership boundaries."""
import ast
import asyncio
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from router_v5_data import context,A,B,C,D
from assistant.router_v5.binding import make_plan,model_payload,eligible,decision
from assistant.router_v5.gateway import fallback,select,shortlist
from assistant.router_v5.contracts import BY_ID,registry_hash
from assistant.router_v5.worker import CPUWorker,RouterOverloaded

@pytest.mark.parametrize('kind,ids,source',[
    ('selection',[A,B],'SELECTED_BOOKS'),('previous',[A,B],'PREVIOUS_COMPARISON'),
    ('previous_focus',[A,B],'PREVIOUS_COMPARISON'),('changed',[C,D],'SELECTED_BOOKS'),
    ('recommendations',[C,D],'PREVIOUS_RECOMMENDATIONS'),('page',[A],'CURRENT_PAGE_BOOK'),
    ('empty_results',[],'AMBIGUOUS')])
def test_authority_precedence(kind,ids,source):
    p=make_plan(context(kind),'compare them')
    assert list(p.ids)==ids and p.source.value==source
    if kind=='changed':assert not p.focus

def test_structured_arguments_override_all_other_sources():
    ctx=context('changed');ctx['structured_action_work_ids']=[B]
    p=make_plan(ctx,'Describe Gardens Beyond the River')
    assert p.ids==(B,) and p.literal

def test_literal_title_overrides_current_selection_and_stale_pair():
    p=make_plan(context('changed'),'Please describe The Lantern Coast')
    assert p.ids==(A,) and p.source.value=='EXPLICIT_BOOK'

def test_exact_titles_require_boundaries():
    ctx=context('selection')
    p=make_plan(ctx,'describe The Lantern Coastline')
    assert p.ids==(A,B) and not p.literal

def test_private_identifiers_never_enter_worker_payload():
    ctx=context('changed');ctx['document_id']='PRIVATE_DOC';ctx['structured_action_work_ids']=[A]
    payload=model_payload(f'{A} {B} {C} {D} PRIVATE_DOC OL123456W',make_plan(ctx,f'{A} {B} {C} {D} PRIVATE_DOC OL123456W'))
    text=json.dumps(payload)
    assert all(value not in text for value in [A,B,C,D,'PRIVATE_DOC','OL123456W'])
    assert not any(key in payload for key in ['user_id','document_id','selected_work_ids','page_books'])

def test_capabilities_eliminate_impossible_source_access():
    ctx=context('none');ctx['authenticated']=False
    allowed=eligible(make_plan(ctx))
    assert not any(k.startswith('ACCOUNT_') for k in allowed)
    assert 'DOCUMENT_QUESTION' not in allowed and 'BOOK_CONTENT_QUESTION' not in allowed
    assert 'DOCUMENT_QUESTION' in eligible(make_plan(context('document')))
    assert 'BOOK_CONTENT_QUESTION' in eligible(make_plan(context('book_access')))

@pytest.mark.parametrize('position,focus,expected',[
    ('FIRST',[],[A]),('SECOND',[],[B]),('LAST',[],[B]),('OTHER',[A],[B]),('FOCUS',[B],[B])])
def test_positions_are_resolved_against_server_ids(position,focus,expected):
    out=decision('BOOK_DETAILS',make_plan(context('selection',focus)),'details',position)
    assert out.resolved_work_ids==expected

def test_other_without_focus_clarifies_instead_of_choosing():
    out=decision('BOOK_DETAILS',make_plan(context('selection')),'other','OTHER')
    assert out.intent.value=='CLARIFICATION' and not out.resolved_work_ids

@pytest.mark.parametrize('key',['BORROW','RETURN','RESERVE','ADD_READING_LIST','REMOVE_READING_LIST','CLEAR_READING_LIST'])
def test_mutations_always_remain_confirmation_proposals(key):
    out=decision(key,make_plan(context('page')),'perform it','FOCUS')
    assert out.requires_confirmation

def test_criterion_absence_is_deterministic():
    out=decision('COMPARE_PREFERENCE',make_plan(context('selection')),'choose one')
    assert out.clarification_type.value=='CRITERIA_AMBIGUITY'
    assert out.resolved_work_ids==[A,B]

def test_live_enum_history_preserves_the_previous_semantic_meaning():
    from assistant.schemas import Intent
    ctx=context('previous');ctx['last_intent']=Intent.CHECK_AVAILABILITY
    payload=model_payload('and the other?',make_plan(ctx))
    assert payload['last_meaning']==BY_ID['CHECK_AVAILABILITY'].meaning

def test_search_preserves_the_original_request():
    text='Need introductory books about molluscs, please.'
    out=decision('CATALOGUE_TOPIC_SEARCH',make_plan(context('selection')),text)
    assert out.query==text and not out.resolved_work_ids and not out.mentioned_titles

class Qwen:
    def __init__(self,raw):self.raw=raw;self.calls=[]
    async def generate(self,prompt,schema,stage):
        self.calls.append(prompt);return self.raw

def prediction(keys):
    return {'methods':{'C':[{'id':k,'score':1-i*.1} for i,k in enumerate(keys)]}}

@pytest.mark.parametrize('raw',[
    '{"a":"BOOK_DETAILS","t":"Invented unrelated novel"}',
    '{"a":"BOOK_DETAILS","t":"it"}',
    '{"a":"BOOK_DETAILS","work_id":"OL999W"}',
    'invalid json'])
def test_one_call_rejects_invented_generic_or_id_entities(raw):
    q=Qwen(raw);out,info=asyncio.run(fallback(q,'tell me about it',make_plan(context('selection')),prediction(['BOOK_DETAILS'])))
    assert len(q.calls)==1 and out.intent.value=='CLARIFICATION'

def test_literal_named_entity_can_be_extracted_without_model_ids():
    q=Qwen('{"a":"BOOK_DETAILS","t":"Dracula"}')
    out,info=asyncio.run(fallback(q,'Tell me about Dracula',make_plan(context('selection')),prediction(['BOOK_DETAILS'])))
    assert out.mentioned_titles==['Dracula'] and not out.resolved_work_ids
    assert info['entity_extraction_used']

def test_shortlist_is_bounded_even_while_awaiting_criterion():
    ctx=context('selection');ctx['awaiting_criteria']=True
    keys=shortlist(prediction(list(BY_ID)),make_plan(ctx))
    assert len(keys)==4 and 'COMPARE_PREFERENCE' in keys

def test_prompt_contains_no_private_identity_or_work_ids():
    q=Qwen('{"a":"CHECK_AVAILABILITY"}')
    asyncio.run(fallback(q,'check them',make_plan(context('selection')),prediction(['CHECK_AVAILABILITY'])))
    assert A not in q.calls[0] and B not in q.calls[0]
    assert 'The Lantern Coast' in q.calls[0]

def test_verifier_disagreement_falls_back():
    p=prediction(['BOOK_DETAILS','CHECK_AVAILABILITY']);p['methods']['D']=[{'id':'CHECK_AVAILABILITY','score':4},{'id':'BOOK_DETAILS','score':1}]
    out,reason,_=select(p,make_plan(context('page')),'status',{'method':'D'})
    assert out is None and reason=='VERIFIER_DISAGREEMENT'

def test_filter_extraction_rejects_missing_arguments():
    q=Qwen('{"a":"REFINE_RESULTS"}')
    out,_=asyncio.run(fallback(q,'filter these by author',make_plan(context('results')),prediction(['REFINE_RESULTS'])))
    assert out.intent.value=='CLARIFICATION'

def test_filter_extraction_keeps_author_literal_and_sort_bounded():
    q=Qwen('{"a":"REFINE_RESULTS","o":"rating","v":true}')
    out,_=asyncio.run(fallback(q,'sort by rating, only available',make_plan(context('results')),prediction(['REFINE_RESULTS'])))
    assert out.context_operation=='REFINE_RESULTS' and out.filters.available_only and out.filters.sort_preference=='rating'

def test_chat_reuses_lifespan_transport_with_request_local_bearer():
    tree=ast.parse((ROOT/'assistant/api.py').read_text())
    chat=next(n for n in ast.walk(tree) if isinstance(n,ast.AsyncFunctionDef) and n.name=='chat')
    assert not any(isinstance(n,ast.Call) and ast.unparse(n.func)=='httpx.AsyncClient' for n in ast.walk(chat))
    text=ast.unparse(chat)
    assert 'AssistantTools(client' in text and 'credentials.credentials' in text
    source=(ROOT/'assistant/api.py').read_text()
    assert source.count('httpx.AsyncClient(')==1 and 'max_connections=40, max_keepalive_connections=20' in source

def test_frozen_contract_hash_and_no_trained_heads():
    seal=json.loads((ROOT/'reports/assistant_router_v5_contract_meanings_seal.json').read_text())
    assert registry_hash()==seal['registry_sha256']
    text=(ROOT/'assistant/router_v5/matcher.py').read_text()
    assert 'requires_grad_(False)' in text and "device='cpu'" in text and 'local_files_only=True' in text
    assert all(s not in text for s in ['.fit(','.backward(', 'torch.nn.Linear','AutoModelForCausalLM'])

def test_real_worker_queue_bound_cancellation_and_request_isolation():
    async def run():
        worker=await asyncio.to_thread(CPUWorker,capacity=2,batch_size=2,batch_delay=.005)
        try:
            tasks=[asyncio.create_task(worker.predict('Check current free copies',context('selection'))),
                   asyncio.create_task(worker.predict('Inspect outstanding late penalties',context('changed')))]
            await asyncio.sleep(0)
            with pytest.raises(RouterOverloaded):await worker.predict('extra',context('none'))
            tasks[0].cancel()
            with pytest.raises(asyncio.CancelledError):await tasks[0]
            result=await tasks[1]
            serial=await worker.predict('Inspect outstanding late penalties',context('changed'))
            # Compare identity of the computation, independently of whether
            # the semantic model understands this particular sentence.
            assert result['prediction']['methods']['C'][0]['id']==serial['prediction']['methods']['C'][0]['id']
            assert result['prediction']['methods']['C'][0]['score']==pytest.approx(serial['prediction']['methods']['C'][0]['score'],abs=1e-6)
            await asyncio.sleep(.1)
            assert not worker.pending and worker.audit['cuda_allocated_bytes']==0 and not worker.audit['cuda_initialized']
        finally:worker.close()
    asyncio.run(run())

@pytest.mark.parametrize('key',['BORROW','RETURN','RESERVE'])
def test_circulation_executor_does_not_write_without_confirmation(key,monkeypatch):
    from assistant.orchestrator import AssistantOrchestrator
    from assistant.state import ConversationStore
    from assistant import schemas,tools as tool_module
    from evaluate_assistant_semantics import FixtureTools
    tools=FixtureTools(schemas,tool_module)
    tools.records[A]=schemas.Book(work_id=A,title='The Lantern Coast',available_copies=1,total_copies=1)
    writes=[]
    async def forbidden(*args,**kw):writes.append(True);raise AssertionError('No confirmation was supplied')
    async def loans(history=False):return {'issues':[{'work_id':A,'issue_id':1}]}
    tools.loans.loans=loans;tools.loans.borrow=forbidden;tools.loans.return_book=forbidden;tools.reservations.reserve=forbidden
    parsed=decision(key,make_plan(context('page')),'propose the transaction','FOCUS')
    class ParsedGateway:
        async def parse(self,*args):return parsed
        async def respond(self,message,response):return response.message
    monkeypatch.setenv('ASSISTANT_MUTATING_ACTIONS_ENABLED','true')
    orch=AssistantOrchestrator(ParsedGateway(),ConversationStore())
    response=asyncio.run(orch.chat(schemas.AssistantRequest(message='propose the transaction',page_context={'work_id':A}),'fixture-owner',tools))
    assert response.pending_action and response.pending_action.requires_confirmation and response.pending_action.work_id==A
    assert not writes and not response.errors
