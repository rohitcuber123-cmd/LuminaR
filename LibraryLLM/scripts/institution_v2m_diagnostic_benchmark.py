"""Protected-reader end-to-end CLI latency in an authenticated synthetic diagnostic fixture."""
from datetime import datetime,timedelta,timezone
import json,os,statistics,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.institution_v2m_fixture import AuthMongo,provision,seed_database
from scripts.institution_v2m_secrets import protect,command
from backend.services.library_worker_observer import Configuration,RestrictedWriter
from backend.services.library_worker_telemetry import COLLECTION,SLOT
from bson import BSON


def stats(v):
    v=sorted(v);return {'median':statistics.median(v),'p95':v[min(len(v)-1,int(.95*len(v)))],'samples':len(v),'min':v[0],'max':v[-1]}


def main():
    result={'scope':'Actual CLI/SCRAM/DPAPI startup/read/serialization timings; coherent synthetic native records, not an actual worker or serving artifact. No production SLO.', 'commands':[]}
    with AuthMongo() as s:
        seed_database(s);provision(s)
        path=s.root/'reader-benchmark/reader.clixml';result['secret_protection']=protect(s.root,path,s.reader_uri)
        owner='tenant-'+str(uuid4());w=RestrictedWriter(Configuration(s.database,s.telemetry_uri),owner);w.start()
        lib=str(uuid4());now=datetime.now(timezone.utc)
        job={'job_id':str(uuid4()),'library_id':lib,'target':'SEARCH_INDEX','worker_id':owner,'fence_token':str(uuid4()),'state':'RUNNING','stage':'EMBEDDING',
            'progress_current':1,'progress_total':151,'effective_active':True,'created_at':now,'started_at':now,'heartbeat_at':now,'lease_expires_at':now+timedelta(minutes=5),
            'artifact_generation_id':str(uuid4()),'requested_generation_id':str(uuid4())}
        s.db.institution_intelligence_jobs.insert_one(job);w.observe(job)
        try:
            for label,script in [('worker','diagnose_worker_telemetry.py'),('queue_artifacts','diagnose_library_intelligence.py')]:
                latencies=[];sizes=[]
                for _ in range(10):
                    w.pulse('ACTIVE',job)
                    payload={'fixture_root':str(s.root),'secret_path':str(path),'database':s.database,'python':sys.executable,
                        'script':str(ROOT/'scripts'/script),'library_id':lib,'format':'json'}
                    if label=='queue_artifacts':payload['artifact_root']=str(s.artifact_root)
                    at=time.perf_counter();p=subprocess.run(command('operator'),input=json.dumps(payload),cwd=ROOT,capture_output=True,text=True,timeout=20)
                    latencies.append((time.perf_counter()-at)*1000)
                    assert p.returncode==0,'Protected diagnostic benchmark invocation failed'
                    json.loads(p.stdout);sizes.append(len(p.stdout.encode()))
                    assert s.reader_uri not in p.stdout+p.stderr and s.read_password not in p.stdout+p.stderr
                result['commands'].append({'command':script,'end_to_end_ms':stats(latencies),'max_output_bytes':max(sizes),
                    'includes':'PowerShell process + DPAPI import + Python process/import + SCRAM + bounded reads + JSON serialization.'})
            result['telemetry_BSON_bytes']=len(BSON.encode(s.db[COLLECTION].find_one({'_id':SLOT})))
            plan=s.db.command('explain',{'find':COLLECTION,'filter':{'_id':SLOT},'limit':1},verbosity='executionStats')['executionStats']
            result['auxiliary_documents_examined']=plan['totalDocsExamined'];result['auxiliary_keys_examined']=plan['totalKeysExamined']
        finally:w.close()
    result['owned_fixture_removed']=True
    (ROOT/'reports/institution_v2m_diagnostic_benchmark.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({'actual_cli_calls':20,'commands':len(result['commands']),'owned_fixture_removed':True}))


if __name__=='__main__':main()
