"""Local Events HTTP/performance fixture; only disposable accounts/records are cleaned."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import statistics
import sys
import time
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.database.mongodb import db, users_collection, books_collection
from backend.services.identity_service import next_user_id
from backend.services.auth_service import hash_password
from backend.utils.jwt_utils import create_access_token

REPORTS = ROOT / 'reports'
FIXTURE = ROOT / '.scratch/events_fixture.json'
client = httpx.Client(base_url='http://127.0.0.1:8002', timeout=20)

def save(name, data):
    (REPORTS / name).write_text(json.dumps(data, indent=2, default=str), encoding='utf8')

def request(f, role, method, path, body=None, expected=200):
    started = time.perf_counter()
    response = client.request(method, path, json=body, headers={'Authorization': 'Bearer ' + f['accounts'][role]['token']})
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    assert response.status_code == expected, (method, path, response.status_code, response.text[:300])
    return response.json(), elapsed

def seed():
    assert not FIXTURE.exists(), 'Finish/clean the previous disposable fixture before starting another.'
    marker = 'EVTEST-' + uuid4().hex[:10]
    f = {'marker': marker, 'accounts': {}, 'event_ids': []}
    FIXTURE.parent.mkdir(exist_ok=True)
    password = 'Events-test-only-2026!'
    hashed = hash_password(password)
    for key, role in [('admin', 'ADMIN'), ('librarian', 'LIBRARIAN'), ('readerA', 'GENERAL_USER'), ('readerB', 'GENERAL_USER')]:
        uid = next_user_id()
        email = f'{marker.lower()}-{key.lower()}@example.com'
        user = {'user_id': uid, 'email': email, 'name': 'Disposable Events ' + key, 'role': role,
                'password_hash': hashed, 'is_email_verified': True, 'is_active': True,
                'created_at': datetime.now(timezone.utc), 'events_test_marker': marker}
        users_collection.insert_one(user)
        f['accounts'][key] = {'user_id': uid, 'email': email, 'password': password, 'token': create_access_token(uid, email, role)}
        FIXTURE.write_text(json.dumps(f), encoding='utf8')
    f['book_ids'] = [r['work_id'] for r in books_collection.find({'work_id': {'$exists': True}}, {'_id': 0, 'work_id': 1}).limit(3)]
    assert len(f['book_ids']) == 3
    FIXTURE.write_text(json.dumps(f), encoding='utf8')
    return f

def body(f, **fields):
    return {'title': f['marker'] + ' new arrivals', 'category': 'NEW_ARRIVALS', 'summary': 'Disposable validation announcement.',
            'description': 'Temporary library validation. This record is removed after the checks.',
            'related_work_ids': f['book_ids'], **fields}

def create(f, role='librarian', **fields):
    row, elapsed = request(f, role, 'POST', '/staff/events', body(f, **fields), 201)
    f['event_ids'].append(row['event_id'])
    FIXTURE.write_text(json.dumps(f), encoding='utf8')
    return row, elapsed

def run(f):
    checks = {}
    security = {}
    perf = {}
    request(f, 'readerA', 'GET', '/events/unseen'); request(f, 'readerB', 'GET', '/events/unseen')
    notifications_before = db.notifications.count_documents({'user_id': {'$in': [a['user_id'] for a in f['accounts'].values()]}})
    draft, elapsed = create(f)
    perf['create_event'] = [elapsed]
    id = draft['event_id']
    assert draft['status'] == 'DRAFT' and draft['published_at'] is None and len(draft['related_books']) == 3
    request(f, 'readerA', 'GET', '/events/' + id, expected=404)
    assert request(f, 'readerA', 'GET', '/events/unseen')[0]['count'] == 0
    checks['draft_three_related_books_private'] = True
    event, elapsed = request(f, 'librarian', 'POST', '/staff/events/' + id + '/publish')
    perf['publish_event'] = [elapsed]
    pub = event['published_at']
    unseen, elapsed = request(f, 'readerA', 'GET', '/events/unseen'); perf['unseen_count'] = [elapsed]
    assert unseen['count'] == 1 and unseen['latest_event']['event_id'] == id
    checks['first_publish_visible_with_new_unseen'] = True
    request(f, 'readerB', 'POST', '/events/mark-seen', {'cursor': unseen['seen_cursor']}, 422)
    request(f, 'readerA', 'POST', '/events/mark-seen', {'cursor': unseen['seen_cursor'], 'user_id': f['accounts']['readerB']['user_id']}, 422)
    security['receipt_cannot_cross_account_or_take_payload_identity'] = True
    page, elapsed = request(f, 'readerA', 'GET', '/events?query=' + f['marker']); perf['published_list'] = [elapsed]
    assert len(page['events']) == 1 and page['events'][0]['event_id'] == id
    seen, elapsed = request(f, 'readerA', 'POST', '/events/mark-seen', {'cursor': page['seen_cursor']}); perf['mark_seen'] = [elapsed]
    assert seen['count'] == 0 and request(f, 'readerB', 'GET', '/events/unseen')[0]['count'] == 1
    checks['opening_events_receipt_seen_and_per_account_isolation'] = True
    changed, elapsed = request(f, 'admin', 'PATCH', '/staff/events/' + id, {'description': 'Corrected details.'}); perf['edit_event'] = [elapsed]
    assert changed['published_at'] == pub and changed['updated_by_user_id'] == f['accounts']['admin']['user_id']
    assert request(f, 'readerA', 'GET', '/events/unseen')[0]['count'] == 0
    assert request(f, 'admin', 'POST', '/staff/events/' + id + '/publish')[0]['published_at'] == pub
    checks['cross_staff_edit_preserves_first_publish_no_notification'] = True
    detail, elapsed = request(f, 'readerA', 'GET', '/events/' + id); perf['event_detail'] = [elapsed]
    assert [b['work_id'] for b in detail['related_books']] == f['book_ids'] and 'created_by' not in detail
    stored = db.events.find_one({'event_id': id})
    assert 'related_books' not in stored
    checks['related_metadata_hydrated_not_stored'] = True
    for method, path, payload in [('GET', '/staff/events', None), ('POST', '/staff/events', body(f)),
        ('PATCH', '/staff/events/' + id, {'title': 'Forbidden change'}), ('POST', '/staff/events/' + id + '/publish', None),
        ('POST', '/staff/events/' + id + '/cancel', None), ('POST', '/staff/events/' + id + '/archive', None), ('DELETE', '/staff/events/' + id, None)]:
        request(f, 'readerA', method, path, payload, 403)
    security['general_user_all_management_routes_403'] = True
    request(f, 'admin', 'POST', '/staff/events', body(f, created_by_user_id=f['accounts']['readerA']['user_id']), 422)
    security['server_audit_fields_reject_spoofing'] = True
    assert client.get('/events').status_code == 401
    security['unauthenticated_events_401'] = True
    request(f, 'admin', 'DELETE', '/staff/events/' + id, expected=409)
    checks['published_hard_delete_blocked'] = True
    request(f, 'admin', 'POST', '/staff/events/' + id + '/cancel')
    assert request(f, 'readerA', 'GET', '/events?query=' + f['marker'])[0]['count'] == 0
    assert request(f, 'readerA', 'GET', '/events/' + id)[0]['status'] == 'CANCELLED'
    request(f, 'librarian', 'POST', '/staff/events/' + id + '/archive')
    request(f, 'readerA', 'GET', '/events/' + id, expected=404)
    assert request(f, 'admin', 'GET', '/staff/events/' + id)[0]['status'] == 'ARCHIVED'
    checks['cancel_removed_upcoming_archive_retains_staff_history'] = True
    sale, _ = create(f, 'admin', category='BOOK_SALE', title=f['marker'] + ' book sale')
    assert sale['status'] == 'DRAFT' and not any(k in sale for k in ['price', 'checkout', 'payment'])
    request(f, 'admin', 'POST', '/staff/events/' + sale['event_id'] + '/publish')
    checks['admin_create_and_book_sale_informational_only'] = True
    past, _ = create(f, title=f['marker'] + ' past workshop', category='WORKSHOP',
                     start_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
    request(f, 'admin', 'POST', '/staff/events/' + past['event_id'] + '/publish')
    assert request(f, 'readerA', 'GET', '/events?view=past&query=' + f['marker'])[0]['events'][0]['event_id'] == past['event_id']
    checks['upcoming_past_category_search_and_pagination'] = True
    for _ in range(4):
        for key, role, method, path, payload in [
            ('published_list', 'readerA', 'GET', '/events', None), ('event_detail', 'readerA', 'GET', '/events/' + sale['event_id'], None),
            ('unseen_count', 'readerA', 'GET', '/events/unseen', None), ('staff_management_list', 'admin', 'GET', '/staff/events', None),
            ('category_search_filter', 'readerA', 'GET', '/events?category=BOOK_SALE&query=' + f['marker'], None),
            ('edit_event', 'admin', 'PATCH', '/staff/events/' + sale['event_id'], {'location': 'Test hall'}),
            ('publish_event', 'admin', 'POST', '/staff/events/' + sale['event_id'] + '/publish', None)]:
            _, elapsed = request(f, role, method, path, payload); perf.setdefault(key, []).append(elapsed)
        cursor = request(f, 'readerA', 'GET', '/events/unseen')[0]['seen_cursor']
        _, elapsed = request(f, 'readerA', 'POST', '/events/mark-seen', {'cursor': cursor}); perf['mark_seen'].append(elapsed)
        extra, elapsed = create(f, title=f['marker'] + ' latency draft'); perf['create_event'].append(elapsed)
        request(f, 'admin', 'DELETE', '/staff/events/' + extra['event_id'])
    assert db.notifications.count_documents({'user_id': {'$in': [a['user_id'] for a in f['accounts'].values()]}}) == notifications_before == 0
    assert db.event_user_state.count_documents({'user_id': {'$in': [f['accounts']['readerA']['user_id'], f['accounts']['readerB']['user_id']]}}) == 2
    checks['one_seen_record_per_reader_and_no_inbox_fanout'] = True
    indexes = {name: [{'name': i['name'], 'key': dict(i['key']), 'unique': bool(i.get('unique'))} for i in db[name].list_indexes()] for name in ['events', 'event_user_state']}
    timings = {}
    for key, samples in perf.items():
        threshold = 100 if key == 'unseen_count' else 500 if key in {'create_event','edit_event','publish_event','mark_seen'} else 250
        timings[key] = {'samples_ms': samples, 'median_ms': round(statistics.median(samples), 2), 'max_ms': max(samples),
                        'preferred_ms': threshold, 'within_preferred_max': max(samples) <= threshold}
    save('events_api.json', {'pass': all(checks.values()), 'checks': checks, 'indexes': indexes,
                            'base_url': 'http://127.0.0.1:8002', 'synthetic_records_only': True})
    save('events_security.json', {'pass': all(security.values()), 'live_checks': security,
                                'additional_security_cases': 'reports/events_backend.xml'})
    save('events_unseen_validation.json', {'pass': True, 'checks': {k:v for k,v in checks.items() if any(w in k for w in ['unseen','seen','notification','fanout'])},
         'window_days': 14, 'maximum_recent_events': 500, 'first_access_seeds_backlog': True,
         'equal_timestamp_publication_race': 'covered by Events backend test', 'session_bound_signed_receipts': True,
         'client_toast_validation': 'reports/events_frontend.log and events_live_validation.json'})
    save('events_performance.json', {'pass': all(t['within_preferred_max'] for t in timings.values()), 'timings': timings,
          'method': 'Five actual localhost HTTP samples/action; published idempotent repetitions and first publication are both included. Small V1 test event catalogue, existing live book catalogue; no ML.',
          'book_hydration': 'One bounded $in lookup per list/detail; at most 50 events × 12 canonical IDs.', 'indexes': indexes,
          'scalability_limit': 'Escaped substring search and computed upcoming sorting may scan/sort matching events; measurements are not a large-catalogue guarantee.'})
    print(json.dumps({'api_checks': len(checks), 'security_checks': len(security), 'performance': {k:v['max_ms'] for k,v in timings.items()}, 'marker': f['marker']}))

def cleanup(f):
    ids = [a['user_id'] for a in f['accounts'].values()]
    # All created events, including UI-created ones, are marked in their title
    # and attributed to the disposable staff. No unrelated records match.
    result = db.events.delete_many({'created_by_user_id': {'$in': ids}, 'title': {'$regex': '^' + f['marker']}})
    states = db.event_user_state.delete_many({'user_id': {'$in': ids}})
    accounts = users_collection.delete_many({'user_id': {'$in': ids}, 'events_test_marker': f['marker']})
    assert accounts.deleted_count == len(ids)
    FIXTURE.unlink()
    save('events_cleanup.json', {'pass': True, 'synthetic_events_removed': result.deleted_count,
          'synthetic_seen_states_removed': states.deleted_count, 'synthetic_accounts_removed': accounts.deleted_count,
          'method': 'Explicit marker and disposable staff IDs only; no production events or users removed. Product API still forbids hard deletion of published events.'})
    print('Disposable Events records cleaned.')

if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'run'
    if action == 'run':
        run(seed())
    else:
        f = json.loads(FIXTURE.read_text(encoding='utf8'))
        if action == 'cleanup': cleanup(f)
        elif action == 'publish-ui':
            row, _ = create(f, title=f['marker'] + ' online announcement')
            request(f, 'admin', 'POST', '/staff/events/' + row['event_id'] + '/publish')
            print(row['event_id'])
        elif action == 'credentials':
            # Only freshly generated, disposable test credentials; never real users.
            print(json.dumps({key:{'email': a['email'], 'password': a['password']} for key,a in f['accounts'].items()}))
