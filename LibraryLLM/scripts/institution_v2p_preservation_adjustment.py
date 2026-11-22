"""Remove only the proven new empty schema artifact; retain valid user notices."""
from pathlib import Path
from datetime import datetime,timezone
import json
from dotenv import dotenv_values
from pymongo import MongoClient
from scripts.institution_v2i_baseline import digest
ROOT=Path(__file__).resolve().parents[1]

def main():
    baseline=json.loads((ROOT/'reports/institution_v2p_baseline.json').read_text(encoding='utf8'))
    assert 'institution_announcements' not in baseline['mongo_indexes']
    env=dotenv_values(ROOT/'.env')
    with MongoClient(env['MONGO_URI']) as client:
        db=client['luminar_library']
        expected={'_id_','announcement_id_1','library_id_1_created_by_user_id_1_request_id_1',
            'library_id_1_status_1_published_at_-1_announcement_id_1','delivery.state_1_delivery.next_attempt_at_1_published_at_1'}
        indexes=list(db.institution_announcements.list_indexes())
        assert {i['name'] for i in indexes}==expected
        assert db.institution_announcements.count_documents({})==0
        # Collection did not exist before this task; it has no user records and
        # exactly the new feature's index set. Do not delete any other namespace.
        db.drop_collection('institution_announcements')
        cutoff=datetime.fromisoformat(baseline['captured_at'])
        added=list(db.notifications.find({'created_at':{'$gte':cutoff}}))
        assert len(added)==1 and added[0]['type']=='OVERDUE' and added[0]['source']=='SYSTEM' and added[0]['scope']=='GLOBAL'
        old=list(db.notifications.find({'notification_id':{'$nin':[r['notification_id'] for r in added]}}))
        assert len(old)==baseline['communication_state']['notifications']['count']
        assert digest(old)==baseline['communication_state']['notifications']['sha256']
        report={'captured_at':datetime.now(timezone.utc).isoformat(),'empty_task_schema_removed':True,'removed_collection':'institution_announcements',
            'verified_empty':True,'absent_from_baseline':True,'exact_new_index_set_verified':True,
            'retained_system_notice':{'notification_id':added[0]['notification_id'],'type':added[0]['type'],'source':added[0]['source'],'scope':added[0]['scope'],'created_at':added[0]['created_at']},
            'original_50_notifications_byte_semantics_equal':True,'original_50_sha256':digest(old),
            'notice_attribution':'Observed in test window. Provenance is an existing overdue reminder, consistent with legacy lifespan worker startup; attribution is not conclusively proven. It is valid user history and was retained.',
            'actual_reminder_deleted':False,'production_auth_changed':False,'production_telemetry_enabled':False,
            'scope_note':'Default database remains UNKNOWN classification. No user/account/loan/event records were deleted or changed by this cleanup. New runner isolates legacy fallback startup; no frozen assertion altered.'}
    (ROOT/'reports/institution_v2p_preservation_adjustment.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf8')
    print(json.dumps(report,default=str))
if __name__=='__main__':main()
