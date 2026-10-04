"""Read-only real catalogue/API/HTTP acceptance checks; private records excluded."""
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
    names=['Economics of Football','The Economics of the National Football League','Atomic Habits','Frankenstein']
    books=[books_collection.find_one({'title':{'$regex':'^'+re.escape(n)+'$','$options':'i'}}) for n in names]
    assert all(books),'Required public catalogue titles missing'
    a,b,c,d=[row['work_id'] for row in books];ab=[a,b];cd=[c,d]
    user=next(u for u in users_collection.find({'is_email_verified':True,'role':'GENERAL_USER'})
        if current_identity({'sub':str(u['user_id'])}))
    token=create_access_token(user['user_id'],user['email'],user['role'])
    def turn(message,intent,ids,selection=None,clarification=None,fields=None,page=None,goal=None):
        return dict(message=message,expected_intent=intent,expected_ids=ids,
            selected_work_ids=selection if selection is not None else ab,
            expected_clarification=clarification,fields=fields or [],page_context=page or {},expected_goal=goal)
    chains=[('original_six',[
        turn('what differences do these books indicate','COMPARE_BOOKS',ab,goal='FACTUAL_COMPARE'),
        turn('which one would be better','COMPARE_BOOKS',ab,clarification='CRITERIA_AMBIGUITY',goal='PREFERENCE_COMPARE'),
        turn('for someone mainly interested in soccer economics','COMPARE_BOOKS',ab,goal='PREFERENCE_COMPARE'),
        turn('is the first one available','CHECK_AVAILABILITY',[a]),
        turn('and the other?','CHECK_AVAILABILITY',[b]),
        turn('anything similar to that one','MORE_LIKE_THIS',[b])]),
        ('second_pair',[
            turn('how do they stack up?','COMPARE_BOOKS',cd,cd,goal='FACTUAL_COMPARE'),
            turn('which has more subjects?','COMPARE_BOOKS',cd,cd,fields=['subjects'],goal='COMPARE_BY_FIELD'),
            turn('what about availability?','CHECK_AVAILABILITY',cd,cd),
            turn('tell me more about the second','BOOK_DETAILS',[d],cd),
            turn('find something related to it','MORE_LIKE_THIS',[d],cd)]),
        ('previous_comparison',[
            turn('Compare selected books','COMPARE_BOOKS',ab),
            turn('which one is available?','CHECK_AVAILABILITY',ab,[]),
            turn('tell me about the second','BOOK_DETAILS',[b],[])]),
        ('selection_change',[
            turn('Compare selected books','COMPARE_BOOKS',ab),
            turn('which has the better rating?','COMPARE_BOOKS',cd,cd,fields=['average_rating'],goal='COMPARE_BY_FIELD')]),
        ('page_context',[
            turn('is this available?','CHECK_AVAILABILITY',[a],[],page={'work_id':a}),
            turn('anything like it?','MORE_LIKE_THIS',[a],[],page={'work_id':a})]),
        ('account_language',[
            turn('what do I currently have checked out?','USER_LOANS',[],[]),
            turn('do I owe anything?','USER_FEES',[],[]),
            turn('have I reserved something?','USER_RESERVATIONS',[],[]),
            turn('show me my recent borrowing activity','USER_HISTORY',[],[])]),
        ('search_language',[
            turn("I'm after something beginner-friendly about neural networks",'SEARCH_BOOKS',[],[]),
            turn('show me books dealing with household budgeting','SEARCH_BOOKS',[],[])])]
    path=ROOT/'reports/assistant_router_v2_live.json'
    profile_path=ROOT/'reports/assistant_router_v2_http_profiles.jsonl'
    report={'method':'normal authenticated HTTP endpoint; real Mongo catalogue and existing APIs; no mutations',
        'privacy':'Tokens, identity details and private account records omitted',
        'public_books':[{'work_id':row['work_id'],'title':row['title']} for row in books],
        'chains':[],'complete':False}
    def save():path.write_text(json.dumps(report,indent=2),encoding='utf8')
    def profile(trace):
        if not profile_path.exists():return None
        for line in reversed(profile_path.read_text(encoding='utf8').splitlines()):
            item=json.loads(line)
            if item['trace_id']==trace:return item
        return None
    with httpx.Client(timeout=90,headers={'Authorization':'Bearer '+token}) as client:
        for name,turns in chains:
            conversation=None;chain={'name':name,'turns':[]};report['chains'].append(chain)
            for case in turns:
                payload={k:case[k] for k in ('message','selected_work_ids','page_context')}
                payload['conversation_id']=conversation
                structured=case['message']=='Compare selected books'
                if structured:payload['action']='COMPARE'
                started=time.perf_counter();result=client.post('http://127.0.0.1:8005/assistant/chat',json=payload)
                result.raise_for_status();data=result.json();conversation=data['conversation_id']
                if data['intent'] in {'MORE_LIKE_THIS','RECOMMEND_FROM_SELECTION','RECOMMEND_FROM_BOOK'}:
                    ids=data.get('seed_work_ids',[])
                else:
                    ids=[book['work_id'] for book in (data.get('comparison') or {}).get('books',[])]
                    if not ids:ids=[book['work_id'] for book in data.get('books',[])]
                # Search IDs are result cards, not contextual references.
                if case['expected_intent']=='SEARCH_BOOKS':ids=[]
                notice=(data.get('clarification') or {}).get('type')
                observation=profile(result.headers.get('x-assistant-trace'))
                fields=(data.get('comparison') or {}).get('requested_fields',[])
                good=data['intent']==case['expected_intent'] and ids==case['expected_ids'] and notice==case['expected_clarification'] and not data.get('errors')
                good=good and set(case['fields'])<=set(fields)
                actual_goal=(observation or {}).get('router_v2',{}).get('goal')
                if case['expected_goal']:good=good and actual_goal==case['expected_goal']
                calls=observation['qwen_call_count'] if observation else None
                good=good and bool(observation and observation['qwen_response_calls']==0 and calls==(0 if structured else 1)+int(bool((observation.get('router_v2') or {}).get('retry_used'))))
                row={**case,'actual_intent':data['intent'],'resolved_ids':ids,
                    'actual_clarification':notice,'actual_goal':actual_goal,'comparison_fields':fields,'errors':[e['code'] for e in data.get('errors',[])],
                    'http_status':result.status_code,'elapsed_ms':(time.perf_counter()-started)*1000,
                    'profile':observation,'pass':bool(good),'structured_action':structured}
                if name!='account_language':row['public_result_count']=len(data.get('books',[]))
                chain['turns'].append(row);save()
                print('V2 LIVE',name,case['message'],data['intent'],good,flush=True)
            chain['passed']=sum(t['pass'] for t in chain['turns']);chain['total']=len(chain['turns'])
    rows=[t for c in report['chains'] for t in c['turns']]
    report.update(complete=True,total=len(rows),passed=sum(t['pass'] for t in rows))
    save()
    print('V2 LIVE COMPLETE',report['passed'],'/',len(rows),flush=True)


if __name__=='__main__':main()
