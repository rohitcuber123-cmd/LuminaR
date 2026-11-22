"""Immutable publications and bounded, restart-safe delivery via the shared inbox.

The single announcement document is the durable publication intent. A cursor
may lag a copied notice after failure; the existing unique dedupe key makes
replay safe. This is deliberately not a cross-document transaction claim.
"""
import re
from datetime import timedelta
from uuid import uuid4
from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.write_concern import WriteConcern
from backend.database.mongodb import db
from backend.services.institution_repository import collection, now, library_mutation
from backend.services.library_inventory_access import require_library_membership, eligible_actor
from backend.institution_dependencies import require_library_role
from backend.services.announcement_audience import member_query, can_read

KIND = 'ANNOUNCEMENT_PUBLISHED'
MAX_RECIPIENTS = 20000
FIELDS = ('announcement_id', 'library_id', 'title', 'body', 'category', 'priority', 'status',
          'created_at', 'updated_at', 'published_at', 'withdrawn_at', 'linked_event_id', 'revision', 'audience', 'recipient_user_id')

def records():
    return collection('announcements').with_options(write_concern=WriteConcern(w=1, j=True))

def ensure_indexes():
    records().create_index('announcement_id', unique=True)
    records().create_index([('library_id', 1), ('created_by_user_id', 1), ('request_id', 1)], unique=True)
    records().create_index([('library_id', 1), ('status', 1), ('published_at', -1), ('announcement_id', 1)])
    records().create_index([('delivery.state', 1), ('delivery.next_attempt_at', 1), ('published_at', 1)])
    # One shared inbox, existing globally unique dedupe_key remains authoritative.
    db.notifications.create_index([('user_id', 1), ('scope', 1), ('library_id', 1), ('read_at', 1), ('created_at', -1)])

def access(library_id, actor, *, staff=False, locked=False):
    identity = eligible_actor(actor)
    _, membership = require_library_membership(library_id, identity, locked=locked)
    if membership.get('role') not in ['ADMIN','LIBRARIAN','GENERAL_USER']:
        raise HTTPException(404, 'Library resource not found.')
    if staff:
        require_library_role(library_id, identity, 'ADMIN', locked=locked)
    return int(identity['sub'])

def document(library_id, announcement_id):
    row = records().find_one({'library_id': library_id, 'announcement_id': announcement_id})
    if not row:
        raise HTTPException(404, 'Announcement not found.')
    return row

def event_reference(library_id, event_id, *, publishing=False):
    if not event_id:
        return
    from backend.services.event_service import document as event_document
    event = event_document(str(event_id), library_id)
    if publishing and (event['status'] not in ['PUBLISHED', 'CANCELLED'] or not event.get('published_at')):
        raise HTTPException(409, 'Publish the linked event before this announcement.')

def recipient_metadata(library_id, ids):
    ids = eligible_recipients(library_id, list(set(ids))) if ids else []
    return {r['user_id']:{k:r.get(k,'') for k in ['user_id','name','email']} for r in db.users.find(
        {'user_id':{'$in':ids}}, {'_id':0,'user_id':1,'name':1,'email':1})} if ids else {}

def validate_target(library_id, values, *, status=422):
    scope=values.get('audience','ALL_ACTIVE_MEMBERS');uid=values.get('recipient_user_id')
    if scope=='ALL_ACTIVE_MEMBERS' and uid is None:return
    if scope!='SPECIFIC_MEMBER' or type(uid) is not int or uid<=0 or uid>9007199254740991 or eligible_recipients(library_id,[uid])!=[uid]:
        raise HTTPException(status, 'Selected member unavailable or recipient scope invalid.')

