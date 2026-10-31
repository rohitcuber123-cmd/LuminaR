"""Bounded read supplement promoted from2K. No native runtime imports or writes."""
from datetime import datetime,timezone
import hashlib
from pymongo import timeout
from pymongo.read_preferences import ReadPreference
from backend.services.library_operator_access import DiagnosticError
from .library_worker_telemetry import COLLECTION,SLOT,PREFIX,MAX_PROGRESS,MAX_BYTES,uuid,utc,digest,native_ref,tuple_of,ACTIVE


def classify(row,now,*,stale_seconds=30):
    result={'classification':'UNKNOWN','idle':'UNKNOWN','active_job_observed':False,
            'process_independently_verified':False,'stalled':'NOT_DETERMINED',
            'evidence':'Recent self-report proves only a successful write at its recorded time.',
            'restart_observed':False,'instance_ref':None,'pulse_age_seconds':None,
            'started_at':None,'last_seen_at':None,'stopped_at':None,'lifecycle_report':'UNKNOWN'}
    if not isinstance(row,dict) or row.get('schema')!=1:return result
    c=row.get('current')
    if not isinstance(c,dict) or not uuid(c.get('instance_id')):return result
    result['instance_ref']='instance-'+hashlib.sha256(c['instance_id'].encode()).hexdigest()[:16]
    result['restart_observed']=bool(isinstance(row.get('previous'),dict) and uuid(row['previous'].get('instance_id')) and row['previous']['instance_id']!=c['instance_id'])
    seen,started,stopped=map(utc,[c.get('last_seen_at'),c.get('started_at'),c.get('stopped_at')])
    now=utc(now)
    if not now or not seen or not started or c.get('clock_rollback') is not False or seen>now or started>seen:return result
    age=(now-seen).total_seconds();result['pulse_age_seconds']=round(age,3)
    result.update(started_at=started.isoformat(),last_seen_at=seen.isoformat(),stopped_at=stopped.isoformat() if stopped else None,
                  lifecycle_report=c.get('lifecycle') if c.get('lifecycle') in ['IDLE','ACTIVE','STOPPING','STOPPED'] else 'UNKNOWN')
    if c.get('lifecycle')=='STOPPED':
        if stopped and started<=stopped<=seen:result['classification']='STOPPED_REPORTED'
    elif c.get('lifecycle') in ['IDLE','ACTIVE','STOPPING']:
        result['classification']='RECENTLY_OBSERVED' if age<=stale_seconds else 'STALE'
        if age<=stale_seconds:
            result['idle']=c['lifecycle']=='IDLE'
            result['active_job_observed']=c['lifecycle']=='ACTIVE'
    return result


