from pathlib import Path
import json,httpx,hashlib
R=Path(__file__).resolve().parents[1];D=R/'reports';S=R/'.scratch/institution-v2q/final-continuation/lab'
cfg=json.loads((S/'configuration.json').read_text());m=json.loads((S/'manifest.json').read_text());rows=[]
with httpx.Client(base_url='http://127.0.0.1:18005',timeout=60) as c:
 r=c.post('/auth/login',json={'email':'member@q1d.example.com','password':cfg['password']});r.raise_for_status();h={'Authorization':'Bearer '+r.json()['access_token']}
 for lib in m['libraries'][:2]:
  r=c.post(f"/libraries/{lib['library_id']}/catalogue/recommendations",headers=h,json={'work_ids':[x['work_id'] for x in m['global_books']],'limit':10});b=r.json();books=b.get('results',[])
  rows.append({'case':'FOR_YOU_'+lib['alias'],'http':r.status_code,'pass':r.status_code==200 and len(books)>0 and all(x.get('library_id')==lib['library_id'] for x in books),'library':lib['alias'],'source':b.get('source'),'rows':[{'rank':i+1,'book_id':x.get('library_book_id') or x.get('work_id'),'metadata':{k:x.get(k) for k in ['title','authors','subjects','description','available_copies','total_copies']},'query':'Cold-start For You','requested_filters':'No availability-only filter','relevance_grade':None,'judge_identity':None,'judgment_rationale':None} for i,x in enumerate(books)]})
(D/'institution_v2q1d_recommendations.json').write_text(json.dumps({'cases':rows,'provider':'Controlled Global fixture candidates; actual unchanged tenant GLOBAL_INTERSECTION_AND_LOCAL_DISCOVERY service','independent_review':'UNASSIGNED; no metrics'},indent=2))
old=json.loads((D/'institution_v2q1d_security.json').read_text());cases=[x for x in old['cases'] if not x['case'].startswith('FOR_YOU_')]+[{k:v for k,v in x.items() if k!='rows'} for x in rows]
(D/'institution_v2q1d_security_final.json').write_text(json.dumps({'cases':cases,'passed':sum(x['pass'] for x in cases),'failed':sum(not x['pass'] for x in cases),'original_method_errors_preserved':'institution_v2q1d_security.json and .log; corrected POST-only recommendation checks run separately'},indent=2))
old_review=json.loads((D/'institution_v2q1c_relevance_review.json').read_text());old_review['prior_source_sha256']=hashlib.sha256((D/'institution_v2q1c_relevance_review.json').read_bytes()).hexdigest();old_review['additional_private_rows']=[{**x,'library':case['library']} for case in rows for x in case['rows']];old_review['scale']={'0':'Irrelevant','1':'Partially relevant','2':'Relevant','3':'Highly relevant','UNKNOWN':'Cannot judge from available data'}
(D/'institution_v2q1d_relevance_review.json').write_text(json.dumps(old_review,indent=2))
print([(x['case'],x['http'],x['pass'],len(x['rows'])) for x in rows])
