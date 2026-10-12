"""Write-ahead plans for standalone Mongo. Recovery requires stopped writers.

Absolute $set/$setOnInsert effects and fixed IDs can be replayed after ANY
uncertain acknowledgement. The persistent V1 gate prevents stale successors.
"""
import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import HTTPException
from pymongo.write_concern import WriteConcern
from backend.services.institution_repository import collection, now


class RecoveryRequired(RuntimeError):
    pass


def durable(name):
    return collection(name).with_options(write_concern=WriteConcern(w=1, j=True))


def ensure_indexes():
    collection('lending_config').create_index('library_id', unique=True)
    collection('lending_operations').create_index('operation_id', unique=True)
    collection('lending_operations').create_index([('library_id', 1), ('actor_user_id', 1), ('idempotency_key', 1)], unique=True)
    collection('lending_operations').create_index([('library_id', 1), ('state', 1)])
    for name, identifier in [('lending_requests', 'lending_request_id'), ('loans', 'loan_id')]:
        collection(name).create_index(identifier, unique=True)
        collection(name).create_index([('library_id', 1), ('library_book_id', 1), ('status', 1)])
        collection(name).create_index([('library_id', 1), ('user_id', 1), ('status', 1)])
    collection('lending_requests').create_index([('library_id', 1), ('request_type', 1), ('status', 1), ('requested_at', 1)])
    collection('lending_requests').create_index([('library_id', 1), ('request_type', 1), ('expires_at', 1), ('status', 1)])
    collection('lending_requests').create_index([('library_id', 1), ('user_id', 1), ('library_book_id', 1), ('request_type', 1)], unique=True,
        partialFilterExpression={'status': 'PENDING', 'request_type': 'BORROW'})
    collection('lending_requests').create_index([('library_id', 1), ('loan_id', 1), ('request_type', 1)], unique=True,
        partialFilterExpression={'status': 'PENDING', 'request_type': 'RETURN'})
    collection('loans').create_index([('library_id', 1), ('user_id', 1), ('library_book_id', 1)], unique=True,
        partialFilterExpression={'status': 'ACTIVE'})


def state(library_id):
    return (collection('lending_config').find_one({'library_id': library_id}) or {}).get('state', 'LEGACY')


def fingerprint(kind, payload):
    return hashlib.sha256(json.dumps([kind, payload], sort_keys=True, default=str).encode()).hexdigest()


def response_value(value):
    # PyMongo's default BSON decoder returns UTC datetimes without tzinfo.
    # Restore that provenance at the new lending boundary so browser dates do
    # not interpret UTC wall time as the user's local timezone.
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if isinstance(value, dict):
        return {k: response_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [response_value(v) for v in value]
    return value


def receipt(library_id, actor, key, kind, payload):
    old = collection('lending_operations').find_one({'library_id': library_id, 'actor_user_id': actor, 'idempotency_key': str(key)})
    if not old:
        return None
    if old['fingerprint'] != fingerprint(kind, payload):
        raise HTTPException(409, 'Idempotency key was used for a different command.')
    if old['state'] != 'COMMITTED':
        raise HTTPException(503, 'RECOVERY_REQUIRED: this operation needs reconciliation.')
    return response_value(old['result'])


def effect(name, query, values, insert=False):
    return {'collection': name, 'query': query, 'values': values, 'insert_only': insert}


def replay(plan):
    for step in plan['effects']:
        query = step['query']
        if query.get('library_id') != plan['library_id']:
            raise RecoveryRequired('Journal effect is missing canonical tenant scope.')
        update = {'$setOnInsert' if step['insert_only'] else '$set': step['values']}
        result = durable(step['collection']).update_one(query, update, upsert=step['insert_only'])
        if not step['insert_only'] and result.matched_count != 1:
            raise RecoveryRequired('Journal target disappeared; operator review required.')
    durable('lending_operations').update_one({'operation_id': plan['operation_id'], 'library_id': plan['library_id']},
        {'$set': {'state': 'COMMITTED', 'completed_at': now()}})


def commit(library_id, actor, key, kind, payload, effects, result, *, borrower=None):
    # Part 2C augments the existing durable plan only after explicit tenant cutover.
    from backend.services.library_v2c_plan import extend
    extend(library_id, actor, kind, effects, result)
    operation_id = str(uuid4()); stamp = now()
    result['operation_id'] = operation_id
    for step in effects:
        step['values']['last_lending_operation_id'] = operation_id
    # Audit intents are part of the SAME durable plan, never an untracked post-commit callback.
    plan = {'operation_id': operation_id, 'library_id': library_id, 'actor_user_id': actor, 'borrower_user_id': borrower,
        'idempotency_key': str(key), 'operation_type': kind, 'fingerprint': fingerprint(kind, payload),
        'lending_request_id': result.get('lending_request_id'), 'loan_id': result.get('loan_id'),
        'library_book_id': result.get('library_book_id'), 'holding_id': result.get('holding_id'), 'copy_id': result.get('copy_id'),
        'state': 'PREPARED', 'created_at': stamp, 'effects': effects, 'result': result}
    event_kind = ('BORROW_REQUEST_' + result['status']) if kind == 'BORROW_REQUEST_APPROVED' and result.get('status') in ['CANCELLED', 'REJECTED'] else kind
    events = [event_kind] + (['LOAN_ISSUED'] if kind == 'BORROW_REQUEST_APPROVED' and result.get('status') == 'APPROVED' else [])
    for event in events:
        event_id = f'{operation_id}:{event}'
        metadata = {k: result[k] for k in ['library_book_id', 'holding_id', 'copy_id', 'lending_request_id', 'loan_id', 'reservation_id', 'fee_id', 'policy_id', 'reason', 'circulation_status', 'current_amount_minor', 'paid_amount_minor', 'balance_minor', 'currency'] if k in result}
        metadata['operation_id'] = operation_id
        if 'requestable' in result:
            metadata['counts'] = {k: result[k] for k in ['total', 'requestable', 'pending_holds', 'active_loans', 'unavailable_stock'] if k in result}
        plan['effects'].append(effect('audit', {'event_id': event_id, 'library_id': library_id},
            {'event_id': event_id, 'library_id': library_id, 'event': event, 'actor_user_id': actor,
             'target_user_id': borrower, 'metadata': metadata, 'created_at': stamp}, True))
    try:
        durable('lending_operations').insert_one(plan)
        replay(plan)
        stored = collection('lending_operations').find_one({'operation_id': operation_id, 'state': 'COMMITTED'}, {'result': 1})
        if not stored:
            raise RecoveryRequired('Durable operation receipt cannot be verified.')
    except Exception as exc:
        # A lost acknowledgement may occur even for journal insertion. Keep the gate.
        try:
            durable('lending_config').update_one({'library_id': library_id}, {'$set': {'state': 'RECOVERY_REQUIRED', 'updated_at': now()}}, upsert=True)
        except Exception:
            pass
        raise RecoveryRequired('Circulation commit is uncertain. Stop writers and recover its durable plan.') from exc
    return response_value(stored['result'])
