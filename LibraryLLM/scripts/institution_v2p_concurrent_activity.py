"""Read-only preservation of original records while respecting live app activity."""
from pathlib import Path
from datetime import datetime,timezone
import json
from dotenv import dotenv_values
from pymongo import MongoClient
from scripts.institution_v2i_baseline import digest
ROOT=Path(__file__).resolve().parents[1]

def capture(baseline):
    cutoff=datetime.fromisoformat(baseline['captured_at']);env=dotenv_values(ROOT/'.env')
    report={'captured_at':datetime.now(timezone.utc).isoformat(),'database_classification':'UNKNOWN','read_only':True,'concurrent_data_cleanup_performed':False}
    with MongoClient(env['MONGO_URI']) as client:
        db=client['luminar_library']
        fresh=list(db.notifications.find({'created_at':{'$gte':cutoff}}))
        original=list(db.notifications.find({'notification_id':{'$nin':[r['notification_id'] for r in fresh]}}))
        report['original_50_notifications_equal']=len(original)==baseline['communication_state']['notifications']['count'] and digest(original)==baseline['communication_state']['notifications']['sha256']
        report['original_50_sha256']=digest(original)
        report['current_notification_count']=db.notifications.count_documents({})
        report['new_notifications_metadata']=[{k:r.get(k) for k in ['notification_id','type','scope','library_id','source_id','created_at']} for r in fresh]
        report['concurrent_announcements_metadata']=list(db.institution_announcements.find({}, {'_id':0,'announcement_id':1,'library_id':1,'created_by_user_id':1,'created_at':1,'published_at':1,'withdrawn_at':1,'status':1,'revision':1,'delivery.total':1,'delivery.state':1}))
        report['announcements_not_task_fixtures']=all(r['library_id']==baseline['state']['TEST']['library_id'] and r['created_by_user_id']==4 for r in report['concurrent_announcements_metadata'])
        report['original_append_only_journals']={}
        for name in ['institution_audit','institution_lending_operations']:
            old=list(db[name].find({'created_at':{'$lt':cutoff}}));new=list(db[name].find({'created_at':{'$gte':cutoff}}))
            report['original_append_only_journals'][name]={'original_count':len(old),'original_hash':digest(old),
                'original_equal':len(old)==baseline['state']['tenant_collections'][name]['count'] and digest(old)==baseline['state']['tenant_collections'][name]['sha256'],
                'new_count':len(new),'new_metadata':[{k:r.get(k) for k in ['library_id','event','operation_id','operation_type','actor_user_id','lending_request_id','state','created_at']} for r in new]}
        # The existing journal stores the exact original insert receipt. Use it
        # only in memory to verify the baseline, never to reset an expired request.
        current=list(db.institution_lending_requests.find({'created_at':{'$lt':cutoff}}))
        expiries=list(db.institution_lending_operations.find({'created_at':{'$gte':cutoff},'operation_type':'BORROW_REQUEST_EXPIRED','actor_user_id':0,'state':'COMMITTED'}))
        projections={};transitions=[]
        for operation in expiries:
            row=next(r for r in current if r['lending_request_id']==operation['lending_request_id'])
            creation=db.institution_lending_operations.find_one({'operation_id':row['operation_id'],'state':'COMMITTED'})
            before_step=next(s for s in creation['effects'] if s['collection']=='lending_requests' and s['query']['lending_request_id']==row['lending_request_id'] and s['insert_only'])
            expiry_step=next(s for s in operation['effects'] if s['collection']=='lending_requests' and s['query']['lending_request_id']==row['lending_request_id'])
            matches=all(row.get(k)==v for k,v in expiry_step['values'].items())
            projections[row['lending_request_id']]={**before_step['values'],'_id':row['_id']}
            transitions.append({'lending_request_id':row['lending_request_id'],'operation_id':operation['operation_id'],
                'from':before_step['values'].get('status'),'to':row['status'],'actor':0,'current_matches_committed_expiry_effect':matches,
                'method':'Exact original committed creation receipt substituted in memory only; no database reversal.'})
        projected=[projections.get(r['lending_request_id'],r) for r in current]
        report['lending_request_expiry_provenance']=transitions
        report['original_requests_projection_equal']=len(projected)==baseline['state']['tenant_collections']['institution_lending_requests']['count'] and digest(projected)==baseline['state']['tenant_collections']['institution_lending_requests']['sha256'] and all(t['current_matches_committed_expiry_effect'] for t in transitions)
        report['original_requests_projected_sha256']=digest(projected)
        report['original_events_equal']=digest(db.events.find({}))==baseline['communication_state']['events']['sha256']
        report['original_event_seen_equal']=digest(db.event_user_state.find({}))==baseline['communication_state']['event_user_state']['sha256']
    report['source_classification']='Observed live activity is in existing TEST library/creator4, not task fixture IDs. One existing pending request expired through its original committed journal. Preserve these records; do not force old counts/states. A system overdue notice also appeared; its initiating process is not conclusively attributed.'
    report['no_live_announcement_content_exported']=True
    report['result']='PASS' if report['original_50_notifications_equal'] and report['announcements_not_task_fixtures'] and report['original_requests_projection_equal'] and report['original_events_equal'] and report['original_event_seen_equal'] and all(r['original_equal'] for r in report['original_append_only_journals'].values()) else 'PARTIAL'
    (ROOT/'reports/institution_v2p_concurrent_activity.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf8')
    return report

if __name__=='__main__':
    baseline=json.loads((ROOT/'reports/institution_v2p_baseline.json').read_text(encoding='utf8'))
    report=capture(baseline)
    print(json.dumps({'result':report['result'],'original_notices_equal':report['original_50_notifications_equal'],'request_projection_equal':report['original_requests_projection_equal'],'new_announcements':len(report['concurrent_announcements_metadata']),'current_notifications':report['current_notification_count']}))
