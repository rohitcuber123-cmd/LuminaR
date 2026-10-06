"""Once-only new sealed evaluation, followed by exposed 116/121 regression."""
import asyncio
import json
import os
from pathlib import Path
import sys
import threading
from time import perf_counter
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from assistant.router_v5.gateway import HybridGateway,MODEL_DIR
from assistant.router_v5.contracts import registry_hash
from assistant.qwen import QwenGateway
from assistant.profiling import current,observe_model
from assistant.orchestrator import AssistantOrchestrator
from assistant.state import ConversationStore
from assistant import schemas,tools as tool_module
import evaluate_assistant_semantics as fixtures
from evaluate_assistant_router_v2 import score
from router_v5_evidence import grade,totals,write,digest

class Observed:
    def __init__(self,hybrid):self.hybrid=hybrid;self.decision=None;self.raw=[];self.telemetry={};self.prompt_hash=None;self.schema_hash=None
    async def parse(self,message,context):
        self.decision=await self.hybrid.parse(message,context)
        self.telemetry=json.loads(json.dumps((current.get() or {}).get('router_v5',{})))
        return self.decision
    async def respond(self,*args,**kw):return await self.hybrid.respond(*args,**kw)
    async def generate(self,*args,**kw):return await self.hybrid.generate(*args,**kw)

def guard():
    seal=json.loads((ROOT/'reports/assistant_router_v5_candidate_seal.json').read_text(encoding='utf8'))
    assert registry_hash()==seal['registry_sha256']
    assert digest(MODEL_DIR/'manifest.json')==seal['manifest_sha256']
    assert digest(ROOT/'evaluation/assistant_router_v5/sealed.json')==seal['sealed_sha256']
    for name,value in seal['runtime_sha256'].items():assert digest(ROOT/name)==value,name
    marker=ROOT/'reports/assistant_router_v5_once_only.json'
    with marker.open('x',encoding='utf8') as stream:
        json.dump({'started_at':datetime.now(timezone.utc).isoformat(),'seal_sha256':digest(ROOT/'reports/assistant_router_v5_candidate_seal.json')},stream,indent=2)

async def main():
    if '--sealed-once' not in sys.argv:raise SystemExit('Explicit --sealed-once required')
    guard()
    os.environ['ASSISTANT_ROUTER_MODE']='router_v5';os.environ['ASSISTANT_ROUTER_V2_VARIANT']='';os.environ['ASSISTANT_ROUTER_V2_RETRY']='0'
    from rag.llm import LuminaRLLM
    model=LuminaRLLM();observe_model(model)
    qwen=QwenGateway(model,threading.Lock());qwen.router_variant='';qwen.router_retry=False
    hybrid=await asyncio.to_thread(HybridGateway,qwen)
    resource={'worker':hybrid.worker.audit,'router_cuda_bytes':hybrid.worker.audit['cuda_allocated_bytes']}
    import psutil,torch
    resource.update(parent_rss_mb=psutil.Process().memory_info().rss/1048576,host_available_mb=psutil.virtual_memory().available/1048576,
                    host_total_mb=psutil.virtual_memory().total/1048576,existing_qwen_cuda_allocated_bytes=torch.cuda.memory_allocated())
    write('resources',resource)
    try:
        cases=json.loads((ROOT/'evaluation/assistant_router_v5/sealed.json').read_text(encoding='utf8'));rows=[]
        for index,r in enumerate(cases):
            profile={'stages_ms':{},'qwen_calls':[]};token=current.set(profile);start=perf_counter()
            try:
                out=await hybrid.parse(r['message'],r['context']);okay,checks=grade(r,out)
                telemetry=profile.get('router_v5',{})
                item={**r,'accepted':telemetry.get('accepted',False),'pass':okay,'checks':checks,'decision':out.model_dump(mode='json'),
                      'telemetry':telemetry,'qwen_calls':len(profile['qwen_calls']),'profile':profile,'latency_ms':1000*(perf_counter()-start)}
            except Exception as exc:
                item={**r,'accepted':False,'pass':False,'checks':{},'error':type(exc).__name__,'qwen_calls':len(profile['qwen_calls'])}
            finally:current.reset(token)
            rows.append(item)
            if (index+1)%10==0 or index==len(cases)-1:
                write('sealed_results',{'complete':len(rows)==len(cases),'method':'Frozen parse-level strict action/goal/IDs/fields/criterion/confirmation; literal safety. Tools exercised separately in old regression and live HTTP.',
                                       'metrics':totals(rows),'cases':rows,'evaluation_runs':1})
                print('SEALED ONCE',index+1,len(cases),item['pass'],flush=True)
        old={}
        for name,file in [('116','existing'),('121','hidden')]:
            observed=Observed(hybrid);orch=AssistantOrchestrator(observed,ConversationStore());rows=[]
            cases=json.loads((ROOT/f'reports/assistant_router_v3_baseline_snapshot/{file}_sealed.json').read_text(encoding='utf8'))
            for index,case in enumerate(cases):
                tools=fixtures.FixtureTools(schemas,tool_module);request=fixtures.establish(orch,case,schemas)
                try:
                    response,profile,titles,searches=await fixtures.measured_case(orch,tools,request)
                    item=score(case,response,orch.store.entries[request.conversation_id],observed,titles,searches,profile,index)
                    if observed.decision and case['expected_intent']=='COMPARE_BOOKS':
                        goal='COMPARE_BY_FIELD' if case['fields'] else 'PREFERENCE_COMPARE' if case['category'] in {'preference','preference_criterion'} else 'FACTUAL_COMPARE'
                        item['goal_ok']=observed.decision.goal.value==goal;item['pass']=item['pass'] and item['goal_ok']
                    item.update(accepted=observed.telemetry.get('accepted',False),critical=case['context'] in {'selected','changed','comparison','page'},
                                qwen_calls=sum(c['stage']=='intent' for c in profile['qwen_calls']))
                except Exception as exc:
                    item={**case,'pass':False,'accepted':False,'critical':case['context'] in {'selected','changed','comparison','page'},'qwen_calls':0,'error':type(exc).__name__}
                rows.append(item)
                if (index+1)%10==0 or index==len(cases)-1:
                    old[name]={'complete':len(rows)==len(cases),'metrics':totals(rows),'cases':rows}
                    write('old_regression',{'method':'Previously exposed 116/121 sets; product responses with API fixtures, including goal strictness. No tuning after candidate freeze.','sets':old,'complete':name=='121' and len(rows)==len(cases)})
                    print('OLD REGRESSION',name,index+1,len(cases),item['pass'],flush=True)
    finally:hybrid.close()
    write('evaluation_complete',{'sealed_once':True,'old_regression_complete':True,'default_mode':'existing_qwen','finished_at':datetime.now(timezone.utc).isoformat()})

if __name__=='__main__':asyncio.run(main())
