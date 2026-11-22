"""Measured standalone-Mongo fixture latency/operation counts; never production."""
import os, sys, json, time, statistics
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
name='luminar_institution_v2p_perf_'+uuid4().hex
os.environ.update(MONGO_URI='mongodb://127.0.0.1:27017',MONGO_DB_NAME=name,JWT_SECRET_KEY='part2p-disposable-performance-key',NOTIFICATION_DUE_WORKER_ENABLED='0',NOTIFICATION_OUTBOX_WORKER_ENABLED='0')
from pymongo import monitoring
class Commands(monitoring.CommandListener):
    def __init__(self):self.counts={}
    def started(self,event):self.counts[event.command_name]=self.counts.get(event.command_name,0)+1
    def succeeded(self,event):pass
    def failed(self,event):pass
counter=Commands();monitoring.register(counter)
from backend.database.mongodb import db,client
from backend.services import institution_repository as ir,notification_service as ns,library_announcement_service as service
from backend.schemas.library_announcements import DraftCreate,Revision

def measure(fn):
    counter.counts={};start=time.perf_counter();value=fn()
    return value,{'milliseconds':round((time.perf_counter()-start)*1000,3),'mongo_commands':dict(counter.counts)}

def main():
    report={'database':name,'kind':'Disposable real local standalone Mongo; application service calls, no production throughput claim','sizes':[]}
    try:
        for module in [ir,ns,service]:module.ensure_indexes()
        for size in [20,200,2000]:
            lib=str(uuid4())
            db.institution_libraries.insert_one({'library_id':lib,'slug_normalized':lib,'name':'Performance fixture','status':'ACTIVE','owner_user_id':1,'library_type':'PRIVATE_INSTITUTION','access_mode':'PRIVATE_CODE'})
            for coll in [db.users]:coll.delete_many({})
            db.users.insert_many([{'user_id':uid,'email':f'perf-{uid}@example.com','role':'GENERAL_USER','is_active':True,'is_email_verified':True} for uid in range(1,size+1)])
            db.institution_memberships.insert_many([{'membership_id':str(uuid4()),'library_id':lib,'user_id':uid,'role':'ADMIN' if uid==1 else 'GENERAL_USER','status':'ACTIVE'} for uid in range(1,size+1)])
            row=service.create(lib,{'sub':'1'},DraftCreate(title='Performance announcement',body='Measured fixture message.',request_id=uuid4()))
            published,publish=measure(lambda:service.publish(lib,row['announcement_id'],{'sub':'1'},Revision(revision=0)))
            def fanout():
                batches=[]
                for _ in range((size+99)//100):batches.append(service.deliver_one(lib,row['announcement_id'],100))
                return batches
            batches,delivery=measure(fanout)
            lists=[measure(lambda:service.listing(lib,{'sub':'2'}))[1] for _ in range(5)]
            counts=[measure(lambda:ns.unread(2))[1] for _ in range(5)]
            inbox=[measure(lambda:ns.list_own(2))[1] for _ in range(5)]
            assert db.notifications.count_documents({'library_id':lib})==size and all(not b['failed'] for b in batches)
            report['sizes'].append({'active_recipients':size,'publish':publish,'fanout':delivery,'batch_size':100,'batches':len(batches),
                'list_samples':lists,'unread_samples':counts,'inbox_samples':inbox,'notification_count':size,
                'list_median_ms':statistics.median(x['milliseconds'] for x in lists),'unread_median_ms':statistics.median(x['milliseconds'] for x in counts),'inbox_median_ms':statistics.median(x['milliseconds'] for x in inbox)})
            print(json.dumps({'recipients':size,'publish_ms':publish['milliseconds'],'fanout_ms':delivery['milliseconds']}),flush=True)
        report['result']='PASS'
    except Exception as error:
        report.update(result='FAIL',error=type(error).__name__);raise
    finally:
        assert db.name==name and name.startswith('luminar_institution_v2p_perf_');client.drop_database(name)
        report['owned_database_removed']=True
        (ROOT/'reports/institution_v2p_performance.json').write_text(json.dumps(report,indent=2),encoding='utf8')
if __name__=='__main__':main()
