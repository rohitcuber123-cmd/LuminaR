from pathlib import Path
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from jose import jwt
import json,sys,httpx
from backend.database.mongodb import db
from backend.utils.jwt_utils import JWT_SECRET_KEY,JWT_ALGORITHM
R=Path('reports');f=json.loads((R/'search_v2c_b1_fixture.json').read_text());c=db.search_sessions_v2b
uid=str(f['member_id']);lid=f['library_id'];out=R/('search_v2c_b1_browser_mongo'+('_final' if len(sys.argv)>2 else '')+'.json');e=json.loads(out.read_text()) if out.exists() else {}
a=sys.argv[1]
row=c.find_one({'user_id':uid,'library_id':lid,'workspace':'PATRON','current_plan':{'$exists':True}},sort=[('updated_at',-1)])
if a=='accepted':
 assert row;e['accepted']=row
elif a=='forged':
 p=c.find_one({'user_id':uid,'library_id':lid,'record_type':'CLARIFICATION','search_session_id':e['accepted']['_id']},sort=[('created_at',-1)]);assert p
 before=c.find_one({'_id':e['accepted']['_id']});assert json.loads(json.dumps(before,default=str))==e['accepted']
 payload={'sub':uid,'sid':p['login_session'],'exp':datetime.now(timezone.utc)+timedelta(minutes=15)}
 auth={'Authorization':'Bearer '+jwt.encode(payload,JWT_SECRET_KEY,algorithm=JWT_ALGORITHM)}
 body={'clarification_id':p['_id'].split(':',1)[1],'choice_id':str(uuid4()),'query':p['query'],'mode':p['mode'],'library_id':lid,'session_id':p['search_session_id']}
 res=httpx.post('http://127.0.0.1:8003/query/resolve',headers=auth,json=body,timeout=60)
 after=c.find_one({'_id':before['_id']});pa=c.find_one({'_id':p['_id']});assert res.status_code==404 and before==after and p==pa
 e['forged']={'status':res.status_code,'accepted_unchanged':before==after,'pending_unchanged':p==pa,'before':before,'after':after,'pending':p}
elif a=='valid':
 p=e['forged']['pending'];current=c.find_one({'_id':e['accepted']['_id']});assert current['version']==e['accepted']['version']+1 and current['current_plan']['subjects']==['Romance']
 assert c.find_one({'_id':p['_id']}).get('used');e['valid']={'after':current,'exactly_one_commit':True,'pending_consumed':True}
else:
 assert row;e.setdefault('chip_snapshots',[]).append({'name':a,'context':row})
out.write_text(json.dumps(e,indent=2,default=str));print(a, 'PASS', 'version',row['version'] if row else None)
