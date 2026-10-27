"""Run and report the independently approved five-flow mode supplement only."""
from datetime import datetime,timezone
import hashlib,json,os
from pathlib import Path
import subprocess,sys

ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run():
    target=R/'search_v2c_c5a_native_modes_attempt1';target.mkdir(exist_ok=False)
    env=os.environ.copy()
    for key in ['LUMINAR_C4_REPORT_DIR','LUMINAR_C3_REPORT_DIR','LUMINAR_C2_REPORT_DIR','LUMINAR_SECURITY_REPORT_DIR','LUMINAR_C5A_NATIVE_REPORT_DIR']:env[key]=str(target)
    env['LUMINAR_SESSION_DB']=str(target/'search_v2c_c5a_login_sessions.sqlite')
    env['PYTHONPATH']=str(ROOT)+os.pathsep+str(ROOT/'tests/institution_v2g')+os.pathsep+env.get('PYTHONPATH','')
    command=[sys.executable,'-m','pytest','-q','-x','tests/institution_v2g/test_query_v2c_c5a_native_modes.py','--tb=short','--junitxml='+str(target/'search_v2c_c5a_native_modes.xml')]
    old={str(p.relative_to(ROOT)):sha(p) for p in R.rglob('*') if p.is_file() and ('search_v2c_c4' in p.name or ('search_v2c_c5' in p.name and 'search_v2c_c5a' not in p.name))}
    meta={'version':'C5A-native-mode-supplement-v1','started_at':datetime.now(timezone.utc).isoformat(),'command':command,
      'harness_sha256':sha(ROOT/'tests/institution_v2g/test_query_v2c_c5a_native_modes.py'),
      'main_harness_sha256':sha(ROOT/'tests/institution_v2g/test_query_v2c_c5a_native.py'),
      'environment_report_paths':{k:v for k,v in env.items() if k.startswith('LUMINAR_') and ('REPORT' in k or k=='LUMINAR_SESSION_DB')},
      'historical_before':old,'calibration_parser_evaluations':0,'heldout_access':False,'parser_core_credit':0}
    with (target/'search_v2c_c5a_native_modes.log').open('w',encoding='utf8') as log:result=subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    meta.update(exit_code=result.returncode,completed_at=datetime.now(timezone.utc).isoformat(),historical_changed=[p for p,h in old.items() if sha(ROOT/p)!=h])
    (target/'search_v2c_c5a_native_modes_run.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf8')
    raw=target/'search_v2c_c5a_observations.jsonl'
    rows=[json.loads(x) for x in raw.read_text().splitlines()] if raw.exists() else []
    output={'version':'C5A-native-mode-supplement-v1','status':'PASS' if result.returncode==0 and len(rows)==5 and all(r['result']=='PASS' for r in rows) else 'PARTIAL',
      'supplemental_native_sequences':len(rows),'main_native_sequences':264,'disjoint_from_main_counts':True,
      'scope_count':len({r['scope'] for r in rows}),'explicit_EXACT_searches':len(rows),'SMART_genuine_correction_issuances':sum(len(r.get('issuances',[])) for r in rows),
      'native_api_boundaries':sum(len(r['boundaries']) for r in rows),'original_wording_retention':sum(r.get('exact_context_preserved_after_smart_resolution',False) for r in rows),
      'parser_calibration_core_credit':0,'calibration_parser_evaluations':0,'heldout_access':False,
      'raw_file':str(raw.relative_to(ROOT)),'raw_sha256':sha(raw) if raw.exists() else None,'harness_sha256':meta['harness_sha256'],
      'main_harness_unchanged':meta['main_harness_sha256']==json.loads((R/'search_v2c_c5a_native_attempt3/search_v2c_c5a_run.json').read_text())['harness_sha256'],
      'historical_changed':meta['historical_changed'],'cases':[{'case_id':r['case_id'],'scope':r['scope'],'result':r['result'],'EXACT_session_id':r['mode_steps'][0]['session_id'] if r.get('mode_steps') else None,'SMART_issued_id':r.get('issuances',[{}])[0].get('pending',{}).get('_id'),'statuses':[b['status'] for b in r['boundaries']]} for r in rows]}
    (R/'search_v2c_c5a_native_modes_results.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf8')
    print(json.dumps(output,indent=2));sys.exit(result.returncode)
if __name__=='__main__':run()
