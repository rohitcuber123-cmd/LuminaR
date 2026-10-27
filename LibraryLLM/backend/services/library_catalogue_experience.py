"""Membership-scoped catalogue discovery. All circulation commands stay in Part 2B/C."""
from contextlib import contextmanager
from datetime import timedelta
import re
from fastapi import HTTPException
from backend.institution_dependencies import actor_id
from backend.services.institution_repository import collection, library_mutation, require_readable
from backend.services.library_inventory_access import require_library_membership, require_library_patron, require_library_staff
from backend.services import library_lending_service as lending
from backend.services.library_v2c_plan import enabled
from backend.services.library_catalogue_availability import project
from backend.database.mongodb import books_collection
from rag.book_assets import capabilities as book_capabilities

WINDOW_DAYS = 90
RAIL_LIMIT = 12
UNAVAILABLE = ['LOST', 'DAMAGED', 'WITHDRAWN', 'UNVERIFIED', 'RESERVED']


def ensure_indexes():
    # Catalogue read indexes only; no global dataset/index/build operation.
    collection('library_books').create_index([('library_id', 1), ('status', 1), ('created_at', -1)])
    collection('library_books').create_index([('library_id', 1), ('status', 1), ('subjects', 1)])
    collection('loans').create_index([('library_id', 1), ('borrowed_at', -1), ('library_book_id', 1)])
    collection('lending_requests').create_index([('library_id', 1), ('reviewed_at', -1), ('library_book_id', 1)])
    collection('reservations').create_index([('library_id', 1), ('requested_at', -1), ('library_book_id', 1)])


@contextmanager
def read_context(library_id, actor, *, patron=True, staff=False):
    guard = require_library_staff if staff else require_library_patron if patron else require_library_membership
    # Verify eligibility/scope before locking or running canonical maintenance.
    library, membership = guard(library_id, actor)
    canonical = lending.journal.state(library_id) == 'CANONICAL'
    if canonical:
        with library_mutation(library_id, wait_seconds=30, durable=True):
            lending.access_locked(library_id, actor, patron=patron and not staff, staff=staff)
            library, membership = guard(library_id, actor, locked=True)
            yield library, membership, canonical
    else:
        yield library, membership, canonical
        require_readable(library_id)


def usable(library_id, *, search='', subject='', author='', circulation_status='', staff=False):
    query = {'library_id': library_id, 'status': 'ACTIVE', 'title': {'$type': 'string', '$regex': r'\S'}}
    if search.strip():
        # Exactly the existing tenant inventory search_text semantics; no global index routing.
        query['search_text'] = {'$regex': re.escape(search.strip().casefold())}
    if subject: query['subjects'] = subject
    if author: query['authors'] = {'$regex': re.escape(author.strip()), '$options': 'i'}
    from backend.services.library_book_formats import format_pipeline
    pipeline = [{'$match': query}, *format_pipeline(library_id, staff=staff)]
    if not staff: pipeline.append({'$match': {'$or': [{'has_physical':True},{'has_online':True}]}})
    if circulation_status: pipeline.append({'$match': {'holding.circulation_status': circulation_status}})
    return pipeline


def source_locked(library_id, library, membership, canonical, *, staff=False):
    count = list(collection('library_books').aggregate([*usable(library_id, staff=staff), {'$count': 'count'}]))
    total = count[0]['count'] if count else 0
    local = staff or total > 0
    return {'library_id': library_id, 'library_name': library['name'],
        'catalogue_source': 'LIBRARY_LOCAL' if local else 'GLOBAL_FALLBACK', 'local_book_count': total,
        'capabilities': {'physical_actions': bool(local and canonical and membership['role'] == 'GENERAL_USER'),
            'reservations': bool(local and canonical and enabled(library_id) and membership['role'] == 'GENERAL_USER'),
            'local_search': local, 'global_discovery': not local},
        'circulation_state': 'CANONICAL' if canonical else lending.journal.state(library_id),
        'discovery_notice': None if local else 'Global Catalogue · Not currently held by this library.'}


def source(library_id, actor, *, staff=False):
    with read_context(library_id, actor, patron=False, staff=staff) as (library, membership, canonical):
        return source_locked(library_id, library, membership, canonical, staff=staff)


