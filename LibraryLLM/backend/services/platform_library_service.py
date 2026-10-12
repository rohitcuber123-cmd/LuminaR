"""Safe installation directory and audited lifecycle; never tenant-internal authority."""
import re
from uuid import uuid4
from fastapi import HTTPException
from pymongo.write_concern import WriteConcern
from backend.database.mongodb import db
from backend.platform_dependencies import require_platform_admin
from backend.schemas.institution_models import Library
from backend.services.institution_repository import collection, library_mutation, now, require_readable
from backend.services.library_lending_journal import fingerprint, response_value

FIELDS=('library_id','name','slug','library_type','access_mode','owner_user_id','status','created_at','updated_at')
TRANSITIONS={'suspend':({'ACTIVE'},'SUSPENDED','LIBRARY_SUSPENDED'),
             'remove':({'ACTIVE','SUSPENDED'},'REMOVED','LIBRARY_REMOVED'),
             'restore':({'SUSPENDED','REMOVED'},'ACTIVE','LIBRARY_RESTORED')}


def ensure_indexes():
    collection('libraries').create_index([('status',1),('library_type',1),('name',1),('library_id',1)])
    db.platform_audit.create_index('event_id',unique=True)
    db.platform_audit.create_index([('library_id',1),('actor_user_id',1),('idempotency_key',1)],unique=True)
    db.platform_audit.create_index([('library_id',1),('created_at',-1),('event_id',1)])


def safe_summary(row):
    library_id=row['library_id'];scope={'library_id':library_id,'status':'ACTIVE'}
    owner=row.get('owner') or db.users.find_one({'user_id':row['owner_user_id']},{'_id':0,'user_id':1,'name':1,'email':1}) or {}
    return {**{k:row.get(k) for k in FIELDS},'owner':{k:owner.get(k) for k in ('user_id','name','email')},
            'counts':{'members':collection('memberships').count_documents({**scope,'role':'GENERAL_USER'}),
                      'staff':collection('memberships').count_documents({**scope,'role':{'$in':['ADMIN','LIBRARIAN']}}),
                      'local_books':collection('library_books').count_documents(scope)}}


def directory(limit,offset,q='',status=None,library_type=None):
    match={}
    if status:match['status']=status
    if library_type:match['library_type']=library_type
    pipeline=[{'$match':match},{'$project':{**{k:1 for k in FIELDS},'_id':0}},
              {'$lookup':{'from':'users','let':{'owner':'$owner_user_id'},'pipeline':[
                  {'$match':{'$expr':{'$eq':['$user_id','$$owner']}}},
                  {'$project':{'_id':0,'user_id':1,'name':1,'email':1}}],'as':'owner'}},
              {'$unwind':{'path':'$owner','preserveNullAndEmptyArrays':True}}]
    if q:
        literal={'$regex':re.escape(q.strip()),'$options':'i'}
        pipeline.append({'$match':{'$or':[{k:literal} for k in ('name','slug','library_id','owner.name','owner.email')]}})
    pipeline.extend([{'$sort':{'name':1,'library_id':1}},
                     {'$facet':{'rows':[{'$skip':offset},{'$limit':limit}],'total':[{'$count':'count'}]}}])
    result=list(collection('libraries').aggregate(pipeline,maxTimeMS=10000))[0]
    rows=[safe_summary(row) for row in result['rows']];total=result['total'][0]['count'] if result['total'] else 0
    return response_value({'results':rows,'total':total,'offset':offset,'limit':limit,'has_more':offset+len(rows)<total})


def library_record(library_id):
    row=collection('libraries').find_one({'library_id':library_id})
    if not row:raise HTTPException(404,'Library not found.')
    require_readable(library_id)
    return row


def audit_rows(library_id,limit=20,offset=0):
    query={'library_id':library_id,'state':'COMMITTED'}
    fields={'_id':0,**{k:1 for k in ['event_id','event','library_id','actor_user_id','created_at','reason','previous_state','new_state']}}
    return response_value({'results':list(db.platform_audit.find(query,fields).sort([('created_at',-1),('event_id',1)]).skip(offset).limit(limit)),
                           'total':db.platform_audit.count_documents(query),'limit':limit,'offset':offset})


def detail(library_id):
    row=library_record(library_id)
    lending=collection('lending_config').find_one({'library_id':library_id}) or {}
    cutover=collection('v2c_config').find_one({'library_id':library_id}) or {}
    return response_value({'library':safe_summary(row),'cutover':{'circulation':lending.get('state','LEGACY'),
        'reservations':cutover.get('reservation_mode','LEGACY'),'fees':cutover.get('fee_mode','LEGACY')},
        'audit':audit_rows(library_id),'tenant_internals_require_membership':True})


