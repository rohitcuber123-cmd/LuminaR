"""Real Qwen on synthetic private assets; persist no private prompt/answer text."""
from pathlib import Path
import httpx,json,time,hashlib
R=Path(__file__).resolve().parents[1];S=R/'.scratch/institution-v2q/continuation/lab'
def main():
 out=R/'reports/institution_v2q1c_private_qwen.json';assert not out.exists()
 cfg=json.loads((S/'configuration.json').read_text());m=json.loads((S/'manifest.json').read_text());rows=[]
 with httpx.Client(base_url='http://127.0.0.1:18005',timeout=180) as c:
  tokens={}
  for label in ['owner','outsider']:
   r=c.post('/auth/login',json={'email':label+'@q1c.example.com','password':cfg['password']});r.raise_for_status();tokens[label]=r.json()['access_token']
  for lib in m['libraries'][:2]:
   asset=lib['assets'][0];path=f"/libraries/{lib['library_id']}/assets/{asset['asset_id']}/rag"
   for label in ['outsider','owner']:
    start=time.perf_counter();r=c.post(path,headers={'Authorization':'Bearer '+tokens[label]},json={'query':'What calibration code is recorded?'});b=r.json();answer=str(b.get('answer',''));expected='ALPHA' if lib['alias']=='A' else 'BRAVO'
    row={'library':lib['alias'],'user':label,'http':r.status_code,'elapsed_ms':round((time.perf_counter()-start)*1000,3),'verdict':b.get('verdict'),'expected_synthetic_fact_present':expected in answer.upper(),'answer_sha256':hashlib.sha256(answer.encode()).hexdigest(),'source_count':len(b.get('sources',[])),'pass':r.status_code==404 if label=='outsider' else r.status_code==200 and expected in answer.upper()}
    rows.append(row);out.write_text(json.dumps(rows,indent=2));print(lib['alias'],label,row['pass'],flush=True)
if __name__=='__main__':main()
