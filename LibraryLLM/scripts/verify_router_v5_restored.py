"""Default-mode smoke and artifact cleanup, with no credentials persisted."""
import asyncio
import json
from pathlib import Path
import sqlite3
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import httpx
from backend.utils.jwt_utils import create_access_token
from check_router_v4_live import identities_and_books,identifiers
from router_v5_evidence import write,digest

async def main():
    books,user,_=identities_and_books();a,b=books[0]['work_id'],books[1]['work_id']
    headers={'Authorization':'Bearer '+create_access_token(user['user_id'],user['email'],user['role'])}
    out={'health':{},'smokes':[],'default':'existing_qwen'}
    async with httpx.AsyncClient(timeout=180) as client:
        for label,url in [('core','http://127.0.0.1:8002/health'),('search','http://127.0.0.1:8003/health'),
                          ('recommendation','http://127.0.0.1:8004/'),('rag','http://127.0.0.1:8005/health'),
                          ('frontend','http://127.0.0.1:5173/')]:
            response=await client.get(url);out['health'][label]=response.status_code
        for payload,intent,expected in [({'message':'Compare selected books','action':'COMPARE','selected_work_ids':[a,b]},'COMPARE_BOOKS',[a,b]),
            ({'message':'is this available?','page_context':{'work_id':a}},'CHECK_AVAILABILITY',[a])]:
            response=await client.post('http://127.0.0.1:8005/assistant/chat',headers=headers,json=payload);data=response.json()
            trace=response.headers.get('x-assistant-trace');observed={}
            path=ROOT/'reports/assistant_router_v5_restored_profiles.jsonl'
            for _ in range(30):
                if path.exists():
                    observed=next((p for p in map(json.loads,reversed(path.read_text(encoding='utf8').splitlines())) if p['trace_id']==trace),{})
                    if observed:break
                await asyncio.sleep(.01)
            ids=identifiers(data)
            out['smokes'].append({'expected_intent':intent,'actual_intent':data.get('intent'),'expected_public_ids':expected,
                 'resolved_ids':ids,'status':response.status_code,'errors':[e.get('code') for e in data.get('errors',[])],
                 'no_v5_telemetry':'router_v5' not in observed,'qwen_calls':observed.get('qwen_call_count'),
                 'pass':response.status_code==200 and data.get('intent')==intent and ids==expected and not data.get('errors') and 'router_v5' not in observed})
    path=ROOT/'rag/private_documents/registry.sqlite'
    if path.exists():
        with sqlite3.connect(f'file:{path.as_posix()}?mode=ro',uri=True) as db:
            out['private_document_registry_rows']=db.execute('SELECT count(*) FROM documents').fetchone()[0]
        out['private_document_directories']=sum(p.is_dir() and p.name.startswith('doc_') for p in path.parent.iterdir())
    baseline=json.loads((ROOT/'reports/assistant_router_v5_baseline.json').read_text(encoding='utf8'))
    out['baseline_differences']=[p for p,h in baseline['frozen_files'].items() if not (ROOT/p).exists() or digest(ROOT/p)!=h]
    manifest=json.loads((ROOT/'assistant/models/router_v5/manifest.json').read_text(encoding='utf8'))
    out['cached_encoder_hashes_unchanged']=all(digest(p)==h for p,h in manifest['cached_encoder_files'].items())
    seal=json.loads((ROOT/'reports/assistant_router_v5_candidate_seal.json').read_text(encoding='utf8'))
    out['frozen_runtime_hashes_unchanged']=all(digest(ROOT/p)==h for p,h in seal['runtime_sha256'].items())
    out['complete']=True;write('restored',out)
    print('RESTORED',out['health'],[r['pass'] for r in out['smokes']],out['baseline_differences'],flush=True)

if __name__=='__main__':asyncio.run(main())
