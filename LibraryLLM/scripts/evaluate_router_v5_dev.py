"""E ablation on all DEV; paired full-Qwen control on stratified DEV fallback."""
import asyncio
import json
import os
from pathlib import Path
import sys
import threading
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from assistant.router_v5.gateway import select,fallback
from assistant.router_v5.binding import make_plan
from assistant.qwen import QwenGateway
from assistant.profiling import current,observe_model
from router_v5_evidence import grade,totals,write

async def main():
    if (ROOT/'reports/assistant_router_v5_candidate_seal.json').exists():raise SystemExit('Candidate frozen; DEV rerun prohibited')
    os.environ['ASSISTANT_ROUTER_V2_VARIANT']='';os.environ['ASSISTANT_ROUTER_V2_RETRY']='0'
    from rag.llm import LuminaRLLM
    model=LuminaRLLM();observe_model(model)
    qwen=QwenGateway(model,threading.Lock());qwen.router_variant='';qwen.router_retry=False
    dev=json.loads((ROOT/'reports/assistant_router_v5_dev.json').read_text(encoding='utf8'))
    calibration=dev['selected_calibration']
    source=json.loads((ROOT/'evaluation/assistant_router_v5/dev.json').read_text(encoding='utf8'))
    predictions=json.loads((ROOT/'reports/assistant_router_v5_dev_scores.json').read_text(encoding='utf8'))['dev_cases']
    rows=[];control=[];sampled={};selected_total=0
    try:
        for index,(r,raw) in enumerate(zip(source,predictions)):
            plan=make_plan(r['context'],r['message']);prediction=raw['prediction']
            # Final candidate excludes the verifier, including shortlist ordering.
            prediction['methods'].pop('D',None)
            out,reason,key=select(prediction,plan,r['message'],calibration);accepted=out is not None
            profile={'stages_ms':{},'qwen_calls':[]};token=current.set(profile);info={};start=perf_counter()
            try:
                if not accepted:out,info=await fallback(qwen,r['message'],plan,prediction)
                okay,checks=grade(r,out)
                item={'id':r['id'],'contract_id':r['contract_id'],'critical':r['critical'],'accepted':accepted,'pass':okay,
                      'reason':reason,'checks':checks,'decision':out.model_dump(mode='json'),'fallback':info,
                      'qwen_calls':len(profile['qwen_calls']),'profile':profile,'latency_ms':1000*(perf_counter()-start)}
            finally:current.reset(token)
            rows.append(item)
            # Up to two per contract, at most forty: fixed stratification, no
            # cherry-picking by observed correctness or test outcomes.
            if not accepted and sampled.get(r['contract_id'],0)<2 and selected_total<40:
                sampled[r['contract_id']]=sampled.get(r['contract_id'],0)+1;selected_total+=1
                profile={'stages_ms':{},'qwen_calls':[]};token=current.set(profile);start=perf_counter()
                try:
                    old=await qwen.parse(r['message'],r['context']);old_ok,old_checks=grade(r,old)
                    control.append({'id':r['id'],'shortlist_pass':okay,'full_qwen_pass':old_ok,'full_qwen_checks':old_checks,
                                    'full_qwen_decision':old.model_dump(mode='json'),'full_qwen_profile':profile,
                                    'full_qwen_ms':1000*(perf_counter()-start),'shortlist_profile':item['profile'],
                                    'shortlist_ms':item['latency_ms']})
                finally:current.reset(token)
            if (index+1)%10==0 or index==len(source)-1:
                write('dev_hybrid',{'complete':len(rows)==len(source),'calibration_fixed_before_qwen':True,
                                   'metrics':totals(rows),'cases':rows,'paired_dev_controls':control})
                print('DEV E',index+1,len(source),okay,reason,flush=True)
    finally:qwen.close()
    write('qwen_fallback',{'source':'DEV only; stratified at most two per contract, capped forty; paired control is an extra offline call, not runtime retry.',
                         'control_cases':control,'paired_count':len(control),
                         'shortlist_correct':sum(r['shortlist_pass'] for r in control),'full_qwen_correct':sum(r['full_qwen_pass'] for r in control),
                         'runtime_max_routing_calls':1,'dev_fallback_metrics':totals(rows),'complete':True})

if __name__=='__main__':asyncio.run(main())
