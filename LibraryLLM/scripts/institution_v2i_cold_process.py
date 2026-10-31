"""Fresh application-process reads, with explicitly warm/unspecified OS/Mongo caches."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.institution_v2i_benchmark import seed,db,mongo,repo,inventory,store,DBNAME,stats

CHILD='''import importlib.util,json,sys,time
from pathlib import Path
from backend.services import library_intelligence_service as current
root=Path.cwd()
if sys.argv[1]=='before':
    spec=importlib.util.spec_from_file_location('original',root/'.scratch/institution-v2i/before/backend/services/library_intelligence_service.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
else:module=current
a,c=time.perf_counter(),time.process_time()
v=module.status(sys.argv[2],{'sub':'1'})
print(json.dumps({'status_ms':(time.perf_counter()-a)*1000,'cpu_ms':(time.process_time()-c)*1000,'books':v['eligible_book_count'],'states':[v['search']['status'],v['kg']['status']]}))
'''


def main():
    result={'isolation':'Unique disposable real Mongo and synthetic checksum-valid artifact fixtures',
            'database':DBNAME,'samples_per_size_version':3,'cases':[],
            'cold_definition':'New Python/application process per sample, first status call. subprocess_wall_ms includes imports/startup; status_ms excludes imports. No OS page-cache or Mongo-cache flush; not physical cold-disk or cold-server qualification.'}
    with tempfile.TemporaryDirectory(prefix='luminar-v2i-cold-') as tmp:
        os.environ['LIBRARY_INTELLIGENCE_ROOT']=tmp
        try:
            repo.ensure_indexes();inventory.ensure_indexes();store.initialize()
            db.users.insert_one({'user_id':1,'email':'cold-fixture@example.com','is_active':True,'is_email_verified':True,'role':'GENERAL_USER'})
            for n in [0,1,10,100,1000,10000,50000]:
                lib=seed(n,published=n!=0)
                pairs={'before':[],'after':[]}
                for repeat in range(3):
                    for label in (['before','after'] if repeat%2 else ['after','before']):
                        at=time.perf_counter()
                        child=subprocess.run([sys.executable,'-c',CHILD,label,lib],cwd=ROOT,env=os.environ.copy(),capture_output=True,text=True,timeout=90)
                        assert child.returncode==0,child.stderr[-1000:]
                        value=json.loads(child.stdout.strip().splitlines()[-1])
                        value['subprocess_wall_ms']=(time.perf_counter()-at)*1000
                        assert value['books']==n and value['states']==(['NOT_BUILT']*2 if n==0 else ['READY']*2)
                        pairs[label].append(value)
                for label,values in pairs.items():
                    result['cases'].append({'eligible_books':n,'version':label,'samples':values,
                                            'first_status_ms':stats([v['status_ms'] for v in values]),
                                            'subprocess_wall_ms':stats([v['subprocess_wall_ms'] for v in values])})
                print(n,round(result['cases'][-2]['first_status_ms']['median'],2),round(result['cases'][-1]['first_status_ms']['median'],2),flush=True)
        finally:
            assert db.name==DBNAME and DBNAME.startswith('luminar_institution_v2i_benchmark_')
            mongo.drop_database(DBNAME)
            result['disposable_database_removed']=True
    result['owned_temporary_artifacts_removed']=True
    (ROOT/'reports/institution_v2i_cold_process.json').write_text(json.dumps(result,indent=2),encoding='utf8')


if __name__=='__main__':main()
