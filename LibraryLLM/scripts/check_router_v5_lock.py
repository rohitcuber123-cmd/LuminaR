"""Admitted parsing with the actual gateway mutex held; no second GPU model."""
import asyncio
import json
from pathlib import Path
import sys
import threading
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from assistant.qwen import QwenGateway
from assistant.router_v5.gateway import HybridGateway
from assistant.profiling import current
from router_v5_evidence import write

class NoGeneration:
    def __init__(self):self.calls=0
    def generate(self,*args,**kwargs):self.calls+=1;raise AssertionError('Admitted routing must not generate')
    def _prefix_function(self,*args):raise AssertionError('Admitted routing must not decode')

async def main():
    assert (ROOT/'reports/assistant_router_v5_evaluation_complete.json').exists()
    model=NoGeneration();mutex=threading.Lock();qwen=QwenGateway(model,mutex)
    hybrid=await asyncio.to_thread(HybridGateway,qwen)
    mutex.acquire();rows=[]
    async def one(i):
        profile={'stages_ms':{},'qwen_calls':[]};token=current.set(profile);start=perf_counter()
        try:
            result=await asyncio.wait_for(hybrid.parse('Do I have charges due to the library?',{'authenticated':True}),2)
            rows.append({'request':i,'intent':result.intent.value,'accepted':profile.get('router_v5',{}).get('accepted'),
                         'routing_attempts':profile.get('router_v5',{}).get('qwen_routing_calls'),
                         'latency_ms':1000*(perf_counter()-start),'pass':result.intent.value=='USER_FEES'})
        finally:current.reset(token)
    try:
        await asyncio.gather(*(one(i) for i in range(20)))
    finally:mutex.release();hybrid.close()
    import numpy as np
    write('lock_isolation',{'method':'Actual QwenGateway inference mutex held while twenty admitted parses run. Model injection deliberately forbids generation, avoiding any duplicate GPU stack. Real RAG GPU coexistence measured separately over HTTP.',
          'requests':rows,'accepted':sum(r['accepted'] for r in rows),'semantic_correct':sum(r['pass'] for r in rows),
          'qwen_generation_calls':model.calls,'inference_lock_acquisitions_by_routes':0 if not model.calls and not any(r['routing_attempts'] for r in rows) else None,
          'p95_ms':float(np.quantile([r['latency_ms'] for r in rows],.95))})

if __name__=='__main__':asyncio.run(main())
