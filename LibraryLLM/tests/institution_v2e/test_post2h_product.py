"""Online-only analytics regression, provenance and exact tenant/count boundaries."""
from uuid import uuid4
from datetime import datetime,timezone,timedelta
import pytest
from backend.services import library_analytics_service as analytics
from test_analytics import member

def add(client,lid,physical=False):
    r=client.post(f'/libraries/{lid}/inventory/books',json={'title':'Intentional online record','subjects':['Networks'],
        'create_physical_holding':physical,'copies':1 if physical else 0,'idempotency_key':str(uuid4())})
    assert r.status_code==201,r.text
    return r.json()
def get(client,lid,user=1,range='30d'):
    return client.get(f'/libraries/{lid}/analytics',params={'range':range},headers={'x-test-user':str(user)})

def test_staff_analytics_test_library_loads(client,library):
    lid=library();add(client,lid,True);add(client,lid)
    response=get(client,lid);assert response.status_code==200,response.text
    assert response.json()['overview']['active_books']==2 and response.json()['collection']['total_holding_quantity']==1

def test_staff_analytics_empty_activity_returns_zero(client,library):
    lid=library();add(client,lid)
    result=get(client,lid);assert result.status_code==200,result.text
    assert result.json()['circulation']['active_loans']==0 and result.json()['overview']['pending_borrow_requests']==0
    assert result.json()['collection']['requestable_units']==0

@pytest.mark.parametrize('key',['7d','30d','90d','all'])
def test_staff_analytics_supported_ranges_online_only(client,library,key):
    lid=library();add(client,lid);result=get(client,lid,range=key)
    assert result.status_code==200 and result.json()['range']['key']==key

def test_staff_analytics_30_day_range():
    stamp=datetime(2026,10,13,23,59,tzinfo=timezone.utc);window=analytics.span('30d',stamp)
    assert window['start_at']==datetime(2026,9,14,tzinfo=timezone.utc) and window['end_at']==stamp

def test_staff_analytics_invalid_range_denied(client,library):
    assert get(client,library(),range='today-ish').status_code==422

def test_staff_analytics_tenant_scoped(client,library):
    a,b=library(),library(name='Other');add(client,a);add(client,b,True)
    assert get(client,a).json()['overview']['active_books']==1
    assert get(client,a).json()['collection']['total_holding_quantity']==0

def test_staff_analytics_no_legacy_lib001(client,library,database):
    lid=library();add(client,lid)
    database.books.insert_one({'work_id':'OL1W','title':'Legacy filler','library_id':'LIB001','total_copies':999})
    assert get(client,lid).json()['overview']['active_books']==1

def test_staff_analytics_no_global_fallback(client,library,database):
    lid=library();database.books.insert_one({'work_id':'OL1W','title':'Global filler'})
    assert get(client,lid).json()['overview']['active_books']==0

@pytest.mark.parametrize('role,user',[('ADMIN',1),('LIBRARIAN',3)])
def test_staff_analytics_current_staff_allowed(client,library,database,role,user):
    lid=library();add(client,lid)
    if user!=1:member(database,lid,user,role)
    assert get(client,lid,user).status_code==200

def test_staff_analytics_general_user_denied(client,library,database):
    lid=library();member(database,lid,2)
    assert get(client,lid,2).status_code==403

def test_platform_only_analytics_denied(client,library,database):
    lid=library();database.platform_role_assignments.insert_one({'user_id':10,'role':'PLATFORM_ADMIN','status':'ACTIVE'})
    assert get(client,lid,10).status_code in [403,404]

def test_missing_physical_holding_still_requires_reconciliation(client,library,database):
    lid=library();row=add(client,lid,True)
    database.institution_holdings.delete_one({'library_book_id':row['library_book_id']})
    assert get(client,lid).status_code==503

def test_unstocked_book_with_physical_allocation_still_denied(client,library,database):
    lid=library();row=add(client,lid)
    database.institution_loans.insert_one({'library_id':lid,'library_book_id':row['library_book_id'],'status':'ACTIVE'})
    assert get(client,lid).status_code==503

def test_online_only_not_counted_as_physical_circulating(client,library):
    lid=library();add(client,lid);result=get(client,lid)
    assert result.status_code==200 and result.json()['collection']['circulation_status']['CIRCULATING']==0