def search_recipients(library_id, actor, query, limit=10):
    # Start inside this tenant's indexed memberships, never a global directory.
    with library_mutation(library_id, wait_seconds=30):
        access(library_id, actor, staff=True, locked=True)
        pattern=re.escape(query.strip())
        if len(query.strip())<2:raise HTTPException(422, 'Enter at least two characters.')
        rows=list(collection('memberships').aggregate([
            {'$match':{'library_id':library_id,'status':'ACTIVE','role':{'$in':['ADMIN','LIBRARIAN','GENERAL_USER']},'user_id':{'$type':['int','long'],'$gt':0,'$lte':9007199254740991}}},
            {'$lookup':{'from':'users','localField':'user_id','foreignField':'user_id','as':'account'}},
            {'$unwind':'$account'},
            {'$match':{'account.is_active':{'$in':[None,True]},'account.is_email_verified':True,'account.password_setup_required':{'$in':[None,False]},
                'account.role':{'$in':['ADMIN','LIBRARIAN','GENERAL_USER']},'$or':[{'account.name':{'$regex':pattern,'$options':'i'}},{'account.email':{'$regex':pattern,'$options':'i'}}]}},
            {'$lookup':{'from':'institution_invitations','let':{'grant':'$grant_invitation_id','uid':'$user_id'},'pipeline':[
                {'$match':{'library_id':library_id,'status':'ACCEPTED','$expr':{'$and':[{'$eq':['$invitation_id','$$grant']},{'$eq':['$accepted_by_user_id','$$uid']}]}}},
                {'$limit':1},{'$project':{'_id':1}}],'as':'proof'}},
            {'$match':{'$or':[{'grant_invitation_id':None},{'grant_invitation_id':''},{'proof.0':{'$exists':True}}]}},
            {'$sort':{'account.name':1,'user_id':1}},{'$limit':limit+1},
            {'$project':{'_id':0,'user_id':1,'name':'$account.name','email':'$account.email'}}],maxTimeMS=3000))
        eligible=set(eligible_recipients(library_id,[r['user_id'] for r in rows]))
        rows=[r for r in rows if r['user_id'] in eligible]
        return {'library_id':library_id,'results':rows[:limit],'has_more':len(rows)>limit}


def present(row, staff=False, available_events=None, recipients=None):
    from backend.services.notification_service import normalize_dates
    value = {k: row.get(k) for k in FIELDS}
    value['linked_event_available'] = row.get('linked_event_id') in available_events if available_events is not None else bool(row.get('linked_event_id') and db.events.find_one({
        'event_id': row['linked_event_id'], 'library_id': row['library_id'], 'scope': 'LIBRARY',
        'status': {'$in': ['PUBLISHED', 'CANCELLED']}, 'published_at': {'$ne': None}}, {'_id': 1}))
    if staff:
        if row.get('audience')=='SPECIFIC_MEMBER':
            metadata=recipients if recipients is not None else recipient_metadata(row['library_id'],[row['recipient_user_id']] if type(row.get('recipient_user_id')) is int else [])
            value['recipient']=metadata.get(row.get('recipient_user_id'))
            value['recipient_unavailable']=value['recipient'] is None
        value.update({k:row.get(k) for k in ['created_by_user_id','updated_by_user_id','published_by_user_id','withdrawn_by_user_id']})
        value['delivery']={k:v for k,v in row.get('delivery', {}).items() if k != 'recipients'}
    return normalize_dates(value)

def listing(library_id, actor, *, staff=False, status=None, limit=20, offset=0):
    with library_mutation(library_id, wait_seconds=30):
        uid = access(library_id, actor, staff=staff, locked=True)
        query = {'library_id': library_id}
        if not staff: query.update({'status':'PUBLISHED',**member_query(uid)})
        elif status: query['status'] = status
        rows = list(records().find(query, {'delivery.recipients': 0}).sort([('published_at', -1), ('created_at', -1), ('announcement_id', 1)]).skip(offset).limit(limit))
        total = records().count_documents(query)
        event_ids=[r['linked_event_id'] for r in rows if r.get('linked_event_id')]
        available={r['event_id'] for r in db.events.find({'library_id':library_id,'scope':'LIBRARY','event_id':{'$in':event_ids},
            'status':{'$in':['PUBLISHED','CANCELLED']},'published_at':{'$ne':None}},{'event_id':1})} if event_ids else set()
        recipients=recipient_metadata(library_id,[r['recipient_user_id'] for r in rows if r.get('audience')=='SPECIFIC_MEMBER' and type(r.get('recipient_user_id')) is int]) if staff else {}
        return {'results': [present(r, staff,available,recipients) for r in rows], 'total': total, 'limit': limit, 'offset': offset, 'has_more': offset + limit < total}

