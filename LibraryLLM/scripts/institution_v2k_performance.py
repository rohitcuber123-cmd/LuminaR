"""Paired bounded authenticated diagnostic overhead; disposable indexed history only."""
from datetime import datetime,timedelta,timezone
import json,os,statistics,sys,time
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bson import BSON
from scripts.institution_v2k_fixture import AuthMongo,provision,seed_database
from scratch.institution_v2k_telemetry.telemetry import Actor,COLLECTION,SLOT
from scratch.institution_v2k_telemetry.observer import inspect_telemetry
from backend.services.library_operator_access import connect_operator,COLLECTIONS
from backend.services.library_intelligence_diagnostics import inspect


def stats(values):
    if not values:return None
    v=sorted(values);return {'median':statistics.median(v),'p95':v[min(len(v)-1,int(len(v)*.95))],'min':v[0],'max':v[-1],'samples':len(v)}


def instrument_explain(reader,server):
    """Admin measures plans for the exact bounded reader queries; never changes their execution."""
    captured=[];rows,aggregate=reader.rows,reader.aggregate
    def explain(command):
        plan=server.db.command('explain',command,verbosity='executionStats')
        stats=([plan['executionStats']] if 'executionStats' in plan else
               [s['$cursor']['executionStats'] for s in plan.get('stages',[]) if '$cursor' in s and 'executionStats' in s['$cursor']])
        captured.append({'operation':next(iter(command)),'collection':command[next(iter(command))],
            'documents_examined':sum(s.get('totalDocsExamined',0) for s in stats),
            'keys_examined':sum(s.get('totalKeysExamined',0) for s in stats)})
    def traced_rows(name,query,projection,**kw):
        cmd={'find':COLLECTIONS[name],'filter':query,'projection':projection,'limit':kw.get('limit',1)}
        if kw.get('sort'):cmd['sort']=dict(kw['sort'])
        if kw.get('hint'):cmd['hint']=kw['hint']
        explain(cmd);return rows(name,query,projection,**kw)
    def traced_aggregate(name,pipeline):
        explain({'aggregate':COLLECTIONS[name],'pipeline':pipeline,'cursor':{}});return aggregate(name,pipeline)
    reader.rows,reader.aggregate=traced_rows,traced_aggregate
    return captured


def main():
    out={'qualification':'Disposable local auth-enabled mongod; no production SLO claim.','scenarios':[],
         'before':'Unchanged Part 2J full bounded inspection.','after':'Same Part 2J inspection plus fixture telemetry supplement.',
         'cpu_memory_limit':'In-process diagnostics time.process_time and RSS delta; resident native child idle/build pairs recorded separately.'}
    import psutil
    proc=psutil.Process()
    with AuthMongo() as s:
        seed_database(s);provision(s);lib=str(uuid4());owner='tenant-'+str(uuid4())
        a=Actor(s.telemetry_uri,s.database,owner);a.start()
        for label,count,state in [('empty',0,'SUCCEEDED'),('one_queued',1,'QUEUED'),('one_active',1,'RUNNING'),
                                  ('history_10',10,'SUCCEEDED'),('history_100',100,'SUCCEEDED'),('history_1000',1000,'SUCCEEDED')]:
            s.db.institution_intelligence_jobs.delete_many({})
            now=datetime.now(timezone.utc);rows=[]
            for i in range(count):rows.append({'job_id':str(uuid4()),'library_id':lib,'target':'SEARCH_INDEX','state':state,
                 'stage':'EMBEDDING' if state=='RUNNING' else 'QUEUED' if state=='QUEUED' else 'COMPLETE',
                 'progress_current':0 if state!='SUCCEEDED' else 10,'progress_total':10,'created_at':now-timedelta(seconds=i),
                 'effective_active':state in ['QUEUED','RUNNING'],'fence_token':str(uuid4()),'worker_id':owner,
                 'heartbeat_at':now,'lease_expires_at':now+timedelta(seconds=90),'completed_at':now if state=='SUCCEEDED' else None})
            if rows:s.db.institution_intelligence_jobs.insert_many(rows)
            if state=='RUNNING':a.observe(rows[0]);a.pulse('ACTIVE',rows[0])
            else:a.pulse()
            result={'scenario':label,'history_count':count,'pairs':[]}
            for enabled in [False,True]:
                times=[];cpu=[];sizes=[];rss0=proc.memory_info().rss
                for _ in range(20):
                    reader=connect_operator(s.reader_uri,s.database,seconds=10)
                    try:
                        at=time.perf_counter();c0=time.process_time()
                        value=inspect(reader,lib,limit=20,artifact_root=s.artifact_root,artifact_limit=20)
                        if enabled:value={'native':value,'telemetry':inspect_telemetry(reader,lib)}
                        times.append((time.perf_counter()-at)*1000);cpu.append((time.process_time()-c0)*1000)
                        sizes.append(len(json.dumps(value,default=str).encode()))
                    finally:reader.close()
                result['pairs'].append({'telemetry_enabled':enabled,'read_ms':stats(times),'cpu_ms':stats(cpu),
                    'rss_delta_bytes':proc.memory_info().rss-rss0,'max_output_bytes':max(sizes)})
            # Explain outside latency sampling, using the actual frozen J reader call graph.
            reader=connect_operator(s.reader_uri,s.database)
            try:
                plans=instrument_explain(reader,s)
                inspect(reader,lib,limit=20,artifact_root=s.artifact_root,artifact_limit=20)
                inspect_telemetry(reader,lib)
                result['native_reader_query_plans']=plans
                result['native_reader_documents_examined']=sum(p['documents_examined'] for p in plans)
                result['plan_note']='Actual server explain executionStats, exact queries outside timed samples; telemetry singleton reads measured separately.'
            finally:reader.close()
            explain=s.db.command('explain',{'find':COLLECTION,'filter':{'_id':SLOT},'limit':1},verbosity='executionStats')['executionStats']
            result['auxiliary_documents_examined']=explain['totalDocsExamined'];result['auxiliary_keys_examined']=explain['totalKeysExamined']
            result['auxiliary_storage_bson_bytes']=len(BSON.encode(s.db[COLLECTION].find_one({'_id':SLOT})))
            result['auxiliary_document_count']=s.db[COLLECTION].count_documents({})
            out['scenarios'].append(result)
        # Measure actual writes at the candidate interval independently of stage polling.
        a.latencies=[]
        for _ in range(20):a.pulse()
        out['auxiliary_write_ms']=stats([v['ms'] for v in a.latencies if v['kind']=='pulse_write'])
        out['actor_metrics']=dict(a.metrics);a.close()
        out['retention']='One preallocated document; current + previous, max eight progress entries each, max16384 BSON bytes; no telemetry insert/delete grant.'
    (ROOT/'reports/institution_v2k_performance.json').write_text(json.dumps(out,indent=2),encoding='utf8')
    print(json.dumps({'scenarios':len(out['scenarios']),'paired_reads':240,'write_ms':out['auxiliary_write_ms']}))


if __name__=='__main__':main()
