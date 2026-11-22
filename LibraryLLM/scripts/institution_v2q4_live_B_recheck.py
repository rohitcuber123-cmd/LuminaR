"""Final-runtime model checks and actual unchanged private document RAG."""
from pathlib import Path
from time import sleep,perf_counter
import json,socket,hashlib,httpx
R=Path(__file__).resolve().parents[1];S=R/'.scratch/institution-v2q/q4-review/lab'

def main():
 out=R/'reports/institution_v2q4_live_B_recheck.json';assert not out.exists()
 for _ in range(180):
  with socket.socket() as s:ready=s.connect_ex(('127.0.0.1',18005))==0
  if ready:break
  sleep(1)
 cfg=json.loads((S/'configuration.json').read_text());m=json.loads((S/'manifest.json').read_text());runtime=json.loads((R/'reports/institution_v2q4_final_runtime.json').read_text())
 assert all(hashlib.sha256((R/n).read_bytes()).hexdigest()==v for n,v in runtime['source_sha256'].items())
 data={'runtime':runtime,'cases':[],'private_rag':[],'complete':False}
 def save():out.write_text(json.dumps(data,indent=2),encoding='utf8')
 with httpx.Client(base_url='http://127.0.0.1:18005',timeout=180) as c:
  r=c.post('/auth/login',json={'email':'member@q4.example.com','password':cfg['password']});r.raise_for_status();h={'Authorization':'Bearer '+r.json()['access_token']}
  c.post(f"/libraries/{m['libraries'][1]['library_id']}/join",headers=h,json={'access_code':cfg['private_code']}).raise_for_status()
  for label,lib in [('B',m['libraries'][1])]:
   for q in ['Does this book have a PDF?','Is this book available?','Can I borrow this book?','Borrow this book for me.']:
    wid=lib['books'][0]['library_book_id'] if lib else m['global_books'][0]['work_id']
    scope={'library_id':lib['library_id']} if lib else {};start=perf_counter()
    r=c.post('/assistant/chat',headers=h,json={'message':q,'page_context':{'work_id':wid},**scope});b=r.json();digital=b.get('digital_availability',[])
    expected='AUTHORIZED' if lib and lib['alias'] in ['A','B'] else 'UNKNOWN'
    good=(len(digital)==1 and digital[0]['status']==expected and 'available copies' not in b.get('message','')) if 'PDF' in q else len(b.get('availability',[]))==1 and b['availability'][0]['available_copies']==2
    if q.startswith('Can I borrow'):good=b.get('pending_action') is None and len(b.get('availability',[]))==1
    if q.startswith('Borrow this'):good=b.get('pending_action') is not None
    row={'library':label,'question':q,'http':r.status_code,'response':b,'expected_id':wid,'elapsed_ms':round((perf_counter()-start)*1000,3),'pass':r.status_code==200 and not b.get('errors') and good and [x['work_id'] for x in b.get('books',[])]==[wid]};data['cases'].append(row);save();print(label,q,row['pass'],flush=True)
  for iteration in [1]:
   for lib in m['libraries'][1:2]:
    start=perf_counter();r=c.post(f"/libraries/{lib['library_id']}/assets/{lib['assets'][0]['asset_id']}/rag",headers=h,json={'query':'What calibration code is recorded?'});b=r.json()
    data['private_rag'].append({'iteration':iteration,'library':lib['alias'],'http':r.status_code,'question':'What calibration code is recorded?','response':b,'elapsed_ms':round((perf_counter()-start)*1000,3),'protected_candidate_used':False});save();print('ORIGINAL_RAG',lib['alias'],b.get('verdict'),flush=True)
 data['complete']=True;save()

if __name__=='__main__':main()
