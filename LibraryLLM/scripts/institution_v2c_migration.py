"""Explicit tenant evidence, deterministic IDs; legacy records are never changed."""
from decimal import Decimal, InvalidOperation
from uuid import uuid5, NAMESPACE_URL
from fastapi import HTTPException
from backend.database.mongodb import db
from backend.services.institution_repository import collection, library_mutation
from backend.services import library_lending_journal as journal
from backend.services.library_lending_service import scoped, clean, now
from backend.services.library_fee_service import initial_policy


def identity(kind, library_id, old_id):
    return str(uuid5(NAMESPACE_URL, f'luminar-v2c:{kind}:{library_id}:{old_id}'))


def plan(library_id, legacy_library_id, kind):
    alias = collection('library_aliases').find_one({'canonical_library_id': library_id, 'legacy_library_id': legacy_library_id})
    target = 'reservations' if kind == 'reservations' else 'fees'; source = db.reservations if kind == 'reservations' else db.fines
    key = 'reservation_id' if kind == 'reservations' else 'fine_id'; rows = []; quarantine = []; skipped = []
    legacy_policy = collection('fee_policies').find_one(scoped(library_id, version=1))
    policy = clean(legacy_policy) if legacy_policy else initial_policy(library_id, 0)
    counters = {r['library_book_id']: r['last_sequence'] for r in collection('reservation_counters').find(scoped(library_id))}
    records = list(source.find({'$or': [{'library_id': legacy_library_id}, {'library_id': {'$exists': False}}]}))
    if kind == 'reservations':
        records.sort(key=lambda r: (str(r.get('reserved_at', '')), r.get(key, 0)))
    seen = set()
    for record in records:
        old_id = record.get(key)
        def reject(reason): quarantine.append({'legacy_id': old_id, 'reason': reason})
        tenant_proven = record.get('library_id') == legacy_library_id
        if kind == 'fees' and not record.get('library_id') and record.get('issue_id') is not None:
            # Legacy create_fine never stores library_id. A globally unique,
            # explicitly migrated issue→loan identity is independent evidence.
            mapped = list(collection('loans').find({'legacy_issue_id': record['issue_id']}))
            tenant_proven = len(mapped) == 1 and mapped[0]['library_id'] == library_id
        if not alias or not tenant_proven:
            reject('Missing verified tenant alias or record-level library evidence.'); continue
        if collection(target).find_one(scoped(library_id, **{'legacy_' + key: old_id})):
            skipped.append(old_id); continue
        if kind == 'reservations':
            books = list(collection('library_books').find(scoped(library_id, global_work_id=record.get('work_id')))) if record.get('work_id') else []
            if len(books) != 1 or not record.get('reserved_at') or not record.get('user_id'):
                reject('Queue requires unique work-to-library-book mapping and reliable borrower/date.'); continue
            book = books[0]; pair = (book['library_book_id'], record['user_id'])
            if record.get('status') not in ['ACTIVE', 'CANCELLED', 'EXPIRED', 'READY_FOR_PICKUP']:
                reject('Unknown legacy reservation lifecycle requires operator review.'); continue
            if record['status'] == 'READY_FOR_PICKUP':
                reject('Legacy pickup allocation requires explicit physical reconciliation; no synthetic canonical hold.'); continue
            if record['status'] == 'ACTIVE' and (pair in seen or collection('reservations').find_one(scoped(library_id, library_book_id=pair[0], user_id=pair[1], status={'$in': ['WAITING', 'CONVERTED']}))):
                reject('Duplicate active member/book queue entries require operator review.'); continue
            if record['status'] == 'ACTIVE' and (collection('loans').find_one(scoped(library_id, library_book_id=pair[0], user_id=pair[1], status='ACTIVE')) or collection('lending_requests').find_one(scoped(library_id, library_book_id=pair[0], user_id=pair[1], request_type='BORROW', status='PENDING'))):
                reject('Active canonical loan/borrow hold conflicts with legacy waiting entry.'); continue
            if record['status'] == 'ACTIVE': seen.add(pair)
            counters[pair[0]] = counters.get(pair[0], 0) + 1
            rows.append({'reservation_id': identity(kind, library_id, old_id), 'library_id': library_id, 'library_book_id': pair[0],
                'user_id': pair[1], 'global_work_id': book.get('global_work_id'), 'title': book['title'], 'accession_number': book['accession_number'],
                'queue_sequence': counters[pair[0]], 'status': 'WAITING' if record['status'] == 'ACTIVE' else 'CANCELLED' if record['status'] == 'CANCELLED' else 'EXPIRED',
                'requested_at': record['reserved_at'], 'created_at': record['reserved_at'], 'updated_at': now(), 'expires_at': None,
                'lending_request_id': None, 'loan_id': None, 'legacy_reservation_id': old_id, 'migration_provenance': 'Explicit alias + unique tenant global-work mapping; reserved_at then legacy ID.'})
        else:
            loans = list(collection('loans').find(scoped(library_id, legacy_issue_id=record.get('issue_id')))) if record.get('issue_id') is not None else []
            if len(loans) != 1 or loans[0]['user_id'] != record.get('user_id'):
                reject('Fine requires one proven canonical loan and matching borrower.'); continue
            loan = loans[0]
            if loan['loan_id'] in seen or collection('fees').find_one(scoped(library_id, loan_id=loan['loan_id'], fee_type='OVERDUE')):
                reject('A canonical overdue fee or duplicate legacy fine already exists for this loan.'); continue
            try:
                minor = Decimal(str(record['amount'])) * 100
                if minor != minor.to_integral_value() or minor < 0 or minor > 1000000000000:
                    raise ValueError()
                amount = int(minor)
            except (KeyError, ValueError, InvalidOperation):
                reject('Legacy amount cannot be represented exactly in supported minor units.'); continue
            if record.get('status') not in ['PAID', 'UNPAID'] or not record.get('created_at'):
                reject('Fine payment status or creation date is unproven.'); continue
            seen.add(loan['loan_id']); paid = amount if record['status'] == 'PAID' else 0
            rows.append({'fee_id': identity(kind, library_id, old_id), 'library_id': library_id, 'loan_id': loan['loan_id'],
                'library_book_id': loan['library_book_id'], 'user_id': loan['user_id'], 'borrower_user_id': loan['user_id'],
                'title': loan['title'], 'accession_number': loan['accession_number'], 'fee_type': 'OVERDUE', 'status': 'PAID' if paid == amount else 'OPEN',
                'currency': 'INR', 'original_amount_minor': amount, 'current_amount_minor': amount, 'paid_amount_minor': paid, 'balance_minor': amount - paid,
                'policy_id': policy['policy_id'], 'policy_snapshot': policy, 'calculation': {'kind': 'LEGACY_IMPORTED', 'amount_minor': amount, 'legacy_issue_id': record['issue_id']},
                'source_event': 'LEGACY_FINE_MIGRATION', 'created_at': record['created_at'], 'updated_at': now(), 'legacy_fine_id': old_id,
                'legacy_paid_at': record.get('paid_at'), 'migration_provenance': 'Verified alias and unique migrated canonical loan; original legacy INR amount/payment history retained without retrospective recalculation.'})
    return {'library_id': library_id, 'legacy_library_id': legacy_library_id, 'kind': kind, 'read_only': True,
        'ok': bool(alias) and journal.state(library_id) == 'CANONICAL', 'rows': rows, 'quarantine': quarantine, 'already_migrated': skipped,
        'counters': counters, 'policy': policy}


