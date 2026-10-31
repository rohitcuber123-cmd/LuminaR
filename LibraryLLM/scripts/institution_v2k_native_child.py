"""Owned child laboratory: actual native resident worker and offline MiniLM/FAISS/KG.

All connection/artifact settings must be supplied by the auth-enabled parent
fixture before any application import. No production defaults are accepted.
"""
import argparse,gc,json,os,sys,time
from contextlib import nullcontext
from datetime import datetime,timezone
from pathlib import Path
from threading import Event,Thread
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
assert os.environ.get('LUMINAR_V2K_ISOLATED_CHILD')=='1'
assert os.environ.get('MONGO_DB_NAME','').startswith('luminar_v2k_fixture_')
assert os.environ.get('MONGO_URI','').startswith('mongodb://fixture_admin:')
assert Path(os.environ['LIBRARY_INTELLIGENCE_ROOT']).name=='tenant-artifacts'
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',
                  NOTIFICATION_DUE_WORKER_ENABLED='0',NOTIFICATION_OUTBOX_WORKER_ENABLED='0',
                  JWT_SECRET_KEY='v2k-disposable-native-jwt')
from backend.database.mongodb import db,client as mongo
from backend.services import institution_repository as repo,library_catalogue_repository as inventory,library_intelligence_store as store
from backend.services import library_intelligence_artifacts as artifacts
from search.library_intelligence import TenantIntelligence
from scratch.institution_v2k_telemetry.telemetry import Actor,Agent,COLLECTION,SLOT,digest
from scratch.institution_v2k_telemetry.adapter import NativeAdapter


