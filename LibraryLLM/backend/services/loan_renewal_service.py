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
    settings = policy()
    return normalize_dates([{**loan, 'renewal_count': loan.get('renewal_count',0), 'renewal': {
        **settings, 'eligible': False, 'reason': 'LEGACY_READ_ONLY',
        'message': 'Historical record; use your canonical library workspace.',
        'renewal_count': loan.get('renewal_count',0), 'remaining_renewals': 0}} for loan in records])


def owned_loan(issue_id, actor, assisted=False):
    loan = loans.get_issue_by_id(issue_id)
    if not loan:
        raise RenewalError('LOAN_NOT_FOUND', 'Issue record not found.', 404)
    from backend.services.library_lending_legacy import guard_loan
    guard_loan(loan)
    if not assisted and loan['user_id'] != actor:
        raise RenewalError('RENEWAL_NOT_OWNER', 'You can only renew loans issued to you.', 403)
    return loan


def renewal_eligibility(issue_id, actor, assisted=False):
    return with_renewal_policy([owned_loan(issue_id, actor, assisted)])[0]


def renew_loan(issue_id, actor, request_id, expected_due_date, assisted=False, now=None):
    from backend.platform_dependencies import retirement
    retirement()
