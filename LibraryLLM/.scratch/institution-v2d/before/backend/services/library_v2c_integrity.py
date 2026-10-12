"""Read-only reconciliation of circulation, queue links and financial history."""
from backend.database.mongodb import db
from backend.services.institution_repository import collection
from backend.services import library_lending_journal as journal
from backend.services.library_lending_service import scoped
from backend.services.library_fee_service import verify_ledger
from scripts.lending_v2b_operations import reconcile as lending_reconcile


POLICY_FIELDS = ('policy_id', 'library_id', 'version', 'currency', 'rate_minor_per_day',
                 'overdue_enabled', 'grace_days', 'charge_stop_policy', 'day_boundary')


def policy_matches(snapshot, policy):
    return bool(snapshot and policy) and all(snapshot.get(k) == policy.get(k) for k in POLICY_FIELDS)


def reconcile(library_id):
    result = lending_reconcile(library_id); problems = list(result['problems'])
    reservations = list(collection('reservations').find(scoped(library_id)))
    pairs = []; sequences = []
    for row in reservations:
        if not collection('library_books').find_one(scoped(library_id, library_book_id=row['library_book_id'])):
            problems.append('Reservation book does not belong to library: ' + row['reservation_id'])
        sequences.append((row['library_book_id'], row['queue_sequence']))
        if row['status'] in ['WAITING', 'CONVERTED']:
            pairs.append((row['library_book_id'], row['user_id']))
        if row['status'] == 'WAITING':
            if row.get('lending_request_id'):
                problems.append('Waiting reservation must not own a borrow hold: ' + row['reservation_id'])
        requests = list(collection('lending_requests').find(scoped(library_id, reservation_id=row['reservation_id'])))
        if row.get('lending_request_id') or row['status'] in ['CONVERTED', 'FULFILLED']:
            if len(requests) != 1 or requests[0]['lending_request_id'] != row.get('lending_request_id') or requests[0]['request_type'] != 'BORROW' or any(requests[0][k] != row[k] for k in ['library_book_id', 'user_id']):
                problems.append('Converted reservation must link exactly one matching borrow request: ' + row['reservation_id'])
            elif requests[0]['status'] not in {'CONVERTED': ['PENDING'], 'FULFILLED': ['APPROVED'], 'CANCELLED': ['CANCELLED', 'REJECTED'], 'EXPIRED': ['EXPIRED']}.get(row['status'], []):
                problems.append('Reservation lifecycle and linked request disagree: ' + row['reservation_id'])
            elif row['status'] == 'FULFILLED' and row.get('loan_id') != requests[0].get('loan_id'):
                problems.append('Fulfilled reservation loan link disagrees with issuance: ' + row['reservation_id'])
        elif requests:
            problems.append('Unconverted reservation has an unexpected borrow request: ' + row['reservation_id'])
    if len(pairs) != len(set(pairs)) or len(sequences) != len(set(sequences)):
        problems.append('Duplicate active user/book reservation or book queue sequence.')
    counters = list(collection('reservation_counters').find(scoped(library_id)))
    for book_id in {r['library_book_id'] for r in reservations}:
        if not any(c['library_book_id'] == book_id for c in counters):
            problems.append('Queue sequence history has no persistent counter: ' + book_id)
    for counter in counters:
        maximum = max((r['queue_sequence'] for r in reservations if r['library_book_id'] == counter['library_book_id']), default=0)
        if counter['last_sequence'] < maximum:
            problems.append('Queue counter is behind persistent sequence history.')
    policies = {r['policy_id']: r for r in collection('fee_policies').find(scoped(library_id))}
    canonical = (collection('v2c_config').find_one(scoped(library_id)) or {}).get('state') == 'CANONICAL'
    for loan in collection('loans').find(scoped(library_id)):
        if (canonical or loan.get('fee_policy_id')) and not policy_matches(loan.get('fee_policy_snapshot'), policies.get(loan.get('fee_policy_id'))):
            problems.append('Loan policy snapshot does not match immutable tenant policy: ' + loan['loan_id'])
    legacy_ids = []
    for row in collection('fees').find(scoped(library_id)):
        loan = collection('loans').find_one(scoped(library_id, loan_id=row['loan_id']))
        if not loan or any(loan.get(k) != row.get(k) for k in ['user_id', 'library_book_id']):
            problems.append('Fee loan/borrower/book tenancy mismatch: ' + row['fee_id'])
        if not policy_matches(row.get('policy_snapshot'), policies.get(row['policy_id'])):
            problems.append('Fee policy snapshot does not match immutable tenant policy: ' + row['fee_id'])
        if row.get('currency') != (row.get('policy_snapshot') or {}).get('currency'):
            problems.append('Fee currency and policy disagree: ' + row['fee_id'])
        if loan and row.get('source_event') != 'LEGACY_FINE_MIGRATION' and row['policy_id'] != loan.get('fee_policy_id'):
            problems.append('Fee policy does not match loan issuance provenance: ' + row['fee_id'])
        if row.get('legacy_fine_id') is not None:
            legacy_ids.append(row['legacy_fine_id'])
        if loan and loan.get('legacy_issue_id') is not None:
            legacy = list(db.fines.find({'issue_id': loan['legacy_issue_id']}))
            if len(legacy) > 1 or any(f['fine_id'] != row.get('legacy_fine_id') or f.get('user_id') != row['user_id'] for f in legacy):
                problems.append('Legacy/canonical overdue charge mapping requires review: ' + row['fee_id'])
        try:
            verify_ledger(row)
        except journal.RecoveryRequired as error:
            problems.append(str(error) + ': ' + row['fee_id'])
        expected = 'PAID' if row['balance_minor'] == 0 else 'PARTIALLY_PAID' if row['paid_amount_minor'] else 'OPEN'
        if row['status'] not in ['WAIVED', 'CANCELLED', expected] or row['status'] in ['WAIVED', 'CANCELLED'] and row['balance_minor'] != 0:
            problems.append('Fee status and balance disagree: ' + row['fee_id'])
    if len(legacy_ids) != len(set(legacy_ids)):
        problems.append('One legacy fine maps to multiple canonical charges.')
    return {**result, 'ok': not problems, 'problems': problems, 'reservation_count': len(reservations), 'fee_count': collection('fees').count_documents(scoped(library_id))}

