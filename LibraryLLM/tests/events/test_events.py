"""Events V1: real Mongo in disposable DB; no production event/account mutations."""
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.database.mongodb import client as mongo
from backend.dependencies import get_current_user
from backend.routes.events import router,staff_router
from backend.services import event_service as es,identity_service

NOW=datetime(2026,10,6,12,tzinfo=timezone.utc)

@pytest.fixture
def isolated(monkeypatch):
    name='luminar_events_test_'+uuid4().hex
    db=mongo[name]
    monkeypatch.setattr(es,'db',db);monkeypatch.setattr(es,'events',db.events);monkeypatch.setattr(es,'states',db.event_user_state)
    monkeypatch.setattr(es,'books_collection',db.books);monkeypatch.setattr(es,'users_collection',db.users)
    monkeypatch.setattr(identity_service,'users_collection',db.users)
    monkeypatch.setattr(es,'now',lambda:NOW)
    db.users.insert_many([{'user_id':uid,'name':'Test','email':f'u{uid}@test.invalid','role':role,
        'is_active':True,'is_email_verified':True} for uid,role in [(1,'ADMIN'),(2,'LIBRARIAN'),(3,'GENERAL_USER'),(4,'GENERAL_USER')]])
    db.books.insert_many([{'work_id':f'OL{i}W','title':f'Book {i}','authors':'Test Author'} for i in range(1,15)])
    es.ensure_indexes()
    app=FastAPI();app.include_router(router);app.include_router(staff_router)
    yield db,app
    mongo.drop_database(name)

def http(fixture,uid=1,sid='session',claimed='ADMIN'):
    db,app=fixture
    app.dependency_overrides[get_current_user]=lambda:{'sub':str(uid),'sid':sid,'role':claimed}
    return TestClient(app)

def create(fixture,uid=1,**fields):
    return http(fixture,uid).post('/staff/events',json={'title':'Library program','category':'OTHER',**fields})

def publish(fixture,uid=1,**fields):
    row=create(fixture,uid,**fields).json()
    return http(fixture,uid).post('/staff/events/'+row['event_id']+'/publish')

def unseen(fixture,uid=3):
    return http(fixture,uid).get('/events/unseen').json()

@pytest.mark.parametrize('uid',[1,2])
def test_event_create_admin_and_librarian(isolated,uid):
    response=create(isolated,uid,related_work_ids=['OL2W','OL1W'])
    assert response.status_code==201
    row=response.json();assert row['status']=='DRAFT' and row['created_by_user_id']==uid
    assert UUID(row['event_id']).version==4 and row['published_at'] is None
    assert [r['work_id'] for r in row['related_books']]==['OL2W','OL1W']
    stored=isolated[0].events.find_one({'event_id':row['event_id']})
    assert 'related_books' not in stored and 'authors' not in stored

@pytest.mark.parametrize('action',['create','edit','publish','cancel','archive','delete','manage','detail'])
def test_general_user_cannot_manage_even_with_claimed_admin(isolated,action):
    row=create(isolated).json();id=row['event_id'];client=http(isolated,3,claimed='ADMIN')
    responses={'create':lambda:client.post('/staff/events',json={'title':'Test Event','category':'OTHER'}),
        'edit':lambda:client.patch('/staff/events/'+id,json={'title':'Edited Event'}),
        'delete':lambda:client.delete('/staff/events/'+id),'manage':lambda:client.get('/staff/events'),
        'detail':lambda:client.get('/staff/events/'+id)}
    response=responses[action]() if action in responses else client.post('/staff/events/'+id+'/'+action)
    assert response.status_code==403

@pytest.mark.parametrize('field',['created_by_user_id','updated_by_user_id','status','published_at','event_id','user_id'])
def test_audit_and_status_fields_cannot_be_spoofed(isolated,field):
    assert create(isolated,**{field:1}).status_code==422
    row=create(isolated).json()
    assert http(isolated).patch('/staff/events/'+row['event_id'],json={field:1}).status_code==422

