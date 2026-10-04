"""Opt-in read-only live assistant HTTP checks. No credentials persisted."""
import json
from pathlib import Path
import re
import sys
import time
import httpx
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.database.mongodb import books_collection, users_collection
from backend.services.identity_service import current_identity
from backend.utils.jwt_utils import create_access_token


def main():
    names = ['Economics of Football','The Economics of the National Football League']
    books = [books_collection.find_one({'title':{'$regex':'^'+re.escape(name)+'$','$options':'i'}}) for name in names]
    assert all(books), 'Required live titles missing'
    ids = [b['work_id'] for b in books]
    user = next(u for u in users_collection.find({'is_email_verified':True,'role':'GENERAL_USER'})
                if current_identity({'sub':str(u['user_id'])}))
    token = create_access_token(user['user_id'],user['email'],user['role'])
    report={'method':'authenticated HTTP /assistant/chat against normal RAG service; public catalogue only',
            'selected_work_ids':ids,'chains':[]}
    path=ROOT/'reports/assistant_semantic_router_http.json'
    profile_path=ROOT/'reports/assistant_semantic_router_http_profiles.jsonl'
    primary=[('what differences do these books indicate','COMPARE_BOOKS',ids,None),
        ('which one would be better','COMPARE_BOOKS',ids,'CRITERIA_AMBIGUITY'),
        ('for someone mainly interested in soccer economics','COMPARE_BOOKS',ids,None),
        ('is the first one available','CHECK_AVAILABILITY',[ids[0]],None),
        ('and the other?','CHECK_AVAILABILITY',[ids[1]],None),
        ('anything similar to that one','MORE_LIKE_THIS',[ids[1]],None)]
    secondary=[('tell me how they differ','COMPARE_BOOKS',ids,None),
        ('and which one is available','CHECK_AVAILABILITY',ids,None),
        ("what about the first one's subjects",'BOOK_DETAILS',[ids[0]],None),
        ('anything similar to that one','MORE_LIKE_THIS',[ids[0]],None)]
    with httpx.Client(timeout=70,headers={'Authorization':'Bearer '+token}) as client:
        for name,entries in [('required_six_turns',primary),('additional_four_turns',secondary)]:
            conversation=None; chain={'name':name,'turns':[]};report['chains'].append(chain)
            for message,intent,expected,clarification in entries:
                started=time.perf_counter();result=client.post('http://127.0.0.1:8005/assistant/chat',json={
                    'message':message,'selected_work_ids':ids,'conversation_id':conversation})
                result.raise_for_status();response=result.json();conversation=response['conversation_id']
                resolved=(response.get('seed_work_ids') if intent=='MORE_LIKE_THIS' else
                    [b['work_id'] for b in (response.get('comparison') or {}).get('books',[])])
                if not resolved:resolved=[b['work_id'] for b in response.get('books',[])]
                actual_clarification=(response.get('clarification') or {}).get('type')
                profile=None
                if profile_path.exists():
                    traces=[json.loads(line) for line in profile_path.read_text().splitlines()]
                    profile=next((r for r in reversed(traces) if r['trace_id']==result.headers.get('x-assistant-trace')),None)
                good=response['intent']==intent and resolved==expected and actual_clarification==clarification and not response.get('errors')
                if profile:good=good and profile['qwen_intent_calls']==1 and profile['qwen_response_calls']==0
                chain['turns'].append({'message':message,'expected_intent':intent,'expected_ids':expected,
                    'response':response,'resolved_ids':resolved,'http_status':result.status_code,
                    'elapsed_ms':(time.perf_counter()-started)*1000,'profile':profile,'pass':good})
                path.write_text(json.dumps(report,indent=2),encoding='utf8')
                print(name,message,response['intent'],good,flush=True)
        result=client.post('http://127.0.0.1:8005/assistant/chat',json={'message':'Compare selected books','action':'COMPARE','selected_work_ids':ids})
        result.raise_for_status(); response=result.json();profile=None
        if profile_path.exists():
            traces=[json.loads(line) for line in profile_path.read_text().splitlines()]
            profile=next((r for r in reversed(traces) if r['trace_id']==result.headers.get('x-assistant-trace')),None)
        report['structured_compare']={'response':response,'profile':profile,'pass':response['intent']=='COMPARE_BOOKS' and bool(profile and profile['qwen_call_count']==0)}
    turns=[r for chain in report['chains'] for r in chain['turns']]
    report['total']=len(turns);report['passed']=sum(r['pass'] for r in turns);report['complete']=True
    path.write_text(json.dumps(report,indent=2),encoding='utf8')
    print('HTTP complete',report['passed'],'/',report['total'], 'button',report['structured_compare']['pass'],flush=True)

if __name__=='__main__':main()
