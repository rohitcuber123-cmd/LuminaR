"""Status/freshness, read-only reconciliation and explicit unknown-outcome repair."""
from datetime import timezone
import json
from fastapi import HTTPException
from backend.services import library_intelligence_store as store
from backend.services.library_inventory_access import require_library_staff

def expired(row):
    deadline=row.get('lease_expires_at')
    return not deadline or deadline.replace(tzinfo=timezone.utc)<=store.now()
def pointer_manifest(library_id,target,row):
    path=store.directory(library_id,'search' if target=='SEARCH_INDEX' else 'kg',row['active_generation_id'])
    file=path/'manifest.json'
    if file.resolve()!=file or store.checksum(file)!=row.get('manifest_checksum'):raise HTTPException(409,'ARTIFACT_CORRUPT')
    manifest=json.loads(file.read_text(encoding='utf8'))
    if manifest.get('library_id')!=library_id or manifest.get('generation_id')!=row['active_generation_id'] or manifest.get('target')!=target or manifest.get('source_fingerprint')!=row['source_fingerprint'] or manifest.get('source_generation_id')!=row['source_generation_id']:raise HTTPException(409,'ARTIFACT_CORRUPT')
    from backend.services.library_intelligence_artifacts import expected_files,MAX_ARTIFACT_BYTES
    if set(manifest['files'])!=expected_files(target,manifest):raise HTTPException(409,'ARTIFACT_CORRUPT')
    for name,digest in manifest['files'].items():
        artifact=path/name
        if artifact.resolve()!=artifact or artifact.stat().st_size>MAX_ARTIFACT_BYTES or store.checksum(artifact)!=digest:raise HTTPException(409,'ARTIFACT_CORRUPT')
    return manifest
def target_status(library_id,target,source_fingerprint=None,observe_stale=True):
    library_id=store.canonical(library_id)
    row=store.collection('intelligence_targets').find_one({'library_id':library_id,'target':target}) or {}
    job=store.collection('intelligence_jobs').find_one({'library_id':library_id,'target':target,'effective_active':True})
    state=row.get('state','NOT_BUILT');error=row.get('error_code')
    if job and job['state']!='QUEUED' and expired(job):state='RECOVERY_REQUIRED';error='LEASE_EXPIRED'
    if row.get('active_generation_id'):
        try:
            pointer_manifest(library_id,target,row)
            source_fingerprint=source_fingerprint or store.fingerprint(store.source_records(library_id))
            if state in {'READY','EMPTY'} and source_fingerprint!=row.get('source_fingerprint'):
                state='STALE'
                if observe_stale and not row.get('stale_since'):
                    observed=store.now()
                    store.collection('intelligence_targets').update_one({'library_id':library_id,'target':target,'active_generation_id':row['active_generation_id'],'stale_since':{'$exists':False}},{'$set':{'stale_since':observed}})
                    row=store.collection('intelligence_targets').find_one({'library_id':library_id,'target':target}) or row
        except (HTTPException,ValueError,KeyError,OSError):state='RECOVERY_REQUIRED';error='ARTIFACT_CORRUPT'
    elif state in {'READY','EMPTY'}:state='RECOVERY_REQUIRED';error='PUBLISH_POINTER_MISSING'
    return {'target':target,'status':state,'active_generation_id':row.get('active_generation_id'),'source_generation_id':row.get('source_generation_id'),
        'source_fingerprint':row.get('source_fingerprint'),'manifest_checksum':row.get('manifest_checksum'),'record_count':row.get('record_count',0),
        'built_at':row.get('built_at'),'stale_since':row.get('stale_since') if state=='STALE' else None,'current_job':store.safe_job(job) if job else None,
        'error_code':error,'node_count':row.get('node_count'),'edge_count':row.get('edge_count'),'artifact_bytes':row.get('artifact_bytes',0),
        'fallback_policy':'Current tenant-local catalogue when not READY; no global filler.'}
def status(library_id,actor):
    require_library_staff(store.canonical(library_id),actor)
    with store.library_mutation(library_id,wait_seconds=30):
        require_library_staff(library_id,actor,locked=True)
        records=store.source_records(library_id);fp=store.fingerprint(records)
        latest=store.collection('intelligence_generations').find_one({'library_id':library_id},sort=[('sequence',-1)])
        member=require_library_staff(library_id,actor,locked=True)[1]
        return {'library_id':library_id,'can_build':member['role']=='ADMIN','eligible_book_count':len(records),
            'dataset':{'status':latest['status'] if latest else 'NOT_BUILT','generation_id':latest['generation_id'] if latest else None,'sequence':latest.get('sequence') if latest else None,'current_source_fingerprint':fp,'book_count':latest.get('book_count',0) if latest else 0},
            'search':control_status(library_id,'SEARCH_INDEX',fp),'kg':control_status(library_id,'KNOWLEDGE_GRAPH',fp)}

