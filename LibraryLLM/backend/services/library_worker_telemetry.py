"""Canonical bounded auxiliary primitives promoted from the accepted2K prototype.

No job/target writes, native store imports, public endpoints or provisioning.
Only the fixture administrator creates the singleton/schema and writer role.
"""
from collections import Counter,deque
from datetime import datetime,timezone
import hashlib,json,secrets,time,logging
from threading import Event,Lock,Thread
from uuid import UUID,uuid4
from pymongo import MongoClient,ReturnDocument,timeout
from pymongo.uri_parser import parse_uri
from pymongo.write_concern import WriteConcern
from pymongo.read_preferences import ReadPreference

COLLECTION='institution_worker_telemetry_v2k'
SLOT='resident-tenant-worker-v1'
PREFIX='luminar_v2k_fixture_'
MAX_PROGRESS=8
MAX_BYTES=16384
STAGES={'DATASET','EMBEDDING','KG_METADATA','VALIDATION','PUBLISH','COMPLETE','FAILED','RECOVERY_REQUIRED','RECOVERED'}
ACTIVE={'RUNNING','VALIDATING','PUBLISHING'}
PHASE={'QUEUED':0,'RUNNING':1,'VALIDATING':2,'PUBLISHING':3,'SUCCEEDED':4}


class TelemetryError(Exception):pass


def uuid(value):
    try:return isinstance(value,str) and str(UUID(value))==value
    except (TypeError,ValueError,AttributeError):return False


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()


def utc(value):return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc) if isinstance(value,datetime) else None


def native_ref(owner):
    return 'worker-'+hashlib.sha256(owner.encode()).hexdigest()[:16] if isinstance(owner,str) and owner.startswith('tenant-') and uuid(owner[7:]) else None


def tuple_of(row):return [row.get(k) for k in ['state','stage','progress_current','progress_total']]


def safe_context(row,owner):
    if (not isinstance(row,dict) or row.get('worker_id')!=owner or not native_ref(owner)
            or not all(uuid(row.get(k)) for k in ['job_id','library_id','fence_token'])
            or row.get('target') not in ['SEARCH_INDEX','KNOWLEDGE_GRAPH']):
        return None
    return {k:row[k] for k in ['job_id','library_id','target','fence_token','worker_id']}


