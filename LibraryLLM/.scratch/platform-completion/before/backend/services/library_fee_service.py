"""Integer minor-unit charges, immutable policies and an append-only desk ledger."""
import re
from uuid import uuid4, uuid5, NAMESPACE_URL
from fastapi import HTTPException
from backend.database.mongodb import db
from backend.institution_dependencies import actor_id
from backend.services.institution_repository import collection, library_mutation
from backend.services.library_inventory_access import require_library_staff
from backend.services import library_lending_journal as journal, library_lending_service as lending
from backend.services.library_reservation_service import access


def initial_policy(library_id, actor):
    return {'policy_id': str(uuid5(NAMESPACE_URL, 'luminar-fee-policy:' + library_id + ':1')), 'library_id': library_id,
        'version': 1, 'effective_from': lending.now(), 'overdue_enabled': True, 'rate_minor_per_day': 500,
        'currency': 'INR', 'minor_units_per_major': 100, 'grace_days': 0, 'charge_stop_policy': 'PHYSICAL_RECEIPT',
        'day_boundary': 'UTC_CALENDAR_DAY', 'created_by_user_id': actor, 'created_at': lending.now(),
        'provenance': 'Legacy FINE_PER_DAY=5; INR activity text; UTC date subtraction in issue_service.return_book.'}


def current_policy(library_id):
    row = collection('fee_policies').find_one(lending.scoped(library_id), sort=[('version', -1)])
    if not row:
        raise journal.RecoveryRequired('Canonical fee policy is missing.')
    return lending.clean(row)


def calculation(loan, stop=None):
    policy = loan.get('fee_policy_snapshot')
    if not policy or not loan.get('fee_policy_id') or policy['policy_id'] != loan['fee_policy_id']:
        raise journal.RecoveryRequired('Loan fee policy provenance requires reconciliation.')
    received = loan.get('physical_received_at') or loan.get('returned_at')
    valid_request = loan.get('valid_return_requested_at')
    stop = stop or received or lending.now()
    if received and policy['charge_stop_policy'] == 'FIRST_VALID_RETURN_REQUEST' and valid_request:
        stop = valid_request
    days = max(0, (lending.utc(stop).date() - lending.utc(loan['due_at']).date()).days - policy['grace_days'])
    amount = days * policy['rate_minor_per_day'] if policy['overdue_enabled'] else 0
    if amount > 1000000000000:
        raise journal.RecoveryRequired('Charge exceeds supported integer money range; admin review required.')
    return {'policy_id': policy['policy_id'], 'policy_version': policy['version'], 'due_at': loan['due_at'],
        'return_requested_at': loan.get('return_requested_at'), 'valid_return_requested_at': valid_request,
        'physical_received_at': received, 'charge_stop_at': stop, 'charge_stop_policy': policy['charge_stop_policy'],
        'day_boundary': policy['day_boundary'], 'grace_days': policy['grace_days'], 'overdue_days': days,
        'rate_minor_per_day': policy['rate_minor_per_day'], 'currency': policy['currency'], 'amount_minor': amount,
        'kind': 'FINAL' if received else 'ESTIMATED'}


def fee_effects(p, loan, actor):
    if loan['status'] != 'RETURNED':
        return None
    existing = collection('fees').find_one(lending.scoped(p.library_id, loan_id=loan['loan_id'], fee_type='OVERDUE'))
    if existing:
        return lending.clean(existing)
    calc = calculation(loan)
    if not calc['amount_minor']:
        return None
    stamp = lending.now(); fee_id = str(uuid5(NAMESPACE_URL, 'luminar-overdue-fee:' + p.library_id + ':' + loan['loan_id']))
    row = {'fee_id': fee_id, 'library_id': p.library_id, 'loan_id': loan['loan_id'], 'library_book_id': loan['library_book_id'],
        'user_id': loan['user_id'], 'borrower_user_id': loan['user_id'], 'title': loan['title'], 'accession_number': loan['accession_number'],
        'fee_type': 'OVERDUE', 'status': 'OPEN', 'currency': calc['currency'], 'original_amount_minor': calc['amount_minor'],
        'current_amount_minor': calc['amount_minor'], 'paid_amount_minor': 0, 'balance_minor': calc['amount_minor'],
        'policy_id': loan['fee_policy_id'], 'policy_snapshot': loan['fee_policy_snapshot'], 'calculation': calc,
        'source_event': 'PHYSICAL_RETURN_CONFIRMED', 'created_at': stamp, 'updated_at': stamp}
    p.add('fees', 'fee_id', fee_id, row, True)
    entry_id = str(uuid5(NAMESPACE_URL, 'luminar-fee-initial-charge:' + fee_id))
    p.add('fee_ledger', 'entry_id', entry_id, {'entry_id': entry_id, 'fee_id': fee_id, 'library_id': p.library_id,
        'entry_type': 'CHARGE', 'amount_minor': calc['amount_minor'], 'actor_user_id': actor,
        'reason': 'Final overdue charge at confirmed physical receipt.', 'created_at': stamp}, True)
    p.audit('FEE_CREATED', row, actor, amount_minor=calc['amount_minor'], currency=calc['currency'], policy_version=calc['policy_version'])
    return row


