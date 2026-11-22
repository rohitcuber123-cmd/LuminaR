"""New communication paths under the existing isolated authenticated-mode gate."""
import os,sys,json,subprocess
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def child():
    from fastapi.testclient import TestClient
    from pymongo.errors import OperationFailure
    from backend.main import app
    from backend.database.mongodb import db
    from backend.utils.jwt_utils import create_access_token
    from backend.services import institution_repository as ir,notification_service as ns,library_announcement_service as service,tenant_notification_service as tn
    for module in [ir,ns,service,tn]:module.ensure_indexes()
    client=TestClient(app);tokens={}
    for uid in [1,2,3]:
        db.users.insert_one({'user_id':uid,'email':f'auth2p-{uid}@example.com','role':'GENERAL_USER','is_active':True,'is_email_verified':True})
        tokens[uid]=create_access_token(uid,f'auth2p-{uid}@example.com','GENERAL_USER')
    def api(path,method='GET',body=None,uid=1,code=200):
        r=client.request(method,path,json=body,headers={'Authorization':'Bearer '+tokens[uid]})
        assert r.status_code==code,(path,r.status_code);return r.json()
    lib=api('/libraries/register','POST',{'name':'Authenticated Part2P','slug':'auth2p-'+uuid4().hex[:12],'library_type':'PUBLIC_LIBRARY','access_mode':'PUBLIC'},code=201)['library']['library_id']
    api(f'/libraries/{lib}/join','POST',{},uid=2)
    row=api(f'/libraries/{lib}/announcements','POST',{'title':'Authenticated notice','body':'Verified gated fixture','request_id':str(uuid4())},code=201)
    api(f'/libraries/{lib}/announcements/{row["announcement_id"]}/publish','POST',{'revision':0})
    assert tn.materialize()['delivered']==2
    assert api('/notifications',uid=2)['unread_count']==1
    assert api('/notifications',uid=1)['notifications'][0]['action_route'].startswith('/staff/libraries/')
    api(f'/libraries/{lib}/announcements',uid=3,code=404)
    notice=api('/notifications',uid=2)['notifications'][0]
    api('/notifications/'+notice['notification_id']+'/read','PATCH',uid=2)
    assert api('/notifications',uid=2)['unread_count']==0
    found=api(f'/libraries/{lib}/staff/announcement-recipients?q=auth2p-2&limit=10')
    assert [r['user_id'] for r in found['results']]==[2]
    selected=api(f'/libraries/{lib}/announcements','POST',{'title':'Authenticated selected notice','body':'Selected account only','request_id':str(uuid4()),'audience':'SPECIFIC_MEMBER','recipient_user_id':2},code=201)
    published=api(f'/libraries/{lib}/announcements/{selected["announcement_id"]}/publish','POST',{'revision':0})
    assert published['delivery']['total']==1 and tn.materialize()['delivered']==1
    assert api('/notifications',uid=2)['unread_count']==1
    assert api('/notifications',uid=1)['unread_count']==1
    api(f'/libraries/{lib}/announcements/{selected["announcement_id"]}',uid=1,code=404)
    assert api(f'/libraries/{lib}/announcements/{selected["announcement_id"]}',uid=2)['recipient_user_id']==2
    ir.collection('memberships').update_one({'library_id':lib,'user_id':2},{'$set':{'status':'REMOVED'}})
    assert api('/notifications',uid=2)['count']==0
    try:db.institution_worker_telemetry_v2k.insert_one({'unauthorized':True})
    except OperationFailure as e:assert e.code==13
    else:raise AssertionError('Existing telemetry write boundary lost')
    try:db.client.drop_database(db.name)
    except OperationFailure as e:assert e.code==13
    else:raise AssertionError('App unexpectedly has destructive database rights')
    return {'result':'PASS','checks':16,'targeted_authenticated_search_and_delivery':True,'new_collection_authenticated_access':True,'private_copy_revocation':True,'staff_action_route':True,
        'telemetry_write_denied':True,'database_drop_denied':True,'role_qualification':'Existing named-resource compatibility fixture envelope, not a production minimum-role claim','production_auth_changed':False}

def main():
    if len(sys.argv)>1 and sys.argv[1]=='child':
        print(json.dumps(child()));return
    from scripts.institution_v2n_fixture import AuthMongo,provision_application
    with AuthMongo() as server:
        provision_application(server)
        env={**os.environ,'LUMINAR_MONGO_MODE':'AUTHENTICATED','MONGO_URI':server.app_uri,'MONGO_DB_NAME':server.database,
            'JWT_SECRET_KEY':'part2p-disposable-auth-fixture','LUMINAR_SESSION_DB':str(server.root/'sessions.sqlite'),
            'NOTIFICATION_DUE_WORKER_ENABLED':'0','NOTIFICATION_OUTBOX_WORKER_ENABLED':'0'}
        p=subprocess.run([sys.executable,__file__,'child'],cwd=ROOT,env=env,text=True,capture_output=True,timeout=120)
        (ROOT/'reports/institution_v2p1_authenticated.log').write_text(p.stdout+p.stderr,encoding='utf8')
        if p.returncode:raise RuntimeError('Authenticated fixture failed; see isolated log')
        report=json.loads(p.stdout.strip().splitlines()[-1])
    report['owned_server_and_data_removed']=True
    (ROOT/'reports/institution_v2p1_authenticated.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report))
if __name__=='__main__':main()
