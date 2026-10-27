"""Canonical tenant datasets, durable fenced builds and safe status contracts."""
from datetime import timedelta
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID,uuid4
import hashlib,json,os,unicodedata
from fastapi import HTTPException
from pymongo import ReturnDocument
from backend.services.institution_repository import collection,library_mutation,now
from backend.services.library_inventory_access import require_library_staff,require_library_membership
from backend.institution_dependencies import actor_id
from backend.database.mongodb import books_collection

@contextmanager
def intelligence_barrier(library_id,job=None):
    """Tenant serialization; unresolved *index* commits belong to their own job.

    No canonical book/membership/holding mutation occurs in this barrier. Convert
    index-only errors into a handled outcome so the shared barrier is released.
    The tag also permits explicit fenced recovery after a true worker crash.
    """
    with library_mutation(library_id,wait_seconds=30,durable=True):
        if job:
            collection('locks').update_one({'_id':library_id},{'$set':{'intelligence_job_id':job['job_id']}})
        try:yield
        except HTTPException:raise
        except Exception as error:raise HTTPException(409,'WORKER_CRASH') from error

SCHEMA='tenant-catalogue-v1'
MODEL='all-MiniLM-L6-v2'
DIMENSION=384
TARGETS={'SEARCH_INDEX','KNOWLEDGE_GRAPH'}
MAX_BOOKS=50000
MAX_DATASET_BYTES=64*1024*1024
LEASE_SECONDS=90
SOURCE_FIELDS=('library_book_id','library_id','global_work_id','status','title','authors','subjects','description','isbn_10','isbn_13','publication_year','edition','publisher','classification')
def canonical(value):
    try:return str(UUID(str(value)))
    except (ValueError,TypeError,AttributeError):raise HTTPException(404,'Library intelligence resource not found.')
def root():
    path=Path(os.getenv('LIBRARY_INTELLIGENCE_ROOT',str(Path(__file__).resolve().parents[2]/'local-data/library-intelligence'))).resolve()
    for forbidden in ('knowledge_graph','indexes','search','rag/private_documents','data','artifacts'):
        protected=Path(__file__).resolve().parents[2]/forbidden
        if path==protected.resolve() or protected.resolve() in path.parents:raise HTTPException(503,'Tenant artifact root is invalid.')
    return path
def directory(library_id,kind,generation_id):
    if kind not in {'datasets','search','kg'}:raise HTTPException(404,'Artifact type not found.')
    base=root();path=base/canonical(library_id)/kind/canonical(generation_id)
    if path.resolve()!=path or base not in path.resolve().parents:raise HTTPException(404,'Artifact namespace is invalid.')
    return path
