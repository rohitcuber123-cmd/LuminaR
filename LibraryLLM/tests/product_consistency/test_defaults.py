from uuid import uuid4
import pytest
from backend.database.mongodb import db
from backend.services import library_lending_journal as journal
from backend.services.library_canonical_defaults import recover_initialization


def command(): return {'idempotency_key': str(uuid4())}


@pytest.fixture
def fresh(client):
    result = client.post('/libraries/register', headers={'x-test-user':'1'}, json={
        'name':'Fresh Test Library', 'slug':uuid4().hex, 'library_type':'PUBLIC_LIBRARY', 'access_mode':'PUBLIC'})
    assert result.status_code == 201, result.text
    return result.json()['library']['library_id']


def get(client, lid, suffix, user=1):
    return client.get('/libraries/' + lid + suffix, headers={'x-test-user':str(user)})


@pytest.fixture
def historical(fresh):
    for name in ['lending_config','v2c_config','fee_policies','lending_operations']:
        db['institution_' + name].delete_many({'library_id':fresh})
    return fresh


def test_new_library_lending_canonical(client, fresh):
    assert get(client,fresh,'/lending/config').json()['state'] == 'CANONICAL'


def test_new_library_reservation_canonical(client, fresh):
    assert db.institution_v2c_config.find_one({'library_id':fresh})['reservation_mode']=='CANONICAL'
    assert get(client,fresh,'/staff/reservations').status_code == 200


def test_new_library_fee_canonical(client, fresh):
    assert db.institution_v2c_config.find_one({'library_id':fresh})['fee_mode']=='CANONICAL'
    policy=db.institution_fee_policies.find_one({'library_id':fresh})
    assert policy['rate_minor_per_day']==500 and policy['charge_stop_policy']=='PHYSICAL_RECEIPT'
    assert get(client,fresh,'/staff/fees').status_code==200


def test_new_library_empty_counts_zero(client, fresh):
    for suffix in ['/staff/lending/borrow-requests','/staff/lending/return-requests','/staff/loans']:
        result=get(client,fresh,suffix)
        assert result.status_code==200 and result.json()['total']==0


def test_registration_initialization_failure_is_not_active(client, monkeypatch):
    original=journal.replay
    monkeypatch.setattr(journal,'replay',lambda plan: (_ for _ in ()).throw(RuntimeError('Injected acknowledgement failure')))
    response=client.post('/libraries/register',headers={'x-test-user':'1'},json={'name':'Fault Library','slug':uuid4().hex,
        'library_type':'PUBLIC_LIBRARY','access_mode':'PUBLIC'})
    assert response.status_code==503
    row=db.institution_libraries.find_one({'name':'Fault Library'})
    assert row['status']=='PROVISIONING' and db.institution_locks.find_one({'_id':row['library_id']})
    assert client.get('/libraries/discover').status_code in [200,404,422]
    monkeypatch.setattr(journal,'replay',original)
    with pytest.raises(ValueError): recover_initialization(row['library_id'])
    result=recover_initialization(row['library_id'],writers_stopped=True)
    assert result['recovered'] and db.institution_libraries.find_one({'library_id':row['library_id']})['status']=='ACTIVE'
    assert not db.institution_locks.find_one({'_id':row['library_id']})


def test_empty_legacy_safe_promotion(client,historical):
    before=get(client,historical,'/staff/canonical-defaults/preflight').json()
    assert before['safe']
    key=command(); path='/libraries/'+historical+'/staff/canonical-defaults/promote'
    first=client.post(path,json=key,headers={'x-test-user':'1'})
    second=client.post(path,json=key,headers={'x-test-user':'1'})
    assert first.status_code==second.status_code==200 and first.json()==second.json()
    assert db.institution_lending_config.find_one({'library_id':historical})['state']=='CANONICAL'
    assert db.institution_v2c_config.find_one({'library_id':historical})['state']=='CANONICAL'


@pytest.mark.parametrize('collection,record',[
    ('issues',{'issue_id':88,'status':'ISSUED'}),
    ('reservations',{'reservation_id':88,'status':'ACTIVE'}),
    ('fines',{'fine_id':88,'is_paid':False}),
    ('library_inventory',{'work_id':'OL1W','quantity':1}),
    ('institution_library_aliases',{'legacy_library_id':'LIB001'}),
    ('institution_inventory_migrations',{'source_key':'legacy:88'}),
    ('institution_lending_config',{'state':'PREPARING'}),
    ('institution_loans',{'loan_id':str(uuid4()),'status':'ACTIVE'}),
],ids=['test_promotion_active_legacy_loan_denied','test_promotion_unresolved_reservations_denied',
       'test_promotion_unresolved_fees_denied','mapped_inventory','test_real_legacy_library_not_force_promoted',
       'migration_conflict','preparing_conflict','canonical_consistency'])
