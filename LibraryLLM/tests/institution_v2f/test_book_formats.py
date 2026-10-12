from uuid import uuid4
import pytest


@pytest.fixture
def format_library(library,client):
    library_id=library()
    assert client.post(f'/libraries/{library_id}/join',headers={'x-test-user':'2'},json={}).status_code==200
    return library_id


def create(client,lib,physical=True):
    r=client.post(f'/libraries/{lib}/inventory/books',json={'title':'Format fixture '+uuid4().hex,'subjects':['Reference'],
        'idempotency_key':str(uuid4()),'create_physical_holding':physical,'copies':2 if physical else 0})
    assert r.status_code==201,r.text
    return r.json()


def detail(client,lib,book):
    r=client.get(f'/libraries/{lib}/inventory/books/{book["library_book_id"]}')
    assert r.status_code==200,r.text
    return r.json()


def attach(upload,ready,lib,book):
    r=upload(lib,book_id=book['library_book_id']);assert r.status_code==202,r.text
    asset=r.json();ready(asset);return asset


def test_format_derived_physical(client,format_library):
    book=create(client,format_library)
    assert detail(client,format_library,book)['book_format']=='PHYSICAL_ONLY'


def test_online_does_not_create_holding(client,format_library,database):
    book=create(client,format_library,False)
    assert book['holding'] is None
    assert database.institution_holdings.count_documents({'library_book_id':book['library_book_id']})==0
    assert database.institution_copies.count_documents({'library_book_id':book['library_book_id']})==0
    assert detail(client,format_library,book)['book_format']=='UNAVAILABLE'
    assert 'create_physical_holding' not in database.institution_library_books.find_one({'library_book_id':book['library_book_id']})


def test_format_derived_online(client,format_library,upload,ready):
    book=create(client,format_library,False);attach(upload,ready,format_library,book)
    result=detail(client,format_library,book)
    assert result['book_format']=='DIGITAL_ONLY' and result['has_online'] and not result['has_physical']


def test_format_derived_physical_online(client,format_library,upload,ready):
    book=create(client,format_library);attach(upload,ready,format_library,book)
    assert detail(client,format_library,book)['book_format']=='PHYSICAL_AND_DIGITAL'


@pytest.mark.parametrize('state',['PROCESSING','FAILED'])
def test_processing_asset_does_not_count_as_online_available(client,format_library,upload,database,state):
    book=create(client,format_library,False);a=upload(format_library,book_id=book['library_book_id']).json()
    database.institution_library_assets.update_one({'asset_id':a['asset_id']},{'$set':{'status':state}})
    assert detail(client,format_library,book)['book_format']=='UNAVAILABLE'
    r=client.get(f'/libraries/{format_library}/catalogue/books',headers={'x-test-user':'2'})
    assert r.status_code==200 and not r.json()['results']


def test_deleted_final_asset_removes_online_capability(client,format_library,upload,ready):
    book=create(client,format_library,False);a=attach(upload,ready,format_library,book)
    assert client.delete(f'/libraries/{format_library}/assets/{a["asset_id"]}').status_code==200
    assert detail(client,format_library,book)['book_format']=='UNAVAILABLE'


def test_add_online_preserves_library_book_id_accession_holding(client,format_library,upload,ready,database):
    book=create(client,format_library)
    before=database.institution_holdings.find_one({'library_book_id':book['library_book_id']})
    attach(upload,ready,format_library,book);row=detail(client,format_library,book)
    assert row['library_book_id']==book['library_book_id'] and row['accession_number']==book['accession_number']
    assert database.institution_holdings.find_one({'library_book_id':book['library_book_id']})==before
    assert database.institution_library_books.count_documents({'library_id':format_library})==1


def test_online_add_physical_becomes_both(client,format_library,upload,ready,database):
    book=create(client,format_library,False);attach(upload,ready,format_library,book)
    payload={'idempotency_key':str(uuid4()),'total_copies':3,'unavailable_stock':0,'allocation_mode':'AGGREGATE','circulation_status':'CIRCULATING'}
    path=f'/libraries/{format_library}/staff/lending/books/{book["library_book_id"]}/stock'
    response=client.put(path,json=payload);assert response.status_code==200,response.text
    assert client.put(path,json=payload).status_code==200
    assert database.institution_holdings.count_documents({'library_book_id':book['library_book_id']})==1
    assert detail(client,format_library,book)['book_format']=='PHYSICAL_AND_DIGITAL'


@pytest.mark.parametrize('mode',['PHYSICAL_ONLY','DIGITAL_ONLY','PHYSICAL_AND_DIGITAL'])
def test_inventory_format_filter(client,format_library,upload,ready,mode):
    p=create(client,format_library);o=create(client,format_library,False);both=create(client,format_library)
    attach(upload,ready,format_library,o);attach(upload,ready,format_library,both)
    r=client.get(f'/libraries/{format_library}/inventory/books?format={mode}&limit=1')
    assert r.status_code==200 and r.json()['total']==1 and len(r.json()['results'])==1
    assert r.json()['results'][0]['book_format']==mode


def test_online_book_no_request_action(client,format_library,upload,ready):
    book=create(client,format_library,False);attach(upload,ready,format_library,book)
    r=client.get(f'/libraries/{format_library}/catalogue/books/{book["library_book_id"]}',headers={'x-test-user':'2'})
    assert r.status_code==200,r.text
    row=r.json()['book'];assert row['book_format']=='DIGITAL_ONLY' and row['availability'] is None
    assert not row['actions']['request'] and not row['actions']['reserve']
    assert row['online_asset_id']


def test_staff_only_online_asset_not_exposed_to_patron(client,format_library,upload,ready):
    book=create(client,format_library,False);a=upload(format_library,book_id=book['library_book_id'],visibility='STAFF_ONLY').json();ready(a)
    assert detail(client,format_library,book)['book_format']=='DIGITAL_ONLY'
    assert client.get(f'/libraries/{format_library}/catalogue/books/{book["library_book_id"]}',headers={'x-test-user':'2'}).status_code==404


def test_online_rejects_fake_stock_and_shelf(client,format_library):
    for patch in [{'copies':1},{'shelf_location':'Fake shelf'},{'barcode':'Fake copy'}]:
        r=client.post(f'/libraries/{format_library}/inventory/books',json={'title':'Invalid online','subjects':['Reference'],
            'create_physical_holding':False,'copies':0,'idempotency_key':str(uuid4()),**patch})
        assert r.status_code==422


def test_lost_physical_holding_is_not_silently_recreated(client,format_library,database):
    book=create(client,format_library)
    database.institution_holdings.delete_one({'library_book_id':book['library_book_id']})
    response=client.put(f'/libraries/{format_library}/staff/lending/books/{book["library_book_id"]}/stock',
        json={'idempotency_key':str(uuid4()),'total_copies':1,'unavailable_stock':0,'allocation_mode':'AGGREGATE','circulation_status':'CIRCULATING'})
    assert response.status_code==409
    assert database.institution_holdings.count_documents({'library_book_id':book['library_book_id']})==0
