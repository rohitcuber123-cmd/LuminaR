"""Measure the unchanged storage contract at retention capacity; synthetic accepted job tuples only."""
from datetime import datetime,timedelta,timezone
import json,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.institution_v2m_fixture import AuthMongo,provision,seed_database
from backend.services.library_worker_observer import RestrictedWriter,Configuration
from backend.services.library_worker_telemetry import COLLECTION,SLOT
from bson import BSON


def main():
    result={'scope':'Retention capacity measurement using explicit fixture-admin seeded accepted tuples; not a real model build or production workload.', 'samples':[]}
    with AuthMongo() as s:
        seed_database(s);provision(s)
        actors=[]
        try:
            for generation in range(2):
                a=RestrictedWriter(Configuration(s.database,s.telemetry_uri),'tenant-'+str(uuid4()));actors.append(a);a.start()
                for i in range(8 if generation==0 else 64):
                    j={'job_id':str(uuid4()),'library_id':str(uuid4()),'target':'SEARCH_INDEX','worker_id':a.owner,'fence_token':str(uuid4()),
                        'state':'RUNNING','stage':'EMBEDDING','progress_current':i,'progress_total':151,'effective_active':True,
                        'lease_expires_at':datetime.now(timezone.utc)+timedelta(minutes=5)}
                    s.db.institution_intelligence_jobs.insert_one(j);assert a.observe(j)
                    if i in [0,7,15,31,63]:
                        row=s.db[COLLECTION].find_one({'_id':SLOT})
                        result['samples'].append({'epoch':row['epoch'],'observations_in_epoch':i+1,'BSON_bytes':len(BSON.encode(row)),
                            'current_entries':len(row['current']['progress']),'previous_entries':len((row.get('previous') or {}).get('progress',[])),
                            'document_count':s.db[COLLECTION].count_documents({})})
                if generation==0:a.close()
            assert all(v['BSON_bytes']<=16384 and v['document_count']==1 for v in result['samples'])
            full=[v for v in result['samples'] if v['current_entries']==v['previous_entries']==8]
            assert full and max(v['BSON_bytes'] for v in full)==min(v['BSON_bytes'] for v in full)
            result['capacity_BSON_bytes']=full[-1]['BSON_bytes'];result['stable_after_eviction']=True
        finally:
            for a in actors:a.close()
    result['owned_fixture_removed']=True
    (ROOT/'reports/institution_v2m_storage_measurement.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({'capacity_BSON_bytes':result['capacity_BSON_bytes'],'single_document':True,'stable_after_eviction':True}))


if __name__=='__main__':main()