def inspect_telemetry(reader,library_id,*,stale_seconds=30,fixture_only=False):
    if not reader.authenticated or fixture_only and not reader.database.name.startswith(PREFIX):raise DiagnosticError('PROTOTYPE_FIXTURE_ONLY')
    if reader.database.read_preference!=ReadPreference.PRIMARY:raise DiagnosticError('PRIMARY_READ_REQUIRED')
    if not uuid(library_id):raise DiagnosticError('INVALID_LIBRARY_ID')
    # No caller-selected collection, unbounded query, or database-wide progress output.
    with timeout(reader.remaining()):
        rows=list(reader.database[COLLECTION].aggregate([
            {'$match':{'_id':SLOT}},{'$limit':1},{'$project':{'_id':0,'record':'$$ROOT','observed_now':'$$NOW'}}
        ],maxTimeMS=500,allowDiskUse=False))
    if not rows:return {'prototype_only':fixture_only,'worker':classify(None,None),'previous_worker':classify(None,None),
                        'progress':[],'associated_job':None,'read_only':True,'consistency':'BEST_EFFORT_REVALIDATED','process_verification':'NOT_AVAILABLE'}
    row,now=rows[0]['record'],rows[0]['observed_now']
    from bson import BSON
    if len(BSON.encode(row))>MAX_BYTES:raise DiagnosticError('MALFORMED_TELEMETRY')
    worker=classify(row,now,stale_seconds=stale_seconds)
    previous_worker=classify({'schema':row.get('schema'),'current':row.get('previous')},now,stale_seconds=stale_seconds)
    previous_worker.update(historical=True,current_instance=False)
    current=row.get('current') or {};entries=current.get('progress',[])
    if not isinstance(entries,list) or len(entries)>MAX_PROGRESS:raise DiagnosticError('MALFORMED_TELEMETRY')
    progress=[]
    for e in entries:
        if not isinstance(e,dict) or e.get('library_id')!=library_id or not uuid(e.get('job_id')):continue
        output={'job_id':e['job_id'],'target':e.get('target') if e.get('target') in ['SEARCH_INDEX','KNOWLEDGE_GRAPH'] else 'UNKNOWN',
                'recency':'UNKNOWN','last_progress_observed_at':None,'progress_age_seconds':None,
                'publication':'UNKNOWN','stalled':'NOT_DETERMINED','native_job_state':'UNKNOWN','stage':'UNKNOWN',
                'progress':{'current':None,'total':None},'outcome':'UNKNOWN','heartbeat_age_seconds':None,'heartbeat_evidence':'UNKNOWN'}
        jobs=reader.rows('jobs',{'library_id':library_id,'job_id':e['job_id']},{'_id':0},limit=1)
        j=jobs[0] if jobs else {}
        valid=(j.get('target')==e.get('target') and native_ref(j.get('worker_id'))==e.get('native_worker_ref')==current.get('native_worker_ref')
               and digest(j.get('fence_token'))==e.get('fence_ref') and digest(tuple_of(j))==e.get('fingerprint'))
        at=utc(e.get('last_progress_observed_at'));observed=utc(e.get('observed_at'));server=utc(now)
        if j.get('state') in ACTIVE:
            lease=utc(j.get('lease_expires_at'))
            valid=valid and j.get('effective_active') and lease and lease>server
        if valid:
            output.update(native_job_state=j.get('state'),stage=j.get('stage'),
                          progress={'current':j.get('progress_current'),'total':j.get('progress_total')},
                          outcome=j['state'] if j.get('state') in ['SUCCEEDED','FAILED','RECOVERY_REQUIRED'] else 'NOT_TERMINAL')
            heartbeat=utc(j.get('heartbeat_at'))
            if heartbeat and heartbeat<=server:
                age=(server-heartbeat).total_seconds()
                output.update(heartbeat_age_seconds=round(age,3),heartbeat_evidence='RECENT' if age<=30 else 'STALE')
        if valid and at and observed and at<=observed<=server and not current.get('clock_rollback'):
            age=(server-at).total_seconds()
            output.update(recency='RECENT_PROGRESS_OBSERVED' if age<=stale_seconds else 'NO_RECENT_PROGRESS_OBSERVED',
                          last_progress_observed_at=at.isoformat(),progress_age_seconds=round(age,3))
            if j.get('state')=='RECOVERY_REQUIRED':output['recency']='RECOVERY_REQUIRED'
            if j.get('state')=='SUCCEEDED':
                pointers=reader.rows('targets',{'library_id':library_id,'target':j['target']},{'_id':0},limit=1)
                p=pointers[0] if pointers else {}
                if (p.get('published_by_job_id')==j['job_id'] and uuid(j.get('artifact_generation_id'))
                        and p.get('active_generation_id')==j['artifact_generation_id'] and uuid(j.get('requested_generation_id'))
                        and p.get('source_generation_id')==j['requested_generation_id']):output['publication']='ACKNOWLEDGED_POINTER_MATCH'
                else:output.update(recency='UNKNOWN',last_progress_observed_at=None,progress_age_seconds=None)
        progress.append(output)
    associated=None
    hint=current.get('current_job')
    if isinstance(hint,dict) and hint.get('library_id')==library_id and uuid(hint.get('job_id')) and hint.get('target') in ['SEARCH_INDEX','KNOWLEDGE_GRAPH']:
        jobs=reader.rows('jobs',{'library_id':library_id,'job_id':hint['job_id'],'target':hint['target']},{'_id':0,'worker_id':1,'state':1,'stage':1},limit=1)
        if jobs and native_ref(jobs[0].get('worker_id'))==current.get('native_worker_ref'):
            associated={'job_id':hint['job_id'],'target':hint['target'],'basis':'SCOPED_LATEST_SELF_REPORT_REVALIDATED_NATIVE_OWNER'}
    # Recheck identity/sequence after job/pointer reads. Concurrent observer changes invalidate the joined view.
    with timeout(reader.remaining()):
        same=reader.database[COLLECTION].find_one({'_id':SLOT,'epoch':row.get('epoch'),
             'current.instance_id':current.get('instance_id'),'current.boot_hash':current.get('boot_hash'),
             'current.progress_seq':current.get('progress_seq'),'current.pulse_seq':current.get('pulse_seq')}, {'_id':1},max_time_ms=500)
    if not same:
        for p in progress:p.update(recency='UNKNOWN',last_progress_observed_at=None,progress_age_seconds=None,publication='UNKNOWN',
                                   native_job_state='UNKNOWN',stage='UNKNOWN',progress={'current':None,'total':None},outcome='UNKNOWN',heartbeat_age_seconds=None,heartbeat_evidence='UNKNOWN')
        worker=classify(None,None);previous_worker=classify(None,None);associated=None
    return {'prototype_only':fixture_only,'read_only':True,'worker':worker,'previous_worker':previous_worker,'progress':progress,
            'associated_job':associated,'process_verification':'NOT_AVAILABLE',
            'consistency':'BEST_EFFORT_REVALIDATED','timestamp_semantics':'Post-read observation of accepted native state; not its exact commit time.'}
