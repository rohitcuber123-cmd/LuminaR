"""Actual-model protected-secret rollout/rotation/disabled rollback in one disposable DB."""
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.institution_v2m_fixture import AuthMongo,provision,seed_database,provision_unauthorized,rotate_writer
from scripts.institution_v2m_secrets import protect,command
from backend.services.library_worker_telemetry import COLLECTION,SLOT,digest,TelemetryError
from backend.services.library_worker_observer import Configuration,RestrictedWriter
from pymongo import MongoClient
from pymongo.errors import OperationFailure


def main():
    report={'scope':'Protected-secret authenticated deployment fixture only; no production enablement/credentials/ACL changes.',
        'phases':[],'secret_storage':[],'rollout':'IN_PROGRESS','rollback':'IN_PROGRESS',
        'production_equivalence':'Tenant fixture151 books; actual native class/JWT router/models, not the full5M global Search service or approved service-account deployment.'}
    out=ROOT/'reports/institution_v2m_rollout_validation.json'
    def save():out.write_text(json.dumps(report,indent=2),encoding='utf8')
    with AuthMongo() as s:
        seed_database(s);provision(s);provision_unauthorized(s)
        writer_path=s.root/'writer-secret/writer.clixml';reader_path=s.root/'reader-secret/reader.clixml'
        for label,path,secret in [('writer',writer_path,s.telemetry_uri),('reader',reader_path,s.reader_uri)]:
            report['secret_storage'].append({'purpose':label,**protect(s.root,path,secret)})
        base={**os.environ,'MONGO_URI':s.writer_uri,'MONGO_DB_NAME':s.database,'LIBRARY_INTELLIGENCE_ROOT':str(s.artifact_root),
            'LUMINAR_V2M_ISOLATED_CHILD':'1','LUMINAR_V2M_BOOK_COUNT':'151'}
        for name in ['LUMINAR_WORKER_TELEMETRY_ENABLED','LUMINAR_WORKER_TELEMETRY_MONGO_URI','LUMINAR_OPERATOR_MONGO_URI',
                     'V2M_TELEMETRY_URI','V2M_READER_URI','LUMINAR_V2M_BASELINE_NATIVE','LUMINAR_V2M_OBSERVER_CRASH']:
            base.pop(name,None)
        def phase(name,enabled,scenario='benchmark',secret=writer_path,repetitions=3):
            path=ROOT/f'reports/institution_v2m_native_{name}.json';at=time.perf_counter()
            payload={'fixture_root':str(s.root),'secret_path':str(secret),'database':s.database,'python':sys.executable,
                'script':str(ROOT/'scripts/institution_v2m_native_child.py'),'scenario':scenario,'output':str(path),
                'enabled':enabled,'repetitions':repetitions}
            with path.with_suffix('.log').open('w',encoding='utf8') as log:
                p=subprocess.run(command('native'),input=json.dumps(payload),env=base,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,text=True,timeout=240)
            value=json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
            report['phases'].append({'name':name,'enabled':enabled,'exit':p.returncode,'seconds':time.perf_counter()-at,'evidence':path.name});save()
            assert p.returncode==0,'Owned encrypted-secret native phase failed; inspect its sanitized2M log'
            assert value['worker_thread_ended'] and value['observer_thread_ended']
            assert all(b['state']=='SUCCEEDED' and b['pointer_ack_match'] for b in value.get('builds',[]))
            return value
        def snapshot():
            return {'jobs':digest(list(s.db.institution_intelligence_jobs.find({}))),
                'targets':digest(list(s.db.institution_intelligence_targets.find({}))),
                'locks':digest(list(s.db.institution_locks.find({}))),
                'generations':digest(list(s.db.institution_intelligence_generations.find({}))),
                'files':{p.relative_to(s.artifact_root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in s.artifact_root.rglob('*') if p.is_file()}}
        before=phase('disabled_before',False)
        assert before['observer_final_state']=='DISABLED' and s.db[COLLECTION].find_one({'_id':SLOT})['epoch']==0
        enabled=phase('enabled_rollout',True)
        assert enabled['idle']['pulse_seq']>=3 and enabled['observer_final_state'] in ['STOPPED','CLOSED']
        report['rollout']='PASS'
        lib=enabled['builds'][0]['library_id'];report['operator_cli']=[]
        for fmt in ['json','text']:
            payload={'fixture_root':str(s.root),'secret_path':str(reader_path),'database':s.database,'python':sys.executable,
                'script':str(ROOT/'scripts/diagnose_worker_telemetry.py'),'library_id':lib,'format':fmt}
            p=subprocess.run(command('operator'),input=json.dumps(payload),env=base,cwd=ROOT,capture_output=True,text=True,timeout=20)
            assert p.returncode==0,'Protected operator credential invocation failed'
            assert s.reader_uri not in p.stdout+p.stderr and s.read_password not in p.stdout+p.stderr
            report['operator_cli'].append({'format':fmt,'exit':p.returncode,'bytes':len(p.stdout.encode()),'output':p.stdout.strip()})
        protected=snapshot();old_epoch=s.db[COLLECTION].find_one({'_id':SLOT})['epoch']
        rotated_uri=rotate_writer(s);replacement=s.root/'writer-rotated/replacement.clixml'
        report['secret_storage'].append({'purpose':'rotated_writer',**protect(s.root,replacement,rotated_uri)})
        s.db.command('dropUser','fixture_telemetry')
        try:RestrictedWriter(Configuration(s.database,s.telemetry_uri),'tenant-00000000-0000-0000-0000-000000000001')
        except TelemetryError:report['old_credential_fresh_auth_rejected']=True
        else:raise AssertionError('Revoked old writer was accepted')
        assert snapshot()==protected,'Credential replacement itself changed native data/artifacts'
        rotated=phase('rotated_writer',True,secret=replacement)
        new_epoch=s.db[COLLECTION].find_one({'_id':SLOT})['epoch'];assert new_epoch>old_epoch
        report['rotation']={'old_fresh_auth_rejected':True,'new_principal_authenticated':True,'new_epoch':new_epoch,'old_epoch':old_epoch,
            'instance_rotated':enabled['instance_ref']!=rotated['instance_ref'],'native_data_unchanged_by_credential_operations':True}
        protected=snapshot();slot_before=s.db[COLLECTION].find_one({'_id':SLOT})
        old_rows={name:list(s.db['institution_intelligence_'+name].find({})) for name in ['jobs','targets','generations']}
        idle=phase('rollback_restart_only',False,'restart',secret=replacement,repetitions=1)
        assert snapshot()==protected and s.db[COLLECTION].find_one({'_id':SLOT})==slot_before
        rollback=phase('disabled_after_rollback',False,secret=replacement)
        for name,rows in old_rows.items():
            assert all(s.db['institution_intelligence_'+name].find_one({'_id':row['_id']})==row for row in rows),'A retained native record changed during disabled manual builds'
        retained=all((s.artifact_root/p).is_file() and hashlib.sha256((s.artifact_root/p).read_bytes()).hexdigest()==h for p,h in protected['files'].items())
        assert retained and rollback['observer_final_state']=='DISABLED' and s.db[COLLECTION].find_one({'_id':SLOT})==slot_before
        report['rollback']='PASS';report['rollback_evidence']={'disable_restart_native_data_unchanged':True,'old_artifact_bytes_retained':retained,
            'retained_jobs_targets_generations_unchanged':True,
            'telemetry_document_unchanged_while_disabled':True,'native_builds_after_rollback':rollback['builds'],
            'retained_targets_validated':len(rollback['retained_targets_validated']),'no_cancel_recover_unlock_delete_or_rewrite':True}
        c=MongoClient(s.reader_uri)
        try:
            try:c[s.database][COLLECTION].update_one({'_id':SLOT},{'$set':{'epoch':999}})
            except OperationFailure as e:report['operator_write_denied_code']=e.code
        finally:c.close()
        assert report.get('operator_write_denied_code')==13;save()
    report['owned_fixture_removed']=True;report['completed_at']=datetime.now(timezone.utc).isoformat();save()
    print(json.dumps({'rollout':report['rollout'],'rollback':report['rollback'],'phases':len(report['phases']),'rotation':'PASS'}))


if __name__=='__main__':main()
