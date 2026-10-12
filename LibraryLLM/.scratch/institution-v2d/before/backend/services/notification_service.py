"""Durable account-owned in-app notices. No email, model or external push."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import re
import time
from pymongo.errors import DuplicateKeyError
from backend.database.mongodb import db, users_collection, issues_collection
from backend.services.identity_service import find_user_by_email

notifications = db['notifications']
PUBLIC_FIELDS = {'_id': 0, 'notification_id': 1, 'type': 1, 'title': 1, 'message': 1,
                 'created_at': 1, 'read_at': 1, 'source': 1, 'source_ref': 1, 'priority': 1,
                 'resolved_at': 1, 'resolution_reason': 1}
USER_FIELDS = {'_id': 0, 'user_id': 1, 'name': 1, 'email': 1, 'role': 1}


def ensure_indexes():
    notifications.create_index('notification_id', unique=True)
    notifications.create_index('dedupe_key', unique=True)
    notifications.create_index([('user_id', 1), ('created_at', -1), ('notification_id', -1)])
    notifications.create_index([('user_id', 1), ('read_at', 1)])
    notifications.create_index([('created_by_user_id', 1), ('created_at', -1)])
    notifications.create_index([('source', 1), ('created_at', -1), ('notification_id', -1)])
    notifications.create_index([('source_ref.loan_id', 1), ('resolved_at', 1)])
    notifications.create_index([('source', 1), ('resolved_at', 1), ('type', 1)])
    notifications.create_index([('user_id', 1), ('resolved_at', 1), ('created_at', -1), ('notification_id', -1)])
    issues_collection.create_index([('status', 1), ('due_date', 1)])
    db['activity'].create_index([('user_id', 1), ('created_at', -1), ('activity_id', -1)])
    db['activity'].create_index([('work_id', 1), ('created_at', -1)])
    db['activity'].create_index([('created_at', -1), ('activity_id', -1)])
    db['activity'].create_index('event_key', unique=True, sparse=True)


def directory(query='', limit=20, offset=0):
    criteria = {'is_active': {'$ne': False}, 'is_email_verified': True}
    if query:
        criteria['email'] = {'$regex': re.escape(query.strip()), '$options': 'i'}
    return {'users': list(users_collection.find(criteria, USER_FIELDS)
                          .sort([('email', 1), ('user_id', 1)]).skip(offset).limit(limit)),
            'count': users_collection.count_documents(criteria)}


def recipients(ids, emails):
    # Resolve all recipients before writing any delivery. Never accept email as ownership.
    wanted = set(ids)
    for email in emails:
        user = find_user_by_email(email)
        if not user:
            raise ValueError('A recipient email was not found or is ambiguous.')
        wanted.add(user['user_id'])
    if not wanted or len(wanted) > 50:
        raise ValueError('Select between 1 and 50 recipients.')
    found = list(users_collection.find({'user_id': {'$in': list(wanted)},
                                      'is_active': {'$ne': False}, 'is_email_verified': True}, USER_FIELDS))
    if {u['user_id'] for u in found} != wanted:
        raise ValueError('A recipient is unavailable.')
    return sorted(wanted)


def insert_notice(user_id, kind, title, message, key, source='SYSTEM', source_ref=None, sender=None, now=None):
    notice = {'notification_id': uuid4().hex, 'user_id': user_id, 'type': kind,
              'title': title, 'message': message, 'created_at': now or datetime.now(timezone.utc),
              'read_at': None, 'resolved_at': None, 'resolution_reason': None,
              'source': source, 'source_ref': source_ref or {},
              'priority': 'NORMAL', 'dedupe_key': key, 'created_by_user_id': sender}
    try:
        result = notifications.update_one({'dedupe_key': key}, {'$setOnInsert': notice}, upsert=True)
        created = result.upserted_id is not None
    except DuplicateKeyError:
        created = False
    return notifications.find_one({'dedupe_key': key}, {'_id': 0}), created


def send_admin(actor, ids, emails, title, message, request_id):
    targets = recipients(ids, emails)
    keys = [f'ADMIN_MESSAGE:{actor}:{request_id}:{uid}' for uid in targets]
    existing = list(notifications.find({'dedupe_key': {'$in': keys}}, {'title': 1, 'message': 1}))
    if any(n['title'] != title or n['message'] != message for n in existing):
        raise ValueError('This send request was already used for different content.')
    delivered = []
    for uid, key in zip(targets, keys):
        notice, created = insert_notice(uid, 'ADMIN_MESSAGE', title, message, key,
                                       source='ADMIN', sender=actor)
        delivered.append({'notification_id': notice['notification_id'], 'user_id': uid,
                          'status': 'STORED', 'created': created})
    return {'deliveries': delivered, 'recipient_count': len(delivered)}


def list_own(user_id, limit=20, offset=0):
    query = {'user_id': user_id}
    current = {**query, 'resolved_at': None}
    current_count = notifications.count_documents(current)
    order = [('created_at', -1), ('notification_id', -1)]
    rows = list(notifications.find(current, PUBLIC_FIELDS).sort(order).skip(offset).limit(limit)) if offset < current_count else []
    if len(rows) < limit:
        rows += list(notifications.find({**query, 'resolved_at': {'$ne': None}}, PUBLIC_FIELDS)
            .sort(order).skip(max(0, offset - current_count)).limit(limit - len(rows)))
    return normalize_dates({'notifications': rows,
        'count': notifications.count_documents(query), 'unread_count': unread(user_id),
        'limit': limit, 'offset': offset})


def unread(user_id):
    return notifications.count_documents({'user_id': user_id, 'read_at': None, 'resolved_at': None})


def mark_read(user_id, notification_id):
    query = {'notification_id': notification_id, 'user_id': user_id}
    if not notifications.find_one(query, {'_id': 1}):
        raise LookupError('Notification not found.')
    notifications.update_one({**query, 'read_at': None}, {'$set': {'read_at': datetime.now(timezone.utc)}})
    return normalize_dates(notifications.find_one(query, PUBLIC_FIELDS))


def read_all(user_id):
    # Timestamp cutoff prevents a concurrent newly-arrived message being silently marked read.
    now = datetime.now(timezone.utc)
    result = notifications.update_many({'user_id': user_id, 'read_at': None, 'created_at': {'$lte': now}},
                                       {'$set': {'read_at': now}})
    return {'marked': result.modified_count}


def sent(limit=20, offset=0):
    query = {'source': 'ADMIN'}
    rows = list(notifications.find(query, {'_id': 0}).sort([('created_at', -1), ('notification_id', -1)])
                .skip(offset).limit(limit))
    ids = {n[k] for n in rows for k in ['user_id', 'created_by_user_id'] if n.get(k) is not None}
    users = {u['user_id']: u for u in users_collection.find({'user_id': {'$in': list(ids)}}, USER_FIELDS)}
    return normalize_dates({'notifications': [{**{k: v for k, v in n.items() if k != 'dedupe_key'},
                'recipient': users.get(n['user_id']), 'sender': users.get(n['created_by_user_id']),
                'delivery_status': 'STORED'} for n in rows],
            'count': notifications.count_documents(query), 'limit': limit, 'offset': offset})


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def normalize_dates(value):
    """Mongo returns naive UTC; explicit offsets keep browser display unambiguous."""
    if isinstance(value, datetime):
        return utc(value)
    if isinstance(value, dict):
        return {k: normalize_dates(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_dates(v) for v in value]
    return value


def due_state(due, now):
    delta = (utc(due).date() - utc(now).date()).days
    return 'OVERDUE' if delta < 0 else 'DUE_TODAY' if delta == 0 else 'DUE_SOON' if delta == 2 else None


def scan_due(now=None, user_ids=None):
    """Only relevant active loans. Optional owner scope is for isolated CLI validation."""
    started = time.perf_counter()
    now = utc(now or datetime.now(timezone.utc))
    cutoff = datetime.combine(now.date() + timedelta(days=3), datetime.min.time(), timezone.utc)
    query = {'status': 'ISSUED', 'due_date': {'$lt': cutoff}}
    if user_ids is not None:
        query['user_id'] = {'$in': list(user_ids)}
    counts = {'active_loans_scanned': 0, 'relevant_loans': 0, 'created': 0, 'duplicates_skipped': 0,
              'invalid_or_changed_skipped': 0}
    from backend.services.loan_notification_service import reconcile_current_reminders, reconcile_loan_notifications, stale_reason
    counts['resolved_stale'] = reconcile_current_reminders(user_ids)
    cursor = issues_collection.find(query, {'_id': 0}).batch_size(500)
    for loan in cursor:
        counts['active_loans_scanned'] += 1
        try:
            kind = due_state(loan['due_date'], now)
            uid = loan['user_id']
            if not isinstance(uid, int) or isinstance(uid, bool):
                raise ValueError('Invalid account reference')
        except (KeyError, ValueError, TypeError, AttributeError):
            counts['invalid_or_changed_skipped'] += 1
            continue
        if not kind:
            continue
        counts['relevant_loans'] += 1
        # Re-read exact source state immediately before storing; changed/returned loans are skipped.
        current = {'issue_id': loan['issue_id'], 'user_id': uid, 'status': 'ISSUED', 'due_date': loan['due_date']}
        if not issues_collection.find_one(current, {'_id': 1}):
            counts['invalid_or_changed_skipped'] += 1
            continue
        title = loan.get('title') or loan.get('work_id') or 'Your book'
        suffix = {'DUE_SOON': 'is due in 2 days.', 'DUE_TODAY': 'is due today.', 'OVERDUE': 'is overdue.'}[kind]
        due = utc(loan['due_date']).isoformat()
        key = f"{kind}:{loan['issue_id']}:{due}"
        _, created = insert_notice(uid, kind, {'DUE_SOON': 'Book due soon', 'DUE_TODAY': 'Book due today',
                                              'OVERDUE': 'Book overdue'}[kind], f'{title} {suffix}', key,
                                  source_ref={'loan_id': loan['issue_id'], 'work_id': loan.get('work_id'),
                                              'due_date': due}, now=now)
        counts['created' if created else 'duplicates_skipped'] += 1
        # If return/renew won after the precheck (including after its reconciliation),
        # this postcheck resolves our insert. If it wins later, that mutation resolves it.
        latest = issues_collection.find_one({'issue_id': loan['issue_id']}, {'_id': 0})
        reason = stale_reason(latest, due)
        if reason:
            counts['resolved_stale'] += reconcile_loan_notifications(loan['issue_id'], due, reason)
    return {**counts, 'scanned_at': now.isoformat(), 'duration_ms': (time.perf_counter()-started)*1000}


def notify_reservation_available(reservation):
    return insert_notice(reservation['user_id'], 'RESERVATION_AVAILABLE', 'Reservation ready',
        f"{reservation['title']} is ready for pickup.", f"RESERVATION_AVAILABLE:{reservation['reservation_id']}",
        source_ref={'reservation_id': reservation['reservation_id'], 'work_id': reservation['work_id']})
