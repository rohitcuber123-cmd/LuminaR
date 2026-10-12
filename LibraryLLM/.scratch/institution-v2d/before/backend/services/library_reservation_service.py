"""Canonical UUID queues with no physical allocation in WAITING state."""
import re
from uuid import uuid4
from fastapi import HTTPException
from backend.database.mongodb import db
from backend.institution_dependencies import actor_id
from backend.services.institution_repository import collection, library_mutation
from backend.services import library_lending_journal as journal, library_lending_service as lending
from backend.services.library_inventory_access import require_library_staff
from backend.services.library_v2c_plan import enabled, account_eligible

MAX_ACTIVE = 5


def ensure_indexes():
    for name, identifier in [('reservations', 'reservation_id'), ('fees', 'fee_id'), ('fee_ledger', 'entry_id'), ('fee_policies', 'policy_id')]:
        collection(name).create_index(identifier, unique=True)
        collection(name).create_index([('library_id', 1), ('user_id', 1), ('status', 1)])
    collection('v2c_config').create_index('library_id', unique=True)
    collection('reservation_counters').create_index([('library_id', 1), ('library_book_id', 1)], unique=True)
    collection('reservations').create_index([('library_id', 1), ('library_book_id', 1), ('queue_sequence', 1)], unique=True)
    collection('reservations').create_index([('library_id', 1), ('library_book_id', 1), ('status', 1), ('queue_sequence', 1)])
    collection('reservations').create_index([('library_id', 1), ('library_book_id', 1), ('user_id', 1)], unique=True, partialFilterExpression={'status': 'WAITING'})
    collection('fees').create_index([('library_id', 1), ('loan_id', 1), ('fee_type', 1)], unique=True)
    collection('fees').create_index([('library_id', 1), ('status', 1), ('created_at', -1)])
    collection('fee_ledger').create_index([('library_id', 1), ('fee_id', 1), ('created_at', 1)])
    collection('fee_policies').create_index([('library_id', 1), ('version', 1)], unique=True)


def access(library_id, actor, staff=False, patron=False):
    lending.access_locked(library_id, actor, staff=staff, patron=patron)
    if not enabled(library_id):
        raise HTTPException(409, 'Reservations and fees require library admin cutover after reconciliation.')


def advance_locked(library_id, book_id):
    if not enabled(library_id):
        return
    waiting = list(collection('reservations').find(lending.scoped(library_id, library_book_id=book_id, status='WAITING')).sort('queue_sequence', 1))
    if not waiting:
        return
    invalid = any(not account_eligible(library_id, r['user_id']) or r.get('expires_at') and lending.utc(r['expires_at']) <= lending.now()
        or collection('loans').find_one(lending.scoped(library_id, library_book_id=book_id, user_id=r['user_id'], status='ACTIVE'))
        or collection('lending_requests').find_one(lending.scoped(library_id, library_book_id=book_id, user_id=r['user_id'], request_type='BORROW', status='PENDING')) for r in waiting)
    availability = lending.availability_locked(library_id, book_id)
    if not invalid and (not availability['physical_available'] or availability['circulation_status'] != 'CIRCULATING' or collection('lending_requests').count_documents(lending.scoped(library_id, user_id=waiting[0]['user_id'], request_type='BORROW', status='PENDING')) >= lending.settings()[1]):
        return
    return journal.commit(library_id, 0, uuid4(), 'QUEUE_ADVANCED', {}, [], {'library_id': library_id, 'library_book_id': book_id})


def blocks_direct(library_id, book_id):
    if enabled(library_id):
        advance_locked(library_id, book_id)
        if collection('reservations').find_one(lending.scoped(library_id, library_book_id=book_id, status='WAITING')):
            raise HTTPException(409, 'This unit is reserved for the waiting queue. The head member must become eligible first.')


def renewal_blocked(library_id, book_id, user_id):
    return any(account_eligible(library_id, r['user_id']) for r in collection('reservations').find(lending.scoped(library_id,
        library_book_id=book_id, user_id={'$ne': user_id}, status='WAITING')) if not r.get('expires_at') or lending.utc(r['expires_at']) > lending.now())


