"""First CPU audit of the already-cached verifier; DEV only, no thresholds."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter
import numpy as np
import psutil

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from assistant.router_v5.worker import CPUWorker
from assistant.router_v5.binding import make_plan,model_payload


def write(name,data):
    (ROOT/'reports'/f'assistant_router_v5_{name}.json').write_text(json.dumps(data,indent=2),encoding='utf8')


async def bench(worker,rows,concurrent,total=80):
    sem=asyncio.Semaphore(concurrent);times=[];queue=[];encoder=[];verifier=[];errors=[]
    process=psutil.Process(worker.audit['pid']);cpu0=sum(process.cpu_times()[:2]);started=perf_counter()
    async def one(i):
        async with sem:
            case=rows[i%len(rows)];start=perf_counter()
            try:
                result=await worker.predict(case['message'],case['context'])
                queue.append(result['queue_ms']);encoder.append(result['prediction']['encoder_ms']);verifier.append(result['prediction']['verifier_ms'])
            except Exception as exc:
                errors.append(type(exc).__name__)
            finally:times.append((perf_counter()-start)*1000)
    await asyncio.gather(*(one(i) for i in range(total)))
    seconds=perf_counter()-started
    return {'requests':total,'concurrency':concurrent,'median_ms':float(np.median(times)),
            'p95_ms':float(np.quantile(times,.95)),'max_ms':max(times),'throughput_per_sec':total/seconds,
            'queue_p95_ms':float(np.quantile(queue,.95)) if queue else None,
            'encoder_p95_ms':float(np.quantile(encoder,.95)) if encoder else None,
            'verifier_p95_ms':float(np.quantile(verifier,.95)) if verifier else None,
            'cpu_percent':100*(sum(process.cpu_times()[:2])-cpu0)/seconds,
            'rss_mb':process.memory_info().rss/1048576,'commit_mb':process.memory_info().vms/1048576,
            'host_available_mb':psutil.virtual_memory().available/1048576,'errors':errors,
            'qwen_calls':0,'qwen_lock_acquisitions':0}


async def main():
    if (ROOT/'reports/assistant_router_v5_candidate_seal.json').exists():
        raise SystemExit('Candidate is already frozen; do not repeat DEV selection.')
    rows=json.loads((ROOT/'evaluation/assistant_router_v5/dev.json').read_text(encoding='utf8'))
    compact='--definition-only' in sys.argv
    prefix='_compact' if compact else ''
    worker=await asyncio.to_thread(CPUWorker,verifier=True,verifier_examples=not compact)
    out={'method':'Existing cached CrossEncoder L6 CPU top-three contract verifier; no Search API calls and no model downloads.',
         'license':'Apache-2.0; publisher model card https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2',
         'task_mismatch':'MS MARCO query/passage relevance model, not an NLI entailment classifier.',
         'audit':worker.audit,'dev_cases':[],'complete':False}
    try:
        for i,row in enumerate(rows):
            measured=await worker.predict(row['message'],row['context'])
            out['dev_cases'].append({'id':row['id'],'prediction':measured['prediction'],'queue_ms':measured['queue_ms']})
            if (i+1)%25==0:
                print('DEV CONTRACT SCORING',i+1,len(rows),flush=True);write('dev_scores'+prefix,out)
        out['complete']=True
        for method in ['A','B','C','D']:
            evaluable=[(r,s) for r,s in zip(rows,out['dev_cases']) if s['prediction']['methods'].get(method)]
            out.setdefault('raw_top1',{})[method]={'correct':sum(s['prediction']['methods'][method][0]['id']==r['contract_id'] for r,s in evaluable),'total':len(evaluable)}
        write('dev_scores'+prefix,out)
        benchmark={}
        representatives=[];seen=set()
        for row in rows:
            if row['contract_id'] not in seen:representatives.append(row);seen.add(row['contract_id'])
        for n in [1,5,10,20]:
            benchmark[str(n)]=await bench(worker,representatives,n)
            print('CPU VERIFIER',n,benchmark[str(n)]['p95_ms'],flush=True)
        audit=dict(worker.audit)
    finally:worker.close()
    micro=await asyncio.to_thread(CPUWorker,verifier=True,batch_size=8,batch_delay=.005,verifier_examples=not compact)
    try:
        batches={str(n):await bench(micro,representatives,n) for n in [1,5,10,20]}
        micro_audit=micro.audit
    finally:micro.close()
    write('crossencoder'+prefix,{'license':out['license'],'task_mismatch':out['task_mismatch'],'audit':audit,
                         'micro_audit':micro_audit,'dev_raw_top1':out['raw_top1'],'no_batching':benchmark,
                         'micro_batching':batches,'no_downloads':True,'runtime_cuda_bytes':0,'complete':True,
                         'registry_sha256':audit['registry_sha256']})
    print('EXISTING CROSSENCODER AUDIT COMPLETE',flush=True)


if __name__=='__main__':asyncio.run(main())