def test_draft_not_public_and_defaults_safe(isolated):
    row=create(isolated).json()
    assert http(isolated,3).get('/events').json()['count']==0
    assert http(isolated,3).get('/events/'+row['event_id']).status_code==404

def test_publish_sets_immutable_date_and_current_metadata(isolated):
    row=publish(isolated,2,related_work_ids=['OL1W']).json()
    assert row['status']=='PUBLISHED' and datetime.fromisoformat(row['published_at']).utcoffset()==timedelta(0)
    isolated[0].books.update_one({'work_id':'OL1W'},{'$set':{'title':'Current title'}})
    result=http(isolated,3).get('/events/'+row['event_id']).json()
    assert result['related_books'][0]['title']=='Current title'
    assert 'created_by_user_id' not in result and 'created_by' not in result
    edited=http(isolated,1).patch('/staff/events/'+row['event_id'],json={'description':'Correction','location':'New room'})
    assert edited.status_code==200 and edited.json()['published_at']==row['published_at']
    assert edited.json()['created_by_user_id']==2 and edited.json()['updated_by_user_id']==1
    assert http(isolated).post('/staff/events/'+row['event_id']+'/publish').json()['published_at']==row['published_at']

def test_delete_only_draft(isolated):
    row=create(isolated).json()
    assert http(isolated).delete('/staff/events/'+row['event_id']).status_code==200
    row=publish(isolated).json()
    assert http(isolated).delete('/staff/events/'+row['event_id']).status_code==409

def test_cancel_and_archive_history_visibility(isolated):
    row=publish(isolated).json();id=row['event_id']
    assert http(isolated,2).post('/staff/events/'+id+'/cancel').json()['status']=='CANCELLED'
    assert http(isolated,3).get('/events/'+id).json()['status']=='CANCELLED'
    assert http(isolated,3).get('/events').json()['count']==0
    assert http(isolated,2).post('/staff/events/'+id+'/archive').json()['status']=='ARCHIVED'
    assert http(isolated,3).get('/events/'+id).status_code==404
    assert http(isolated).patch('/staff/events/'+id,json={'title':'Edited archive'}).status_code==409
    assert http(isolated).post('/staff/events/'+id+'/publish').status_code==409
    assert http(isolated).get('/staff/events?status=ARCHIVED').json()['count']==1

@pytest.mark.parametrize('fields',[{'title':'a'},{'title':' '},{'title':'x'*141},{'summary':'x'*301},
    {'description':'x'*5001},{'location':'x'*201},{'category':'FREE_TEXT'},{'featured':'yes'},
    {'start_at':'2026-10-08T12:00:00'}, {'start_at':'2026-10-08T12:00:00Z','end_at':'2026-10-07T12:00:00Z'},
    {'end_at':'2026-10-08T12:00:00Z'},{'related_work_ids':['OL1W','OL1W']},
    {'related_work_ids':['missing']},{'related_work_ids':[f'OL{i}W' for i in range(1,14)]}])
def test_event_validation(isolated,fields):
    assert create(isolated,**fields).status_code==422 and isolated[0].events.count_documents({})==0

def test_patch_merged_date_validation_and_utc(isolated):
    row=create(isolated,start_at='2026-10-08T17:30:00+05:30',end_at='2026-10-08T18:30:00+05:30').json()
    assert datetime.fromisoformat(row['start_at'])==datetime(2026,10,8,12,tzinfo=timezone.utc)
    assert http(isolated).patch('/staff/events/'+row['event_id'],json={'end_at':'2026-10-08T11:00:00Z'}).status_code==422
    assert http(isolated).patch('/staff/events/'+row['event_id'],json={'start_at':None,'end_at':None}).status_code==200

def test_unknown_related_set_rejected_and_removed_catalogue_at_publish(isolated):
    assert create(isolated,related_work_ids=['OL1W','bad']).status_code==422
    row=create(isolated,related_work_ids=['OL1W']).json()
    isolated[0].books.delete_one({'work_id':'OL1W'})
    assert http(isolated).post('/staff/events/'+row['event_id']+'/publish').status_code==422
    assert isolated[0].events.find_one({'event_id':row['event_id']})['status']=='DRAFT'

