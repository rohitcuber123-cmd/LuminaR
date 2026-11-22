"""Actual unchanged tenant recommendation service, owned synthetic HTTP fixtures."""
from pathlib import Path
from uuid import uuid4
import json,httpx,hashlib
R=Path(__file__).resolve().parents[1];S=R/'.scratch/institution-v2q/validator-review/lab'

def main():
 cfg=json.loads((S/'configuration.json').read_text());m=json.loads((S/'manifest.json').read_text())
 output=R/'reports/institution_v2q2_recommendation_matrix.json';assert not output.exists()
 data={'mode':'Real authenticated tenant service; controlled Global candidate IDs; no Qwen inference.','cases':[],'owned_additional_libraries':[],'semantic_relevance':'UNASSIGNED; ownership and candidate membership only'}
 def save():output.write_text(json.dumps(data,indent=2))
 with httpx.Client(base_url='http://127.0.0.1:18005',timeout=60) as c:
  def login(who):
   r=c.post('/auth/login',json={'email':who+'@q2.example.com','password':cfg['password']});r.raise_for_status();return {'Authorization':'Bearer '+r.json()['access_token']}
  owner=login('owner');member=login('member')
  fixtures=list(m['libraries'][:2])
  for label,count in [('SINGLE',1),('FIVE',5),('EMPTY',0)]:
   r=c.post('/libraries/register',headers=owner,json={'name':'Q2 '+label,'slug':'q2-'+label.lower()+'-'+uuid4().hex[:8],'library_type':'PRIVATE_INSTITUTION','access_mode':'PRIVATE_CODE','access_code':cfg['private_code']});r.raise_for_status()
   lib=r.json()['library']['library_id'];entry={'alias':label,'library_id':lib,'books':[]};data['owned_additional_libraries'].append(entry);save()
   r=c.post(f'/libraries/{lib}/join',headers=member,json={'access_code':cfg['private_code']});r.raise_for_status()
   for i in range(count):
    r=c.post(f'/libraries/{lib}/inventory/books',headers=owner,json={'title':f'{label} Local Acquisition {i+1}','authors':['Disposable Author'],'subjects':['Gardening'],'copies':1,'idempotency_key':str(uuid4())});r.raise_for_status();entry['books'].append({'library_book_id':r.json()['library_book_id'],'title':f'{label} Local Acquisition {i+1}'})
   fixtures.append(entry);save()
  candidates=[x['work_id'] for x in m['global_books']]
  for lib in fixtures:
   for mode,ids in [('COLD_START',[]),('UNMAPPED_NO_MATCH',candidates)]:
    r=c.post(f"/libraries/{lib['library_id']}/catalogue/recommendations",headers=member,json={'work_ids':ids,'limit':10});b=r.json();books=b.get('results',[])
    row={'case':lib['alias']+'_'+mode,'http':r.status_code,'source':b.get('source'),'ranking':b.get('ranking'),'intersection_count':b.get('intersection_count'),
         'book_ids':[x.get('library_book_id') for x in books],'expected_count':min(10,len(lib['books'])),'actual_count':len(books),
         'all_current_library':all(x.get('library_id')==lib['library_id'] for x in books),'no_matching_preference':'No preferences set; nonmatching Global candidates exercise local discovery, not a personalized preference model.',
         'pass':r.status_code==200 and len(books)==min(10,len(lib['books'])) and all(x.get('library_id')==lib['library_id'] for x in books)}
    data['cases'].append(row);save();print(row['case'],row['pass'],flush=True)
 data['complete']=True;save()
 # Preserve all seventy historical judgment rows verbatim inside the new export.
 previous=R/'reports/institution_v2q1d_relevance_review.json';review=json.loads(previous.read_text())
 review['prior_export_sha256']=hashlib.sha256(previous.read_bytes()).hexdigest();review['human_reviewed_rows']=0
 review['scale']={'0':'Irrelevant','1':'Partially relevant','2':'Relevant','3':'Highly relevant','UNKNOWN':'Insufficient information'}
 (R/'reports/institution_v2q2_relevance_review.json').write_text(json.dumps(review,indent=2))
 lines=['# Independent relevance review worksheet','', 'All judgments remain unassigned. Use 0 / 1 / 2 / 3 / UNKNOWN. Record reviewer identity and rationale. No ranking metric is calculated.','', '|Query|Library|Rank|Title|Author|Metadata / constraints|Judgment|Reviewer|Rationale|','|---|---|---:|---|---|---|---|---|---|']
 for row in review.get('rows',[])+review.get('additional_private_rows',[]):
  md=row.get('metadata',{});clean=lambda v:str(v or '').replace('|','/').replace('\n',' ')
  lines.append('|'+ '|'.join(map(clean,[row.get('query'),row.get('scope',row.get('library')),row.get('rank'),md.get('title',row.get('title')),md.get('authors',row.get('authors')),str(md)+'; '+str(row.get('expected_topic',row.get('requested_filters',''))),'UNASSIGNED','','']))+'|')
 (R/'reports/institution_v2q2_relevance_review.md').write_text('\n'.join(lines),encoding='utf8')

if __name__=='__main__':main()
