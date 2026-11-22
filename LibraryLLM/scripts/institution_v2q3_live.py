"""Genuine Qwen follow-ups and fresh digital authority over owned HTTP fixtures."""
from pathlib import Path
from time import perf_counter
import json,httpx
R=Path(__file__).resolve().parents[1];S=R/'.scratch/institution-v2q/digital-review/lab'

def main():
 out=R/'reports/institution_v2q3_live.json';assert not out.exists()
 cfg=json.loads((S/'configuration.json').read_text());m=json.loads((S/'manifest.json').read_text())
 result={'mode':'Genuine single resident Qwen; controlled Global retrieval; actual tenant native search and authorization.','cases':[],'complete':False}
 with httpx.Client(base_url='http://127.0.0.1:18005',timeout=180) as c:
  tokens={}
  for who in ['member','owner','outsider']:
   r=c.post('/auth/login',json={'email':who+'@q3.example.com','password':cfg['password']});r.raise_for_status();tokens[who]=r.json()['access_token']
  h={'Authorization':'Bearer '+tokens['member']}
  c.post('/libraries/'+m['libraries'][1]['library_id']+'/join',headers=h,json={'access_code':cfg['private_code']}).raise_for_status()
  for label,lib in [('GLOBAL',None)]+[(x['alias'],x) for x in m['libraries']]:
   scope={'library_id':lib['library_id']} if lib else {};conversation=None;recent=[]
   for q in ['Show me database books.','Is the second one available?','Does it have a digital version?',
      'Can I read that one online?','Compare their availability.','Which one can I borrow physically?','Which one has an accessible PDF?']:
    payload={'message':q,'recent_work_ids':recent,**scope}
    if conversation:payload['conversation_id']=conversation
    start=perf_counter();r=c.post('/assistant/chat',headers=h,json=payload);b=r.json()
    row={'library':label,'question':q,'http':r.status_code,'elapsed_ms':round((perf_counter()-start)*1000,3),
         'request_recent_ids':recent,'response':b,'genuine_qwen_request':True}
    result['cases'].append(row);out.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(label,q,r.status_code,b.get('intent'),[x['status'] for x in b.get('digital_availability',[])],flush=True)
    conversation=b.get('conversation_id',conversation)
    if b.get('books'):recent=[x['work_id'] for x in b['books']]
  for lib in m['libraries'][:2]:
   for q in ['Is there a digital version?','Can I read this online?','Does this book have a PDF?','Can I access the ebook?','Is it available digitally?']:
    start=perf_counter();r=c.post('/assistant/chat',headers=h,json={'message':q,'library_id':lib['library_id'],'page_context':{'work_id':lib['books'][0]['library_book_id']}});b=r.json();digital=b.get('digital_availability',[])
    row={'library':lib['alias'],'question':q,'single_page':True,'http':r.status_code,'elapsed_ms':round((perf_counter()-start)*1000,3),'response':b,
         'pass':r.status_code==200 and len(digital)==1 and digital[0]['status']=='AUTHORIZED' and 'available copies' not in b.get('message','') and not b.get('errors')}
    result['cases'].append(row);out.write_text(json.dumps(result,indent=2),encoding='utf8');print('LINKED',lib['alias'],q,row['pass'],flush=True)
 result['complete']=True;out.write_text(json.dumps(result,indent=2),encoding='utf8')
 # Matrix starts only after all normal Assistant calls complete, in the same resident process.
 (S/'matrix.request').write_text('Review-only alternative; never apply previous rejected patch.')

if __name__=='__main__':main()
