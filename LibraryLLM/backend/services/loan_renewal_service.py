"""Central V1 policy, server eligibility and optimistic/idempotent loan renewal."""
import os
from datetime import datetime, timedelta, timezone
from backend.services import issue_service as loans
from backend.services.notification_service import utc, normalize_dates
from backend.services.loan_notification_service import reconcile_loan_notifications


class RenewalError(ValueError):
    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code, self.status = code, status


def policy():
    try:
        days = int(os.getenv('LOAN_RENEWAL_DAYS', str(loans.LOAN_PERIOD_DAYS)))
        maximum = int(os.getenv('LOAN_MAX_RENEWALS', '1'))
    except ValueError:
        raise RenewalError('RENEWAL_POLICY_INVALID', 'Renewal configuration needs administrator review.', 503)
    if not 1 <= days <= 365 or not 0 <= maximum <= 20:
        raise RenewalError('RENEWAL_POLICY_INVALID', 'Renewal configuration needs administrator review.', 503)
    return {'enabled': os.getenv('LOAN_RENEWAL_ENABLED', '1') == '1',
            'days': days, 'max_renewals': maximum, 'allow_overdue': False}


def with_renewal_policy(records, now=None):
    settings = policy(); now = utc(now or datetime.now(timezone.utc))
    works = {l['work_id'] for l in records if l.get('status') == 'ISSUED'}
    reservations = list(loans.reservations_collection.find({
        'work_id': {'$in': list(works)}, 'status': {'$in': ['ACTIVE', 'READY_FOR_PICKUP']}},
        {'work_id': 1, 'user_id': 1})) if works else []
    result = []
    for loan in records:
        count = loan.get('renewal_count', 0)
        code, message = None, None
        if not settings['enabled']:
            code, message = 'RENEWAL_DISABLED', 'Loan renewal is currently unavailable.'
        elif loan.get('status') != 'ISSUED':
            code, message = 'RENEWAL_NOT_ACTIVE', 'Returned loans cannot be renewed.'
        elif not isinstance(count, int) or isinstance(count, bool) or count < 0:
            code, message = 'RENEWAL_INVALID_STATE', 'This loan needs librarian review.'
        elif count >= settings['max_renewals']:
            code, message = 'RENEWAL_LIMIT_REACHED', 'This loan has used all available renewals.'
        elif utc(loan['due_date']) < now:
            code, message = 'RENEWAL_OVERDUE', 'Overdue loans cannot be renewed. Please return this book.'
        elif any(r['work_id'] == loan['work_id'] and r.get('user_id') != loan['user_id'] for r in reservations):
            code, message = 'RENEWAL_BLOCKED_BY_RESERVATION', 'Another reader is waiting for this book.'
        remaining = max(0, settings['max_renewals'] - count) if isinstance(count, int) else 0
        result.append({**loan, 'renewal_count': count, 'renewal': {
            **settings, 'eligible': code is None, 'reason': code, 'message': message,
            'renewal_count': count, 'remaining_renewals': remaining}})
    return normalize_dates(result)


def owned_loan(issue_id, actor, assisted=False):
    loan = loans.get_issue_by_id(issue_id)
    if not loan:
        raise RenewalError('LOAN_NOT_FOUND', 'Issue record not found.', 404)
    if not assisted and loan['user_id'] != actor:
        raise RenewalError('RENEWAL_NOT_OWNER', 'You can only renew loans issued to you.', 403)
    return loan


def renewal_eligibility(issue_id, actor, assisted=False):
    return with_renewal_policy([owned_loan(issue_id, actor, assisted)])[0]


def _finish(loan, receipt, replay):
    reconcile_loan_notifications(loan['issue_id'], receipt['old_due_date'], 'LOAN_RENEWED', receipt['renewed_at'])
    loans.create_activity(user_id=loan['user_id'], actor_user_id=receipt['actor_user_id'],
        activity_type='BOOK_RENEWED', description=f"Book renewed: {loan['title']}",
        issue_id=loan['issue_id'], work_id=loan['work_id'], title=loan['title'],
        old_due_date=receipt['old_due_date'], new_due_date=receipt['new_due_date'],
        occurred_at=receipt['renewed_at'], event_key=f"BOOK_RENEWED:{loan['issue_id']}:{receipt['request_id']}")
    return normalize_dates({'issue_id': loan['issue_id'], 'work_id': loan['work_id'],
        'old_due_date': receipt['old_due_date'], 'new_due_date': receipt['new_due_date'],
        'renewal_count': receipt['renewal_count'],
        'remaining_renewals': max(0, policy()['max_renewals'] - receipt['renewal_count']),
        'status': loan['status'], 'idempotent_replay': replay})


def renew_loan(issue_id, actor, request_id, expected_due_date, assisted=False, now=None):
    loan = owned_loan(issue_id, actor, assisted)
    def replay_if_found(current):
        for receipt in current.get('renewal_receipts', []):
            if receipt['request_id'] == request_id:
                if receipt['actor_user_id'] != actor or utc(receipt['old_due_date']) != utc(expected_due_date):
                    raise RenewalError('RENEWAL_REQUEST_CONFLICT', 'This renewal request was already used for a different action.')
                return _finish(current, receipt, True)
        return None
    replay = replay_if_found(loan)
    if replay is not None:
        return replay
    state = with_renewal_policy([loan], now)[0]['renewal']
    if not state['eligible']:
        raise RenewalError(state['reason'], state['message'])
    if utc(loan['due_date']) != utc(expected_due_date):
        raise RenewalError('RENEWAL_STATE_CHANGED', 'This loan changed. Refresh before renewing.')
    now = utc(now or datetime.now(timezone.utc)); count = loan.get('renewal_count', 0)
    new_due = utc(loan['due_date']) + timedelta(days=state['days'])
    receipt = {'request_id': request_id, 'actor_user_id': actor, 'old_due_date': loan['due_date'],
               'new_due_date': new_due, 'renewal_count': count + 1, 'renewed_at': now}
    query = {'issue_id': issue_id, 'user_id': loan['user_id'], 'status': 'ISSUED', 'due_date': loan['due_date'],
             '$or': [{'renewal_count': count}, {'renewal_count': {'$exists': False}}] if count == 0 else [{'renewal_count': count}]}
    result = loans.issues_collection.update_one(query, {
        '$set': {'due_date': new_due, 'renewal_count': count + 1, 'last_renewed_at': now,
                 'last_renewal_new_due_date': new_due,
                 'original_due_date': loan.get('original_due_date', loan['due_date'])},
        '$push': {'renewal_receipts': receipt}})
    if not result.modified_count:
        current = owned_loan(issue_id, actor, assisted)
        replay = replay_if_found(current)
        if replay is not None:
            return replay
        raise RenewalError('RENEWAL_STATE_CHANGED', 'This loan changed. Refresh before renewing.')
    return _finish({**loan, 'due_date': new_due}, receipt, False)
