"""Bounded read-only observations, never readiness/authorization/action authority.

No imports of the application store/validators/worker: they transitively import
the write-on-import Mongo module. Manifest rules mirror the existing protocol;
native FAISS/graph and catalogue freshness validation are explicitly not done.
"""
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
from uuid import UUID

from bson import ObjectId
from backend.services.library_operator_access import DiagnosticError

ROOT = Path(__file__).resolve().parents[2]
TARGETS = {'SEARCH_INDEX': 'search', 'KNOWLEDGE_GRAPH': 'kg'}
STATES = {'QUEUED','RUNNING','VALIDATING','PUBLISHING','SUCCEEDED','FAILED','RECOVERY_REQUIRED'}
EXECUTING = ['RUNNING','VALIDATING','PUBLISHING']
STAGES = {'QUEUED','DATASET','EMBEDDING','KG_METADATA','VALIDATION','PUBLISH','COMPLETE','RECOVERED','FAILED','RECOVERY_REQUIRED'}
FAILURES = {'BUILD_FAILED','WORKER_CRASH','WORKER_FENCED','HEARTBEAT_LOSS','SOURCE_CHANGED','DATASET_STALE',
            'DATASET_CORRUPT','ARTIFACT_CORRUPT','EMBEDDING_INVALID','EMBEDDING_CACHE_CORRUPT','DATASET_LIMIT',
            'EMPTY_CATALOGUE','RECOVERED_UNPUBLISHED','LEASE_EXPIRED'}
JOB_FIELDS = ['job_id','library_id','target','state','stage','progress_current','progress_total','attempt',
              'created_at','started_at','heartbeat_at','completed_at','lease_expires_at','effective_active',
              'artifact_generation_id','requested_generation_id','error_code','worker_id']
JOB_PROJECT = {k:1 for k in JOB_FIELDS}
TARGET_PROJECT = {k:1 for k in ['library_id','target','state','active_generation_id','previous_generation_id','source_generation_id',
                               'source_fingerprint','manifest_checksum','published_by_job_id','record_count','built_at']}
HEX = re.compile(r'[0-9a-f]{64}')


def canonical(value):
    try:
        result = str(UUID(str(value)))
        if result != value:
            raise ValueError()
        return result
    except (TypeError,ValueError,AttributeError):
        raise DiagnosticError('INVALID_UUID') from None


def identifier(value):
    try:
        return canonical(value)
    except DiagnosticError:
        return None


def date(value):
    return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc) if isinstance(value, datetime) else None


def iso(value):
    value = date(value)
    return value.isoformat() if value else None


def age(value, now):
    value = date(value)
    return max(0, (now-value).total_seconds()) if value else None


def integer(value):
    return value if type(value) is int and 0 <= value <= 1000000 else None


def job_view(row, now):
    state = row.get('state') if row.get('state') in STATES else 'UNKNOWN'
    heartbeat, lease = date(row.get('heartbeat_at')), date(row.get('lease_expires_at'))
    recent = 'NOT_AVAILABLE' if not heartbeat else 'CLOCK_SKEW' if heartbeat > now else 'RECENT' if age(heartbeat,now) <= 30 else 'STALE'
    expired = bool(state in EXECUTING and row.get('effective_active') and (not lease or lease <= now))
    end = date(row.get('completed_at')) if state in ['SUCCEEDED','FAILED'] else now
    start = date(row.get('started_at'))
    owner=row.get('worker_id')
    worker_reference='worker-'+hashlib.sha256(owner.encode()).hexdigest()[:16] if isinstance(owner,str) and owner.startswith('tenant-') and identifier(owner[7:]) else None
    return {'job_id':identifier(row.get('job_id')), 'library_id':identifier(row.get('library_id')),
            'target':row.get('target') if row.get('target') in TARGETS else 'UNKNOWN', 'state':state,
            'stage':row.get('stage') if row.get('stage') in STAGES else 'OTHER',
            'worker_reference':worker_reference,
            'progress':{'current':integer(row.get('progress_current')),'total':integer(row.get('progress_total')),
                        'last_progress_at':'NOT_AVAILABLE','recency':'UNKNOWN'},
            'created_at':iso(row.get('created_at')),'queued_at':iso(row.get('created_at')),
            'queued_at_basis':'created_at; no separate queued timestamp', 'started_at':iso(start),
            'heartbeat_at':iso(heartbeat),'heartbeat_age_seconds':age(heartbeat,now),'heartbeat_evidence':recent,
            'lease_expires_at':iso(lease),'lease_valid':bool(lease and lease>now and row.get('effective_active')),
            'last_updated_at':'NOT_AVAILABLE','completed_at':iso(row.get('completed_at')),
            'duration_seconds':max(0,(end-start).total_seconds()) if start and end else None,
            'duration_basis':'completed interval' if state in ['SUCCEEDED','FAILED'] else 'elapsed observation',
            'failure_category':row.get('error_code') if row.get('error_code') in FAILURES else 'BUILD_FAILED' if row.get('error_code') else None,
            'recovery_required':state=='RECOVERY_REQUIRED' or expired,'lease_expired':expired,
            'publication_outcome':'UNKNOWN' if state=='RECOVERY_REQUIRED' or expired else 'ACKNOWLEDGED_SUCCEEDED' if state=='SUCCEEDED' else 'KNOWN_FAILED' if state=='FAILED' else 'NOT_TERMINAL',
            'manual_intervention_required':state=='RECOVERY_REQUIRED' or expired,
            'artifact_generation_id':identifier(row.get('artifact_generation_id')),
            'source_generation_id':identifier(row.get('requested_generation_id'))}