def apply(library_id, legacy_library_id, kind, *, writers_stopped, idempotency_key):
    if not writers_stopped:
        raise ValueError('Stop all API and worker writers before applying migration.')
    with library_mutation(library_id, wait_seconds=1, durable=True):
        payload = {'legacy_library_id': legacy_library_id, 'kind': kind}
        old = journal.receipt(library_id, 0, idempotency_key, 'V2C_MIGRATION', payload)
        if old is not None: return old
        result = plan(library_id, legacy_library_id, kind)
        if not result['ok']:
            raise HTTPException(409, 'Proven alias and canonical Part 2B lending are required.')
        from backend.services.library_reservation_service import ensure_indexes
        ensure_indexes(); effects = []; policy = result['policy']
        if not collection('fee_policies').find_one(scoped(library_id, policy_id=policy['policy_id'])):
            effects.append(journal.effect('fee_policies', scoped(library_id, policy_id=policy['policy_id']), policy, True))
        for row in result['rows']:
            target, key = ('reservations', 'reservation_id') if kind == 'reservations' else ('fees', 'fee_id')
            effects.append(journal.effect(target, scoped(library_id, **{key: row[key]}), row, True))
            if kind == 'fees':
                for event, amount in [('CHARGE', row['original_amount_minor']), ('PAYMENT_RECORD', row['paid_amount_minor'])]:
                    if event == 'PAYMENT_RECORD' and not amount: continue
                    entry_id = identity(event, library_id, row['legacy_fine_id'])
                    entry = {'entry_id': entry_id, 'library_id': library_id, 'fee_id': row['fee_id'], 'entry_type': event,
                        'amount_minor': amount, 'reason': 'Imported legacy history; no money processed.', 'actor_user_id': 0, 'created_at': row['created_at']}
                    if event == 'PAYMENT_RECORD': entry.update({'method': 'OTHER', 'receipt_id': identity('legacy-receipt', library_id, row['legacy_fine_id']), 'payment_processing': 'LEGACY_IMPORTED'})
                    effects.append(journal.effect('fee_ledger', scoped(library_id, entry_id=entry_id), entry, True))
        if kind == 'reservations':
            for book_id, sequence in result['counters'].items():
                query = scoped(library_id, library_book_id=book_id)
                effects.append(journal.effect('reservation_counters', query, {**query, 'last_sequence': sequence}, not bool(collection('reservation_counters').find_one(query))))
        return journal.commit(library_id, 0, idempotency_key, 'V2C_MIGRATION', payload, effects, {**result, 'read_only': False})
