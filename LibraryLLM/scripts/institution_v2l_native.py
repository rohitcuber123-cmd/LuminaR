"""Integrated native lifecycle, fenced restart, security and paired actual-model runs."""
import json,os,subprocess,sys,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.institution_v2l_fixture import AuthMongo,provision,seed_database,provision_unauthorized
from backend.services.library_worker_telemetry import COLLECTION,SLOT,digest
from backend.services.library_worker_diagnostics import inspect_telemetry,classify
from backend.services.library_operator_access import connect_operator
from pymongo import MongoClient
from pymongo.errors import OperationFailure


def main():
    result={'qualification':'NATIVE_INTEGRATED_IN_AUTHENTICATED_FIXTURES; PRODUCTION_DISABLED',
        'cases':[],'crashes':[],'production_enabled':False,'process_verification':'NOT_AVAILABLE',
        'scope':'Actual native resident class and real cached MiniLM/FAISS/KG, existing JWT build router. No full global engine/backend-main deployment process or OS verification.'}
    out=ROOT/'reports/institution_v2l_native_validation.json'
    def save():out.write_text(json.dumps(result,indent=2,default=str),encoding='utf8')
    with AuthMongo() as s:
        seed_database(s);provision(s);provision_unauthorized(s)
        base={**os.environ,'LUMINAR_V2L_ISOLATED_CHILD':'1','MONGO_URI':s.writer_uri,'MONGO_DB_NAME':s.database,
            'LIBRARY_INTELLIGENCE_ROOT':str(s.artifact_root),'V2L_TELEMETRY_URI':s.telemetry_uri,'V2L_READER_URI':s.reader_uri}
        def child(name,scenario,*args,expected=0,extra=None):
            path=ROOT/f'reports/institution_v2l_native_{name}.json';at=time.perf_counter()
            with path.with_suffix('.log').open('w',encoding='utf8') as f:
                p=subprocess.run([sys.executable,str(ROOT/'scripts/institution_v2l_native_child.py'),'--scenario',scenario,'--output',str(path),*args],
                    env={**base,**(extra or {})},cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=240)
            result['cases'].append({'name':name,'exit':p.returncode,'expected':expected,'seconds':time.perf_counter()-at,'evidence':path.name});save()
            assert p.returncode==expected,result['cases'][-1]
            return json.loads(path.read_text(encoding='utf8'))
        life=child('lifecycle','success','--enabled');result['idle']=life['idle'];result['return_to_idle']=life['return_to_idle']
        assert life['return_to_idle']['lifecycle']=='IDLE' and life['observer_thread_ended']
        lib=life['builds'][0]['library_id'];result['cli']=[]
        for fmt in ['json','text']:
            p=subprocess.run([sys.executable,str(ROOT/'scripts/diagnose_worker_telemetry.py'),'--database',s.database,'--library-id',lib,'--format',fmt],
                env={**os.environ,'LUMINAR_OPERATOR_MONGO_URI':s.reader_uri},capture_output=True,text=True,timeout=10)
            result['cli'].append({'format':fmt,'exit':p.returncode,'bytes':len(p.stdout.encode()),'output':p.stdout.strip()});assert p.returncode==0
        c=MongoClient(s.reader_uri)
        try:
            try:c[s.database][COLLECTION].update_one({'_id':SLOT},{'$set':{'epoch':99}})
            except OperationFailure as e:result['operator_write_denied_code']=e.code
        finally:c.close()
        assert result.get('operator_write_denied_code')==13
        for label,flags,env in [('frozen_before',[],{'LUMINAR_V2L_BASELINE_NATIVE':'1'}),('integrated_disabled',[],{}),('integrated_enabled',['--enabled'],{})]:
            child(label,'benchmark',*flags,extra={**env,'LUMINAR_V2L_BENCH_REPETITIONS':'3'})
        child('invalid_writer','benchmark','--enabled','--bad-writer')
        for name,target,fault in [('idle','KNOWLEDGE_GRAPH','IDLE'),('embedding','SEARCH_INDEX','EMBEDDING_BATCH'),
             ('kg','KNOWLEDGE_GRAPH','KG_NODES'),('validation','KNOWLEDGE_GRAPH','VALIDATION'),
             ('before_publication','KNOWLEDGE_GRAPH','SERIALIZATION_ACK'),('during_publication','KNOWLEDGE_GRAPH','PUBLISH'),
             ('after_pointer_before_ack','KNOWLEDGE_GRAPH','ACKNOWLEDGEMENT_LOSS')]:
            value=child('crash_'+name,'crash','--enabled','--target',target,'--fault',fault,expected=77)
            slot=s.db[COLLECTION].find_one({'_id':SLOT});j=value.get('crash_job')
            before=s.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']}) if j else None
            pointer=s.db.institution_intelligence_targets.find_one({'library_id':j['library_id'],'target':target}) if j else None
            restart=child('restart_'+name,'restart','--enabled')
            after=s.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']}) if j else None
            after_pointer=s.db.institution_intelligence_targets.find_one({'library_id':j['library_id'],'target':target}) if j else None
            result['crashes'].append({'name':name,'genuine_exit':77,'job_unchanged':digest(before)==digest(after),'pointer_unchanged':digest(pointer)==digest(after_pointer),
                'new_instance':value['instance_ref']!=restart['instance_ref'],'stale_with_explicit_logical_31s_observer':classify(slot,datetime.now(timezone.utc)+timedelta(seconds=31))['classification'],
                'job_state':before['state'] if before else None,'published_before_ack':bool(pointer and pointer.get('published_by_job_id')==j['job_id'])})
            assert digest(before)==digest(after) and digest(pointer)==digest(after_pointer);save()
        result['fixture_removed']='Only owned Mongo/temporary artifacts are shut down/removed by fixture ownership guard.';save()
    print(json.dumps({'cases':len(result['cases']),'genuine_crashes':len(result['crashes']),'operator_write_denied':result['operator_write_denied_code']}))


if __name__=='__main__':main()