def policy(library_id, actor, command=None):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        access(library_id, actor, staff=bool(command))
        if command is None:
            return {'current': current_policy(library_id), 'versions': [lending.clean(r) for r in collection('fee_policies').find(lending.scoped(library_id)).sort('version', -1)]}
        _, member = require_library_staff(library_id, actor, locked=True)
        if member['role'] != 'ADMIN':
            raise HTTPException(403, 'Library admin authority is required to create a policy version.')
        user = actor_id(actor); payload = command.model_dump(mode='json')
        old = journal.receipt(library_id, user, command.idempotency_key, 'FEE_POLICY_CREATED', payload)
        if old is not None:
            return old
        previous = current_policy(library_id)
        row = {**initial_policy(library_id, user), **{k: v for k, v in payload.items() if k != 'idempotency_key'},
            'policy_id': str(uuid4()), 'version': previous['version'] + 1, 'provenance': 'Library admin versioned policy.'}
        return journal.commit(library_id, user, command.idempotency_key, 'FEE_POLICY_CREATED', payload,
            [journal.effect('fee_policies', lending.scoped(library_id, policy_id=row['policy_id']), row, True)], row)


def verify_ledger(fee):
    entries = list(collection('fee_ledger').find(lending.scoped(fee['library_id'], fee_id=fee['fee_id'])))
    charge = sum(e['amount_minor'] * (1 if e['entry_type'] == 'CHARGE' else -1 if e['entry_type'] in ['CREDIT', 'WAIVER'] else 0) for e in entries)
    paid = sum(e['amount_minor'] for e in entries if e['entry_type'] == 'PAYMENT_RECORD')
    if min(charge, paid, charge - paid) < 0 or (charge, paid, charge - paid) != (fee['current_amount_minor'], fee['paid_amount_minor'], fee['balance_minor']):
        raise journal.RecoveryRequired('Fee balance and immutable ledger disagree.')
    return entries


def details(library_id, fee_id, actor, staff=False):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        access(library_id, actor, staff=staff, patron=not staff)
        query = lending.scoped(library_id, fee_id=fee_id)
        if not staff:
            query['user_id'] = actor_id(actor)
        fee = collection('fees').find_one(query)
        if not fee:
            raise HTTPException(404, 'Fee not found.')
        return {**lending.clean(fee), 'ledger': [lending.clean(e) for e in verify_ledger(fee)]}


def rows(library_id, actor, *, staff=False, status='all', fee_type='all', search='', since=None, until=None, offset=0, limit=20):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        access(library_id, actor, staff=staff, patron=not staff)
        query = lending.scoped(library_id)
        if not staff:
            query['user_id'] = actor_id(actor)
        if status != 'all':
            query['status'] = status
        if fee_type != 'all':
            query['fee_type'] = fee_type
        if since or until:
            query['created_at'] = {**({'$gte': since} if since else {}), **({'$lte': until} if until else {})}
        if search:
            text = re.escape(search)
            criteria = [{f: {'$regex': text, '$options': 'i'}} for f in ['title', 'accession_number', 'fee_id', 'loan_id']]
            if staff:
                # Only accounts already represented in this tenant's fees are searched.
                users = collection('fees').distinct('user_id', lending.scoped(library_id))
                ids = [u['user_id'] for u in db.users.find({'user_id': {'$in': users}, '$or': [{'name': {'$regex': text, '$options': 'i'}}, {'email': {'$regex': text, '$options': 'i'}}]}, {'user_id': 1})]
                criteria.append({'user_id': {'$in': ids}})
            query['$or'] = criteria
        result = [lending.clean(r) for r in collection('fees').find(query).sort('created_at', -1).skip(offset).limit(limit)]
        for row in result:
            verify_ledger(row)
            if staff:
                account = db.users.find_one({'user_id': row['user_id']}, {'name': 1, 'email': 1}) or {}
                row['borrower'] = {k: account.get(k) for k in ['name', 'email']}
        estimates = []
        if not staff and offset == 0:
            for loan in collection('loans').find(lending.scoped(library_id, user_id=actor_id(actor), status='ACTIVE')).limit(100):
                calc = calculation(loan)
                if calc['amount_minor']:
                    estimates.append({'loan_id': loan['loan_id'], 'title': loan['title'], **calc})
        return {'results': result, 'total': collection('fees').count_documents(query), 'estimates': journal.response_value(estimates), 'offset': offset, 'limit': limit}


