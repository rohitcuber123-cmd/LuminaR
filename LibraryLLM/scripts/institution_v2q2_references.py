"""Genuine Qwen conversational reference evaluation, four owned contexts."""
from pathlib import Path
from time import perf_counter
import json,httpx
R=Path(__file__).resolve().parents[1];S=R/'.scratch/institution-v2q/validator-review/lab'

def main():
 out=R/'reports/institution_v2q2_references.json';assert not out.exists()
 cfg=json.loads((S/'configuration.json').read_text());m=json.loads((S/'manifest.json').read_text())
 assert not (S/'candidate.active').exists()
 assert json.loads((R/'reports/institution_v2q2_validator_matrix.json').read_text())['complete']
 data={'mode':'Actual unchanged Qwen; controlled Global retrieval provider; actual tenant handlers and native retrieval.','cases':[],'complete':False}
 with httpx.Client(base_url='http://127.0.0.1:18005',timeout=180) as c:
  r=c.post('/auth/login',json={'email':'owner@q2.example.com','password':cfg['password']});r.raise_for_status();h={'Authorization':'Bearer '+r.json()['access_token']}
  for label,lib in [('GLOBAL',None)]+[(x['alias'],x) for x in m['libraries']]:
   scope={'library_id':lib['library_id']} if lib else {}
   canonical={x.get('library_book_id',x.get('work_id')) for x in (lib['books'] if lib else m['global_books'])}
   comparison=None
   questions=['Tell me about the first book.','Tell me about the third book.','Is the second book available?','Compare the first and third.','Which one is easier?','Show similar books to the last book.','What about that one?','Is the currently selected book available?','Does this book have a digital copy?']
   for i,q in enumerate(questions):
    try:
     seed=c.post('/assistant/chat',headers=h,json={'message':'Recommend','action':'RECOMMEND',**scope});seed.raise_for_status();seed=seed.json();recent=[x['work_id'] for x in seed['books']]
     payload={'message':q,'conversation_id':comparison if i==4 and comparison else seed['conversation_id'],'recent_work_ids':recent,**scope}
     if i==7:payload['selected_work_ids']=[recent[1]]
     if i==8:
      focus=(lib['books'][0]['library_book_id'] if lib else m['global_books'][0]['work_id'])
      payload['page_context']={'work_id':focus}
     start=perf_counter();r=c.post('/assistant/chat',headers=h,json=payload);b=r.json()
     returned=[x['work_id'] for x in b.get('books',[])];available=[x['work_id'] for x in b.get('availability',[])]
     expected=[recent[0]] if i==0 else [recent[2]] if i==1 else [recent[1]] if i in (2,7) else [recent[0],recent[2]] if i==3 else []
     row={'case':label+'-'+str(i+1),'library':label,'library_uuid':scope.get('library_id'),'question':q,'request_context':{'recent_ids':recent,'selected_ids':payload.get('selected_work_ids',[]),'page':payload.get('page_context')},
          'expected_reference_ids':expected,'http':r.status_code,'elapsed_ms':round((perf_counter()-start)*1000,3),'intent':b.get('intent'),'actual_book_ids':returned,'availability':b.get('availability',[]),'actual_message':b.get('message'),'clarification':b.get('clarification'),'errors':b.get('errors',[]),'all_returned_ids_authorized':all(x in canonical for x in returned+available),
          'reference_identity_match':set(returned if i in (0,1,3) else available)==set(expected) if expected else None,
          'ambiguous_reference_clarified':bool(b.get('clarification')) if i==6 else None,
          'expected_digital_copy':True if i==8 and lib and lib['alias'] in ('A','B') else None,
          'digital_answer_requires_manual_review':i==8,'genuine_qwen':'See matching original parsed-decision trace, no explicit action supplied.'}
     if i==3:comparison=b.get('conversation_id')
     data['cases'].append(row);out.write_text(json.dumps(data,indent=2));print(row['case'],r.status_code,row['intent'],row['reference_identity_match'],flush=True)
    except Exception as e:
     data['cases'].append({'case':label+'-'+str(i+1),'question':q,'error':type(e).__name__});out.write_text(json.dumps(data,indent=2));print(label,i,type(e).__name__,flush=True)
 data['complete']=True;out.write_text(json.dumps(data,indent=2))

if __name__=='__main__':main()
