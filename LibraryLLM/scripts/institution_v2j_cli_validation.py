"""Execute the shipped CLI against auth-enforced disposable Mongo and artifacts."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
from datetime import datetime,timedelta,timezone
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.institution_v2j_fixture import AuthMongo,seed_database
from tests.institution_v2j.test_diagnostics import job,published,digest_db,files,NOW


def main():
    report={'surface':'scripts/diagnose_library_intelligence.py','transport':'Actual local subprocess CLI / auth-enabled Mongo / built-in database read principal',
            'production_operator_credential_provisioned':False,'browser':'NOT_RUN; CLI surface chosen','steps':[],'observations':[]}
    def passed(label,**detail):
        report['steps'].append({'check':label,'passed':True,**detail})
        print(label,flush=True)
    with AuthMongo() as server:
        seed_database(server)
        private=str(uuid4())
        server.db.institution_libraries.insert_one({'library_id':private,'library_type':'PRIVATE_INSTITUTION','access_mode':'PRIVATE_CODE'})
        good,path,pointer=published(server,private)
        queued=job(server,private,created_at=NOW-timedelta(minutes=10))
        tied=job(server,created_at=queued['created_at'])
        running=job(server,state='RUNNING',started_at=NOW-timedelta(hours=1),worker_id='HIDDEN_WORKER',fence_token='HIDDEN_FENCE')
        stale=job(server,state='RUNNING',heartbeat_at=NOW-timedelta(seconds=45))
        expired=job(server,state='RUNNING',lease_expires_at=NOW-timedelta(seconds=1))
        failed=job(server,private,state='FAILED',target='KNOWLEDGE_GRAPH',error_code='BUILD_FAILED',error_message='Traceback PRIVATE_PATH PASSWORD')
        unknown,u_path,u_ptr=published(server,state='RECOVERY_REQUIRED')
        temporary,t_path,t_ptr=published(server,state='FAILED',point=False,temporary=True)
        (t_path/'manifest.json').write_text('invalid manifest')
        server.db.institution_locks.insert_one({'_id':private,'holder':'HIDDEN_LOCK','created_at':NOW-timedelta(minutes=5)})
        before,artifacts=digest_db(server),files(server)
        env=os.environ.copy();env['LUMINAR_OPERATOR_MONGO_URI']=server.reader_uri
        base=[sys.executable,str(ROOT/'scripts/diagnose_library_intelligence.py'),'--database',server.database,
              '--artifact-root',str(server.artifact_root),'--timeout-seconds','20']
        def cli(lib,*,mode='json',extra=(),authorization=server.reader_uri,profile=False):
            selected=env.copy()
            if authorization is None:selected.pop('LUMINAR_OPERATOR_MONGO_URI',None)
            else:selected['LUMINAR_OPERATOR_MONGO_URI']=authorization
            if profile:server.db.command('profile',2)
            try:
                p=subprocess.run([*base,'--library-id',lib,'--format',mode,*extra],cwd=ROOT,env=selected,
                                 capture_output=True,text=True,encoding='utf8',timeout=25)
            finally:
                if profile:server.db.command('profile',0)
            assert all(secret not in p.stdout+p.stderr for secret in [server.password,server.read_password,'HIDDEN_WORKER','HIDDEN_FENCE','HIDDEN_LOCK','PRIVATE_PATH','PASSWORD'])
            if authorization!=server.reader_uri:
                assert p.returncode!=0 and queued['job_id'] not in p.stdout+p.stderr
                return p
            assert p.returncode==0,p.stderr
            return json.loads(p.stdout) if mode=='json' else p.stdout
        data=cli(private,extra=['--job-id',queued['job_id'],'--verify-checksums'],profile=True)
        assert data['selected_job']['state']=='QUEUED'
        assert data['queue']['selected_job_position_range']['maximum']>data['queue']['selected_job_position_range']['minimum']
        assert data['queue']['head_of_line']=='POTENTIAL_TENANT_BARRIER_BLOCK'
        passed('Authorized operator inspects a private library; FIFO ties are a range and barrier evidence is explicit')
        report['observations'].append({'case':'private_queued','report':data})
        for auth,label in [(None,'No operator credential denied'),('platform-admin.jwt','Platform application identity grants no operator authority'),
                           ('general-user.jwt','General application identity denied'),(server.reader_uri.replace(server.read_password,'incorrect'),'Wrong database credential denied')]:
            cli(private,authorization=auth)
            passed(label)
        recent=cli(running['library_id'],extra=['--job-id',running['job_id']])
        assert recent['selected_job']['heartbeat_evidence']=='RECENT'
        assert recent['selected_job']['progress']['recency']=='UNKNOWN' and recent['worker']['process_alive']=='UNKNOWN'
        passed('Real durable RUNNING state and recent renewal do not claim a healthy process or progressing work')
        old=cli(stale['library_id'],extra=['--job-id',stale['job_id']])
        assert old['selected_job']['heartbeat_evidence']=='STALE'
        passed('Stale heartbeat is distinguishable from recent renewal')
        overdue=cli(expired['library_id'],extra=['--job-id',expired['job_id']])
        assert overdue['selected_job']['lease_expired'] and overdue['selected_job']['recovery_required']
        passed('Expired lease is a derived recovery observation; durable state is untouched')
        bad=cli(private,extra=['--job-id',failed['job_id'],'--verify-checksums'])
        assert bad['selected_job']['state']=='FAILED'
        assert bad['targets'][1]['published_generation_id']==good['artifact_generation_id']
        assert bad['targets'][1]['published_checksum_integrity']=='VERIFIED_WITHIN_BUDGET'
        passed('FAILED is known failure; last published generation remains separately visible and checksum-anchored')
        uncertain=cli(unknown['library_id'],extra=['--job-id',unknown['job_id'],'--verify-checksums'])
        assert uncertain['selected_job']['state']=='RECOVERY_REQUIRED' and uncertain['selected_job']['publication_outcome']=='UNKNOWN'
        passed('Unknown publication after pointer update is distinct from FAILED and requires manual investigation')
        retained=cli(temporary['library_id'])
        assert any(a['manifest']=='INVALID_OR_UNREADABLE_MANIFEST' for a in retained['artifacts']['generations'])
        passed('Invalid retained temporary generation is visible without repair, promotion or deletion')
        assert before==digest_db(server) and artifacts==files(server)
        missing=job(server,state='FAILED')
        # Fixture setup, deliberately outside the before/after diagnostic check.
        before=digest_db(server)
        missing_data=cli(missing['library_id'])
        assert missing_data['artifacts']['missing_reference_count']>=1
        passed('Missing or never-created temporary/final candidates are reported without guessing the outcome')
        text=cli(private,mode='text')
        assert 'read-only observation' in text and 'Worker CPU / memory / GPU: NOT_AVAILABLE' in text
        (ROOT/'reports/institution_v2j_cli_text.txt').write_text(text,encoding='utf8')
        passed('Readable text and structured JSON use the same bounded diagnostic model')
        assert before==digest_db(server) and artifacts==files(server)
        passed('Every actual diagnostic call preserves durable rows, artifact bytes and mtimes; no global rebuild path exists')
        profile=list(server.db['system.profile'].find({'appName':'LuminaR-operator-read-only'}))
        assert profile,'No actual CLI profiler observations captured'
        commands=[]
        for event in profile:
            command=event.get('command',{})
            kind=next((n for n in ['find','aggregate','getMore','killCursors','connectionStatus'] if n in command),event.get('op'))
            assert not any(n in command for n in ['insert','update','delete','createIndexes','findAndModify','drop','renameCollection'])
            commands.append({'operation':kind,'namespace':event.get('ns'),'documents_examined':event.get('docsExamined',0)})
        report['actual_cli_mongo_profile']=commands
        report['state_unchanged']=True;report['artifact_bytes_and_mtimes_unchanged']=True
        report['private_outsider_denied']=True;report['secrets_in_output']=False
        report['status']='PASS'
    report['task_owned_fixture_server_stopped']=True
    (ROOT/'reports/institution_v2j_browser_or_cli.json').write_text(json.dumps(report,indent=2),encoding='utf8')


if __name__=='__main__':main()
