"""Current-user READY capability selection, no arbitrary resource or physical fake."""
from test_book_formats import format_library,create,attach
from uuid import uuid4

def patron(client,lid,bid):
    r=client.get(f'/libraries/{lid}/catalogue/books/{bid}',headers={'x-test-user':'2'})
    assert r.status_code==200,r.text
    return r.json()['book']
def test_online_read_uses_authorized_ready_asset(client,format_library,upload,ready):
    book=create(client,format_library,False);asset=attach(upload,ready,format_library,book)
    result=patron(client,format_library,book['library_book_id'])
    assert result['online_asset_id']==asset['asset_id'] and result['book_format']=='DIGITAL_ONLY'
    assert result['availability'] is None and result['shelf_location'] is None and not result['actions']['request']

def test_staff_only_asset_no_patron_read_action(client,format_library,upload,ready):
    book=create(client,format_library);r=upload(format_library,book_id=book['library_book_id'],visibility='STAFF_ONLY');ready(r.json())
    result=patron(client,format_library,book['library_book_id'])
    assert not result['has_online'] and result['online_asset_id'] is None and result['book_format']=='PHYSICAL_ONLY'
    assert client.get(f'/libraries/{format_library}/assets/{r.json()["asset_id"]}/file',headers={'x-test-user':'2'}).status_code in [403,404]

def test_members_asset_patron_read_action(client,format_library,upload,ready):
    book=create(client,format_library);asset=attach(upload,ready,format_library,book)
    result=patron(client,format_library,book['library_book_id'])
    assert result['has_online'] and result['has_physical'] and result['actions']['request']

def test_multiple_member_assets_require_explicit_choice(client,format_library,upload,ready,pdf_bytes):
    book=create(client,format_library);attach(upload,ready,format_library,book)
    r=upload(format_library,book_id=book['library_book_id'],content=pdf_bytes+b'\n% distinct fixture')
    assert r.status_code==202,r.text;ready(r.json())
    result=patron(client,format_library,book['library_book_id'])
    assert result['has_online'] and result['online_asset_id'] is None

def test_staff_only_not_selected_over_single_member_asset(client,format_library,upload,ready,pdf_bytes):
    book=create(client,format_library);member=attach(upload,ready,format_library,book)
    r=upload(format_library,book_id=book['library_book_id'],visibility='STAFF_ONLY',content=pdf_bytes+b'\n% staff-only');ready(r.json())
    assert patron(client,format_library,book['library_book_id'])['online_asset_id']==member['asset_id']

def test_revoked_membership_denied_before_content(client,format_library,upload,ready,database):
    book=create(client,format_library,False);asset=attach(upload,ready,format_library,book)
    database.institution_memberships.update_one({'library_id':format_library,'user_id':2},{'$set':{'status':'REMOVED'}})
    assert client.get(f'/libraries/{format_library}/assets/{asset["asset_id"]}/file',headers={'x-test-user':'2'}).status_code in [403,404]

def test_both_zero_physical_still_online(client,format_library,upload,ready,database):
    book=create(client,format_library);asset=attach(upload,ready,format_library,book)
    database.institution_holdings.update_one({'library_book_id':book['library_book_id']},{'$set':{'unavailable_stock':2}})
    result=patron(client,format_library,book['library_book_id'])
    assert result['requestable_count']==0 and result['has_online'] and result['online_asset_id']==asset['asset_id']

def saved(client,lid,bid):
    target=f'local:{lid}:{bid}'
    r=client.post('/reading-list/',headers={'x-test-user':'2'},json={'work_id':target})
    assert r.status_code==200,r.text
    r=client.get('/reading-list/my',headers={'x-test-user':'2'})
    assert r.status_code==200,r.text
    return r.json()['items'][0]

def test_reading_list_uses_current_authorized_capabilities(client,format_library,upload,ready):
    book=create(client,format_library,False);asset=attach(upload,ready,format_library,book)
    item=saved(client,format_library,book['library_book_id'])
    assert item['accessible']
    assert item['library_book']['online_asset_id']==asset['asset_id']
    assert item['library_book']['owned_by_current_library'] and not item['library_book']['has_physical']

def test_reading_list_cannot_promote_staff_only_asset(client,format_library,upload,ready):
    book=create(client,format_library);r=upload(format_library,book_id=book['library_book_id'],visibility='STAFF_ONLY');ready(r.json())
    item=saved(client,format_library,book['library_book_id'])
    assert item['accessible'] and not item['library_book']['has_online']

def test_reading_list_revocation_removes_current_capabilities(client,format_library,upload,ready,database):
    book=create(client,format_library,False);attach(upload,ready,format_library,book)
    saved(client,format_library,book['library_book_id'])
    database.institution_memberships.update_one({'library_id':format_library,'user_id':2},{'$set':{'status':'REMOVED'}})
    r=client.get('/reading-list/my',headers={'x-test-user':'2'})
    item=r.json()['items'][0]
    assert not item['accessible'] and item['library_book'] is None
    assert item['title']=='Unavailable library book'
