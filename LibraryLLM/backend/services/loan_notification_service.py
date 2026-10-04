"""Resolve historical system reminders without deleting them or changing read state."""
from datetime import datetime, timezone
from backend.services import notification_service as ns

DUE_TYPES = ['DUE_SOON', 'DUE_TODAY', 'OVERDUE']


def reconcile_loan_notifications(loan_id, old_due_date=None, reason='DUE_DATE_CHANGED', now=None):
    query = {'source': 'SYSTEM', 'type': {'$in': DUE_TYPES},
             'source_ref.loan_id': loan_id, 'resolved_at': None}
    if old_due_date is not None:
        query['source_ref.due_date'] = ns.utc(old_due_date).isoformat()
    result = ns.notifications.update_many(query, {'$set': {
        'resolved_at': now or datetime.now(timezone.utc), 'resolution_reason': reason}})
    return result.modified_count


def stale_reason(loan, due_version):
    if not loan:
        return 'LOAN_UNAVAILABLE'
    if loan.get('status') != 'ISSUED':
        return 'LOAN_RETURNED'
    try:
        current_due = ns.utc(loan['due_date'])
    except (KeyError, ValueError, TypeError, AttributeError):
        return 'LOAN_STATE_INVALID'
    if current_due.isoformat() != due_version:
        last = loan.get('last_renewal_new_due_date')
        return 'LOAN_RENEWED' if last and ns.utc(last) == ns.utc(loan['due_date']) else 'DUE_DATE_CHANGED'
    return None


def reconcile_current_reminders(user_ids=None):
    """Recover interrupted reconciliation in bounded, indexed unresolved batches."""
    query = {'source': 'SYSTEM', 'type': {'$in': DUE_TYPES}, 'resolved_at': None}
    if user_ids is not None:
        query['user_id'] = {'$in': list(user_ids)}
    batch, resolved = [], 0
    def flush(rows):
        ids = {n['source_ref']['loan_id'] for n in rows if n.get('source_ref', {}).get('loan_id') is not None}
        loans = {l['issue_id']: l for l in ns.issues_collection.find({'issue_id': {'$in': list(ids)}}, {'_id': 0})}
        count = 0
        for notice in rows:
            ref = notice.get('source_ref', {})
            if ref.get('loan_id') is None or not ref.get('due_date'):
                continue
            loan = loans.get(ref['loan_id'])
            reason = stale_reason(loan, ref['due_date'])
            if reason:
                count += reconcile_loan_notifications(ref['loan_id'], ref['due_date'], reason)
        return count
    for n in ns.notifications.find(query, {'source_ref': 1}).batch_size(500):
        batch.append(n)
        if len(batch) == 500:
            resolved += flush(batch); batch = []
    return resolved + flush(batch)
