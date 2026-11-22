"""Reuse accepted product group inventories in isolated independent processes."""
from pathlib import Path
from uuid import uuid4
import json,os,secrets,shutil,subprocess,sys,time
import xml.etree.ElementTree as ET
from pymongo import MongoClient
ROOT=Path(__file__).resolve().parents[1]

def main():
    name='luminar_v2q1c_target_'+uuid4().hex[:20]
    scope=(ROOT/'.scratch/institution-v2q/final-continuation/targeted'/name).resolve()
    assert scope.is_relative_to((ROOT/'.scratch/institution-v2q/final-continuation/targeted').resolve())
    scope.mkdir(parents=True,exist_ok=False)
    env={**os.environ,'MONGO_URI':'mongodb://127.0.0.1:27017','MONGO_DB_NAME':name,
        'LUMINAR_MONGO_MODE':'DEVELOPMENT','JWT_SECRET_KEY':secrets.token_urlsafe(32),
        'LUMINAR_SESSION_DB':str(scope/'sessions.sqlite'),
        'NOTIFICATION_DUE_WORKER_ENABLED':'0','NOTIFICATION_OUTBOX_WORKER_ENABLED':'0'}
    inventory=json.loads((ROOT/'reports/institution_v2q_2q1_closure_backend.json').read_text())
    selected={'assistant','security','institution_v2j','institution_v2o2','institution_v2q_ai'}
    protected={p:(ROOT/'reports'/p).read_bytes() for p in ['institution_v2e_backend_benchmark.json','full_product_generated_test_plan.json']}
    results=[]
    try:
        for group in inventory:
            if group['group'] not in selected:continue
            label=group['group'];base=ROOT/f'reports/institution_v2q1d_targeted_{label}'
            start=time.perf_counter()
            with base.with_suffix('.log').open('w',encoding='utf8') as out:
                p=subprocess.run([sys.executable,'-m','pytest',*group['files'],'-q','--junitxml='+str(base.with_suffix('.xml'))],
                    cwd=ROOT,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=900)
            cases=list(ET.parse(base.with_suffix('.xml')).iter('testcase'))
            failed=sum(any(child.tag in ('failure','error') for child in case) for case in cases)
            skipped=sum(any(child.tag=='skipped' for child in case) for case in cases)
            row={'group':label,'exit':p.returncode,'passed':len(cases)-failed-skipped,'failed':failed,'skipped':skipped,
                 'seconds':round(time.perf_counter()-start,3),'files':group['files']}
            results.append(row)
            (ROOT/'reports/institution_v2q1d_targeted.json').write_text(json.dumps(results,indent=2),encoding='utf8')
            print(json.dumps({k:v for k,v in row.items() if k!='files'}),flush=True)
    finally:
        for filename,payload in protected.items():(ROOT/'reports'/filename).write_bytes(payload)
        assert name.startswith('luminar_v2q1c_target_') and name!='luminar_library'
        with MongoClient('mongodb://127.0.0.1:27017') as client:client.drop_database(name)
        assert scope.parent==(ROOT/'.scratch/institution-v2q/final-continuation/targeted').resolve()
        shutil.rmtree(scope)
        (ROOT/'reports/institution_v2q1d_targeted_isolation.json').write_text(json.dumps({
            'owned_fallback_database':name,'removed':True,'owned_session_directory_removed':True,
            'existing_test_bodies_unchanged':True}),encoding='utf8')
    return int(any(row['exit'] for row in results))

if __name__=='__main__':raise SystemExit(main())