def test_upcoming_past_featured_category_search_pagination(isolated):
    future=(NOW+timedelta(days=1)).isoformat();past=(NOW-timedelta(days=1)).isoformat()
    rows=[publish(isolated,title='Workshop future',start_at=future).json(),
          publish(isolated,title='Workshop featured',featured=True,start_at=future).json(),
          publish(isolated,title='New titles',category='NEW_ARRIVALS',related_work_ids=['OL1W']).json(),
          publish(isolated,title='Finished program',start_at=past).json(),
          publish(isolated,title='Ongoing program',start_at=past,end_at=future).json()]
    data=http(isolated,3).get('/events?page_size=2').json()
    assert data['count']==4 and data['has_more'] and data['events'][0]['event_id']==rows[1]['event_id']
    second=http(isolated,3).get('/events?page_size=2&page=2').json()
    assert not set(r['event_id'] for r in data['events'])&set(r['event_id'] for r in second['events'])
    assert http(isolated,3).get('/events?view=past').json()['events'][0]['event_id']==rows[3]['event_id']
    assert http(isolated,3).get('/events?category=NEW_ARRIVALS').json()['count']==1
    assert http(isolated,3).get('/events?query=WORKSHOP').json()['count']==2
    assert http(isolated,3).get('/events?query=.*').json()['count']==0
    assert http(isolated,3).get('/events?featured=true').json()['count']==1
    assert http(isolated,3).get('/events?page_size=51').status_code==422

def test_new_publish_unseen_mark_seen_equal_timestamp_race_and_edit(isolated):
    assert unseen(isolated)['count']==0
    unseen(isolated,4)
    draft=create(isolated).json();assert unseen(isolated)['count']==0
    http(isolated).post('/staff/events/'+draft['event_id']+'/publish')
    snapshot=unseen(isolated);assert snapshot['count']==1
    # A new publication shares exactly the same millisecond but isn't in the
    # issued receipt; advancing state must not hide it.
    second=publish(isolated,title='Second event').json()
    result=http(isolated,3).post('/events/mark-seen',json={'cursor':snapshot['seen_cursor']})
    assert result.json()['count']==1 and result.json()['latest_event']['event_id']==second['event_id']
    assert unseen(isolated,4)['count']==2
    assert http(isolated,3).post('/events/mark-seen',json={'cursor':result.json()['seen_cursor']}).json()['count']==0
    http(isolated).patch('/staff/events/'+second['event_id'],json={'description':'Correction'})
    assert unseen(isolated)['count']==0 and isolated[0].event_user_state.count_documents({})==2
    assert isolated[0]['notifications'].count_documents({})==0

def test_seen_receipt_private_and_extra_user_id_forbidden(isolated):
    unseen(isolated);unseen(isolated,4);publish(isolated)
    receipt=unseen(isolated)['seen_cursor']
    assert http(isolated,4).post('/events/mark-seen',json={'cursor':receipt}).status_code==422
    assert http(isolated,3,sid='another').post('/events/mark-seen',json={'cursor':receipt}).status_code==422
    assert http(isolated,3).post('/events/mark-seen',json={'cursor':receipt,'user_id':4}).status_code==422
    assert http(isolated,3).post('/events/mark-seen',json={'cursor':'forged'}).status_code==422
    assert unseen(isolated)['count']==1 and unseen(isolated,4)['count']==1

def test_cancelled_archived_unseen_and_new_user_backlog(isolated):
    unseen(isolated)
    row=publish(isolated).json()
    assert unseen(isolated)['count']==1
    assert unseen(isolated,4)['count']==0  # First access seeds historic backlog.
    http(isolated).post('/staff/events/'+row['event_id']+'/cancel')
    assert unseen(isolated)['count']==0
    http(isolated).post('/staff/events/'+row['event_id']+'/archive')
    assert unseen(isolated)['count']==0

