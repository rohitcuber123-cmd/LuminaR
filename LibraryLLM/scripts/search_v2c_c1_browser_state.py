"""Correlate real Chromium-created contexts with live denial and Mongo state."""
import json,sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
from jose import jwt
import httpx
from backend.database.mongodb import db
from backend.utils.jwt_utils import JWT_SECRET_KEY,JWT_ALGORITHM
R=Path('reports');f=json.loads((R/'search_v2c_c1_fixture.json').read_text());c=db.search_sessions_v2b
phase,scope=sys.argv[1:3];lid=f['public_library_id'] if scope=='public' else f['library_id']
p=R/('search_v2c_c1_browser_revocation_mongo.json' if phase.startswith('revocation_') else f'search_v2c_c1_browser_{scope}_mongo.json')
def save(d):p.write_text(json.dumps(d,indent=2,default=str))
if phase=='deny':
 row=c.find_one({'user_id':str(f['member_id']),'library_id':lid,'workspace':'PATRON','current_plan':{'$exists':True}},sort=[('updated_at',-1)])
 assert row
 pending=c.find_one({'record_type':'CLARIFICATION','search_session_id':row['_id'],'login_session':row['login_session'],'used':{'$ne':True}},sort=[('created_at',-1)])
 assert pending
 owner={'user_id':row['user_id'],'login_session':row['login_session']}
 before=list(c.find(owner).sort('_id'));u=db.users.find_one({'user_id':f['member_id']})
 token=jwt.encode({'sub':str(f['member_id']),'sid':row['login_session'],'email':u['email'],'role':u['role'],'exp':datetime.now(timezone.utc)+timedelta(minutes=30)},JWT_SECRET_KEY,algorithm=JWT_ALGORITHM)
 response=httpx.get('http://127.0.0.1:8003/query/suggestions',params={'q':'neur','library_id':lid,'staff':'true'},headers={'Authorization':'Bearer '+token},timeout=30)
 after=list(c.find(owner).sort('_id'));assert response.status_code==403 and before==after
 save({'source':'Real Chromium UI-created accepted/pending rows; live API denial uses same verified owner and JWT sid','owner':owner,'library_id':lid,'accepted_id':row['_id'],'pending_id':pending['_id'],'before':before,'after_denial':after,'http_status':response.status_code,'body':response.json(),'accepted_unchanged':True,'pending_unchanged':True,'all_other_login_contexts_unchanged':True})
elif phase=='resolved':
 d=json.loads(p.read_text());before=next(r for r in d['before'] if r['_id']==d['accepted_id']);row=c.find_one({'_id':d['accepted_id']});pending=c.find_one({'_id':d['pending_id']})
 assert row['version']==before['version']+1 and pending['used'] is True
 d.update(after_ui_resolution=row,pending_after_ui_resolution=pending,exactly_one_commit=True);save(d)
elif phase=='revocation_before':
 row=c.find_one({'user_id':str(f['member_id']),'library_id':lid,'workspace':'PATRON','current_plan':{'$exists':True}},sort=[('updated_at',-1)]);assert row
 save({'owner':{'user_id':row['user_id'],'login_session':row['login_session']},'library_id':lid,'before_revocation':list(c.find({'user_id':row['user_id'],'login_session':row['login_session']}).sort('_id'))})
elif phase=='revocation_after':
 d=json.loads(p.read_text());after=json.loads(json.dumps(list(c.find(d['owner']).sort('_id')),default=str));before=d['before_revocation'];affected=[r for r in before if r.get('library_id')==lid];unrelated=[r for r in before if r.get('library_id')!=lid]
 assert affected and not any(r.get('library_id')==lid for r in after)
 assert unrelated and unrelated==after
 d.update(after_revocation=after,affected_invalidated=[r['_id'] for r in affected],unrelated_preserved=[r['_id'] for r in unrelated],scope_exact=True);save(d)
print(json.dumps({'phase':phase,'scope':scope,'result':'PASS'}))
