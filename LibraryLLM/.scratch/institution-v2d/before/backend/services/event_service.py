"""Core-owned events, first-publish lifecycle and bounded per-account seen receipts."""
from datetime import datetime, timedelta, timezone
import re
from backend.services.event_publish_validation import validate_publish, requires_published_validation
from uuid import uuid4

from fastapi import HTTPException
from jose import jwt, JWTError
from pydantic import ValidationError
from pymongo import ReturnDocument
from backend.database.mongodb import db, books_collection, users_collection
from backend.schemas.events import EventCreate
from backend.utils.jwt_utils import JWT_SECRET_KEY, JWT_ALGORITHM

events=db['events']
states=db['event_user_state']
WINDOW_DAYS=14
WINDOW_LIMIT=500
EDIT_FIELDS=set(EventCreate.model_fields)
PUBLIC_FIELDS=EDIT_FIELDS | {'event_id','status','created_at','updated_at','published_at','cancelled_at','archived_at'}

def now():
    return datetime.now(timezone.utc)

def utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value

def ensure_indexes():
    specifications=[(events,[('event_id',1)],True,'event_id_unique'),
        (events,[('status',1),('start_at',1)],False,'event_status_start'),
        (events,[('status',1),('published_at',-1),('event_id',1)],False,'event_status_publish'),
        (events,[('category',1),('status',1),('start_at',1)],False,'event_category_status_start'),
        (states,[('user_id',1)],True,'event_seen_user_unique')]
    for collection,keys,unique,name in specifications:
        existing=list(collection.list_indexes()) if collection.name in db.list_collection_names() else []
        same=[i for i in existing if list(i['key'].items())==keys]
        if same:
            if unique and not any(i.get('unique') for i in same):
                raise RuntimeError('Events require a unique identity index; conflicting index needs review.')
        else:
            collection.create_index(keys,unique=unique,name=name)

def validate_books(ids):
    if ids:
        found={r['work_id'] for r in books_collection.find({'work_id':{'$in':ids}},{'_id':0,'work_id':1})}
        if found!=set(ids):
            raise HTTPException(422,'One or more related books no longer exist in the catalogue.')

def document(event_id):
    row=events.find_one({'event_id':str(event_id)})
    if not row:
        raise HTTPException(404,'Event not found.')
    return row

def hydrate(rows,staff=False):
    ids=list(dict.fromkeys(wid for row in rows for wid in row.get('related_work_ids',[])))
    book_fields={'_id':0,'work_id':1,'title':1,'authors':1,'subjects':1,'cover_url':1,'average_rating':1}
    books={r['work_id']:r for r in books_collection.find({'work_id':{'$in':ids}},book_fields)} if ids else {}
    people={}
    if staff and rows:
        people_ids=list({r[k] for r in rows for k in ['created_by_user_id','updated_by_user_id']})
        people={r['user_id']:{k:r.get(k) for k in ['user_id','name','email']} for r in users_collection.find(
            {'user_id':{'$in':people_ids}},{'_id':0,'user_id':1,'name':1,'email':1})}
    output=[]
    for row in rows:
        result={k:utc(v) if isinstance(v,datetime) else v for k,v in row.items() if k in PUBLIC_FIELDS}
        result['related_books']=[books[wid] for wid in row.get('related_work_ids',[]) if wid in books]
        result['missing_related_work_ids']=[wid for wid in row.get('related_work_ids',[]) if wid not in books]
        if staff:
            result.update(created_by_user_id=row['created_by_user_id'],updated_by_user_id=row['updated_by_user_id'],
                created_by=people.get(row['created_by_user_id']),updated_by=people.get(row['updated_by_user_id']))
        output.append(result)
    return output

def create(body,actor):
    data=body.model_dump(mode='python')
    data['category']=body.category.value
    validate_books(data['related_work_ids'])
    stamp=now()
    row={**data,'event_id':str(uuid4()),'status':'DRAFT','created_by_user_id':actor,'updated_by_user_id':actor,
         'created_at':stamp,'updated_at':stamp,'published_at':None,'cancelled_at':None,'archived_at':None,'revision':0}
    events.insert_one(row)
    return hydrate([row],True)[0]