def worker_view(jobs, now):
    observed=[job_view(j,now) for j in jobs]
    active=[j for j in observed if j['state'] in EXECUTING]
    stale=any(j['heartbeat_evidence']=='STALE' or j['lease_expired'] for j in active)
    recovery=any(j['recovery_required'] for j in observed)
    classification='STALE_HEARTBEAT' if stale else 'DEGRADED' if recovery or len(active)>1 else 'UNKNOWN'
    return {'classification':classification,'process_alive':'UNKNOWN','startup':'NOT_AVAILABLE','shutdown':'NOT_AVAILABLE',
            'restart':'NOT_AVAILABLE','current_executing_observations':active,
            'observed_worker_references':sorted({j['worker_reference'] for j in observed if j['worker_reference']}),
            'reason':'Job renewal is stale or its lease expired; this does not prove the process is dead.' if stale else
                     'Unresolved recovery or competing execution observations; investigate manually.' if classification=='DEGRADED' else
                     'No independent worker process/idle heartbeat exists. Even a recent job heartbeat is not proof of current process liveness.',
            'heartbeat_recent_window_seconds':30,'heartbeat_window_basis':'three existing ten-second renewal intervals; diagnostic only',
            'progress_recency':'UNKNOWN','health_is_durable_job_state':False}


def cursor_encode(library_id, states, last):
    return base64.urlsafe_b64encode(json.dumps([library_id,states,str(last)],separators=(',',':')).encode()).decode().rstrip('=')


def cursor_decode(value, library_id, states):
    try:
        if not isinstance(value,str) or len(value)>300:
            raise ValueError()
        lib, scope, last=json.loads(base64.b64decode(value+'='*(-len(value)%4),altchars=b'-_',validate=True))
        if lib!=library_id or scope!=states or not ObjectId.is_valid(last):
            raise ValueError()
        return ObjectId(last)
    except Exception:
        raise DiagnosticError('INVALID_CURSOR') from None


