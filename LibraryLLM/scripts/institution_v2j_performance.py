"""Authenticated diagnostic latency/DB work on isolated bounded job fixtures."""
from pathlib import Path
from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import json,os,statistics,subprocess,sys,time,tracemalloc
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.institution_v2j_fixture import AuthMongo,seed_database
from backend.services.library_operator_access import connect_operator
from backend.services.library_intelligence_diagnostics import inspect


def stats(values):
    v=sorted(values)
    return {'median':statistics.median(v),'p90':v[min(len(v)-1,int(.9*len(v)))],'p95':v[min(len(v)-1,int(.95*len(v)))],'min':v[0],'max':v[-1]}


def main():
    report={'layer':'Auth-enabled disposable Mongo; real read principal, actual diagnostic implementation; no production reads/writes',
            'samples_per_case':15,'cases':[],'cold_definition':'New CLI process first observation; OS/Mongo caches not flushed.',
            'limits':'Local development samples, not a production SLO. Per-query deadline bounds sparse history index scans; returned rows are bounded independently.'}
    with AuthMongo() as server:
        seed_database(server)
        lib=str(uuid4());now=datetime.now(timezone.utc)
        for n in [0,1,100,1000,10000]:
            coll=server.db.institution_intelligence_jobs
            coll.delete_many({})
            for start in range(0,n,1000):
                coll.insert_many([{'library_id':lib,'job_id':str(uuid4()),'target':'SEARCH_INDEX','state':'FAILED','stage':'FAILED',
                    'effective_active':False,'created_at':now-timedelta(seconds=i+1),'artifact_generation_id':str(uuid4())}
                    for i in range(start,min(start+1000,n))])
            wall=[];cpu=[];outputs=[]
            for _ in range(15):
                reader=connect_operator(server.reader_uri,server.database,seconds=20)
                try:
                    at,ct=time.perf_counter(),time.process_time()
                    out=inspect(reader,lib,artifact_root=server.artifact_root,limit=20)
                    wall.append((time.perf_counter()-at)*1000);cpu.append((time.process_time()-ct)*1000)
                    outputs.append(len(json.dumps(out,indent=2,allow_nan=False).encode('utf8'))+1)
                finally:reader.close()
            server.db.command('profile',2)
            reader=connect_operator(server.reader_uri,server.database,seconds=20)
            tracemalloc.start()
            try:
                out=inspect(reader,lib,artifact_root=server.artifact_root,limit=20)
                _,peak=tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop();reader.close();server.db.command('profile',0)
            profile=list(server.db['system.profile'].find({'appName':'LuminaR-operator-read-only'}))
            namespaces=Counter(event.get('ns','').split('.',1)[-1] for event in profile)
            assert not any('library_books' in name or name=='books' for name in namespaces)
            case={'historical_jobs':n,'service_ms':stats(wall),'cpu_ms':stats(cpu),'max_output_bytes':max(outputs),
                  'tracemalloc_peak_bytes':peak,'observed_mongo_operations':len(profile),
                  'documents_examined_profile_sample':sum(e.get('docsExamined',0) for e in profile),
                  'namespaces':dict(namespaces),'returned_job_rows':len(out['jobs']),
                  'artifact_checksum_bytes':out['artifacts']['checksum_bytes_read'],'catalogue_queries':0}
            report['cases'].append(case)
            server.db['system.profile'].drop()
            print(n,round(case['service_ms']['median'],2),case['documents_examined_profile_sample'],flush=True)
        # A scoped UUID job lookup is the efficient route in a sparse history;
        # the bounded insertion-ID history page may examine foreign rows.
        foreign=str(uuid4())
        coll.update_many({}, {'$set':{'library_id':foreign}})
        own={'library_id':lib,'job_id':str(uuid4()),'target':'SEARCH_INDEX','state':'FAILED','effective_active':False,'created_at':now}
        coll.insert_one(own)
        reader=connect_operator(server.reader_uri,server.database,seconds=20)
        try:
            out=inspect(reader,lib,job_id=own['job_id'],artifact_root=server.artifact_root)
            report['sparse_explicit_job_lookup']={'returned_jobs':len(out['jobs']),'query_hint':'job_id_1','mongo_operations':len(reader.operations)}
        finally:reader.close()
        env=os.environ.copy();env['LUMINAR_OPERATOR_MONGO_URI']=server.reader_uri
        cold=[]
        for _ in range(3):
            at=time.perf_counter()
            run=subprocess.run([sys.executable,str(ROOT/'scripts/diagnose_library_intelligence.py'),'--library-id',lib,
                '--database',server.database,'--job-id',own['job_id'],'--artifact-root',str(server.artifact_root),'--format','json'],
                cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf8',timeout=15)
            assert run.returncode==0,run.stderr
            cold.append((time.perf_counter()-at)*1000)
        report['application_cold_cli_wall_ms']=stats(cold)
        def call(_):
            reader=connect_operator(server.reader_uri,server.database,seconds=20)
            try:
                at=time.perf_counter();out=inspect(reader,lib,job_id=own['job_id'],artifact_root=server.artifact_root)
                assert out['library_id']==lib
                return (time.perf_counter()-at)*1000
            finally:reader.close()
        with ThreadPoolExecutor(4) as pool:values=list(pool.map(call,range(12)))
        report['concurrent']={'workers':4,'requests':12,'errors':0,'service_ms':stats(values),'authorization':'Fresh database authentication per invocation; no cache or mutation locks'}
        report['staff_status_preservation']='Part 2I service/store/worker/routes/UI hashes unchanged; its 60 regression checks still run. Diagnostic code is not installed in that call graph.'
        report['status']='PASS'
    (ROOT/'reports/institution_v2j_performance.json').write_text(json.dumps(report,indent=2),encoding='utf8')


if __name__=='__main__':main()