def edit(event_id,body,actor):
    old=document(event_id)
    if old['status']=='ARCHIVED':
        raise HTTPException(409,'Archived events are read-only.')
    changes=body.model_dump(exclude_unset=True,mode='python')
    try:
        merged=EventCreate.model_validate({**{k:utc(v) if isinstance(v,datetime) else v for k,v in old.items() if k in EDIT_FIELDS},**changes})
    except ValidationError as error:
        raise HTTPException(422,'Invalid event fields or date range. End time cannot be before start time.') from error
    validate_books(merged.related_work_ids)
    values=merged.model_dump(mode='python');values['category']=merged.category.value
    if old['status']=='PUBLISHED' and requires_published_validation(old,values):
        validate_publish(values)
    values.update(updated_at=now(),updated_by_user_id=actor)
    row=events.find_one_and_update({'event_id':str(event_id),'revision':old['revision']},
        {'$set':values,'$inc':{'revision':1}},return_document=ReturnDocument.AFTER)
    if not row:
        raise HTTPException(409,'The event changed. Refresh before editing again.')
    return hydrate([row],True)[0]

def transition(event_id,operation,actor):
    old=document(event_id)
    target={'publish':'PUBLISHED','cancel':'CANCELLED','archive':'ARCHIVED'}[operation]
    allowed={'publish':{'DRAFT'},'cancel':{'PUBLISHED'},'archive':{'PUBLISHED','CANCELLED'}}[operation]
    if old['status']==target:
        return hydrate([old],True)[0]  # Idempotent; never reset first publication.
    if old['status'] not in allowed:
        raise HTTPException(409,'This status transition is not available.')
    if operation=='publish':
        validate_publish(old)
        validate_books(old['related_work_ids'])
    stamp=now()
    field={'publish':'published_at','cancel':'cancelled_at','archive':'archived_at'}[operation]
    row=events.find_one_and_update({'event_id':str(event_id),'revision':old['revision'],'status':old['status']},
        {'$set':{'status':target,field:stamp,'updated_at':stamp,'updated_by_user_id':actor},'$inc':{'revision':1}},
        return_document=ReturnDocument.AFTER)
    if not row:
        raise HTTPException(409,'The event changed. Refresh before trying again.')
    return hydrate([row],True)[0]

def delete_draft(event_id):
    row=document(event_id)
    if row['status']!='DRAFT':
        raise HTTPException(409,'Only drafts can be deleted. Cancel or archive published events.')
    if events.delete_one({'event_id':str(event_id),'status':'DRAFT','revision':row['revision']}).deleted_count!=1:
        raise HTTPException(409,'The event changed. Refresh before trying again.')
    return {'deleted':True}

def listing(view,category,query,featured,page,page_size,status=None,sort='updated',staff=False):
    match={}
    if category:match['category']=category
    if query.strip():
        pattern=re.escape(query.strip())
        match['$or']=[{'title':{'$regex':pattern,'$options':'i'}},{'summary':{'$regex':pattern,'$options':'i'}}]
    if featured is not None:match['featured']=featured
    stamp=now()
    if staff:
        if status:match['status']=status
        ordering={'updated':[('updated_at',-1),('event_id',1)],'created':[('created_at',-1),('event_id',1)],
                  'start':[('start_at',1),('event_id',1)]}[sort]
        rows=list(events.find(match).sort(ordering).skip((page-1)*page_size).limit(page_size))
    else:
        match['status']='PUBLISHED'
        dated={'$or':[{'end_at':{'$gte':stamp}}, {'end_at':None,'start_at':{'$gte':stamp}},
                      {'end_at':None,'start_at':None}]} if view=='upcoming' else {
            '$or':[{'end_at':{'$lt':stamp}}, {'end_at':None,'start_at':{'$lt':stamp}}]}
        match={'$and':[match,dated]}
        pipeline=[{'$match':match},{'$addFields':{'effective_date':{'$ifNull':['$end_at','$start_at']},
                  'upcoming_sort':{'$ifNull':['$start_at',datetime(9999,1,1,tzinfo=timezone.utc)]}}},
                  {'$sort':{'featured':-1,'upcoming_sort':1,'published_at':-1,'event_id':1} if view=='upcoming'
                   else {'effective_date':-1,'published_at':-1,'event_id':1}},
                  {'$skip':(page-1)*page_size},{'$limit':page_size}]
        rows=list(events.aggregate(pipeline))
    count=events.count_documents(match)
    return {'events':hydrate(rows,staff),'count':count,'page':page,'page_size':page_size,'has_more':page*page_size<count}

