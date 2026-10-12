"""Journal-owned notification intents and retryable, bounded inbox materialization.

Standalone Mongo: no cross-document transaction claim. A COMMITTED operation
is the sole authority for dispatch. A failed notification never rewrites its
domain receipt. Absolute outbox effects replay with the existing operation plan.
"""
from datetime import timedelta
from uuid import UUID, uuid5, NAMESPACE_URL
from fastapi import HTTPException
from pymongo.write_concern import WriteConcern
from backend.services.institution_repository import collection, now
from backend.services.library_inventory_access import require_library_staff, require_library_patron

KINDS = {
    'BORROW_REQUEST_CREATED': ('STAFF', 'New borrow request', 'A patron request is ready for staff review.', 'circulation'),
    'BORROW_REQUEST_APPROVED': ('PATRON', 'Borrow request approved', 'Your library has approved your borrow request.', 'my-library'),
    'BORROW_REQUEST_REJECTED': ('PATRON', 'Borrow request rejected', 'Review the request outcome in My Library.', 'my-library'),
    'RETURN_REQUEST_CREATED': ('STAFF', 'New return request', 'A return request is ready for staff review.', 'circulation?tab=return'),
    'RETURN_CONFIRMED': ('PATRON', 'Return confirmed', 'Your library has confirmed physical receipt of your book.', 'my-library'),
    'RESERVATION_CREATED': ('PATRON', 'Reservation created', 'Your reservation is in the library queue.', 'reservations'),
    'RESERVATION_CONVERTED_TO_BORROW_REQUEST': ('PATRON', 'Reservation ready', 'Your reserved book is ready for a staff-reviewed borrow request.', 'reservations'),
    'RESERVATION_CANCELLED': ('PATRON', 'Reservation cancelled', 'Review the reservation outcome in your library.', 'reservations'),
    'RESERVATION_EXPIRED': ('PATRON', 'Reservation expired', 'Your library reservation has expired.', 'reservations'),
    'FEE_CREATED': ('PATRON', 'Library fee assessed', 'Review the fee in your library account.', 'fees'),
    'FEE_WAIVED': ('PATRON', 'Library fee waived', 'Your library has waived the fee.', 'fees'),
    'FEE_PAYMENT_RECORDED': ('PATRON', 'Payment recorded', 'Your library has recorded a desk payment.', 'fees'),
    'FEE_ADJUSTED': ('PATRON', 'Library fee adjusted', 'Review the updated fee in your library account.', 'fees'),
}
ALIASES = {'RESERVATION_CONVERTED_TO_BORROW_REQUEST': 'RESERVATION_READY', 'FEE_CREATED': 'FEE_ASSESSED', 'FEE_PAYMENT_RECORDED': 'PAYMENT_RECORDED'}


def ensure_indexes():
    outbox = collection('notification_outbox')
    outbox.create_index('outbox_id', unique=True)
    outbox.create_index([('library_id', 1), ('operation_id', 1)])
    outbox.create_index([('state', 1), ('next_attempt_at', 1), ('created_at', 1)])
    from backend.services.notification_service import notifications
    notifications.create_index([('library_id', 1), ('created_at', -1)])
    # Preserve the stricter existing global unique dedupe index. New keys include
    # recipient identity and therefore satisfy user+key uniqueness too.


