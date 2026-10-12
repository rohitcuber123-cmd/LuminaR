"""Pure plan extension. No writes or callbacks before/after journal replay.

All reads occur behind the shared durable library gate. Projecting preceding
effects lets a released unit become exactly one borrow hold in the SAME plan.
"""
from datetime import timedelta
from uuid import uuid4, uuid5, NAMESPACE_URL
from fastapi import HTTPException
from backend.services.institution_repository import collection
from backend.services.library_inventory_access import require_library_membership
from backend.services import library_lending_journal as journal
from backend.services import library_lending_service as lending


def enabled(library_id):
    return (collection('v2c_config').find_one({'library_id': library_id}) or {}).get('state') == 'CANONICAL'


class Projection:
    def __init__(self, library_id, effects):
        self.library_id, self.effects = library_id, effects

    def rows(self, name, **scope):
        query = lending.scoped(self.library_id, **scope)
        rows = [lending.clean(r) for r in collection(name).find(query)]
        for step in self.effects:
            if step['collection'] != name:
                continue
            match = next((r for r in rows if all(r.get(k) == v for k, v in step['query'].items())), None)
            if match is not None:
                if not step['insert_only']:
                    match.update(step['values'])
            elif step['insert_only'] and all(step['values'].get(k) == v for k, v in query.items()):
                rows.append(dict(step['values']))
        return rows

    def add(self, name, field, identity, values, insert=False):
        self.effects.append(journal.effect(name, lending.scoped(self.library_id, **{field: identity}), values, insert))

    def audit(self, event, row, actor, **metadata):
        event_id = str(uuid4())
        self.add('audit', 'event_id', event_id, {'event_id': event_id, 'library_id': self.library_id,
            'event': event, 'actor_user_id': actor, 'target_user_id': row.get('user_id'),
            'metadata': {**{k: row.get(k) for k in ['reservation_id', 'fee_id', 'loan_id', 'library_book_id', 'policy_id'] if row.get(k)}, **metadata}, 'created_at': lending.now()}, True)


def account_eligible(library_id, user_id):
    try:
        require_library_membership(library_id, {'sub': str(user_id)}, locked=True)
        return True
    except HTTPException as error:
        if error.status_code in [401, 403, 404]:
            return False
        raise


def queue(p, book_id, actor):
    holdings = p.rows('holdings', library_book_id=book_id)
    books = p.rows('library_books', library_book_id=book_id)
    if len(books) != 1 or len(holdings) != 1:
        raise journal.RecoveryRequired('Projected queue book/holding identity requires reconciliation.')
    book, holding = books[0], holdings[0]
    reservations = sorted((r for r in p.rows('reservations', library_book_id=book_id) if r['status'] == 'WAITING'), key=lambda r: r['queue_sequence'])
    loans = p.rows('loans', library_book_id=book_id)
    requests = p.rows('lending_requests', library_book_id=book_id)
    copies = p.rows('copies', library_book_id=book_id)
    pending = [r for r in requests if r['request_type'] == 'BORROW' and r['status'] == 'PENDING']
    active = [r for r in loans if r['status'] == 'ACTIVE']
    conditions = sum(c['status'] in ['LOST', 'DAMAGED', 'WITHDRAWN', 'UNVERIFIED', 'RESERVED'] for c in copies)
    units = holding['total_copies'] - holding.get('unavailable_stock', 0) - conditions - len(active) - len(pending)
    if units < 0:
        raise journal.RecoveryRequired('Projected queue stock is inconsistent.')
    hours, maximum = lending.settings()
    for row in reservations:
        stamp = lending.now(); reason = None
        if not account_eligible(p.library_id, row['user_id']):
            reason = 'Account or library membership is no longer eligible.'
        elif any(r['user_id'] == row['user_id'] for r in active + pending):
            reason = 'An active loan or pending borrow request already exists.'
        elif row.get('expires_at') and lending.utc(row['expires_at']) <= stamp:
            reason = 'Waiting reservation expired.'
        if reason:
            status = 'EXPIRED' if reason == 'Waiting reservation expired.' else 'CANCELLED'
            p.add('reservations', 'reservation_id', row['reservation_id'], {'status': status, 'reason': reason, 'updated_at': stamp, 'ended_at': stamp})
            p.audit('RESERVATION_' + status, row, actor, reason=reason)
            continue
        if not units or book['status'] != 'ACTIVE' or holding.get('circulation_status', 'CIRCULATING') != 'CIRCULATING':
            continue
        all_pending = p.rows('lending_requests', user_id=row['user_id'])
        if sum(r['request_type'] == 'BORROW' and r['status'] == 'PENDING' for r in all_pending) >= maximum:
            # Strict FIFO: a temporarily limited head blocks later/direct requests.
            break
        request_id = str(uuid5(NAMESPACE_URL, 'luminar-reservation-request:' + row['reservation_id']))
        copy_id = None
        if holding.get('allocation_mode', 'AGGREGATE') == 'COPY':
            available = sorted((c for c in copies if c['status'] == 'AVAILABLE'), key=lambda c: c['copy_number'])
            if len(available) != units:
                raise journal.RecoveryRequired('Projected copy inventory and queue allocations disagree.')
            copy = available[0]; copy_id = copy['copy_id']; copy['status'] = 'HELD_FOR_REQUEST'
            p.add('copies', 'copy_id', copy_id, {'status': 'HELD_FOR_REQUEST', 'lending_request_id': request_id, 'loan_id': None, 'updated_at': stamp})
        request = {'lending_request_id': request_id, 'library_id': p.library_id, 'library_book_id': book_id,
            'holding_id': holding['holding_id'], 'copy_id': copy_id, 'allocation_mode': holding.get('allocation_mode', 'AGGREGATE'),
            'user_id': row['user_id'], 'request_type': 'BORROW', 'status': 'PENDING', 'loan_id': None,
            'reservation_id': row['reservation_id'], 'title': book['title'], 'accession_number': book['accession_number'],
            'requested_at': stamp, 'expires_at': stamp + timedelta(hours=hours), 'created_at': stamp, 'updated_at': stamp}
        p.add('lending_requests', 'lending_request_id', request_id, request, True)
        p.add('reservations', 'reservation_id', row['reservation_id'], {'status': 'CONVERTED', 'lending_request_id': request_id, 'converted_at': stamp, 'updated_at': stamp})
        p.audit('RESERVATION_BECAME_ELIGIBLE', row, actor)
        p.audit('RESERVATION_CONVERTED_TO_BORROW_REQUEST', row, actor, lending_request_id=request_id)
        p.audit('BORROW_REQUEST_CREATED', row, actor, lending_request_id=request_id)
        pending.append(request); units -= 1