def create(library_id, actor, command):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        access(library_id, actor, patron=True); user = actor_id(actor); payload = command.model_dump(mode='json')
        old = journal.receipt(library_id, user, command.idempotency_key, 'RESERVATION_CREATED', payload)
        if old is not None:
            return old
        book_id = str(command.library_book_id); book, holding = lending.book_holding(library_id, book_id)
        advance_locked(library_id, book_id)
        if book['status'] != 'ACTIVE' or holding.get('circulation_status', 'CIRCULATING') != 'CIRCULATING':
            raise HTTPException(409, 'This book is not circulating.')
        scope = lending.scoped(library_id, library_book_id=book_id, user_id=user)
        if collection('reservations').find_one({**scope, 'status': 'WAITING'}) or collection('loans').find_one({**scope, 'status': 'ACTIVE'}) or collection('lending_requests').find_one({**scope, 'request_type': 'BORROW', 'status': 'PENDING'}):
            raise HTTPException(409, 'You already have a waiting reservation, pending request or active loan for this book.')
        if collection('reservations').count_documents(lending.scoped(library_id, user_id=user, status={'$in': ['WAITING', 'CONVERTED']})) >= MAX_ACTIVE:
            raise HTTPException(409, 'Active reservation limit reached (5 per library).')
        if lending.availability_locked(library_id, book_id)['requestable'] and not collection('reservations').find_one(lending.scoped(library_id, library_book_id=book_id, status='WAITING')):
            raise HTTPException(409, 'This book is available. Request Book for staff approval.')
        counter_scope = lending.scoped(library_id, library_book_id=book_id)
        counter = collection('reservation_counters').find_one(counter_scope)
        sequence = (counter or {}).get('last_sequence', 0) + 1
        stamp = lending.now(); rid = str(uuid4())
        row = {'reservation_id': rid, 'library_id': library_id, 'library_book_id': book_id, 'user_id': user,
            'global_work_id': book.get('global_work_id'), 'title': book['title'], 'accession_number': book['accession_number'],
            'queue_sequence': sequence, 'status': 'WAITING', 'requested_at': stamp, 'created_at': stamp, 'updated_at': stamp,
            'expires_at': None, 'lending_request_id': None, 'loan_id': None}
        effects = [journal.effect('reservation_counters', counter_scope, {**counter_scope, 'last_sequence': sequence}, not bool(counter)),
            journal.effect('reservations', lending.scoped(library_id, reservation_id=rid), row, True)]
        return journal.commit(library_id, user, command.idempotency_key, 'RESERVATION_CREATED', payload, effects, row, borrower=user)


def cancel(library_id, reservation_id, actor, command):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        access(library_id, actor, patron=True); user = actor_id(actor); payload = {**command.model_dump(mode='json'), 'reservation_id': reservation_id}
        old = journal.receipt(library_id, user, command.idempotency_key, 'RESERVATION_CANCELLED', payload)
        if old is not None:
            return old
        row = collection('reservations').find_one(lending.scoped(library_id, reservation_id=reservation_id, user_id=user))
        if not row:
            raise HTTPException(404, 'Reservation not found.')
        if row['status'] != 'WAITING':
            raise HTTPException(409, 'Only waiting reservations can be cancelled here. Cancel the linked Borrow Request after conversion.')
        patch = {'status': 'CANCELLED', 'ended_at': lending.now(), 'updated_at': lending.now(), 'reason': 'Cancelled by member.'}
        return journal.commit(library_id, user, command.idempotency_key, 'RESERVATION_CANCELLED', payload,
            [lending.update_effect('reservations', library_id, 'reservation_id', reservation_id, patch)], {**lending.clean(row), **patch}, borrower=user)