def recent():
    return list(events.find({'status':'PUBLISHED','published_at':{'$gte':now()-timedelta(days=WINDOW_DAYS)}},
                {'_id':0,'event_id':1,'title':1,'category':1,'published_at':1})
                .sort([('published_at',-1),('event_id',1)]).limit(WINDOW_LIMIT+1))

def state(user_id,rows):
    existing=states.find_one({'user_id':user_id})
    if existing:return existing
    # First access establishes an exact snapshot baseline; future publication,
    # including an equal-timestamp UUID, remains unseen until explicitly seen.
    states.update_one({'user_id':user_id},{'$setOnInsert':{'user_id':user_id,
        'seen_event_ids':[r['event_id'] for r in rows[:WINDOW_LIMIT]],'revision':0,
        'initialized_at':now(),'updated_at':now(),'last_seen_published_at':None,'last_seen_event_id':None}},upsert=True)
    return states.find_one({'user_id':user_id})

def receipt(rows,user):
    return jwt.encode({'kind':'events_seen','sub':str(user['sub']),'sid':user.get('sid','legacy'),
        'ids':[r['event_id'] for r in rows[:WINDOW_LIMIT]],'exp':now()+timedelta(minutes=10)},JWT_SECRET_KEY,algorithm=JWT_ALGORITHM)

def unseen(user):
    rows=recent();seen=state(int(user['sub']),rows)
    pending=[r for r in rows[:WINDOW_LIMIT] if r['event_id'] not in set(seen['seen_event_ids'])]
    latest=pending[0] if pending else None
    return {'count':len(pending),'count_capped':len(rows)>WINDOW_LIMIT,
        'latest_event':{k:utc(v) if isinstance(v,datetime) else v for k,v in latest.items()} if latest else None,
        'event_ids':[r['event_id'] for r in pending], 'seen_cursor':receipt(pending,user)}

def mark_seen(cursor,user):
    try:
        data=jwt.decode(cursor,JWT_SECRET_KEY,algorithms=[JWT_ALGORITHM],options={'require_exp':True})
        if data.get('kind')!='events_seen' or data.get('sub')!=str(user['sub']) or data.get('sid')!=user.get('sid','legacy'):
            raise ValueError('Wrong seen receipt owner')
        ids=data['ids']
        if not isinstance(ids,list) or len(ids)>WINDOW_LIMIT or any(not isinstance(v,str) for v in ids):
            raise ValueError('Invalid seen receipt')
    except (JWTError,ValueError,KeyError) as error:
        raise HTTPException(422,'This event receipt is invalid or expired. Reload Events.') from error
    rows=recent();allowed={r['event_id'] for r in rows[:WINDOW_LIMIT]};valid=set(ids)&allowed
    for _ in range(5):
        current=state(int(user['sub']),rows)
        merged=(set(current['seen_event_ids'])&allowed)|valid
        ordered=[r for r in rows[:WINDOW_LIMIT] if r['event_id'] in merged]
        values={'seen_event_ids':[r['event_id'] for r in ordered],'updated_at':now()}
        if ordered:
            values.update(last_seen_published_at=ordered[0]['published_at'],last_seen_event_id=ordered[0]['event_id'])
        result=states.update_one({'user_id':int(user['sub']),'revision':current['revision']},
            {'$set':values,'$inc':{'revision':1}})
        if result.matched_count:return unseen(user)
    raise HTTPException(409,'Seen state changed. Reload Events and try again.')
