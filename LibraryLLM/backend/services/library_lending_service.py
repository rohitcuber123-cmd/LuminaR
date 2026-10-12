"""Approval circulation. All stock decisions use canonical tenant records only."""
import os
import re
from datetime import timedelta, timezone
from uuid import uuid4, uuid5, NAMESPACE_URL
from fastapi import HTTPException
from backend.database.mongodb import db
from backend.institution_dependencies import actor_id
from backend.services.library_inventory_access import require_library_membership, require_library_staff, require_library_patron
from backend.services.institution_repository import collection, library_mutation, now as clock_now, require_readable
from backend.services import library_lending_journal as journal


def clean(row):
    return journal.response_value({k: v for k, v in row.items() if k != '_id'})


def now():
    stamp = clock_now()
    return stamp.replace(microsecond=(stamp.microsecond // 1000) * 1000)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def scoped(library_id, **fields):
    return {'library_id': library_id, **fields}


def settings():
    try:
        hours = int(os.getenv('LIBRARY_BORROW_HOLD_HOURS', '24'))
        maximum = int(os.getenv('LIBRARY_MAX_PENDING_REQUESTS', '5'))
    except ValueError:
        raise HTTPException(503, 'Circulation policy requires review.')
    if not 1 <= hours <= 168 or not 1 <= maximum <= 100:
        raise HTTPException(503, 'Circulation policy requires review.')
    return hours, maximum


def canonical(library_id):
    if journal.state(library_id) != 'CANONICAL':
        raise HTTPException(409, 'Approval circulation is not enabled for this library; staff must reconcile and activate it.')


def book_holding(library_id, book_id):
    book = collection('library_books').find_one(scoped(library_id, library_book_id=book_id))
    holding = collection('holdings').find_one(scoped(library_id, library_book_id=book_id))
    if not book or not holding:
        raise HTTPException(404, 'Library book not found.')
    return book, holding


def availability_locked(library_id, book_id):
    book, holding = book_holding(library_id, book_id)
    query = scoped(library_id, library_book_id=book_id)
    pending = collection('lending_requests').count_documents({**query, 'request_type': 'BORROW', 'status': 'PENDING'})
    active = collection('loans').count_documents({**query, 'status': 'ACTIVE'})
    mode = holding.get('allocation_mode', 'AGGREGATE')
    known = collection('copies').count_documents(query)
    conditions = collection('copies').count_documents({**query, 'status': {'$in': ['LOST', 'DAMAGED', 'WITHDRAWN', 'UNVERIFIED', 'RESERVED']}})
    copy_available = collection('copies').count_documents({**query, 'status': 'AVAILABLE'}) if mode == 'COPY' else 0
    from backend.services.library_v2c_plan import enabled
    waiting = enabled(library_id) and bool(collection('reservations').find_one({**query, 'status': 'WAITING'}))
    from backend.services.library_catalogue_availability import project
    return project(library_id, book, holding, pending=pending, active=active, known=known,
                   conditions=conditions, available=copy_available, waiting=waiting)


def update_effect(name, library_id, field, identity, values):
    return journal.effect(name, scoped(library_id, **{field: identity}), values)


def release_effect(request):
    if not request.get('copy_id'):
        return []
    copy = collection('copies').find_one(scoped(request['library_id'], copy_id=request['copy_id']))
    if not copy or copy['status'] != 'HELD_FOR_REQUEST' or copy.get('lending_request_id') != request['lending_request_id']:
        raise journal.RecoveryRequired('Borrow hold copy identity needs reconciliation.')
    return [update_effect('copies', request['library_id'], 'copy_id', request['copy_id'],
        {'status': 'AVAILABLE', 'lending_request_id': None, 'loan_id': None, 'updated_at': now()})]


def finish_borrow(request, status, actor, key, kind, payload, reason=None):
    patch = {'status': status, 'reviewed_at': now(), 'reviewed_by_user_id': actor, 'rejection_reason': reason, 'updated_at': now()}
    result = {**clean(request), **patch, 'reason': reason}
    effects = release_effect(request) + [update_effect('lending_requests', request['library_id'], 'lending_request_id', request['lending_request_id'], patch)]
    return journal.commit(request['library_id'], actor, key, kind, payload, effects, result, borrower=request['user_id'])


def expire_locked(library_id):
    query = scoped(library_id, request_type='BORROW', status='PENDING', expires_at={'$lte': now()})
    for request in collection('lending_requests').find(query).sort('expires_at', 1).limit(50):
        key = str(uuid5(NAMESPACE_URL, 'luminar-expire:' + request['lending_request_id']))
        finish_borrow(request, 'EXPIRED', 0, key, 'BORROW_REQUEST_EXPIRED', {}, 'Approval hold expired.')
    if collection('lending_requests').find_one(query):
        raise HTTPException(503, 'Expired holds are being released in bounded batches. Refresh to continue.', headers={'Retry-After': '3'})
    from backend.services.library_v2c_plan import enabled
    if enabled(library_id):
        from backend.services.library_reservation_service import advance_locked
        books = collection('reservations').distinct('library_book_id', scoped(library_id, status='WAITING'))
        for book_id in books[:50]:
            advance_locked(library_id, book_id)


def access_locked(library_id, actor, staff=False, patron=False):
    guard = require_library_staff if staff else require_library_patron if patron else require_library_membership
    guard(library_id, actor, locked=True); canonical(library_id); expire_locked(library_id)


def availability(library_id, book_id, actor):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        access_locked(library_id, actor)
        from backend.services.library_reservation_service import advance_locked
        advance_locked(library_id, book_id)
        return availability_locked(library_id, book_id)


def config(library_id, actor):
    require_library_membership(library_id, actor)
    result = {'library_id': library_id, 'state': journal.state(library_id), 'hold_hours': settings()[0], 'max_pending_requests': settings()[1]}
    require_readable(library_id)
    return result


def activate(library_id, actor, command):
    """Only empty/snapshot-consistent libraries activate online. Migration handles legacy loans."""
    with library_mutation(library_id, wait_seconds=30, durable=True):
        _, membership = require_library_staff(library_id, actor, locked=True)
        if membership['role'] != 'ADMIN':
            raise HTTPException(403, 'Library admin authority is required for cutover.')
        payload = command.model_dump(mode='json'); user = actor_id(actor)
        old = journal.receipt(library_id, user, command.idempotency_key, 'LENDING_CUTOVER', payload)
        if old is not None:
            return old
        if journal.state(library_id) != 'LEGACY':
            raise HTTPException(409, 'Library already has a lending cutover state.')
        aliases = [a['legacy_library_id'] for a in collection('library_aliases').find({'canonical_library_id': library_id})]
        if db.issues.find_one({'library_id': {'$in': [library_id, *aliases]}, 'status': 'ISSUED'}):
            raise HTTPException(409, 'Active legacy loans require explicit migration before cutover.')
        effects = [journal.effect('lending_config', scoped(library_id), {'library_id': library_id, 'state': 'PREPARING', 'cutover_at': now()},
            not bool(collection('lending_config').find_one(scoped(library_id))))]
        for h in collection('holdings').find(scoped(library_id)):
            known = collection('copies').count_documents(scoped(library_id, library_book_id=h['library_book_id']))
            bad = collection('copies').count_documents(scoped(library_id, library_book_id=h['library_book_id'], status={'$in': ['BORROWED', 'HELD_FOR_REQUEST', 'RESERVED']}))
            if bad or known > h['total_copies']:
                raise HTTPException(409, 'Copy allocations require reconciliation before cutover.')
            conditions = collection('copies').count_documents(scoped(library_id, library_book_id=h['library_book_id'], status={'$in': ['LOST', 'DAMAGED', 'WITHDRAWN', 'UNVERIFIED']}))
            deficit = h['total_copies'] - h['available_copies']
            if deficit < conditions:
                raise HTTPException(409, 'Inventory snapshot conflicts with copy conditions; reconcile before cutover.')
            effects.append(update_effect('holdings', library_id, 'holding_id', h['holding_id'],
                {'allocation_mode': 'AGGREGATE', 'unavailable_stock': deficit - conditions, 'circulation_status': h.get('circulation_status', 'CIRCULATING'), 'quantity_semantics': 'CANONICAL_CIRCULATION'}))
        effects.append(journal.effect('lending_config', scoped(library_id), {'state': 'CANONICAL', 'cutover_at': now()}))
        return journal.commit(library_id, user, command.idempotency_key, 'LENDING_CUTOVER', payload, effects, {'library_id': library_id, 'state': 'CANONICAL'})


def borrow(library_id, actor, command):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        access_locked(library_id, actor, patron=True); user = actor_id(actor); payload = command.model_dump(mode='json')
        old = journal.receipt(library_id, user, command.idempotency_key, 'BORROW_REQUEST_CREATED', payload)
        if old is not None:
            return old
        book_id = str(command.library_book_id); book, holding = book_holding(library_id, book_id)
        from backend.services.library_reservation_service import blocks_direct
        blocks_direct(library_id, book_id)
        query = scoped(library_id, user_id=user, library_book_id=book_id)
        if collection('loans').find_one({**query, 'status': 'ACTIVE'}) or collection('lending_requests').find_one({**query, 'request_type': 'BORROW', 'status': 'PENDING'}):
            raise HTTPException(409, 'You already have an active loan or pending request for this book.')
        hours, maximum = settings()
        if collection('lending_requests').count_documents(scoped(library_id, user_id=user, request_type='BORROW', status='PENDING')) >= maximum:
            raise HTTPException(409, 'Pending book request limit reached.')
        counts = availability_locked(library_id, book_id)
        if counts['requestable'] < 1:
            raise HTTPException(409, 'This book is currently unavailable for requests.')
        stamp = now(); request_id = str(uuid4()); copy_id = None; effects = []
        if counts['allocation_mode'] == 'COPY':
            copy = collection('copies').find_one(scoped(library_id, library_book_id=book_id, status='AVAILABLE'), sort=[('copy_number', 1)])
            copy_id = copy['copy_id']
            effects.append(update_effect('copies', library_id, 'copy_id', copy_id, {'status': 'HELD_FOR_REQUEST', 'lending_request_id': request_id, 'updated_at': stamp}))
        row = {'lending_request_id': request_id, 'library_id': library_id, 'library_book_id': book_id, 'holding_id': holding['holding_id'],
            'copy_id': copy_id, 'allocation_mode': counts['allocation_mode'], 'user_id': user, 'request_type': 'BORROW', 'status': 'PENDING',
            'loan_id': None, 'title': book['title'], 'accession_number': book['accession_number'], 'requested_at': stamp,
            'expires_at': stamp + timedelta(hours=hours), 'created_at': stamp, 'updated_at': stamp}
        effects.append(journal.effect('lending_requests', scoped(library_id, lending_request_id=request_id), row, True))
        return journal.commit(library_id, user, command.idempotency_key, 'BORROW_REQUEST_CREATED', payload, effects, row, borrower=user)


def request_record(library_id, request_id, kind):
    request = collection('lending_requests').find_one(scoped(library_id, lending_request_id=request_id, request_type=kind))
    if not request:
        raise HTTPException(404, 'Request not found.')
    return request


def review_borrow(library_id, request_id, actor, command, action):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        access_locked(library_id, actor, staff=action != 'cancel', patron=action == 'cancel'); user = actor_id(actor)
        kind = {'cancel': 'BORROW_REQUEST_CANCELLED', 'reject': 'BORROW_REQUEST_REJECTED', 'approve': 'BORROW_REQUEST_APPROVED'}[action]
        payload = {**command.model_dump(mode='json'), 'request_id': request_id}
        old = journal.receipt(library_id, user, command.idempotency_key, kind, payload)
        if old is not None:
            return old
        request = request_record(library_id, request_id, 'BORROW')
        if action == 'cancel' and request['user_id'] != user:
            raise HTTPException(404, 'Request not found.')
        if request['status'] != 'PENDING':
            raise HTTPException(409, 'Request is no longer pending. Refresh its status.')
        if action != 'approve':
            return finish_borrow(request, 'CANCELLED' if action == 'cancel' else 'REJECTED', user, command.idempotency_key, kind, payload, getattr(command, 'reason', None))
        try:
            require_library_membership(library_id, {'sub': str(request['user_id'])}, locked=True)
        except HTTPException:
            return finish_borrow(request, 'CANCELLED', user, command.idempotency_key, kind, payload, 'Borrower account or membership is no longer eligible. Hold released; no loan issued.')
        book, holding = book_holding(library_id, request['library_book_id'])
        if book['status'] != 'ACTIVE' or holding.get('circulation_status', 'CIRCULATING') != 'CIRCULATING':
            return finish_borrow(request, 'REJECTED', user, command.idempotency_key, kind, payload, 'Book is no longer circulating. Hold released; no loan issued.')
        counts = availability_locked(library_id, request['library_book_id']); loan_id = str(uuid4()); stamp = now()
        from backend.services.issue_service import LOAN_PERIOD_DAYS
        loan = {'loan_id': loan_id, 'library_id': library_id, 'library_book_id': request['library_book_id'], 'holding_id': request['holding_id'],
            'copy_id': request.get('copy_id'), 'allocation_mode': request['allocation_mode'], 'user_id': request['user_id'],
            'borrower_user_id': request['user_id'], 'approved_by_user_id': user, 'borrow_request_id': request_id,
            'borrowed_at': stamp, 'due_at': stamp + timedelta(days=LOAN_PERIOD_DAYS), 'returned_at': None, 'status': 'ACTIVE',
            'global_work_id': book.get('global_work_id'), 'title': book['title'], 'accession_number': book['accession_number'], 'renewal_count': 0}
        patch = {'status': 'APPROVED', 'loan_id': loan_id, 'reviewed_at': stamp, 'reviewed_by_user_id': user, 'updated_at': stamp}
        effects = []
        if request.get('copy_id'):
            release_effect(request)  # verifies the SAME hold before conversion
            effects.append(update_effect('copies', library_id, 'copy_id', request['copy_id'], {'status': 'BORROWED', 'loan_id': loan_id, 'updated_at': stamp}))
        # Drop pending uniqueness before inserting active loan. Readers are behind the gate.
        effects += [update_effect('lending_requests', library_id, 'lending_request_id', request_id, patch),
            journal.effect('loans', scoped(library_id, loan_id=loan_id), loan, True)]
        result = {**clean(request), **patch, 'loan': loan, 'requestable': counts['requestable']}
        return journal.commit(library_id, user, command.idempotency_key, kind, payload, effects, result, borrower=request['user_id'])


def loan_record(library_id, loan_id):
    row = collection('loans').find_one(scoped(library_id, loan_id=loan_id))
    if not row:
        raise HTTPException(404, 'Loan not found.')
    return row


def return_request(library_id, loan_id, actor, command, *, staff=False):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        access_locked(library_id, actor, patron=not staff, staff=staff); user = actor_id(actor); payload = {**command.model_dump(mode='json'), 'loan_id': loan_id}
        if staff: payload['staff_assisted'] = True
        old = journal.receipt(library_id, user, command.idempotency_key, 'RETURN_REQUEST_CREATED', payload)
        if old is not None:
            return old
        loan = loan_record(library_id, loan_id)
        if not staff and loan['user_id'] != user:
            raise HTTPException(404, 'Loan not found.')
        if staff and loan['user_id'] == user:
            raise HTTPException(403, 'Staff cannot perform a personal return through assisted receipt.')
        if loan['status'] != 'ACTIVE':
            raise HTTPException(409, 'Only active loans can request return.')
        pending = collection('lending_requests').find_one(scoped(library_id, loan_id=loan_id, request_type='RETURN', status='PENDING'))
        if pending:
            if staff and loan.get('pending_return_request_id') == pending['lending_request_id']:
                return clean(pending)
            raise HTTPException(409, 'Return is already awaiting librarian confirmation.')
        stamp = now(); request_id = str(uuid4())
        row = {k: loan.get(k) for k in ['library_id', 'library_book_id', 'holding_id', 'copy_id', 'allocation_mode', 'user_id', 'loan_id', 'title', 'accession_number']}
        row.update({'lending_request_id': request_id, 'request_type': 'RETURN', 'status': 'PENDING', 'requested_at': stamp,
            'expires_at': None, 'created_at': stamp, 'updated_at': stamp, 'requested_by_user_id': user, 'staff_assisted': staff})
        effects = [journal.effect('lending_requests', scoped(library_id, lending_request_id=request_id), row, True),
            update_effect('loans', library_id, 'loan_id', loan_id, {'return_requested_at': loan.get('return_requested_at') or stamp, 'pending_return_request_id': request_id})]
        return journal.commit(library_id, user, command.idempotency_key, 'RETURN_REQUEST_CREATED', payload, effects, row, borrower=loan['user_id'])


def review_return(library_id, request_id, actor, command, action):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        access_locked(library_id, actor, staff=True); user = actor_id(actor)
        kind = 'RETURN_CONFIRMED' if action == 'confirm' else 'RETURN_REQUEST_REJECTED'
        payload = {**command.model_dump(mode='json'), 'request_id': request_id}
        old = journal.receipt(library_id, user, command.idempotency_key, kind, payload)
        if old is not None:
            return old
        request = request_record(library_id, request_id, 'RETURN'); loan = loan_record(library_id, request['loan_id'])
        if request['status'] != 'PENDING' or loan['status'] != 'ACTIVE' or loan.get('pending_return_request_id') != request_id:
            raise HTTPException(409, 'Return request is no longer pending.')
        stamp = now(); patch = {'status': 'COMPLETED' if action == 'confirm' else 'REJECTED', 'reviewed_at': stamp,
            'reviewed_by_user_id': user, 'rejection_reason': command.reason, 'updated_at': stamp}
        loan_patch = {'pending_return_request_id': None}
        effects = []
        if action == 'confirm':
            loan_patch.update({'status': 'RETURNED', 'returned_at': stamp, 'received_by_user_id': user})
            if loan.get('copy_id'):
                copy = collection('copies').find_one(scoped(library_id, copy_id=loan['copy_id']))
                if not copy or copy['status'] != 'BORROWED' or copy.get('loan_id') != loan['loan_id']:
                    raise journal.RecoveryRequired('Returned copy does not match active loan allocation.')
                effects.append(update_effect('copies', library_id, 'copy_id', loan['copy_id'], {'status': 'AVAILABLE', 'loan_id': None, 'lending_request_id': None, 'updated_at': stamp}))
        effects += [update_effect('lending_requests', library_id, 'lending_request_id', request_id, patch), update_effect('loans', library_id, 'loan_id', loan['loan_id'], loan_patch)]
        return journal.commit(library_id, user, command.idempotency_key, kind, payload, effects, {**clean(request), **patch, 'loan': {**clean(loan), **loan_patch}}, borrower=loan['user_id'])


def renew(library_id, loan_id, actor, command, *, staff=False):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        access_locked(library_id, actor, patron=not staff, staff=staff); user = actor_id(actor); payload = {**command.model_dump(mode='json'), 'loan_id': loan_id}
        if staff: payload['staff_assisted'] = True
        old = journal.receipt(library_id, user, command.idempotency_key, 'LOAN_RENEWED', payload)
        if old is not None:
            return old
        loan = loan_record(library_id, loan_id)
        if not staff and loan['user_id'] != user:
            raise HTTPException(404, 'Loan not found.')
        borrower = loan['user_id']
        if staff:
            if borrower == user:
                raise HTTPException(403, 'Staff cannot renew their own loan through assisted renewal.')
            require_library_patron(library_id, {'sub': str(borrower)}, locked=True)
        from backend.services.loan_renewal_service import policy
        rules = policy()
        if loan['status'] != 'ACTIVE' or loan.get('pending_return_request_id') or not rules['enabled'] or loan.get('renewal_count', 0) >= rules['max_renewals'] or utc(loan['due_at']) < now():
            raise HTTPException(409, 'Loan is not eligible for renewal; pending physical return blocks renewal.')
        if utc(loan['due_at']) != utc(command.expected_due_at):
            raise HTTPException(409, 'Loan due date changed. Refresh before renewing.')
        # Only reservations with proven canonical/explicit alias tenancy can block.
        aliases = [a['legacy_library_id'] for a in collection('library_aliases').find({'canonical_library_id': library_id})]
        work = loan.get('global_work_id')
        from backend.services.library_v2c_plan import enabled
        from backend.services.library_reservation_service import renewal_blocked
        if enabled(library_id) and renewal_blocked(library_id, loan['library_book_id'], borrower):
            raise HTTPException(409, 'Another eligible member of this library has a waiting reservation.')
        if not enabled(library_id) and work and db.reservations.find_one({'library_id': {'$in': [library_id, *aliases]}, 'work_id': work,
                'user_id': {'$ne': borrower}, 'status': {'$in': ['ACTIVE', 'READY_FOR_PICKUP']}}):
            raise HTTPException(409, 'Another member of this library has a reservation.')
        patch = {'due_at': utc(loan['due_at']) + timedelta(days=rules['days']), 'renewal_count': loan.get('renewal_count', 0) + 1, 'last_renewed_at': now(), 'renewed_by_user_id': user}
        return journal.commit(library_id, user, command.idempotency_key, 'LOAN_RENEWED', payload,
            [update_effect('loans', library_id, 'loan_id', loan_id, patch)], {**clean(loan), **patch}, borrower=borrower)


def rows(library_id, actor, *, kind='BORROW', staff=False, status='all', search='', user_id=None, since=None, until=None, offset=0, limit=20, loans=False):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        access_locked(library_id, actor, staff=staff, patron=not staff)
        query = scoped(library_id)
        if not loans:
            query['request_type'] = kind
        if not staff:
            query['user_id'] = actor_id(actor)
        elif user_id is not None:
            query['user_id'] = user_id
        if status != 'all':
            query['status'] = status
        if search:
            query['$or'] = [{'title': {'$regex': re.escape(search), '$options': 'i'}}, {'accession_number': {'$regex': re.escape(search), '$options': 'i'}}]
        if since or until:
            query['borrowed_at' if loans else 'requested_at'] = {**({'$gte': since} if since else {}), **({'$lte': until} if until else {})}
        coll = collection('loans' if loans else 'lending_requests')
        result = [clean(r) for r in coll.find(query).sort('borrowed_at' if loans else 'requested_at', 1).skip(offset).limit(limit)]
        for row in result:
            _, holding = book_holding(library_id, row['library_book_id'])
            row['shelf_location'] = holding.get('shelf_location'); row['call_number'] = holding.get('call_number')
            if staff:
                if row.get('request_type') == 'BORROW' and row['status'] == 'PENDING':
                    from backend.services.issue_service import LOAN_PERIOD_DAYS
                    row['proposed_due_at'] = now() + timedelta(days=LOAN_PERIOD_DAYS)
                account = db.users.find_one({'user_id': row['user_id']}, {'name': 1, 'email': 1}) or {}
                member = collection('memberships').find_one(scoped(library_id, user_id=row['user_id'])) or {}
                row['borrower'] = {'name': account.get('name'), 'email': account.get('email'), 'membership_status': member.get('status', 'REMOVED')}
                row['availability'] = availability_locked(library_id, row['library_book_id'])
        badges = {k: collection('lending_requests').count_documents(scoped(library_id, request_type=k, status='PENDING')) for k in ['BORROW', 'RETURN']} if staff else None
        return {'results': result, 'total': coll.count_documents(query), 'offset': offset, 'limit': limit, 'pending_counts': badges}


def manage(library_id, book_id, actor, command, action, copy_id=None):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        access_locked(library_id, actor, staff=True); user = actor_id(actor)
        kind = {'stock': 'STOCK_CIRCULATION_UPDATED', 'shelf': 'SHELF_UPDATED', 'copy': 'COPY_CONDITION_UPDATED'}[action]
        payload = {**command.model_dump(mode='json'), 'library_book_id': book_id, 'copy_id': copy_id}
        old = journal.receipt(library_id, user, command.idempotency_key, kind, payload)
        if old is not None:
            return old
        book = collection('library_books').find_one(scoped(library_id, library_book_id=book_id))
        holding = collection('holdings').find_one(scoped(library_id, library_book_id=book_id))
        if not book:raise HTTPException(404,'Library book not found.')
        if holding is None:
            from backend.services.library_book_formats import unstocked_origin
            if not unstocked_origin(library_id,book_id):
                raise HTTPException(409,'Missing physical holding requires operator review; it cannot be recreated as new stock.')
            if (collection('loans').find_one(scoped(library_id,library_book_id=book_id,status='ACTIVE'))
                    or collection('lending_requests').find_one(scoped(library_id,library_book_id=book_id,status='PENDING'))
                    or collection('copies').find_one(scoped(library_id,library_book_id=book_id))):
                raise HTTPException(409,'Missing physical holding has allocations; operator review is required.')
            if action!='stock' or book['status']!='ACTIVE' or command.total_copies<1 or command.allocation_mode!='AGGREGATE':
                raise HTTPException(422,'Add positive physical stock in aggregate mode before managing shelf or copies.')
            if command.unavailable_stock>command.total_copies:raise HTTPException(422,'Unavailable units exceed stock.')
            holding={'holding_id':str(uuid4()),'library_id':library_id,'library_book_id':book_id,'total_copies':command.total_copies,
                'available_copies':command.total_copies-command.unavailable_stock,'shelf_location':book.get('shelf_location'),
                'call_number':book.get('local_call_number'),'local_tags':book.get('local_tags',[]),'acquisition_note':book.get('acquisition_note'),
                'quantity_semantics':'CANONICAL_CIRCULATION','created_at':now(),'updated_at':now(),
                'created_by_user_id':user,'updated_by_user_id':user,**{k:v for k,v in command.model_dump().items() if k!='idempotency_key'}}
            from backend.schemas.library_catalogue import LibraryHolding
            LibraryHolding.model_validate({**holding,'quantity_semantics':'INVENTORY_SNAPSHOT_NOT_CIRCULATION'})
            return journal.commit(library_id,user,command.idempotency_key,kind,payload,
                [journal.effect('holdings',scoped(library_id,holding_id=holding['holding_id']),holding,True)],holding)
        counts = availability_locked(library_id, book_id); effects = []
        if action == 'shelf':
            patch = {'shelf_location': (command.shelf_location or '').strip() or None, 'call_number': (command.call_number or '').strip() or None, 'updated_at': now()}
            effects.append(update_effect('library_books', library_id, 'library_book_id', book_id, {'shelf_location': patch['shelf_location'], 'local_call_number': patch['call_number'], 'updated_at': now()}))
        elif action == 'copy':
            copy = collection('copies').find_one(scoped(library_id, library_book_id=book_id, copy_id=copy_id))
            if not copy:
                raise HTTPException(404, 'Copy not found.')
            if copy['status'] in ['BORROWED', 'HELD_FOR_REQUEST', 'RESERVED']:
                raise HTTPException(409, 'An allocated copy cannot change condition through stock management.')
            if holding.get('allocation_mode', 'AGGREGATE') != 'COPY' and counts['active_loans'] + counts['pending_holds']:
                raise HTTPException(409, 'Aggregate allocations prevent safe individual copy changes.')
            effects.append(update_effect('copies', library_id, 'copy_id', copy_id, {'status': command.status, 'updated_at': now()})); patch = {'updated_at': now()}
            added = int(copy['status'] == 'AVAILABLE' and command.status != 'AVAILABLE')
            if added and counts['physical_available'] < 1:
                raise HTTPException(409, 'No free physical unit exists to mark unavailable.')
        else:
            known = collection('copies').count_documents(scoped(library_id, library_book_id=book_id))
            conditions = counts['unavailable_stock'] - holding.get('unavailable_stock', 0)
            required = counts['active_loans'] + counts['pending_holds'] + command.unavailable_stock + conditions
            if command.total_copies < max(required, known):
                raise HTTPException(409, 'Total stock cannot be below active loans, holds, unavailable units or known copies.')
            if command.allocation_mode != holding.get('allocation_mode', 'AGGREGATE') and counts['active_loans'] + counts['pending_holds']:
                raise HTTPException(409, 'Allocation mode cannot change while requests or loans exist.')
            if command.allocation_mode == 'COPY' and (known != command.total_copies or command.unavailable_stock or collection('copies').find_one(scoped(library_id, library_book_id=book_id, status={'$in': ['UNVERIFIED', 'RESERVED']}))):
                raise HTTPException(409, 'Copy mode requires every physical unit to have a verified identity and condition.')
            patch = {k: v for k, v in command.model_dump().items() if k != 'idempotency_key'}; patch['updated_at'] = now()
        effects.append(update_effect('holdings', library_id, 'holding_id', holding['holding_id'], patch))
        result = {'library_id': library_id, 'library_book_id': book_id, 'holding_id': holding['holding_id'], 'copy_id': copy_id, **patch}
        return journal.commit(library_id, user, command.idempotency_key, kind, payload, effects, result)