def main():
    p=argparse.ArgumentParser();p.add_argument('--scenario',choices=['success','benchmark','crash','restart','recover'],required=True)
    p.add_argument('--output',required=True);p.add_argument('--fault',default='');p.add_argument('--target',default='SEARCH_INDEX')
    p.add_argument('--enabled',action='store_true');p.add_argument('--bad-writer',action='store_true')
    p.add_argument('--seed-last-good',action='store_true');p.add_argument('--queued-c',action='store_true');p.add_argument('--drain-queued',action='store_true')
    p.add_argument('--recovery-job');p.add_argument('--recovery-library')
    p.add_argument('--telemetry-fault',choices=['','permission','timeout'],default='');a=p.parse_args()
    import psutil
    proc=psutil.Process();output=Path(a.output)
    result={'scenario':a.scenario,'enabled':a.enabled,'fault':a.fault,'actual_native_resident_worker':True,
            'authentication':'Actual existing JWT decoder and current DB identity; no dependency override.',
            'stages':[],'events':[],'builds':[],'security':[],'model':'NOT_LOADED_KG_OR_IDLE',
            'telemetry_writer_mode':'UNQUALIFIED_READ_ONLY_WRITER' if a.bad_writer else 'RESTRICTED_AUXILIARY_WRITER',
            'telemetry_fault':a.telemetry_fault}
    def save():output.write_text(json.dumps(result,indent=2,default=str),encoding='utf8')
    repo.ensure_indexes();inventory.ensure_indexes();store.initialize()
    for user in range(1,7):db.users.update_one({'user_id':user},{'$set':{'name':'Private fixture identity','email':f'v2k-{user}@example.com',
        'is_active':True,'is_email_verified':True,'role':'ADMIN' if user==6 else 'GENERAL_USER'}},upsert=True)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.routes.library_intelligence import router
    from backend.utils.jwt_utils import create_access_token
    app=FastAPI();app.include_router(router);api=TestClient(app)
    def headers(user=1):return {'Authorization':'Bearer '+create_access_token(user,f'v2k-{user}@example.com','GENERAL_USER')}
    if a.scenario=='recover':
        r=api.post(f'/libraries/{a.recovery_library}/intelligence/jobs/{a.recovery_job}/recover',headers=headers())
        result.update(actual_native_resident_worker=False,explicit_native_recovery_http=r.status_code,recovered_job=r.json(),
                      recovery_authority='Explicit existing Library Admin endpoint, invoked only by this fixture experiment; never telemetry-triggered.')
        save();assert r.status_code==200,r.text;mongo.close();return
    def seed(n=10):
        lib=str(uuid4());repo.collection('libraries').insert_one({'library_id':lib,'slug_normalized':lib,'name':'Private fixture',
            'status':'ACTIVE','library_type':'PRIVATE_INSTITUTION','access_mode':'PRIVATE_CODE'})
        repo.collection('memberships').insert_one({'membership_id':str(uuid4()),'library_id':lib,'user_id':1,'role':'ADMIN','is_owner':True,'status':'ACTIVE'})
        for user,role in [(3,'LIBRARIAN'),(4,'MEMBER')]:repo.collection('memberships').insert_one({'membership_id':str(uuid4()),'library_id':lib,'user_id':user,'role':role,'status':'ACTIVE'})
        repo.collection('library_books').insert_many([{'library_id':lib,'library_book_id':str(uuid4()),'status':'ACTIVE','accession_number':str(i),
            'accession_sequence':i,'title':f'Private fixture networks {i}','authors':['Fixture author'],'subjects':['Networks','Technology'],
            'description':'Private synthetic catalogue metadata.','publication_year':'2020','classification':'004'} for i in range(n)])
        return lib
    need_search=a.scenario in ['success','benchmark'] or a.scenario=='crash' and a.target=='SEARCH_INDEX' or a.queued_c or a.drain_queued
    if need_search:
        import torch,faiss
        from sentence_transformers import SentenceTransformer
        torch.set_num_threads(2);faiss.omp_set_num_threads(2)
        cache=Path.home()/'.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2'
        rev=(cache/'refs/main').read_text().strip();at=time.perf_counter()
        model=SentenceTransformer(str(cache/'snapshots'/rev),device='cpu',local_files_only=True);model.max_seq_length=256
        result['model']={'name':store.MODEL,'revision':rev,'offline':True,'device':'cpu','load_ms':(time.perf_counter()-at)*1000}
        def encode(texts):return model.encode(texts,normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)
    else:
        def encode(texts):raise AssertionError('KG/idle experiment must not encode')
    active_job=[None];first_fault=[False];armed=[not a.seed_last_good];injected=[False];monitor_stop=Event();worker=None;agent=None
    def sample():
        if not active_job[0]:return
        j=repo.collection('intelligence_jobs').find_one({'job_id':active_job[0]}) or {}
        slot=db[COLLECTION].find_one({'_id':SLOT}) or {};c=slot.get('current') or {}
        event={'at':datetime.now(timezone.utc),'state':j.get('state'),'stage':j.get('stage'),
               'current':j.get('progress_current'),'total':j.get('progress_total'),'heartbeat_at':j.get('heartbeat_at'),
               'pulse_seq':c.get('pulse_seq'),'progress_seq':c.get('progress_seq'),
               'progress':[{k:e.get(k) for k in ['job_id','stage','state','progress_current','last_progress_observed_at','publication']} for e in c.get('progress',[]) if e.get('job_id')==active_job[0]]}
        key=[event[k] for k in ['state','stage','current','total','heartbeat_at','pulse_seq','progress_seq']]
        if not result['events'] or result['events'][-1].get('key')!=key:
            event['key']=key;result['events'].append(event)
            if len(result['events'])>500:result['events'].pop(0)
    def monitor():
        while not monitor_stop.wait(.1):
            try:sample()
            except Exception:pass
    def fail(stage):
        if stage not in result['stages']:result['stages'].append(stage)
        if a.telemetry_fault and stage=='EMBEDDING_BATCH' and not injected[0]:
            injected[0]=True
            if a.telemetry_fault=='permission':
                db.command('revokeRolesFromUser','fixture_telemetry',roles=[{'role':'fixture_telemetry_writer','db':db.name}])
                result['telemetry_fault_injected']='Actual server role revocation while native Search embedding active; native writer untouched.'
                time.sleep(12)
            else:
                mongo.admin.command('configureFailPoint','failCommand',mode={'times':1},data={
                    'failCommands':['update'],'appName':'LuminaR-2K-prototype-telemetry','blockConnection':True,'blockTimeMS':1200})
                result['telemetry_fault_injected']='Actual server auxiliary update block1200ms against500ms client deadline during native Search.'
                time.sleep(3)
        if a.scenario=='crash' and armed[0] and stage==a.fault and not first_fault[0]:
            first_fault[0]=True;time.sleep(1.2);sample()
            result['crash_job']=repo.collection('intelligence_jobs').find_one({'job_id':active_job[0]},{'_id':0})
            for private in ['fence_token','worker_id']:
                result['crash_job'][private+'_digest']=digest(result['crash_job'].pop(private,None))
            result['pointer_at_crash']=repo.collection('intelligence_targets').find_one({'library_id':result['crash_job']['library_id'],'target':a.target},{'_id':0})
            if result['pointer_at_crash'] and 'fence_token' in result['pointer_at_crash']:
                result['pointer_at_crash']['fence_token_digest']=digest(result['pointer_at_crash'].pop('fence_token'))
            result['telemetry_before_crash']={k:v for k,v in (db[COLLECTION].find_one({'_id':SLOT}) or {}).items() if k in ['epoch']}
            result['instance_ref']=digest(agent.actor.instance_id) if agent and agent.actor else None
            result['genuine_process_exit']=77;save();os._exit(77)
        if a.scenario=='success':
            if stage=='EMBEDDING_BATCH' and not first_fault[0]:first_fault[0]=True;time.sleep(12)
            elif stage in ['VALIDATION','PUBLISH','KG_SERIALIZATION']:time.sleep(1.2)
    worker=TenantIntelligence(encode,model_version=store.MODEL+':native-v2k',fail=fail)
    if a.enabled:
        agent=Agent(lambda:Actor(os.environ['V2K_READER_URI'] if a.bad_writer else os.environ['V2K_TELEMETRY_URI'],db.name,worker.worker_id),worker.worker_id)
    adapter=NativeAdapter(worker,store,agent) if agent else nullcontext()
    try:
        with adapter:
            worker.start()
            if agent:agent.ready.wait(3)
            t=Thread(target=monitor,daemon=True);t.start()
            if a.scenario=='crash' and a.fault=='IDLE':
                time.sleep(1.2);result['instance_ref']=digest(agent.actor.instance_id)
                result['idle_crash']=True;result['genuine_process_exit']=77;save();os._exit(77)
            if a.scenario=='restart':
                before=list(repo.collection('intelligence_jobs').find({'effective_active':True,'state':{'$ne':'QUEUED'},'worker_id':{'$ne':worker.worker_id}},{'_id':0}))
                if a.drain_queued:
                    until=time.monotonic()+30
                    while repo.collection('intelligence_jobs').count_documents({'$or':[{'state':'QUEUED','effective_active':True},{'worker_id':worker.worker_id,'state':{'$in':['RUNNING','VALIDATING','PUBLISHING']}}]}):
                        assert time.monotonic()<until;time.sleep(.1)
                    time.sleep(1.2)
                else:time.sleep(3)
                after=list(repo.collection('intelligence_jobs').find({'job_id':{'$in':[j['job_id'] for j in before]}},{'_id':0}))
                result['old_active_jobs_unchanged']=digest(before)==digest(after)
                result['instance_ref']=digest(agent.actor.instance_id) if agent and agent.actor else None
            else:
                if a.scenario in ['success','benchmark']:
                    c0=time.process_time();r0=proc.memory_info().rss;idle0=time.perf_counter()
                    time.sleep(32 if a.scenario=='success' else 22)
                    slot=db[COLLECTION].find_one({'_id':SLOT}) or {};c=slot.get('current') or {}
                    result['idle']={'seconds':time.perf_counter()-idle0,'cpu_ms':(time.process_time()-c0)*1000,
                         'rss_increase_bytes':proc.memory_info().rss-r0,'pulse_seq':c.get('pulse_seq'), 'lifecycle':c.get('lifecycle')}
                targets=['SEARCH_INDEX','KNOWLEDGE_GRAPH'] if a.scenario in ['success','benchmark'] else [a.target]
                for target in targets:
                    lib=seed(101 if target=='KNOWLEDGE_GRAPH' else 10)
                    if a.seed_last_good:
                        if a.queued_c:
                            alib=seed(10);ar=api.post(f'/libraries/{alib}/intelligence/builds',headers=headers(),json={'target':'SEARCH_INDEX'})
                            assert ar.status_code==202,ar.text
                            until=time.monotonic()+45
                            while repo.collection('intelligence_jobs').find_one({'job_id':ar.json()['job_id']})['state']!='SUCCEEDED':
                                assert time.monotonic()<until;time.sleep(.05)
                            result['library_a_search']={'library_id':alib,'job_id':ar.json()['job_id'],'state':'SUCCEEDED'}
                        prior=api.post(f'/libraries/{lib}/intelligence/builds',headers=headers(),json={'target':target});assert prior.status_code==202,prior.text
                        until=time.monotonic()+45
                        while repo.collection('intelligence_jobs').find_one({'job_id':prior.json()['job_id']})['state']!='SUCCEEDED':
                            assert time.monotonic()<until;time.sleep(.05)
                        old=repo.collection('intelligence_targets').find_one({'library_id':lib,'target':target})
                        oldpath=store.directory(lib,'search' if target=='SEARCH_INDEX' else 'kg',old['active_generation_id'])
                        result['last_good']={'generation_id':old['active_generation_id'],'files':{str(p):store.checksum(p) for p in oldpath.iterdir() if p.is_file()}}
                        armed[0]=True
                    if a.scenario=='success':
                        for user in [2,3,4,6]:
                            r=api.get(f'/libraries/{lib}/intelligence',headers=headers(user))
                            # Staff Librarian may read its own library; no operator privilege or telemetry fields are introduced.
                            result['security'].append({'user':user,'status':r.status_code,'no_telemetry_fields':'worker_instance' not in r.text and COLLECTION not in r.text})
                    at=time.perf_counter();c0=time.process_time();rss0=proc.memory_info().rss
                    r=api.post(f'/libraries/{lib}/intelligence/builds',headers=headers(),json={'target':target});assert r.status_code==202,r.text
                    j=r.json();active_job[0]=j['job_id'];result['current_library']=lib;save()
                    if a.queued_c:
                        clib=seed(10);cr=api.post(f'/libraries/{clib}/intelligence/builds',headers=headers(),json={'target':'SEARCH_INDEX'})
                        assert cr.status_code==202,cr.text
                        result['library_c_queued']={'library_id':clib,'job_id':cr.json()['job_id']};save()
                    deadline=time.monotonic()+90
                    while True:
                        row=repo.collection('intelligence_jobs').find_one({'job_id':j['job_id']})
                        if row['state'] in ['SUCCEEDED','FAILED','RECOVERY_REQUIRED']:break
                        if time.monotonic()>deadline:raise RuntimeError('Native build timed out')
                        time.sleep(.05)
                    time.sleep(1.2);sample()
                    pointer=repo.collection('intelligence_targets').find_one({'library_id':lib,'target':target})
                    result['builds'].append({'target':target,'library_id':lib,'job_id':j['job_id'],'state':row['state'],'error_code':row.get('error_code'),
                        'submit_to_observed_ms':(time.perf_counter()-at)*1000,'native_build_ms':(row['completed_at']-row['started_at']).total_seconds()*1000,
                        'cpu_ms':(time.process_time()-c0)*1000,'rss_increase_bytes':proc.memory_info().rss-rss0,
                        'pointer_ack_match':pointer.get('published_by_job_id')==j['job_id'] and pointer.get('active_generation_id')==row['artifact_generation_id']})
                    assert row['state']=='SUCCEEDED',row.get('error_code')
                    assert result['builds'][-1]['pointer_ack_match']
                    save()
                time.sleep(10.2 if a.scenario=='success' else 1.2)
                if a.scenario=='success':
                    idle=(db[COLLECTION].find_one({'_id':SLOT}) or {}).get('current') or {}
                    result['return_to_idle']={'lifecycle':idle.get('lifecycle'),'current_job':idle.get('current_job'),'pulse_seq':idle.get('pulse_seq')}
                result['native_serial']=repo.collection('intelligence_jobs').count_documents({'state':{'$in':['RUNNING','VALIDATING','PUBLISHING']}})==0
            if agent and agent.actor:
                result['telemetry_metrics']=dict(agent.actor.metrics);result['latencies']=list(agent.actor.latencies)
                result['instance_ref']=digest(agent.actor.instance_id);result['agent_errors']=dict(agent.errors)
            if agent:result['agent_errors']=dict(agent.errors)
    finally:
        worker.close()
        if worker.thread:worker.thread.join(timeout=5)
        monitor_stop.set();gc.collect()
    slot=db[COLLECTION].find_one({'_id':SLOT}) or {};c=slot.get('current') or {}
    result['shutdown_lifecycle']=c.get('lifecycle') if agent else 'NO_TELEMETRY'
    result['worker_thread_ended']=not worker.thread.is_alive();save();mongo.close()


if __name__=='__main__':main()