class Actor:
    """Synchronous, restricted auxiliary operations; used by a separate thread."""
    app_name='LuminaR-2K-prototype-telemetry'
    def database_allowed(self,database):
        """Default retains the2K fixture-only boundary; integration must bind explicitly."""
        return isinstance(database,str) and database.startswith(PREFIX)

    def __init__(self,uri,database,owner,*,instance_factory=uuid4):
        if not self.database_allowed(database) or not native_ref(owner):raise TelemetryError('PROTOTYPE_ONLY')
        try:
            p=parse_uri(uri)
            if (not uri.startswith('mongodb://') or p['database']!=database or not p['username'] or not p['password']
                    or len(p['nodelist'])!=1 or p['nodelist'][0][0] not in ['localhost','127.0.0.1','::1']
                    or p['options'].get('authsource',database)!=database
                    or p['options'].get('authmechanism','SCRAM-SHA-256') not in ['SCRAM-SHA-256','SCRAM-SHA-1']):raise ValueError()
        except Exception:raise TelemetryError('WRITER_AUTH_REQUIRED') from None
        self.client=MongoClient(uri,serverSelectionTimeoutMS=500,connectTimeoutMS=500,socketTimeoutMS=500,
                                retryReads=False,retryWrites=False,maxPoolSize=2,appname=self.app_name)
        self.db=self.client.get_database(database,write_concern=WriteConcern(w=1,j=True),read_preference=ReadPreference.PRIMARY)
        self.collection=self.db[COLLECTION]
        self.owner=owner;self.instance_id=str(instance_factory());self.boot_hash=digest(secrets.token_hex(32))
        if not uuid(self.instance_id):self.client.close();raise TelemetryError('INVALID_INSTANCE')
        self.epoch=None;self.lock=Lock();self.metrics=Counter();self.latencies=[];self.ownership_lost=False
        try:
            with timeout(.5):
                info=self.db.command('connectionStatus',showPrivileges=True).get('authInfo',{})
            users=info.get('authenticatedUsers',[])
            privileges=info.get('authenticatedUserPrivileges',[])
            actual={(p.get('resource',{}).get('db'),p.get('resource',{}).get('collection'),a) for p in privileges for a in p.get('actions',[])}
            expected={(database,COLLECTION,'find'),(database,COLLECTION,'update'),
                      (database,'institution_intelligence_jobs','find'),(database,'institution_intelligence_targets','find')}
            if len(users)!=1 or users[0].get('db')!=database or actual!=expected:raise TelemetryError('WRITER_PRIVILEGES_UNQUALIFIED')
        except Exception:
            self.client.close();raise TelemetryError('WRITER_AUTH_UNAVAILABLE_OR_UNQUALIFIED') from None

    def call(self,kind,fn):
        at=time.perf_counter()
        try:
            with timeout(.5):value=fn()
            self.metrics[kind]+=1
            return value
        except Exception as error:
            code=getattr(error,'code',None)
            label='PERMISSION_DENIED' if code==13 else 'INVALID_DOCUMENT' if code==121 else 'AUXILIARY_UNAVAILABLE'
            self.metrics['errors_'+label]+=1
            raise TelemetryError(label) from None
        finally:
            self.latencies.append({'kind':kind,'ms':(time.perf_counter()-at)*1000})
            if len(self.latencies)>512:self.latencies.pop(0)

    def query(self):return {'_id':SLOT,'epoch':self.epoch,'current.instance_id':self.instance_id,'current.boot_hash':self.boot_hash}

    def start(self):
        with self.lock:
            row=self.call('boot_read',lambda:self.collection.find_one({'_id':SLOT},max_time_ms=400))
            if not row or row.get('schema')!=1:raise TelemetryError('TELEMETRY_NOT_PROVISIONED')
            for current in [row.get('current'),row.get('previous')]:
                if current and current.get('instance_id')==self.instance_id:
                    if current.get('boot_hash')==self.boot_hash and current is row.get('current'):
                        self.epoch=row['epoch'];return True
                    raise TelemetryError('DUPLICATE_INSTANCE_ID')
            epoch=row.get('epoch')
            if type(epoch) is not int or epoch<0:raise TelemetryError('MALFORMED_TELEMETRY')
            current={'instance_id':{'$literal':self.instance_id},'boot_hash':{'$literal':self.boot_hash},
                     'native_worker_ref':{'$literal':native_ref(self.owner)},'started_at':'$$NOW','last_seen_at':'$$NOW',
                     'stopped_at':None,'lifecycle':'IDLE','pulse_seq':0,'progress_seq':0,'progress':[],
                     'clock_rollback':False,'current_job':None}
            result=self.call('boot_write',lambda:self.collection.find_one_and_update({'_id':SLOT,'epoch':epoch},
                [{'$set':{'previous':'$current','current':current,'epoch':{'$add':['$epoch',1]}}}],
                return_document=ReturnDocument.AFTER,maxTimeMS=400))
            if not result:raise TelemetryError('BOOT_CAS_CONFLICT')
            self.epoch=result['epoch'];return True

    def pulse(self,lifecycle='IDLE',context=None):
        if lifecycle not in ['IDLE','ACTIVE','STOPPING','STOPPED']:raise TelemetryError('INVALID_LIFECYCLE')
        job=None
        if context:
            if safe_context(context,self.owner) is None:raise TelemetryError('INVALID_NATIVE_CONTEXT')
            job={k:context[k] for k in ['job_id','library_id','target']}
        patch={'current.last_seen_at':'$$NOW','current.lifecycle':{'$literal':lifecycle},
               'current.current_job':{'$literal':job},'current.pulse_seq':{'$add':['$current.pulse_seq',1]},
               'current.clock_rollback':{'$or':['$current.clock_rollback',{'$lt':['$$NOW','$current.last_seen_at']}]}}
        if lifecycle=='STOPPED':patch['current.stopped_at']='$$NOW'
        value=self.call('pulse_write' if lifecycle!='STOPPED' else 'stop_write',lambda:self.collection.update_one(self.query(),[{'$set':patch}]))
        if not value.matched_count:self.metrics['old_instance_rejected']+=1;self.ownership_lost=True;return False
        return True

    def observe(self,context):
        if safe_context(context,self.owner) is None:raise TelemetryError('INVALID_NATIVE_CONTEXT')
        with self.lock:
            row=self.call('job_read',lambda:self.db.institution_intelligence_jobs.find_one(
                {k:context[k] for k in ['job_id','library_id','fence_token','worker_id']},
                {k:1 for k in ['job_id','library_id','target','worker_id','fence_token','state','stage','progress_current','progress_total',
                              'lease_expires_at','effective_active','artifact_generation_id','requested_generation_id']},max_time_ms=400))
            if not row or row.get('target')!=context['target']:
                self.metrics['native_context_rejected']+=1;return False
            state=row.get('state');stage=row.get('stage');now=datetime.now(timezone.utc)
            if state in ACTIVE:
                deadline=utc(row.get('lease_expires_at'))
                if not row.get('effective_active') or not deadline or deadline<=now:
                    self.metrics['native_context_rejected']+=1;return False
            elif state not in ['SUCCEEDED','FAILED','RECOVERY_REQUIRED']:return False
            if stage not in STAGES or any(type(row.get(k)) is not int or not 0<=row[k]<=1000000 for k in ['progress_current','progress_total']):
                raise TelemetryError('MALFORMED_NATIVE_PROGRESS')
            slot=self.call('progress_read',lambda:self.collection.find_one(self.query(),max_time_ms=400))
            if not slot:self.metrics['old_instance_rejected']+=1;self.ownership_lost=True;return False
            current=slot['current'];entries=current.get('progress',[])
            if not isinstance(entries,list) or len(entries)>MAX_PROGRESS:raise TelemetryError('MALFORMED_TELEMETRY')
            fence_ref=digest(row['fence_token']);key=row['job_id']+':'+fence_ref
            previous=next((e for e in entries if e.get('key')==key),None)
            fingerprint=digest(tuple_of(row))
            if previous and previous.get('fingerprint')==fingerprint:
                self.metrics['identical_progress_ignored']+=1;return True
            acknowledged=False
            if state=='SUCCEEDED':
                pointer=self.call('pointer_read',lambda:self.db.institution_intelligence_targets.find_one(
                    {'library_id':row['library_id'],'target':row['target']},{'published_by_job_id':1,'active_generation_id':1,'source_generation_id':1},max_time_ms=400)) or {}
                acknowledged=(pointer.get('published_by_job_id')==row['job_id'] and pointer.get('active_generation_id')==row.get('artifact_generation_id')
                              and pointer.get('source_generation_id')==row.get('requested_generation_id') and uuid(row.get('artifact_generation_id')) and uuid(row.get('requested_generation_id')))
            old_tuple=previous.get('tuple') if previous else None
            meaningful=state in ACTIVE and (not old_tuple or PHASE.get(state,-1)>PHASE.get(old_tuple[0],-1)
                or stage!=old_tuple[1] or row['progress_current']>old_tuple[2]) or state=='SUCCEEDED' and acknowledged
            entry={k:{'$literal':row[k]} for k in ['job_id','library_id','target','state','stage','progress_current','progress_total']}
            entry.update(key={'$literal':key},fence_ref={'$literal':fence_ref},native_worker_ref={'$literal':native_ref(self.owner)},
                         fingerprint={'$literal':fingerprint},tuple={'$literal':tuple_of(row)},observed_at='$$NOW',
                         last_progress_observed_at='$$NOW' if meaningful else {'$literal':previous.get('last_progress_observed_at') if previous else None},
                         last_outcome_observed_at='$$NOW' if state in ['SUCCEEDED','FAILED','RECOVERY_REQUIRED'] else {'$literal':previous.get('last_outcome_observed_at') if previous else None},
                         publication={'$literal':'ACKNOWLEDGED_POINTER_MATCH' if acknowledged else 'UNKNOWN' if state in ['SUCCEEDED','RECOVERY_REQUIRED'] else 'NOT_COMPLETE'},
                         kind={'$literal':'PROGRESS' if meaningful else 'OUTCOME' if state in ['FAILED','RECOVERY_REQUIRED','SUCCEEDED'] else 'OBSERVATION'})
            update={'current.progress':{'$slice':[{'$concatArrays':[{'$filter':{'input':'$current.progress','as':'p','cond':{'$ne':['$$p.key',key]}}},[entry]]},-MAX_PROGRESS]},
                    'current.progress_seq':{'$add':['$current.progress_seq',1]},
                    'current.clock_rollback':{'$or':['$current.clock_rollback',{'$lt':['$$NOW','$current.last_seen_at']}]}}
            q=self.query()|{'current.progress_seq':current.get('progress_seq',0)}
            value=self.call('progress_write',lambda:self.collection.update_one(q,[{'$set':update}]))
            if not value.matched_count:self.metrics['progress_cas_rejected']+=1;return False
            return True

    def close(self):self.client.close()