def grouped(name, query, fields=None):
    fields = fields or {'count': {'$sum': 1}}
    return {r['_id']: r for r in collection(name).aggregate([{'$match': query}, {'$group': {'_id': '$library_book_id', **fields}}])}


def hydrate(library_id, actor, rows, canonical, *, staff=False):
    """Constant database round trips per bounded batch; no per-card HTTP or Mongo calls."""
    if not rows: return []
    ids = [r['library_book_id'] for r in rows]
    scope = {'library_id': library_id, 'library_book_id': {'$in': ids}}
    user = actor_id(actor)
    requests = list(collection('lending_requests').find({**scope, 'user_id': user, 'request_type': 'BORROW', 'status': 'PENDING'}, {'_id': 0}).sort('requested_at', -1)) if canonical else []
    # Aggregate counts, not unbounded rows, for all member allocations.
    pending = grouped('lending_requests', {**scope, 'request_type': 'BORROW', 'status': 'PENDING'}) if canonical else {}
    active = grouped('loans', {**scope, 'status': 'ACTIVE'}) if canonical else {}
    copies = grouped('copies', scope, {'known': {'$sum': 1},
        'conditions': {'$sum': {'$cond': [{'$in': ['$status', UNAVAILABLE]}, 1, 0]}},
        'available': {'$sum': {'$cond': [{'$eq': ['$status', 'AVAILABLE']}, 1, 0]}}}) if canonical else {}
    own_requests = {r['library_book_id']: r for r in reversed(requests) if r['user_id'] == user}
    global_ids = list({r['global_work_id'] for r in rows if r.get('global_work_id')})
    global_metadata = {b['work_id']: b for b in books_collection.find({'work_id': {'$in': global_ids}},
        {'_id': 0, 'work_id': 1, 'book_id': 1, 'description': 1, 'average_rating': 1, 'rating_count': 1, 'reading_log_count': 1})} if global_ids else {}
    digital_flags = book_capabilities(global_ids) if global_ids else {}
    own_loans = {r['library_book_id']: r for r in collection('loans').find({**scope, 'user_id': user, 'status': 'ACTIVE'}, {'_id': 0})} if canonical else {}
    reservations_enabled = bool(canonical and enabled(library_id))
    own_reservations = {r['library_book_id']: r for r in collection('reservations').find({**scope, 'user_id': user,
        'status': {'$in': ['WAITING', 'CONVERTED']}}, {'_id': 0}).sort('requested_at', 1)} if reservations_enabled else {}
    branches = [{'case': {'$eq': ['$library_book_id', bid]}, 'then': r['queue_sequence']}
                for bid, r in own_reservations.items() if r['status'] == 'WAITING']
    threshold = {'$switch': {'branches': branches, 'default': -1}} if branches else -1
    waiting = grouped('reservations', {**scope, 'status': 'WAITING'}, {'count': {'$sum': 1},
        'position': {'$sum': {'$cond': [{'$lte': ['$queue_sequence', threshold]}, 1, 0]}}}) if reservations_enabled else {}
    result = []
    for row in rows:
        bid, holding = row['library_book_id'], row.get('holding') or {}
        metadata = global_metadata.get(row.get('global_work_id'), {})
        counts = copies.get(bid, {})
        availability = project(library_id, row, holding, pending=pending.get(bid, {}).get('count', 0),
            active=active.get(bid, {}).get('count', 0), known=counts.get('known', 0), conditions=counts.get('conditions', 0),
            available=counts.get('available', 0), waiting=bool(waiting.get(bid))) if canonical and holding else None
        request, reservation, loan = own_requests.get(bid), own_reservations.get(bid), own_loans.get(bid)
        if staff: request = reservation = loan = None
        result.append({'display_id': bid, 'library_id': library_id, 'library_book_id': bid,
            **{k: row.get(k) for k in ('book_format','has_physical','has_online','online_asset_id')},
            'global_work_id': row.get('global_work_id'), 'title': row['title'], 'authors': row.get('authors') or [],
            'subjects': row.get('subjects') or [], 'description': row.get('description') or metadata.get('description'),
            'publication_year': row.get('publication_year'), 'language': row.get('language'),
            'isbn_10': row.get('isbn_10'), 'isbn_13': row.get('isbn_13'), 'local_call_number': row.get('local_call_number'),
            'cover_seed': metadata.get('book_id'), 'average_rating': metadata.get('average_rating'),
            'rating_count': metadata.get('rating_count'), 'reading_log_count': metadata.get('reading_log_count'),
            **digital_flags.get(row.get('global_work_id'), {}),
            'cover_url': row.get('cover_url'), 'source': 'LIBRARY', 'owned_by_current_library': True,
            'accession_number': row.get('accession_number'), 'shelf_location': holding.get('shelf_location'),
            **{k:row.get(k) for k in ('isbn_10','isbn_13','status')},
            'local_call_number': holding.get('call_number') or row.get('local_call_number'),
            'circulation_status': availability['circulation_status'] if availability else holding.get('circulation_status'),
            'requestable_count': availability['requestable'] if availability else None, 'availability': availability,
            'added_at': row.get('added_at') or row.get('created_at'),
            'user_request_state': {'id': request['lending_request_id'], 'status': request['status']} if request else None,
            'user_reservation_state': {'id': reservation['reservation_id'], 'status': reservation['status'],
                'queue_position': waiting.get(bid, {}).get('position') if reservation['status'] == 'WAITING' else None,
                'queue_length': waiting.get(bid, {}).get('count', 0)} if reservation else None,
            'user_loan_state': {'id': loan['loan_id'], 'status': loan['status'], 'due_at': loan.get('due_at'),
                'return_requested': bool(loan.get('pending_return_request_id'))} if loan else None,
            'actions': {'request': bool(not staff and canonical and availability and availability['circulation_status'] == 'CIRCULATING' and availability['requestable'] > 0 and not (request or loan or reservation)),
                'reserve': bool(not staff and reservations_enabled and availability and availability['circulation_status'] == 'CIRCULATING' and availability['requestable'] == 0 and not (request or loan or reservation)),
                'cancel_request': bool(request), 'cancel_reservation': bool(reservation and reservation['status'] == 'WAITING')},
            **({'popularity': row['popularity']} if 'popularity' in row else {})})
    return result


