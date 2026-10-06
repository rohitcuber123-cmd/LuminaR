"""Frozen TEST evaluation and bounded concurrency with one resident Qwen.

This runner starts the normal RAG service, then evaluates an isolated opt-in
gateway. HTTP production remains existing_qwen. Writes only V3 evidence.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from assistant.router_v3 import (CPUWorker,HybridGateway,Classifiers,MODEL_DIR,FAMILIES,features,
                                 context_pool,structural_decision)
from assistant.qwen import QwenGateway
from assistant.orchestrator import AssistantOrchestrator
from assistant.state import ConversationStore
from assistant import schemas,tools as tool_module
from assistant.profiling import current
import evaluate_assistant_semantics as fixtures
from evaluate_assistant_router_v2 import score,metrics


def write(name,data):
    path=ROOT/'reports'/name;tmp=path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data,indent=2,default=str),encoding='utf8')
    for attempt in range(10):
        try:os.replace(tmp,path);return
        except PermissionError:
            if attempt==9:raise
            time.sleep(.02)


def summary(values,seconds=None,errors=0):
    import numpy as np
    return {'requests':len(values),'median_ms':float(np.median(values)) if values else None,
        'p90_ms':float(np.quantile(values,.9)) if values else None,
        'p95_ms':float(np.quantile(values,.95)) if values else None,'max_ms':max(values,default=None),
        'throughput_per_sec':len(values)/seconds if seconds else None,'errors':errors}


class ObserveQwen:
    def __init__(self,gateway):self.gateway=gateway;self.raw=[];self.calls=0
    async def generate(self,prompt,schema=None,stage='response'):
        self.calls+=1;result=await self.gateway.generate(prompt,schema,stage);self.raw.append(result);return result
    async def parse(self,message,context):return await QwenGateway.parse(self,message,context)
    async def respond(self,*args,**kwargs):return await self.gateway.respond(*args,**kwargs)
    def close(self):self.gateway.close()


class ObservedHybrid:
    def __init__(self,hybrid,observer):
        self.hybrid=hybrid;self.observer=observer;self.decision=None;self.raw=[];self.telemetry={};self.prompt_hash=None;self.schema_hash=None
    async def parse(self,message,context):
        self.observer.raw=[]
        self.decision=None;self.raw=[];self.telemetry={}
        try:
            self.decision=await self.hybrid.parse(message,context)
            return self.decision
        finally:
            self.raw=list(self.observer.raw)
            self.telemetry=copy_dict((current.get() or {}).get('router_v3',{}))
            self.telemetry['retry_used']=False
    async def respond(self,*args,**kwargs):return await self.hybrid.respond(*args,**kwargs)
    async def generate(self,*args,**kwargs):return await self.hybrid.generate(*args,**kwargs)


def copy_dict(data):return json.loads(json.dumps(data))


def expected_subtype(case):
    intent=case['expected_intent'];category=case['category']
    if intent=='COMPARE_BOOKS':
        if case['fields']:return 'FIELD'
        if category in {'preference','preference_criterion'}:return 'PREFERENCE'
        return 'FACTUAL'
    return {'SEARCH_BOOKS':'SEARCH','RECOMMEND_BOOKS':'RECOMMEND','RECOMMEND_FROM_SELECTION':'RECOMMEND',
        'RECOMMEND_FROM_BOOK':'RECOMMEND','CHECK_AVAILABILITY':'AVAILABILITY','BOOK_DETAILS':'DETAILS',
        'MORE_LIKE_THIS':'SIMILAR','USER_FEES':'FEES','USER_LOANS':'LOANS','USER_HISTORY':'HISTORY',
        'USER_RESERVATIONS':'RESERVATIONS','USER_READING_LIST':'READING_LIST','BORROW_BOOK':'BORROW',
        'RETURN_BOOK':'RETURN','RESERVE_BOOK':'RESERVE'}.get(intent)


def selective_metrics(rows):
    accepted=[r for r in rows if r['telemetry'].get('accepted')]
    components={};denoms={};category={};reasons={}
    for r in rows:
        p=r['telemetry'].get('components',{});gold=expected_subtype(r)
        expected_source={'selected':'SELECTION','changed':'SELECTION','comparison':'PREVIOUS_COMPARISON','page':'PAGE'}.get(r['context'],'AMBIGUOUS')
        if r['category']=='explicit_entity':expected_source='EXPLICIT'
        if gold and (gold=='SEARCH' or FAMILIES[gold]=='ACCOUNT'):expected_source='NONE'
        gold_heads={'intent_subtypes':gold,'intent_family':FAMILIES[gold] if gold else None,
            'reference':expected_source,'fields':r['fields'][0] if r['fields'] else 'NONE',
            'criterion':'PRESENT' if r['criterion'] else 'ABSENT'}
        for head,expected in gold_heads.items():
            if expected is not None:
                components[head]=components.get(head,0)+int(p.get(head,{}).get('label')==expected);denoms[head]=denoms.get(head,0)+1
        if r['expected_ids'] and r['category']!='explicit_entity':
            source_ids=[fixtures.A,fixtures.B] if r['context'] in {'selected','comparison'} else [fixtures.C,fixtures.D] if r['context']=='changed' else [fixtures.B]
            pos=p.get('position',{}).get('label');focus=[]
            try:
                from assistant.semantic import bind_position
                okay=bind_position(source_ids,pos,focus)==r['expected_ids']
            except ValueError:okay=False
            components['position_binding']=components.get('position_binding',0)+int(okay);denoms['position_binding']=denoms.get('position_binding',0)+1
        c=category.setdefault(r['category'],{'requests':0,'accepted':0,'accepted_correct':0,'fallback':0,'hybrid_correct':0})
        c['requests']+=1;c['accepted']+=int(r['telemetry'].get('accepted',False));c['accepted_correct']+=int(r['telemetry'].get('accepted',False) and r['pass'])
        c['fallback']+=int(not r['telemetry'].get('accepted',False));c['hybrid_correct']+=int(r['pass'])
        reason=r['telemetry'].get('fallback_reason','NO_CLASSIFIER');reasons[reason]=reasons.get(reason,0)+1
    return {'coverage_percent':100*len(accepted)/len(rows),
        'accepted_precision_percent':100*sum(r['pass'] for r in accepted)/len(accepted) if accepted else None,
        'accepted':len(accepted),'accepted_correct':sum(r['pass'] for r in accepted),
        'fallback_rate_percent':100*(len(rows)-len(accepted))/len(rows),
        'qwen_calls_per_100':100*sum(len(r['profile']['qwen_calls']) for r in rows)/len(rows),
        'components':{h:{'correct':n,'total':denoms[h],'accuracy_percent':100*n/denoms[h]} for h,n in components.items()},
        'position_metric':'Authoritative binding equivalence, not separately hand-labelled ordinal words; excludes named entities.',
        'categories':category,'fallback_reasons':reasons}


async def run_cases(hybrid,observer,name,cases):
    observed=ObservedHybrid(hybrid,observer);orch=AssistantOrchestrator(observed,ConversationStore());rows=[]
    path=ROOT/'reports'/('assistant_router_v3_'+name+'_cases.json')
    previous=json.loads(path.read_text(encoding='utf8'))['cases'] if path.exists() else []
    for index,case in enumerate(cases):
        if index<len(previous) and not previous[index]['errors']:
            old=previous[index]
            old['telemetry']=copy_dict(old['profile'].get('router_v3',{}))
            old['transport_recovery']='Prior successful response retained; observer telemetry reconciled to request-local profile.'
            rows.append(old);continue
        fixture_tools=fixtures.FixtureTools(schemas,tool_module);request=fixtures.establish(orch,case,schemas)
        response,profile,titles,searches=await fixtures.measured_case(orch,fixture_tools,request)
        row=score(case,response,orch.store.entries[request.conversation_id],observed,titles,searches,profile,index)
        rows.append(row);base=metrics(rows)
        write('assistant_router_v3_'+name+'_cases.json',{'complete':len(rows)==len(cases),'method':'Real frozen CPU MiniLM classifiers + existing resident Qwen fallback; authoritative API fixtures',
            'model_artifact_sha256':hashlib.sha256((MODEL_DIR/'manifest.json').read_bytes()).hexdigest(),
            'metrics':base,'selective':selective_metrics(rows),'cases':rows})
        print('V3 TEST',name,index+1,'/',len(cases),response.intent.value,row['pass'],row['telemetry'].get('fallback_reason'),flush=True)


async def cpu_bench(worker,context,messages,n,total):
    semaphore=asyncio.Semaphore(n);times=[];queues=[];batch_sizes=[];errors=[];subtypes=[];accepted=[]
    calibration=json.loads((MODEL_DIR/'calibration.json').read_text(encoding='utf8'))
    async def request(i):
        async with semaphore:
            started=perf_counter()
            try:
                result=await worker.predict(messages[i%len(messages)],context)
                queues.append(result['queue_ms']);batch_sizes.append(result['batch_size']);subtypes.append(result['prediction']['intent_subtypes']['label'])
                accepted.append(structural_decision(result['prediction'],context,messages[i%len(messages)],calibration)[0] is not None)
            except Exception as exc:errors.append(type(exc).__name__)
            times.append((perf_counter()-started)*1000)
    start=perf_counter();await asyncio.gather(*(request(i) for i in range(total)));elapsed=perf_counter()-start
    return {**summary(times,elapsed,len(errors)),'queue':summary(queues),'batches':batch_sizes,'observed_subtypes':sorted(set(subtypes)),
            'qwen_calls':0,'accepted_routes':sum(accepted),'method':'CPU worker encoder+heads+IPC+structural policy; excludes tool/HTTP latency','concurrency':n}


async def concurrency(engine,hybrid,observer):
    import psutil,torch
    c={'selected_books':[{'work_id':'CONCURRENCY_A'},{'work_id':'CONCURRENCY_B'}]}
    # Select benchmark eligibility from authored DEV examples under a fixed
    # synthetic tray. No TEST predictions feed model, thresholds or this list.
    candidates=[r['message'] for r in (json.loads(line) for line in
        (ROOT/'training/assistant_router_v3/dataset.jsonl').read_text(encoding='utf8').splitlines()) if r['split']=='dev']
    messages=[]
    for text in candidates:
        value=await hybrid.worker.predict(text,c)
        if structural_decision(value['prediction'],c,text,hybrid.calibration)[0] is not None:messages.append(text)
        if len(messages)>=24:break
    assert messages,'No reliable DEV requests available for CPU benchmark'
    out={'no_batching':{},'micro_batching':{},'baseline':{},'complete':False,'high_confidence_workload_count':len(messages),
         'workload_provenance':'DEV accepted examples; no TEST-derived eligibility or tuning'}
    baseline_cuda={'allocated_bytes':torch.cuda.memory_allocated(),'reserved_bytes':torch.cuda.memory_reserved()}
    print('V3 BENCH starting',flush=True)
    # Bench batching as an experiment, never enable it in production by default.
    for batching in [False,True]:
        worker=CPUWorker(batch_size=8 if batching else 1,batch_delay=.005 if batching else 0)
        try:
            key='micro_batching' if batching else 'no_batching';out[key]['startup']=worker.audit
            out[key]['cuda_delta_bytes']=torch.cuda.memory_allocated()-baseline_cuda['allocated_bytes']
            for n in [1,5,10,20]:
                # 80 requests per tier, enough warm samples without GPU overload.
                process=psutil.Process(worker.audit['pid']);process.cpu_percent(None)
                result=await cpu_bench(worker,c,messages,n,80)
                result['cpu_percent_worker']=process.cpu_percent(None);result['rss_mb_worker']=process.memory_info().rss/1048576
                out[key][str(n)]=result;write('assistant_router_v3_concurrency.json',out)
        finally:worker.close()
    # Safe baseline measures actual admission, including busy errors; no retries.
    for n in [1,2,5]:
        latencies=[];errors=[];lock_wait=[];calls=[]
        async def baseline(i):
            p={'stages_ms':{},'qwen_calls':[]};token=current.set(p);started=perf_counter()
            try:await observer.parse(messages[i%len(messages)],c)
            except Exception as exc:errors.append(type(exc).__name__)
            finally:latencies.append((perf_counter()-started)*1000);calls.append(len(p['qwen_calls']));current.reset(token)
        start=perf_counter();await asyncio.gather(*(baseline(i) for i in range(n)));duration=perf_counter()-start
        out['baseline'][str(n)]={**summary(latencies,duration,len(errors)),'successful_throughput_per_sec':(n-len(errors))/duration,
            'qwen_calls':sum(calls),'errors_by_type':errors,'admission':'Existing nonblocking gateway rejects concurrent requests as busy; no unbounded GPU queue.',
            'inference_lock_wait_ms':'not instrumented separately; no concurrent RAG during baseline'}
        write('assistant_router_v3_concurrency.json',out)
    # Mixed load: one complex request enters Qwen, other fallbacks are admitted
    # or rejected by existing busy behavior. CPU work continues independently.
    mixed=[]
    async def request(i):
        p={'stages_ms':{},'qwen_calls':[]};token=current.set(p);started=perf_counter()
        message=messages[i%len(messages)] if i<15 else 'I want whichever book is most helpful for an advanced course on the economics of ocean shipping, but I care less about management and more about historical trade.'
        try:
            d=await hybrid.parse(message,c);error=None
        except Exception as exc:d=None;error=type(exc).__name__
        finally:
            mixed.append({'id':i,'classifier_eligible_candidate':i<15,'duration_ms':(perf_counter()-started)*1000,
                'intent':d.intent.value if d else None,'error':error,'telemetry':copy_dict(p.get('router_v3',{})),
                'qwen_calls':len(p['qwen_calls'])});current.reset(token)
    start=perf_counter();await asyncio.gather(*(request(i) for i in range(20)));elapsed=perf_counter()-start
    accepted=[r for r in mixed if r['telemetry'].get('accepted')]
    out['mixed']={'requests':mixed,'total_seconds':elapsed,'accepted':len(accepted),
        'accepted_latency':summary([r['duration_ms'] for r in accepted]),
        'fallback_errors':sum(bool(r['error']) for r in mixed),'qwen_calls':sum(r['qwen_calls'] for r in mixed),
        'cuda_delta_bytes':torch.cuda.memory_allocated()-baseline_cuda['allocated_bytes']}
    # Explicit lock coexistence: CPU classifier runs while a distinct thread
    # owns RAG's real inference lock, without actually generating duplicate RAG.
    import threading
    held=threading.Event();release=threading.Event()
    def hold():
        with engine.inference_lock:held.set();release.wait(10)
    t=threading.Thread(target=hold);t.start();await asyncio.to_thread(held.wait,2)
    try:out['real_gpu_lock_held']=await cpu_bench(hybrid.worker,c,messages,20,20)
    finally:release.set();t.join(timeout=2)
    # 200 independently generated performance messages, distinct from accuracy
    # cases; repetitions measure infrastructure and are not training evidence.
    workload=[]
    for subtype,count,message in [('search',40,'Locate reading material concerning marine conservation'),
        ('availability_details',30,'Show catalogue details for the second volume'),('account',30,'List my current borrowed books'),
        ('compare',30,'Present a factual comparison of these volumes'),('recommend',20,'Give me some reading suggestions'),
        ('kg',10,'Find books with themes shared by the second volume'),('fallback',20,'Interpret the findings in the file I uploaded'),
        ('other',20,'Explain how the library works')]:
        workload.extend({'category':subtype,'message':message,'id':f'performance-{len(workload)+i}'} for i in range(count))
    out['performance_workload']={'size':len(workload),'mix':{k:sum(r['category']==k for r in workload) for k in {r['category'] for r in workload}},
        'cpu_only_inference':await cpu_bench(hybrid.worker,c,[r['message'] for r in workload],20,200),
        'notes':'This measures classification throughput for the requested mix. Actual GPU coexistence uses the bounded 20-request mixed test above.'}
    (ROOT/'reports/assistant_router_v3_performance_workload.json').write_text(json.dumps(workload,indent=2),encoding='utf8')
    out['complete']=True
    out['throughput_speedup']=out['micro_batching']['20']['throughput_per_sec']/out['baseline']['1']['successful_throughput_per_sec']
    out['comparison_limit']='Worker classification throughput vs serialized Qwen routing only; not complete tool/HTTP or production capacity. Busy errors are counted explicitly.'
    write('assistant_router_v3_concurrency.json',out)
    write('assistant_router_v3_resources.json',{'encoder':json.loads((ROOT/'reports/assistant_router_v3_encoder_audit.json').read_text()),
        'classifier_worker':hybrid.worker.audit,'rag_process_rss_mb':psutil.Process().memory_info().rss/1048576,
        'cuda_before_worker':baseline_cuda,'cuda_after_bench':{'allocated_bytes':torch.cuda.memory_allocated(),'reserved_bytes':torch.cuda.memory_reserved()},
        'gpu_name':torch.cuda.get_device_name(),'host_ram_total_bytes':psutil.virtual_memory().total,
        'worker_load_gpu_delta_bytes':out['no_batching']['cuda_delta_bytes'],'cuda20_delta_bytes':out['mixed']['cuda_delta_bytes'],
        'queue_capacity':64,'batch_size_default':1,'batching_experiment':{'batch_size':8,'delay_ms':5},
        'full_resource_detail':'assistant_router_v3_concurrency.json'})


async def evaluate(engine):
    import torch
    before={'allocated_bytes':torch.cuda.memory_allocated(),'reserved_bytes':torch.cuda.memory_reserved()}
    qwen=QwenGateway(engine.llm,engine.inference_lock);qwen.router_variant='';qwen.router_retry=False
    observer=ObserveQwen(qwen);hybrid=HybridGateway(observer)
    write('assistant_router_v3_worker_startup.json',{'cuda_before':before,'cuda_after':{'allocated_bytes':torch.cuda.memory_allocated(),'reserved_bytes':torch.cuda.memory_reserved()},'audit':hybrid.worker.audit})
    try:
        for name in ['existing','hidden']:
            cases=json.loads((ROOT/'reports/assistant_router_v3_baseline_snapshot'/(name+'_sealed.json')).read_text(encoding='utf8'))
            await run_cases(hybrid,observer,name,cases)
        await concurrency(engine,hybrid,observer)
    finally:hybrid.close()
    write('assistant_router_v3_evaluation_complete.json',{'complete':True,'default_http_router':'existing_qwen'})


if __name__=='__main__':
    os.environ['ASSISTANT_ROUTER_MODE']='existing_qwen'
    os.environ['ASSISTANT_ROUTER_V2_VARIANT']=''
    os.environ['ASSISTANT_ROUTER_V2_RETRY']='0'
    os.environ['ASSISTANT_PROFILE_PATH']=str(ROOT/'reports/assistant_router_v3_default_http_profiles.jsonl')
    import rag.api
    async def startup():
        async def task():
            try:await evaluate(rag.api.engine)
            except Exception as exc:
                write('assistant_router_v3_evaluation_error.json',{'type':type(exc).__name__,'message':str(exc)})
                import traceback;traceback.print_exc()
        rag.api.app.state.router_v3_evaluation=asyncio.create_task(task())
    rag.api.app.router.add_event_handler('startup',startup)
    import uvicorn
    uvicorn.run(rag.api.app,host='127.0.0.1',port=8005,workers=1)
