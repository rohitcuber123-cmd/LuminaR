"""Execute actual native worker children against one owned authenticated mongod."""
import json,os,subprocess,sys,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.institution_v2k_fixture import AuthMongo,provision,seed_database
from scratch.institution_v2k_telemetry.telemetry import COLLECTION,SLOT,digest
from scratch.institution_v2k_telemetry.observer import classify,inspect_telemetry
from backend.services.library_operator_access import connect_operator
from pymongo import MongoClient
from pymongo.errors import OperationFailure


def main():
    report={'qualification':'ISOLATED_PROTOTYPE_ONLY','cases':[],'real_process_crashes':[],
            'production_enabled':False,'limitations':['No deployment OS/supervisor proof.','Native adapter is confined process-global instrumentation, not an integration seam.']}
    out=ROOT/'reports/institution_v2k_native_validation.json'
    def save():out.write_text(json.dumps(report,indent=2,default=str),encoding='utf8')
    with AuthMongo() as s:
        seed_database(s);provision(s)
        env={**os.environ,'LUMINAR_V2K_ISOLATED_CHILD':'1','MONGO_URI':s.writer_uri,'MONGO_DB_NAME':s.database,
             'LIBRARY_INTELLIGENCE_ROOT':str(s.artifact_root),'V2K_TELEMETRY_URI':s.telemetry_uri,'V2K_READER_URI':s.reader_uri}
        def child(name,scenario,*args,expected=0):
            path=ROOT/f'reports/institution_v2k_native_{name}.json';log=path.with_suffix('.log')
            at=time.perf_counter()
            with log.open('w',encoding='utf8') as f:
                p=subprocess.run([sys.executable,str(ROOT/'scripts/institution_v2k_native_child.py'),'--scenario',scenario,'--output',str(path),*args],env=env,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=180)
            value=json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
            case={'name':name,'exit':p.returncode,'expected_exit':expected,'seconds':time.perf_counter()-at,'evidence':path.name}
            report['cases'].append(case);save()
            assert p.returncode==expected,case
            return value
        success=child('lifecycle','success','--enabled')
        report['idle']=success.get('idle');report['actual_search_and_kg']=success.get('builds')
        lib=success['builds'][0]['library_id'];r=connect_operator(s.reader_uri,s.database)
        try:report['authenticated_operator_observation']=inspect_telemetry(r,lib)
        finally:r.close()
        cli_env={**os.environ,'LUMINAR_OPERATOR_MONGO_URI':s.reader_uri}
        report['cli']=[]
        for fmt in ['json','text']:
            p=subprocess.run([sys.executable,str(ROOT/'scripts/diagnose_institution_v2k_prototype.py'),'--database',s.database,'--library-id',lib,'--format',fmt],env=cli_env,capture_output=True,text=True,timeout=10)
            report['cli'].append({'format':fmt,'exit':p.returncode,'bytes':len(p.stdout.encode()),'output':p.stdout.strip()})
            assert p.returncode==0
        c=MongoClient(s.reader_uri)
        try:
            try:c[s.database][COLLECTION].update_one({'_id':SLOT},{'$set':{'epoch':999}})
            except OperationFailure as e:report['operator_write_denied_code']=e.code
        finally:c.close()
        assert report.get('operator_write_denied_code')==13
        for enabled in [False,True]:child('paired_'+str(enabled).lower(),'benchmark',*(['--enabled'] if enabled else []))
        child('bad_writer','benchmark','--enabled','--bad-writer')
        for name,target,fault in [('embedding','SEARCH_INDEX','EMBEDDING_BATCH'),('kg','KNOWLEDGE_GRAPH','KG_NODES'),
                                  ('validation','KNOWLEDGE_GRAPH','VALIDATION'),('before_publication','KNOWLEDGE_GRAPH','SERIALIZATION_ACK'),
                                  ('during_publication','KNOWLEDGE_GRAPH','PUBLISH'),('after_pointer_before_ack','KNOWLEDGE_GRAPH','ACKNOWLEDGEMENT_LOSS')]:
            value=child('crash_'+name,'crash','--enabled','--target',target,'--fault',fault,expected=77)
            j=value['crash_job'];before=s.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']})
            pointer=s.db.institution_intelligence_targets.find_one({'library_id':j['library_id'],'target':target})
            slot=s.db[COLLECTION].find_one({'_id':SLOT})
            restart=child('restart_'+name,'restart','--enabled')
            after=s.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']})
            after_pointer=s.db.institution_intelligence_targets.find_one({'library_id':j['library_id'],'target':target})
            report['real_process_crashes'].append({'name':name,'fault':fault,'target':target,'job_state_before_restart':before['state'],
                'job_unchanged_by_restart':digest(before)==digest(after),'pointer_unchanged_by_restart':digest(pointer)==digest(after_pointer),
                'published_pointer_matches_crashed_job':pointer.get('published_by_job_id')==j['job_id'],
                'new_instance':restart.get('instance_ref')!=value.get('instance_ref'),
                'stale_after_31s_logical_observation':classify(slot,datetime.now(timezone.utc)+timedelta(seconds=31))['classification'],
                'qualification':'Actual os._exit(77); stale threshold evaluated with explicit future observer time, not a 31-second wall wait. Native lease was not shortened or recovered.'})
            assert digest(before)==digest(after) and digest(pointer)==digest(after_pointer)
            save()
        report['fixture_database_and_artifacts']='Owned mongod shutdown and TemporaryDirectory cleanup only; production untouched.'
        save()
    print(json.dumps({'native_cases':len(report['cases']),'genuine_crashes':len(report['real_process_crashes']),'operator_write_denied':report['operator_write_denied_code']}))


if __name__=='__main__':main()
