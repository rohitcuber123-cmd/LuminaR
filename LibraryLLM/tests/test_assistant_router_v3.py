"""V3 authority, fallback, privacy and real CPU worker concurrency contracts."""
import asyncio
import copy
import json
from pathlib import Path
import threading
from functools import wraps
from unittest.mock import Mock

import pytest
from assistant.router_v3 import (CPUWorker, HybridGateway, MODEL_DIR, Classifiers, RouterOverloaded,
    context_pool, features, structural_decision, FAMILIES)
from assistant.schemas import AssistantIntentDecision, Intent, ReferenceScope, SemanticGoal


def async_test(func):
    @wraps(func)
    def run(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))
    return run


def calibration():
    labels={'intent_family':set(FAMILIES.values()),'intent_subtypes':set(FAMILIES),
            'reference':{'SELECTION','PAGE','PREVIOUS_COMPARISON','PREVIOUS_RECOMMENDATIONS','RECENT','AMBIGUOUS','NONE','EXPLICIT'},
            'position':{'ALL','FIRST','SECOND','LAST','OTHER','FOCUS'},
            'fields':{'NONE','average_rating','rating_count','availability','subjects','authors','description'},
            'criterion':{'ABSENT','PRESENT'}}
    return {'ood_min_similarity':.1,'policies':{h:{x:{'confidence':.97,'margin':.1} for x in xs} for h,xs in labels.items()}}


def prediction(subtype,reference='SELECTION',position='ALL',field='NONE',criterion='ABSENT'):
    p={h:{'label':v,'confidence':.999,'margin':.999,'entropy':.001} for h,v in {
        'intent_family':FAMILIES[subtype],'intent_subtypes':subtype,'reference':reference,
        'position':position,'fields':field,'criterion':criterion}.items()}
    p['ood_similarity']=.8
    return p


def ctx(ids=('ONE','TWO')):
    return {'selected_books':[{'work_id':w} for w in ids]}


@pytest.mark.parametrize('subtype,reference,position,field,intent',[
    ('SEARCH','NONE','ALL','NONE',Intent.SEARCH_BOOKS),
    ('AVAILABILITY','SELECTION','FIRST','NONE',Intent.CHECK_AVAILABILITY),
    ('FACTUAL','SELECTION','ALL','NONE',Intent.COMPARE_BOOKS),
    ('FIELD','SELECTION','ALL','average_rating',Intent.COMPARE_BOOKS),
    ('LOANS','NONE','ALL','NONE',Intent.USER_LOANS),
    ('FEES','NONE','ALL','NONE',Intent.USER_FEES),
    ('RESERVATIONS','NONE','ALL','NONE',Intent.USER_RESERVATIONS),
    ('HISTORY','NONE','ALL','NONE',Intent.USER_HISTORY),
    ('READING_LIST','NONE','ALL','NONE',Intent.USER_READING_LIST),
    ('RECOMMEND','SELECTION','ALL','NONE',Intent.RECOMMEND_FROM_SELECTION),
    ('SIMILAR','SELECTION','SECOND','NONE',Intent.MORE_LIKE_THIS),
    ('DETAILS','SELECTION','SECOND','NONE',Intent.BOOK_DETAILS),
    ('PREFERENCE','SELECTION','ALL','NONE',Intent.COMPARE_BOOKS),
])
def test_authoritative_decisions_no_classifier_ids(subtype,reference,position,field,intent):
    result,reason=structural_decision(prediction(subtype,reference,position,field),ctx(),'unaltered search text',calibration())
    assert reason=='ACCEPTED' and result.intent==intent
    assert result.resolved_work_ids==[] and result.mentioned_titles==[]
    if subtype=='SEARCH':assert result.query=='unaltered search text'
    if subtype=='PREFERENCE':assert result.clarification_type.value=='CRITERIA_AMBIGUITY'


@pytest.mark.parametrize('subtype',['BORROW','RETURN','RESERVE','ADD_LIST','REMOVE_LIST','CLEAR_LIST'])
def test_mutations_always_require_fallback_and_existing_confirmation(subtype):
    decision,reason=structural_decision(prediction(subtype),ctx(),'request',calibration())
    assert decision is None and reason=='MUTATION_REQUIRES_QWEN_AND_CONFIRMATION'


@pytest.mark.parametrize('head',['intent_family','intent_subtypes','reference','position','fields','criterion'])
def test_threshold_rejects_uncertain_components(head):
    p=prediction('FIELD',field='subjects');p[head]['confidence']=.96
    result,reason=structural_decision(p,ctx(),'request',calibration())
    assert result is None and reason.startswith('LOW_CONFIDENCE')


