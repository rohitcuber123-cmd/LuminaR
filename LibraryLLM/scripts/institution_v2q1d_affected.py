from pathlib import Path
from uuid import uuid4
import os,json,subprocess,sys,hashlib,shutil
import xml.etree.ElementTree as ET
from pymongo import MongoClient
R=Path(__file__).resolve().parents[1];name='luminar_v2q1d_affected_'+uuid4().hex[:16];scope=(R/'.scratch/institution-v2q/final-continuation/affected'/name).resolve();scope.mkdir(parents=True)
env={**os.environ,'MONGO_URI':'mongodb://127.0.0.1:27017','MONGO_DB_NAME':name,'LUMINAR_MONGO_MODE':'DEVELOPMENT','JWT_SECRET_KEY':uuid4().hex,'LUMINAR_SESSION_DB':str(scope/'sessions.sqlite'),'NOTIFICATION_DUE_WORKER_ENABLED':'0','NOTIFICATION_OUTBOX_WORKER_ENABLED':'0'}
files=next(x['files'] for x in json.loads((R/'reports/institution_v2q_2q1_closure_backend.json').read_text()) if x['group']=='assistant');base=R/'reports/institution_v2q1d_affected_assistant'
try:
 with base.with_suffix('.log').open('w',encoding='utf8') as out:p=subprocess.run([sys.executable,'-m','pytest',*files,'-q','--junitxml='+str(base.with_suffix('.xml'))],cwd=R,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=900)
 cases=list(ET.parse(base.with_suffix('.xml')).iter('testcase'));failed=sum(any(c.tag in {'failure','error'} for c in x) for x in cases);skipped=sum(any(c.tag=='skipped' for c in x) for x in cases)
 base.with_suffix('.json').write_text(json.dumps({'passed':len(cases)-failed-skipped,'failed':failed,'skipped':skipped,'exit':p.returncode,'application_source_sha256':hashlib.sha256((R/'assistant/qwen.py').read_bytes()).hexdigest(),'reason':'Repeat all439 affected assistant tests after final reference-boundary refinement; no double-counting in full-suite totals.'},indent=2));print(len(cases)-failed-skipped,failed,skipped)
finally:
 assert name.startswith('luminar_v2q1d_affected_') and scope.is_relative_to((R/'.scratch/institution-v2q/final-continuation/affected').resolve())
 with MongoClient('mongodb://127.0.0.1:27017') as c:c.drop_database(name)
 shutil.rmtree(scope)
