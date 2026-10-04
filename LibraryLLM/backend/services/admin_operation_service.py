"""Bounded audit/display hydration. Circulation collections remain authoritative."""
import re
from backend.database.mongodb import db, activity_collection, users_collection
from backend.services.notification_service import USER_FIELDS, normalize_dates

TYPES = ['BOOK_ISSUED', 'BOOK_RETURNED', 'BOOK_RENEWED', 'RESERVATION_CREATED', 'RESERVATION_CANCELLED',
         'RESERVATION_READY', 'RESERVATION_FULFILLED', 'FINE_CREATED', 'FINE_PAID']


def operations(limit=20, offset=0, user_id=None, email='', work_id='', title='', operation_type=''):
    query = {}
    if user_id is not None:
        query['user_id'] = user_id
    if email:
        ids = [u['user_id'] for u in users_collection.find(
            {'email': {'$regex': re.escape(email.strip()), '$options': 'i'}}, {'user_id': 1})]
        query['user_id'] = {'$in': [uid for uid in ids if user_id is None or uid == user_id]}
    if work_id:
        query['work_id'] = work_id
    if operation_type:
        query['activity_type'] = operation_type
    if title:
        # New events retain title; legacy titles resolve only through explicit source references.
        pattern = {'$regex': re.escape(title.strip()), '$options': 'i'}
        clauses = [{'title': pattern}]
        for collection, field in [('issues', 'issue_id'), ('reservations', 'reservation_id'), ('fines', 'fine_id')]:
            ids = [x[field] for x in db[collection].find({'title': pattern}, {field: 1})]
            if ids:
                clauses.append({field: {'$in': ids}})
        query['$or'] = clauses
    rows = list(activity_collection.find(query, {'_id': 0})
                .sort([('created_at', -1), ('activity_id', -1)]).skip(offset).limit(limit))
    sources = {}
    for collection, field in [('issues', 'issue_id'), ('reservations', 'reservation_id'), ('fines', 'fine_id')]:
        ids = {row[field] for row in rows if row.get(field) is not None}
        sources[field] = {x[field]: x for x in db[collection].find({field: {'$in': list(ids)}}, {'_id': 0})} if ids else {}
    ids = {row[k] for row in rows for k in ['user_id', 'actor_user_id'] if row.get(k) is not None}
    users = {u['user_id']: u for u in users_collection.find({'user_id': {'$in': list(ids)}}, USER_FIELDS)} if ids else {}
    works = {row['work_id'] for row in rows if row.get('work_id')}
    books = {b['work_id']: b for b in db['books'].find({'work_id': {'$in': list(works)}},
                                                    {'work_id': 1, 'title': 1})} if works else {}
    from backend.services.loan_renewal_service import with_renewal_policy
    renewal = {l['issue_id']: l for l in with_renewal_policy(list(sources['issue_id'].values()))}
    result = []
    for row in rows:
        source = next((sources[field][row[field]] for field in ['issue_id', 'reservation_id', 'fine_id']
                       if row.get(field) in sources[field]), {})
        target, actor = row.get('user_id'), row.get('actor_user_id')
        # Presentation fallback is explicit: never invent or backfill a legacy actor.
        if actor is not None:
            performed_by = {'kind': 'ACCOUNT', 'account': users.get(actor), 'user_id': actor}
        elif row['activity_type'] in ['RESERVATION_READY', 'FINE_CREATED']:
            performed_by = {'kind': 'SYSTEM', 'account': None, 'user_id': None}
        else:
            performed_by = {'kind': 'LEGACY_READER', 'account': users.get(target), 'user_id': target}
        result.append({'operation_id': str(row['activity_id']), 'operation_type': row['activity_type'],
            'target_user_id': target, 'target_user': users.get(target), 'actor_user_id': actor,
            'actor': users.get(actor) if actor is not None else None,
            'performed_by': performed_by,
            'book': {'work_id': row.get('work_id'), 'title': row.get('title') or source.get('title')
                     or books.get(row.get('work_id'), {}).get('title')},
            'occurred_at': row.get('created_at'), 'due_at': source.get('due_date'),
            'old_due_date': row.get('old_due_date'), 'new_due_date': row.get('new_due_date'),
            'renewal': renewal.get(row.get('issue_id'), {}).get('renewal'),
            'returned_at': source.get('returned_at'), 'status': source.get('status'),
            'description': row.get('description'),
            'source_ref': {k: row[k] for k in ['issue_id', 'reservation_id', 'fine_id'] if row.get(k) is not None}})
    return normalize_dates({'operations': result, 'count': activity_collection.count_documents(query),
            'limit': limit, 'offset': offset, 'operation_types': TYPES})


def user_activity(user_id):
    user = users_collection.find_one({'user_id': user_id}, USER_FIELDS)
    if not user:
        raise LookupError('Account not found.')
    def page(name, filters, sort):
        q = {'user_id': user_id, **filters}
        return {'records': list(db[name].find(q, {'_id': 0}).sort(sort, -1).limit(20)),
                'count': db[name].count_documents(q)}
    return normalize_dates({'user': user, 'loans': page('issues', {'status': 'ISSUED'}, 'issued_at'),
            'reservations': page('reservations', {'status': {'$in': ['ACTIVE', 'READY_FOR_PICKUP']}}, 'reserved_at'),
            'fines': page('fines', {}, 'created_at'), 'activity': operations(user_id=user_id),
            'notifications': {'records': list(db['notifications'].find({'user_id': user_id},
                {'_id': 0, 'dedupe_key': 0}).sort('created_at', -1).limit(20)),
                'count': db['notifications'].count_documents({'user_id': user_id})}})
