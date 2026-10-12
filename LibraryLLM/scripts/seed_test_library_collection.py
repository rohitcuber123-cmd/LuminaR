"""Persistent manual QA seed through real authenticated canonical APIs.

Password is runtime input only. Never writes credentials, tokens or auth payloads
to reports. Global collection is accessed through a read-only Mongo interface.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from uuid import NAMESPACE_URL, uuid5, uuid4
import bcrypt
import httpx
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT=Path(__file__).resolve().parents[1]
SEED='LUMINAR_TEST_LIBRARY_QA_2026'
KEYWORDS=['computer','programming','artificial intelligence','data science','mathematics','physics',
          'engineering','network','security','literature','history','philosophy','economics','business','biology','science','fiction']
LOCAL=[('TEST Community Oral History Handbook',['Local history','Community archives']),
       ('TEST Makerspace Equipment Guide',['Engineering','Library instruction']),
       ('TEST Reading Circle Discussion Notes',['Literature','Reading groups']),
       ('TEST Campus Network Practice Workbook',['Computer networks','Technical education'])]


def fingerprint(row):
    return hashlib.sha256(json.dumps(row,sort_keys=True,default=str,ensure_ascii=False).encode()).hexdigest()


def values(raw, limit, width):
    source=re.split(r'[|;]',raw) if isinstance(raw,str) else raw or []
    return list(dict.fromkeys(v.strip() for v in source if isinstance(v,str) and 0<len(v.strip())<=width))[:limit]


def metadata(row):
    title=row.get('title'); subjects=values(row.get('subjects'),30,200)
    if not isinstance(title,str) or not title.strip() or len(title.strip())>500 or not subjects:
        return None
    return {'title':title.strip(),'subjects':subjects,'authors':values(row.get('authors'),25,300), 'global_work_id':row['work_id']}


def candidates(global_books, categories, existing):
    """Indexed fixed windows + existing category previews, no global rewrite."""
    existing_works={r.get('global_work_id') for r in existing}
    existing_titles={re.sub(r'\s+',' ',r['title'].strip().casefold()) for r in existing}
    raw={}
    fields={'_id':0,'book_id':1,'work_id':1,'title':1,'authors':1,'subjects':1}
    # The production category collection contains over a million labels.
    # Bound this operator sample too; never materialize that entire collection.
    names=['Computer science','Computers','Programming','Artificial intelligence','Data science','Mathematics',
           'Physics','Engineering','Computer networks','Cybersecurity','Literature','History','Philosophy',
           'Economics','Business','Biology','Science','Fiction','Nonfiction']
    anchors=list(categories.find({'name':{'$in':names}}, {'_id':0,'name':1,'preview_book':1}).sort('name',1).limit(40))
    for category in anchors:
        if any(k in str(category.get('name','')).casefold() for k in KEYWORDS):
            work=(category.get('preview_book') or {}).get('work_id')
            row=global_books.find_one({'work_id':work},fields) if work else None
            if row: raw[row['work_id']]=row
    starts=[1]+[1+int(hashlib.sha256((SEED+':'+str(i)).encode()).hexdigest()[:8],16)%4_999_700 for i in range(20)]
    for start in starts:
        for row in global_books.find({'book_id':{'$gte':start}},fields).sort('book_id',1).limit(250):
            if re.fullmatch(r'OL[0-9]+W',str(row.get('work_id',''))): raw[row['work_id']]=row
    buckets=defaultdict(list)
    for work,row in raw.items():
        data=metadata(row)
        if not data or work in existing_works or re.sub(r'\s+',' ',data['title'].casefold()) in existing_titles: continue
        subjects=' '.join(data['subjects']).casefold()
        bucket=next((k for k in KEYWORDS if k in subjects),'other')
        buckets[bucket].append(data)
    for rows in buckets.values(): rows.sort(key=lambda row:hashlib.sha256((SEED+':'+row['global_work_id']).encode()).hexdigest())
    result=[]; used=set(existing_titles)
    while any(buckets.values()):
        for key in sorted(buckets):
            if not buckets[key]: continue
            row=buckets[key].pop(0); title=re.sub(r'\s+',' ',row['title'].casefold())
            if title not in used: result.append(row); used.add(title)
    return result


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--apply',action='store_true')
    parser.add_argument('--core',default='http://127.0.0.1:8088'); parser.add_argument('--email',default='rohitcuber123@gmail.com')
    args=parser.parse_args(); load_dotenv(ROOT/'.env')
    mongo=MongoClient(os.getenv('MONGO_URI'),serverSelectionTimeoutMS=5000); database=mongo['luminar_library']
    account=database.users.find_one({'email':args.email})
    libraries=list(database.institution_libraries.find({'name':'TEST','owner_user_id':account['user_id'],'status':'ACTIVE'})) if account else []
    if len(libraries)!=1: raise RuntimeError('Exactly one existing TEST library owned by the supplied account must be proven.')
    library=libraries[0]; lid=library['library_id']; scope={'library_id':lid}; base='/libraries/'+lid
    before=list(database.institution_library_books.find(scope,{'_id':0})); before_hash={r['library_book_id']:fingerprint(r) for r in before}
    global_before=database.books.estimated_document_count(); sample=candidates(database.books,database.book_categories,before)
    existing_local=sum(not r.get('global_work_id') and not r.get('isbn_10') and not r.get('isbn_13') for r in before if r.get('status')=='ACTIVE')
    local_to_add=[(title,subjects) for title,subjects in LOCAL if not any(r['title'].casefold()==title.casefold() for r in before)][:max(0,4-existing_local)]
    active_before=sum(r.get('status')=='ACTIVE' for r in before)
    linked_to_add=sample[:max(0,150-active_before-len(local_to_add))]
    source_rows={r['global_work_id']:database.books.find_one({'work_id':r['global_work_id']},{'_id':0}) for r in linked_to_add}
    source_hash={work:fingerprint(row) for work,row in source_rows.items()}
    report={'library_name':'TEST','library_id':lid,'owner_user_id':account['user_id'],'seed':SEED,'apply':args.apply,
        'test_books_before':active_before,'global_book_count_before':global_before,'existing_book_hashes':before_hash,
        'planned_global_linked':len(linked_to_add),'planned_local_only':len(local_to_add),'source_hashes_before':source_hash,
        'sampling':'Existing category previews and 21 indexed fixed 250-book windows; SHA256 ordering and round-robin actual subject buckets.',
        'global_linked_added':0,'local_only_added':0,'holdings_created':0,'created_ids':[]}
    target=ROOT/'reports/test_library_seed.json'
    if target.exists():
        prior=json.loads(target.read_text(encoding='utf8'))
        if prior.get('apply') and prior.get('status')=='PASS':
            print('TEST has a completed persistent seed; use its existing report for original before/after evidence.'); return
    target.write_text(json.dumps(report,indent=2),encoding='utf8')
    if not args.apply:
        print(json.dumps({k:report[k] for k in ['library_id','test_books_before','planned_global_linked','planned_local_only','global_book_count_before']},indent=2)); return
    password=getpass.getpass('Local development account password (runtime only): ')
    with httpx.Client(timeout=90) as client:
        def login(email):
            response=client.post(args.core+'/auth/login',json={'email':email,'password':password})
            response.raise_for_status(); return {'Authorization':'Bearer '+response.json()['access_token']}
        owner=login(args.email); report['test_account_used']=True
        def call(headers,method,path,body=None,expected=200):
            response=client.request(method,args.core+path,headers=headers,json=body)
            if response.status_code!=expected: raise RuntimeError(f'{method} {path}: {response.status_code} {response.text[:300]}')
            return response.json()
        source=call(owner,'GET',base+'/catalogue/source'); report['catalogue_source_before']=source['catalogue_source']
        if source['circulation_state']!='CANONICAL':
            preflight=call(owner,'GET',base+'/staff/canonical-defaults/preflight')
            (ROOT/'reports/canonical_empty_library_promotion.json').write_text(json.dumps(preflight,indent=2),encoding='utf8')
            if not preflight['safe']: raise RuntimeError('TEST promotion is blocked; retain it and follow reported migration procedure.')
            call(owner,'POST',base+'/staff/canonical-defaults/promote',{'idempotency_key':str(uuid5(NAMESPACE_URL,SEED+':promotion:'+lid))})
        # A separate real development account with the provided development
        # password is selected only after password verification. No auth bypass.
        patron=None
        for user in database.users.find({'user_id':{'$ne':account['user_id']},'role':'GENERAL_USER','is_email_verified':True,'is_active':{'$ne':False}}).sort('user_id',1):
            try: valid=bcrypt.checkpw(password.encode(),user.get('password_hash','').encode())
            except ValueError: valid=False
            membership=database.institution_memberships.find_one({**scope,'user_id':user['user_id']})
            if valid and (not membership or membership.get('role')=='GENERAL_USER'):
                patron=user; break
        report['separate_general_user_available']=bool(patron)
        if patron:
            patron_headers=login(patron['email']); call(patron_headers,'POST',base+'/join',{})
            report['patron_user_id']=patron['user_id']; report['patron_email']=patron['email']
        for n,data in enumerate([*linked_to_add,*[{'title':title,'subjects':subjects,'global_work_id':None,'authors':['TEST Library']} for title,subjects in local_to_add]]):
            linked=bool(data['global_work_id']); key=data['global_work_id'] or data['title']
            bucket=next((i for i,k in enumerate(KEYWORDS) if k in ' '.join(data['subjects']).casefold()),len(KEYWORDS))
            shelves=['CS','CS','CS','CS','MATH','SCI','ENG','CS','CS','LIT','HIS','PHI','BUS','BUS','SCI','SCI','LIT','GEN']
            copies=3 if n%29==0 else 2 if n%7==0 else 1
            payload={**data,'idempotency_key':str(uuid5(NAMESPACE_URL,SEED+':'+lid+':'+key)),
                'copies':copies,'shelf_location':f'{shelves[bucket]}-{1+bucket%4:02d}',
                'circulation_status':'CIRCULATING','acquisition_note':'Persistent local development manual QA collection.'}
            result=call(owner,'POST',base+'/inventory/books',payload,201); bid=result['library_book_id']
            status='REFERENCE_ONLY' if n in [9,39,79] else 'TEMPORARILY_UNAVAILABLE' if n in [19,59] else 'CIRCULATING'
            if status!='CIRCULATING':
                call(owner,'PUT',base+'/staff/lending/books/'+bid+'/stock',{'idempotency_key':str(uuid5(NAMESPACE_URL,SEED+':status:'+bid)),
                    'total_copies':copies,'unavailable_stock':0,'allocation_mode':'AGGREGATE','circulation_status':status})
            report['global_linked_added' if linked else 'local_only_added']+=1
            report['holdings_created']+=1; report['created_ids'].append(bid)
            target.write_text(json.dumps(report,indent=2),encoding='utf8')
        report['catalogue_source_after']=call(owner,'GET',base+'/catalogue/source')['catalogue_source']
        report['test_books_after']=database.institution_library_books.count_documents({**scope,'status':'ACTIVE'})
        report['circulation_status_counts']=dict(Counter(r.get('circulation_status','CIRCULATING') for r in database.institution_holdings.find(scope)))
        report['global_book_count_after']=database.books.estimated_document_count()
        report['global_source_records_unchanged']=all(fingerprint(database.books.find_one({'work_id':work},{'_id':0}))==digest for work,digest in source_hash.items())
        report['existing_test_records_unchanged']=all(fingerprint(database.institution_library_books.find_one({**scope,'library_book_id':bid},{'_id':0}))==digest for bid,digest in before_hash.items())
        report['owner_remains_staff_only']=database.institution_memberships.find_one({**scope,'user_id':account['user_id']})['role']=='ADMIN'
        report['preserved_for_manual_review']=True; report['hnsw_rebuilt']=False; report['kg_rebuilt']=False
        report['status']='PASS' if report['global_source_records_unchanged'] and report['existing_test_records_unchanged'] and report['owner_remains_staff_only'] else 'FAIL'
        report['completed_at']=datetime.now(timezone.utc).isoformat(); target.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({k:report[k] for k in ['status','library_id','test_books_before','test_books_after','global_linked_added','local_only_added','holdings_created','separate_general_user_available']},indent=2))


if __name__=='__main__': main()
