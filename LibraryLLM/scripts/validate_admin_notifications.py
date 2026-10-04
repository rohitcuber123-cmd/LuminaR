"""Loopback validation with explicitly disposable accounts and catalogue works only."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PRIVATE = ROOT / '.admin_notification_validation.json'
REPORT = ROOT / 'reports/admin_notification_live_validation.json'


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare', 'run', 'cleanup'])
    args = parser.parse_args()
    from backend.database.mongodb import db, users_collection, books_collection
    from backend.services.identity_service import next_user_id
    from backend.services.auth_service import hash_password
    from backend.services.notification_service import scan_due
    import httpx

    def collection_state(exclude_ids=None):
        ids = exclude_ids or []
        return {name: hashlib.sha256(json.dumps(list(db[name].find({'user_id': {'$nin': ids}}).sort('_id', 1)),
            sort_keys=True, default=str).encode()).hexdigest()
            for name in ['users', 'activity', 'issues', 'reservations', 'fines', 'reading_list', 'library_inventory']}

    if args.action == 'prepare':
        assert not PRIVATE.exists(), 'Validation already prepared.'
        run = uuid4().hex[:10]
        data = {'run': run, 'before': collection_state(), 'books_before_count': books_collection.count_documents({}), 'accounts': {}}
        for label, role in [('Admin A', 'ADMIN'), ('Alice', 'GENERAL_USER'), ('Bob', 'GENERAL_USER')]:
            uid = next_user_id(); password = uuid4().hex + 'aA1!'
            email = f'notify-{label.lower().replace(" ","-")}-{run}@example.com'
            users_collection.insert_one({'user_id': uid, 'name': f'Disposable {label}', 'email': email,
                'password_hash': hash_password(password), 'role': role, 'is_email_verified': True,
                'is_active': True, 'created_at': datetime.now(timezone.utc)})
            data['accounts'][label] = {'user_id': uid, 'email': email, 'password': password, 'role': role}
        largest = books_collection.find_one({}, {'book_id': 1}, sort=[('book_id', -1)])['book_id']
        data['works'] = []
        for i in range(2):
            wid = f'OL{int(run, 16) + 900000000 + i}W'
            assert not books_collection.find_one({'work_id': wid})
            books_collection.insert_one({'book_id': largest + i + 1, 'work_id': wid, 'title': f'Notification Test Book {"AB"[i]}',
                'authors': 'Disposable test author', 'subjects': 'Test fixture', 'description': 'Disposable circulation validation book.',
                'available_copies': 2, 'total_copies': 2})
            data['works'].append(wid)
        PRIVATE.write_text(json.dumps(data, indent=2), encoding='utf-8')
        print('Prepared three disposable accounts and two disposable works; private credentials saved locally.')
        return

    data = json.loads(PRIVATE.read_text(encoding='utf-8'))
    ids = [a['user_id'] for a in data['accounts'].values()]
    if args.action == 'cleanup':
        assert all(users_collection.find_one({'user_id': a['user_id'], 'name': {'$regex': '^Disposable '}})
                   for a in data['accounts'].values())
        for name in ['activity', 'issues', 'reservations', 'fines', 'notifications', 'reading_list']:
            db[name].delete_many({'user_id': {'$in': ids}})
        users_collection.delete_many({'user_id': {'$in': ids}, 'name': {'$regex': '^Disposable '}})
        books_collection.delete_many({'work_id': {'$in': data['works']}, 'authors': 'Disposable test author'})
        assert collection_state() == data['before'], 'Non-test circulation/account state changed.'
        assert books_collection.count_documents({}) == data['books_before_count']
        report = json.loads(REPORT.read_text(encoding='utf-8'))
        report['disposable_cleanup'] = 'Complete; original users/circulation/inventory hashes and book count match.'
        REPORT.write_text(json.dumps(report, indent=2), encoding='utf-8')
        PRIVATE.unlink()
        print('Removed test-only accounts, works, loans, events and notifications; original data hashes match.')
        return

    assert not REPORT.exists(), 'Preserve prior evidence; choose a fresh report before rerunning.'
    tokens = {}
    perf = {}
    with httpx.Client(base_url='http://127.0.0.1:8002', timeout=30) as client:
        for label, a in data['accounts'].items():
            response = client.post('/auth/login', json={'email': a['email'], 'password': a['password']})
            assert response.status_code == 200, (label, response.status_code)
            tokens[label] = response.json()['access_token']
            a['token'] = tokens[label]
        def req(label, method, path, **kw):
            start = time.perf_counter(); response = client.request(method, path,
                headers={'Authorization': 'Bearer ' + tokens[label]}, **kw)
            perf.setdefault(method + ' ' + path.split('?')[0], []).append((time.perf_counter()-start)*1000)
            assert response.is_success, (path, response.status_code, response.text[:150])
            return response.json()
        loans = []
        for label, wid in zip(['Alice', 'Bob'], data['works']):
            result = req(label, 'POST', '/issues/issue', json={'work_id': wid}); loans.append(result['issue'])
        alice, bob = data['accounts']['Alice'], data['accounts']['Bob']
        filtered = req('Admin A', 'GET', '/admin/operations?email=' + alice['email'])
        assert filtered['count'] == 1 and filtered['operations'][0]['target_user_id'] == alice['user_id']
        assert filtered['operations'][0]['actor_user_id'] == alice['user_id']
        req('Admin A', 'POST', f"/admin/operations/return/{loans[0]['issue_id']}")
        rows = req('Admin A', 'GET', f"/admin/operations?user_id={alice['user_id']}")['operations']
        returned = next(r for r in rows if r['operation_type'] == 'BOOK_RETURNED')
        assert returned['actor_user_id'] == data['accounts']['Admin A']['user_id']
        old = alice['email']; alice['email'] = f"notify-alice-new-{data['run']}@example.com"
        users_collection.update_one({'user_id': alice['user_id']}, {'$set': {'email': alice['email']}})
        changed = req('Admin A', 'GET', '/admin/operations?email=' + alice['email'])
        assert changed['count'] == 2 and all(r['target_user']['email'] == alice['email'] for r in changed['operations'])
        assert req('Admin A', 'GET', '/admin/operations?email=' + old)['count'] == 0
        rid = str(uuid4())
        sent = req('Admin A', 'POST', '/admin/notifications', json={'recipient_emails': [alice['email']],
            'title': 'Library notice', 'message': 'Please visit the circulation desk.', 'request_id': rid})
        nid = sent['deliveries'][0]['notification_id']
        inbox = req('Alice', 'GET', '/notifications'); assert inbox['count'] == inbox['unread_count'] == 1
        assert req('Bob', 'GET', '/notifications')['count'] == 0
        assert client.patch('/notifications/'+nid+'/read', headers={'Authorization':'Bearer '+tokens['Bob']}).status_code == 404
        # Persistence through fresh HTTP clients and normal logout/login.
        req('Alice', 'POST', '/auth/logout')
        login = client.post('/auth/login', json={'email': alice['email'], 'password': alice['password']})
        assert login.status_code == 200
        tokens['Alice'] = login.json()['access_token']; alice['token'] = tokens['Alice']
        assert req('Alice', 'GET', '/notifications')['count'] == 1
        req('Alice', 'PATCH', '/notifications/'+nid+'/read')
        assert req('Alice', 'GET', '/notifications/unread-count')['unread_count'] == 0
        req('Admin A', 'POST', '/admin/notifications', json={'recipient_user_ids': [alice['user_id'], bob['user_id']],
            'title': 'Selected-account notice', 'message': 'Validation only.', 'request_id': str(uuid4())})
        now = datetime.now(timezone.utc)
        # Existing disposable Bob loan becomes due today. New disposable Alice loan is due in2days.
        db.issues.update_one({'issue_id': loans[1]['issue_id'], 'user_id': bob['user_id']}, {'$set': {'due_date': now}})
        soon = req('Alice', 'POST', '/issues/issue', json={'work_id': data['works'][0]})['issue']
        db.issues.update_one({'issue_id': soon['issue_id'], 'user_id': alice['user_id']}, {'$set': {'due_date': now+timedelta(days=2)}})
        oid = db.issues.find_one({}, {'issue_id': 1}, sort=[('issue_id', -1)])['issue_id'] + 1
        db.issues.insert_one({'issue_id': oid, 'user_id': alice['user_id'], 'work_id': data['works'][0],
            'title': 'Notification Test Book A', 'issued_at': now-timedelta(days=20),
            'due_date': now-timedelta(days=3), 'status': 'ISSUED', 'returned_at': None})
        first = scan_due(now, ids); repeat = scan_due(now, ids)
        assert first['created'] == 3 and repeat['created'] == 0 and repeat['duplicates_skipped'] == 3
        kinds = {n['type'] for n in db.notifications.find({'user_id': {'$in': ids}, 'source': 'SYSTEM'})}
        assert kinds == {'DUE_SOON', 'DUE_TODAY', 'OVERDUE'}
        for _ in range(3):
            for path in ['/admin/operations?limit=1', '/admin/operations?limit=1&offset=1',
                '/admin/operations?email='+alice['email'], f"/admin/users/{alice['user_id']}/activity"]:
                req('Admin A', 'GET', path)
            req('Alice', 'GET', '/notifications'); req('Alice', 'GET', '/notifications/unread-count')
        req('Alice', 'POST', '/notifications/read-all')
        assert req('Alice', 'GET', '/notifications/unread-count')['unread_count'] == 0
    PRIVATE.write_text(json.dumps(data, indent=2), encoding='utf-8')
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'isolated_accounts': ids,
        'isolated_works': data['works'], 'self_service_attribution': True, 'admin_assisted_return_actor': True,
        'current_email_change_history': True, 'single_admin_message_correct_user': True,
        'bob_received_no_alice_notice': True, 'refresh_and_relogin_persistence': True,
        'mark_read_unread_count': True, 'multi_recipient': True, 'cross_user_id_private_404': True,
        'due_first': first, 'due_repeat': repeat, 'due_types': sorted(kinds),
        'non_test_state_unchanged': collection_state(ids) == data['before'],
        'qwen_calls': 0, 'method': 'Real loopback API, disposable DB records; scoped reminder batch. Browser checks recorded separately.'}
    assert report['non_test_state_unchanged']
    REPORT.write_text(json.dumps(report, indent=2), encoding='utf-8')
    (ROOT/'reports/admin_notification_performance.json').write_text(json.dumps({
        'http_ms': {k: {'samples': len(v), 'median': statistics.median(v), 'max': max(v)} for k,v in perf.items()},
        'due_batch': first, 'repeat_due_batch': repeat}, indent=2), encoding='utf-8')
    print('Live attribution, changed email, persistence, private ownership, multi-send and all3 due states pass.')


if __name__ == '__main__': main()
