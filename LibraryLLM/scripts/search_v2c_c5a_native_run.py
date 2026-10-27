"""Run only C5A native integration; retain raw attempts and never score corpus."""
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,os
from pathlib import Path
import subprocess,sys,tempfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reports'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(suffix,value):
    (R/('search_v2c_c5a_'+suffix+'.json')).write_text(json.dumps(value,indent=2,default=str)+'\n',encoding='utf8')
def run():
    tag=sys.argv[1] if len(sys.argv)>1 else 'attempt1'
    security=len(sys.argv)>2 and sys.argv[2]=='security'
    assert tag.replace('_','').isalnum()
    target=R/('search_v2c_c5a_'+('security_' if security else 'native_')+tag)
    target.mkdir(exist_ok=False)
    env=os.environ.copy()
    for key in ['LUMINAR_C4_REPORT_DIR','LUMINAR_C3_REPORT_DIR','LUMINAR_C2_REPORT_DIR','LUMINAR_SECURITY_REPORT_DIR','LUMINAR_C5A_NATIVE_REPORT_DIR']:
        env[key]=str(target)
    env['LUMINAR_SESSION_DB']=str(target/'search_v2c_c5a_login_sessions.sqlite')
    staging=Path(tempfile.mkdtemp(prefix='search_v2c_c5a_security_')) if security else None
    if staging:env['LUMINAR_SECURITY_REPORT_DIR']=str(staging)
    env['PYTHONPATH']=str(ROOT)+os.pathsep+str(ROOT/'tests/institution_v2g')+os.pathsep+env.get('PYTHONPATH','')
    command=[sys.executable,'-m','pytest','-q','-x','tests/institution_v2g/test_query_v2c_c5a_'+('security' if security else 'native')+'.py','--tb=short','--junitxml='+str(target/'search_v2c_c5a_native.xml')]
    if len(sys.argv)>2 and sys.argv[2]=='remaining':command+=['-k','not test_ten_missing_correction_contexts and not test_reviewed_historical_native']
    historical={str(p.relative_to(ROOT)):sha(p) for p in R.rglob('*') if p.is_file() and ('search_v2c_c4' in p.name or ('search_v2c_c5' in p.name and 'search_v2c_c5a' not in p.name))}
    meta={'version':'C5A-native-harness-v2','attempt':tag,'started_at':datetime.now(timezone.utc).isoformat(),'command':command,
      'environment_report_paths':{k:v for k,v in env.items() if k.startswith('LUMINAR_') and 'REPORT' in k},
      'harness_sha256':sha(ROOT/'tests/institution_v2g/test_query_v2c_c5a_native.py'),'historical_hashes_before':historical,
      'calibration_parser_evaluations':0,'heldout_access':False,'production_index_builds':0,'fixture_hnsw_builds':0,'fixture_kg_builds':0}
    (target/'search_v2c_c5a_run.json').write_text(json.dumps(meta,indent=2)+'\n')
    with (target/'search_v2c_c5a_native.log').open('w',encoding='utf8') as out:
        result=subprocess.run(command,cwd=ROOT,env=env,stdout=out,stderr=subprocess.STDOUT)
    meta['exit_code']=result.returncode;meta['completed_at']=datetime.now(timezone.utc).isoformat()
    if staging:
        meta['accepted_report_staging']=str(staging)
        meta['accepted_reports']=[]
        for source in staging.glob('*.json'):
            output=target/('search_v2c_c5a_accepted_'+source.name.removeprefix('search_v2c_'))
            output.write_bytes(source.read_bytes())
            meta['accepted_reports'].append({'original_name':source.name,'c5a_copy':str(output),'sha256':sha(output)})
    meta['historical_hash_changes']=[p for p,h in historical.items() if sha(ROOT/p)!=h]
    (target/'search_v2c_c5a_run.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps({'attempt':tag,'exit_code':result.returncode,'historical_changed':meta['historical_hash_changes'],'raw_dir':str(target)}))
    sys.exit(result.returncode)
if __name__=='__main__':run()