def test_promotion_blockers(client,historical,collection,record):
    row={**record, 'canonical_library_id' if collection.endswith('library_aliases') else 'library_id':historical}
    db[collection].insert_one(row)
    preview=get(client,historical,'/staff/canonical-defaults/preflight')
    assert preview.status_code in [200,409,503]
    if preview.status_code==200:
        assert not preview.json()['safe'] and preview.json()['reasons']
    response=client.post('/libraries/'+historical+'/staff/canonical-defaults/promote',json=command(),headers={'x-test-user':'1'})
    assert response.status_code in [409,503]
    assert (db.institution_lending_config.find_one({'library_id':historical}) or {}).get('state')!='CANONICAL'
    assert db[collection].find_one(row)


def test_promotion_general_user_and_platform_role_denied(client,historical):
    client.post('/libraries/'+historical+'/join',json={},headers={'x-test-user':'2'})
    assert get(client,historical,'/staff/canonical-defaults/preflight',2).status_code==403
    db.platform_role_assignments.insert_one({'user_id':3,'role':'PLATFORM_ADMIN','status':'ACTIVE'})
    assert get(client,historical,'/staff/canonical-defaults/preflight',3).status_code==404


def test_first_local_book_switches_source(client,fresh):
    client.post('/libraries/'+fresh+'/join',json={},headers={'x-test-user':'2'})
    assert get(client,fresh,'/catalogue/source',2).json()['catalogue_source']=='GLOBAL_FALLBACK'
    response=client.post('/libraries/'+fresh+'/inventory/books',headers={'x-test-user':'1'},json={
        **command(),'title':'First Local Manual','subjects':['Networks'],'copies':1,'shelf_location':'A-01'})
    assert response.status_code==201,response.text
    source=get(client,fresh,'/catalogue/source',2).json()
    assert source['catalogue_source']=='LIBRARY_LOCAL' and source['local_book_count']==1
    assert 'has_dataset' not in db.institution_libraries.find_one({'library_id':fresh})


def test_import_preview_does_not_switch_source(client,fresh):
    before=get(client,fresh,'/catalogue/source').json()
    result=client.post('/libraries/'+fresh+'/inventory/imports/preview',headers={'x-test-user':'1'},
        files={'file':('sample.csv',b'title,subjects,copies,shelf_location\nImport Manual,Networks,2,CS-02\n','text/csv')})
    assert result.status_code==201,result.text
    assert get(client,fresh,'/catalogue/source').json()['catalogue_source']==before['catalogue_source']=='GLOBAL_FALLBACK'


def test_import_apply_switches_source(client,fresh):
    preview=client.post('/libraries/'+fresh+'/inventory/imports/preview',headers={'x-test-user':'1'},
        files={'file':('sample.csv',b'title,subjects,copies,shelf_location\nImport Manual,Networks,2,CS-02\n','text/csv')}).json()
    result=client.post('/libraries/'+fresh+'/inventory/imports/'+preview['import_id']+'/apply',headers={'x-test-user':'1'},json={'existing_policy':'skip'})
    assert result.status_code==200,result.text
    assert get(client,fresh,'/catalogue/source').json()['catalogue_source']=='LIBRARY_LOCAL'


def test_source_uses_active_records(client,fresh):
    result=client.post('/libraries/'+fresh+'/inventory/books',headers={'x-test-user':'1'},json={**command(),'title':'Withdrawn Book','subjects':['Networks']}).json()
    response=client.delete('/libraries/'+fresh+'/inventory/books/'+result['library_book_id'],headers={'x-test-user':'1','idempotency-key':str(uuid4())})
    assert response.status_code==200,response.text
    assert get(client,fresh,'/catalogue/source').json()['catalogue_source']=='GLOBAL_FALLBACK'


def test_inventory_availability_is_bulk(client,fresh,monkeypatch):
    from backend.services import library_lending_service as lending
    for n in range(10):
        response=client.post('/libraries/'+fresh+'/inventory/books',headers={'x-test-user':'1'},json={
            **command(),'title':f'Bulk Manual {n}','subjects':['Networks'],'copies':2})
        assert response.status_code==201
    monkeypatch.setattr(lending,'availability_locked',lambda *args: (_ for _ in ()).throw(AssertionError('Per-card availability read')))
    result=get(client,fresh,'/inventory/books?limit=10')
    assert result.status_code==200,result.text
    assert len(result.json()['results'])==10 and all(r['availability']['requestable']==2 for r in result.json()['results'])
