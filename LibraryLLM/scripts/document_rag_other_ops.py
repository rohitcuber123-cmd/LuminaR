"""One sequential warm sanity pass using existing accounts and loan access."""
import hashlib
import argparse
import json
from pathlib import Path
import sys
import time
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',default='sanity');parser.add_argument('--mode',default='fast');args=parser.parse_args()
    from backend.database.mongodb import users_collection,issues_collection,reservations_collection,reading_list_collection
    from backend.services.identity_service import current_identity
    from backend.utils.jwt_utils import create_access_token
    from rag.book_assets import indexed_books
    users=[u for u in users_collection.find({'role':'GENERAL_USER','is_email_verified':True}) if current_identity({'sub':str(u['user_id'])})]
    def auth(u):return {'Authorization':'Bearer '+create_access_token(u['user_id'],u['email'],u['role'])}
    headers=auth(users[0]);indexed=set(indexed_books())
    book_user,loan=next((u,l) for u in users for l in issues_collection.find({'user_id':u['user_id'],'status':'ISSUED'}) if l.get('work_id') in indexed)
    seeds=json.loads((ROOT/'reports/assistant_latency_cases.json').read_text())['seeds']
    collections=[issues_collection,reservations_collection,reading_list_collection]
    before=[digest(list(c.find({}))) for c in collections]
    output=ROOT/f'reports/document_rag_other_ops_{args.phase}.json'
    if output.exists():raise RuntimeError('Refusing to overwrite evidence')
    result={'runs':[],'warm_repetitions':1,'mode':args.mode,'real_services':True,'cache_hits_not_document_benchmark':True}
    def save():output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    with httpx.Client(timeout=240) as client:
        client.post('http://127.0.0.1:8005/__document_latency/control',json={'mode':args.mode}).raise_for_status()
        def call(name,payload,credentials=headers,measure=True):
            started=time.perf_counter();response=client.post('http://127.0.0.1:8005/assistant/chat',headers=credentials,json=payload)
            total=(time.perf_counter()-started)*1000;body=response.json();tid=response.headers.get('x-assistant-trace')
            profiles=[json.loads(s) for s in (ROOT/'reports/document_rag_profiles.jsonl').read_text().splitlines() if s]
            row={'case':name,'status':response.status_code,'total_ms':total,'errors':body.get('errors'),
                 'profile':next((r for r in profiles if r['trace_id']==tid),None),'intent':body.get('intent'),
                 'rag_verdict':(body.get('rag') or {}).get('verdict'),'source_ids':[s.get('chunk_id') for s in (body.get('rag') or {}).get('sources',[])]}
            if measure:result['runs'].append(row);save();print(json.dumps(row),flush=True)
            return body
        call('warmup',{'message':'What is Gothic fiction?'},measure=False)
        call('search_warmup',{'message':'Find books about neural networks'},measure=False)
        for name,payload,credentials in [
            ('simple_search',{'message':'Find books about neural networks'},headers),
            ('complex_search',{'message':'Find available books about artificial intelligence by different authors, sorted by title'},headers),
            ('general_help',{'message':'What is Gothic fiction?'},headers),
            ('default_recommendation',{'message':'Recommend','action':'RECOMMEND'},headers),
            ('single_seed',{'message':'Recommend','action':'RECOMMEND_SIMILAR','selected_work_ids':seeds[:1]},headers),
            ('multi_seed',{'message':'Recommend','action':'RECOMMEND_FROM_SELECTION','selected_work_ids':seeds},headers),
            ('compare',{'message':'Compare these','action':'COMPARE','selected_work_ids':seeds},headers),
            ('availability',{'message':'Is this available?','action':'CHECK_AVAILABILITY','selected_work_ids':seeds[:1]},headers),
            ('fees',{'message':'What do I owe?'},headers),
            ('loans',{'message':'Show my loans'},headers),
            ('reading_list',{'message':'Show my reading list'},headers),
            ('available_alternatives',{'message':'Find available alternatives','action':'RECOMMEND_AVAILABLE_SIMILAR','selected_work_ids':seeds[:1]},headers),
            ('authorized_book_rag',{'message':'Who is the main character in this selected book?','action':'BOOK_CONTENT_QUESTION','selected_work_ids':[loan['work_id']]},auth(book_user)),
        ]:
            body=call(name,payload,credentials)
            if name=='single_seed':call('explain_recommendation',{'message':'Why these recommendations?','action':'EXPLAIN_RECOMMENDATION','conversation_id':body['conversation_id'],'selected_work_ids':[]})
            if name=='compare':call('explain_comparison',{'message':'Explain comparison','action':'EXPLAIN_COMPARISON','conversation_id':body['conversation_id'],'selected_work_ids':[]})
        result['real_state_unchanged']=before==[digest(list(c.find({}))) for c in collections]
        result['pass']=len(result['runs'])==15 and all(r['status']==200 and not r['errors'] for r in result['runs']) and result['real_state_unchanged']
        save()
if __name__=='__main__':main()
