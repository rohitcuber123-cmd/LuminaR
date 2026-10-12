"""Disposable localhost validation. Public reports omit source text and credentials."""
import json, sys, time, hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
TMP=ROOT/'.scratch/cloze_v2_3'
def dump(path,value):path.write_text(json.dumps(value,indent=2),encoding='utf8')
def state():return json.loads((TMP/'session.json').read_text())
def seed():
    from datetime import datetime,timezone
    from uuid import uuid4
    from backend.database.mongodb import users_collection
    from backend.services.identity_service import next_user_id
    from backend.services.auth_service import hash_password
    from backend.utils.jwt_utils import create_access_token
    assert not (TMP/'session.json').exists()
    marker='cloze-v2-3-'+uuid4().hex[:10];uid=next_user_id();email=marker+'@example.com';password='Local-cloze-fixture-2026!'
    users_collection.insert_one({'user_id':uid,'name':'Cloze test reader','email':email,'password_hash':hash_password(password),
        'role':'GENERAL_USER','is_email_verified':True,'is_active':True,'created_at':datetime.now(timezone.utc),'cloze_v2_3_marker':marker})
    dump(TMP/'session.json',{'user_id':uid,'email':email,'password':password,'marker':marker,
        'token':create_access_token(uid,email,'GENERAL_USER'),'documents':[]})
    print('Disposable reader created.')
