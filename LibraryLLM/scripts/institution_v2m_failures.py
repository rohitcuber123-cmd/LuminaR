"""Fresh2M native failure/restart/manual-recovery evidence, disposable auth-enabled Mongo only."""
from datetime import datetime,timedelta,timezone
import json,os,socket,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.institution_v2m_fixture import AuthMongo,provision,seed_database
from backend.services.library_worker_observer import Configuration,RestrictedWriter
from backend.services.library_worker_telemetry import COLLECTION,SLOT,digest
from backend.services.library_worker_diagnostics import classify


def main():
    report={'scope':'Fresh authenticated2M disposable native crash/failure experiments; no production faults.', 'cases':[],'crashes':[],
        'limits':'One cached encoder per owned native process; no monitoring process/model added to production. Logical future observation used for stale threshold, not wall-clock31s wait.'}
    out=ROOT/'reports/institution_v2m_native_failures.json'
    def save():out.write_text(json.dumps(report,indent=2,default=str),encoding='utf8')
    with AuthMongo() as s:
        seed_database(s);provision(s)
        base={**os.environ,'LUMINAR_V2M_ISOLATED_CHILD':'1','MONGO_URI':s.writer_uri,'MONGO_DB_NAME':s.database,
            'LIBRARY_INTELLIGENCE_ROOT':str(s.artifact_root),'V2M_TELEMETRY_URI':s.telemetry_uri,'LUMINAR_V2M_BOOK_COUNT':'151'}
        for key in ['LUMINAR_V2M_BASELINE_NATIVE','LUMINAR_V2M_OBSERVER_CRASH']:base.pop(key,None)
        def child(name,scenario,*args,expected=0,extra=None):
            path=ROOT/f'reports/institution_v2m_failure_{name}.json';at=time.perf_counter()
            with path.with_suffix('.log').open('w',encoding='utf8') as f:
                p=subprocess.run([sys.executable,str(ROOT/'scripts/institution_v2m_native_child.py'),'--scenario',scenario,'--output',str(path),*args],
                    env={**base,**(extra or {})},cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=240)
            report['cases'].append({'case':name,'scenario':scenario,'exit':p.returncode,'expected':expected,'seconds':time.perf_counter()-at,'evidence':path.name});save()
            assert p.returncode==expected,'Owned native fault case failed; inspect its2M log'
            return json.loads(path.read_text(encoding='utf8'))
        for mode in ['permission','timeout']:
            value=child('aux_'+mode,'benchmark','--enabled','--telemetry-fault',mode)
            assert sum(value['agent_errors'].values())>0 and all(b['state']=='SUCCEEDED' and b['pointer_ack_match'] for b in value['builds'])
        value=child('observer_exception','benchmark','--enabled',extra={'LUMINAR_V2M_OBSERVER_CRASH':'1'})
        assert value['agent_errors']['OBSERVER_LOOP_UNAVAILABLE']==1 and all(b['state']=='SUCCEEDED' and b['pointer_ack_match'] for b in value['builds'])
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));unused=sock.getsockname()[1]
        from pymongo.uri_parser import parse_uri
        # Preserve secret solely in child environment; never argv/log/report values.
        offline=s.telemetry_uri.replace(':'+str(s.port)+'/',':'+str(unused)+'/')
        value=child('connection_failure','benchmark','--enabled',extra={'V2M_TELEMETRY_URI':offline})
        assert value['agent_errors'].get('TELEMETRY_UNAVAILABLE')==1 and all(b['state']=='SUCCEEDED' and b['pointer_ack_match'] for b in value['builds'])
        for name,target,stage in [('embedding','SEARCH_INDEX','EMBEDDING_BATCH'),('kg','KNOWLEDGE_GRAPH','KG_NODES'),
             ('before_publication','KNOWLEDGE_GRAPH','SERIALIZATION_ACK'),('after_pointer','KNOWLEDGE_GRAPH','ACKNOWLEDGEMENT_LOSS')]:
            value=child('crash_'+name,'crash','--enabled','--target',target,'--fault',stage,expected=77)
            j=value['crash_job'];before=s.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']})
            pointer=s.db.institution_intelligence_targets.find_one({'library_id':j['library_id'],'target':target});slot=s.db[COLLECTION].find_one({'_id':SLOT})
            restarted=child('restart_'+name,'restart','--enabled')
            after=s.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']});after_pointer=s.db.institution_intelligence_targets.find_one({'library_id':j['library_id'],'target':target})
            assert digest(before)==digest(after) and digest(pointer)==digest(after_pointer)
            case={'name':name,'stage_hook':stage,'genuine_process_exit':77,'job_unchanged_by_restart':True,'pointer_unchanged_by_restart':True,
                'state_before_restart':before['state'],'fresh_instance':value['instance_ref']!=restarted['instance_ref'],
                'stale_with_logical_now_plus31s':classify(slot,datetime.now(timezone.utc)+timedelta(seconds=31))['classification']}
            if name in ['before_publication','after_pointer']:
                s.db.institution_intelligence_jobs.update_one({'job_id':j['job_id']},{'$set':{'lease_expires_at':datetime.now(timezone.utc)-timedelta(seconds=1)}})
                recovered=child('manual_recover_'+name,'recover','--recovery-library',j['library_id'],'--recovery-job',j['job_id'])
                expected_state='SUCCEEDED' if name=='after_pointer' else 'FAILED'
                assert recovered['explicit_native_recovery_http']==200 and recovered['recovered_job']['state']==expected_state
                case['explicit_manual_recovery']={'http':200,'state':expected_state,'lease_expiry':'Injected only into this disposable native job after unchanged restart proof; native90s constant untouched.'}
            report['crashes'].append(case);save()
        before=digest(list(s.db.institution_intelligence_jobs.find({})))
        a=RestrictedWriter(Configuration(s.database,s.telemetry_uri),'tenant-'+str(uuid4()));a.start()
        b=RestrictedWriter(Configuration(s.database,s.telemetry_uri),'tenant-'+str(uuid4()));b.start()
        try:
            assert not a.pulse()
            s.db[COLLECTION].update_one({'_id':SLOT},{'$set':{'current.last_seen_at':datetime.now(timezone.utc)+timedelta(days=1)}})
            b.pulse();assert classify(s.db[COLLECTION].find_one({'_id':SLOT}),datetime.now(timezone.utc))['classification']=='UNKNOWN'
            assert before==digest(list(s.db.institution_intelligence_jobs.find({})))
            report['late_instance_and_clock']={'old_pulse_rejected':True,'rollback_bit_sticky':True,'classification':'UNKNOWN','native_jobs_unchanged':True}
        finally:a.close();b.close()
        save()
    report['owned_fixture_removed']=True;save();print(json.dumps({'native_crashes':len(report['crashes']),'cases':len(report['cases']),'no_automatic_action':True}))


if __name__=='__main__':main()