def arrival_sort():
    return [{'$set': {'added_at': {'$ifNull': [{'$convert': {'input': '$acquisition_date', 'to': 'date', 'onError': None, 'onNull': None}}, '$created_at']}}},
            {'$sort': {'added_at': -1, 'library_book_id': 1}}]


def subject_rows(library_id, offset=0, limit=24, *, staff=False):
    rows = list(collection('library_books').aggregate([*usable(library_id, staff=staff), {'$project': {'subjects': {'$setUnion': [{'$ifNull': ['$subjects', []]}, []]}}},
        {'$unwind': '$subjects'}, {'$match': {'subjects': {'$type': 'string', '$regex': r'\S'}}},
        {'$group': {'_id': '$subjects', 'count': {'$sum': 1}}}, {'$sort': {'count': -1, '_id': 1}},
        {'$facet': {'results': [{'$skip': offset}, {'$limit': limit}], 'total': [{'$count': 'count'}]}}]))[0]
    total = rows['total'][0]['count'] if rows['total'] else 0
    return {'results': [{'subject': r['_id'], 'count': r['count']} for r in rows['results']], 'total': total,
            'offset': offset, 'limit': limit, 'has_more': offset + len(rows['results']) < total}


def popular_rows(library_id, limit=RAIL_LIMIT, offset=0, **filters):
    cutoff = lending.now() - timedelta(days=WINDOW_DAYS)
    def signal(name, date, statuses, weight):
        query = {'library_id': library_id, 'status': {'$in': statuses}, date: {'$gte': cutoff}}
        if name == 'lending_requests': query['request_type'] = 'BORROW'
        return [{'$match': query}, {'$project': {'library_book_id': 1, 'weight': {'$literal': weight},
            'signal': {'$literal': name}}}]
    pipeline = signal('loans', 'borrowed_at', ['ACTIVE', 'RETURNED'], 8)
    pipeline += [{'$unionWith': {'coll': collection('lending_requests').name, 'pipeline': signal('lending_requests', 'reviewed_at', ['APPROVED', 'COMPLETED'], 2)}},
        {'$unionWith': {'coll': collection('reservations').name, 'pipeline': signal('reservations', 'requested_at', ['WAITING', 'CONVERTED', 'FULFILLED'], 1)}},
        {'$group': {'_id': '$library_book_id', 'score': {'$sum': '$weight'},
            'loans': {'$sum': {'$cond': [{'$eq': ['$signal', 'loans']}, 1, 0]}},
            'approved_requests': {'$sum': {'$cond': [{'$eq': ['$signal', 'lending_requests']}, 1, 0]}},
            'reservations': {'$sum': {'$cond': [{'$eq': ['$signal', 'reservations']}, 1, 0]}}}},
        {'$lookup': {'from': collection('library_books').name, 'let': {'bid': '$_id'}, 'pipeline': [
            {'$match': {'$expr': {'$eq': ['$library_book_id', '$$bid']}}}, *usable(library_id, **filters)], 'as': 'book'}},
        {'$unwind': '$book'}, {'$sort': {'score': -1, 'loans': -1, '_id': 1}},
        {'$set': {'book.popularity': {'score': '$score', 'loans': '$loans', 'approved_requests': '$approved_requests', 'reservations': '$reservations', 'window_days': WINDOW_DAYS}}},
        {'$replaceRoot': {'newRoot': '$book'}}, {'$facet': {'results': [{'$skip': offset}, {'$limit': limit}], 'total': [{'$count': 'count'}]}}]
    payload = list(collection('loans').aggregate(pipeline))[0]
    return payload['results'], payload['total'][0]['count'] if payload['total'] else 0