def extend(library_id, actor, kind, effects, result):
    if not enabled(library_id):
        return
    p = Projection(library_id, effects)
    from backend.services.library_fee_service import current_policy, fee_effects
    # Snapshot policy once, at actual issuance. Renewals keep that provenance.
    for step in list(effects):
        if step['collection'] == 'loans' and step['insert_only']:
            policy = current_policy(library_id)
            step['values'].update({'fee_policy_id': policy['policy_id'], 'fee_policy_snapshot': policy})
            if result.get('loan', {}).get('loan_id') == step['values']['loan_id']:
                result['loan'].update({'fee_policy_id': policy['policy_id'], 'fee_policy_snapshot': policy})
        if step['collection'] == 'lending_requests' and not step['insert_only']:
            request = collection('lending_requests').find_one(step['query'])
            if request and request.get('reservation_id') and step['values'].get('status') in ['APPROVED', 'CANCELLED', 'REJECTED', 'EXPIRED']:
                status = 'FULFILLED' if step['values']['status'] == 'APPROVED' else 'EXPIRED' if step['values']['status'] == 'EXPIRED' else 'CANCELLED'
                row = collection('reservations').find_one(lending.scoped(library_id, reservation_id=request['reservation_id']))
                if not row or row['lending_request_id'] != request['lending_request_id']:
                    raise journal.RecoveryRequired('Converted reservation request link is inconsistent.')
                p.add('reservations', 'reservation_id', row['reservation_id'], {'status': status, 'ended_at': lending.now(), 'updated_at': lending.now(), 'loan_id': step['values'].get('loan_id')})
                p.audit('RESERVATION_' + status, row, actor)
    if kind == 'RETURN_CONFIRMED':
        request = collection('lending_requests').find_one(lending.scoped(library_id, lending_request_id=result['lending_request_id']))
        loan = p.rows('loans', loan_id=result['loan_id'])[0]
        patch = {'valid_return_requested_at': request['requested_at'], 'physical_received_at': loan['returned_at']}
        p.add('loans', 'loan_id', loan['loan_id'], patch); loan.update(patch)
        result['loan'].update(patch)
        fee_effects(p, loan, actor)
    books = {step['values'].get('library_book_id') or step['query'].get('library_book_id') for step in effects if step['collection'] in ['holdings', 'copies', 'loans', 'lending_requests', 'reservations', 'library_books']}
    if result.get('library_book_id'):
        books.add(result['library_book_id'])
    # Updates often target only a UUID; resolve book identity explicitly in tenant scope.
    for step in list(effects):
        if step['collection'] in ['holdings', 'copies', 'loans', 'lending_requests', 'reservations'] and not (step['values'].get('library_book_id') or step['query'].get('library_book_id')):
            old = collection(step['collection']).find_one(step['query'])
            if old:
                books.add(old['library_book_id'])
    for book_id in sorted(b for b in books if b):
        queue(p, book_id, actor)
