"""Complete Assistant candidate suite with a task-owned authenticated Mongo."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.institution_v2o2_fixture import AuthMongo,provision_application


def main():
    R=ROOT/'reports';CAND=ROOT/'.scratch/institution-v2o2/candidate/LibraryLLM'
    for ext in ('xml','log'):
        old=R/f'institution_v2o2_candidate_assistant.{ext}'
        preserved=R/f'institution_v2o2_candidate_assistant_initial.{ext}'
        if old.exists() and not preserved.exists():shutil.copyfile(old,preserved)
    xml=R/'institution_v2o2_candidate_assistant_owned.xml'
    with AuthMongo() as server:
        provision_application(server)
        env=os.environ.copy();env.update({'MONGO_URI':server.app_uri,'MONGO_DB_NAME':server.database,'LUMINAR_MONGO_MODE':'DEVELOPMENT','PYTHONPATH':str(CAND),
                                       'NOTIFICATION_DUE_WORKER_ENABLED':'0','NOTIFICATION_OUTBOX_WORKER_ENABLED':'0'})
        start=time.perf_counter()
        with xml.with_suffix('.log').open('w',encoding='utf8') as out:
            p=subprocess.run([sys.executable,'-m','pytest','tests/test_assistant_backend.py','-q','--junitxml='+str(xml)],cwd=CAND,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=300)
        cases=list(ET.parse(xml).iter('testcase'));failed=sum(any(n.tag in {'failure','error'} for n in c) for c in cases);skip=sum(any(n.tag=='skipped' for n in c) for c in cases)
        result={'group':'assistant','exit':p.returncode,'passed':len(cases)-failed-skip,'failed':failed,'skipped':skip,'seconds':time.perf_counter()-start,'xml':xml.name,
                'fixture':'Task-owned separate authenticated mongod; scoped application role; no production data or credentials. Owned server closed after test.',
                'initial_fixture_problem':'Initial candidate run deliberately had no database at port 1; three module-import index operations failed. Full unchanged suite rerun with owned service; no assertion altered.'}
    (R/'institution_v2o2_candidate_assistant_owned.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
    return p.returncode


if __name__=='__main__':raise SystemExit(main())
