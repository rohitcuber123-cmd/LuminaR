"""Read-only canonical tenant aggregates. Never invokes lazy domain maintenance.

Every root and lookup predicate includes the canonical UUID. Aggregation returns
only totals and bounded lists. Optimistic audit/revision barriers detect a domain
write completed between reads; an active or interrupted gate fails closed.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException

from backend.database.mongodb import db
from backend.services.institution_repository import collection, require_readable
from backend.services.library_inventory_access import require_library_staff
from backend.services.library_lending_journal import response_value

MAX_TIME_MS = 10000
SUBJECT_LIMIT = 20
POPULAR_LIMIT = 10
TREND_LIMIT = 90
UNAVAILABLE_COPY = ['LOST', 'DAMAGED', 'WITHDRAWN', 'UNVERIFIED', 'RESERVED']
ACTIVITY_FIELDS = {
    'BORROW_REQUEST_CREATED': 'requested_in_range',
    'BORROW_REQUEST_APPROVED': 'approved_in_range',
    'BORROW_REQUEST_REJECTED': 'rejected_in_range',
    'RETURN_CONFIRMED': 'returns_confirmed_in_range',
    'LOAN_RENEWED': 'renewals_in_range',
    'RESERVATION_CREATED': 'created_in_range',
    'RESERVATION_FULFILLED': 'fulfilled_in_range',
    'RESERVATION_CANCELLED': 'cancelled_in_range',
    'RESERVATION_EXPIRED': 'expired_in_range',
}
TREND_EVENTS = {
    'BORROW_REQUEST_CREATED': 'borrow_requests', 'LOAN_ISSUED': 'loans_issued',
    'RETURN_CONFIRMED': 'returns_confirmed', 'LOAN_RENEWED': 'renewals',
    'RESERVATION_CREATED': 'reservations',
}


def now():
    return datetime.now(timezone.utc)


def aggregate(name, pipeline):
    target = db.events if name == 'events' else collection(name)
    return list(target.aggregate(pipeline, maxTimeMS=MAX_TIME_MS, allowDiskUse=False))


def count_when(condition):
    return {'$sum': {'$cond': [condition, 1, 0]}}


def span(key, stamp):
    if key not in ('7d', '30d', '90d', 'all'):
        raise HTTPException(422, 'Unsupported analytics range.')
    stamp = stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)
    today = stamp.replace(hour=0, minute=0, second=0, microsecond=0)
    start = None if key == 'all' else today - timedelta(days=int(key[:-1]) - 1)
    return {'key': key, 'start_at': start, 'end_at': stamp, 'timezone': 'UTC', 'bucket': 'day',
            'trend_start_at': start or today - timedelta(days=TREND_LIMIT - 1),
            'trend_window_limited': key == 'all'}


def date_query(window, field, *, trend=False):
    start = window['trend_start_at'] if trend else window['start_at']
    return {field: {'$lt': window['end_at'], **({'$gte': start} if start else {})}}


def in_range(field, window):
    conditions = [{'$ne': [field, None]}, {'$lt': [field, window['end_at']]}]
    if window['start_at']:
        conditions.append({'$gte': [field, window['start_at']]})
    return {'$and': conditions}


def lookup(library_id, name, local_field, remote_field, pipeline, alias):
    return {'$lookup': {'from': collection(name).name, 'let': {'identity': '$' + local_field},
            'pipeline': [{'$match': {'library_id': library_id,
                         '$expr': {'$eq': ['$' + remote_field, '$$identity']}}}, *pipeline], 'as': alias}}


def first(rows, defaults=None):
    return {**(defaults or {}), **({k: v for k, v in rows[0].items() if k != '_id'} if rows else {})}


def marker(library_id):
    # Constant-sized signatures, server-side aggregation; no tenant row loading.
    audit = aggregate('audit', [{'$match': {'library_id': library_id}}, {'$group': {'_id': None,
        'count': {'$sum': 1}, 'latest': {'$max': '$created_at'}, 'identity': {'$max': '$event_id'}}}])
    events = aggregate('events', [{'$match': {'library_id': library_id, 'scope': 'LIBRARY'}},
        {'$group': {'_id': None, 'count': {'$sum': 1}, 'revision': {'$sum': '$revision'},
                    'latest': {'$max': '$updated_at'}}}])
    return audit, events


def configs(library_id):
    fields = {'_id': 0, 'state': 1, 'updated_at': 1}
    return tuple(collection(name).find_one({'library_id': library_id}, fields) or {'state': 'LEGACY'}
                 for name in ('lending_config', 'v2c_config'))


def collection_metrics(library_id, window, canonical, *, reservations_enabled=True):
    pipeline = [{'$match': {'library_id': library_id, 'status': 'ACTIVE'}},
        lookup(library_id, 'holdings', 'library_book_id', 'library_book_id', [{'$project': {'_id': 0}}], 'holding'),
        {'$unwind': {'path': '$holding', 'preserveNullAndEmptyArrays': True}},
        {'$set': {'holding.circulation_status': {'$ifNull': ['$holding.circulation_status', 'CIRCULATING']}}}]
    if canonical:
        # Intentional nonphysical creation is provenance, not lost stock. Never
        # exempt a broken physical holding merely because an asset exists.
        from backend.services.library_book_formats import unstocked_origin_pipeline
        has_unstocked_origin = collection('lending_operations').find_one({'library_id': library_id,
            'operation_type': 'LIBRARY_BOOK_CREATED', 'state': 'COMMITTED', 'result.has_physical': False}, {'_id': 1}) or collection('audit').find_one({
            'library_id': library_id, 'event': 'LIBRARY_BOOK_CREATED', 'metadata.holding_id': {'$exists': False}}, {'_id': 1})
        pipeline.extend(unstocked_origin_pipeline(library_id) if has_unstocked_origin else [{'$set': {'_unstocked_origin': False}}])
        for name, query, alias in [
            ('lending_requests', {'request_type': 'BORROW', 'status': 'PENDING'}, 'pending'),
            ('loans', {'status': 'ACTIVE'}, 'active'),
            ('reservations', {'status': 'WAITING'}, 'waiting'),
        ]:
            # An indexed existence probe avoids thousands of empty correlated
            # lookups in newly populated or historically idle collections.
            # Audit/gate checks still reject a concurrent allocation change.
            if (name != 'reservations' or reservations_enabled) and collection(name).find_one(
                    {'library_id': library_id, **query}, {'_id': 1}):
                pipeline.append(lookup(library_id, name, 'library_book_id', 'library_book_id',
                                       [{'$match': query}, {'$count': 'count'}], alias))
            else:
                pipeline.append({'$set': {alias: []}})
        if collection('copies').find_one({'library_id': library_id}, {'_id': 1}):
            pipeline.append(lookup(library_id, 'copies', 'library_book_id', 'library_book_id',
                [{'$group': {'_id': None, 'known': {'$sum': 1},
                            'conditions': count_when({'$in': ['$status', UNAVAILABLE_COPY]}),
                            'available': count_when({'$eq': ['$status', 'AVAILABLE']})}}], 'copy_counts'))
        else:
            pipeline.append({'$set': {'copy_counts': []}})
        pipeline.append({'$set': {name: {'$ifNull': [{'$arrayElemAt': ['$' + name + '.count', 0]}, 0]}
                                     for name in ('pending', 'active', 'waiting')}})
        pipeline.append({'$set': {'physical_units': {'$subtract': [
            {'$ifNull': ['$holding.total_copies', 0]}, {'$add': ['$pending', '$active',
                {'$ifNull': ['$holding.unavailable_stock', 0]},
                {'$ifNull': [{'$arrayElemAt': ['$copy_counts.conditions', 0]}, 0]}]}]}}})
        pipeline.append({'$set': {'requestable': {'$cond': [{'$and': [
            {'$ne': [{'$ifNull': ['$holding.holding_id', None]}, None]},
            {'$eq': ['$holding.circulation_status', 'CIRCULATING']}, {'$eq': ['$waiting', 0]}]}, '$physical_units', 0]},
            'invalid': {'$or': [{'$lt': ['$physical_units', 0]},
                {'$and': [{'$eq': [{'$ifNull': ['$holding.holding_id', None]}, None]},
                    {'$or': [{'$ne': ['$_unstocked_origin', True]}, {'$gt': ['$pending', 0]}, {'$gt': ['$active', 0]},
                        {'$gt': ['$waiting', 0]}, {'$gt': [{'$ifNull': [{'$arrayElemAt': ['$copy_counts.known', 0]}, 0]}, 0]}]}]},
                {'$and': [{'$eq': ['$holding.allocation_mode', 'COPY']}, {'$or': [
                    {'$ne': [{'$ifNull': [{'$arrayElemAt': ['$copy_counts.known', 0]}, 0]}, '$holding.total_copies']},
                    {'$ne': [{'$ifNull': [{'$arrayElemAt': ['$copy_counts.available', 0]}, 0]}, '$physical_units']}]}]}]}}})
    summary = {'_id': None, 'active_books': {'$sum': 1},
        'total_holding_quantity': {'$sum': '$holding.total_copies'},
        'local_only_books': count_when({'$eq': [{'$ifNull': ['$global_work_id', None]}, None]}),
        'globally_linked_books': count_when({'$ne': [{'$ifNull': ['$global_work_id', None]}, None]}),
        **{status: count_when({'$and': [{'$ne': [{'$ifNull': ['$holding.holding_id', None]}, None]}, {'$eq': ['$holding.circulation_status', status]}]})
           for status in ('CIRCULATING', 'REFERENCE_ONLY', 'TEMPORARILY_UNAVAILABLE')},
        **({'requestable_units': {'$sum': '$requestable'}, 'invalid': count_when('$invalid')} if canonical else {})}
    pipeline.append({'$facet': {'summary': [{'$group': summary}],
        'subjects': [{'$project': {'subjects': {'$setUnion': [{'$ifNull': ['$subjects', []]}, []]}}},
            {'$unwind': '$subjects'}, {'$match': {'subjects': {'$type': 'string', '$regex': r'\S'}}},
            {'$group': {'_id': '$subjects', 'count': {'$sum': 1}}}, {'$sort': {'count': -1, '_id': 1}},
            {'$limit': SUBJECT_LIMIT}]}})
    payload = aggregate('library_books', pipeline)[0]
    values = first(payload['summary'], {key: 0 for key in summary if key != '_id'})
    if values.pop('invalid', 0):
        raise HTTPException(503, 'Canonical collection allocation requires reconciliation.')
    # Retained withdrawals do not erase actual acquisition history. Current
    # collection snapshots/subjects remain ACTIVE-only; creation activity counts
    # accepted ACTIVE and WITHDRAWN records, excluding incomplete PROVISIONING.
    history = aggregate('library_books', [{'$match': {'library_id': library_id,
        'status': {'$in': ['ACTIVE', 'WITHDRAWN']}, **date_query(window, 'created_at')}},
        {'$facet': {'totals': [{'$count': 'count'}],
            'trends': [{'$match': date_query(window, 'created_at', trend=True)},
                {'$group': {'_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$created_at', 'timezone': 'UTC'}},
                            'acquisitions': {'$sum': 1}}}, {'$sort': {'_id': 1}}, {'$limit': TREND_LIMIT}]}}])[0]
    values['recent_acquisitions'] = history['totals'][0]['count'] if history['totals'] else 0
    statuses = {key: values.pop(key) for key in ('CIRCULATING', 'REFERENCE_ONLY', 'TEMPORARILY_UNAVAILABLE')}
    return {'available': True, **values, 'requestable_units': values.get('requestable_units') if canonical else None,
            'circulation_status': statuses,
            'subjects': [{'subject': row['_id'], 'count': row['count']} for row in payload['subjects']]}, history['trends']


def committed_activity(library_id, window):
    known = list(set(ACTIVITY_FIELDS) | set(TREND_EVENTS))
    pipeline = [{'$match': {'library_id': library_id, 'event': {'$in': known},
                           'metadata.operation_id': {'$type': 'string'}, **date_query(window, 'created_at')}},
        lookup(library_id, 'lending_operations', 'metadata.operation_id', 'operation_id',
               [{'$match': {'state': 'COMMITTED'}}, {'$project': {'_id': 1}}], 'committed'),
        {'$match': {'committed.0': {'$exists': True}}},
        {'$facet': {'totals': [{'$group': {'_id': '$event', 'count': {'$sum': 1}}}],
            'trends': [{'$match': date_query(window, 'created_at', trend=True)},
                {'$group': {'_id': {'date': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$created_at', 'timezone': 'UTC'}},
                                   'event': '$event'}, 'count': {'$sum': 1}}},
                {'$sort': {'_id.date': 1, '_id.event': 1}}]}}]
    payload = aggregate('audit', pipeline)[0]
    return {row['_id']: row['count'] for row in payload['totals']}, payload['trends']


def circulation_metrics(library_id, activity, canonical):
    fields = ('pending_borrow_requests', 'pending_return_requests', 'active_loans', 'requested_in_range',
              'approved_in_range', 'rejected_in_range', 'returns_confirmed_in_range', 'renewals_in_range')
    if not canonical:
        return {'available': False, 'unavailable_reason': 'Canonical circulation cutover is not complete.',
                **{key: None for key in fields}}
    requests = first(aggregate('lending_requests', [{'$match': {'library_id': library_id, 'status': 'PENDING'}},
        {'$group': {'_id': None, 'pending_borrow_requests': count_when({'$eq': ['$request_type', 'BORROW']}),
                    'pending_return_requests': count_when({'$eq': ['$request_type', 'RETURN']})}}]),
                    {'pending_borrow_requests': 0, 'pending_return_requests': 0})
    loans = first(aggregate('loans', [{'$match': {'library_id': library_id, 'status': 'ACTIVE'}},
                                   {'$count': 'active_loans'}]), {'active_loans': 0})
    return {'available': True, 'unavailable_reason': None, **requests, **loans,
            **{field: activity.get(event, 0) for event, field in ACTIVITY_FIELDS.items()
               if not event.startswith('RESERVATION_')}}


def reservation_metrics(library_id, activity, enabled):
    fields = ('active', 'waiting', 'ready', 'fulfilled_in_range', 'cancelled_in_range', 'expired_in_range', 'created_in_range')
    if not enabled:
        return {'available': False, 'unavailable_reason': 'Canonical reservations cutover is not complete.',
                **{key: None for key in fields}, 'average_queue_depth': None}
    rows = aggregate('reservations', [{'$match': {'library_id': library_id, 'status': {'$in': ['WAITING', 'CONVERTED']}}},
        {'$facet': {'totals': [{'$group': {'_id': None, 'active': {'$sum': 1},
             'waiting': count_when({'$eq': ['$status', 'WAITING']}), 'ready': count_when({'$eq': ['$status', 'CONVERTED']})}}],
            'depth': [{'$match': {'status': 'WAITING'}}, {'$group': {'_id': '$library_book_id', 'count': {'$sum': 1}}},
                      {'$group': {'_id': None, 'average': {'$avg': '$count'}}}]}}])[0]
    return {'available': True, 'unavailable_reason': None, **first(rows['totals'], {'active': 0, 'waiting': 0, 'ready': 0}),
            **{field: activity.get(event, 0) for event, field in ACTIVITY_FIELDS.items() if event.startswith('RESERVATION_')},
            'average_queue_depth': rows['depth'][0]['average'] if rows['depth'] else None}


def fee_metrics(library_id, window, enabled, admin):
    keys = ('currency', 'minor_units_per_major', 'open_count', 'open_balance_minor', 'assessed_in_range',
            'assessed_minor', 'payments_minor', 'waived_minor', 'settled_minor')
    if not enabled:
        return {'available': False, 'unavailable_reason': 'Canonical fees cutover is not complete.',
                **{key: None for key in keys}}, []
    policy = collection('fee_policies').find_one({'library_id': library_id}, {'currency': 1, 'minor_units_per_major': 1},
                                                 sort=[('version', -1)])
    if not policy or policy.get('currency') != 'INR' or policy.get('minor_units_per_major') != 100:
        raise HTTPException(503, 'Canonical fee currency policy requires review.')
    # Verify append-only ledger against aggregate balance without returning fee or member rows.
    fees = aggregate('fees', [{'$match': {'library_id': library_id}},
        lookup(library_id, 'fee_ledger', 'fee_id', 'fee_id', [{'$group': {'_id': None,
            'charge': {'$sum': {'$switch': {'branches': [
                {'case': {'$eq': ['$entry_type', 'CHARGE']}, 'then': '$amount_minor'},
                {'case': {'$in': ['$entry_type', ['CREDIT', 'WAIVER']]}, 'then': {'$multiply': [-1, '$amount_minor']}}], 'default': 0}}},
            'paid': {'$sum': {'$cond': [{'$eq': ['$entry_type', 'PAYMENT_RECORD']}, '$amount_minor', 0]}}}}], 'ledger'),
        {'$set': {'ledger_charge': {'$ifNull': [{'$arrayElemAt': ['$ledger.charge', 0]}, 0]},
                   'ledger_paid': {'$ifNull': [{'$arrayElemAt': ['$ledger.paid', 0]}, 0]}}},
        {'$group': {'_id': None,
            'invalid': count_when({'$or': [{'$ne': ['$currency', policy['currency']]},
                {'$ne': ['$ledger_charge', '$current_amount_minor']}, {'$ne': ['$ledger_paid', '$paid_amount_minor']},
                {'$ne': [{'$subtract': ['$ledger_charge', '$ledger_paid']}, '$balance_minor']}, {'$lt': ['$balance_minor', 0]}]}),
            'open_count': count_when({'$gt': ['$balance_minor', 0]}),
            'open_balance_minor': {'$sum': '$balance_minor'},
            'assessed_in_range': count_when(in_range('$created_at', window)),
            'assessed_minor': {'$sum': {'$cond': [in_range('$created_at', window), '$original_amount_minor', 0]}}}}])
    totals = first(fees, {'invalid': 0, 'open_count': 0, 'open_balance_minor': 0, 'assessed_in_range': 0, 'assessed_minor': 0})
    if totals.pop('invalid'):
        raise HTTPException(503, 'Canonical fee ledger requires reconciliation.')
    ledger = aggregate('fee_ledger', [{'$match': {'library_id': library_id, **date_query(window, 'created_at')}},
        {'$facet': {'totals': [{'$group': {'_id': None,
            'payments_minor': {'$sum': {'$cond': [{'$eq': ['$entry_type', 'PAYMENT_RECORD']}, '$amount_minor', 0]}},
            'waived_minor': {'$sum': {'$cond': [{'$eq': ['$entry_type', 'WAIVER']}, '$amount_minor', 0]}}}}],
            'trends': [{'$match': date_query(window, 'created_at', trend=True)},
                {'$group': {'_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$created_at', 'timezone': 'UTC'}},
                    'payments_minor': {'$sum': {'$cond': [{'$eq': ['$entry_type', 'PAYMENT_RECORD']}, '$amount_minor', 0]}}}},
                {'$sort': {'_id': 1}}, {'$limit': TREND_LIMIT}]}}])[0]
    charges = aggregate('fees', [{'$match': {'library_id': library_id, **date_query(window, 'created_at', trend=True)}},
        {'$group': {'_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$created_at', 'timezone': 'UTC'}},
                    'fees_assessed_minor': {'$sum': '$original_amount_minor'}}}, {'$sort': {'_id': 1}}, {'$limit': TREND_LIMIT}])
    values = first(ledger['totals'], {'payments_minor': 0, 'waived_minor': 0})
    settled = 0
    if admin:
        # A partially paid fee is not settled. The canonical FEE_PAID audit
        # records the full paid amount at the actual settlement transition.
        rows = aggregate('audit', [{'$match': {'library_id': library_id, 'event': 'FEE_PAID',
            'metadata.operation_id': {'$type': 'string'}, 'metadata.currency': policy['currency'],
            **date_query(window, 'created_at')}},
            lookup(library_id, 'lending_operations', 'metadata.operation_id', 'operation_id',
                [{'$match': {'state': 'COMMITTED'}}, {'$project': {'_id': 1}}], 'committed'),
            {'$match': {'committed.0': {'$exists': True}}},
            {'$group': {'_id': None, 'amount': {'$sum': '$metadata.amount_minor'}}}])
        settled = rows[0]['amount'] if rows else 0
    # BSON sums promote an overflowing int64 to double. Never serialize that
    # approximation as exact money, or accept malformed fractional minor units.
    amounts = [totals['open_balance_minor'], totals['assessed_minor'], values['payments_minor'],
               values['waived_minor'], settled]
    # PyMongo decodes BSON int64 as Int64 (an int subclass). It is exact;
    # doubles and booleans are not accepted minor-unit amounts.
    if any(not isinstance(amount, int) or isinstance(amount, bool) or amount < 0 for amount in amounts):
        raise HTTPException(503, 'Exact minor-unit fee totals require reconciliation.')
    if any(not isinstance(row[key], int) or isinstance(row[key], bool) or row[key] < 0 for row in [*ledger['trends'], *charges]
           for key in ('payments_minor', 'fees_assessed_minor') if key in row):
        raise HTTPException(503, 'Exact minor-unit fee history requires reconciliation.')
    return {'available': True, 'unavailable_reason': None, 'currency': policy['currency'],
        'minor_units_per_major': policy['minor_units_per_major'], **totals, **values,
        'open_balance_minor': str(totals['open_balance_minor']), 'assessed_minor': str(totals['assessed_minor']),
        'payments_minor': str(values['payments_minor']), 'waived_minor': str(values['waived_minor']) if admin else None,
        'settled_minor': str(settled) if admin else None}, [*ledger['trends'], *charges]


def event_metrics(library_id, window):
    effective_end = {'$ifNull': ['$end_at', '$start_at']}
    rows = aggregate('events', [{'$match': {'library_id': library_id, 'scope': 'LIBRARY'}},
        {'$facet': {'totals': [{'$group': {'_id': None,
            'upcoming': count_when({'$and': [{'$eq': ['$status', 'PUBLISHED']}, {'$gte': [effective_end, window['end_at']]}]}),
            'completed': count_when({'$and': [{'$eq': ['$status', 'PUBLISHED']}, {'$lt': [effective_end, window['end_at']]}]}),
            'published_in_range': count_when(in_range('$published_at', window)),
            'cancelled_in_range': count_when(in_range('$cancelled_at', window)),
            'drafts': count_when({'$eq': ['$status', 'DRAFT']})}}],
            'trends': [{'$match': date_query(window, 'published_at', trend=True)},
                {'$group': {'_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$published_at', 'timezone': 'UTC'}},
                            'events_published': {'$sum': 1}}}, {'$sort': {'_id': 1}}, {'$limit': TREND_LIMIT}]}}])[0]
    return {'available': True, **first(rows['totals'], {key: 0 for key in
             ('upcoming', 'completed', 'published_in_range', 'cancelled_in_range', 'drafts')})}, rows['trends']


def membership_metrics(library_id, admin):
    rows = aggregate('memberships', [{'$match': {'library_id': library_id, 'status': 'ACTIVE'}},
                                   {'$group': {'_id': '$role', 'count': {'$sum': 1}}}])
    totals = {row['_id']: row['count'] for row in rows}
    return {'active_total': sum(totals.values()), 'role_counts': {role: totals.get(role, 0)
            for role in ('ADMIN', 'LIBRARIAN', 'GENERAL_USER')} if admin else None}


def popular_books(library_id, window, canonical, reservations):
    if not canonical:
        return []
    # The established Home signals/weights/statuses, applied to the selected UTC
    # window. Home's existing 90-day ranking remains untouched.
    def signal(name, date, statuses, weight):
        query = {'library_id': library_id, 'status': {'$in': statuses}, **date_query(window, date)}
        if name == 'lending_requests':
            query['request_type'] = 'BORROW'
        return [{'$match': query}, {'$project': {'library_book_id': 1, 'weight': {'$literal': weight},
                                                'signal': {'$literal': name}}}]
    pipeline = signal('loans', 'borrowed_at', ['ACTIVE', 'RETURNED'], 8)
    pipeline.append({'$unionWith': {'coll': collection('lending_requests').name,
                    'pipeline': signal('lending_requests', 'reviewed_at', ['APPROVED', 'COMPLETED'], 2)}})
    if reservations:
        pipeline.append({'$unionWith': {'coll': collection('reservations').name,
                        'pipeline': signal('reservations', 'requested_at', ['WAITING', 'CONVERTED', 'FULFILLED'], 1)}})
    pipeline.extend([{'$group': {'_id': '$library_book_id', 'score': {'$sum': '$weight'},
        **{key: count_when({'$eq': ['$signal', name]}) for key, name in
           [('loans', 'loans'), ('approved_requests', 'lending_requests'), ('reservations', 'reservations')]}}},
        lookup(library_id, 'library_books', '_id', 'library_book_id',
            [{'$match': {'status': 'ACTIVE', 'title': {'$type': 'string', '$regex': r'\S'}}},
             {'$project': {'_id': 0, 'library_book_id': 1, 'title': 1, 'authors': 1, 'global_work_id': 1}}], 'book'),
        {'$unwind': '$book'},
        lookup(library_id, 'holdings', '_id', 'library_book_id', [{'$project': {'_id': 1}}], 'held'),
        {'$match': {'held.0': {'$exists': True}}}, {'$sort': {'score': -1, 'loans': -1, '_id': 1}},
        {'$limit': POPULAR_LIMIT}, {'$project': {'_id': 0, 'library_book_id': '$book.library_book_id',
            'title': '$book.title', 'authors': {'$ifNull': ['$book.authors', []]},
            'global_work_id': {'$ifNull': ['$book.global_work_id', None]}, 'score': 1,
            'loans': 1, 'approved_requests': 1, 'reservations': 1}}])
    return aggregate('loans', pipeline)


def outbox_metrics(library_id):
    rows = aggregate('notification_outbox', [{'$match': {'library_id': library_id}},
        {'$group': {'_id': None, 'pending': count_when({'$eq': ['$state', 'PENDING']}),
            'retry_required': count_when({'$and': [{'$eq': ['$state', 'PENDING']}, {'$gt': ['$attempts', 0]}]}),
            'delivered': count_when({'$eq': ['$state', 'DELIVERED']}),
            'suppressed': count_when({'$eq': ['$state', 'SUPPRESSED']})}}])
    return first(rows, {key: 0 for key in ('pending', 'retry_required', 'delivered', 'suppressed')})


def trends(collection_rows, audit_rows, fee_rows, event_rows, canonical, enabled):
    result = {}
    def row(date):
        if date not in result:
            result[date] = {'date': date, 'acquisitions': 0, 'events_published': 0,
                **{key: 0 if canonical and (enabled or key != 'reservations') else None for key in TREND_EVENTS.values()},
                'fees_assessed_minor': 0 if enabled else None, 'payments_minor': 0 if enabled else None}
        return result[date]
    for source in (collection_rows, fee_rows, event_rows):
        for value in source:
            target = row(value['_id'])
            for key, amount in value.items():
                if key != '_id':
                    target[key] = amount
    for value in audit_rows:
        key = TREND_EVENTS.get(value['_id']['event'])
        if key and canonical and (enabled or key != 'reservations'):
            row(value['_id']['date'])[key] = value['count']
    for value in result.values():
        for key in ('fees_assessed_minor', 'payments_minor'):
            value[key] = str(value[key]) if value[key] is not None else None
    return [result[date] for date in sorted(result)][-TREND_LIMIT:]


def dashboard(library_id, actor, range_key='30d', *, stamp=None):
    try:
        library_id = str(UUID(str(library_id)))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, 'A canonical library UUID is required.')
    library, member = require_library_staff(library_id, actor)
    config_before = configs(library_id)
    version_before = marker(library_id)
    require_readable(library_id)
    window = span(range_key, stamp or now())
    canonical = config_before[0]['state'] == 'CANONICAL'
    enabled = canonical and config_before[1]['state'] == 'CANONICAL'
    if config_before[1]['state'] in ('PREPARING', 'RECOVERY_REQUIRED'):
        raise HTTPException(503, 'RECOVERY_REQUIRED: reservation and fee cutover must complete.')
    admin = member['role'] == 'ADMIN'
    books, collection_trends = collection_metrics(library_id, window, canonical, reservations_enabled=enabled)
    activity, audit_trends = committed_activity(library_id, window) if canonical else ({}, [])
    circulation = circulation_metrics(library_id, activity, canonical)
    reservations = reservation_metrics(library_id, activity, enabled)
    fees, fee_trends = fee_metrics(library_id, window, enabled, admin)
    events, event_trends = event_metrics(library_id, window)
    members = membership_metrics(library_id, admin)
    popular = popular_books(library_id, window, canonical, enabled)
    outbox = outbox_metrics(library_id) if admin else None
    require_readable(library_id)
    # Revalidate *current* identity/membership/lifecycle before returning private
    # aggregates; even a valid old JWT cannot retain revoked tenant authority.
    current_library, current_member = require_library_staff(library_id, actor)
    if (current_member['membership_id'], current_member['role']) != (member['membership_id'], member['role']):
        raise HTTPException(503, 'Library authority changed. Refresh analytics.')
    if version_before != marker(library_id) or config_before != configs(library_id):
        raise HTTPException(503, 'Library activity changed during analytics. Please retry.', headers={'Retry-After': '1'})
    require_readable(library_id)
    return response_value({'library_id': library_id, 'library_name': current_library['name'],
        'membership_role': current_member['role'], 'generated_at': window['end_at'], 'range': window,
        'capabilities': {'membership_breakdown': admin, 'financial_detail': admin, 'outbox_health': admin},
        'overview': {'active_books': books['active_books'], 'total_holding_quantity': books['total_holding_quantity'],
            'requestable_units': books['requestable_units'], 'active_loans': circulation['active_loans'],
            'pending_borrow_requests': circulation['pending_borrow_requests'], 'pending_return_requests': circulation['pending_return_requests'],
            'active_reservations': reservations['active'], 'open_fee_balance_minor': fees['open_balance_minor'],
            'currency': fees['currency'], 'upcoming_events': events['upcoming'], 'active_members': members['active_total']},
        'collection': books, 'circulation': circulation, 'reservations': reservations, 'fees': fees,
        'events': events, 'membership': members, 'popular_books': popular,
        'trends': trends(collection_trends, audit_trends, fee_trends, event_trends, canonical, enabled), 'outbox': outbox})