def control_status(library_id,target,fp):
    """Presentation over Part 2G; catalogue reader/fallback decisions are unchanged."""
    current=target_status(library_id,target,fp)
    pointer=store.collection('intelligence_targets').find_one({'library_id':library_id,'target':target}) or {}
    latest=store.collection('intelligence_jobs').find_one({'library_id':library_id,'target':target},sort=[('created_at',-1)])
    published=store.collection('intelligence_jobs').find_one({'library_id':library_id,'job_id':pointer.get('published_by_job_id')}) if pointer.get('published_by_job_id') else None
    valid=False
    if pointer.get('active_generation_id'):
        try:pointer_manifest(library_id,target,pointer);valid=True
        except (HTTPException,ValueError,KeyError,OSError):pass
    active='NOT_BUILT' if not pointer.get('active_generation_id') else 'RECOVERY_REQUIRED' if not valid else 'READY' if fp==pointer.get('source_fingerprint') else 'STALE'
    sequence=store.collection('intelligence_jobs').count_documents({'library_id':library_id,'target':target,'state':'SUCCEEDED'}) if published else None
    duration=None
    if published and published.get('started_at') and published.get('completed_at'):
        duration=max(0,(published['completed_at']-published['started_at']).total_seconds())
    current.update(active_status=active,artifact_verified=valid,generation_sequence=sequence,last_build_duration_seconds=duration,
        latest_job=store.safe_job(latest) if latest else None,can_retry=current['status']!='RECOVERY_REQUIRED' and not current['current_job'],
        model=store.MODEL,dimension=store.DIMENSION,parameters={'M':16,'efConstruction':80,'efSearch':64})
    # Public diagnostics are stable bounded codes, never worker exception strings.
    if current.get('error_code'):current['error_code']='RECOVERY_REQUIRED' if current['status']=='RECOVERY_REQUIRED' else 'BUILD_FAILED'
    return current
def reconcile(library_id,actor):
    library_id=store.canonical(library_id);require_library_staff(library_id,actor)
    from backend.services.library_intelligence_artifacts import validate
    problems=[];targets={}
    for target,kind in [('SEARCH_INDEX','search'),('KNOWLEDGE_GRAPH','kg')]:
        pointer=store.collection('intelligence_targets').find_one({'library_id':library_id,'target':target}) or {}
        targets[target]=target_status(library_id,target,observe_stale=False)
        if pointer.get('active_generation_id'):
            try:
                pointer_manifest(library_id,target,pointer);validate(library_id,target,pointer['active_generation_id'])
            except Exception:problems.append({'target':target,'code':'ACTIVE_ARTIFACT_INVALID','generation_id':pointer['active_generation_id']})
        succeeded=list(store.collection('intelligence_jobs').find({'library_id':library_id,'target':target,'state':'SUCCEEDED'}).sort('completed_at',-1).limit(100))
        for job in succeeded:
            try:validate(library_id,target,job['artifact_generation_id'])
            except Exception:problems.append({'target':target,'code':'SUCCEEDED_ARTIFACT_INVALID','generation_id':job['artifact_generation_id']})
        if succeeded and not pointer.get('active_generation_id'):problems.append({'target':target,'code':'PUBLISH_POINTER_MISSING'})
        active=list(store.collection('intelligence_jobs').find({'library_id':library_id,'target':target,'effective_active':True}))
        if len(active)>1:problems.append({'target':target,'code':'MULTIPLE_EFFECTIVE_ACTIVE_JOBS'})
        for job in active:
            if job['state']=='RECOVERY_REQUIRED' or job['state']!='QUEUED' and expired(job):problems.append({'target':target,'code':'JOB_RECOVERY_REQUIRED','job_id':job['job_id']})
        base=store.root()/library_id/kind
        if base.exists():
            if base.resolve()!=base:problems.append({'target':target,'code':'ARTIFACT_NAMESPACE_INVALID'});continue
            for p in list(base.iterdir())[:5000]:
                if p.name.endswith('.building'):
                    problems.append({'target':target,'code':'TEMPORARY_GENERATION','generation_id':p.name[:-9]});continue
                try:gen=store.canonical(p.name)
                except HTTPException:problems.append({'target':target,'code':'INVALID_GENERATION_DIRECTORY'});continue
                job=store.collection('intelligence_jobs').find_one({'library_id':library_id,'target':target,'artifact_generation_id':gen})
                if not job or job['state'] not in {'SUCCEEDED','PUBLISHING','RECOVERY_REQUIRED'}:problems.append({'target':target,'code':'ORPHAN_FINAL_GENERATION','generation_id':gen})
        if targets[target]['status']=='STALE':problems.append({'target':target,'code':'SOURCE_FINGERPRINT_CHANGED'})
    return {'library_id':library_id,'dry_run':True,'problems':problems,'targets':targets,'destructive_actions':False}