class ArtifactInspector:
    def __init__(self, root, reader, *, verify=False, byte_budget=16*1024*1024):
        self.root=Path(root).absolute()
        if (str(self.root).startswith(('\\\\','//')) or self.root.resolve()!=self.root or self.root==ROOT
                or any(self.root==p or p in self.root.parents for p in [ROOT/'knowledge_graph',ROOT/'datasets',ROOT/'search',ROOT/'rag',ROOT/'local-data/search-index'])):
            raise DiagnosticError('INVALID_ARTIFACT_ROOT')
        self.reader,self.verify,self.byte_budget=reader,verify,byte_budget
        self.hashed_bytes=0
        self.manifest_bytes_read=0
        self.file_reads=0

    def safe(self,path):
        self.reader.remaining()
        if path.resolve()!=path or self.root not in path.parents:
            raise DiagnosticError('UNSAFE_ARTIFACT_NAMESPACE')
        return path

    def content(self,path,limit,*,hashing=False):
        self.safe(path)
        if path.is_symlink():
            raise DiagnosticError('UNSAFE_ARTIFACT_NAMESPACE')
        with path.open('rb') as stream:
            before=os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size>limit:
                raise DiagnosticError('ARTIFACT_LIMIT')
            if hashing and before.st_size>self.byte_budget-self.hashed_bytes:
                raise DiagnosticError('CHECKSUM_BUDGET_EXCEEDED')
            self.file_reads+=1
            digest=hashlib.sha256() if hashing else None
            data=bytearray()
            read=0
            while read<before.st_size:
                self.reader.remaining()
                block=stream.read(min(1024*1024,before.st_size-read))
                if not block:raise DiagnosticError('ARTIFACT_CHANGED_DURING_READ')
                read+=len(block)
                if hashing:
                    digest.update(block);self.hashed_bytes+=len(block)
                else:
                    data.extend(block);self.manifest_bytes_read+=len(block)
            after=os.fstat(stream.fileno())
            if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
                raise DiagnosticError('ARTIFACT_CHANGED_DURING_READ')
            if hashing:
                return digest.hexdigest()
            return bytes(data)

    def generation(self, library_id, target, generation, *, pointer=None, temporary=False):
        path=self.root/library_id/TARGETS[target]/(generation+('.building' if temporary else ''))
        result={'library_id':library_id,'target':target,'generation_id':generation,'temporary':temporary,
                'manifest':'NOT_VERIFIED','checksums':'NOT_REQUESTED','ownership':'NOT_VERIFIED',
                'directory_present':False,'known_file_bytes':0,'native_structure':'NOT_CHECKED','record_ownership':'NOT_CHECKED','catalogue_freshness':'NOT_CHECKED'}
        try:
            self.safe(path)
            if not path.is_dir():
                result['manifest']='MISSING_GENERATION'
                return result
            result['directory_present']=True
            names={'manifest.json','metadata.json','index.faiss','vectors.npy'} if target=='SEARCH_INDEX' else {'manifest.json','metadata.json','graph.json'}
            for name in names:
                p=path/name
                self.safe(p)
                if p.is_file():result['known_file_bytes']+=p.stat().st_size
            raw=self.content(path/'manifest.json',65536)
            def unique(pairs):
                d={}
                for key,value in pairs:
                    if key in d:raise ValueError()
                    d[key]=value
                return d
            manifest=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if not isinstance(manifest,dict):raise ValueError()
            if (manifest.get('library_id')!=library_id or manifest.get('generation_id')!=generation or manifest.get('target')!=target):
                result['manifest']='OWNERSHIP_MISMATCH'
                return result
            result['ownership']='MANIFEST_SCOPE_MATCH'
            files=manifest.get('files')
            expected={'metadata.json'}|({'index.faiss','vectors.npy'} if target=='SEARCH_INDEX' and not manifest.get('empty') else {'graph.json'} if target=='KNOWLEDGE_GRAPH' else set())
            if (manifest.get('schema_version')!='tenant-catalogue-v1' or not isinstance(files,dict) or set(files)!=expected
                    or any(not isinstance(v,str) or not HEX.fullmatch(v) for v in files.values())
                    or not identifier(manifest.get('source_generation_id')) or not isinstance(manifest.get('source_fingerprint'),str)
                    or not HEX.fullmatch(manifest['source_fingerprint']) or type(manifest.get('book_count')) is not int
                    or not 0<=manifest['book_count']<=50000):
                raise ValueError()
            if target=='SEARCH_INDEX' and type(manifest.get('empty')) is not bool:raise ValueError()
            if pointer and (not identifier(pointer.get('published_by_job_id')) or manifest['source_generation_id']!=pointer.get('source_generation_id')
                    or manifest['source_fingerprint']!=pointer.get('source_fingerprint') or manifest.get('job_id')!=pointer.get('published_by_job_id')
                    or manifest['book_count']!=pointer.get('record_count')):
                result['manifest']='POINTER_INCONSISTENT'
                return result
            if pointer and hashlib.sha256(raw).hexdigest()!=pointer.get('manifest_checksum'):
                result['manifest']='POINTER_CHECKSUM_MISMATCH'
                return result
            result['manifest']='POINTER_ANCHORED_MANIFEST' if pointer else 'IDENTITY_VALID_MANIFEST'
            result['source_generation_id']=manifest['source_generation_id']
            result['source_fingerprint']=manifest['source_fingerprint']
            result['manifest_job_id']=identifier(manifest.get('job_id'))
            result['book_count']=manifest['book_count']
            missing=[name for name in expected if not self.safe(path/name).is_file()]
            if missing:
                result['checksums']='MISSING_EXPECTED_FILE'
            elif self.verify:
                result['checksums']='MATCH'
                for name,digest in sorted(files.items()):
                    if self.content(path/name,256*1024*1024,hashing=True)!=digest:
                        result['checksums']='MISMATCH'
                        break
        except FileNotFoundError:
            result['manifest']='MISSING_MANIFEST'
        except DiagnosticError as error:
            result['checksums' if error.code=='CHECKSUM_BUDGET_EXCEEDED' else 'manifest']=error.code
        except (OSError,ValueError,KeyError,TypeError,RecursionError):
            result['manifest']='INVALID_OR_UNREADABLE_MANIFEST'
        return result

    def inventory(self, library_id, pointers, limit, job_references=()):
        candidates={}
        coverage={}
        for target,kind in TARGETS.items():
            row=pointers.get(target,{})
            for field in ['active_generation_id','previous_generation_id']:
                value=identifier(row.get(field))
                if value:candidates[(target,value,False)]=field
            for job in job_references:
                if job.get('target')!=target:continue
                value=identifier(job.get('artifact_generation_id'))
                if not value:continue
                for temporary in [False,True]:
                    if sum(k[0]==target for k in candidates)>=limit+2:break
                    candidates.setdefault((target,value,temporary),'job_temporary_candidate' if temporary else 'job_artifact_reference')
            base=self.root/library_id/kind
            count=0
            try:
                self.safe(base)
                with os.scandir(base) as entries:
                    for entry in entries:
                        self.reader.remaining()
                        count+=1
                        if count>limit:break
                        temporary=entry.name.endswith('.building')
                        value=identifier(entry.name[:-9] if temporary else entry.name)
                        if value and entry.is_dir(follow_symlinks=False) and sum(k[0]==target for k in candidates)<limit+2:
                            candidates.setdefault((target,value,temporary),'enumerated')
                coverage[target]={'entries_examined':min(count,limit),'truncated':count>limit or sum(k[0]==target for k in candidates)>=limit+2,'order':'prioritize pointers and bounded job references, then filesystem enumeration; not exhaustive history'}
            except FileNotFoundError:
                coverage[target]={'entries_examined':0,'truncated':False,'directory':'NOT_PRESENT'}
            except (OSError,DiagnosticError):
                coverage[target]={'entries_examined':min(count,limit),'truncated':True,'directory':'UNAVAILABLE_OR_UNSAFE'}
            coverage[target]['candidate_limit']=limit+2
            coverage[target]['truncated']=coverage[target]['truncated'] or sum(k[0]==target for k in candidates)>=limit+2
        values=[self.generation(library_id,t,g,pointer=pointers.get(t) if role=='active_generation_id' else None,temporary=temp)
                | {'reference':role} for (t,g,temp),role in candidates.items()]
        # The accepted schema has no artifact_generation_id history index.
        # Resolve bounded page/pointer/manifest job IDs through the unique job
        # index instead of scanning every historical job for each directory.
        job_ids={identifier(j.get('job_id')) for j in job_references}
        job_ids.update(identifier(p.get('published_by_job_id')) for p in pointers.values())
        job_ids.update(v.get('manifest_job_id') for v in values)
        job_ids.discard(None)
        jobs=self.reader.rows('jobs',{'library_id':library_id,'job_id':{'$in':list(job_ids)}},JOB_PROJECT,limit=min(201,len(job_ids)+1)) if job_ids else []
        by_generation={}
        for job in jobs:by_generation.setdefault(job.get('artifact_generation_id'),[]).append(job)
        for value in values:
            matching=[j for j in by_generation.get(value['generation_id'],[]) if j.get('target')==value['target']]
            value['associated_jobs']=[{'job_id':identifier(j.get('job_id')),'state':j.get('state') if j.get('state') in STATES else 'UNKNOWN'} for j in matching[:2]]
            value['job_reference']='MATCH' if any(j.get('job_id')==value.get('manifest_job_id') and j.get('requested_generation_id')==value.get('source_generation_id') for j in matching) else 'NOT_VERIFIED'
            value['reconciliation']='NOT_CREATED_OR_MISSING' if not value['directory_present'] else 'PUBLISHED_REFERENCE' if value['reference']=='active_generation_id' else 'PREVIOUS_RETAINED_REFERENCE' if value['reference']=='previous_generation_id' else 'FAILED_RETAINED' if any(j.get('state')=='FAILED' for j in matching) else 'RECOVERY_REQUIRED' if any(j.get('state')=='RECOVERY_REQUIRED' for j in matching) else 'INCOMPLETE_TEMPORARY' if value['temporary'] else 'UNREFERENCED_OR_HISTORICAL'
        return {'generations':values,'coverage':coverage,'observed_generation_count':len({v['generation_id'] for v in values if v['directory_present']}),
                'observed_reference_count':len(values),'present_directory_count':sum(v['directory_present'] for v in values),
                'missing_reference_count':sum(not v['directory_present'] for v in values),
                'observed_known_file_bytes':sum(v['known_file_bytes'] for v in values),
                'estimated_total_disk_consumption':'NOT_AVAILABLE; bounded known files only',
                'checksum_bytes_read':self.hashed_bytes,'manifest_bytes_read':self.manifest_bytes_read,'file_reads':self.file_reads,'read_only':True}


