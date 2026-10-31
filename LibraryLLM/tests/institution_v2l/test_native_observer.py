"""Native worker/real Mongo contract tests; deterministic encoder, not native-model qualification."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from threading import Event
import time
from uuid import uuid4
import pytest
from backend.services.library_worker_observer import NativeObserver,RestrictedWriter,Configuration,configured_factory,ENABLE_ENV,URI_ENV
from backend.services.library_worker_telemetry import COLLECTION,SLOT,TelemetryError
from backend.services.library_worker_diagnostics import classify


def wait_until(fn,seconds=8):
    deadline=time.monotonic()+seconds
    while not fn():
        assert time.monotonic()<deadline,'Expected bounded observation did not arrive'
        time.sleep(.02)

def record(s):return s.db[COLLECTION].find_one({'_id':SLOT})
def fast_factory(s):return lambda owner:NativeObserver(lambda:RestrictedWriter(Configuration(s.database,s.telemetry_uri),owner),owner,pulse_seconds=.1,poll_seconds=.05)
def request(s,lib,target='SEARCH_INDEX'):
    from backend.services import library_intelligence_store as store
    return store.request_build(lib,{'sub':'1'},target)
def outcome(s,j):return s.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']})


def test_native_worker_disabled_by_default(lab,worker_factory):
    w=worker_factory();w.start();wait_until(lambda:w.thread.is_alive())
    assert w.observer is None and record(lab)['epoch']==0

def test_native_worker_starts_one_observer(lab,worker_factory):
    calls=[]
    def factory(owner):calls.append(owner);return fast_factory(lab)(owner)
    w=worker_factory(observer_factory=factory);w.start();assert w.observer.ready.wait(3)
    assert calls==[w.worker_id] and w.observer.thread.is_alive() and w.observer.owner==w.worker_id

def test_actual_install_wires_explicit_factory_without_new_routes(lab,monkeypatch):
    from fastapi import FastAPI
    from search.library_intelligence_api import install
    class Model:
        def __getitem__(self,index):return object()
        def encode(self,*a,**kw):raise AssertionError('Idle must not encode')
    class Ranker:
        def predict(self,*a,**kw):raise AssertionError('Idle must not rerank')
    class Engine:embedding_model=Model();reranker=Ranker()
    monkeypatch.setenv(ENABLE_ENV,'1');monkeypatch.setenv(URI_ENV,lab.telemetry_uri)
    app=FastAPI();install(app,Engine());w=app.state.tenant_intelligence
    assert w.start in app.router.on_startup and not any('telemetry' in path for path in app.openapi()['paths'])
    try:w.start();assert w.observer.ready.wait(3) and w.observer.state=='OBSERVING'
    finally:w.close();w.thread.join(timeout=1)

def test_degraded_install_does_not_start_build_worker(lab):
    from fastapi import FastAPI
    from search.library_intelligence_api import install
    class Engine:embedding_model=None;reranker=None
    app=FastAPI();install(app,Engine());w=app.state.tenant_intelligence
    assert w.start not in app.router.on_startup and w.observer is None
    w.close()

def test_native_worker_repeated_start_safe(lab,worker_factory):
    calls=[]
    def factory(owner):calls.append(owner);return fast_factory(lab)(owner)
    w=worker_factory(observer_factory=factory)
    with ThreadPoolExecutor(3) as p:list(p.map(lambda _:w.start(),range(6)))
    assert w.observer.ready.wait(3);native_thread,observer_thread=w.thread,w.observer.thread
    w.start();assert w.thread is native_thread and w.observer.thread is observer_thread and len(calls)==1

def test_native_worker_idle_observation(lab,worker_factory):
    w=worker_factory(observer_factory=fast_factory(lab));w.start();assert w.observer.ready.wait(3)
    wait_until(lambda:record(lab)['current']['pulse_seq']>=2)
    d=record(lab);assert d['current']['lifecycle']=='IDLE' and lab.db.institution_intelligence_jobs.count_documents({})==0
    assert classify(d,datetime.now(timezone.utc))['classification']=='RECENTLY_OBSERVED'

def test_native_worker_active_observation_and_return_idle(lab,worker_factory,library):
    entered,release=Event(),Event()
    def fail(stage):
        if stage=='EMBEDDING_BATCH':entered.set();assert release.wait(5)
    lib=library();j=request(lab,lib);w=worker_factory(observer_factory=fast_factory(lab),fail=fail);w.start()
    try:
        assert entered.wait(5)
        wait_until(lambda:(record(lab).get('current') or {}).get('lifecycle')=='ACTIVE')
        c=record(lab)['current'];assert c['current_job']['job_id']==j['job_id']
    finally:release.set()
    wait_until(lambda:outcome(lab,j)['state']=='SUCCEEDED');wait_until(lambda:record(lab)['current']['lifecycle']=='IDLE')
    assert record(lab)['current']['current_job'] is None

def test_native_progress_hint_after_acknowledgement(lab,worker_factory,library):
    observations=[]
    class Recorder:
        def started(self):pass
        def claimed(self,j):assert outcome(lab,j)['state']=='RUNNING'
        def progress(self,j):
            row=outcome(lab,j);observations.append((row['state'],row['stage'],row['progress_current']))
        def finished(self,j):assert outcome(lab,j)['state'] in ['SUCCEEDED','FAILED','RECOVERY_REQUIRED']
        def stopping(self,native_stopped=False):pass
        def stopped(self):pass
    j=request(lab,library());w=worker_factory(observer_factory=lambda _:Recorder());w.start()
    wait_until(lambda:outcome(lab,j)['state']=='SUCCEEDED')
    assert any(stage=='EMBEDDING' for _,stage,_ in observations)
    assert ('VALIDATING','VALIDATION',3) in observations and ('PUBLISHING','PUBLISH',3) in observations
    assert w.observer_errors==0

def test_observer_cannot_mutate_native_claim_context(lab,worker_factory,library):
    class Mutating:
        def started(self):pass
        def claimed(self,j):j.update(job_id='foreign',fence_token='foreign',library_id='foreign')
        def progress(self,j):j.update(job_id='foreign',fence_token='foreign')
        def finished(self,j):j.clear()
        def stopping(self,**kw):pass
        def stopped(self):pass
    lib=library();j=request(lab,lib);w=worker_factory(observer_factory=lambda _:Mutating());w.start()
    wait_until(lambda:outcome(lab,j)['state']=='SUCCEEDED')
    row=outcome(lab,j);assert row['library_id']==lib and row['fence_token']!='foreign' and row['worker_id']==w.worker_id

def test_native_worker_shutdown_bounded_and_no_orphan(lab,worker_factory):
    w=worker_factory(observer_factory=fast_factory(lab));w.start();assert w.observer.ready.wait(3)
    at=time.monotonic();w.close();assert time.monotonic()-at<3.5
    assert not w.observer.thread.is_alive();w.thread.join(timeout=1);assert not w.thread.is_alive()
    assert record(lab)['current']['lifecycle'] in ['STOPPING','STOPPED']
    epoch=record(lab)['epoch'];w.start();assert record(lab)['epoch']==epoch and not w.observer.thread.is_alive()

def test_native_close_does_not_join_inflight_or_invent_shutdown(lab,worker_factory,library):
    entered,release=Event(),Event()
    def fail(stage):
        if stage=='EMBEDDING_BATCH':entered.set();assert release.wait(5)
    j=request(lab,library());w=worker_factory(observer_factory=fast_factory(lab),fail=fail);w.start()
    try:
        assert entered.wait(5);at=time.monotonic();w.close()
        assert time.monotonic()-at<3.5 and w.thread.is_alive()
        assert record(lab)['current']['lifecycle']=='STOPPING'
        assert not w.observer.thread.is_alive()
    finally:release.set()
    w.thread.join(timeout=5);assert outcome(lab,j)['state']=='SUCCEEDED'

def test_native_worker_restart_new_identity(lab,worker_factory):
    a=worker_factory(observer_factory=fast_factory(lab));a.start();assert a.observer.ready.wait(3)
    first=record(lab)['current']['instance_id'];a.close();a.thread.join(timeout=1)
    b=worker_factory(observer_factory=fast_factory(lab));b.start();assert b.observer.ready.wait(3)
    d=record(lab);assert d['epoch']==2 and d['current']['instance_id']!=first and d['previous']['instance_id']==first

def test_old_observer_loses_epoch_and_terminates(lab,worker_factory):
    a=worker_factory(observer_factory=fast_factory(lab));a.start();assert a.observer.ready.wait(3)
    b=worker_factory(observer_factory=fast_factory(lab));b.start();assert b.observer.ready.wait(3)
    wait_until(lambda:not a.observer.thread.is_alive())
    assert a.observer.state=='OWNERSHIP_LOST' and record(lab)['current']['instance_id']==b.observer.actor.instance_id
    assert a.observer.actor.ownership_lost and a.observer.actor.metrics['old_instance_rejected']>=1

def test_telemetry_write_frequency_bounded(lab,worker_factory):
    w=worker_factory(observer_factory=fast_factory(lab));w.start();assert w.observer.ready.wait(3)
    time.sleep(.36);w.close();n=w.observer.actor.metrics['pulse_write']
    assert 2<=n<=5 and lab.db[COLLECTION].count_documents({})==1

@pytest.mark.parametrize('fault',['factory','callback'])
def test_telemetry_observer_exception_isolated(lab,worker_factory,library,fault):
    class Broken:
        def __getattr__(self,name):
            def broken(*a,**kw):raise RuntimeError('private exception must not leak')
            return broken
    def factory(owner):
        if fault=='factory':raise RuntimeError('private exception must not leak')
        return Broken()
    j=request(lab,library());w=worker_factory(observer_factory=factory);w.start()
    wait_until(lambda:outcome(lab,j)['state']=='SUCCEEDED')
    assert w.observer_errors and lab.db.institution_intelligence_jobs.count_documents({})==1

@pytest.mark.parametrize('mode',['timeout','connection','permission'])
def test_native_build_telemetry_failure_isolated(lab,worker_factory,library,mode):
    entered,release=Event(),Event()
    def fail(stage):
        if stage=='EMBEDDING_BATCH':entered.set();assert release.wait(5)
    j=request(lab,library());w=worker_factory(observer_factory=fast_factory(lab),fail=fail);w.start()
    assert w.observer.ready.wait(3) and entered.wait(5)
    roles=[{'role':'fixture_telemetry_writer','db':lab.database}]
    try:
        if mode=='permission':lab.db.command('revokeRolesFromUser','fixture_telemetry',roles=roles)
        else:
            data={'failCommands':['update'],'appName':RestrictedWriter.app_name}
            data.update({'blockConnection':True,'blockTimeMS':1200} if mode=='timeout' else {'closeConnection':True})
            lab.writer.admin.command('configureFailPoint','failCommand',mode={'times':1},data=data)
        time.sleep(.8);release.set();wait_until(lambda:outcome(lab,j)['state']=='SUCCEEDED')
        assert sum(w.observer.errors.values())>0
    finally:
        release.set()
        lab.writer.admin.command('configureFailPoint','failCommand',mode='off')
        prior_pulses=w.observer.actor.metrics['pulse_write']
        if mode=='permission':lab.db.command('grantRolesToUser','fixture_telemetry',roles=roles)
    # The same instance can resume pulses after restored connectivity/permissions.
    wait_until(lambda:w.observer.actor.metrics['pulse_write']>prior_pulses)

def test_native_failed_rebuild_preserves_last_good(lab,worker_factory,library):
    from fastapi import HTTPException
    lib=library();a=request(lab,lib,'KNOWLEDGE_GRAPH');w=worker_factory();assert w.run_one()
    old=lab.db.institution_intelligence_targets.find_one({'library_id':lib})['active_generation_id']
    b=request(lab,lib,'KNOWLEDGE_GRAPH')
    def fail(stage):
        if stage=='VALIDATION':raise HTTPException(409,'ARTIFACT_CORRUPT')
    v=worker_factory(observer_factory=fast_factory(lab),fail=fail);v.start();wait_until(lambda:outcome(lab,b)['state']=='FAILED')
    assert lab.db.institution_intelligence_targets.find_one({'library_id':lib})['active_generation_id']==old

def test_native_recovery_required_unchanged(lab,worker_factory,library):
    def fail(stage):
        if stage=='ACKNOWLEDGEMENT_LOSS':raise RuntimeError('fixture acknowledgement loss')
    lib=library();j=request(lab,lib,'KNOWLEDGE_GRAPH');w=worker_factory(observer_factory=fast_factory(lab),fail=fail);w.start()
    wait_until(lambda:outcome(lab,j)['state']=='RECOVERY_REQUIRED')
    row=outcome(lab,j);pointer=lab.db.institution_intelligence_targets.find_one({'library_id':lib})
    assert row['effective_active'] and pointer['published_by_job_id']==j['job_id']
    time.sleep(.2);assert outcome(lab,j)['state']=='RECOVERY_REQUIRED' and lab.db.institution_intelligence_jobs.count_documents({})==1

def test_auxiliary_thread_unexpected_exception_and_shutdown_timeout(lab):
    # Controlled blocked test callback is released after the bounded join; no orphan remains.
    release=Event()
    class Blocked:
        ownership_lost=False
        def start(self):pass
        def pulse(self,*a):release.wait(5);return True
        def close(self):pass
    a=NativeObserver(lambda:Blocked(),'tenant-'+str(uuid4()),pulse_seconds=.1,poll_seconds=.05)
    a.start();assert a.ready.wait(1);time.sleep(.05)
    at=time.monotonic();a.stopping();elapsed=time.monotonic()-at
    try:assert elapsed<3.5 and a.errors['OBSERVER_SHUTDOWN_TIMEOUT']==1
    finally:release.set();a.thread.join(timeout=2)
    assert not a.thread.is_alive()

def test_agent_loop_unexpected_exception_is_sanitized(lab,caplog):
    class Unexpected:
        def start(self):pass
        def pulse(self,*a):return True
        def close(self):pass
        @property
        def ownership_lost(self):raise OSError('private disk-full simulation')
        def observe(self,*a):return True
    owner='tenant-'+str(uuid4());a=NativeObserver(lambda:Unexpected(),owner,pulse_seconds=.1,poll_seconds=.05)
    a.note_claim({'worker_id':owner,'job_id':str(uuid4()),'library_id':str(uuid4()),'fence_token':str(uuid4()),'target':'SEARCH_INDEX'})
    a.start();wait_until(lambda:a.state=='UNAVAILABLE');a.stopping()
    assert a.errors['OBSERVER_LOOP_UNAVAILABLE']==1 and 'private disk-full' not in caplog.text

def test_observer_thread_exception_during_native_build_isolated(lab,worker_factory,library):
    entered,release=Event(),Event()
    def fail(stage):
        if stage=='EMBEDDING_BATCH':entered.set();assert release.wait(5)
    class Exploding(RestrictedWriter):
        def __getattribute__(self,name):
            if name=='ownership_lost' and entered.is_set():raise RuntimeError('private injected observer error')
            return super().__getattribute__(name)
    def factory(owner):return NativeObserver(lambda:Exploding(Configuration(lab.database,lab.telemetry_uri),owner),owner,pulse_seconds=.1,poll_seconds=.05)
    j=request(lab,library());w=worker_factory(observer_factory=factory,fail=fail);w.start()
    try:
        assert entered.wait(8),{k:outcome(lab,j).get(k) for k in ['state','stage','error_code']}
        wait_until(lambda:w.observer.state=='UNAVAILABLE')
        assert w.thread.is_alive() and not w.observer.accepting
    finally:release.set()
    wait_until(lambda:outcome(lab,j)['state']=='SUCCEEDED')
    assert w.observer.errors['OBSERVER_LOOP_UNAVAILABLE']==1
