"""Platform directory and lifecycle over real HTTP, isolated standalone Mongo."""
from uuid import uuid4
import pytest
from backend.database.mongodb import db
from backend.services.institution_repository import collection
from backend.services import platform_library_service as service
from test_authority import grant, h, cmd

def url(library): return '/platform/libraries/'+library['id']
def change(client,library,action,status='ACTIVE',**values):
    return client.post(url(library)+'/'+action,headers=h(3),json=cmd(reason='Scoped lifecycle QA',expected_status=status,**values))
def snapshot(library):
    return {name:list(db[name].find({'library_id':library['id']}).sort('_id')) for name in db.list_collection_names()
            if name.startswith('institution_') and name not in ['institution_libraries','institution_locks']}

def test_platform_libraries_route_exists(client):
    grant();assert client.get('/platform/libraries',headers=h(3)).status_code==200
def test_platform_libraries_requires_platform_admin(client):
    assert client.get('/platform/libraries').status_code==403
def test_legacy_admin_denied_platform_libraries(client):
    assert db.users.find_one({'user_id':1})['role']=='ADMIN'
    assert client.get('/platform/libraries').status_code==403
def test_library_admin_denied_platform_libraries(client,libraries):
    assert client.get('/platform/libraries',headers=h(2)).status_code==403
def test_platform_admin_lists_libraries(client,libraries):
    grant();body=client.get('/platform/libraries?limit=2',headers=h(3)).json()
    assert body['total']==3 and len(body['results'])==2 and body['has_more']
    second=client.get('/platform/libraries?limit=2&offset=2',headers=h(3)).json()
    assert len(second['results'])==1 and not second['has_more']
    assert not {r['library_id'] for r in body['results']} & {r['library_id'] for r in second['results']}
@pytest.mark.parametrize('field',['name','slug','library_id','owner_email','owner_name'])
def test_platform_admin_search_libraries(client,libraries,field):
    grant();record=collection('libraries').find_one({'library_id':libraries[0]['id']})
    query={'owner_email':'workspace-1@example.com','owner_name':'Account 1'}.get(field,record.get(field))
    rows=client.get('/platform/libraries',params={'q':query},headers=h(3)).json()['results']
    assert [r['library_id'] for r in rows]==[libraries[0]['id']]
@pytest.mark.parametrize('status',['ACTIVE','SUSPENDED','REMOVED'])
def test_platform_admin_filter_status(client,libraries,status):
    grant();collection('libraries').update_one({'library_id':libraries[0]['id']},{'$set':{'status':status}})
    rows=client.get('/platform/libraries',params={'status':status},headers=h(3)).json()['results']
    assert rows and all(r['status']==status for r in rows)
@pytest.mark.parametrize('kind',['PUBLIC_LIBRARY','PRIVATE_INSTITUTION'])
def test_platform_admin_filter_type(client,libraries,kind):
    grant();collection('libraries').update_one({'library_id':libraries[0]['id']},{'$set':{'library_type':kind}})
    rows=client.get('/platform/libraries',params={'library_type':kind},headers=h(3)).json()['results']
    assert rows and all(r['library_type']==kind for r in rows)
def test_platform_library_detail(client,libraries):
    grant();body=client.get(url(libraries[0]),headers=h(3)).json()
    assert body['library']['counts']=={'members':0,'staff':1,'local_books':1}
    assert body['tenant_internals_require_membership']
    assert body['cutover']=={'circulation':'CANONICAL','reservations':'CANONICAL','fees':'CANONICAL'}
    forbidden=['access_code_hash','password_hash','invitation','loan_id','fee_id','document_id']
    assert not any(key in str(body) for key in forbidden)
def test_platform_admin_suspend(client,libraries):
    grant();before=snapshot(libraries[0]);response=change(client,libraries[0],'suspend')
    assert response.status_code==200,response.text
    assert response.json()['status']=='SUSPENDED' and snapshot(libraries[0])==before
    assert client.get(libraries[0]['base']+'/staff/loans').status_code==404
    event=db.platform_audit.find_one({'event_id':response.json()['event_id']})
    assert event['event']=='LIBRARY_SUSPENDED' and event['actor_user_id']==3 and event['state']=='COMMITTED'
@pytest.mark.parametrize('reason',[None,'','   '])
def test_suspend_requires_reason(client,libraries,reason):
    grant();body=cmd(expected_status='ACTIVE')
    if reason is not None:body['reason']=reason
    assert client.post(url(libraries[0])+'/suspend',headers=h(3),json=body).status_code==422
def test_platform_admin_restore(client,libraries):
    grant();assert change(client,libraries[0],'suspend').status_code==200
    assert change(client,libraries[0],'restore','SUSPENDED').json()['status']=='ACTIVE'
    assert client.get(libraries[0]['base']+'/staff/loans').status_code==200
def test_platform_admin_soft_remove(client,libraries):
    grant();assert change(client,libraries[0],'remove').json()['status']=='REMOVED'
    assert collection('libraries').find_one({'library_id':libraries[0]['id']})
@pytest.mark.parametrize('reason',[None,'','   '])
def test_remove_requires_reason(client,libraries,reason):
    grant();body=cmd(expected_status='ACTIVE')
    if reason is not None:body['reason']=reason
    assert client.post(url(libraries[0])+'/remove',headers=h(3),json=body).status_code==422
def test_removed_library_data_preserved(client,libraries):
    grant();before=snapshot(libraries[0]);assert change(client,libraries[0],'remove').status_code==200
    assert snapshot(libraries[0])==before
def test_removed_library_hidden_from_discovery(client,libraries):
    grant();change(client,libraries[0],'remove')
    response=client.get('/libraries',headers=h(3));assert response.status_code==200,response.text
    assert libraries[0]['id'] not in str(response.json())