def summary(library_id, actor, canonical):
    scope = {'library_id': library_id, 'user_id': actor_id(actor)}
    return {'pending_requests': collection('lending_requests').count_documents({**scope, 'request_type': 'BORROW', 'status': 'PENDING'}) if canonical else 0,
        'active_loans': collection('loans').count_documents({**scope, 'status': 'ACTIVE'}) if canonical else 0,
        'waiting_reservations': collection('reservations').count_documents({**scope, 'status': 'WAITING'}) if canonical and enabled(library_id) else 0}


def home(library_id, actor):
    with read_context(library_id, actor) as (library, membership, canonical):
        descriptor = source_locked(library_id, library, membership, canonical)
        payload = {'source': descriptor, 'featured': [], 'new_arrivals': [], 'popular': [], 'subjects': [],
            'my_library': summary(library_id, actor, canonical), 'popularity_window_days': WINDOW_DAYS}
        if descriptor['catalogue_source'] == 'GLOBAL_FALLBACK': return payload
        arrivals = list(collection('library_books').aggregate([*usable(library_id), *arrival_sort(), {'$limit': RAIL_LIMIT}]))
        featured = list(collection('library_books').aggregate([*usable(library_id), {'$sort': {'accession_sequence': 1, 'library_book_id': 1}}, {'$limit': RAIL_LIMIT}]))
        popular, _ = popular_rows(library_id)
        union = {}
        for row in [*featured, *arrivals, *popular]:
            bid = row['library_book_id']
            union[bid] = {**union.get(bid, {}), **row}
        hydrated = {r['library_book_id']: r for r in hydrate(library_id, actor, list(union.values()), canonical)}
        for key, rows in [('featured', featured), ('new_arrivals', arrivals), ('popular', popular)]:
            payload[key] = [hydrated[r['library_book_id']] for r in rows]
        payload['subjects'] = subject_rows(library_id)['results']
        # Category artwork also comes from canonical holdings, including local-only works.
        previews = list(collection('library_books').aggregate([*usable(library_id), *arrival_sort(), {'$set': {'preview': '$$ROOT'}},
            {'$unwind': '$subjects'}, {'$match': {'subjects': {'$in': [s['subject'] for s in payload['subjects']]}}},
            {'$group': {'_id': '$subjects', 'book': {'$first': '$preview'}}}]))
        preview_books = {r['library_book_id']: r for r in hydrate(library_id, actor,
            list({p['book']['library_book_id']: p['book'] for p in previews}.values()), canonical)}
        by_subject = {p['_id']: preview_books[p['book']['library_book_id']] for p in previews}
        payload['subjects'] = [{**s, 'preview_book': by_subject.get(s['subject'])} for s in payload['subjects']]
        return payload


