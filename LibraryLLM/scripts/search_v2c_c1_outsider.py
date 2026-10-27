"""Bounded outsider checks against the disposable private tenant."""
import json
from pathlib import Path
import httpx
from backend.database.mongodb import db
from backend.utils.jwt_utils import create_access_token
R=Path('reports');f=json.loads((R/'search_v2c_c1_fixture.json').read_text());u=db.users.find_one({'user_id':f['outsider_id']});token=create_access_token(u['user_id'],u['email'],u['role']);lid=f['library_id'];results=[]
for base,path,params in [('8003','/query/suggestions',{'q':'neur','library_id':lid}),('8003','/query/suggestions',{'q':'neur','library_id':lid,'staff':'true'}),('8003','/libraries/'+lid+'/catalogue/search',{'search':'books about neural networks'}),('8002','/libraries/'+lid+'/catalogue/books',{}),('8002','/libraries/'+lid+'/catalogue/facets',{})]:
 r=httpx.get('http://127.0.0.1:'+base+path,params=params,headers={'Authorization':'Bearer '+token},timeout=30)
 assert r.status_code in [403,404],r.text
 assert not any(s.lower() in r.text.lower() for s in ['V2CC1 Wizards','V2CC1 Romance','Private Orchid','Synthetic A1 Author','Neural Networks'])
 results.append({'path':path,'params':params,'status':r.status_code,'response':r.json()})
(R/'search_v2c_c1_outsider_api.json').write_text(json.dumps({'result':'PASS','private_leaks_observed':0,'requests':results},indent=2));print('PASS: five outsider requests denied without private vocabulary.')

