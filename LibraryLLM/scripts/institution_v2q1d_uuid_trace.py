"""Actual resident-Qwen reference decisions against isolated authenticated fixtures."""
from pathlib import Path
from datetime import datetime,timezone
import json,time,httpx,sys,socket
ROOT=Path(__file__).resolve().parents[1]
SCOPE=ROOT/'.scratch/institution-v2q/final-continuation/lab'
def main():
 config=json.loads((SCOPE/'configuration.json').read_text());fixture=json.loads((SCOPE/'manifest.json').read_text())
 phase=sys.argv[1] if len(sys.argv)>1 else 'before'
 output=ROOT/f'reports/institution_v2q1d_ordinal_{phase}.json';assert not output.exists()
 result={'started_at':datetime.now(timezone.utc).isoformat(),'mode':'REAL_QWEN; controlled Global retrieval; real tenant native retrieval','cases':[]}
 aliases={b['library_book_id']:b['alias'] for lib in fixture['libraries'] for b in lib['books']}
 aliases.update({b['work_id']:b['alias'] for b in fixture['global_books']})
 for _ in range(120):
  with socket.socket() as probe:
   if probe.connect_ex(('127.0.0.1',18005))==0:break
  time.sleep(1)
 else:raise RuntimeError('Owned Qwen lab not ready within 120 seconds')
 with httpx.Client(base_url='http://127.0.0.1:18005',timeout=240) as c:
  r=c.post('/auth/login',json={'email':'owner@q1d.example.com','password':config['password']});r.raise_for_status();headers={'Authorization':'Bearer '+r.json()['access_token']}
  for label,lib in [('A',fixture['libraries'][0])]:
   scope={'library_id':lib['library_id']} if lib else {}
   books=[b['library_book_id'] for b in lib['books']] if lib else [b['work_id'] for b in fixture['global_books']]
   seed=c.post('/assistant/chat',headers=headers,json={'message':'Recommend','action':'RECOMMEND',**scope});seed.raise_for_status();seed=seed.json()
   recent=[b['work_id'] for b in seed['books']];assert len(recent)>=3
   for index,message in enumerate(['Compare the first and third.']):
    if True:
     seeded=c.post('/assistant/chat',headers=headers,json={'message':'Recommend','action':'RECOMMEND',**scope});seeded.raise_for_status();seed=seeded.json();recent=[b['work_id'] for b in seed['books']]
    started=time.perf_counter();r=c.post('/assistant/chat',headers=headers,json={'message':message,'conversation_id':seed['conversation_id'],'recent_work_ids':recent,**scope,**({'selected_work_ids':[recent[0]],'page_context':{'work_id':recent[2]}} if index==8 else {})});body=r.json()
    row={'id':label+'-RECENT-'+str(index+1),'query':message,'http':r.status_code,'elapsed_ms':round((time.perf_counter()-started)*1000,3),'intent':body.get('intent'),'books':[aliases.get(b['work_id'],'UNKNOWN') for b in body.get('books',[])],'availability':[{'book':aliases.get(a['work_id'],'UNKNOWN'),'available':a.get('available_copies')} for a in body.get('availability',[])],'response_text':body.get('message'),'clarification':body.get('clarification'),'errors':[e['code'] for e in body.get('errors',[])]}
    result['cases'].append(row);output.write_text(json.dumps(result,indent=2));print(row['id'],row['http'],row['intent'],row['books'],flush=True)
  result['complete']=True;output.write_text(json.dumps(result,indent=2))
if __name__=='__main__':main()
