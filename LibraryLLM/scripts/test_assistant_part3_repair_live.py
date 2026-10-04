"""Warm, sequential real-service benchmark. No model loader or real writes."""
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

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['baseline', 'final'], required=True)
    args = parser.parse_args()
    from backend.database.mongodb import users_collection, issues_collection, reservations_collection, reading_list_collection
    from backend.services.identity_service import current_identity
    from backend.utils.jwt_utils import create_access_token
    from rag.book_assets import indexed_books
    users = [u for u in users_collection.find({'role':'GENERAL_USER','is_email_verified':True}) if current_identity({'sub':str(u['user_id'])})]
    def auth(user):
        return {'Authorization':'Bearer '+create_access_token(user['user_id'],user['email'],user['role'])}
    headers = auth(users[0])
    indexed = set(indexed_books())
    eligible = [(u, loan) for u in users for loan in issues_collection.find({'user_id':u['user_id'],'status':'ISSUED'}) if loan.get('work_id') in indexed]
    book_user, loan = eligible[0]
    config = json.loads((ROOT/'reports/assistant_latency_cases.json').read_text())
    seeds, doc = config['seeds'], config['document_id']
    collections = [issues_collection, reservations_collection, reading_list_collection]
    before = [digest(list(c.find({}))) for c in collections]
    profile_path = ROOT/f'reports/part3_repair_profiles_{args.phase}.jsonl'
    output = ROOT/f'reports/part3_repair_latency_{args.phase}_raw.json'
    result = {'phase':args.phase,'real_services':True,'mutations_enabled':False,'runs':[], 'checks':[], 'health':None}
    def save():
        output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    with httpx.Client(timeout=180) as client:
        result['health'] = client.get('http://127.0.0.1:8005/health').json()
        def call(case,payload,credentials=headers,measure=True,round_number=None):
            started=time.perf_counter()
            response=client.post('http://127.0.0.1:8005/assistant/chat',headers=credentials,json=payload)
            total=(time.perf_counter()-started)*1000
            body=response.json()
            trace=response.headers.get('x-assistant-trace')
            profile=None
            for _ in range(20):
                rows=[json.loads(s) for s in profile_path.read_text().splitlines() if s] if profile_path.exists() else []
                profile=next((r for r in rows if r['trace_id']==trace),None)
                if profile: break
                time.sleep(.025)
            rag=body.get('rag') or {}
            row={'case':case,'round':round_number,'status':response.status_code,'intent':body.get('intent'),'client_total_ms':round(total,2),'profile':profile,
                'book_ids':[b['work_id'] for b in body.get('books',[])],'seed_work_ids':body.get('seed_work_ids'),'recommendation_mode':body.get('recommendation_mode'),
                'has_more':body.get('has_more'),'result_offset':body.get('result_offset'),'error_codes':[e['code'] for e in body.get('errors',[])],
                'rag_verdict':rag.get('verdict'),'rag_answer':rag.get('answer'),'rag_source_count':len(rag.get('sources',[])),'rag_timing_ms':rag.get('timing_ms'),
                'rag_source_ids':[{'work_id':s.get('work_id'),'filename':s.get('filename'),'chunk_id':s.get('chunk_id')} for s in rag.get('sources',[])],
                'reading_list_count':len(body.get('reading_list') or []),'account_digest':digest(body.get('account')),'pending_present':bool(body.get('pending_action'))}
            if measure:
                result['runs'].append(row);save()
                print(json.dumps({'case':case,'round':round_number,'ms':row['client_total_ms'],'calls':profile['qwen_call_count'] if profile else None,'errors':row['error_codes']}),flush=True)
            return body,row
        call('warmup',{'message':'What is Gothic fiction?'},measure=False)
        call('search_warmup',{'message':'Find books about neural networks'},measure=False)
        for number in range(1,4):
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
                ('document_rag',{'message':'According to this PDF, what is role-based access control?','action':'DOCUMENT_QUESTION','page_context':{'document_id':doc}},headers),
            ]:
                body,row=call(name,payload,credentials,round_number=number)
                if name=='single_seed':
                    call('explain_recommendation',{'message':'Why these recommendations?','action':'EXPLAIN_RECOMMENDATION','conversation_id':body['conversation_id'],'selected_work_ids':[]},round_number=number)
                if name=='compare':
                    call('explain_comparison',{'message':'Explain comparison','action':'EXPLAIN_COMPARISON','conversation_id':body['conversation_id'],'selected_work_ids':[]},round_number=number)
        # Read-only live state/routing/security checks, separate from the benchmark.
        def check(name,payload,credentials=headers,predicate=lambda b,r:r['status']==200 and not r['error_codes']):
            body,row=call(name,payload,credentials,measure=False)
            result['checks'].append({'case':name,'pass':bool(predicate(body,row)),'evidence':row});save()
            return body
        state=check('continuation_setup',{'message':'Find books about neural networks'})
        if state.get('has_more'):
            check('continuation',{'message':'Show more','action':'SHOW_MORE','result_offset':len(state['books']),'conversation_id':state['conversation_id']},predicate=lambda b,r:r['status']==200 and not r['error_codes'] and not ({x['work_id'] for x in state['books']} & set(r['book_ids'])) and r['result_offset']==len(state['books']) and r['profile']['qwen_call_count']==0)
        check('available_only_refinement',{'message':'only available ones','conversation_id':state['conversation_id']},predicate=lambda b,r:r['intent']=='SEARCH_BOOKS' and not r['error_codes'] and r['profile']['qwen_call_count']==0 and all((x.get('available_copies') or 0)>0 for x in b['books']))
        recommended=check('recommendation_continuation_setup',{'message':'Recommend','action':'RECOMMEND_SIMILAR','selected_work_ids':seeds[:1]})
        if recommended.get('has_more'):
            check('recommendation_continuation',{'message':'Show more','action':'SHOW_MORE','conversation_id':recommended['conversation_id'],'result_offset':len(recommended['books'])},predicate=lambda b,r:r['seed_work_ids']==seeds[:1] and r['recommendation_mode']==recommended['recommendation_mode'] and not (set(r['book_ids']) & {x['work_id'] for x in recommended['books']}) and r['profile']['qwen_call_count']==0 and not r['error_codes'])
        check('concept_after_search',{'message':'What is dystopian fiction?','conversation_id':state['conversation_id']},predicate=lambda b,r:r['intent']=='GENERAL_LIBRARY_HELP' and not r['error_codes'])
        check('pdf_after_search',{'message':'What does this PDF say about indexing?','page_context':{'document_id':doc},'conversation_id':state['conversation_id']},predicate=lambda b,r:r['intent']=='DOCUMENT_QUESTION' and not r['error_codes'])
        check('fees_after_search',{'message':'What do I owe?','conversation_id':state['conversation_id']},predicate=lambda b,r:r['intent']=='USER_FEES' and not r['error_codes'])
        check('due_first',{'message':'Which one is due first?'},predicate=lambda b,r:r['intent']=='USER_LOANS' and not r['error_codes'])
        check('unauthenticated',{'message':'Show my loans'},{},lambda b,r:r['status']==401)
        check('invalid_token',{'message':'Show my loans'},{'Authorization':'Bearer invalid-repair-token'},lambda b,r:r['status']==401)
        check('unknown_book',{'message':'Is this available?','action':'CHECK_AVAILABILITY','selected_work_ids':['OL9999999999999W']},predicate=lambda b,r:bool(r['error_codes']) or b.get('clarification') is not None)
        if len(users)>1:
            check('cross_user_conversation',{'message':'Show my loans','conversation_id':state['conversation_id']},auth(users[1]),lambda b,r:r['status']==404 and r['profile']['qwen_call_count']==0)
        # All proposals remain disabled and never execute real transactions.
        proposal=check('reserve_disabled',{'message':'reserve this','selected_work_ids':seeds[:1]},predicate=lambda b,r:bool(b.get('pending_action')) and not r['error_codes'])
        if proposal.get('pending_action'):
            check('confirm_disabled',{'message':'Confirm','action':'CONFIRM_ACTION','pending_action_id':proposal['pending_action']['action_id'],'conversation_id':proposal['conversation_id']},predicate=lambda b,r:bool(r['error_codes']) and 'MUTATIONS_DISABLED' in r['error_codes'])
        proposal=check('pending_before_explanation',{'message':'reserve this','selected_work_ids':seeds[:1],'conversation_id':recommended['conversation_id']},predicate=lambda b,r:bool(b.get('pending_action')))
        if proposal.get('pending_action'):
            check('explanation_invalidates_pending',{'message':'Why these recommendations?','action':'EXPLAIN_RECOMMENDATION','conversation_id':proposal['conversation_id']},predicate=lambda b,r:bool(b.get('message')) and not r['pending_present'] and not r['error_codes'] and r['profile']['qwen_call_count']==1)
            check('old_confirmation_replay',{'message':'Confirm','action':'CONFIRM_ACTION','pending_action_id':proposal['pending_action']['action_id'],'conversation_id':proposal['conversation_id']},predicate=lambda b,r:r['intent']=='CLARIFICATION' and not r['pending_present'])
        check('unauthorized_book_rag',{'message':'Who is the main character?','action':'BOOK_CONTENT_QUESTION','selected_work_ids':[loan['work_id']]},predicate=lambda b,r:'HTTP_403' in r['error_codes'])
        result['real_state_unchanged']=before==[digest(list(c.find({}))) for c in collections]
        result['summary']={name:{'runs':len(rows),'min_ms':min(r['client_total_ms'] for r in rows),'median_ms':statistics.median(r['client_total_ms'] for r in rows),'max_ms':max(r['client_total_ms'] for r in rows),'qwen_calls':[r['profile']['qwen_call_count'] if r['profile'] else None for r in rows]} for name in sorted({r['case'] for r in result['runs']}) for rows in [[r for r in result['runs'] if r['case']==name]]}
        save()
        print('Complete; real state unchanged: '+str(result['real_state_unchanged']),flush=True)

if __name__=='__main__': main()