def inspect(reader, library_id, *, states=None, limit=20, cursor=None, job_id=None, artifact_root=None,
            artifact_limit=20, verify_checksums=False, checksum_budget=16*1024*1024, now=None):
    if not getattr(reader,'authenticated',False):raise DiagnosticError('OPERATOR_AUTH_REQUIRED')
    library_id=canonical(library_id)
    states=sorted(states or STATES)
    if (not states or any(s not in STATES for s in states) or type(limit) is not int or not 1<=limit<=50
            or type(artifact_limit) is not int or not 1<=artifact_limit<=50
            or type(checksum_budget) is not int or not 0<=checksum_budget<=256*1024*1024):
        raise DiagnosticError('INVALID_LIMIT_OR_FILTER')
    job_id=canonical(job_id) if job_id else None
    fixed_now=date(now)
    now=fixed_now or datetime.now(timezone.utc)
    started_at=now
    query={'library_id':library_id,'state':{'$in':states}}
    if job_id and cursor:raise DiagnosticError('INVALID_CURSOR')
    if cursor:query['_id']={'$lt':cursor_decode(cursor,library_id,states)}
    if job_id:query['job_id']=job_id
    history=reader.rows('jobs',query,JOB_PROJECT,sort=None if job_id else [('_id',-1)],limit=limit+1,hint='job_id_1' if job_id else '_id_')
    page=history[:limit]
    pointers=reader.rows('targets',{'library_id':library_id,'target':{'$in':list(TARGETS)}},TARGET_PROJECT,limit=3)
    by_target={r['target']:r for r in pointers}
    active=reader.rows('jobs',{'effective_active':True,'state':{'$in':EXECUTING+['RECOVERY_REQUIRED']}},JOB_PROJECT,sort=[('created_at',1)],limit=6)
    tenant_active=reader.rows('jobs',{'library_id':library_id,'effective_active':True},JOB_PROJECT,limit=3)
    counts=reader.aggregate('jobs',[{'$match':{'effective_active':True,'state':{'$in':['QUEUED',*EXECUTING,'RECOVERY_REQUIRED']}}},
                                  {'$group':{'_id':'$state','count':{'$sum':1}}}])
    totals={r['_id']:r['count'] for r in counts}
    heads=reader.rows('jobs',{'effective_active':True,'state':'QUEUED'},JOB_PROJECT,sort=[('created_at',1)],limit=4)
    lock_ids=list({library_id,*[r.get('library_id') for r in heads if identifier(r.get('library_id'))]})
    locks=reader.rows('locks',{'_id':{'$in':lock_ids}},{'_id':1,'created_at':1,'intelligence_job_id':1},limit=5)
    locked={r['_id']:r for r in locks}
    selected=None
    position=None
    if job_id:
        rows=reader.rows('jobs',{'library_id':library_id,'job_id':job_id},JOB_PROJECT,limit=1)
        if not rows:raise DiagnosticError('SCOPED_JOB_NOT_FOUND')
        selected=rows[0]
        if selected.get('state')=='QUEUED' and selected.get('effective_active') and date(selected.get('created_at')):
            stamp=selected['created_at']
            rank=reader.aggregate('jobs',[{'$match':{'effective_active':True,'state':'QUEUED','created_at':{'$lte':stamp}}},
                {'$group':{'_id':None,'ahead':{'$sum':{'$cond':[{'$lt':['$created_at',stamp]},1,0]}},
                           'tied':{'$sum':{'$cond':[{'$eq':['$created_at',stamp]},1,0]}}}}])
            if rank:position={'minimum':rank[0]['ahead']+1,'maximum':rank[0]['ahead']+rank[0]['tied'],
                              'basis':'created_at FIFO; worker has no tie-breaker; approximate point-in-time range'}
    inspector=ArtifactInspector(artifact_root or os.getenv('LIBRARY_INTELLIGENCE_ROOT') or ROOT/'local-data/library-intelligence',reader,
                                verify=verify_checksums,byte_budget=checksum_budget)
    observed_jobs=([selected] if selected else [])+tenant_active+page
    artifacts=inspector.inventory(library_id,by_target,artifact_limit,observed_jobs)
    generation_ids=list({a.get('source_generation_id') for a in artifacts['generations'] if a.get('source_generation_id')})
    sources=reader.rows('generations',{'library_id':library_id,'generation_id':{'$in':generation_ids}},
                        {'generation_id':1,'source_fingerprint':1,'status':1,'_id':0},limit=105) if generation_ids else []
    sources={r['generation_id']:r for r in sources}
    for artifact in artifacts['generations']:
        source=sources.get(artifact.get('source_generation_id'),{})
        artifact['dataset_reference']='MATCH' if source.get('status')=='READY' and source.get('source_fingerprint')==artifact.get('source_fingerprint') else 'NOT_VERIFIED'
    reread=reader.rows('targets',{'library_id':library_id,'target':{'$in':list(TARGETS)}},TARGET_PROJECT,limit=3)
    changed=sorted(pointers,key=lambda r:r['target'])!=sorted(reread,key=lambda r:r['target'])
    now=fixed_now or datetime.now(timezone.utc)
    targets=[]
    for target in TARGETS:
        pointer=by_target.get(target,{})
        artifact=next((a for a in artifacts['generations'] if a['target']==target and a['reference']=='active_generation_id'),None)
        integrity=bool(artifact and artifact['manifest']=='POINTER_ANCHORED_MANIFEST' and artifact['checksums']=='MATCH' and artifact['dataset_reference']=='MATCH' and artifact['job_reference']=='MATCH' and not changed)
        attempts=list({j.get('job_id'):j for j in observed_jobs if j.get('target')==target and j.get('library_id')==library_id}.values())
        latest=max(attempts,key=lambda j:date(j.get('created_at')) or datetime.min.replace(tzinfo=timezone.utc)) if attempts else None
        tied=bool(latest and sum(date(j.get('created_at'))==date(latest.get('created_at')) for j in attempts)>1)
        needs_recovery=any(job_view(j,now)['recovery_required'] for j in tenant_active if j.get('target')==target)
        targets.append({'target':target,'stored_state':pointer.get('state') if pointer.get('state') in STATES|{'NOT_BUILT','READY','EMPTY','STALE','BUILDING'} else 'UNKNOWN',
                        'published_generation_id':identifier(pointer.get('active_generation_id')),'previous_generation_id':identifier(pointer.get('previous_generation_id')),
                        'published_by_job_id':identifier(pointer.get('published_by_job_id')),'record_count':integer(pointer.get('record_count')),
                        'manifest_observation':artifact['manifest'] if artifact else 'NO_PUBLISHED_REFERENCE',
                        'published_checksum_integrity':'VERIFIED_WITHIN_BUDGET' if integrity else 'NOT_VERIFIED',
                        'runtime_usable':'NOT_DETERMINED; catalogue freshness and native structure not checked',
                        'last_good_reference_present':bool(identifier(pointer.get('active_generation_id'))),
                        'previous_retained_reference_present':bool(identifier(pointer.get('previous_generation_id'))),
                        'latest_observed_attempt':job_view(latest,now) if latest else None,
                        'latest_observed_timestamp_tie':tied,
                        'latest_attempt_coverage':'bounded page, selected job and current tenant active jobs; not complete history',
                        'manual_investigation_required':bool(changed or needs_recovery or pointer.get('state')=='RECOVERY_REQUIRED' or artifact and (artifact['manifest'] not in ['POINTER_ANCHORED_MANIFEST'] or artifact['checksums'] in ['MISMATCH','MISSING_EXPECTED_FILE'] or artifact['dataset_reference']!='MATCH' or artifact['job_reference']!='MATCH'))})
    disk={'status':'NOT_AVAILABLE'}
    try:
        inspector.reader.remaining()
        if inspector.root.is_dir():
            usage=shutil.disk_usage(inspector.root)
            disk={'status':'OBSERVED_LOCAL_VOLUME','total_bytes':usage.total,'free_bytes':usage.free,'worker_admission_check':False}
    except OSError:pass
    return {'schema':'tenant-intelligence-diagnostics-v1','observation_started_at':started_at.isoformat(),'observed_at':now.isoformat(),'library_id':library_id,'read_only':True,
            'authorization':'LOCAL_MONGODB_AUTHENTICATED_READ_PRINCIPAL; not application/platform authority',
            'consistency':'CONCURRENT_POINTER_CHANGE; repeat inspection' if changed else 'BEST_EFFORT_READ_ONLY; not a transactional snapshot',
            'jobs':[job_view(r,now) for r in page],'selected_job':job_view(selected,now) if selected else None,
            'tenant_active_jobs':[job_view(j,now) for j in tenant_active[:2]],
            'pagination':{'limit':limit,'has_more':len(history)>limit,'next_cursor':cursor_encode(library_id,states,page[-1]['_id']) if len(history)>limit else None,
                          'order':'Mongo insertion _id descending; not FIFO order','filter_states':states},
            'worker':worker_view(active[:5],now),
            'queue':{'scope':'AUTHORIZED_DATABASE_JOB_QUEUE; intentionally includes other tenant UUIDs',
                     'queued_total':totals.get('QUEUED',0),'executing_total':sum(totals.get(s,0) for s in EXECUTING),
                     'recovery_required_total':totals.get('RECOVERY_REQUIRED',0),'oldest_queued_age_seconds':age(heads[0].get('created_at'),now) if heads else None,
                     'executing_total_basis':'durable executing states; not proof of a live process',
                     'oldest_observed_jobs':[job_view(r,now)|{'tenant_barrier_observed':r.get('library_id') in locked} for r in heads[:3]],
                     'executing_observations_truncated':len(active)>5,'selected_job_position_range':position,'eta':'NOT_AVAILABLE',
                     'head_of_line':'POTENTIAL_TENANT_BARRIER_BLOCK' if heads and heads[0].get('library_id') in locked else 'POTENTIAL_WAIT_BEHIND_EXECUTION_STATE' if heads and any(j.get('state') in EXECUTING for j in active) else 'UNKNOWN' if heads else 'NO_QUEUED_JOBS',
                     'wait_policy':'No ETA, queue age is observed; no prolonged-wait SLO exists. Ties are not deterministic.'},
            'targets':targets,'artifacts':artifacts,
            'resources':{'worker_cpu':'NOT_AVAILABLE','worker_memory':'NOT_AVAILABLE','gpu_memory':'NOT_AVAILABLE','disk':disk,
                         'reason':'No trustworthy PID/resource mapping from resident worker_id; no worker telemetry was added.'},
            'bounds':{'job_page_limit':limit,'artifact_entries_per_target':artifact_limit,'checksum_budget_bytes':checksum_budget,
                      'mongo_operations':len(reader.operations),'db_operation_timeout_ms':1000,
                      'catalogue_reads':0,'authorization_cached':False,'checksum_default':'OFF; explicit opt-in and shared byte/deadline budget'},
            'actions_available':[]}