def mutate(library_id, fee_id, actor, command, action):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        access(library_id, actor, staff=True)
        _, member = require_library_staff(library_id, actor, locked=True)
        if action in ['waive', 'adjust'] and member['role'] != 'ADMIN':
            raise HTTPException(403, 'Library admin authority is required for adjustments and waivers.')
        user = actor_id(actor); kind = {'waive': 'FEE_WAIVED', 'adjust': 'FEE_ADJUSTED', 'payments': 'FEE_PAYMENT_RECORDED'}[action]
        payload = {**command.model_dump(mode='json'), 'fee_id': fee_id}
        old = journal.receipt(library_id, user, command.idempotency_key, kind, payload)
        if old is not None:
            return old
        fee = collection('fees').find_one(lending.scoped(library_id, fee_id=fee_id))
        if not fee:
            raise HTTPException(404, 'Fee not found.')
        verify_ledger(fee)
        if fee['status'] in ['WAIVED', 'CANCELLED'] or (fee['balance_minor'] == 0 and action != 'adjust'):
            raise HTTPException(409, 'This fee has no open balance for this action.')
        entry_type = 'WAIVER' if action == 'waive' else command.direction if action == 'adjust' else 'PAYMENT_RECORD'
        amount = fee['balance_minor'] if action == 'waive' else command.amount_minor
        charge, paid = fee['current_amount_minor'], fee['paid_amount_minor']
        if entry_type == 'CHARGE':
            charge += amount
        elif entry_type in ['CREDIT', 'WAIVER']:
            charge -= amount
        else:
            paid += amount
        if charge > 1000000000000 or min(charge, paid, charge - paid) < 0:
            raise HTTPException(409, 'Amount would exceed the open balance or supported money range.')
        status = 'WAIVED' if action == 'waive' else 'PAID' if charge == paid else 'PARTIALLY_PAID' if paid else 'OPEN'
        stamp = lending.now(); entry_id = str(uuid4())
        entry = {'entry_id': entry_id, 'library_id': library_id, 'fee_id': fee_id, 'entry_type': entry_type,
            'amount_minor': amount, 'actor_user_id': user, 'idempotency_key': str(command.idempotency_key),
            'reason': getattr(command, 'reason', None) or getattr(command, 'note', None) or 'Manual payment recorded at library desk.', 'created_at': stamp}
        if action == 'payments':
            entry.update({'method': command.method, 'reference': command.reference, 'receipt_id': str(uuid4()), 'payment_processing': 'MANUAL_RECORD_ONLY'})
        patch = {'current_amount_minor': charge, 'paid_amount_minor': paid, 'balance_minor': charge - paid, 'status': status, 'updated_at': stamp}
        from backend.services.library_v2c_plan import Projection
        effects = [journal.effect('fee_ledger', lending.scoped(library_id, entry_id=entry_id), entry, True), lending.update_effect('fees', library_id, 'fee_id', fee_id, patch)]
        if status == 'PAID' and fee['status'] != 'PAID':
            Projection(library_id, effects).audit('FEE_PAID', fee, user, amount_minor=paid, currency=fee['currency'])
        return journal.commit(library_id, user, command.idempotency_key, kind, payload, effects,
            {**lending.clean(fee), **patch, 'ledger_entry': entry, 'reason': entry['reason']}, borrower=fee['user_id'])


def generate(library_id, loan_id, actor, command):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        access(library_id, actor, staff=True); user = actor_id(actor)
        payload = {**command.model_dump(mode='json'), 'loan_id': loan_id}
        old = journal.receipt(library_id, user, command.idempotency_key, 'FEE_GENERATION_RECONCILED', payload)
        if old is not None:
            return old
        loan = lending.loan_record(library_id, loan_id)
        if loan['status'] != 'RETURNED':
            raise HTTPException(409, 'Only physically received loans have a final charge. Active-loan amounts are estimates.')
        from backend.services.library_v2c_plan import Projection
        effects = []; fee = fee_effects(Projection(library_id, effects), loan, user)
        return journal.commit(library_id, user, command.idempotency_key, 'FEE_GENERATION_RECONCILED', payload, effects,
            {'library_id': library_id, 'loan_id': loan_id, 'fee': fee}, borrower=loan['user_id'])
