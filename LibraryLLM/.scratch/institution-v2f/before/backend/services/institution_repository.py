"""Small Mongo boundary. No process-local tenant state or authoritative cache."""
from contextlib import contextmanager
from datetime import datetime, timezone
from time import monotonic, sleep
from uuid import uuid4

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from backend.database.mongodb import db


def now():
    return datetime.now(timezone.utc)


def collection(name):
    return db['institution_' + name]


def ensure_indexes():
    specs = {
        'libraries': [([('library_id', 1)], {'unique': True}),
                      ([('slug_normalized', 1)], {'unique': True}),
                      ([('status', 1), ('library_type', 1), ('name', 1)], {})],
        'security': [([('library_id', 1)], {'unique': True})],
        'memberships': [([('membership_id', 1)], {'unique': True}),
                        ([('library_id', 1), ('user_id', 1)], {'unique': True}),
                        ([('user_id', 1), ('status', 1), ('library_id', 1)], {}),
                        ([('library_id', 1), ('status', 1), ('role', 1)], {})],
        'invitations': [([('invitation_id', 1)], {'unique': True}),
                        ([('token_hash', 1)], {'unique': True, 'partialFilterExpression': {'token_hash': {'$type': 'string'}}}),
                        ([('library_id', 1), ('email_normalized', 1)], {'unique': True, 'partialFilterExpression': {'status': 'PENDING'}}),
                        ([('library_id', 1), ('status', 1), ('created_at', -1)], {}),
                        ([('email_normalized', 1), ('status', 1)], {}),
                        ([('expires_at', 1)], {})],
        'audit': [([('event_id', 1)], {'unique': True}),
                  ([('library_id', 1), ('created_at', -1)], {}),
                  ([('actor_user_id', 1), ('created_at', -1)], {})],
        'attempts': [([('expires_at', 1)], {'expireAfterSeconds': 0})],
    }
    for name, indexes in specs.items():
        coll = collection(name)
        existing = list(coll.list_indexes()) if name in [n.removeprefix('institution_') for n in db.list_collection_names()] else []
        for keys, options in indexes:
            same = [i for i in existing if list(i['key'].items()) == keys]
            if same:
                if not any(all(i.get(k) == v for k, v in options.items()) for i in same):
                    raise RuntimeError('Institution index requires operator review: ' + name)
                continue
            coll.create_index(keys, **options)


@contextmanager
def library_mutation(library_id, *, wait_seconds=3, durable=False):
    """Cross-worker serialization on standalone Mongo.

    A crashed holder is NEVER timed out/replaced automatically: a stale writer
    cannot race a successor. Reads fail closed while this lock exists. Operators
    must stop API workers and reconcile interrupted mutations before removing it.
    """
    locks = collection('locks')
    if durable:
        from pymongo.write_concern import WriteConcern
        locks = locks.with_options(write_concern=WriteConcern(w=1, j=True))
    holder = str(uuid4())
    deadline = monotonic() + wait_seconds
    while True:
        try:
            locks.insert_one({'_id': library_id, 'holder': holder, 'created_at': now()})
            break
        except DuplicateKeyError:
            if monotonic() >= deadline:
                raise HTTPException(503, 'Library update in progress. Please retry.', headers={'Retry-After': '3'})
            sleep(0.02)
    try:
        yield
    except HTTPException:
        locks.delete_one({'_id': library_id, 'holder': holder})
        raise
    except Exception:
        # Retain the lock when the commit outcome is unknown; never grant partial authority.
        raise
    else:
        locks.delete_one({'_id': library_id, 'holder': holder})


def require_readable(library_id):
    if collection('locks').find_one({'_id': library_id}, {'_id': 1}):
        raise HTTPException(503, 'Library update in progress. Please retry.', headers={'Retry-After': '3'})


def audit(library_id, event, actor, *, target_user_id=None, target_email_normalized=None,
          membership_id=None, metadata=None, event_id=None):
    # Whitelist every metadata key; call sites cannot accidentally persist credentials.
    allowed = {'role', 'previous_role', 'status', 'previous_status', 'access_mode', 'previous_access_mode', 'invitation_id', 'migration',
               'library_book_id', 'holding_id', 'copy_id', 'accession_number', 'global_work_id', 'import_id', 'counts', 'reason'}
    safe = {k: v for k, v in (metadata or {}).items() if k in allowed}
    if 'counts' in safe:
        count_keys = {'total', 'available_snapshot', 'created', 'increased', 'skipped', 'invalid', 'rows_total'}
        safe['counts'] = {k: v for k, v in safe['counts'].items() if k in count_keys and type(v) is int and 0 <= v <= 1000000} if isinstance(safe['counts'], dict) else {}
    event_id = event_id or str(uuid4())
    collection('audit').update_one({'event_id': event_id}, {'$setOnInsert': {
        'event_id': event_id, 'library_id': library_id, 'event': event,
        'actor_user_id': actor, 'target_user_id': target_user_id,
        'target_email_normalized': target_email_normalized, 'membership_id': membership_id,
        'metadata': safe, 'created_at': now(),
    }}, upsert=True)