def test_seen_window_and_bounded_state(isolated):
    unseen(isolated)
    for i in range(505):
        isolated[0].events.insert_one({'event_id':str(uuid4()),'title':f'Event {i}','category':'OTHER','status':'PUBLISHED','published_at':NOW})
    result=unseen(isolated)
    assert result['count']==500 and result['count_capped']
    assert http(isolated,3).post('/events/mark-seen',json={'cursor':result['seen_cursor']}).json()['count']==0
    assert len(isolated[0].event_user_state.find_one({'user_id':3})['seen_event_ids'])==500
    isolated[0].events.update_many({}, {'$set':{'published_at':NOW-timedelta(days=15)}})
    assert unseen(isolated)['count']==0

def test_indexes_idempotent(isolated):
    before=list(isolated[0].events.list_indexes());es.ensure_indexes()
    assert list(isolated[0].events.list_indexes())==before and len(before)==5
    assert len(list(isolated[0].event_user_state.list_indexes()))==2

def test_invalid_identity_and_missing_event(isolated):
    isolated[0].users.update_one({'user_id':3},{'$set':{'is_active':False}})
    assert http(isolated,3).get('/events').status_code==401
    assert http(isolated,1).get('/events/'+str(uuid4())).status_code==404
    assert http(isolated,1).get('/events/not-a-uuid').status_code==422


def test_expired_receipt_rejected_without_advancing_seen(isolated):
    from jose import jwt
    unseen(isolated);publish(isolated)
    receipt=jwt.encode({'kind':'events_seen','sub':'3','sid':'session','ids':[],
        'exp':datetime.now(timezone.utc)-timedelta(minutes=1)},es.JWT_SECRET_KEY,algorithm=es.JWT_ALGORITHM)
    assert http(isolated,3).post('/events/mark-seen',json={'cursor':receipt}).status_code==422
    assert unseen(isolated)['count']==1


def test_concurrent_publish_immutable_single_signal(isolated):
    row=create(isolated).json();unseen(isolated)
    def publish_once(_):
        try:return es.transition(row['event_id'],'publish',1)['published_at']
        except Exception as error:
            assert getattr(error,'status_code',None)==409
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        stamps=[s for s in pool.map(publish_once,range(2)) if s]
    assert len(set(stamps))==1 and unseen(isolated)['count']==1
    stored=isolated[0].events.find_one({'event_id':row['event_id']})
    assert stored['revision']==1


def test_concurrent_seen_receipts_union_without_losing_ids(isolated):
    unseen(isolated);one=publish(isolated).json();two=publish(isolated).json()
    user={'sub':'3','sid':'session'}
    receipts=[es.receipt([{'event_id':r['event_id']}],user) for r in [one,two]]
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda cursor:es.mark_seen(cursor,user),receipts))
    assert unseen(isolated)['count']==0
    assert len(isolated[0].event_user_state.find_one({'user_id':3})['seen_event_ids'])==2


def test_list_hydrates_books_and_staff_in_single_batch(isolated,monkeypatch):
    from unittest.mock import Mock
    rows=[create(isolated,related_work_ids=['OL1W','OL2W']).json() for _ in range(12)]
    documents=list(isolated[0].events.find({'event_id':{'$in':[r['event_id'] for r in rows]}}))
    books=Mock(wraps=isolated[0].books);people=Mock(wraps=isolated[0].users)
    monkeypatch.setattr(es,'books_collection',books);monkeypatch.setattr(es,'users_collection',people)
    hydrated=es.hydrate(documents,True)
    assert len(hydrated)==12 and books.find.call_count==people.find.call_count==1
    assert set(books.find.call_args.args[0]['work_id']['$in'])=={'OL1W','OL2W'}


def test_publication_during_page_read_is_not_acknowledged(isolated,monkeypatch):
    unseen(isolated);draft=create(isolated).json()
    listing=es.listing
    def publish_after_rows(*args,**kwargs):
        result=listing(*args,**kwargs)
        es.transition(draft['event_id'],'publish',1)
        return result
    monkeypatch.setattr(es,'listing',publish_after_rows)
    page=http(isolated,3).get('/events').json()
    assert page['events']==[]
    marked=http(isolated,3).post('/events/mark-seen',json={'cursor':page['seen_cursor']})
    assert marked.json()['count']==1 and marked.json()['latest_event']['event_id']==draft['event_id']
