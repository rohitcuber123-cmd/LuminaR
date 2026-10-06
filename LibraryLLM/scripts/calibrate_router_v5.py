"""DEV-only threshold selection; no model fitting or TEST loading."""
import asyncio
import json
from pathlib import Path
import sys
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from assistant.router_v5.contracts import BY_ID,registry_hash
from assistant.router_v5.binding import make_plan
from assistant.router_v5.gateway import select
from assistant.router_v5.worker import CPUWorker
from benchmark_router_v5_dev import bench
from router_v5_evidence import grade,write,digest,totals

OFF={'score':1000000,'margin':1000000}

def policy(items,min_support=4):
    """Readable monotonic score+margin grid, precision first, support bounded."""
    best=None;best_key=None
    scores=sorted({round(x[0],6) for x in items})
    margins=sorted({0,*[round(x[1],6) for x in items]})
    for score in scores:
        for margin in margins:
            accepted=[x for x in items if x[0]>=score and x[1]>=margin]
            correct=sum(x[2] for x in accepted)
            if len(accepted)<min_support or correct/len(accepted)<.99:continue
            # Prefer the largest region; conservative threshold breaks ties.
            key=(len(accepted),correct,score+margin)
            if best_key is None or key>best_key:best_key=key;best={'score':score,'margin':margin}
    return best or dict(OFF)

def extract(ranking):
    return ranking[0]['score'],ranking[0]['score']-ranking[1]['score'] if len(ranking)>1 else 1

def calibrate(rows,predictions,method):
    aux={}
    for group in ['position','field','criterion']:
        examples={}
        for r,p in zip(rows,predictions):
            c=BY_ID[r['contract_id']]
            relevant=(group=='position' and c.context in {'book','book_access'}) or (group=='field' and c.id=='COMPARE_FIELD') or (group=='criterion' and c.id=='COMPARE_PREFERENCE')
            if not relevant:continue
            ranking=p['aux'][group];label=ranking[0]['label']
            expected=r['position'] if group=='position' else r['field'] if group=='field' else 'PRESENT' if r['criterion_present'] else 'ABSENT'
            examples.setdefault(label,[]).append((*extract(ranking),label==expected))
        aux[group]={label:policy(items,3) for label,items in examples.items()}
    config={'method':method,'policies':{k:{'score':-1000000,'margin':-1000000} for k in BY_ID},'aux':aux}
    if method=='D':config['retrieval_policies']={k:{'score':-1000000,'margin':-1000000} for k in BY_ID}
    buckets={}
    for r,p in zip(rows,predictions):
        ranking=p['methods'][method];key=ranking[0]['id']
        out,_,_=select(p,make_plan(r['context'],r['message']),r['message'],config)
        okay=grade(r,out)[0]
        buckets.setdefault(key,[]).append((*extract(ranking),okay))
    config['policies']={k:policy(buckets.get(k,[]),4) for k in BY_ID}
    # Mutations have a stricter similarity floor and margin, in addition to
    # mandatory executor confirmation. This can only reduce coverage.
    for k,c in BY_ID.items():
        if c.mutation and method!='D':
            config['policies'][k]['score']=max(.80,config['policies'][k]['score'])
            config['policies'][k]['margin']=max(.10,config['policies'][k]['margin'])
    results=[]
    for r,p in zip(rows,predictions):
        out,reason,key=select(p,make_plan(r['context'],r['message']),r['message'],config)
        okay,checks=grade(r,out)
        results.append({'id':r['id'],'critical':r['critical'],'accepted':out is not None,'pass':okay,'reason':reason,'contract':key,'checks':checks})
    return config,results

async def main():
    if (ROOT/'reports/assistant_router_v5_candidate_seal.json').exists():raise SystemExit('Frozen candidate: tuning prohibited')
    rows=json.loads((ROOT/'evaluation/assistant_router_v5/dev.json').read_text(encoding='utf8'))
    scores=json.loads((ROOT/'reports/assistant_router_v5_dev_scores.json').read_text(encoding='utf8'))
    ps=[x['prediction'] for x in scores['dev_cases']]
    output={'dev_sha256':digest(ROOT/'evaluation/assistant_router_v5/dev.json'),'registry_sha256':registry_hash(),
            'method':'DEV-only monotonic score/margin thresholds, >=99% empirical precision with >=4 support; auxiliary >=3. Not learned heads.',
            'limitations':'Small per-action support; empirical in-sample precision is not a confidence guarantee.', 'ablations':{}}
    candidates={}
    for name in ['A','B','C','D']:
        config,result=calibrate(rows,ps,name);candidates[name]=config
        output['ablations'][name]={'calibration':config,'metrics':totals(result),'cases':result,'raw_top1':scores['raw_top1'][name]}
    compact=json.loads((ROOT/'reports/assistant_router_v5_dev_scores_compact.json').read_text(encoding='utf8'))
    cfg,result=calibrate(rows,[x['prediction'] for x in compact['dev_cases']],'D')
    output['ablations']['D_compact']={'calibration':cfg,'metrics':totals(result),'cases':result,'raw_top1':compact['raw_top1']['D']}
    # Both verifier forms missed the hard concurrency gate; select among A/B/C.
    best=max(['A','B','C'],key=lambda n:output['ablations'][n]['metrics']['accepted'])
    output['selected_method']=best;output['verifier_enabled']=False
    output['verifier_decision']='Neither cached verifier formulation meets 20-way p95 <1s; no permanent verifier.'
    write('dev',output)
    concurrency={'verifier_enabled':False,'no_batching':{},'micro_batching':{},'capacity_claim':'CPU routing throughput only, not overall product throughput'}
    for key,size,delay in [('no_batching',1,0),('micro_batching',8,.005)]:
        worker=await asyncio.to_thread(CPUWorker,verifier=False,batch_size=size,batch_delay=delay)
        try:
            concurrency[key+'_audit']=worker.audit
            for n in [1,5,10,20]:
                concurrency[key][str(n)]=await bench(worker,rows,n)
                print('CPU RETRIEVAL',key,n,concurrency[key][str(n)]['p95_ms'],flush=True)
        finally:worker.close()
    selected_batch=8 if concurrency['micro_batching']['20']['p95_ms']<concurrency['no_batching']['20']['p95_ms'] else 1
    output['selected_batch_size']=selected_batch;output['selected_calibration']=candidates[best]
    write('dev',output);write('concurrency',concurrency)
    print('CALIBRATION COMPLETE',best,json.dumps(output['ablations'][best]['metrics']),flush=True)

if __name__=='__main__':asyncio.run(main())