def validate_restore(row):
    """Re-use canonical integrity checks; never disclose tenant record details."""
    try:Library.model_validate(row)
    except ValueError:raise HTTPException(409,'Library identity needs operator review before restoration.') from None
    library_id=row['library_id'];scope={'library_id':library_id}
    owner=db.users.find_one({'user_id':row['owner_user_id'],'is_active':{'$ne':False},'is_email_verified':True})
    member=collection('memberships').find_one({**scope,'user_id':row['owner_user_id'],'role':'ADMIN','status':'ACTIVE'})
    if not owner or owner.get('is_active',True) is not True or owner.get('password_setup_required') or not member or not collection('security').find_one(scope):
        raise HTTPException(409,'Owner authority or library provisioning needs review before restoration.')
    if row['access_mode']=='PRIVATE_CODE' and not (collection('security').find_one(scope) or {}).get('access_code_hash'):
        raise HTTPException(409,'Private access configuration needs review before restoration.')
    configs=[collection(name).find_one(scope) or {} for name in ['lending_config','v2c_config']]
    if any(c.get('state') not in {None,'LEGACY','CANONICAL'} for c in configs):
        raise HTTPException(409,'Subsystem recovery must complete before restoration.')
    if collection('lending_operations').find_one({**scope,'state':{'$ne':'COMMITTED'}}) or collection('inventory_imports').find_one({**scope,'status':{'$in':['APPLYING','RECOVERY_REQUIRED']}}):
        raise HTTPException(409,'An unfinished tenant operation requires recovery before restoration.')
    if configs[1].get('state')=='CANONICAL' and configs[0].get('state')!='CANONICAL':
        raise HTTPException(409,'Canonical subsystem state needs review before restoration.')
    if configs[0].get('state')=='CANONICAL':
        from scripts.lending_v2b_operations import reconcile as lending_reconcile
        from backend.services.library_v2c_integrity import reconcile
        try:report=reconcile(library_id) if configs[1].get('state')=='CANONICAL' else lending_reconcile(library_id)
        except Exception:raise HTTPException(409,'Canonical integrity needs review before restoration.') from None
        if not report.get('ok'):raise HTTPException(409,'Canonical integrity needs review before restoration.')


def lifecycle(library_id,action,command,actor):
    # Check live assignment here as well as the HTTP guard: no stale JWT role grant.
    actor=require_platform_admin(actor);user_id=int(actor['sub'])
    allowed,target,event=TRANSITIONS[action];payload=command.model_dump(mode='json');key=str(command.idempotency_key)
    query={'library_id':library_id,'actor_user_id':user_id,'idempotency_key':key}
    durable_audit=db.platform_audit.with_options(write_concern=WriteConcern(w=1,j=True))
    with library_mutation(library_id,durable=True):
        previous=db.platform_audit.find_one(query)
        if previous:
            if previous['fingerprint']!=fingerprint(action,payload):raise HTTPException(409,'Idempotency key was used for a different command.')
            if previous['state']!='COMMITTED':raise HTTPException(503,'Platform lifecycle recovery is required.')
            return response_value(previous['result'])
        row=collection('libraries').find_one({'library_id':library_id})
        if not row:raise HTTPException(404,'Library not found.')
        if row['status']!=command.expected_status or row['status'] not in allowed:
            raise HTTPException(409,'Library state changed or this transition is not allowed. Refresh before continuing.')
        if action=='restore':validate_restore(row)
        stamp=now();event_id=str(uuid4())
        result={'library_id':library_id,'status':target,'previous_status':row['status'],'event_id':event_id}
        intent={**query,'event_id':event_id,'event':event,'reason':command.reason,'created_at':stamp,
                'previous_state':row['status'],'new_state':target,'fingerprint':fingerprint(action,payload),
                'state':'PREPARED','result':result}
        # A durable intent precedes the status write. Unknown acknowledgement
        # retains the existing cross-worker library gate for explicit recovery.
        durable_audit.insert_one(intent)
        changed=collection('libraries').with_options(write_concern=WriteConcern(w=1,j=True)).update_one(
            {'library_id':library_id,'status':row['status']},
            {'$set':{'status':target,'updated_at':stamp,'platform_lifecycle_event_id':event_id}})
        if changed.matched_count!=1:raise RuntimeError('Platform lifecycle acknowledgement requires recovery.')
        durable_audit.update_one({'event_id':event_id},{'$set':{'state':'COMMITTED','completed_at':now()}})
        if not db.platform_audit.find_one({'event_id':event_id,'state':'COMMITTED'}):
            raise RuntimeError('Platform lifecycle audit acknowledgement requires recovery.')
        return response_value(result)


def recover_lifecycle(library_id,*,writers_stopped=False):
    """Local operator recovery only; no online expiry/stealing of the durable gate."""
    if not writers_stopped:raise ValueError('Stop all writers before lifecycle recovery.')
    if not collection('locks').find_one({'_id':library_id}):raise ValueError('No retained library gate to recover.')
    intents=list(db.platform_audit.find({'library_id':library_id,'state':'PREPARED'}))
    if len(intents)!=1:raise ValueError('Exactly one durable lifecycle intent must be proven.')
    intent=intents[0];row=collection('libraries').find_one({'library_id':library_id})
    if not row or row['status'] not in [intent['previous_state'],intent['new_state']]:raise ValueError('Lifecycle provenance requires review.')
    action=next((name for name,(_,target,event) in TRANSITIONS.items() if target==intent['new_state'] and event==intent['event']),None)
    if not action or intent['previous_state'] not in TRANSITIONS[action][0]:raise ValueError('Invalid lifecycle transition provenance.')
    if row['status']==intent['new_state'] and row.get('platform_lifecycle_event_id')!=intent['event_id']:
        raise ValueError('Lifecycle event acknowledgement provenance requires review.')
    if intent['new_state']=='ACTIVE':validate_restore(row)
    collection('libraries').with_options(write_concern=WriteConcern(w=1,j=True)).update_one({'library_id':library_id},
        {'$set':{'status':intent['new_state'],'updated_at':intent['created_at'],'platform_lifecycle_event_id':intent['event_id']}})
    db.platform_audit.with_options(write_concern=WriteConcern(w=1,j=True)).update_one({'event_id':intent['event_id']},
        {'$set':{'state':'COMMITTED','completed_at':now()}})
    if not collection('libraries').find_one({'library_id':library_id,'status':intent['new_state'],'platform_lifecycle_event_id':intent['event_id']}) or not db.platform_audit.find_one({'event_id':intent['event_id'],'state':'COMMITTED'}):
        raise RuntimeError('Lifecycle recovery acknowledgement requires review.')
    collection('locks').delete_one({'_id':library_id})
    return response_value(intent['result'])