def test_removed_library_join_denied(client,libraries):
    grant();change(client,libraries[0],'remove')
    assert client.post(libraries[0]['base']+'/join',headers=h(3),json={}).status_code==404
def test_restore_removed_library(client,libraries):
    grant();before=snapshot(libraries[0]);change(client,libraries[0],'remove')
    response=change(client,libraries[0],'restore','REMOVED');assert response.status_code==200,response.text
    assert snapshot(libraries[0])==before and response.json()['status']=='ACTIVE'
    assert db.platform_audit.count_documents({'event':'LIBRARY_RESTORED'})==1
def test_platform_admin_cannot_edit_inventory_without_membership(client,libraries):
    grant();response=client.patch(libraries[0]['base']+'/inventory/books/'+libraries[0]['book'],headers=h(3),json={'title':'Forbidden'})
    assert response.status_code==404,response.text
def test_platform_admin_cannot_approve_request_without_membership(client,libraries):
    grant();response=client.post(libraries[0]['base']+'/staff/lending/borrow-requests/'+str(uuid4())+'/approve',headers=h(3),json=cmd())
    assert response.status_code==404,response.text
def test_platform_admin_cannot_manage_staff_without_membership(client,libraries):
    grant();response=client.post(libraries[0]['base']+'/invitations',headers=h(3),json={'email':'denied@example.com','role':'LIBRARIAN'})
    assert response.status_code==404,response.text
def test_platform_admin_cannot_waive_fee_without_membership(client,libraries):
    grant();response=client.post(libraries[0]['base']+'/staff/fees/'+str(uuid4())+'/waive',headers=h(3),json=cmd(reason='Forbidden'))
    assert response.status_code==404,response.text
@pytest.mark.parametrize('method,path,body',[
    ('POST','/staff/loans/{id}/receive',{}),('PUT','/access-code',{'access_code':'fixture-only-code'}),
    ('PATCH','',{'name':'Forbidden'}),('PUT','/access',{'access_mode':'PUBLIC'}),
    ('POST','/settings/fee-policy',{'idempotency_key':str(uuid4())}),
])
def test_platform_admin_cannot_change_tenant_internals(client,libraries,method,path,body):
    grant();response=client.request(method,libraries[0]['base']+path.format(id=uuid4()),headers=h(3),json=cmd(**body) if 'receive' in path else body)
    assert response.status_code in [403,404],response.text
    assert collection('libraries').find_one({'library_id':libraries[0]['id']})['name']=='Library A'
def test_platform_role_revocation(client,libraries):
    grant();assert client.get('/platform/libraries',headers=h(3)).status_code==200
    db.platform_role_assignments.update_one({'user_id':3},{'$set':{'status':'REVOKED'}})
    assert client.get('/platform/libraries',headers=h(3)).status_code==403
    assert change(client,libraries[0],'suspend').status_code==403
def test_dual_authority_independently_checked(client,libraries):
    grant(1);assert client.get('/platform/libraries').status_code==200
    assert client.get(libraries[0]['base']+'/staff/loans').status_code==200
    db.platform_role_assignments.update_one({'user_id':1},{'$set':{'status':'REVOKED'}})
    assert client.get('/platform/libraries').status_code==403
    assert client.get(libraries[0]['base']+'/staff/loans').status_code==200
def test_platform_lifecycle_idempotency_and_stale_state(client,libraries):
    grant();body=cmd(expected_status='ACTIVE',reason='Repeated request')
    first=client.post(url(libraries[0])+'/suspend',headers=h(3),json=body)
    assert first.status_code==200 and client.post(url(libraries[0])+'/suspend',headers=h(3),json=body).json()==first.json()
    assert db.platform_audit.count_documents({})==1
    assert change(client,libraries[0],'remove','ACTIVE').status_code==409
def test_restore_revalidates_owner_and_canonical_integrity(client,libraries):
    grant();change(client,libraries[0],'remove');db.users.update_one({'user_id':1},{'$set':{'is_active':False}})
    assert change(client,libraries[0],'restore','REMOVED').status_code==409
    assert collection('libraries').find_one({'library_id':libraries[0]['id']})['status']=='REMOVED'
@pytest.mark.parametrize('params',[{'limit':51},{'offset':-1},{'q':'x'*121},{'status':'ARCHIVED'},{'library_type':'bad'}])
def test_platform_directory_bounded_input(client,params):
    grant();assert client.get('/platform/libraries',params=params,headers=h(3)).status_code==422
def test_lifecycle_uncertain_ack_retains_gate_and_recovers(client,libraries,monkeypatch):
    from pymongo.collection import Collection
    grant();original=Collection.update_one
    def fail(self,query,update,*args,**kwargs):
        if self.name=='platform_audit' and update.get('$set',{}).get('state')=='COMMITTED':
            raise RuntimeError('Simulated acknowledgement failure')
        return original(self,query,update,*args,**kwargs)
    monkeypatch.setattr(Collection,'update_one',fail)
    assert change(client,libraries[0],'suspend').status_code==503
    # A durable intent and status survive; retained gate is fail-closed.
    assert collection('locks').find_one({'_id':libraries[0]['id']})
    assert client.get(libraries[0]['base']+'/staff/loans').status_code in [404,503]
    monkeypatch.setattr(Collection,'update_one',original)
    with pytest.raises(ValueError):service.recover_lifecycle(libraries[0]['id'])
    assert service.recover_lifecycle(libraries[0]['id'],writers_stopped=True)['status']=='SUSPENDED'
    assert not collection('locks').find_one({'_id':libraries[0]['id']})
    assert db.platform_audit.find_one({'library_id':libraries[0]['id']})['state']=='COMMITTED'