def test_agreement_ood_freeform_and_invalid_context():
    p=prediction('AVAILABILITY');p['intent_family']['label']='ACCOUNT'
    assert structural_decision(p,ctx(),'x',calibration())[1]=='CONFLICTING_CLASSIFIERS'
    p=prediction('AVAILABILITY');p['ood_similarity']=.01
    assert structural_decision(p,ctx(),'x',calibration())[1]=='OUT_OF_DISTRIBUTION'
    assert structural_decision(prediction('PREFERENCE',criterion='PRESENT'),ctx(),'x',calibration())[1]=='FREEFORM_CRITERION_REQUIRED'
    assert structural_decision(prediction('DETAILS',reference='EXPLICIT'),ctx(),'x',calibration())[1]=='EXPLICIT_ENTITY_EXTRACTION_REQUIRED'
    assert structural_decision(prediction('DETAILS'),ctx(),'x',calibration())[1]=='CONTEXT_INVALID_CARDINALITY'
    assert structural_decision(prediction('AVAILABILITY',position='SECOND'),ctx(('ONE',)),'x',calibration())[1]=='CONTEXT_INVALID_POSITION'
    assert structural_decision(prediction('AVAILABILITY',reference='PAGE'),ctx(),'x',calibration())[1]=='CONTEXT_INVALID_REFERENCE'


def test_live_precedence_and_empty_result_authority():
    c=ctx(('C','D'));c['previous_comparison']=[{'work_id':'A'},{'work_id':'B'}];c['page_books']=[{'work_id':'P'}]
    assert context_pool(c)==('SELECTION',['C','D'])
    c.pop('selected_books');assert context_pool(c)==('PREVIOUS_COMPARISON',['A','B'])
    c.pop('previous_comparison');assert context_pool(c)==('PAGE',['P'])
    c={'active_result_context':{'type':'search','work_ids':[]},'last_referenced_work_ids':['STALE']}
    assert context_pool(c)==('AMBIGUOUS',[])


def test_feature_privacy_identity_invariance():
    a=ctx();b=ctx(('SECRET_USER_A','SECRET_USER_B'))
    b['selected_books'][0].update(title='PRIVATE TITLE',description='private document',authors='Someone')
    assert features(a).tolist()==features(b).tolist()
    assert len(features(a))==24


def test_original_search_query_contract_and_account_authentication():
    query='  Unmodified query with Unicode café and punctuation?!  '
    d,reason=structural_decision(prediction('SEARCH',reference='NONE'),{},query,calibration())
    assert d.query==query
    assert structural_decision(prediction('SEARCH',reference='NONE'),{},'x'*2001,calibration())[1]=='QUERY_CONTRACT_LIMIT'
    assert structural_decision(prediction('FEES',reference='NONE'),{'authenticated':False},'x',calibration())[1]=='CONTEXT_AUTHENTICATION_REQUIRED'


class FakeWorker:
    def __init__(self,p):self.p=p
    async def predict(self,message,context):return {'prediction':self.p,'queue_ms':0,'encoder_ms':1,'batch_size':1}
    def close(self):pass


class FakeQwen:
    def __init__(self,result=None):self.calls=0;self.result=result or AssistantIntentDecision(intent=Intent.BOOK_DETAILS)
    async def parse(self,message,context):self.calls+=1;return self.result
    def close(self):pass


def gateway(qwen,p,mode='router_v3'):
    # Test policy independently of local trained artifact confidence.
    g=object.__new__(HybridGateway);g.qwen=qwen;g.worker=FakeWorker(p);g.mode=mode;g.calibration=calibration();return g


@async_test
async def test_accepted_route_zero_qwen_even_while_gpu_lock_held():
    lock=threading.Lock();lock.acquire();qwen=FakeQwen()
    g=gateway(qwen,prediction('FACTUAL'))
    result=await asyncio.wait_for(g.parse('compare this pair',ctx()),.1)
    assert result.intent==Intent.COMPARE_BOOKS and qwen.calls==0
    lock.release()


@async_test
async def test_uncertain_fallback_exactly_one_no_prose():
    qwen=FakeQwen();p=prediction('DETAILS',position='FIRST');p['intent_subtypes']['confidence']=.5
    g=gateway(qwen,p)
    result=await g.parse('request',ctx())
    assert qwen.calls==1 and result.intent==Intent.BOOK_DETAILS


