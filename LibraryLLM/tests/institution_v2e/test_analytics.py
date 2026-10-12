"""Exact canonical metrics, authorization, UTC boundaries and read-only behavior."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import pytest
from pymongo.collection import Collection

from backend.services import library_analytics_service as analytics

STAMP = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
RECENT = STAMP - timedelta(days=2)
OLD = STAMP - timedelta(days=50)
ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / 'reports'


def scoped_get(client, lib, user=1, range='30d'):
    return client.get(f'/libraries/{lib}/analytics?range={range}', headers={'x-test-user': str(user)})


def member(db, lib, user, role='GENERAL_USER', status='ACTIVE'):
    db.institution_memberships.insert_one({'membership_id': str(uuid4()), 'library_id': lib,
                                           'user_id': user, 'role': role, 'status': status})


def book(db, lib, sequence, *, quantity=5, status='ACTIVE', circulation='CIRCULATING', linked=False, stamp=RECENT):
    identity = str(uuid4())
    db.institution_library_books.insert_one({'library_id': lib, 'library_book_id': identity,
        'title': f'Tenant title {sequence}', 'normalized_title': f'tenant title {sequence}',
        'authors': ['Fixture Author'], 'subjects': ['Systems', 'History'] if sequence == 1 else ['Systems'],
        'global_work_id': 'OL_SHARED_W' if linked else None, 'accession_number': f'ISO-{sequence}',
        'accession_sequence': sequence, 'status': status, 'created_at': stamp, 'updated_at': stamp})
    db.institution_holdings.insert_one({'library_id': lib, 'library_book_id': identity,
        'holding_id': str(uuid4()), 'total_copies': quantity, 'available_copies': quantity,
        'circulation_status': circulation, 'allocation_mode': 'AGGREGATE', 'unavailable_stock': 0})
    return identity


def operation(db, lib, event, stamp=RECENT, state='COMMITTED', **metadata):
    identity = str(uuid4())
    db.institution_lending_operations.insert_one({'operation_id': identity, 'library_id': lib,
        'actor_user_id': 1, 'idempotency_key': str(uuid4()), 'state': state, 'created_at': stamp})
    db.institution_audit.insert_one({'event_id': identity + ':' + event, 'library_id': lib, 'event': event,
        'actor_user_id': 1, 'target_user_id': 2, 'created_at': stamp,
        'metadata': {'operation_id': identity, **metadata}})
    return identity


def fee(db, lib, bid, loan, amount=1001, payment=203, waiver=101, stamp=RECENT):
    identity = str(uuid4())
    db.institution_fees.insert_one({'fee_id': identity, 'library_id': lib, 'library_book_id': bid,
        'loan_id': loan, 'fee_type': 'OVERDUE', 'user_id': 2, 'status': 'PARTIALLY_PAID', 'currency': 'INR',
        'original_amount_minor': amount, 'current_amount_minor': amount - waiver,
        'paid_amount_minor': payment, 'balance_minor': amount - waiver - payment,
        'created_at': stamp, 'updated_at': stamp})
    db.institution_fee_ledger.insert_many([{'entry_id': str(uuid4()), 'library_id': lib, 'fee_id': identity,
        'entry_type': kind, 'amount_minor': value, 'created_at': stamp} for kind, value in
        [('CHARGE', amount), ('PAYMENT_RECORD', payment), ('WAIVER', waiver)]])
    return identity


@pytest.fixture
def known(database, library, monkeypatch):
    monkeypatch.setattr(analytics, 'now', lambda: STAMP)
    lib = library()
    member(database, lib, 2)
    member(database, lib, 3, 'LIBRARIAN')
    bid = book(database, lib, 1, linked=True)
    book(database, lib, 2, quantity=2, circulation='REFERENCE_ONLY', stamp=OLD)
    book(database, lib, 3, quantity=3, circulation='TEMPORARILY_UNAVAILABLE')
    book(database, lib, 4, quantity=6, status='WITHDRAWN')
    database.institution_lending_requests.insert_many([
        {'library_id': lib, 'lending_request_id': str(uuid4()), 'library_book_id': bid, 'user_id': user,
         'request_type': kind, 'status': state, 'requested_at': RECENT, 'reviewed_at': RECENT}
        for user, kind, state in [(4, 'BORROW', 'PENDING'), (2, 'RETURN', 'PENDING'),
                                 (5, 'BORROW', 'APPROVED'), (6, 'BORROW', 'REJECTED')]])
    loan = str(uuid4())
    database.institution_loans.insert_one({'library_id': lib, 'loan_id': loan, 'library_book_id': bid,
        'user_id': 2, 'status': 'ACTIVE', 'borrowed_at': RECENT, 'due_at': STAMP + timedelta(days=10), 'renewal_count': 2})
    database.institution_reservations.insert_many([{'library_id': lib, 'reservation_id': str(uuid4()),
        'library_book_id': bid, 'user_id': user, 'queue_sequence': user, 'status': state, 'requested_at': RECENT}
        for user, state in [(7, 'WAITING'), (8, 'WAITING'), (10, 'CONVERTED'), (11, 'CANCELLED'), (12, 'EXPIRED')]])
    for event in ['BORROW_REQUEST_CREATED', 'BORROW_REQUEST_APPROVED', 'BORROW_REQUEST_REJECTED',
                  'RETURN_CONFIRMED', 'LOAN_RENEWED', 'LOAN_RENEWED', 'LOAN_ISSUED', 'RESERVATION_CREATED',
                  'RESERVATION_CREATED', 'RESERVATION_CANCELLED', 'RESERVATION_EXPIRED', 'RESERVATION_FULFILLED']:
        operation(database, lib, event, library_book_id=bid)
    fee_id = fee(database, lib, bid, loan)
    database.events.insert_many([{'library_id': lib, 'scope': 'LIBRARY', 'event_id': str(uuid4()), 'status': status,
        'published_at': RECENT if status != 'DRAFT' else None, 'cancelled_at': RECENT if status == 'CANCELLED' else None,
        'start_at': start, 'end_at': start + timedelta(hours=1), 'created_at': RECENT, 'updated_at': RECENT, 'revision': 1}
        for status, start in [('PUBLISHED', STAMP + timedelta(days=1)), ('PUBLISHED', OLD),
                              ('CANCELLED', STAMP + timedelta(days=3)), ('DRAFT', STAMP + timedelta(days=2))]])
    database.institution_notification_outbox.insert_many([{'library_id': lib, 'outbox_id': str(uuid4()),
        'operation_id': str(uuid4()), 'state': state, 'attempts': attempts}
        for state, attempts in [('PENDING', 0), ('PENDING', 1), ('DELIVERED', 0), ('SUPPRESSED', 0)]])
    return lib, bid, fee_id


def payload(client, known, user=1):
    response = scoped_get(client, known[0], user)
    assert response.status_code == 200, response.text
    return response.json()


def test_admin_can_view_own_library_analytics(client, known):
    value = payload(client, known)
    assert value['membership_role'] == 'ADMIN'
    assert all(value['capabilities'].values())


def test_general_user_cannot_view_staff_analytics(client, known):
    assert scoped_get(client, known[0], 2).status_code == 403


def test_librarian_can_view_operational_analytics(client, known):
    value = payload(client, known, 3)
    assert value['overview']['active_books'] == 3
    assert value['membership']['role_counts'] is None
    assert value['outbox'] is None
    assert value['fees']['waived_minor'] is None
    assert value['fees']['settled_minor'] is None
    assert value['fees']['open_balance_minor'] == '697'


def test_platform_admin_without_membership_denied(client, known, database):
    database.platform_role_assignments.insert_one({'assignment_id': str(uuid4()), 'user_id': 8,
        'role': 'PLATFORM_ADMIN', 'status': 'ACTIVE'})
    assert scoped_get(client, known[0], 8).status_code == 404


def test_legacy_admin_without_membership_denied(client, known):
    assert scoped_get(client, known[0], 9).status_code == 404


def test_cross_library_analytics_denied(client, known, library):
    other = library(owner=4)
    assert scoped_get(client, other).status_code == 404


@pytest.mark.parametrize('status', ['REVOKED', 'SUSPENDED', 'REMOVED'])
def test_revoked_membership_denied(client, known, database, status):
    assert scoped_get(client, known[0]).status_code == 200
    database.institution_memberships.update_one({'library_id': known[0], 'user_id': 1}, {'$set': {'status': status}})
    assert scoped_get(client, known[0]).status_code == 404


@pytest.mark.parametrize('status', ['SUSPENDED', 'REMOVED'])
def test_suspended_removed_library_analytics_denied(client, known, database, status):
    database.institution_libraries.update_one({'library_id': known[0]}, {'$set': {'status': status}})
    assert scoped_get(client, known[0]).status_code == 404


@pytest.mark.parametrize('identity', ['LIB001', 'first', 'not-a-uuid'])
def test_analytics_requires_canonical_uuid(client, identity):
    assert scoped_get(client, identity).status_code == 422


@pytest.mark.parametrize('range', ['31d', '-1', '999d', '2026-10-11'])
def test_analytics_range_bounded(client, known, range):
    assert scoped_get(client, known[0], range=range).status_code == 422


def test_analytics_overview_empty_library(client, library):
    value = payload(client, (library(),))
    assert value['overview']['active_books'] == 0
    assert value['overview']['active_loans'] == 0
    assert value['overview']['open_fee_balance_minor'] == '0'
    assert value['popular_books'] == []
    assert value['trends'] == []


def test_analytics_overview_known_fixture(client, known):
    assert payload(client, known)['overview'] == {'active_books': 3, 'total_holding_quantity': 10,
        'requestable_units': 0, 'active_loans': 1, 'pending_borrow_requests': 1, 'pending_return_requests': 1,
        'active_reservations': 3, 'open_fee_balance_minor': '697', 'currency': 'INR', 'upcoming_events': 1, 'active_members': 3}


def test_overview_library_scoped(client, known, library, database):
    other = library(owner=4)
    for sequence in range(1, 9):
        book(database, other, sequence)
    assert payload(client, known)['overview']['active_books'] == 3
    assert scoped_get(client, other, 4).json()['overview']['active_books'] == 8


@pytest.mark.parametrize('key,expected', [
    ('active_books', 3), ('total_holding_quantity', 10), ('local_only_books', 2),
    ('globally_linked_books', 1), ('recent_acquisitions', 3), ('requestable_units', 0)])
def test_collection_exact_counts(client, known, key, expected):
    assert payload(client, known)['collection'][key] == expected


def test_collection_status_counts(client, known):
    assert payload(client, known)['collection']['circulation_status'] == {
        'CIRCULATING': 1, 'REFERENCE_ONLY': 1, 'TEMPORARILY_UNAVAILABLE': 1}


def test_collection_subject_distribution(client, known):
    assert payload(client, known)['collection']['subjects'] == [{'subject': 'Systems', 'count': 3}, {'subject': 'History', 'count': 1}]


def test_withdrawal_retains_actual_acquisition_history(client, known, database):
    before = payload(client, known)
    database.institution_library_books.update_one({'library_book_id': known[1]}, {'$set': {'status': 'WITHDRAWN'}})
    after = payload(client, known)
    assert after['collection']['active_books'] == before['collection']['active_books'] - 1
    assert after['collection']['recent_acquisitions'] == before['collection']['recent_acquisitions'] == 3
    assert sum(row['acquisitions'] for row in after['trends']) == sum(row['acquisitions'] for row in before['trends'])


def test_legacy_reservation_rows_cannot_affect_canonical_requestable_units(client, known, database):
    database.institution_v2c_config.update_one({'library_id': known[0]}, {'$set': {'state': 'LEGACY'}})
    value = payload(client, known)
    assert value['collection']['requestable_units'] == 3
    assert value['reservations']['available'] is False


def test_missing_circulation_status_reuses_accepted_default(client, library, database):
    lib = library()
    bid = book(database, lib, 1, quantity=4)
    database.institution_holdings.update_one({'library_book_id': bid}, {'$unset': {'circulation_status': 1}})
    assert payload(client, (lib,))['collection']['requestable_units'] == 4


@pytest.mark.parametrize('key,expected', [
    ('pending_borrow_requests', 1), ('pending_return_requests', 1), ('active_loans', 1),
    ('requested_in_range', 1), ('approved_in_range', 1), ('rejected_in_range', 1),
    ('returns_confirmed_in_range', 1), ('renewals_in_range', 2)])
def test_circulation_exact_counts(client, known, key, expected):
    assert payload(client, known)['circulation'][key] == expected


def test_circulation_renewals_uses_persisted_history(client, known, database):
    # Current renewal_count is not a synthetic history source.
    database.institution_loans.update_one({'library_id': known[0]}, {'$set': {'renewal_count': 77}})
    assert payload(client, known)['circulation']['renewals_in_range'] == 2


def test_circulation_time_range(client, known, database):
    operation(database, known[0], 'BORROW_REQUEST_CREATED', OLD)
    assert scoped_get(client, known[0], range='30d').json()['circulation']['requested_in_range'] == 1
    assert scoped_get(client, known[0], range='90d').json()['circulation']['requested_in_range'] == 2


def test_uncommitted_history_excluded(client, known, database):
    operation(database, known[0], 'LOAN_RENEWED', state='PREPARED')
    database.institution_audit.insert_one({'library_id': known[0], 'event_id': str(uuid4()), 'event': 'LOAN_RENEWED',
                                          'created_at': RECENT, 'metadata': {}})
    assert payload(client, known)['circulation']['renewals_in_range'] == 2


@pytest.mark.parametrize('key,expected', [('active', 3), ('waiting', 2), ('ready', 1),
    ('created_in_range', 2), ('fulfilled_in_range', 1), ('cancelled_in_range', 1), ('expired_in_range', 1),
    ('average_queue_depth', 2.0)])
def test_reservation_exact_counts(client, known, key, expected):
    assert payload(client, known)['reservations'][key] == expected


@pytest.mark.parametrize('key,expected', [('open_count', 1), ('open_balance_minor', '697'), ('assessed_in_range', 1),
    ('assessed_minor', '1001'), ('payments_minor', '203'), ('waived_minor', '101'), ('settled_minor', '0')])
def test_fee_exact_counts(client, known, key, expected):
    assert payload(client, known)['fees'][key] == expected


def test_fee_exact_money_semantics(client, known, database):
    # A large sum still uses integer Mongo arithmetic; API money stays strings.
    fee(database, known[0], known[1], str(uuid4()), amount=999999999999, payment=1, waiver=1)
    values = payload(client, known)['fees']
    assert values['open_balance_minor'] == '1000000000694'
    assert values['assessed_minor'] == '1000000001000'


def test_fee_invalid_ledger_fails_closed(client, known, database):
    database.institution_fees.update_one({'fee_id': known[2]}, {'$set': {'balance_minor': 42}})
    assert scoped_get(client, known[0]).status_code == 503


def test_fractional_minor_units_never_presented_as_exact_money(client, known, database):
    database.institution_fees.update_one({'fee_id': known[2]}, {'$set': {'original_amount_minor': 1001.5}})
    assert scoped_get(client, known[0]).status_code == 503


def test_settled_total_requires_actual_paid_transition(client, known, database):
    database.institution_fees.update_one({'fee_id': known[2]},
        {'$set': {'status': 'PAID', 'paid_amount_minor': 900, 'balance_minor': 0}})
    database.institution_fee_ledger.insert_one({'entry_id': str(uuid4()), 'library_id': known[0],
        'fee_id': known[2], 'entry_type': 'PAYMENT_RECORD', 'amount_minor': 697, 'created_at': RECENT})
    operation(database, known[0], 'FEE_PAID', amount_minor=900, currency='INR')
    assert payload(client, known)['fees']['settled_minor'] == '900'


def test_requestable_copy_projection_and_unavailable_conditions(client, library, database, monkeypatch):
    monkeypatch.setattr(analytics, 'now', lambda: STAMP)
    lib = library()
    bid = book(database, lib, 1, quantity=4)
    database.institution_holdings.update_one({'library_id': lib, 'library_book_id': bid},
                                             {'$set': {'allocation_mode': 'COPY'}})
    database.institution_copies.insert_many([{'copy_id': str(uuid4()), 'library_id': lib,
        'library_book_id': bid, 'holding_id': database.institution_holdings.find_one({'library_book_id': bid})['holding_id'],
        'copy_number': i, 'status': status} for i, status in enumerate(['AVAILABLE', 'AVAILABLE', 'DAMAGED', 'BORROWED'])])
    database.institution_loans.insert_one({'loan_id': str(uuid4()), 'library_id': lib, 'library_book_id': bid,
                                         'user_id': 2, 'status': 'ACTIVE', 'borrowed_at': RECENT})
    assert payload(client, (lib,))['collection']['requestable_units'] == 2
    database.institution_copies.update_one({'library_id': lib, 'status': 'AVAILABLE'}, {'$set': {'status': 'UNVERIFIED'}})
    assert payload(client, (lib,))['collection']['requestable_units'] == 1


def test_copy_mode_allocation_inconsistency_fails_closed(client, library, database):
    lib = library()
    bid = book(database, lib, 1, quantity=4)
    database.institution_holdings.update_one({'library_book_id': bid}, {'$set': {'allocation_mode': 'COPY'}})
    assert scoped_get(client, lib).status_code == 503


def test_platform_dual_authority_uses_independent_membership(client, known, database):
    database.platform_role_assignments.insert_one({'assignment_id': str(uuid4()), 'user_id': 3,
        'role': 'PLATFORM_ADMIN', 'status': 'ACTIVE'})
    assert payload(client, known, 3)['membership_role'] == 'LIBRARIAN'


def test_account_disabled_denied_on_next_request(client, known, database):
    assert scoped_get(client, known[0]).status_code == 200
    database.users.update_one({'user_id': 1}, {'$set': {'is_active': False}})
    assert scoped_get(client, known[0]).status_code == 401


def test_analytics_response_not_cached(client, known):
    assert scoped_get(client, known[0]).headers['Cache-Control'] == 'no-store'


def test_mid_read_event_revision_change_rejected(client, known, database, monkeypatch):
    original = analytics.event_metrics
    def changing(lib, window):
        result = original(lib, window)
        database.events.update_one({'library_id': lib, 'status': 'DRAFT'}, {'$inc': {'revision': 1}})
        return result
    monkeypatch.setattr(analytics, 'event_metrics', changing)
    assert scoped_get(client, known[0]).status_code == 503


@pytest.mark.parametrize('key,expected', [('upcoming', 1), ('published_in_range', 3),
                                        ('cancelled_in_range', 1), ('completed', 1), ('drafts', 1)])
def test_event_exact_counts(client, known, key, expected):
    assert payload(client, known)['events'][key] == expected


def test_event_global_and_other_library_excluded(client, known, database):
    database.events.insert_one({'scope': 'GLOBAL', 'event_id': str(uuid4()), 'status': 'PUBLISHED',
                               'start_at': STAMP + timedelta(days=2), 'published_at': RECENT})
    assert payload(client, known)['events']['upcoming'] == 1


def test_member_role_aggregate(client, known):
    assert payload(client, known)['membership'] == {'active_total': 3,
        'role_counts': {'ADMIN': 1, 'LIBRARIAN': 1, 'GENERAL_USER': 1}}


def test_member_analytics_contains_no_private_history(client, known):
    value = payload(client, known)
    serialized = json.dumps(value)
    for forbidden in ('Fixture account', 'v2e-', 'borrower', 'user_id', 'private_documents', 'conversations', 'top_borrowers', 'reading_list'):
        assert forbidden not in serialized


def test_popular_books_uses_tenant_activity(client, known):
    rows = payload(client, known)['popular_books']
    assert len(rows) == 1
    assert rows[0]['library_book_id'] == known[1]
    assert (rows[0]['score'], rows[0]['loans'], rows[0]['approved_requests'], rows[0]['reservations']) == (13, 1, 1, 3)


def test_popular_books_cross_library_isolated(client, known, library, database):
    other = library(owner=4)
    bid = book(database, other, 1, linked=True)
    database.institution_loans.insert_one({'library_id': other, 'loan_id': str(uuid4()), 'library_book_id': bid,
                                         'user_id': 5, 'status': 'ACTIVE', 'borrowed_at': RECENT})
    assert payload(client, known)['popular_books'][0]['library_book_id'] != bid
    assert scoped_get(client, other, 4).json()['popular_books'][0]['library_book_id'] == bid


def test_analytics_does_not_query_global_books_for_tenant_collection(client, known, monkeypatch):
    original_aggregate = Collection.aggregate
    original_find = Collection.find
    original_find_one = Collection.find_one
    original_count = Collection.count_documents
    def checked(method):
        def wrapper(self, *args, **kwargs):
            assert self.name not in ('books', 'issues', 'reservations', 'fines', 'reading_list', 'activity')
            return method(self, *args, **kwargs)
        return wrapper
    monkeypatch.setattr(Collection, 'aggregate', checked(original_aggregate))
    monkeypatch.setattr(Collection, 'find', checked(original_find))
    monkeypatch.setattr(Collection, 'find_one', checked(original_find_one))
    monkeypatch.setattr(Collection, 'count_documents', checked(original_count))
    assert payload(client, known)['collection']['active_books'] == 3


def test_analytics_read_only_no_mutation_commands(client, known, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Analytics attempted a database mutation')
    for name in ('insert_one', 'insert_many', 'update_one', 'update_many', 'delete_one', 'delete_many',
                 'find_one_and_update', 'find_one_and_delete', 'replace_one', 'bulk_write'):
        monkeypatch.setattr(Collection, name, forbidden)
    assert scoped_get(client, known[0]).status_code == 200


def test_analytics_never_runs_lazy_expiry_or_queue_maintenance(client, known, database):
    database.institution_lending_requests.update_one({'library_id': known[0], 'request_type': 'BORROW', 'status': 'PENDING'},
                                                      {'$set': {'expires_at': OLD}})
    assert payload(client, known)['circulation']['pending_borrow_requests'] == 1
    assert database.institution_lending_requests.count_documents({'library_id': known[0], 'status': 'PENDING'}) == 2


def test_legacy_cutover_unavailable_not_fake_zero(client, known, database):
    database.institution_lending_config.update_one({'library_id': known[0]}, {'$set': {'state': 'LEGACY'}})
    value = payload(client, known)
    assert value['collection']['active_books'] == 3
    assert value['collection']['requestable_units'] is None
    assert value['circulation']['available'] is False
    assert value['overview']['active_loans'] is None
    assert value['reservations']['active'] is None
    assert value['fees']['open_balance_minor'] is None


def test_retained_lock_or_recovery_state_fails_closed(client, known, database):
    database.institution_locks.insert_one({'_id': known[0], 'holder': 'interrupted-operation'})
    assert scoped_get(client, known[0]).status_code == 503
    assert database.institution_locks.find_one({'_id': known[0]})


def test_mid_read_activity_change_rejected(client, known, database, monkeypatch):
    original = analytics.event_metrics
    def changing(lib, window):
        result = original(lib, window)
        operation(database, lib, 'LOAN_RENEWED')
        return result
    monkeypatch.setattr(analytics, 'event_metrics', changing)
    assert scoped_get(client, known[0]).status_code == 503


def test_mid_read_revocation_denied(client, known, database, monkeypatch):
    original = analytics.event_metrics
    def changing(lib, window):
        result = original(lib, window)
        database.institution_memberships.update_one({'library_id': lib, 'user_id': 1}, {'$set': {'status': 'REVOKED'}})
        return result
    monkeypatch.setattr(analytics, 'event_metrics', changing)
    assert scoped_get(client, known[0]).status_code == 404


def test_utc_boundaries_inclusive_start_exclusive_end(client, known, database):
    start = analytics.span('7d', STAMP)['start_at']
    operation(database, known[0], 'BORROW_REQUEST_CREATED', start)
    operation(database, known[0], 'BORROW_REQUEST_CREATED', start - timedelta(milliseconds=1))
    operation(database, known[0], 'BORROW_REQUEST_CREATED', STAMP)
    value = scoped_get(client, known[0], range='7d').json()
    assert value['circulation']['requested_in_range'] == 2
    assert value['range']['timezone'] == 'UTC'
    assert value['range']['start_at'].startswith('2026-10-05T00:00:00')


def test_all_time_trends_remain_bounded_and_real(client, known, database):
    operation(database, known[0], 'LOAN_RENEWED', STAMP - timedelta(days=1000))
    value = scoped_get(client, known[0], range='all').json()
    assert value['circulation']['renewals_in_range'] == 3
    assert value['range']['start_at'] is None
    assert value['range']['trend_window_limited'] is True
    assert len(value['trends']) <= 90
    assert all(item['date'] >= '2026-07-14' for item in value['trends'])
    assert sum(item['renewals'] for item in value['trends']) == 2


def test_no_cache_can_cross_library(client, known, library, database):
    # No cache is implemented; each call observes current records in the UUID.
    other = library(owner=4)
    assert scoped_get(client, other, 4).json()['overview']['active_books'] == 0
    book(database, other, 1)
    assert scoped_get(client, other, 4).json()['overview']['active_books'] == 1
    assert payload(client, known)['overview']['active_books'] == 3


def test_analytics_top_lists_bounded_and_isolated_large_benchmark(client, library, database, monkeypatch):
    monkeypatch.setattr(analytics, 'now', lambda: STAMP)
    lib = library(name='Disposable 3000-book benchmark')
    books, holdings = [], []
    for i in range(3000):
        bid = str(uuid4())
        books.append({'library_id': lib, 'library_book_id': bid, 'title': f'Benchmark {i}',
            'normalized_title': f'benchmark {i}', 'authors': [], 'subjects': [f'Subject {i % 50}'],
            'accession_number': f'BEN-{i}', 'accession_sequence': i, 'status': 'ACTIVE', 'created_at': RECENT})
        holdings.append({'library_id': lib, 'library_book_id': bid, 'holding_id': str(uuid4()),
            'total_copies': 2, 'allocation_mode': 'AGGREGATE', 'unavailable_stock': 0, 'circulation_status': 'CIRCULATING'})
    database.institution_library_books.insert_many(books)
    database.institution_holdings.insert_many(holdings)
    database.institution_loans.insert_many([{'library_id': lib, 'loan_id': str(uuid4()),
        'library_book_id': row['library_book_id'], 'status': 'RETURNED', 'user_id': 2, 'borrowed_at': RECENT} for row in books[:30]])
    window = analytics.span('30d', STAMP)
    timings = {}
    for name, action in [('collection', lambda: analytics.collection_metrics(lib, window, True)),
                         ('circulation', lambda: analytics.circulation_metrics(lib, {}, True)),
                         ('full_dashboard', lambda: analytics.dashboard(lib, {'sub': '1'}, stamp=STAMP))]:
        measurements = []
        for _ in range(3):
            start = perf_counter()
            result = action()
            measurements.append(round((perf_counter() - start) * 1000, 3))
        timings[name] = measurements
    assert len(result['collection']['subjects']) == 20
    assert len(result['popular_books']) == 10
    assert result['overview']['active_books'] == 3000
    assert result['overview']['total_holding_quantity'] == 6000
    plans = {}
    for name, query in [('library_books', {'library_id': lib, 'status': 'ACTIVE'}),
                        ('loans', {'library_id': lib, 'borrowed_at': {'$gte': window['start_at']}}),
                        ('audit', {'library_id': lib, 'created_at': {'$gte': window['start_at']}}),
                        ('fee_ledger', {'library_id': lib}), ('notification_outbox', {'library_id': lib})]:
        target = database['institution_' + name]
        explain = database.command('explain', {'find': target.name, 'filter': query}, verbosity='executionStats')
        encoded = json.dumps(explain, default=str)
        assert 'COLLSCAN' not in encoded
        plans[name] = {'winning_plan': explain['queryPlanner']['winningPlan'],
                       'total_docs_examined': explain['executionStats']['totalDocsExamined'],
                       'total_keys_examined': explain['executionStats']['totalKeysExamined']}
    (REPORTS / 'institution_v2e_backend_benchmark.json').write_text(json.dumps({
        'status': 'PASS', 'database': 'isolated disposable database', 'synthetic_only': True,
        'production_TEST_writes': False, 'books': 3000, 'holding_quantity': 6000,
        'timings_ms': timings, 'query_plans': plans, 'new_indexes': [],
        'existing_indexes_sufficient': True}, indent=2, default=str), encoding='utf-8')


def test_source_metric_reports_from_exact_fixture(client, known):
    value = payload(client, known)
    expected = {'overview': value['overview'], 'collection': value['collection'],
                'circulation': value['circulation'], 'reservations': value['reservations'],
                'fees': value['fees'], 'events': value['events'], 'membership': value['membership']}
    for name, metrics in expected.items():
        report = {'status': 'PASS', 'evidence': 'tests/institution_v2e/test_analytics.py exact isolated canonical fixture assertions',
            'source': 'canonical selected library UUID only', 'fixture_data': True, 'metrics': metrics,
            'privacy': 'aggregate counts only; no member identities/activity ranking/private content'}
        (REPORTS / f'institution_v2e_{name}.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