def append_intents(plan):
    from backend.services.library_lending_journal import effect
    library_id = str(UUID(plan['library_id']))
    for step in list(plan['effects']):
        if step['collection'] != 'audit' or not step['insert_only']:
            continue
        audit = step['values']; kind = audit['event']
        if kind not in KINDS:
            continue
        audience, title, message, page = KINDS[kind]
        metadata = audit.get('metadata', {})
        source_type, source_id = next(((field.removesuffix('_id'), metadata[field]) for field in
            ['fee_id', 'reservation_id', 'lending_request_id', 'loan_id'] if metadata.get(field)), (None, None))
        if not source_id:
            raise ValueError('Notification intent requires canonical domain provenance.')
        source_id = str(UUID(source_id))
        if audience == 'STAFF':
            candidates = collection('memberships').find({'library_id': library_id, 'status': 'ACTIVE', 'role': {'$in': ['ADMIN', 'LIBRARIAN']}}, {'user_id': 1})
            targets = [r['user_id'] for r in candidates]
        else:
            targets = [audit.get('target_user_id')]
        for uid in targets:
            if type(uid) is not int:
                continue
            try:
                guard = require_library_staff if audience == 'STAFF' else require_library_patron
                guard(library_id, {'sub': str(uid)}, locked=True)
            except HTTPException as error:
                if error.status_code in [401, 403, 404]:
                    continue
                raise
            # Audit identity is immutable within the durable plan, including queue
            # advancement generations. Recipient identity is part of the key.
            key = f"LIBRARY:{library_id}:{audit['event_id']}:{uid}"
            identity = str(uuid5(NAMESPACE_URL, 'luminar-notification:' + key))
            record = {'outbox_id': identity, 'library_id': library_id, 'operation_id': plan['operation_id'],
                'audit_event_id': audit['event_id'], 'user_id': uid, 'type': ALIASES.get(kind, kind), 'title': title,
                'message': message, 'audience': audience, 'source_type': source_type, 'source_id': source_id,
                'page': page, 'dedupe_key': key, 'state': 'PENDING', 'attempts': 0,
                'created_at': plan['created_at'], 'next_attempt_at': plan['created_at'], 'last_error_code': None}
            plan['effects'].append(effect('notification_outbox', {'library_id': library_id, 'outbox_id': identity}, record, True))


def action_route(library_id, audience, page):
    return f"/{'staff/' if audience == 'STAFF' else ''}libraries/{str(UUID(library_id))}/{page}"


def materialize(limit=100, *, stamp=None):
    from backend.services import notification_service as ns
    stamp = stamp or now()
    outbox = collection('notification_outbox').with_options(write_concern=WriteConcern(w=1, j=True))
    result = {'scanned': 0, 'delivered': 0, 'skipped': 0, 'failed': 0, 'uncommitted': 0}
    rows = outbox.find({'state': 'PENDING', 'next_attempt_at': {'$lte': stamp}}).sort([('next_attempt_at', 1), ('created_at', 1)]).limit(min(max(limit, 1), 500))
    for row in rows:
        result['scanned'] += 1
        origin = collection('lending_operations').find_one({'library_id': row['library_id'], 'operation_id': row['operation_id'], 'state': 'COMMITTED'}, {'_id': 1})
        if not origin:
            result['uncommitted'] += 1
            outbox.update_one({'outbox_id':row['outbox_id'],'library_id':row['library_id'],'state':'PENDING'},
                {'$set':{'next_attempt_at':stamp+timedelta(seconds=30),'last_error_code':'SOURCE_NOT_COMMITTED'}})
            continue
        query = {'outbox_id': row['outbox_id'], 'library_id': row['library_id'], 'state': 'PENDING'}
        try:
            # Never deliver to revoked staff or a different role/library. A
            # lifecycle change may suppress undelivered ordinary notices; already
            # stored history remains account-owned with a disabled action.
            try:
                guard = require_library_staff if row['audience'] == 'STAFF' else require_library_patron
                guard(row['library_id'], {'sub': str(row['user_id'])})
            except HTTPException as error:
                if error.status_code not in [401, 403, 404]:
                    raise
                outbox.update_one(query, {'$set': {'state': 'SUPPRESSED', 'completed_at': stamp, 'last_error_code': 'RECIPIENT_UNAVAILABLE'}})
                result['skipped'] += 1
                continue
            ns.insert_notice(row['user_id'], row['type'], row['title'], row['message'], row['dedupe_key'],
                source='LIBRARY', source_ref={'operation_id': row['operation_id'], 'source_type': row['source_type'], 'source_id': row['source_id']},
                now=row['created_at'], scope='LIBRARY', library_id=row['library_id'], audience=row['audience'],
                source_type=row['source_type'], source_id=row['source_id'],
                action_route=action_route(row['library_id'], row['audience'], row['page']))
            outbox.update_one(query, {'$set': {'state': 'DELIVERED', 'completed_at': stamp, 'last_error_code': None}})
            result['delivered'] += 1
        except Exception:
            # Error metadata is bounded and secret-free. Concurrent workers may
            # retry the same row; inbox uniqueness prevents duplicate delivery.
            attempts = min(row.get('attempts', 0) + 1, 10000)
            try:
                outbox.update_one(query, {'$set': {'attempts': attempts, 'last_error_code': 'DELIVERY_FAILED',
                    'last_attempt_at': stamp, 'next_attempt_at': stamp + timedelta(seconds=min(3600, 2 ** min(attempts, 12)))}})
            except Exception:
                pass
            result['failed'] += 1
    return result