def rows(library_id, actor, *, staff=False, status='all', search='', offset=0, limit=20, book_id=None):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        access(library_id, actor, staff=staff, patron=not staff)
        # Lazy repair handles changed memberships/expiry using the same durable plans.
        books = collection('reservations').distinct('library_book_id', lending.scoped(library_id, status='WAITING'))
        for identity in books[:50]:
            advance_locked(library_id, identity)
        query = lending.scoped(library_id)
        if not staff:
            query['user_id'] = actor_id(actor)
        if book_id:
            query['library_book_id'] = book_id
        if status != 'all':
            query['status'] = status
        if search:
            query['$or'] = [{'title': {'$regex': re.escape(search), '$options': 'i'}}, {'accession_number': {'$regex': re.escape(search), '$options': 'i'}}]
        result = []
        for record in collection('reservations').find(query).sort('queue_sequence', 1).skip(offset).limit(limit):
            row = lending.clean(record)
            queue_scope = lending.scoped(library_id, library_book_id=row['library_book_id'], status='WAITING')
            row['queue_position'] = collection('reservations').count_documents({**queue_scope, 'queue_sequence': {'$lte': row['queue_sequence']}}) if row['status'] == 'WAITING' else None
            row['queue_length'] = collection('reservations').count_documents(queue_scope)
            if staff:
                account = db.users.find_one({'user_id': row['user_id']}, {'name': 1, 'email': 1}) or {}
                row['borrower'] = {k: account.get(k) for k in ['name', 'email']}
                row['availability'] = lending.availability_locked(library_id, row['library_book_id'])
            result.append(row)
        return {'results': result, 'total': collection('reservations').count_documents(query), 'offset': offset, 'limit': limit}


def activate(library_id, actor, command):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        lending.access_locked(library_id, actor, staff=True)
        _, membership = require_library_staff(library_id, actor, locked=True)
        if membership['role'] != 'ADMIN':
            raise HTTPException(403, 'Library admin authority is required for cutover.')
        user = actor_id(actor); payload = command.model_dump(mode='json')
        old = journal.receipt(library_id, user, command.idempotency_key, 'V2C_CUTOVER', payload)
        if old is not None:
            return old
        existing_config = collection('v2c_config').find_one(lending.scoped(library_id))
        if existing_config and existing_config['state'] != 'LEGACY':
            raise HTTPException(409, 'Library already has a Part 2C cutover state.')
        aliases = [r['legacy_library_id'] for r in collection('library_aliases').find({'canonical_library_id': library_id})]
        for legacy in db.reservations.find({'library_id': {'$in': [library_id, *aliases]}, 'status': {'$in': ['ACTIVE', 'READY_FOR_PICKUP']}}):
            if not collection('reservations').find_one(lending.scoped(library_id, legacy_reservation_id=legacy['reservation_id'])):
                raise HTTPException(409, 'Active mapped legacy reservations require explicit migration before cutover.')
        for loan in collection('loans').find(lending.scoped(library_id, legacy_issue_id={'$exists': True})):
            for legacy in db.fines.find({'issue_id': loan['legacy_issue_id']}):
                if not collection('fees').find_one(lending.scoped(library_id, legacy_fine_id=legacy['fine_id'])):
                    raise HTTPException(409, 'Mapped legacy fine history requires explicit migration before cutover.')
        from backend.services.library_v2c_integrity import reconcile
        if not reconcile(library_id)['ok']:
            raise HTTPException(409, 'Reconcile canonical circulation, queues and fee history before cutover.')
        from backend.services.library_fee_service import initial_policy
        existing_policy = collection('fee_policies').find_one(lending.scoped(library_id), sort=[('version', -1)])
        policy = lending.clean(existing_policy) if existing_policy else initial_policy(library_id, user)
        effects = [] if existing_policy else [journal.effect('fee_policies', lending.scoped(library_id, policy_id=policy['policy_id']), policy, True)]
        effects.append(journal.effect('v2c_config', lending.scoped(library_id), {'library_id': library_id, 'state': 'CANONICAL', 'reservation_mode': 'CANONICAL', 'fee_mode': 'CANONICAL', 'cutover_at': lending.now()}, not bool(existing_config)))
        for loan in collection('loans').find(lending.scoped(library_id, fee_policy_id={'$exists': False})):
            effects.append(lending.update_effect('loans', library_id, 'loan_id', loan['loan_id'], {'fee_policy_id': policy['policy_id'], 'fee_policy_snapshot': policy}))
        return journal.commit(library_id, user, command.idempotency_key, 'V2C_CUTOVER', payload, effects, {'library_id': library_id, 'state': 'CANONICAL'})
