"""Real final-revision Qwen checks for a single current-page context."""
from pathlib import Path
from time import perf_counter,sleep
import json,httpx,hashlib
R=Path(__file__).resolve().parents[1];S=R/'.scratch/institution-v2q/validator-review/lab'

def main():
 out=R/'reports/institution_v2q2_single_page.json';assert not out.exists()
 for _ in range(1800):
  p=R/'reports/institution_v2q2_references_final.json'
  if p.exists() and json.loads(p.read_text()).get('complete'):break
  sleep(1)
 else:raise RuntimeError('Final four-context reference run incomplete')
 cfg=json.loads((S/'configuration.json').read_text());m=json.loads((S/'manifest.json').read_text());rows=[]
 with httpx.Client(base_url='http://127.0.0.1:18005',timeout=180) as c:
  r=c.post('/auth/login',json={'email':'owner@q2.example.com','password':cfg['password']});r.raise_for_status();h={'Authorization':'Bearer '+r.json()['access_token']}
  for label,lib in [('GLOBAL',None)]+[(x['alias'],x) for x in m['libraries']]:
   wid=lib['books'][0]['library_book_id'] if lib else m['global_books'][0]['work_id'];scope={'library_id':lib['library_id']} if lib else {}
   for q in ['Is this book available?','Tell me about the third book.']:
    start=perf_counter();r=c.post('/assistant/chat',headers=h,json={'message':q,'page_context':{'work_id':wid},**scope});b=r.json();available=b.get('availability',[])
    good=(b.get('intent')=='CHECK_AVAILABILITY' and len(available)==1 and available[0]['work_id']==wid and available[0].get('available_copies')==2) if q.startswith('Is') else b.get('intent')=='CLARIFICATION' and not b.get('books') and not available
    row={'library':label,'library_uuid':scope.get('library_id'),'question':q,'expected_page_id':wid,'http':r.status_code,'intent':b.get('intent'),'availability':available,'message':b.get('message'),'clarification':b.get('clarification'),'errors':b.get('errors'),'elapsed_ms':round((perf_counter()-start)*1000,3),'pass':r.status_code==200 and good,'qwen_source_sha256':hashlib.sha256((R/'assistant/qwen.py').read_bytes()).hexdigest()}
    rows.append(row);out.write_text(json.dumps(rows,indent=2));print(label,q,row['pass'],flush=True)

if __name__=='__main__':main()