@async_test
async def test_pronoun_cannot_be_resolved_as_title():
    qwen=FakeQwen(AssistantIntentDecision(intent=Intent.BOOK_DETAILS,reference_scope=ReferenceScope.EXPLICIT_BOOK,mentioned_titles=['the remaining member']))
    p=prediction('DETAILS',position='OTHER');p['intent_subtypes']['confidence']=.5
    result=await gateway(qwen,p).parse('explain the remaining member',ctx())
    assert result.intent==Intent.CLARIFICATION and result.mentioned_titles==[] and qwen.calls==1


@async_test
@pytest.mark.parametrize('literal',[True,False])
async def test_fallback_literal_identifier_is_grounded_before_authority(literal):
    qwen=FakeQwen(AssistantIntentDecision(intent=Intent.BOOK_DETAILS,reference_scope=ReferenceScope.EXPLICIT_BOOK,
                                        resolved_work_ids=['OL123W']))
    p=prediction('DETAILS',position='FIRST');p['intent_subtypes']['confidence']=.4
    message='Show details for OL123W' if literal else 'Show details for this book'
    result=await gateway(qwen,p).parse(message,ctx())
    assert result.intent==(Intent.BOOK_DETAILS if literal else Intent.CLARIFICATION)
    assert qwen.calls==1 and result.mentioned_titles==[]


@async_test
async def test_shadow_returns_existing_decision_one_call():
    qwen=FakeQwen(AssistantIntentDecision(intent=Intent.UNKNOWN))
    result=await gateway(qwen,prediction('FACTUAL'),'router_v3_shadow').parse('request',ctx())
    assert result.intent==Intent.UNKNOWN and qwen.calls==1


@async_test
async def test_shadow_never_waits_for_classifier_queue():
    gate=asyncio.Event()
    class SlowWorker(FakeWorker):
        async def predict(self,*args):
            await gate.wait();return await super().predict(*args)
    qwen=FakeQwen(AssistantIntentDecision(intent=Intent.UNKNOWN));g=gateway(qwen,prediction('FACTUAL'),'router_v3_shadow')
    g.worker=SlowWorker(prediction('FACTUAL'))
    result=await asyncio.wait_for(g.parse('request',ctx()),.05)
    assert result.intent==Intent.UNKNOWN and qwen.calls==1
    gate.set();await asyncio.gather(*g.shadow_tasks)


@async_test
@pytest.mark.parametrize('n',[5,10,20])
async def test_parallel_authority_isolated(n):
    from assistant.semantic import contextual_ids
    from assistant.schemas import AssistantRequest
    from assistant.state import ConversationStore
    qwen=FakeQwen();g=gateway(qwen,prediction('AVAILABILITY',position='FIRST'))
    async def user(i):
        ids=[f'USER_{i}_A',f'USER_{i}_B'];c=ctx(ids)
        decision=await g.parse('check the first one',c)
        req=AssistantRequest(message='check the first one',selected_work_ids=ids)
        store=ConversationStore();state=store.get(None,str(i))
        return contextual_ids(req,decision,state)
    assert await asyncio.gather(*(user(i) for i in range(n)))==[[f'USER_{i}_A'] for i in range(n)]
    assert qwen.calls==0


@async_test
async def test_bounded_admission_cancel_shutdown_without_loading_model():
    from concurrent.futures import Future
    import queue
    w=object.__new__(CPUWorker);w.pending={};w.lock=threading.Lock();w.capacity=1;w.closed=False;w.requests=queue.Queue(1)
    running=asyncio.create_task(w.predict('request',ctx(),timeout=.05));await asyncio.sleep(.01)
    with pytest.raises(RouterOverloaded):await w.predict('second',ctx())
    with pytest.raises(asyncio.TimeoutError):await running
    assert len(w.pending)==1  # cancellation cannot bypass the queue's bound
    w._fail_pending(RuntimeError('shutdown'));assert not w.pending


def test_weights_only_artifact_and_metadata_integrity(tmp_path):
    import shutil
    for p in MODEL_DIR.iterdir():shutil.copy2(p,tmp_path/p.name)
    (tmp_path/'labels.json').write_text('{}')
    with pytest.raises(ValueError,match='digest'):Classifiers(tmp_path)


@async_test
async def test_real_encoder_singleton_cpu_and_batch_concurrency():
    w=CPUWorker(batch_size=8,batch_delay=.005)
    try:
        assert w.audit['encoder_instances']==1 and w.audit['device']=='cpu'
        results=await asyncio.gather(*(w.predict('List my current borrowed books',ctx((f'A{i}',f'B{i}'))) for i in range(20)))
        assert all(r['prediction']['intent_subtypes']['label']=='LOANS' for r in results)
        assert all(1<=r['batch_size']<=8 for r in results)
    finally:w.close()