def recommendations(library_id, actor, work_ids=(), limit=10):
    """Scope existing global candidates; fill only from usable canonical local records."""
    with read_context(library_id, actor) as (library, membership, canonical):
        descriptor = source_locked(library_id, library, membership, canonical)
        if descriptor['catalogue_source'] == 'GLOBAL_FALLBACK':
            return {'source': descriptor, 'results': [], 'ranking': 'GLOBAL_FALLBACK'}
        candidates = list(dict.fromkeys(work_ids))[:200]
        matches = list(collection('library_books').aggregate([*usable(library_id),
            {'$match': {'global_work_id': {'$in': candidates}}},
            {'$set': {'recommendation_rank': {'$indexOfArray': [candidates, '$global_work_id']}}},
            {'$sort': {'recommendation_rank': 1, 'library_book_id': 1}}, {'$limit': limit}])) if candidates else []
        # Deterministic recent-acquisition discovery, with no dependency on a global work ID.
        fallback = list(collection('library_books').aggregate([*usable(library_id),
            {'$match': {'library_book_id': {'$nin': [r['library_book_id'] for r in matches]}}},
            *arrival_sort(), {'$limit': limit - len(matches)}])) if len(matches) < limit else []
        return {'source': descriptor, 'results': hydrate(library_id, actor, [*matches, *fallback], canonical),
            'ranking': 'GLOBAL_INTERSECTION_AND_LOCAL_DISCOVERY', 'intersection_count': len(matches)}


def books(library_id, actor, *, search='', subject='', author='', circulation_status='', sort='title', offset=0, limit=20, staff=False):
    with read_context(library_id, actor, staff=staff) as (library, membership, canonical):
        descriptor = source_locked(library_id, library, membership, canonical, staff=staff)
        if descriptor['catalogue_source'] == 'GLOBAL_FALLBACK':
            return {'source': descriptor, 'results': [], 'total': 0, 'has_more': False, 'offset': offset, 'limit': limit}
        if sort == 'popular':
            rows, total = popular_rows(library_id, limit, offset, search=search, subject=subject, author=author, circulation_status=circulation_status, staff=staff)
        else:
            pipeline = [*usable(library_id, search=search, subject=subject, author=author, circulation_status=circulation_status, staff=staff),
                *(arrival_sort() if sort == 'new_arrivals' else [{'$sort': {'normalized_title': 1, 'library_book_id': 1}}]),
                {'$facet': {'results': [{'$skip': offset}, {'$limit': limit}], 'total': [{'$count': 'count'}]}}]
            payload = list(collection('library_books').aggregate(pipeline))[0]
            rows, total = payload['results'], payload['total'][0]['count'] if payload['total'] else 0
        return {'source': descriptor, 'results': hydrate(library_id, actor, rows, canonical, staff=staff), 'total': total,
            'has_more': offset + len(rows) < total, 'offset': offset, 'limit': limit}


def genres(library_id, actor, offset=0, limit=50, *, staff=False):
    with read_context(library_id, actor, staff=staff) as (library, membership, canonical):
        descriptor = source_locked(library_id, library, membership, canonical, staff=staff)
        return {'source': descriptor, **(subject_rows(library_id, offset, limit, staff=staff) if descriptor['catalogue_source'] == 'LIBRARY_LOCAL' else {'results': [], 'total': 0, 'has_more': False, 'offset': offset, 'limit': limit})}


def detail(library_id, book_id, actor, *, staff=False):
    with read_context(library_id, actor, staff=staff) as (library, membership, canonical):
        pipeline=usable(library_id,staff=staff)
        if staff:pipeline[0]['$match']['status']={'$in':['ACTIVE','WITHDRAWN']}
        rows = list(collection('library_books').aggregate([*pipeline, {'$match': {'library_book_id': book_id}}, *arrival_sort(), {'$limit': 1}]))
        if not rows: raise HTTPException(404, 'Book is not held by this library.')
        return {'source': source_locked(library_id, library, membership, canonical, staff=staff), 'book': hydrate(library_id, actor, rows, canonical, staff=staff)[0]}


def global_context(library_id, work_id, actor):
    with read_context(library_id, actor) as (library, membership, canonical):
        rows = list(collection('library_books').aggregate([*usable(library_id), {'$match': {'global_work_id': work_id}}, *arrival_sort(), {'$limit': 1}]))
        return {'source': source_locked(library_id, library, membership, canonical),
            'book': hydrate(library_id, actor, rows, canonical)[0] if rows else None}
