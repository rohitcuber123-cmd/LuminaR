"""Authenticated opt-in HTTP checks. Never persist credentials/private records."""
import asyncio
import json
from pathlib import Path
import re
import sys
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import httpx
from backend.database.mongodb import books_collection,users_collection
from backend.services.identity_service import current_identity
from backend.services.book_capability_service import get_know_more_books
from backend.utils.jwt_utils import create_access_token

REPORT=ROOT/'reports/assistant_router_v4_live.json'
PROFILE=ROOT/'reports/assistant_router_v4_live_profiles.jsonl'


def save(data):REPORT.write_text(json.dumps(data,indent=2),encoding='utf8')


def profile(trace):
    if PROFILE.exists():
        for line in reversed(PROFILE.read_text(encoding='utf8').splitlines()):
            row=json.loads(line)
            if row['trace_id']==trace:return row
    return {}


async def await_profile(trace):
    for _ in range(30):
        result=profile(trace)
        if result:return result
        await asyncio.sleep(.01)
    return {}


def identifiers(data):
    if data['intent'] in {'MORE_LIKE_THIS','RECOMMEND_FROM_BOOK','RECOMMEND_FROM_SELECTION'}:return data.get('seed_work_ids',[])
    return [b['work_id'] for b in (data.get('comparison') or {}).get('books',[])] or [a['work_id'] for a in data.get('availability',[])] or [b['work_id'] for b in data.get('books',[])]


def identities_and_books():
    names=['Economics of Football','The Economics of the National Football League','Atomic Habits','Frankenstein']
    books=[books_collection.find_one({'title':{'$regex':'^'+re.escape(n)+'$','$options':'i'}}) for n in names]
    assert all(books),'Public test books missing'
    candidates=[u for u in users_collection.find({'is_email_verified':True,'role':'GENERAL_USER'}) if current_identity({'sub':str(u['user_id'])})]
    assert len(candidates)>=2,'Need two existing identities for isolation'
    first=next((u for u in candidates if get_know_more_books(u['user_id'])),candidates[0])
    second=next(u for u in candidates if u['user_id']!=first['user_id'])
    return books,first,second


