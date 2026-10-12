from copy import deepcopy
from uuid import uuid4
from scripts.seed_test_library_collection import metadata, values, fingerprint
from backend.database.mongodb import db


def test_seed_preserves_global_source(client):
    source={'work_id':'OL901W','title':'Real Global Source','subjects':'Physics | Science','authors':'Author One | Author Two',
            'shelf_location':'GLOBAL OLD STOCK','available_copies':999}
    db.books.insert_one(deepcopy(source)); before=fingerprint(db.books.find_one({'work_id':'OL901W'},{'_id':0}))
    payload=metadata(source)
    assert payload['subjects']==['Physics','Science'] and 'shelf_location' not in payload and 'available_copies' not in payload
    assert fingerprint(db.books.find_one({'work_id':'OL901W'},{'_id':0}))==before


def test_seed_creates_canonical_local_records(client,fresh):
    db.books.insert_one({'work_id':'OL901W','title':'Real Global Source','subjects':['Physics']})
    response=client.post('/libraries/'+fresh+'/inventory/books',headers={'x-test-user':'1'},json={
        'idempotency_key':str(uuid4()),'title':'Real Global Source','subjects':['Physics'],'global_work_id':'OL901W','copies':2,'shelf_location':'SCI-01'})
    assert response.status_code==201,response.text
    row=response.json(); assert row['global_work_id']=='OL901W' and row['holding']['total_copies']==2
    assert db.institution_library_books.find_one({'library_id':fresh,'library_book_id':row['library_book_id']})


def test_seed_avoids_existing_duplicates(client,fresh):
    db.books.insert_one({'work_id':'OL901W','title':'Already Owned Manual','subjects':['Science'],'book_id':1})
    payload={'idempotency_key':str(uuid4()),'title':'Already Owned Manual','subjects':['Science'],'copies':1,'global_work_id':'OL901W'}
    first=client.post('/libraries/'+fresh+'/inventory/books',headers={'x-test-user':'1'},json=payload)
    second=client.post('/libraries/'+fresh+'/inventory/books',headers={'x-test-user':'1'},json={**payload,'idempotency_key':str(uuid4())})
    assert first.status_code==201 and second.status_code==409
    assert db.institution_library_books.count_documents({'library_id':fresh})==1


def test_seed_holding_counts_valid(client,fresh):
    for count in [1,2,3]:
        response=client.post('/libraries/'+fresh+'/inventory/books',headers={'x-test-user':'1'},json={
            'idempotency_key':str(uuid4()),'title':f'QA Holding {count}','subjects':['Science'],'copies':count})
        assert response.status_code==201,response.text
        holding=response.json()['holding']; assert holding['total_copies']==count and 0<=holding['available_copies']<=count


def test_seed_shelf_is_local_only(client,fresh):
    db.books.insert_one({'work_id':'OL901W','title':'Source','subjects':['Science']})
    response=client.post('/libraries/'+fresh+'/inventory/books',headers={'x-test-user':'1'},json={
        'idempotency_key':str(uuid4()),'title':'Source','subjects':['Science'],'global_work_id':'OL901W','shelf_location':'TEST-SCI-01'})
    assert response.status_code==201,response.text
    assert response.json()['holding']['shelf_location']=='TEST-SCI-01'
    assert 'shelf_location' not in db.books.find_one({'work_id':'OL901W'})


def test_seed_local_only_books_valid(client,fresh):
    response=client.post('/libraries/'+fresh+'/inventory/books',headers={'x-test-user':'1'},json={
        'idempotency_key':str(uuid4()),'title':'TEST Community Handbook','subjects':['Local history']})
    assert response.status_code==201,response.text
    book=response.json(); assert book['global_work_id'] is None and book['isbn_10'] is None and book['isbn_13'] is None


def test_test_library_source_local_after_seed(client,fresh):
    response=client.post('/libraries/'+fresh+'/inventory/books',headers={'x-test-user':'1'},json={
        'idempotency_key':str(uuid4()),'title':'Seed Manual','subjects':['Science']})
    assert response.status_code==201,response.text
    source=client.get('/libraries/'+fresh+'/catalogue/source',headers={'x-test-user':'1'}).json()
    assert source['catalogue_source']=='LIBRARY_LOCAL' and source['local_book_count']==1
