"""Actual authentication, conversation and asset negatives on disposable fixtures."""
from pathlib import Path
from uuid import uuid4
from time import perf_counter
import json,httpx
from pymongo import MongoClient
R=Path(__file__).resolve().parents[1];S=R/'.scratch/institution-v2q/digital-review/lab';O=R/'reports/institution_v2q3_security.json'
def main():
 assert not O.exists();cfg=json.loads((S/'configuration.json').read_text());m=json.loads((S/'manifest.json').read_text());A,B,I=m['libraries'];rows=[];samples=[]
 def count():
  p=R/'reports/institution_v2q3_private_stages.jsonl'
  return sum(sum(s['stage'].startswith('qwen_') for s in json.loads(line)['stages']) for line in p.read_text().splitlines()) if p.exists() else 0
 with httpx.Client(base_url='http://127.0.0.1:18005',timeout=90) as c:
  tokens={}
  for u in m['users']:
   r=c.post('/auth/login',json={'email':u['email'],'password':cfg['password']});r.raise_for_status();tokens[u['label']]=r.json()['access_token']
  def req(method,path,user,**kw):return c.request(method,path,headers={'Authorization':'Bearer '+tokens[user]} if user else {},**kw)
  def check(name,method,path,user,expected,no_qwen=True,**kw):
   before=count();start=perf_counter();r=req(method,path,user,**kw);body=r.json();generated=count()-before
   row={'case':name,'http':r.status_code,'expected':list(expected),'elapsed_ms':round((perf_counter()-start)*1000,3),'private_model_calls':generated,'pass':r.status_code in expected and (not no_qwen or generated==0)}
   rows.append(row);O.write_text(json.dumps({'cases':rows,'recommendation_samples':samples,'controlled_external_provider':True},indent=2));print(name,row['pass'],flush=True);return body
  for lib,users in [(A,['librarian','revoked']),(B,['second'])]:
   for u in users:req('POST',f"/libraries/{lib['library_id']}/join",u,json={'access_code':cfg['private_code']}).raise_for_status()
  def path(lib):return f"/libraries/{lib['library_id']}/assets/{lib['assets'][0]['asset_id']}"
  for lib,user in [(A,'revoked'),(B,'second')]:check('AUTHORIZED_METADATA_'+lib['alias'],'GET',path(lib),user,(200,))
  for label,lib,user in [('A_ONLY_TO_B',B,'revoked'),('B_ONLY_TO_A',A,'second'),('OUTSIDER',A,'outsider'),('ANONYMOUS',A,None)]:
   check(label,'POST',path(lib)+'/rag',user,(401,403,404),json={'query':'What calibration code is recorded?'})
  check('INVALID_ASSET','POST',f"/libraries/{A['library_id']}/assets/{uuid4()}/rag",'revoked',(404,),json={'query':'What calibration code is recorded?'})
  check('INVALID_DOCUMENT','POST','/rag/ask','revoked',(404,),json={'query':'What is recorded?','document_id':'invalid-q3-document'})
  check('FOREIGN_SOURCE_ID','GET',path(B)+'/sources/foreign-q3-chunk','second',(404,))
  conversations=[]
  for label,lib in [('GLOBAL',None),('A',A),('B',B),('GLOBAL_RETURN',None)]:
   scope={'library_id':lib['library_id']} if lib else {}
   body=check('NEW_CONVERSATION_'+label,'POST','/assistant/chat','owner',(200,),json={'message':'Recommend','action':'RECOMMEND',**scope})
   if lib:
    own=all(x.get('library_id')==lib['library_id'] for x in body.get('books',[]));rows[-1]['all_books_current_library']=own;rows[-1]['pass'] &= own
   if conversations:
    check('OLD_CONVERSATION_DENIED_'+label,'POST','/assistant/chat','owner',(404,),json={'message':'Recommend','action':'RECOMMEND','conversation_id':conversations[-1],**scope})
   conversations.append(body['conversation_id'])
  with MongoClient('mongodb://127.0.0.1:27017') as db:
   member=db[cfg['database']].institution_memberships.find_one({'library_id':A['library_id'],'user_id':6})
  check('REVOKE_OWNED_FIXTURE_MEMBER','PATCH',f"/libraries/{A['library_id']}/memberships/{member['membership_id']}",'owner',(200,),json={'status':'REMOVED'})
  check('REVOKED_ASSET_DENIED','POST',path(A)+'/rag','revoked',(404,),json={'query':'What calibration code is recorded?'})
  for lib,user in [(A,'member'),(B,'second')]:
   body=check('FOR_YOU_'+lib['alias'],'POST',f"/libraries/{lib['library_id']}/catalogue/recommendations",user,(200,),json={'work_ids':[],'limit':10})
   books=body.get('recommendations',body.get('books',body.get('results',[])))
   samples.append({'library':lib['alias'],'source':body.get('source'),'rows':[{'rank':i+1,'book_id':x.get('library_book_id') or x.get('work_id'),'title':x.get('title'),'authors':x.get('authors'),'subjects':x.get('subjects'),'relevance_grade':None,'judge_identity':None,'judgment_rationale':None} for i,x in enumerate(books)],'independent_labels':'UNASSIGNED'})
  O.write_text(json.dumps({'cases':rows,'recommendation_samples':samples,'controlled_external_provider':True,'complete':True},indent=2))
if __name__=='__main__':main()