async def main():
    books,first,second=identities_and_books();a,b,c,d=[row['work_id'] for row in books];ab=[a,b];cd=[c,d]
    tokens=[create_access_token(u['user_id'],u['email'],u['role']) for u in [first,second]]
    if '--context-repair-only' in sys.argv:
        report=json.loads(REPORT.read_text(encoding='utf8'))
        old=report.get('additional_context_checks',[])
        report['invalid_context_setup_attempts']=old[3:8]
        repaired=[]
        async with httpx.AsyncClient(timeout=180) as client:
            async def call(message,intent,ids,selection,conversation=None,action=None):
                payload={'message':message,'selected_work_ids':selection,'conversation_id':conversation}
                if action:payload['action']=action
                start=perf_counter();response=await client.post('http://127.0.0.1:8005/assistant/chat',headers={'Authorization':'Bearer '+tokens[0]},json=payload)
                data=response.json();p=await await_profile(response.headers.get('x-assistant-trace'));resolved=identifiers(data) if response.status_code==200 else []
                repaired.append({'message':message,'expected_intent':intent,'actual_intent':data.get('intent'),'expected_ids':ids,'resolved_ids':resolved,
                    'pass':response.status_code==200 and data.get('intent')==intent and resolved==ids and not data.get('errors'),
                    'http_status':response.status_code,'accepted':p.get('router_v4',{}).get('accepted'),'qwen_calls':p.get('qwen_call_count'),
                    'latency_ms':(perf_counter()-start)*1000,'errors':[e.get('code') for e in data.get('errors',[])],'trace_id':response.headers.get('x-assistant-trace')})
                return data.get('conversation_id')
            conv=await call('Compare selected books','COMPARE_BOOKS',ab,ab,action='COMPARE')
            await call('which has the better rating?','COMPARE_BOOKS',cd,cd,conv)
            conv=await call('Compare selected books','COMPARE_BOOKS',ab,ab,action='COMPARE')
            conv=await call('which one is available?','CHECK_AVAILABILITY',ab,[],conv)
            await call('tell me about the second','BOOK_DETAILS',[b],[],conv)
        report['additional_context_checks']=old[:3]+repaired+old[8:]
        report['context_observer_repair']='Original observer sent an invalid COMPARE_SELECTED action with null message. Only those two setup calls and dependent follow-ups were repeated using the real COMPARE contract. Model and frozen evaluations untouched.'
        save(report);print('CONTEXT OBSERVER REPAIR',sum(t['pass'] for t in repaired),'of',len(repaired));return
    report={'method':'Normal authenticated /assistant/chat endpoint with router_v4 explicitly opted in; real catalogue and frozen tools',
        'privacy':'No credentials, emails, identity IDs, account records or private chunks persisted.',
        'public_books':[{'work_id':r['work_id'],'title':r['title']} for r in books],'chains':[],'complete':False}
    coexist_only='--coexist-only' in sys.argv
    if coexist_only:
        report=json.loads(REPORT.read_text(encoding='utf8'));report['complete']=False
    def turn(message,intent,ids,selection=None,criteria=None,field=None):
        return {'message':message,'intent':intent,'ids':ids,'selection':ab if selection is None else selection,'criteria':criteria,'field':field}
    chains=[('original_sports',[
        turn('what differences do these books indicate','COMPARE_BOOKS',ab),
        turn('which one would be better','COMPARE_BOOKS',ab,criteria='CRITERIA_AMBIGUITY'),
        turn('for someone mainly interested in soccer economics','COMPARE_BOOKS',ab),
        turn('is the first one available','CHECK_AVAILABILITY',[a]),
        turn('and the other?','CHECK_AVAILABILITY',[b]),
        turn('anything similar to that one','MORE_LIKE_THIS',[b])]),
        ('second_pair',[
        turn('how do they stack up?','COMPARE_BOOKS',cd,cd),
        turn('which has more subjects?','COMPARE_BOOKS',cd,cd,field='subjects'),
        turn('what about availability?','CHECK_AVAILABILITY',cd,cd),
        turn('tell me more about the second','BOOK_DETAILS',[d],cd),
        turn('find something connected to it','MORE_LIKE_THIS',[d],cd)]),
        ('accounts',[
        turn('what books do I still have out?','USER_LOANS',[],[]),
        turn('do I owe the library anything?','USER_FEES',[],[]),
        turn('have I got any reservations?','USER_RESERVATIONS',[],[]),
        turn('what have I borrowed recently?','USER_HISTORY',[],[])]),
        ('search',[
        turn('I need a beginner-friendly book about machine learning','SEARCH_BOOKS',[],[]),
        turn('something on saving and household budgeting','SEARCH_BOOKS',[],[])]),
        ('complex',[
        turn("I want whichever of these would give me more useful background for studying the economics of professional sports, but I'm less interested in management or player salaries.",'COMPARE_BOOKS',ab)])]
    async with httpx.AsyncClient(timeout=180) as client:
        if coexist_only:chains=[]
        for name,turns in chains:
            chain={'name':name,'turns':[]};report['chains'].append(chain);conversation=None
            for case in turns:
                started=perf_counter();response=await client.post('http://127.0.0.1:8005/assistant/chat',headers={'Authorization':'Bearer '+tokens[0]},
                    json={'message':case['message'],'conversation_id':conversation,'selected_work_ids':case['selection']})
                data=response.json();conversation=data.get('conversation_id',conversation);p=await await_profile(response.headers.get('x-assistant-trace'))
                ids=identifiers(data) if response.status_code==200 else []
                semantic=p.get('router_v4',{})
                correct=(response.status_code==200 and data.get('intent')==case['intent'] and
                    (not case['ids'] or ids==case['ids']) and not data.get('errors'))
                if case['criteria']:correct=correct and (data.get('clarification') or {}).get('type')==case['criteria']
                if case['field']:correct=correct and case['field'] in (data.get('comparison') or {}).get('requested_fields',[])
                chain['turns'].append({'message':case['message'],'expected_intent':case['intent'],'actual_intent':data.get('intent'),
                    'expected_ids':case['ids'],'resolved_ids':ids,'pass':bool(correct),'http_status':response.status_code,
                    'clarification_type':(data.get('clarification') or {}).get('type'),
                    'errors':[e.get('code') for e in data.get('errors',[])],
                    'classifier_accepted':semantic.get('accepted'),'fallback_reason':semantic.get('fallback_reason'),
                    'reference':semantic.get('components',{}).get('reference'),'position':semantic.get('components',{}).get('position'),
                    'components':semantic.get('components',{}),
                    'qwen_calls':p.get('qwen_call_count'),'latency_ms':(perf_counter()-started)*1000})
                save(report);print('V4 LIVE',name,case['message'],correct,semantic.get('fallback_reason'),flush=True)
        # The same message uses different users' independent trays. We assert
        # every rendered reference belongs to its own tray, including fallback.
        isolation=[]
        async def user(i):
            own=ab if i%2==0 else cd;other=cd if i%2==0 else ab
            started=perf_counter();response=await client.post('http://127.0.0.1:8005/assistant/chat',headers={'Authorization':'Bearer '+tokens[i%2]},
                json={'message':'which one is available?','selected_work_ids':own})
            data=response.json();ids=identifiers(data) if response.status_code==200 else [];p=await await_profile(response.headers.get('x-assistant-trace'))
            isolation.append({'request':i,'user_alias':'A' if i%2==0 else 'B','own_public_tray':own,'resolved_ids':ids,
                'no_crossover':not bool(set(ids)&set(other)),'successful_book_response':bool(ids) and set(ids)<=set(own),
                'canonical_context_matches':ids==own,
                'errors':[e.get('code') for e in data.get('errors',[])],'latency_ms':(perf_counter()-started)*1000,
                'accepted':p.get('router_v4',{}).get('accepted'),'qwen_calls':p.get('qwen_call_count'),
                'trace_id':response.headers.get('x-assistant-trace'),'classifier_ms':p.get('router_v4',{}).get('classifier_ms')})
        await asyncio.gather(*(user(i) for i in range(20)))
        report['multi_user_isolation']={'requests':isolation,'no_crossover':all(r['no_crossover'] for r in isolation),
            'successful_book_responses':sum(r['successful_book_response'] for r in isolation)};save(report)
        extra=[]
        async def context_turn(message,expected,ids,selection,conversation=None,page=None,action=None):
            payload={'message':message,'selected_work_ids':selection,'conversation_id':conversation}
            if page:payload['page_context']={'work_id':page}
            if action:payload['action']=action
            start=perf_counter();response=await client.post('http://127.0.0.1:8005/assistant/chat',headers={'Authorization':'Bearer '+tokens[0]},json=payload)
            result=response.json();p=await await_profile(response.headers.get('x-assistant-trace'));resolved=identifiers(result) if response.status_code==200 else []
            extra.append({'message':message,'expected_intent':expected,'actual_intent':result.get('intent'),'expected_ids':ids,'resolved_ids':resolved,
                'pass':response.status_code==200 and result.get('intent')==expected and resolved==ids and not result.get('errors'),
                'accepted':p.get('router_v4',{}).get('accepted'),'qwen_calls':p.get('qwen_call_count'),'latency_ms':(perf_counter()-start)*1000,
                'errors':[e.get('code') for e in result.get('errors',[])]})
            return result.get('conversation_id')
        for message,intent in [('is this available?','CHECK_AVAILABILITY'),('who wrote it?','BOOK_DETAILS'),('anything like it?','MORE_LIKE_THIS')]:
            await context_turn(message,intent,[a],[],page=a)
        conv=await context_turn('Compare selected books','COMPARE_BOOKS',ab,ab,action='COMPARE')
        await context_turn('which has the better rating?','COMPARE_BOOKS',cd,cd,conv)
        conv=await context_turn('Compare selected books','COMPARE_BOOKS',ab,ab,action='COMPARE')
        conv=await context_turn('which one is available?','CHECK_AVAILABILITY',ab,[],conv)
        await context_turn('tell me about the second','BOOK_DETAILS',[b],[],conv)
        for message,intent,ids in [('whch book is avalable','CHECK_AVAILABILITY',ab),('gimme details of the 2nd','BOOK_DETAILS',[b])]:
            await context_turn(message,intent,ids,ab)
        report['additional_context_checks']=extra;save(report)
        # Final frozen candidate selects eligible routes by observed admission;
        # fallback choices remain complex interpretation, never forced labels.
        pool=['What library books are still with me?','Does my account have money due?','Show the books I am queued for',
            'Retrieve my previous borrowing activity','Show my saved reading collection','A reading guide to beekeeping would help me',
            'Find an introduction to ceramic design','Books discussing soil conservation please','Show me reading about medieval trade',
            'What titles are on loan to me?','Are there outstanding charges on my membership?','Display my past loan transactions']
        eligible=[];fallback=[]
        for message in pool:
            response=await client.post('http://127.0.0.1:8005/assistant/chat',headers={'Authorization':'Bearer '+tokens[0]},
                json={'message':message,'selected_work_ids':[]})
            p=await await_profile(response.headers.get('x-assistant-trace'))
            (eligible if p.get('router_v4',{}).get('accepted') else fallback).append(message)
        fallback+=['Explain the methods in my uploaded PDF','Summarize chapter four of this book','Help me understand membership policies',
            'Which of these suits a doctoral thesis about colonial trade and why?','Discuss the conclusion of this text','Compare these books for an advanced reader studying economic policy']
        # Respect observed eligibility, even if it falls short of the desired mix.
        messages=(eligible*14)[:14]+fallback[:6] if eligible else pool+fallback[:8]
        mixed=[]
        async def mixed_one(i,message):
            start=perf_counter();response=await client.post('http://127.0.0.1:8005/assistant/chat',headers={'Authorization':'Bearer '+tokens[i%2]},
                json={'message':message,'selected_work_ids':[] if i<14 else ab})
            result=response.json();p=await await_profile(response.headers.get('x-assistant-trace'))
            mixed.append({'request':i,'message':message,'status':response.status_code,'intent':result.get('intent'),
                'accepted':p.get('router_v4',{}).get('accepted'),'classifier_ms':p.get('router_v4',{}).get('classifier_ms'),
                'qwen_calls':p.get('qwen_call_count'),'latency_ms':(perf_counter()-start)*1000,'errors':[e.get('code') for e in result.get('errors',[])],
                'busy':any('busy' in e.get('message','').lower() for e in result.get('errors',[]))})
        start=perf_counter();await asyncio.gather(*(mixed_one(i,m) for i,m in enumerate(messages)));duration=perf_counter()-start
        report['mixed_20']={'requests':mixed,'total_seconds':duration,'throughput_per_sec':len(mixed)/duration,
            'accepted':sum(bool(r['accepted']) for r in mixed),'successes':sum(r['status']==200 and not r['errors'] for r in mixed),
            'busy_rejections':sum(r['busy'] for r in mixed),'failures':sum(r['status']!=200 or bool(r['errors']) for r in mixed),
            'eligibility_source':'Observed final candidate predictions on independent live messages; no model/threshold tuning'};save(report)
        # Disposable synthetic document: only the newly uploaded ID is removed.
        import fitz
        pdf=fitz.open();page=pdf.new_page()
        text=('The Cedar Grove library demonstration studied rainwater storage. '
              'The garden collected rainwater in a blue tank with a capacity of 250 litres. '
              'The pilot ran for twelve weeks. Volunteers measured the water level every Friday. '
              'Stored rainwater was used for the herb beds and reduced tap-water use. '
              'This is synthetic test material and contains no personal information. ')
        page.insert_textbox(fitz.Rect(50,50,550,750),text*3,fontsize=11)
        content=pdf.tobytes();pdf.close();document_id=None
        coexist={};headers={'Authorization':'Bearer '+tokens[0]}
        async def traffic():
            rows=[]
            async def call(i):
                start=perf_counter();response=await client.post('http://127.0.0.1:8005/assistant/chat',headers=headers,
                    json={'message':'Are there outstanding monetary charges against me','selected_work_ids':[]})
                p=await await_profile(response.headers.get('x-assistant-trace'));rows.append({'status':response.status_code,
                    'latency_ms':(perf_counter()-start)*1000,'accepted':p.get('router_v4',{}).get('accepted'),
                    'classifier_ms':p.get('router_v4',{}).get('classifier_ms'),'encoder_ms':p.get('router_v4',{}).get('encoder_ms'),
                    'queue_ms':p.get('router_v4',{}).get('queue_ms'),'trace_id':response.headers.get('x-assistant-trace'),
                    'qwen_calls':p.get('qwen_call_count'),'errors':[e.get('code') for e in response.json().get('errors',[])]})
            await asyncio.gather(*(call(i) for i in range(20)));return rows
        try:
            response=await client.post('http://127.0.0.1:8005/rag/upload',headers=headers,files={'file':('router_v4_disposable.pdf',content,'application/pdf')})
            coexist['document_upload_status']=response.status_code
            if response.status_code==200:
                document_id=response.json()['document']['document_id'];start=perf_counter()
                denied=await client.post('http://127.0.0.1:8005/rag/ask',headers={'Authorization':'Bearer '+tokens[1]},
                    json={'query':'What is the capacity of the rainwater storage tank?','document_id':document_id,'depth':'concise'})
                coexist['document_cross_user_status']=denied.status_code
                rag_response,traffic_rows=await asyncio.gather(client.post('http://127.0.0.1:8005/rag/ask',headers=headers,
                    json={'query':'What is the capacity of the rainwater storage tank?','document_id':document_id,'depth':'concise'}),traffic())
                result=rag_response.json();coexist['document']={'status':rag_response.status_code,'duration_ms':(perf_counter()-start)*1000,
                    'verdict':result.get('verdict'),'has_answer':bool(result.get('answer')),'classifier_traffic':traffic_rows}
            eligible=get_know_more_books(first['user_id'])
            if eligible:
                work_id=eligible[0]['work_id'];start=perf_counter()
                rag_response,traffic_rows=await asyncio.gather(client.post('http://127.0.0.1:8005/rag/ask',headers=headers,
                    json={'query':'Explain the central argument presented in the opening chapter.','work_id':work_id,'depth':'concise'}),traffic())
                result=rag_response.json();coexist['book']={'status':rag_response.status_code,'public_work_id':work_id,
                    'duration_ms':(perf_counter()-start)*1000,'verdict':result.get('verdict'),'has_answer':bool(result.get('answer')),
                    'classifier_traffic':traffic_rows,'error_type':result.get('detail') if rag_response.status_code!=200 else None}
            else:coexist['book']={'skipped':'No existing eligible active borrowed indexed book; no circulation mutation performed.'}
        finally:
            if document_id:
                removed=await client.delete('http://127.0.0.1:8005/rag/documents/'+document_id,headers=headers)
                coexist['disposable_document_removed']=removed.status_code==200 and removed.json().get('removed',False)
        report['rag_coexistence']=coexist
    report['complete']=True
    report['strict_live']={'passed':sum(r['pass'] for c in report['chains'] for r in c['turns']),
        'total':sum(len(c['turns']) for c in report['chains'])};save(report)


if __name__=='__main__':asyncio.run(main())
