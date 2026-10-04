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
PRIVATE = ROOT / '.loan_renewal_validation.json'
REPORT = ROOT / 'reports/loan_renewal_live_validation.json'


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
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from backend.services import notification_service as ns
    tokens={};perf={};checks={}
    with httpx.Client(base_url='http://127.0.0.1:8002',timeout=30) as client:
        for label,a in data['accounts'].items():
            r=client.post('/auth/login',json={'email':a['email'],'password':a['password']});r.raise_for_status()
            tokens[label]=r.json()['access_token']
        def req(label,method,path,name=None,**kw):
            start=time.perf_counter();r=client.request(method,path,headers={'Authorization':'Bearer '+tokens[label]},**kw)
            perf.setdefault(name or method+' '+path.split('?')[0],[]).append((time.perf_counter()-start)*1000)
            r.raise_for_status();return r.json()
        now=datetime.now(timezone.utc).replace(microsecond=0)
        alice,bob,admin=(data['accounts'][n]['user_id'] for n in ['Alice','Bob','Admin A'])
        a=req('Alice','POST','/issues/issue',json={'work_id':data['works'][0]})['issue']
        db.issues.update_one({'issue_id':a['issue_id'],'user_id':alice},{'$set':{'due_date':now+timedelta(days=2)}})
        a=db.issues.find_one({'issue_id':a['issue_id']},{'_id':0})
        before=scan_due(now,ids);assert before['created']==1
        admin_message=req('Admin A','POST','/admin/notifications',json={'recipient_user_ids':[alice],'title':'Library notice','message':'Please visit the desk.','request_id':str(uuid4())})
        payload={'expected_due_date':ns.utc(a['due_date']).isoformat(),'request_id':str(uuid4())}
        renewed=req('Alice','POST',f"/issues/{a['issue_id']}/renew",name='renew_operation',json=payload)
        assert ns.utc(renewed['new_due_date'])==ns.utc(a['due_date'])+timedelta(days=14) and renewed['renewal_count']==1
        assert req('Alice','POST',f"/issues/{a['issue_id']}/renew",name='renew_retry',json=payload)['idempotent_replay']
        history=req('Alice','GET','/notifications');old=next(n for n in history['notifications'] if n['type']=='DUE_SOON')
        assert old['resolution_reason']=='LOAN_RENEWED' and old['read_at'] is None
        assert history['unread_count']==1 and history['notifications'][0]['type']=='ADMIN_MESSAGE'
        assert scan_due(now+timedelta(days=3),ids)['created']==0
        future=scan_due(now+timedelta(days=14),ids);assert future['created']==1
        assert db.notifications.count_documents({'user_id':alice,'type':'DUE_SOON','resolved_at':None})==1
        checks.update(owner_renewal=True,renewal_retry_one_extension=True,old_due_resolved_read_separate=True,old_due_no_future_alert=True,new_due_version_future_alert=True,admin_message_unaffected=True)
        # A real one-copy circulation queue reaches READY only after return.
        books_collection.update_one({'work_id':data['works'][1]},{'$set':{'total_copies':1,'available_copies':1}})
        b=req('Bob','POST','/issues/issue',json={'work_id':data['works'][1]})['issue']
        req('Alice','POST','/reservations/',json={'work_id':data['works'][1]})
        db.issues.update_one({'issue_id':b['issue_id'],'user_id':bob},{'$set':{'due_date':now-timedelta(days=3)}})
        overdue=scan_due(now,ids);assert overdue['created']==1
        returned=req('Bob','POST',f"/issues/return/{b['issue_id']}");assert returned['fine']['amount']==15
        assert db.notifications.find_one({'user_id':bob,'type':'OVERDUE'})['resolution_reason']=='LOAN_RETURNED'
        assert scan_due(now,ids)['created']==0
        assert db.notifications.count_documents({'user_id':alice,'type':'RESERVATION_AVAILABLE'})==1
        checks.update(overdue_return_resolved=True,returned_worker_no_new_alert=True,fees_unchanged=True,authoritative_reservation_available=True)
        gui=req('Alice','POST','/issues/issue',json={'work_id':data['works'][1]})['issue']
        db.issues.update_one({'issue_id':gui['issue_id'],'user_id':alice},{'$set':{'due_date':now+timedelta(days=2)}})
        scan_due(now,ids);data['gui_issue_id']=gui['issue_id']
        # Third disposable work permits independent assisted-renew race.
        wid=data['works'][0][:-1]+'99W';assert not books_collection.find_one({'work_id':wid})
        bid=books_collection.find_one({}, {'book_id':1},sort=[('book_id',-1)])['book_id']+1
        books_collection.insert_one({'book_id':bid,'work_id':wid,'title':'Notification Test Book C','authors':'Disposable test author','available_copies':2,'total_copies':2})
        data['works'].append(wid);PRIVATE.write_text(json.dumps(data,indent=2),encoding='utf-8')
        c=req('Alice','POST','/issues/issue',json={'work_id':wid})['issue']
        db.issues.update_one({'issue_id':c['issue_id'],'user_id':alice},{'$set':{'due_date':now+timedelta(days=2)}})
        c=db.issues.find_one({'issue_id':c['issue_id']},{'_id':0})
        def race(doc,action):
            entered,done=Event(),Event();original=ns.insert_notice
            def paused(*args,**kwargs):
                if kwargs.get('source_ref',{}).get('loan_id') != doc['issue_id']:
                    return original(*args,**kwargs)
                entered.set();assert done.wait(10);return original(*args,**kwargs)
            ns.insert_notice=paused
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pending=pool.submit(scan_due,now,[doc['user_id']]);assert entered.wait(10)
                    try:
                        if action=='renew':req('Admin A','POST',f"/admin/operations/renew/{doc['issue_id']}",json={'request_id':str(uuid4()),'expected_due_date':ns.utc(doc['due_date']).isoformat()})
                        else:req('Bob','POST',f"/issues/return/{doc['issue_id']}")
                    finally:done.set()
                    result=pending.result(timeout=10)
            finally:ns.insert_notice=original
            assert result['created'] >= 1 and result['resolved_stale'] >= 1
            assert db.notifications.count_documents({'source_ref.loan_id':doc['issue_id'],'resolved_at':None,'type':{'$in':['DUE_SOON','DUE_TODAY','OVERDUE']}})==0
            return result
        assisted_race=race(c,'renew')
        row=db.activity.find_one({'issue_id':c['issue_id'],'activity_type':'BOOK_RENEWED'})
        assert row['actor_user_id']==admin and row['user_id']==alice
        d=req('Bob','POST','/issues/issue',json={'work_id':data['works'][0]})['issue']
        db.issues.update_one({'issue_id':d['issue_id'],'user_id':bob},{'$set':{'due_date':now-timedelta(days=3)}})
        d=db.issues.find_one({'issue_id':d['issue_id']},{'_id':0});return_race=race(d,'return')
        checks.update(real_core_assisted_renew_race=True,real_core_return_race=True,admin_actor_target=True)
        for _ in range(5):
            req('Alice','GET',f"/issues/{gui['issue_id']}/renewal",name='renew_eligibility')
            req('Alice','GET','/issues/my',name='user_loans_page')
            req('Admin A','GET','/admin/operations?limit=20',name='admin_operations_page')
        # Same source/ref query used by reconciliation: verify the installed index plan.
        query={'source_ref.loan_id':a['issue_id'],'resolved_at':None,'source':'SYSTEM','type':{'$in':['DUE_SOON','DUE_TODAY','OVERDUE']}}
        plan=db.notifications.find(query).explain()
        from backend.services.loan_notification_service import reconcile_loan_notifications
        timings=[]
        for _ in range(5):
            start=time.perf_counter();reconcile_loan_notifications(a['issue_id'],a['due_date'],'LOAN_RENEWED');timings.append((time.perf_counter()-start)*1000)
        perf['idempotent_reconciliation']=timings
        after=scan_due(now,ids)
    PRIVATE.write_text(json.dumps(data,indent=2),encoding='utf-8')
    report={'created_at':datetime.now(timezone.utc).isoformat(),'checks':checks,'test_user_ids':ids,'test_work_ids':data['works'],'gui_issue_id':data['gui_issue_id'],'worker_first':before,'worker_new_version':future,'assisted_renew_race':assisted_race,'return_race':return_race,'worker_final':after,'non_test_state_unchanged':collection_state(ids)==data['before'],'qwen_calls':0}
    assert report['non_test_state_unchanged'];REPORT.write_text(json.dumps(report,indent=2),encoding='utf-8')
    prior=json.loads((ROOT/'reports/admin_notification_performance.json').read_text())['due_batch']
    (ROOT/'reports/loan_renewal_performance.json').write_text(json.dumps({'http_and_service_ms':{k:{'samples':len(v),'median':statistics.median(v),'max':max(v)} for k,v in perf.items()},'worker_before_change_prior_phase':prior,'worker_after_change':after,'comparison_limit':'Before/after use small disposable fixtures; different scenario mix, not a controlled capacity benchmark.','reconciliation_query_plan':plan['queryPlanner']['winningPlan'],'query_execution':{k:plan.get('executionStats',{}).get(k) for k in ['nReturned','totalKeysExamined','totalDocsExamined']}},indent=2),encoding='utf-8')
    print('Live owner renewal, receipts, due versions, return/fines, ready reservation and real Core worker races pass.')


if __name__=='__main__':main()