def detail(library_id, announcement_id, actor, *, staff=False):
    with library_mutation(library_id, wait_seconds=30):
        uid = access(library_id, actor, staff=staff, locked=True)
        row = document(library_id, announcement_id)
        if not staff and (row['status'] != 'PUBLISHED' or not can_read(row,uid)):
            raise HTTPException(404, 'Announcement not found or withdrawn.')
        return present(row, staff)

def content(body):
    data = body.model_dump(mode='json', exclude={'revision', 'request_id'})
    return data

def create(library_id, actor, body):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        uid = access(library_id, actor, staff=True, locked=True)
        values = content(body)
        validate_target(library_id,values)
        event_reference(library_id, values['linked_event_id'])
        query = {'library_id': library_id, 'created_by_user_id': uid, 'request_id': str(body.request_id)}
        existing = records().find_one(query)
        if existing:
            if any(existing.get(k, 'ALL_ACTIVE_MEMBERS' if k=='audience' else None) != v for k, v in values.items()):
                raise HTTPException(409, 'This draft request was already used. Refresh before retrying.')
            return present(existing, True)
        stamp = now()
        row = {**values, **query, 'announcement_id': str(uuid4()), 'status': 'DRAFT', 'revision': 0, 'updated_by_user_id':uid,
               'created_at': stamp, 'updated_at': stamp,
               'published_at': None, 'withdrawn_at': None, 'delivery': {'state': 'NOT_PUBLISHED'}}
        records().insert_one(row)
        # Mongo stores millisecond timestamps; return that authoritative stored
        # form on the initial response too, so retry receipts are byte-stable.
        return present(document(library_id,row['announcement_id']), True)

def update(library_id, announcement_id, actor, body):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        uid = access(library_id, actor, staff=True, locked=True)
        old = document(library_id, announcement_id)
        if old['status'] != 'DRAFT':
            raise HTTPException(409, 'Published content is immutable. Withdraw it and create a new announcement.')
        if old.get('audience')=='SPECIFIC_MEMBER' and not {'audience','recipient_user_id'} <= body.model_fields_set:
            raise HTTPException(422, 'Explicit recipient scope is required when editing a restricted draft.')
        values = content(body)
        validate_target(library_id,values)
        event_reference(library_id, values['linked_event_id'])
        row = records().find_one_and_update({'library_id': library_id, 'announcement_id': announcement_id,
            'status': 'DRAFT', 'revision': body.revision}, {'$set': {**values, 'updated_at': now(),'updated_by_user_id':uid}, '$inc': {'revision': 1}}, return_document=ReturnDocument.AFTER)
        if not row: raise HTTPException(409, 'The draft changed. Reload before editing.')
        return present(row, True)