def live():
    import httpx
    from rag.services import knowledge_cloze as c,cloze_grading as g
    from backend.utils.jwt_utils import create_access_token
    s=state();report={'router_mode':'existing_qwen','documents':[],'privacy':{}}
    if 'isolation' not in s:
        from datetime import datetime,timezone
        from backend.database.mongodb import users_collection
        from backend.services.identity_service import next_user_id
        from backend.services.auth_service import hash_password
        uid=next_user_id();email=s['marker']+'-isolation@example.com'
        users_collection.insert_one({'user_id':uid,'name':'Cloze isolation reader','email':email,'password_hash':hash_password(s['password']),
            'role':'GENERAL_USER','is_email_verified':True,'is_active':True,'created_at':datetime.now(timezone.utc),'cloze_v2_3_marker':s['marker']})
        s['isolation']={'user_id':uid,'email':email,'token':create_access_token(uid,email,'GENERAL_USER')};dump(TMP/'session.json',s)
    with httpx.Client(base_url='http://127.0.0.1:8005',headers={'Authorization':'Bearer '+s['token']},timeout=180) as client:
        for name,path in [('cn',Path('C:/Users/balak/Downloads/CN UNIT-2 NOTES.docx.pdf')),('ocr',TMP/'scanned.pdf')]:
            if name+'_id' in s:
                doc=s[name+'_id'];r=client.get('/rag/documents');r.raise_for_status();meta=next(x for x in r.json()['documents'] if x['document_id']==doc)
            else:
                with path.open('rb') as f:r=client.post('/rag/upload',files={'file':(path.name,f,'application/pdf')})
                r.raise_for_status();meta=r.json()['document'];doc=meta['document_id'];s['documents'].append(doc);s[name+'_id']=doc;dump(TMP/'session.json',s)
            row={'document':name,'pages':meta['pages'],'ocr':meta.get('ocr'),'variants':[],'mixed':{}}
            r=client.post(f'/rag/documents/{doc}/artifacts/quiz',json={'questionTypes':['fill_blank'],'questionCount':12});r.raise_for_status();artifact=r.json()['artifact']
            dump(TMP/f'{name}_live_cloze.json',artifact);row['cloze_count']=len(artifact['content']['questions'])
            assert row['cloze_count']>=10
            for item in artifact['content']['questions']:
                assert c.validate(item)
                src=client.get(f'/rag/documents/{doc}/sources/'+item['sourceChunkIds'][0]);src.raise_for_status();assert item['sourceExcerpt'] in src.json()['text']
                canonical=item['canonicalAnswer'];variants=[('exact',canonical,'CORRECT'),('case',canonical.swapcase(),'CORRECT'),
                    ('spacing','  '+canonical.replace(' ','   ')+'  ','CORRECT'),('wrong_related_term','Selective Repeat' if canonical!='Selective Repeat' else 'Go-Back-N','INCORRECT')]
                if item['blankType'] in {'TERM','ENTITY'}:
                    variants.append(('hyphen',canonical.replace(' ','-'),'CORRECT'))
                    words=canonical.split();idx=next((i for i,w in enumerate(words) if w.isalpha() and len(w)>=8),None)
                    if idx is not None:words[idx]=words[idx][:3]+words[idx][4:];variants.append(('typo',' '.join(words),'CORRECT'))
                if item['blankType'] in {'NUMBER','NUMBER_WITH_UNIT'}:variants.append(('wrong_number','999','INCORRECT'))
                url=f'/rag/documents/{doc}/artifacts/{artifact["id"]}/cloze/{item["id"]}/grade'
                for category,answer,expected in variants:
                    start=time.perf_counter();r=client.post(url,json={'answer':answer});r.raise_for_status();out=r.json()
                    assert out['verdict']==expected,(name,item['id'],category,out)
                    assert out['qwen_calls']==out['cuda_calls']==0 and r.headers['cache-control']=='no-store'
                    row['variants'].append({'item_id':item['id'],'category':category,'expected':expected,'actual':out['verdict'],
                        'page':item['pageStart'],'ms':round((time.perf_counter()-start)*1000,2),'server_ms':out['grading_ms']})
            r=client.post(f'/rag/documents/{doc}/artifacts/quiz',json={'questionTypes':['mcq','matching','fill_blank'],'questionCount':12});r.raise_for_status();mixed=r.json()['artifact'];dump(TMP/f'{name}_live_mixed.json',mixed)
            row['mixed']={'counts':mixed['content']['generatedCounts'],'coverage':mixed['content']['coverage']}
            for item in mixed['content']['questions']:
                if item['type']=='mcq':assert item['correctAnswer'] in item['options'] and len(set(item['options']))==4
                elif item['type']=='matching':assert len(item['correctMatches'])==len(item['leftItems'])
                else:
                    r=client.post(f'/rag/documents/{doc}/artifacts/{mixed["id"]}/cloze/{item["id"]}/grade',json={'answer':item['canonicalAnswer']});r.raise_for_status();assert r.json()['verdict']=='CORRECT'
            row['source_verified']=True;report['documents'].append(row);print(name,row['cloze_count'],len(row['variants']),row['mixed']['counts'],flush=True)
        wrong_sid=create_access_token(s['user_id'],s['email'],'GENERAL_USER')
        url=f'/rag/documents/{doc}/artifacts/{artifact["id"]}/cloze/{artifact["content"]["questions"][0]["id"]}/grade'
        for key,headers in [('unauthenticated',{'Authorization':''}),('wrong_session',{'Authorization':'Bearer '+wrong_sid})]:
            r=client.post(url,json={'answer':'anything'},headers=headers);report['privacy'][key]=r.status_code;assert r.status_code in (401,404)
        r=client.post(url,json={'answer':'anything'},headers={'Authorization':'Bearer '+s['isolation']['token']});assert r.status_code==404;report['privacy']['different_valid_reader']=r.status_code
        from backend.utils.jwt_utils import decode_access_token
        from backend.services.login_sessions import revoke
        revoke(decode_access_token(wrong_sid))
        r=client.post(url,json={'answer':'anything'},headers={'Authorization':'Bearer '+wrong_sid});assert r.status_code==401;report['privacy']['revoked_session']=r.status_code
        r=client.post(url,json={'answer':'anything','canonicalAnswer':'injected'});report['privacy']['client_expected_rejected']=r.status_code;assert r.status_code==422
    dump(ROOT/'reports/cloze_v2_3_live.json',report)
