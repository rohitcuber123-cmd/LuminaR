"""Explicit once-only frozen evaluation plus isolated CPU benchmarks."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from assistant.router_v4 import CPUWorker,HybridGateway,MODEL_DIR,structural_decision
from assistant.qwen import QwenGateway
from assistant.orchestrator import AssistantOrchestrator
from assistant.state import ConversationStore
from assistant import schemas,tools as tool_module
from assistant.profiling import current
import evaluate_assistant_semantics as fixtures
from evaluate_assistant_router_v2 import score,metrics
from evaluate_router_v3 import ObserveQwen,selective_metrics,summary

def write(name,data):
    p=ROOT/'reports'/('assistant_router_v4_'+name+'.json');p.write_text(json.dumps(data,indent=2,default=str),encoding='utf8')

def frozen_guard(explicit,directory=MODEL_DIR,reports=ROOT/'reports'):
    if not explicit:raise ValueError('Frozen evaluation requires explicit --frozen-test; develop on DEV/INTERNAL instead')
    seal=json.loads((Path(reports)/'assistant_router_v4_candidate_seal.json').read_text(encoding='utf8'))
    if hashlib.sha256((Path(directory)/'manifest.json').read_bytes()).hexdigest()!=seal['manifest_sha256']:raise ValueError('Candidate changed after sealing')
    if seal.get('runtime_sha256') and hashlib.sha256((ROOT/'assistant/router_v4.py').read_bytes()).hexdigest()!=seal['runtime_sha256']:
        raise ValueError('Runtime changed after candidate sealing')
    marker=Path(reports)/'assistant_router_v4_frozen_started.json'
    try:
        with marker.open('x',encoding='utf8') as f:json.dump({'manifest_sha256':seal['manifest_sha256'],'once_only':True},f)
    except FileExistsError as exc:raise ValueError('Frozen evaluation already started; do not repeatedly tune or re-evaluate') from exc

class ObservedHybrid:
    def __init__(self,hybrid,observer):self.hybrid=hybrid;self.observer=observer;self.decision=None;self.raw=[];self.telemetry={};self.prompt_hash=None;self.schema_hash=None
    async def parse(self,message,context):
        self.observer.raw=[];self.decision=None;self.raw=[];self.telemetry={}
        try:self.decision=await self.hybrid.parse(message,context);return self.decision
        finally:
            self.raw=list(self.observer.raw);self.telemetry=json.loads(json.dumps((current.get() or {}).get('router_v4',{})));self.telemetry['retry_used']=False
    async def respond(self,*args,**kwargs):return await self.hybrid.respond(*args,**kwargs)
    async def generate(self,*args,**kwargs):return await self.hybrid.generate(*args,**kwargs)

async def run_cases(hybrid,observer,name,cases):
    observed=ObservedHybrid(hybrid,observer);orch=AssistantOrchestrator(observed,ConversationStore());rows=[]
    for i,case in enumerate(cases):
        tools=fixtures.FixtureTools(schemas,tool_module);request=fixtures.establish(orch,case,schemas)
        response,profile,titles,searches=await fixtures.measured_case(orch,tools,request)
        row=score(case,response,orch.store.entries[request.conversation_id],observed,titles,searches,profile,i);rows.append(row)
        selected=selective_metrics(rows)
        # Accepted precision is end-to-end semantic correctness. Component
        # heads are reported independently even when the joint action controls.
        write('frozen_'+name,{'complete':len(rows)==len(cases),'method':'Real V4 fine-tuned CPU encoder and existing Qwen fallback, unchanged authoritative API fixtures',
            'manifest_sha256':hashlib.sha256((MODEL_DIR/'manifest.json').read_bytes()).hexdigest(),'metrics':metrics(rows),'selective':selected,'cases':rows})
        print('FROZEN V4',name,i+1,len(cases),response.intent.value,row['pass'],row['telemetry'].get('fallback_reason'),flush=True)

async def bench(worker,rows,n,total=80):
    import psutil
    sem=asyncio.Semaphore(n);times=[];queues=[];errors=[];encoder=[];process=psutil.Process(worker.audit['pid']);cpu0=sum(process.cpu_times()[:2]);start=perf_counter()
    async def one(i):
        async with sem:
            r=rows[i%len(rows)];t=perf_counter()
            try:
                result=await worker.predict(r['message'],r['context']);queues.append(result['queue_ms']);encoder.append(result['encoder_ms'])
            except Exception as exc:errors.append(type(exc).__name__)
            finally:times.append((perf_counter()-t)*1000)
    await asyncio.gather(*(one(i) for i in range(total)));seconds=perf_counter()-start
    return {**summary(times,seconds,len(errors)),'queue_p95_ms':float(__import__('numpy').quantile(queues,.95)) if queues else None,
            'encoder_p95_ms':float(__import__('numpy').quantile(encoder,.95)) if encoder else None,'cpu_percent':100*(sum(process.cpu_times()[:2])-cpu0)/seconds,
            'rss_mb':process.memory_info().rss/1048576,'qwen_calls':0,'gpu_lock_acquisitions':0}

async def concurrency(engine,hybrid):
    import torch,psutil,threading
    rows=list(map(json.loads,(ROOT/'training/assistant_router_v4/dataset.jsonl').read_text(encoding='utf8').splitlines()))
    # Internal examples only; classification latency includes rejected cases.
    rows=[r for r in rows if r['split']=='internal'][:200]
    default_audit=dict(hybrid.worker.audit)
    out={'default_batch_size':1,'experimental_batch_size':8,'experimental_delay_ms':5,'default_worker':default_audit,
         'no_batching':{},'micro_batching':{},'complete':False}
    before=torch.cuda.memory_allocated()
    for n in [1,5,10,20]:out['no_batching'][str(n)]=await bench(hybrid.worker,rows,n);write('concurrency',out)
    held=threading.Event();release=threading.Event()
    def hold():
        with engine.inference_lock:held.set();release.wait(10)
    thread=threading.Thread(target=hold);thread.start();await asyncio.to_thread(held.wait,2)
    try:out['real_gpu_lock_held']=await bench(hybrid.worker,rows,20,20)
    finally:release.set();thread.join(2)
    # Measure sequentially so even benchmarking never holds two encoders.
    hybrid.worker.close()
    other=await asyncio.to_thread(CPUWorker,batch_size=8,batch_delay=.005);hybrid.worker=other
    out['experimental_worker']=other.audit
    for n in [1,5,10,20]:out['micro_batching'][str(n)]=await bench(other,rows,n);write('concurrency',out)
    out['cuda_delta_bytes']=torch.cuda.memory_allocated()-before;out['complete']=True;out['capacity_claim']='Measured classification requests/sec only; not production tool capacity';write('concurrency',out)
    write('resources',{'worker':default_audit,'rag_rss_mb':psutil.Process().memory_info().rss/1048576,
        'host_total_mb':psutil.virtual_memory().total/1048576,'host_available_mb':psutil.virtual_memory().available/1048576,'cuda_router_delta_bytes':out['cuda_delta_bytes'],
        'cuda_existing_rag_allocated_bytes':torch.cuda.memory_allocated(),'training_gpu_usage_is_offline':True,
        'encoder_instances_at_any_time':1})

async def evaluate(args):
    if args.frozen_test:frozen_guard(True,args.model)
    os.environ['ASSISTANT_ROUTER_MODE']='existing_qwen';os.environ['ASSISTANT_ROUTER_V2_VARIANT']='';os.environ['ASSISTANT_ROUTER_V2_RETRY']='0'
    os.environ['ASSISTANT_PROFILE_PATH']=str(ROOT/'reports/assistant_router_v4_eval_profiles.jsonl')
    import rag.api
    qwen=QwenGateway(rag.api.engine.llm,rag.api.engine.inference_lock);qwen.router_variant='';qwen.router_retry=False
    observer=ObserveQwen(qwen);hybrid=await asyncio.to_thread(HybridGateway,observer,directory=args.model)
    try:
        if args.frozen_test:
            for name,file in [('116','existing'),('121','hidden')]:
                cases=json.loads((ROOT/'reports/assistant_router_v3_baseline_snapshot'/(file+'_sealed.json')).read_text(encoding='utf8'))
                await run_cases(hybrid,observer,name,cases)
        if args.concurrency:await concurrency(rag.api.engine,hybrid)
    finally:hybrid.close();rag.api.app.state.assistant.gateway.close() if hasattr(rag.api.app.state.assistant,'gateway') else None;await rag.api.app.state.assistant_http_client.aclose()
    write('evaluation_complete',{'frozen':args.frozen_test,'concurrency':args.concurrency,'default_mode':'existing_qwen'})

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--frozen-test',action='store_true');p.add_argument('--concurrency',action='store_true');p.add_argument('--model',default=str(MODEL_DIR));args=p.parse_args()
    if not (args.frozen_test or args.concurrency):p.error('Use --concurrency for normal development, or explicitly --frozen-test once after sealing')
    asyncio.run(evaluate(args))