def eligible_recipients(library_id, candidates=None):
    """Batched canonical identity + invitation proof; no per-recipient queries."""
    query = {'library_id': library_id, 'status': 'ACTIVE', 'role': {'$in': ['ADMIN', 'LIBRARIAN', 'GENERAL_USER']}}
    if candidates is not None: query['user_id'] = {'$in': candidates}
    members = list(collection('memberships').find(query, {'_id': 0, 'user_id': 1, 'grant_invitation_id': 1}).limit(MAX_RECIPIENTS + 1))
    if len(members) > MAX_RECIPIENTS:
        raise HTTPException(409, 'Publication supports at most 20,000 active membership records. No publication was made.')
    ids = [m['user_id'] for m in members if type(m.get('user_id')) is int and m['user_id'] > 0]
    eligible = {u['user_id'] for u in db.users.find({'user_id': {'$in': ids}, 'is_active': {'$ne': False},
        'is_email_verified': True, 'password_setup_required': {'$ne': True}, 'role': {'$in': ['ADMIN','LIBRARIAN','GENERAL_USER']}},
        {'_id':0,'user_id':1,'is_active':1,'password_setup_required':1}) if u.get('is_active', True) is True and not u.get('password_setup_required',False)}
    grants = [m['grant_invitation_id'] for m in members if m.get('grant_invitation_id')]
    proofs = {(r['invitation_id'], r.get('accepted_by_user_id')) for r in collection('invitations').find({
        'library_id': library_id, 'invitation_id': {'$in': grants}, 'status': 'ACCEPTED'}, {'_id':0,'invitation_id':1,'accepted_by_user_id':1})} if grants else set()
    return sorted({m['user_id'] for m in members if type(m.get('user_id')) is int and m.get('user_id') in eligible and
        (not m.get('grant_invitation_id') or (m['grant_invitation_id'], m['user_id']) in proofs)})

def publish(library_id, announcement_id, actor, body):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        uid = access(library_id, actor, staff=True, locked=True)
        old = document(library_id, announcement_id)
        if old['status'] == 'PUBLISHED': return present(old, True)
        if old['status'] != 'DRAFT': raise HTTPException(409, 'Withdrawn announcements cannot be republished.')
        if old['revision'] != body.revision: raise HTTPException(409, 'The draft changed. Reload before publishing.')
        event_reference(library_id, old.get('linked_event_id'), publishing=True)
        validate_target(library_id,old,status=409)
        recipients = eligible_recipients(library_id,[old['recipient_user_id']]) if old.get('audience')=='SPECIFIC_MEMBER' else eligible_recipients(library_id)
        stamp = now()
        row = records().find_one_and_update({'library_id':library_id,'announcement_id':announcement_id,'status':'DRAFT','revision':body.revision},
            {'$set': {'status':'PUBLISHED','published_at':stamp,'published_by_user_id':uid,'updated_by_user_id':uid,'updated_at':stamp,
                'delivery': {'state':'PENDING' if recipients else 'COMPLETE','recipients':recipients,'total':len(recipients),
                    'cursor':0,'delivered':0,'suppressed':0,'attempts':0,'last_error_code':None,'next_attempt_at':stamp}}, '$inc':{'revision':1}}, return_document=ReturnDocument.AFTER)
        if not row: raise HTTPException(409, 'The draft changed. Reload before publishing.')
        return present(row, True)

def withdraw(library_id, announcement_id, actor, body):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        uid = access(library_id, actor, staff=True, locked=True)
        old = document(library_id, announcement_id)
        if old['status'] == 'WITHDRAWN': return present(old, True)
        if old['status'] != 'PUBLISHED': raise HTTPException(409, 'Only published announcements can be withdrawn.')
        row = records().find_one_and_update({'library_id':library_id,'announcement_id':announcement_id,'status':'PUBLISHED','revision':body.revision},
            {'$set':{'status':'WITHDRAWN','withdrawn_at':now(),'withdrawn_by_user_id':uid,'updated_by_user_id':uid,'updated_at':now(),'delivery.state':'CANCELLED'},'$inc':{'revision':1}},return_document=ReturnDocument.AFTER)
        if not row: raise HTTPException(409, 'The announcement changed. Reload before withdrawing.')
        return present(row, True)

