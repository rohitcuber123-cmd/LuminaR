"""Frozen opt-in live product matrix, two real accounts and twenty sessions."""
import asyncio
import json
from pathlib import Path
import sys
from time import perf_counter
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import httpx
from backend.utils.jwt_utils import create_access_token
from backend.services.book_capability_service import get_know_more_books
from check_router_v4_live import identities_and_books,identifiers
from router_v5_evidence import write

PROFILE=ROOT/'reports/assistant_router_v5_live_profiles.jsonl'

async def profile(trace):
    for _ in range(30):
        if PROFILE.exists():
            for line in reversed(PROFILE.read_text(encoding='utf8').splitlines()):
                row=json.loads(line)
                if row['trace_id']==trace:return row
        await asyncio.sleep(.01)
    return {}

async def main():
    books,first,second=identities_and_books();a,b,c,d=[r['work_id'] for r in books];ab=[a,b];cd=[c,d]
    tokens=[create_access_token(u['user_id'],u['email'],u['role']) for u in [first,second]]
    report={'method':'Normal opt-in /assistant/chat, existing authoritative services; twenty concurrent conversations using two existing verified accounts.',
            'privacy':'Only public book IDs, numeric timings, action labels and error codes persisted; no credentials, emails, account records or private source chunks.',
            'turns':[],'complete':False,'physical_accounts':2}
    async with httpx.AsyncClient(timeout=180) as client:
        async def call(message,intent,ids=(),selection=(),conversation=None,page=None,action=None,user=0,field=None,clarification=None,group='matrix'):
            payload={'message':message,'selected_work_ids':list(selection),'conversation_id':conversation}
            if page:payload['page_context']={'work_id':page}
            if action:payload['action']=action
            start=perf_counter();response=await client.post('http://127.0.0.1:8005/assistant/chat',headers={'Authorization':'Bearer '+tokens[user]},json=payload)
            data=response.json();p=await profile(response.headers.get('x-assistant-trace'));resolved=identifiers(data) if response.status_code==200 else []
            expected_ids=list(ids)
            okay=response.status_code==200 and data.get('intent')==intent and not data.get('errors')
            # Topic Search returns result IDs, while expected IDs represent seeds.
            if intent!='SEARCH_BOOKS' and (expected_ids or intent.startswith('USER_')):okay=okay and resolved==expected_ids
            if field:okay=okay and field in (data.get('comparison') or {}).get('requested_fields',[])
            if clarification:okay=okay and (data.get('clarification') or {}).get('type')==clarification
            sem=p.get('router_v5',{})
            row={'message':message,'group':group,'expected_intent':intent,'actual_intent':data.get('intent'),'expected_ids':expected_ids,
                 'resolved_ids':resolved,'pass':bool(okay),'status':response.status_code,'accepted':sem.get('accepted',False),
                 'binding_source':sem.get('binding_source'),'binding_count':sem.get('binding_count'),'reason':sem.get('reason'),
                 'fallback_entity_extraction_used':sem.get('fallback',{}).get('entity_extraction_used'),
                 'qwen_calls':p.get('qwen_call_count'),'routing_calls':sem.get('qwen_routing_calls',0),'classifier_ms':sem.get('classifier_ms'),
                 'latency_ms':1000*(perf_counter()-start),'server_ms':p.get('total_ms'),
                 'clarification_type':(data.get('clarification') or {}).get('type'),
                 'errors':[e.get('code') for e in data.get('errors',[])],
                 'busy':any('busy' in e.get('message','').lower() for e in data.get('errors',[]))}
            return data.get('conversation_id'),row,data
        async def check(*args,**kw):
            conv,row,_=await call(*args,**kw);report['turns'].append(row);write('live',report)
            print('LIVE',row['group'],row['message'],row['pass'],row['reason'],flush=True);return conv
        for message,intent in [('what books do I still have out?','USER_LOANS'),('do I owe the library anything?','USER_FEES'),
                               ('have I got any reservations?','USER_RESERVATIONS'),('what have I borrowed recently?','USER_HISTORY')]:
            await check(message,intent,group='account')
        for message,field,clarification in [('how do they stack up?',None,None),('what separates them?',None,None),
                                           ('which one is better?',None,'CRITERIA_AMBIGUITY'),('which has the higher rating?','average_rating',None)]:
            await check(message,'COMPARE_BOOKS',ab,ab,field=field,clarification=clarification,group='comparison')
        conv=await check('Compare selected books','COMPARE_BOOKS',ab,ab,action='COMPARE',group='setup')
        conv=await check('which one is available?','CHECK_AVAILABILITY',ab,conversation=conv,group='previous')
        conv=await check('tell me more about the second','BOOK_DETAILS',[b],conversation=conv,group='previous')
        await check('anything connected to it?','MORE_LIKE_THIS',[b],conversation=conv,group='previous')
        conv=await check('Compare selected books','COMPARE_BOOKS',ab,ab,action='COMPARE',group='setup')
        await check('which has the better rating?','COMPARE_BOOKS',cd,cd,conv,field='average_rating',group='selection_change')
        for message,intent in [('is this available?','CHECK_AVAILABILITY'),('who wrote it?','BOOK_DETAILS'),('anything like it?','MORE_LIKE_THIS')]:
            await check(message,intent,[a],page=a,group='page')
        await check('find books about vampires','SEARCH_BOOKS',group='discovery')
        await check('recommend something based on these','RECOMMEND_FROM_SELECTION',ab,ab,group='discovery')
        await check('anything connected to this book','MORE_LIKE_THIS',[a],page=a,group='discovery')
        conv=await check('is the first one available','CHECK_AVAILABILITY',[a],ab,group='short_setup')
        await check('and the other?','CHECK_AVAILABILITY',[b],ab,conv,group='short')
        await check('what about availability?','CHECK_AVAILABILITY',ab,ab,group='short')
        await check('anything similar?','MORE_LIKE_THIS',[a],page=a,group='short')
        await check('what about my fees?','USER_FEES',group='short')
        dracula=[r['work_id'] for r in __import__('backend.database.mongodb',fromlist=['books_collection']).books_collection.find({'title':{'$regex':'^Dracula$','$options':'i'}},{'work_id':1}).limit(20)]
        if dracula:
            _,row,data=await call('Tell me about Dracula','BOOK_DETAILS',dracula[:1],ab,group='literal')
            # Multiple exact works can correctly require a title choice. Do not
            # label that legitimate ambiguity as a failed entity extraction.
            if len(dracula)>1 and data.get('intent')=='CLARIFICATION':
                choices=(data.get('clarification') or {}).get('choices',[])
                row['pass']=bool(row['status']==200 and row['fallback_entity_extraction_used'] and choices and
                                 all(b['work_id'] in dracula for b in choices) and not data.get('errors'))
                row['catalogue_ambiguity_expected']=True
            report['turns'].append(row);write('live',report)
        else:report['literal_skipped']='Exact Dracula catalogue entry absent; literal extraction is covered by sealed and unit tests.'
        # Accepted CPU route: exact DEV-admitted meaning used only as a load
        # probe, never counted as an independent natural-language result.
        load_message='Give a neutral overview of differences between these works.'
        async def isolated(i):
            own=ab if i%2==0 else cd;other=cd if i%2==0 else ab
            _,row,_=await call(load_message,'COMPARE_BOOKS',own,own,user=i%2,group='load_probe')
            row.update(request=i,user_alias='A' if i%2==0 else 'B',no_crossover=not bool(set(row['resolved_ids'])&set(other)))
            return row
        isolation=await asyncio.gather(*(isolated(i) for i in range(20)))
        report['isolation_20']={'requests':isolation,'no_crossover':all(r['no_crossover'] for r in isolation),
                                'semantic_correct':sum(r['pass'] for r in isolation),'accepted':sum(r['accepted'] for r in isolation),
                                'p95_ms':float(np.quantile([r['latency_ms'] for r in isolation],.95))};write('live',report)
        mixed_cases=[('Do I have charges due to the library?','USER_FEES',[],[]) for _ in range(7)]+[(load_message,'COMPARE_BOOKS',ab,ab) for _ in range(7)]+[
            ('what books do I still have out?','USER_LOANS',[],[]),('what have I borrowed recently?','USER_HISTORY',[],[]),
            ('which has the higher rating?','COMPARE_BOOKS',ab,ab),('tell me more about the second','BOOK_DETAILS',[b],ab),
            ('find books about vampires','SEARCH_BOOKS',[],[]),('anything connected to this book','MORE_LIKE_THIS',[a],[a])]
        async def mixed_one(i,case):
            message,intent,ids,selection=case
            _,row,_=await call(message,intent,ids,selection,user=i%2,field='average_rating' if i==16 else None,group='mixed')
            row['request']=i;return row
        start=perf_counter();mixed=await asyncio.gather(*(mixed_one(i,r) for i,r in enumerate(mixed_cases)))
        report['mixed_20']={'requests':mixed,'accepted':sum(r['accepted'] for r in mixed),'fallback':sum(not r['accepted'] for r in mixed),
                            'busy':sum(r['busy'] for r in mixed),'semantic_correct':sum(r['pass'] for r in mixed),
                            'p95_ms':float(np.quantile([r['latency_ms'] for r in mixed],.95)),
                            'seconds':perf_counter()-start,'scope':'Routing/product action correctness; two physical accounts, twenty conversations; some admitted probes repeat DEV language.'};write('live',report)
        import fitz
        pdf=fitz.open();page=pdf.new_page();text='Synthetic Cedar Grove pilot collected rainwater in a blue tank with capacity 250 litres. Volunteers measured the level every Friday for twelve weeks. '
        page.insert_textbox(fitz.Rect(50,50,550,750),text*8,fontsize=11);content=pdf.tobytes();pdf.close()
        headers={'Authorization':'Bearer '+tokens[0]};doc=None;coexist={}
        async def traffic():
            async def one(i):
                _,row,_=await call('Do I have charges due to the library?','USER_FEES',user=i%2,group='rag_coexistence')
                return row
            return await asyncio.gather(*(one(i) for i in range(20)))
        try:
            response=await client.post('http://127.0.0.1:8005/rag/upload',headers=headers,files={'file':('router_v5_disposable.pdf',content,'application/pdf')})
            coexist['upload_status']=response.status_code
            if response.status_code==200:
                doc=response.json()['document']['document_id']
                denied=await client.post('http://127.0.0.1:8005/rag/ask',headers={'Authorization':'Bearer '+tokens[1]},json={'query':'What is the tank capacity?','document_id':doc,'depth':'concise'})
                coexist['cross_user_status']=denied.status_code
                response,rows=await asyncio.gather(client.post('http://127.0.0.1:8005/rag/ask',headers=headers,
                      json={'query':'What is the tank capacity?','document_id':doc,'depth':'concise'}),traffic())
                coexist['document']={'status':response.status_code,'has_answer':bool(response.json().get('answer')),'traffic':rows,
                                      'server_p95_ms':float(np.quantile([r['server_ms'] for r in rows],.95))}
            available=get_know_more_books(first['user_id'])
            if available:
                response,rows=await asyncio.gather(client.post('http://127.0.0.1:8005/rag/ask',headers=headers,
                    json={'query':'Explain the central argument in the opening chapter.','work_id':available[0]['work_id'],'depth':'concise'}),traffic())
                coexist['book']={'status':response.status_code,'has_answer':bool(response.json().get('answer')),'traffic':rows,
                                  'server_p95_ms':float(np.quantile([r['server_ms'] for r in rows],.95))}
            else:coexist['book']={'skipped':'No existing eligible borrowed indexed book; circulation left unchanged.'}
        finally:
            if doc:
                removed=await client.delete('http://127.0.0.1:8005/rag/documents/'+doc,headers=headers)
                coexist['disposable_document_removed']=removed.status_code==200 and removed.json().get('removed',False)
        report['rag_coexistence']=coexist
    report['complete']=True;report['strict_live']={'correct':sum(r['pass'] for r in report['turns'] if r['group']!='setup'),
        'total':sum(r['group']!='setup' for r in report['turns'])};write('live',report)

if __name__=='__main__':asyncio.run(main())