class Agent:
    """Bounded auxiliary thread; native callbacks only enqueue trusted context."""
    def __init__(self,factory,owner,*,pulse_seconds=10,poll_seconds=1):
        if not .05<=pulse_seconds<=60 or not .05<=poll_seconds<=60:raise ValueError('prototype interval')
        self.factory,self.owner=factory,owner;self.pulse_seconds,self.poll_seconds=pulse_seconds,poll_seconds
        self.stop_event=Event();self.ready=Event();self.thread=None;self.lock=Lock();self.active=None;self.pending=deque(maxlen=8)
        self.actor=None;self.errors=Counter();self.normal_stop=False
        self.lifecycle_lock=Lock();self.accepting=True;self.closed=False;self.report_stopping=False;self.state='CREATED'

    def note_claim(self,row):
        context=safe_context(row,self.owner)
        if context and self.accepting:
            with self.lock:self.active=context

    def note_finished(self):
        with self.lock:
            if self.active and self.accepting:self.pending.append(self.active)
            self.active=None

    def note_progress(self,row):
        # Trusted post-ack hint only. Sampling/Actor reads determine accepted tuple.
        self.note_claim(row)

    def start(self):
        with self.lifecycle_lock:
            if self.thread or self.closed:return
            self.state='STARTING'
            self.thread=Thread(target=self.loop,name='worker-telemetry-observer',daemon=True);self.thread.start()

    def error(self,code):
        if not self.errors[code]:logging.getLogger(__name__).warning('Worker telemetry observer unavailable: %s',code)
        self.errors[code]=min(self.errors[code]+1,1000000)

    def loop(self):
        try:
            self.actor=self.factory();self.actor.start()
        except Exception:
            self.error('TELEMETRY_UNAVAILABLE');self.state='UNAVAILABLE';self.accepting=False;self.ready.set()
            if self.actor:
                try:self.actor.close()
                except Exception:pass
            return
        self.state='OBSERVING'
        self.ready.set();next_pulse=0
        try:
            while not self.stop_event.is_set():
                with self.lock:active=self.active;pending=list(self.pending);self.pending.clear()
                for context in pending+([active] if active else []):
                    if self.stop_event.is_set():break
                    try:self.actor.observe(context)
                    except Exception:self.error('PROGRESS_OBSERVATION_UNAVAILABLE')
                    if self.actor.ownership_lost:
                        self.state='OWNERSHIP_LOST';self.stop_event.set();break
                if self.stop_event.is_set():break
                if time.monotonic()>=next_pulse:
                    try:
                        if not self.actor.pulse('ACTIVE' if active else 'IDLE',active):
                            self.state='OWNERSHIP_LOST';self.stop_event.set()
                    except Exception:self.error('PULSE_UNAVAILABLE')
                    next_pulse=time.monotonic()+self.pulse_seconds
                self.stop_event.wait(self.poll_seconds)
        except Exception:
            self.error('OBSERVER_LOOP_UNAVAILABLE');self.state='UNAVAILABLE'
        finally:
            self.accepting=False
            if self.state!='OWNERSHIP_LOST' and (self.normal_stop or self.report_stopping):
                try:self.actor.pulse('STOPPED' if self.normal_stop else 'STOPPING')
                except Exception:self.error('STOP_OBSERVATION_UNAVAILABLE')
            try:self.actor.close()
            except Exception:self.error('CONNECTION_CLOSE_UNAVAILABLE')
            if self.state not in ['OWNERSHIP_LOST','UNAVAILABLE']:self.state='STOPPED' if self.normal_stop else 'CLOSED'

    def close(self,*,native_stopped):
        with self.lifecycle_lock:
            self.normal_stop=self.normal_stop or bool(native_stopped)
            self.accepting=False;self.closed=True;self.stop_event.set()
        if self.thread and self.thread.ident!=__import__('threading').get_ident():
            self.thread.join(timeout=3)
            if self.thread.is_alive():self.error('OBSERVER_SHUTDOWN_TIMEOUT')
