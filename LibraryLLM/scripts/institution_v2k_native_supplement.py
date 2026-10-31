"""Additional actual last-good, A/B/C queue, idle crash and explicit recovery experiments."""
import hashlib,json,os,subprocess,sys,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.institution_v2k_fixture import AuthMongo,provision,seed_database
from scratch.institution_v2k_telemetry.telemetry import COLLECTION,SLOT,digest
from scratch.institution_v2k_telemetry.observer import classify,inspect_telemetry
from backend.services.library_operator_access import connect_operator


def main():
    result={'qualification':'Actual native child experiments in authenticated disposable DB only.','cases':[],'recovery':[]}
    report=ROOT/'reports/institution_v2k_native_supplement.json'
    def save():report.write_text(json.dumps(result,indent=2,default=str),encoding='utf8')
    with AuthMongo() as s:
        seed_database(s);provision(s)
        env={**os.environ,'LUMINAR_V2K_ISOLATED_CHILD':'1','MONGO_URI':s.writer_uri,'MONGO_DB_NAME':s.database,
             'LIBRARY_INTELLIGENCE_ROOT':str(s.artifact_root),'V2K_TELEMETRY_URI':s.telemetry_uri,'V2K_READER_URI':s.reader_uri}
        def child(name,scenario,*args,expected=0):
            path=ROOT/f'reports/institution_v2k_native_supplement_{name}.json';log=path.with_suffix('.log');at=time.perf_counter()
            with log.open('w',encoding='utf8') as f:
                p=subprocess.run([sys.executable,str(ROOT/'scripts/institution_v2k_native_child.py'),'--scenario',scenario,'--output',str(path),*args],env=env,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=180)
            result['cases'].append({'name':name,'exit':p.returncode,'expected':expected,'seconds':time.perf_counter()-at,'evidence':path.name});save()
            assert p.returncode==expected,result['cases'][-1]
            return json.loads(path.read_text(encoding='utf8'))
        lifecycle=child('return_idle','success','--enabled');result['return_to_idle']=lifecycle['return_to_idle'];assert lifecycle['return_to_idle']['lifecycle']=='IDLE'
        crashed=child('idle_crash','crash','--enabled','--target','KNOWLEDGE_GRAPH','--fault','IDLE',expected=77)
        slot=s.db[COLLECTION].find_one({'_id':SLOT});restart=child('idle_restart','restart','--enabled')
        result['idle_crash']={'genuine_exit':77,'new_instance':crashed['instance_ref']!=restart['instance_ref'],
             'stale_with_logical_31s_observer':classify(slot,datetime.now(timezone.utc)+timedelta(seconds=31))['classification']}
        for name,fault,multi in [('last_good_before_pointer','VALIDATION',False),('abc_after_pointer','ACKNOWLEDGEMENT_LOSS',True)]:
            crash=child(name,'crash','--enabled','--target','KNOWLEDGE_GRAPH','--fault',fault,'--seed-last-good',*(['--queued-c'] if multi else []),expected=77)
            j=crash['crash_job'];before=s.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']})
            c=crash.get('library_c_queued');before_c=s.db.institution_intelligence_jobs.find_one({'job_id':c['job_id']})['state'] if c else None
            restart=child(name+'_restart','restart','--enabled',*(['--drain-queued'] if multi else []))
            after=s.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']})
            prior_retained=all(Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in crash['last_good']['files'].items())
            # Explicit fixture-only expiry injection; native constants and production lease data remain untouched.
            s.db.institution_intelligence_jobs.update_one({'job_id':j['job_id']},{'$set':{'lease_expires_at':datetime.now(timezone.utc)-timedelta(seconds=1)}})
            recovered=child(name+'_explicit_recovery','recover','--recovery-library',j['library_id'],'--recovery-job',j['job_id'])
            recovered_state=recovered['recovered_job']['state'];expected='SUCCEEDED' if fault=='ACKNOWLEDGEMENT_LOSS' else 'FAILED'
            assert recovered_state==expected and prior_retained and digest(before)==digest(after)
            case={'case':name,'before_restart':before['state'],'old_job_unchanged_by_restart':digest(before)==digest(after),
                  'last_good_bytes_retained':prior_retained,'explicit_native_recovery_http':recovered['explicit_native_recovery_http'],
                  'explicit_native_recovered_state':recovered_state,'lease_expiry':'Injected only into this disposable native job after restart; source lease90s/renewal10s unchanged.'}
            if c:
                after_c=s.db.institution_intelligence_jobs.find_one({'job_id':c['job_id']})['state']
                case.update(library_a=crash['library_a_search'],library_b=j['library_id'],library_c=c,library_c_before=before_c,library_c_after_restart=after_c)
                assert before_c=='QUEUED' and after_c=='SUCCEEDED'
                reader=connect_operator(s.reader_uri,s.database)
                try:
                    va=inspect_telemetry(reader,crash['library_a_search']['library_id']);vc=inspect_telemetry(reader,c['library_id'])
                finally:reader.close()
                case['no_cross_library_output']=j['library_id'] not in json.dumps(va) and j['library_id'] not in json.dumps(vc)
                assert case['no_cross_library_output']
            result['recovery'].append(case);save()
    result['owned_fixture_removed']=True;save();print(json.dumps({'supplement_cases':len(result['cases']),'explicit_recovery':len(result['recovery'])}))


if __name__=='__main__':main()