def deliver_one(library_id, announcement_id, limit=100, *, stamp=None, actor=None):
    """One bounded slice under the same gate as membership revocation.

    Failures are caught inside this idempotent delivery slice, so a retry does
    not require clearing an unknown-outcome domain mutation lock.
    """
    stamp = stamp or now()
    result = {'scanned':0,'delivered':0,'suppressed':0,'failed':0}
    with library_mutation(library_id, wait_seconds=3, durable=True):
        if actor is not None: access(library_id,actor,staff=True,locked=True)
        try:
            row = document(library_id, announcement_id)
            state = row['delivery']
            if row['status'] != 'PUBLISHED' or state['state'] != 'PENDING': return result
            library = collection('libraries').find_one({'library_id':library_id,'status':'ACTIVE'})
            if not library:
                records().update_one({'library_id':library_id,'announcement_id':announcement_id,'delivery.state':'PENDING'},
                    {'$set':{'delivery.next_attempt_at':stamp+timedelta(minutes=5)}})
                return result
            start = state['cursor']; batch = state['recipients'][start:start + min(max(limit,1),100)]
            eligible = set(eligible_recipients(library_id, batch))
            from backend.services.notification_service import insert_notice
            delivered = suppressed = 0
            for uid in batch:
                result['scanned'] += 1
                if uid not in eligible or not can_read(row,uid):
                    suppressed += 1
                    continue
                key = f'ANNOUNCEMENT:{library_id}:{announcement_id}:{uid}:{KIND}'
                insert_notice(uid, KIND, 'Library announcement', 'An announcement is available in your library.', key,
                    source='LIBRARY', source_ref={'announcement_id':announcement_id}, now=row['published_at'],
                    scope='LIBRARY', library_id=library_id, audience='MEMBER', source_type='announcement', source_id=announcement_id,
                    action_route=f'/libraries/{library_id}/announcements/{announcement_id}', priority=row['priority'])
                delivered += 1
            cursor = start + len(batch)
            records().update_one({'library_id':library_id,'announcement_id':announcement_id,'delivery.cursor':start,'status':'PUBLISHED'},
                {'$set':{'delivery.cursor':cursor,'delivery.state':'COMPLETE' if cursor >= state['total'] else 'PENDING',
                         'delivery.last_error_code':None,'delivery.next_attempt_at':stamp},
                 '$inc':{'delivery.delivered':delivered,'delivery.suppressed':suppressed}})
            result.update(delivered=delivered,suppressed=suppressed)
        except Exception:
            # No exception strings/content/credentials are persisted. Cursor stays
            # replayable even if the error-recording write also fails.
            result['failed'] += 1
            try:
                attempts = min(10, state.get('attempts',0)+1) if 'state' in locals() else 1
                records().update_one({'library_id':library_id,'announcement_id':announcement_id,'delivery.state':'PENDING'},
                    {'$set':{'delivery.last_error_code':'DELIVERY_FAILED','delivery.attempts':attempts,
                        'delivery.state':'FAILED' if attempts>=10 else 'PENDING',
                        'delivery.next_attempt_at':stamp+timedelta(seconds=min(3600,30*2**(attempts-1)))}})
            except Exception: pass
    return result

def deliver_pending(limit=100, *, stamp=None):
    stamp = stamp or now(); remaining = min(max(limit,1),500)
    result = {'scanned':0,'delivered':0,'suppressed':0,'failed':0}
    rows = records().find({'status':'PUBLISHED','delivery.state':'PENDING','delivery.next_attempt_at':{'$lte':stamp}},
        {'library_id':1,'announcement_id':1}).sort([('delivery.next_attempt_at',1),('published_at',1)]).limit(10)
    for row in rows:
        if remaining <= 0: break
        try: current = deliver_one(row['library_id'],row['announcement_id'],min(100,remaining),stamp=stamp)
        except HTTPException: continue  # Busy tenant is retried by the existing worker.
        for key in result: result[key] += current[key]
        remaining -= max(1,current['scanned'])
    return result

def retry_delivery(library_id, announcement_id, actor):
    # Staff/manual repair is bounded and rechecks authority on every request.
    with library_mutation(library_id, wait_seconds=30, durable=True):
        access(library_id,actor,staff=True,locked=True)
        document(library_id,announcement_id)
        records().update_one({'library_id':library_id,'announcement_id':announcement_id,'status':'PUBLISHED','delivery.state':'FAILED'},
            {'$set':{'delivery.state':'PENDING','delivery.attempts':0,'delivery.next_attempt_at':now()}})
    deliver_one(library_id,announcement_id,100,actor=actor)
    return detail(library_id,announcement_id,actor,staff=True)