def encoded(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf8')
def checksum(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()
def durable_json(path,value):
    payload=encoded(value)
    if len(payload)>MAX_DATASET_BYTES:raise HTTPException(413,'DATASET_LIMIT')
    with Path(path).open('xb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
def text(value,limit=4096):
    return ' '.join(unicodedata.normalize('NFKC',str(value or '')).split())[:limit]
def values(value,limit=40):
    source=value.replace('|',';').split(';') if isinstance(value,str) else value if isinstance(value,(list,tuple)) else []
    return sorted({text(v,200) for v in source if text(v,200)})[:limit]
def source_records(library_id):
    library_id=canonical(library_id)
    query={'library_id':library_id,'status':'ACTIVE','title':{'$type':'string','$regex':r'\S'}}
    if collection('library_books').count_documents(query)>MAX_BOOKS:raise HTTPException(413,'DATASET_LIMIT')
    local=list(collection('library_books').find(query,{**{f:1 for f in SOURCE_FIELDS},'_id':0}).sort('library_book_id',1).limit(MAX_BOOKS))
    linked=list({r.get('global_work_id') for r in local if r.get('global_work_id')})
    enriched={}
    for offset in range(0,len(linked),500):
        for row in books_collection.find({'work_id':{'$in':linked[offset:offset+500]}},{'_id':0,'work_id':1,'title':1,'authors':1,'subjects':1,'description':1,'first_publish_date':1,'active':1,'is_active':1,'searchable':1}):
            if all(row.get(k) is not False for k in ['active','is_active','searchable']):enriched[row['work_id']]=row
    records=[]
    for row in local:
        reference=enriched.get(row.get('global_work_id'),{})
        record={k:row.get(k) for k in SOURCE_FIELDS}
        record.update(library_id=library_id,library_book_id=canonical(row['library_book_id']),title=text(row['title'],500),
            authors=values(row.get('authors') or reference.get('authors'),20),subjects=values(row.get('subjects') or reference.get('subjects')),
            description=text(row.get('description') or reference.get('description')),publication_year=text(row.get('publication_year') or reference.get('first_publish_date'),100))
        for field in ['isbn_10','isbn_13','edition','publisher','classification']:record[field]=text(record.get(field),200)
        records.append(record)
    if len(encoded(records))>MAX_DATASET_BYTES:raise HTTPException(413,'DATASET_LIMIT')
    return records
def fingerprint(records):return hashlib.sha256(encoded({'schema':SCHEMA,'records':records})).hexdigest()
def initialize():
    collection('intelligence_sequences').create_index('library_id',unique=True)
    collection('intelligence_generations').create_index('generation_id',unique=True)
    collection('intelligence_generations').create_index([('library_id',1),('sequence',1)],unique=True)
    collection('intelligence_jobs').create_index('job_id',unique=True)
    collection('intelligence_jobs').create_index([('library_id',1),('target',1)],unique=True,partialFilterExpression={'effective_active':True})
    collection('intelligence_jobs').create_index([('state',1),('created_at',1)])
    collection('intelligence_targets').create_index([('library_id',1),('target',1)],unique=True)
def safe_job(row):
    keys=('job_id','library_id','target','requested_generation_id','artifact_generation_id','state','stage','progress_current','progress_total','attempt','requested_by_user_id','created_at','started_at','heartbeat_at','completed_at','error_code','error_message')
    result={k:row.get(k) for k in keys}
    if result.get('error_code') or result.get('error_message'):
        result['error_code']='RECOVERY_REQUIRED' if row.get('state')=='RECOVERY_REQUIRED' else 'BUILD_FAILED'
        result['error_message']='The build outcome needs operator reconciliation.' if row.get('state')=='RECOVERY_REQUIRED' else 'The build did not complete. The previous validated generation is retained.'
    return result

def build_audit(job,outcome):
    from uuid import uuid5,NAMESPACE_URL
    from backend.services.institution_repository import audit
    event=('SEARCH_INDEX' if job['target']=='SEARCH_INDEX' else 'KG')+'_BUILD_'+outcome
    audit(job['library_id'],event,job['requested_by_user_id'],metadata={'job_id':job['job_id']},
        event_id=str(uuid5(NAMESPACE_URL,job['job_id']+':'+outcome)))
def build_guard(library_id,actor,locked=False):
    _,member=require_library_staff(canonical(library_id),actor,locked=locked)
    if member['role']!='ADMIN':raise HTTPException(403,'Library Admin membership is required to request a build.')
    return member
def request_build(library_id,actor,target,generation_id=None,*,require_nonempty=False):
    library_id=canonical(library_id);build_guard(library_id,actor)
    if target not in TARGETS:raise HTTPException(422,'Unknown intelligence build target.')
    with intelligence_barrier(library_id):
        build_guard(library_id,actor,True)
        old=collection('intelligence_jobs').find_one({'library_id':library_id,'target':target,'effective_active':True})
        if old:return safe_job(old)
        if require_nonempty:
            from backend.services.library_intelligence_service import target_status
            if target_status(library_id,target,observe_stale=False)['status']=='RECOVERY_REQUIRED':
                raise HTTPException(409,'Reconcile the previous build outcome before starting another build.')
            if not source_records(library_id):raise HTTPException(409,'Add eligible catalogue books before starting a build.')
        if generation_id:
            generation_id=canonical(generation_id)
            if not collection('intelligence_generations').find_one({'library_id':library_id,'generation_id':generation_id,'status':'READY'}):raise HTTPException(404,'Dataset generation not found.')
        stamp=now();job={'job_id':str(uuid4()),'library_id':library_id,'target':target,'requested_generation_id':generation_id,
            'artifact_generation_id':str(uuid4()),'state':'QUEUED','stage':'QUEUED','progress_current':0,'progress_total':0,'attempt':0,
            'requested_by_user_id':actor_id(actor),'created_at':stamp,'started_at':None,'heartbeat_at':None,'completed_at':None,
            'error_code':None,'error_message':None,'effective_active':True,'fence_token':None,'lease_expires_at':stamp,'require_nonempty':require_nonempty}
        collection('intelligence_jobs').insert_one(job)
        collection('intelligence_targets').update_one({'library_id':library_id,'target':target},{'$set':{'active_job_id':job['job_id'],'state':'QUEUED'},'$setOnInsert':{'active_generation_id':None}},upsert=True)
        build_audit(job,'REQUESTED')
        return safe_job(job)
def claim(worker_id):
    candidate=collection('intelligence_jobs').find_one({'state':'QUEUED','effective_active':True},sort=[('created_at',1)])
    if not candidate:return None
    with intelligence_barrier(candidate['library_id'],candidate):
        stamp=now();token=str(uuid4())
        row=collection('intelligence_jobs').find_one_and_update({'job_id':candidate['job_id'],'state':'QUEUED','effective_active':True},
            {'$set':{'state':'RUNNING','stage':'DATASET','worker_id':worker_id,'fence_token':token,'started_at':stamp,'heartbeat_at':stamp,'lease_expires_at':stamp+timedelta(seconds=LEASE_SECONDS)},'$inc':{'attempt':1}},return_document=ReturnDocument.AFTER)
        if row:collection('intelligence_targets').update_one({'library_id':row['library_id'],'target':row['target'],'active_job_id':row['job_id']},{'$set':{'state':'BUILDING','fence_token':token}})
        return row
def lease_query(job):return {'job_id':job['job_id'],'fence_token':job['fence_token'],'effective_active':True,'state':{'$in':['RUNNING','VALIDATING','PUBLISHING']},'lease_expires_at':{'$gt':now()}}
def check_lease(job):
    if not collection('intelligence_jobs').find_one(lease_query(job)):raise HTTPException(409,'WORKER_FENCED')
def heartbeat(job):
    return bool(collection('intelligence_jobs').update_one(lease_query(job),{'$set':{'heartbeat_at':now(),'lease_expires_at':now()+timedelta(seconds=LEASE_SECONDS)}}).matched_count)
def progress(job,stage,current=0,total=0,state='RUNNING'):
    check_lease(job)
    if not collection('intelligence_jobs').update_one(lease_query(job),{'$set':{'stage':stage,'state':state,'progress_current':int(current),'progress_total':int(total)}}).matched_count:raise HTTPException(409,'WORKER_FENCED')
    collection('intelligence_targets').update_one({'library_id':job['library_id'],'target':job['target'],'active_job_id':job['job_id'],'fence_token':job['fence_token']},{'$set':{'state':'VALIDATING' if state=='VALIDATING' else 'BUILDING'}})
def dataset(job,fail=lambda stage:None):
    library_id=job['library_id'];actor={'sub':str(job['requested_by_user_id'])}
    with intelligence_barrier(library_id,job):
        build_guard(library_id,actor,True);check_lease(job);records=source_records(library_id);fp=fingerprint(records)
        if job.get('require_nonempty') and not records:raise HTTPException(409,'EMPTY_CATALOGUE')
        requested=job.get('requested_generation_id')
        if requested:
            row=collection('intelligence_generations').find_one({'library_id':library_id,'generation_id':requested,'status':'READY'})
            if not row or row['source_fingerprint']!=fp:raise HTTPException(409,'DATASET_STALE')
        else:row=collection('intelligence_generations').find_one({'library_id':library_id,'source_fingerprint':fp,'status':'READY'})
        if row:
            path=directory(library_id,'datasets',row['generation_id'])
            if checksum(path/'manifest.json')!=row['manifest_checksum'] or checksum(path/'records.json')!=row['records_checksum']:raise HTTPException(409,'DATASET_CORRUPT')
            snapshot=json.loads((path/'records.json').read_text(encoding='utf8'))
            if snapshot!=records:raise HTTPException(409,'DATASET_CORRUPT')
            return row,records
        generation=str(uuid4());sequence=collection('intelligence_sequences').find_one_and_update({'library_id':library_id},{'$inc':{'sequence':1}},upsert=True,return_document=ReturnDocument.AFTER)['sequence']
        row={'generation_id':generation,'library_id':library_id,'sequence':sequence,'source_fingerprint':fp,'status':'PREPARING','book_count':len(records),'local_only_count':sum(not r['global_work_id'] for r in records),'globally_linked_count':sum(bool(r['global_work_id']) for r in records),'schema_version':SCHEMA,'created_by_user_id':job['requested_by_user_id'],'created_at':now(),'completed_at':None}
        # Count formats from canonical facts; no asset source/chunk/content is read.
        from backend.services.library_book_formats import format_pipeline
        formats=list(collection('library_books').aggregate([{'$match':{'library_id':library_id,'status':'ACTIVE'}},*format_pipeline(library_id,staff=True),{'$group':{'_id':'$book_format','count':{'$sum':1}}}]))
        counts={r['_id']:r['count'] for r in formats}
        row.update(physical_count=counts.get('PHYSICAL_ONLY',0),online_count=counts.get('DIGITAL_ONLY',0),physical_online_count=counts.get('PHYSICAL_AND_DIGITAL',0))
        collection('intelligence_generations').insert_one(row);path=directory(library_id,'datasets',generation)
        try:
            fail('DATASET_SNAPSHOT');path.mkdir(parents=True,exist_ok=False);durable_json(path/'records.json',records)
            manifest={k:v for k,v in row.items() if k not in ['_id','created_at','completed_at','status']};manifest['records_checksum']=checksum(path/'records.json')
            durable_json(path/'manifest.json',manifest);changes={'status':'READY','completed_at':now(),'manifest_checksum':checksum(path/'manifest.json'),'records_checksum':manifest['records_checksum']}
            check_lease(job);collection('intelligence_generations').update_one({'generation_id':generation,'status':'PREPARING'},{'$set':changes});row.update(changes)
            return row,records
        except Exception:
            collection('intelligence_generations').update_one({'generation_id':generation,'status':'PREPARING'},{'$set':{'status':'FAILED'}});raise
def scoped_job(library_id,job_id,actor):
    require_library_staff(canonical(library_id),actor)
    row=collection('intelligence_jobs').find_one({'library_id':canonical(library_id),'job_id':canonical(job_id)})
    if not row:raise HTTPException(404,'Build job not found.')
    return safe_job(row)
def scoped_generation(library_id,generation_id,actor):
    require_library_staff(canonical(library_id),actor)
    row=collection('intelligence_generations').find_one({'library_id':canonical(library_id),'generation_id':canonical(generation_id)},{'_id':0})
    if not row:raise HTTPException(404,'Dataset generation not found.')
    return row