def recover(library_id,actor,job_id):
    library_id=store.canonical(library_id);job_id=store.canonical(job_id)
    # A true crashed intelligence worker can leave its short metadata barrier.
    # Fence BOTH publication and job identity before releasing only that tagged
    # barrier. Never remove a lending/authority/unknown untagged tenant lock.
    lock=store.collection('locks').find_one({'_id':library_id,'intelligence_job_id':job_id})
    if lock:
        job=store.collection('intelligence_jobs').find_one({'library_id':library_id,'job_id':job_id,'effective_active':True})
        if not job or not expired(job):raise HTTPException(409,'The build worker lease is still active.')
        store.build_guard(library_id,actor,locked=True)
        token=str(__import__('uuid').uuid4())
        old=job.get('fence_token')
        if not store.collection('intelligence_targets').update_one({'library_id':library_id,'target':job['target'],'active_job_id':job_id,'fence_token':old},{'$set':{'fence_token':token,'state':'RECOVERY_REQUIRED'}}).matched_count:raise HTTPException(409,'Publication ownership must be reconciled.')
        if not store.collection('intelligence_jobs').update_one({'library_id':library_id,'job_id':job_id,'fence_token':old,'effective_active':True},{'$set':{'fence_token':token,'state':'RECOVERY_REQUIRED'}}).matched_count:raise HTTPException(409,'Build ownership must be reconciled.')
        store.collection('locks').delete_one({'_id':library_id,'holder':lock['holder'],'intelligence_job_id':job_id})
    store.build_guard(library_id,actor)
    with store.library_mutation(library_id,wait_seconds=30,durable=True):
        store.build_guard(library_id,actor,True)
        job=store.collection('intelligence_jobs').find_one({'library_id':library_id,'job_id':job_id})
        if not job:raise HTTPException(404,'Build job not found.')
        if not job.get('effective_active'):return store.safe_job(job)
        if job['state']!='RECOVERY_REQUIRED' and not expired(job):raise HTTPException(409,'The build worker is still active.')
        pointer=store.collection('intelligence_targets').find_one({'library_id':library_id,'target':job['target']}) or {}
        succeeded=pointer.get('published_by_job_id')==job_id and pointer.get('active_generation_id')==job['artifact_generation_id']
        if succeeded:
            from backend.services.library_intelligence_artifacts import validate
            pointer_manifest(library_id,job['target'],pointer);validate(library_id,job['target'],job['artifact_generation_id'])
        state='SUCCEEDED' if succeeded else 'FAILED'
        store.collection('intelligence_jobs').update_one({'library_id':library_id,'job_id':job_id,'effective_active':True},{'$set':{'state':state,'effective_active':False,'completed_at':store.now(),'stage':'RECOVERED','error_code':None if succeeded else 'RECOVERED_UNPUBLISHED','fence_token':str(__import__('uuid').uuid4())}})
        store.collection('intelligence_targets').update_one({'library_id':library_id,'target':job['target'],'active_job_id':job_id},{'$set':{'state':('EMPTY' if not pointer.get('record_count') else 'READY') if succeeded else 'FAILED'},'$unset':{'active_job_id':'','fence_token':''}})
        store.build_audit(job,'SUCCEEDED' if succeeded else 'FAILED')
        return store.safe_job(store.collection('intelligence_jobs').find_one({'job_id':job_id}))
def graph(library_id,actor,*,staff=False,query='',limit=100,cache=None):
    from backend.services import library_catalogue_experience as catalogue
    from backend.services.library_intelligence_artifacts import ArtifactCache
    library_id=store.canonical(library_id)
    with catalogue.read_context(library_id,actor,staff=staff) as (library,membership,canonical):
        current=target_status(library_id,'KNOWLEDGE_GRAPH')
        if current['status']!='READY':return {'library_id':library_id,'status':current['status'],'source':'TENANT_KG','nodes':[],'edges':[],'notice':'This library graph is not ready. Global Graph Lab remains available separately.'}
        try:manifest,records,payload=(cache or graph_cache).load(library_id,'KNOWLEDGE_GRAPH',current['active_generation_id'],current['manifest_checksum'])
        except Exception:return {'library_id':library_id,'status':'RECOVERY_REQUIRED','source':'TENANT_KG','nodes':[],'edges':[],'notice':'This library graph requires reconciliation.'}
        pipeline=[*catalogue.usable(library_id,staff=staff),{'$project':{'library_book_id':1}}]
        visible={r['library_book_id'] for r in store.collection('library_books').aggregate(pipeline)}
        books=[n for n in payload['nodes'] if n['type']=='Book' and n['library_book_id'] in visible and (not query or query.casefold() in n['label'].casefold())][:limit]
        selected={n['id'] for n in books};edges=[e for e in payload['edges'] if e['source'] in selected];ids=selected|{e['target'] for e in edges}
        return {'library_id':library_id,'status':'READY','source':'TENANT_KG','generation_id':current['active_generation_id'],'nodes':[n for n in payload['nodes'] if n['id'] in ids],'edges':edges,'total_book_count':len(visible),'limited':len(books)==limit}
from backend.services.library_intelligence_artifacts import ArtifactCache
graph_cache=ArtifactCache()
