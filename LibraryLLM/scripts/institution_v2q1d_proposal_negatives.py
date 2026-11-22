from pathlib import Path
import json,httpx,time,hashlib
R=Path(__file__).resolve().parents[1];S=R/'.scratch/institution-v2q/final-continuation/lab';cfg=json.loads((S/'configuration.json').read_text());m=json.loads((S/'manifest.json').read_text());rows=[]
with httpx.Client(base_url='http://127.0.0.1:18005',timeout=180) as c:
 r=c.post('/auth/login',json={'email':'owner@q1d.example.com','password':cfg['password']});r.raise_for_status();h={'Authorization':'Bearer '+r.json()['access_token']}
 for label,lib,query in [('A_MISSING_FIELD',m['libraries'][0],'What is the maximum operating temperature?'),('B_MISSING_FIELD',m['libraries'][1],'What is the maximum operating temperature?'),('B_FALSE_PREMISE',m['libraries'][1],'Explain why the calibration code is ALPHA-SEVEN.')]:
  start=time.perf_counter();r=c.post(f"/libraries/{lib['library_id']}/assets/{lib['assets'][0]['asset_id']}/rag",headers=h,json={'query':query});b=r.json()
  row={'case':label,'proposal_not_applied':True,'http':r.status_code,'verdict':b.get('verdict'),'sources':len(b.get('sources',[])),'elapsed_ms':round((time.perf_counter()-start)*1000,3),'answer_sha256':hashlib.sha256(str(b.get('answer')).encode()).hexdigest(),'pass':r.status_code==200 and b.get('verdict')=='NOT_SUPPORTED' and not b.get('sources')};rows.append(row);(R/'reports/institution_v2q1d_proposal_negatives.json').write_text(json.dumps(rows,indent=2));print(label,row['pass'],flush=True)
