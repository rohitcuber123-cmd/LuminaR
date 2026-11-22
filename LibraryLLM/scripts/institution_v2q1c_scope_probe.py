"""Genuine Qwen positive/negative contextual reference controls; fixture data only."""
from pathlib import Path
import httpx,json,time
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'.scratch/institution-v2q/continuation/lab'
def main():
 out=ROOT/'reports/institution_v2q1c_scope_controls.json';assert not out.exists()
 cfg=json.loads((S/'configuration.json').read_text());m=json.loads((S/'manifest.json').read_text());rows=[]
 with httpx.Client(base_url='http://127.0.0.1:18005',timeout=180) as c:
  r=c.post('/auth/login',json={'email':'owner@q1c.example.com','password':cfg['password']});r.raise_for_status();h={'Authorization':'Bearer '+r.json()['access_token']}
  for label,lib in [('GLOBAL',None),('A',m['libraries'][0]),('I',m['libraries'][2])]:
   scope={'library_id':lib['library_id']} if lib else {};books=[b['library_book_id'] for b in lib['books']] if lib else [b['work_id'] for b in m['global_books']]
   cases=[('SELECTED','Is the second selected book available?',{'selected_work_ids':books[:2],'recent_work_ids':books[2:]},books[1]),('PAGE','Is the book on the open page available?',{'page_context':{'work_id':books[4]}},books[4]),('MISSING','Is the second one available?',{},None),('TOPIC','Find books about computer networks',{},'SEARCH')]
   for name,query,context,expected in cases:
    start=time.perf_counter();r=c.post('/assistant/chat',headers=h,json={'message':query,**scope,**context});b=r.json();ids=[x['work_id'] for x in b.get('books',[])];avail=[x['work_id'] for x in b.get('availability',[])]
    ok=r.status_code==200 and not b.get('errors') and (bool(b.get('clarification')) and not ids and not avail if expected is None else b.get('intent')=='SEARCH_BOOKS' and bool(ids) if expected=='SEARCH' else avail==[expected])
    rows.append({'id':label+'-'+name,'http':r.status_code,'intent':b.get('intent'),'pass':ok,'elapsed_ms':round((time.perf_counter()-start)*1000,3),'returned_count':len(ids),'availability_count':len(avail),'clarified':bool(b.get('clarification')),'errors':[x['code'] for x in b.get('errors',[])]});out.write_text(json.dumps(rows,indent=2));print(rows[-1]['id'],ok,flush=True)
if __name__=='__main__':main()
