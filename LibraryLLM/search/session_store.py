"""Short-lived Mongo plans shared by the semantic service and core fallback."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from uuid import UUID
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError
from search.query_plan import QueryPlan, parse_query, PARSER_VERSION
from search.query_session import clean, refine, explicit_filters, omit_fields, active, VERSION

IDLE_MINUTES = 30
HARD_MINUTES = 60
MAX_SESSIONS_PER_USER = 32

def collection():
    from backend.database.mongodb import db
    coll = db.search_sessions_v2b
    coll.create_index('expires_at', expireAfterSeconds=0)
    coll.create_index([('user_id',1),('updated_at',1)])
    return coll

def identity(actor, library_id=None, staff=False):
    return {'user_id':str(actor['sub']), 'login_session':actor.get('sid'),
            'scope':'LIBRARY' if library_id else 'GLOBAL', 'library_id':library_id,
            'workspace':'STAFF' if library_id and staff else 'PATRON' if library_id else 'GLOBAL'}

def token(value):
    try:
        return str(UUID(str(value)))
    except (ValueError,TypeError,AttributeError):
        raise HTTPException(422,'Invalid search context identifier.')

def invalidate(actor, library_id=None):
    query = {'user_id':str(actor['sub'])}
    if library_id:
        query['library_id'] = library_id
    collection().delete_many(query)

def invalidate_scope(actor, library_id=None, *, staff=False):
    """Remove accepted and pending state for exactly one ownership tuple.

    Authorization cleanup uses this; explicit logout retains invalidate()'s
    established account-wide policy.
    """
    return collection().delete_many(identity(actor,library_id,staff)).deleted_count

def clear(session_id, actor, library_id=None, staff=False):
    coll = collection()
    key = token(session_id)
    row = coll.find_one({'_id':key})
    owner = identity(actor,library_id,staff)
    if row and any(row.get(k) != v for k,v in owner.items()):
        raise HTTPException(404,'Search context not found.')
    coll.delete_one({'_id':key, **owner})
    coll.delete_many({'search_session_id':key, 'record_type':'CLARIFICATION', **owner})

def resolve(query, actor, facets, *, mode='SMART', filters=None, omit=(), session_id=None,
            library_id=None, staff=False, clock=None, capabilities=None,
            transform=None, expected_version=None, preview=False,commit_guard=None):
    if len(str(query)) > 500:
        raise ValueError('Search query is too long.')
    from search.query_confidence import validate, executable
    if not session_id:
        plan=parse_query(query,facets,mode,filters,omit)
        omit_fields(plan,omit)
        if transform:plan=transform(plan,facets,capabilities)
        plan=validate(plan,capabilities)
        if commit_guard and executable(plan):
            commit_guard.check();commit_guard.committed=True
        return plan, None
    key = token(session_id)
    coll = collection()
    owner = identity(actor,library_id,staff)
    now = clock or datetime.now(timezone.utc)
    filters = filters or {}
    digest = hashlib.sha256(json.dumps([query,mode,filters,sorted(omit)],sort_keys=True).encode()).hexdigest()
    for _ in range(4):
        row = coll.find_one({'_id':key})
        if row and any(row.get(k) != v for k,v in owner.items()):
            raise HTTPException(404,'Search context not found.')
        if row and row['expires_at'].replace(tzinfo=timezone.utc) <= now:
            if commit_guard:raise HTTPException(409,'Search context expired. Submit the query again.')
            if not preview:coll.delete_one({'_id':key,'version':row['version']})
            row = None
        if expected_version is not None and (row['version'] if row else 0)!=expected_version:
            raise HTTPException(409,'Search context changed. Submit the query again.')
        if not transform and row and row['last_request'] == digest and row['current_plan'].get('parser_version')==PARSER_VERSION:
            return validate(QueryPlan(**row['current_plan']),capabilities), public(row)
        previous = QueryPlan(**row['current_plan']) if row and row.get('parser_version') == VERSION else None
        if previous and (not query or query == row['last_query'] and previous.parser_version==PARSER_VERSION) and mode == previous.mode:
            plan, continued = clean(previous), True
        else:
            plan, continued = refine(previous,query,facets,mode)
        if continued:
            edits = filters if row and query == row['last_query'] else {k:v for k,v in filters.items() if v is not None and v != '' and not (k == 'sort' and v == 'RELEVANCE')}
            explicit_filters(plan,edits,row.get('last_filters',{}) if row else {})
        else:
            # Independent topics intentionally reset inherited constraints.
            # Current visible explicit controls remain authoritative.
            explicit_filters(plan,{k:v for k,v in filters.items() if v is not None and v != '' and not(k=='sort' and v=='RELEVANCE')})
        omit_fields(plan,omit)
        if transform:plan=transform(plan,facets,capabilities)
        validate(plan,capabilities)
        if not executable(plan):return plan, public(row) if row else None
        if preview:return plan, public(row) if row else None
        created = row['created_at'].replace(tzinfo=timezone.utc) if row else now
        next_row = {'_id':key, **owner, 'current_plan':asdict(clean(plan)),
                    'previous_plan':asdict(clean(previous)) if previous else None,
                    'version':row['version']+1 if row else 1,
                    'refinement_count':min(100,(row.get('refinement_count',0)+1)) if continued and row else 0,
                    'refined':bool(continued and previous), 'last_query':query,
                    'last_request':digest,'last_filters':filters,'created_at':created,'updated_at':now,
                    'expires_at':min(now+timedelta(minutes=IDLE_MINUTES),created+timedelta(minutes=HARD_MINUTES)),
                    'parser_version':VERSION}
        if commit_guard:
            deadline=commit_guard.check()
            next_row['interaction_receipt']=commit_guard.receipt
        if row:
            predicate={'_id':key,'version':row['version'],**owner}
            if commit_guard:predicate['$expr']={'$and':[{'$lt':['$$NOW',deadline]},{'$gt':['$expires_at','$$NOW']}]}
            result = coll.replace_one(predicate,next_row)
            if not result.modified_count:
                continue
        else:
            # Bounded number of active contexts; TTL cleanup is not authority.
            old = list(coll.find({'user_id':owner['user_id'],'current_plan':{'$exists':True}},{'_id':1}).sort('updated_at',-1).skip(MAX_SESSIONS_PER_USER-1))
            try:
                if commit_guard:commit_guard.check()
                coll.insert_one(next_row)
            except DuplicateKeyError:
                continue
            # Prune only after the new context exists. A late expiry or failed
            # insertion must not evict another accepted context.
            if old:
                coll.delete_many({'_id':{'$in':[r['_id'] for r in old]}})
        if commit_guard:commit_guard.committed=True
        return plan, public(next_row)
    raise HTTPException(409,'Search context changed. Retry your search.')

def public(row):
    # PyMongo's default reads are naive UTC. An ISO string without an offset is
    # interpreted as LOCAL time by JavaScript, prematurely expiring the UUID in
    # browsers east of UTC after an idempotent replay or empty-query restore.
    expires = row['expires_at']
    expires = expires.replace(tzinfo=timezone.utc) if expires.tzinfo is None else expires.astimezone(timezone.utc)
    return {'active':active(QueryPlan(**row['current_plan'])), 'refined':row['refined'],
            'version':row['version'],'expires_at':expires.isoformat()}
