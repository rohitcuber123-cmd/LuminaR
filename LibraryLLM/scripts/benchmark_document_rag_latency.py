"""Sequential authenticated document experiment; no source or account writes."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
import httpx
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
R = ROOT / 'reports'
MONGO = 'User Roles and Permissions in MongoDB'
GRU = 'AI-CSE-III-I-GRU-NOTES'
AUTO = 'AI-CSE-III-I-AUTOENCODER-NOTES'
CORPUS = [
 ('rbac_definition',MONGO,'According to this PDF, what is role-based access control?', ['definition','this document']),
 ('rbac_acronym',MONGO,'Explain RBAC.', ['short acronym']),
 ('roles',MONGO,'What are the roles described in this document?', ['actor','document terminology']),
 ('authentication',MONGO,'How does authentication work in this document?', ['how']),
 ('least_privilege',MONGO,'Why should users be assigned only the privileges they need?', ['why','causal']),
 ('negative_access',MONGO,'Does this document say users can access every database without authentication?', ['negative']),
 ('auth_relationship',MONGO,'What is the relationship between authentication and authorization?', ['multi entity']),
 ('quoted_role',MONGO,"What does 'readWrite' allow according to this document?", ['quoted phrase']),
 ('gru_definition',GRU,'What is a GRU?', ['definition','short acronym']),
 ('gru_update',GRU,'How is the update gate implemented in a GRU?', ['how','implementation']),
 ('gru_temporal',GRU,'What happens after the reset gate is applied?', ['temporal','causal']),
 ('ambiguous',MONGO,'What does it mean here?', ['ambiguous']),
 ('indexing',MONGO,'What does this PDF say about indexing?', ['document reference']),
 ('autoencoder',AUTO,'What is an autoencoder?', ['definition','third document']),
]

def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',required=True);p.add_argument('--mode',default='baseline');p.add_argument('--rounds',type=int,default=3);p.add_argument('--cases');p.add_argument('--switch',action='store_true');args=p.parse_args()
    from backend.database.mongodb import users_collection,issues_collection,reservations_collection,reading_list_collection
    from backend.services.identity_service import current_identity
    from backend.utils.jwt_utils import create_access_token
    user=next(u for u in users_collection.find({'role':'GENERAL_USER','is_email_verified':True}) if current_identity({'sub':str(u['user_id'])}))
    headers={'Authorization':'Bearer '+create_access_token(user['user_id'],user['email'],user['role'])}
    collections=[issues_collection,reservations_collection,reading_list_collection]
    before=[digest(list(c.find({}))) for c in collections]
    corpus=[dict(case=k,document_id=d,question=q,categories=t) for k,d,q,t in CORPUS]
    corpus_path=R/'document_rag_question_corpus.json'
    if corpus_path.exists(): assert json.loads(corpus_path.read_text())==corpus
    else:corpus_path.write_text(json.dumps(corpus,indent=2))
    selected=[c for c in corpus if not args.cases or c['case'] in args.cases.split(',')]
    output=R/f'document_rag_{args.phase}_raw.json'
    if output.exists():raise RuntimeError('Refusing to overwrite existing experiment evidence')
    result={'phase':args.phase,'mode':args.mode,'semantic_cache_cold':args.mode!='cache','runs':[]}
    def save():output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    with httpx.Client(timeout=240) as client:
        for _ in range(90):
            try:
                health=client.get('http://127.0.0.1:8005/health');health.raise_for_status();break
            except (httpx.HTTPError,ConnectionError):time.sleep(1)
        else:raise RuntimeError('RAG worker never became ready')
        result['health']=health.json()
        if args.switch:
            control=client.post('http://127.0.0.1:8005/__document_latency/control',json={'mode':args.mode});control.raise_for_status();result['control']=control.json()
        client.post('http://127.0.0.1:8005/assistant/chat',headers=headers,json={'message':'What is Gothic fiction?'}).raise_for_status()
        for number in range(1,args.rounds+1):
            for case in selected:
                started=time.perf_counter();response=client.post('http://127.0.0.1:8005/assistant/chat',headers=headers,json={'message':case['question'],'action':'DOCUMENT_QUESTION','page_context':{'document_id':case['document_id']}})
                total=(time.perf_counter()-started)*1000;body=response.json();tid=response.headers.get('x-assistant-trace')
                profiles=[json.loads(s) for s in (R/'document_rag_profiles.jsonl').read_text().splitlines() if s]
                observed=[json.loads(s) for s in (R/'document_rag_observations.jsonl').read_text().splitlines() if s]
                row={**case,'round':number,'status':response.status_code,'client_total_ms':total,'errors':body.get('errors'),
                     'rag':body.get('rag'),'profile':next(r for r in profiles if r['trace_id']==tid),
                     'observation':next(r for r in observed if r['trace_id']==tid)}
                result['runs'].append(row);save()
                print(json.dumps({'case':case['case'],'round':number,'seconds':round(total/1000,3),'calls':row['profile']['qwen_call_count'],'verdict':(row['rag'] or {}).get('verdict'),'errors':row['errors']}),flush=True)
        result['real_state_unchanged']=before==[digest(list(c.find({}))) for c in collections]
        totals=[r['client_total_ms'] for r in result['runs']]
        result['summary']={'min_ms':min(totals),'median_ms':statistics.median(totals),'p90_ms':sorted(totals)[__import__('math').ceil(.9*len(totals))-1],'max_ms':max(totals)}
        save();print('Complete; real state unchanged: '+str(result['real_state_unchanged']),flush=True)
if __name__=='__main__':main()
