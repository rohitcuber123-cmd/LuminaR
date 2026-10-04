"""Real resident-service depth comparison; disposable account only."""
import json,sys,time,secrets
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import requests
from backend.database.mongodb import users_collection,db
from backend.services.identity_service import next_user_id
from backend.services.auth_service import hash_password
from backend.utils.jwt_utils import create_access_token
QUERIES=['manage money for finances','beginner artificial intelligence','gothic horror','database systems','time travel science fiction','machine learning','personal finance','investing for beginners']
def main():
 phase=sys.argv[1]
 state=ROOT/'.search_depth_validation.json'
 if phase=='baseline':
  password=secrets.token_urlsafe(24)
  account={'user_id':next_user_id(),'name':'Disposable depth validation','email':f'depth-{uuid4().hex}@example.com','role':'GENERAL_USER','password_hash':hash_password(password),'is_email_verified':True}
  users_collection.insert_one(account)
  token=create_access_token(account['user_id'],account['email'],account['role'])
  state.write_text(json.dumps({'user_id':account['user_id'],'email':account['email'],'password':password,'token':token}),encoding='utf-8')
  db['search_history'].insert_one({'user_id':account['user_id'],'query':QUERIES[0],'created_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc),'results':[]})
 data=json.loads(state.read_text(encoding='utf-8'));headers={'Authorization':'Bearer '+data['token']}
 def call(port,path,body=None,params=None):
  start=time.perf_counter()
  r=requests.post(f'http://127.0.0.1:{port}{path}',json=body,headers=headers,timeout=120) if body is not None else requests.get(f'http://127.0.0.1:{port}{path}',params=params,headers=headers,timeout=120)
  r.raise_for_status();result=r.json();result['wall_ms']=(time.perf_counter()-start)*1000
  return result
 searches=[]
 for query in QUERIES:
  rows=[]
  for depth in ([10,20,50] if query==QUERIES[0] else [50]):
   result=call(8003,'/search',{'query':query,'top_k':depth,'save_history':False})
   rows.append({'depth':depth,'response':result})
  searches.append({'query':query,'runs':rows});print(phase,query,len(rows[-1]['response']['results']),flush=True)
 seed=searches[0]['runs'][-1]['response']['results'][0]['work_id']
 recommendations=[]
 for mode in ['personalized','single_seed']:
  for depth in [10,50]:
   result=call(8004,'/recommendations',params={'limit':depth}) if mode=='personalized' else call(8004,'/recommendations/from-book',{'work_id':seed,'limit':depth})
   recommendations.append({'mode':mode,'limit':depth,'seed_work_ids':[seed] if mode=='single_seed' else [],'response':result})
 result={'phase':phase,'queries':searches,'recommendations':recommendations,'search_health':call(8003,'/health')}
 (ROOT/f'reports/search_depth_{phase}_results.json').write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
if __name__=='__main__':main()
