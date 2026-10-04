"""Baseline restoration smoke test. Writes only new V2 restoration evidence."""
import json
from pathlib import Path
import re
import sys
import time
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.database.mongodb import books_collection,users_collection
from backend.services.identity_service import current_identity
from backend.utils.jwt_utils import create_access_token


def main():
    names=['Economics of Football','The Economics of the National Football League']
    books=[books_collection.find_one({'title':{'$regex':'^'+re.escape(n)+'$','$options':'i'}}) for n in names]
    assert all(books)
    ids=[b['work_id'] for b in books]
    user=next(u for u in users_collection.find({'is_email_verified':True,'role':'GENERAL_USER'})
        if current_identity({'sub':str(u['user_id'])}))
    token=create_access_token(user['user_id'],user['email'],user['role'])
    turns=[('what differences do these books indicate','COMPARE_BOOKS',ids,None),
        ('which one would be better','COMPARE_BOOKS',ids,'CRITERIA_AMBIGUITY'),
        ('for someone mainly interested in soccer economics','COMPARE_BOOKS',ids,None),
        ('is the first one available','CHECK_AVAILABILITY',[ids[0]],None),
        ('and the other?','CHECK_AVAILABILITY',[ids[1]],None),
        ('anything similar to that one','MORE_LIKE_THIS',[ids[1]],None)]
    report={'variant':'restored compact baseline; V2 disabled','turns':[],'complete':False}
    path=ROOT/'reports/assistant_router_v2_restored_live.json'
    sink=ROOT/'reports/assistant_router_v2_restored_profiles.jsonl'
    def profile(result):
        if sink.exists():
            for line in reversed(sink.read_text(encoding='utf8').splitlines()):
                row=json.loads(line)
                if row['trace_id']==result.headers.get('x-assistant-trace'):return row
    with httpx.Client(timeout=90,headers={'Authorization':'Bearer '+token}) as client:
        conversation=None
        for message,intent,expected,clarification in turns:
            result=client.post('http://127.0.0.1:8005/assistant/chat',json={
                'message':message,'selected_work_ids':ids,'conversation_id':conversation})
            result.raise_for_status();data=result.json();conversation=data['conversation_id']
            actual=data.get('seed_work_ids',[]) if intent=='MORE_LIKE_THIS' else [b['work_id'] for b in (data.get('comparison') or {}).get('books',[])]
            if not actual:actual=[b['work_id'] for b in data.get('books',[])]
            p=profile(result)
            good=data['intent']==intent and actual==expected and (data.get('clarification') or {}).get('type')==clarification and not data.get('errors')
            good=good and bool(p and p['qwen_call_count']==1 and p['qwen_response_calls']==0 and 'router_v2' not in p)
            report['turns'].append({'message':message,'actual_intent':data['intent'],'resolved_ids':actual,'profile':p,'pass':good})
            path.write_text(json.dumps(report,indent=2),encoding='utf8')
            print('RESTORED',message,data['intent'],good,flush=True)
        result=client.post('http://127.0.0.1:8005/assistant/chat',json={'message':'Compare selected books','action':'COMPARE','selected_work_ids':ids})
        result.raise_for_status();p=profile(result)
        report['structured_compare_zero_qwen']=bool(p and p['qwen_call_count']==0 and result.json()['intent']=='COMPARE_BOOKS')
    report.update(complete=True,passed=sum(t['pass'] for t in report['turns']),total=len(turns))
    path.write_text(json.dumps(report,indent=2),encoding='utf8')
    print('RESTORED COMPLETE',report['passed'],'/',report['total'],flush=True)


if __name__=='__main__':main()