def performance():
    import httpx
    import statistics
    s=state();a=json.loads((TMP/'cn_live_cloze.json').read_text());items=a['content']['questions'];phrase=next(x for x in items if x['blankType'] in {'SHORT_PHRASE','DESCRIPTION'})
    report={'encoder':'existing cached CPU all-MiniLM-L6-v2','qwen_calls':0,'cuda_calls':0,'gpu_lock_used':False,'levels':[]}
    with httpx.Client(base_url='http://127.0.0.1:8005',headers={'Authorization':'Bearer '+s['token']},timeout=10) as client:
        def run(i):
            item=items[i%len(items)] if i%2==0 else phrase
            answer=item['canonicalAnswer'] if i%2==0 else 'the '+item['canonicalAnswer']+' mechanism'
            start=time.perf_counter();r=client.post(f'/rag/documents/{s["cn_id"]}/artifacts/{a["id"]}/cloze/{item["id"]}/grade',json={'answer':answer});r.raise_for_status();out=r.json()
            assert out['qwen_calls']==out['cuda_calls']==0
            return (time.perf_counter()-start)*1000,out['grading_ms']
        # First semantic grade after server startup: startup preparation handles
        # model loading, distinct answer avoids previous scalar similarities.
        cold=run(1);report['first_request_this_run_ms']=round(cold[0],2);report['first_request_this_run_server_ms']=cold[1]
        report['model_load_policy']='CPU singleton prepared before HTTP startup completes; distinct phrase stress includes uncached semantic requests.'
        for concurrency in [1,5,10,20]:
            results=[]
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                for repeat in range(3):results.extend(pool.map(run,range(concurrency)))
            times=sorted(x[0] for x in results);server=[x[1] for x in results]
            report['levels'].append({'concurrency':concurrency,'requests':len(times),'p50_ms':round(statistics.median(times),2),
                'p95_ms':round(times[max(0,int(.95*len(times))-1)],2),'max_ms':round(max(times),2),'max_server_ms':max(server)})
    report['hard_750ms_pass']=max(x['max_ms'] for x in report['levels'])<750 and cold[0]<750
    report['preferred_200ms_pass']=max(x['p95_ms'] for x in report['levels'])<200
    report['workload']='Alternating identity and phrase evidence grades. Repeated phrase keys exercise bounded scalar memoization and coalescing; includes HTTP/auth/SQLite/source checks.'
    report['unique_phrase_levels']=[]
    with httpx.Client(base_url='http://127.0.0.1:8005',headers={'Authorization':'Bearer '+s['token']},timeout=10) as client:
        for concurrency in [1,5,10,20]:
            def distinct(n):
                # Different bounded text keys per level: no scalar-cache hits.
                answer=phrase['canonicalAnswer']+' '+('method '*n)+('for this description '*([1,5,10,20].index(concurrency)+1))
                start=time.perf_counter();r=client.post(f'/rag/documents/{s["cn_id"]}/artifacts/{a["id"]}/cloze/{phrase["id"]}/grade',json={'answer':answer});r.raise_for_status();out=r.json()
                return {'ms':round((time.perf_counter()-start)*1000,2),'server_ms':out['grading_ms'],'reason':out['reason']}
            with ThreadPoolExecutor(max_workers=concurrency) as pool:results=list(pool.map(distinct,range(concurrency)))
            times=sorted(x['ms'] for x in results)
            report['unique_phrase_levels'].append({'concurrency':concurrency,'requests':len(times),'p50_ms':round(statistics.median(times),2),
                'p95_ms':times[max(0,int(.95*len(times))-1)],'max_ms':max(times),'max_server_ms':max(x['server_ms'] for x in results)})
    report['unique_phrase_note']='Distinct longer bounded submissions, separate keys at each concurrency level, shared CPU batching of source/context, no previously warmed scalar keys. Stress workload does not assume every submission is correct.'
    report['hard_750ms_pass']=report['hard_750ms_pass'] and max(x['max_ms'] for x in report['unique_phrase_levels'])<750
    dump(ROOT/'reports/cloze_v2_3_performance.json',report);print(report,flush=True)
def cleanup():
    import httpx,sqlite3
    from backend.database.mongodb import users_collection
    s=state();assert s['marker'].startswith('cloze-v2-3-')
    assert users_collection.find_one({'user_id':s['user_id'],'cloze_v2_3_marker':s['marker']})
    with httpx.Client(base_url='http://127.0.0.1:8005',headers={'Authorization':'Bearer '+s['token']},timeout=60) as client:
        r=client.get('/rag/documents');r.raise_for_status();rows=r.json()['documents'];assert all(x['document_id'] in s['documents'] for x in rows)
        for x in rows:r=client.delete('/rag/documents/'+x['document_id']);r.raise_for_status()
        r=client.get('/rag/documents');r.raise_for_status();assert not r.json()['documents']
    registries=list((ROOT/'rag').rglob('registry.sqlite'));remaining=0
    for path in registries:
        with sqlite3.connect(path) as db:remaining+=db.execute('select count(*) from documents where owner=?',(str(s['user_id']),)).fetchone()[0]
    assert remaining==0,'Browser fixture session still active'
    assert users_collection.delete_one({'user_id':s['user_id'],'cloze_v2_3_marker':s['marker']}).deleted_count==1
    assert users_collection.delete_one({'user_id':s['isolation']['user_id'],'cloze_v2_3_marker':s['marker']}).deleted_count==1
    dump(ROOT/'reports/cloze_v2_3_cleanup.json',{'remaining_private_rows':0,'fixture_readers_deleted':2,'original_pdf_untouched':True,'api_documents_removed':len(rows)})
    print('Owned fixture data removed.')
if __name__=='__main__':globals()[sys.argv[1]]()
