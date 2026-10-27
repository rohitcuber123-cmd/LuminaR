"""Local explicit-owner TEST build receipt; no credentials/tokens are persisted."""
from pathlib import Path
import json,sys,time,requests
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.full_product_browser_session import credentials
from backend.database.mongodb import db
TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
def main():
    assert db.name=='luminar_library' and db.client.address[0] in ('localhost','127.0.0.1','::1')
    owner=db.institution_memberships.find_one({'library_id':TEST,'user_id':4,'status':'ACTIVE'})
    assert owner and owner['role']=='ADMIN'
    email,password=credentials('staff');login=requests.post('http://127.0.0.1:8002/auth/login',json={'email':email,'password':password},timeout=30);assert login.ok
    headers={'Authorization':'Bearer '+login.json()['access_token']};base=f'http://127.0.0.1:8002/libraries/{TEST}/intelligence'
    jobs=[];started=time.perf_counter()
    for target in ['SEARCH_INDEX','KNOWLEDGE_GRAPH']:
        response=requests.post(base+'/builds',headers=headers,json={'target':target},timeout=30);assert response.status_code==202,response.text
        job=response.json();jobs.append(job)
        print('QUEUED',target,job['job_id'],flush=True)
    deadline=time.monotonic()+900
    while time.monotonic()<deadline:
        values=[]
        for job in jobs:
            response=requests.get(base+'/jobs/'+job['job_id'],headers=headers,timeout=30)
            if response.status_code==503:continue
            assert response.ok,response.text;values.append(response.json())
        if len(values)==2 and all(v['state'] in ['SUCCEEDED','FAILED','RECOVERY_REQUIRED'] for v in values):break
        time.sleep(1)
    assert len(values)==2 and all(v['state']=='SUCCEEDED' for v in values),[(v['target'],v['state'],v.get('error_code')) for v in values]
    status=requests.get(base,headers=headers,timeout=60).json()
    assert status['search']['status']==status['kg']['status']=='READY' and status['search']['record_count']==150
    result={'status':'PASS','library_id':TEST,'authority':'Active ADMIN LibraryMembership, account 4; normal local login.','jobs':values,'intelligence':status,'elapsed_seconds':time.perf_counter()-started}
    (ROOT/'reports/institution_v2g_build_jobs.json').write_text(json.dumps(result,indent=2,default=str),encoding='utf8')
    print('PASS real TEST Search and KG',status['search']['record_count'],flush=True)
if __name__=='__main__':main()
