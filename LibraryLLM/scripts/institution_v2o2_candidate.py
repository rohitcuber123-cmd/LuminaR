"""Copy a bounded candidate checkout; apply proposals only in its own Git root."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
OWN=ROOT/'.scratch/institution-v2o2'
PARENT=OWN/'candidate'
CAND=PARENT/'LibraryLLM'
R=ROOT/'reports'


def setup():
    assert PARENT.resolve().is_relative_to(OWN.resolve())
    assert not CAND.exists(), 'Refusing to overwrite an existing candidate'
    CAND.mkdir(parents=True)
    baseline=json.loads((R/'institution_v2o2_baseline.json').read_text())
    names=set(baseline['source_sha256'])
    names.update(p.relative_to(ROOT).as_posix() for pattern in ('scripts/institution_v2o2*.py','tests/institution_v2o2/**/*') for p in ROOT.glob(pattern) if p.is_file() and '__pycache__' not in str(p))
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'scratch').rglob('*.py'))
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'tests').rglob('*') if p.is_file() and p.suffix in {'.txt','.json','.cjs'})
    names.add('pytest.ini')
    names.update(p.relative_to(ROOT).as_posix() for p in (R/'assistant_backend_baseline').glob('*') if p.is_file())
    # Frozen review inputs used by J/L and fixture role discovery; not big research datasets.
    names.update(p.relative_to(ROOT).as_posix() for prefix in ('institution_v2j_','institution_v2l_','institution_v2i_','institution_v2n_') for p in R.glob(prefix+'*.json') if p.stat().st_size<10*1024*1024)
    for n in sorted(names):
        dst=CAND/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,dst)
    # Trusted compiler is read-only external tooling; no application/node_modules
    # junction and no production data/.env/credentials copied into the candidate.
    compiler=ROOT/'frontend/node_modules/typescript'
    subprocess.run(['git','init','--quiet',str(PARENT)],check=True)
    assert subprocess.check_output(['git','rev-parse','--show-toplevel'],cwd=PARENT,text=True).strip().replace('\\','/').lower()==str(PARENT).replace('\\','/').lower()
    for label in ('j','rag'):
        patch=R/f'institution_v2o2_{label}_approval.patch'
        subprocess.run(['git','apply','--check','--ignore-space-change',str(patch)],cwd=PARENT,check=True)
        subprocess.run(['git','apply','--ignore-space-change',str(patch)],cwd=PARENT,check=True)
    # The helper's compiler_root defaults to this checkout. Copy only TypeScript
    # compiler, not application dependencies or a shared writable node_modules.
    shutil.copytree(compiler,CAND/'frontend/node_modules/typescript',ignore=shutil.ignore_patterns('node_modules'))
    copied={n:hashlib.sha256((CAND/n).read_bytes()).hexdigest() for n in names}
    (R/'institution_v2o2_candidate_setup.json').write_text(json.dumps({'root':str(CAND),'isolated_git_root':str(PARENT),'copied_files':len(copied),
        'patches_applied_to_candidate_only':True,'source_manifest':copied,'production_env_or_data_copied':False},indent=2))
    print(json.dumps({'candidate':str(CAND),'copied_files':len(copied)}))


def run():
    # These are the actual full J/assistant/protocol/authority suites, unchanged
    # except the exact proposed assertions. Each fixture group gets a process.
    groups={'j':['tests/institution_v2j'],'assistant':['tests/test_assistant_backend.py'],
            'tenant_authority':['tests/institution_v2b'],
            'native_search_kg':['tests/institution_v2g/test_intelligence.py','tests/institution_v2g/test_validation_recovery.py','tests/institution_v2g/test_private_isolation.py','tests/institution_v2g/test_search_runtime.py'],
            'native_protocol':['tests/institution_v2l']}
    rows=[]
    env={k:v for k,v in os.environ.items() if k not in {'MONGO_URI','MONGO_DB_NAME','LUMINAR_OPERATOR_MONGO_URI','LUMINAR_WORKER_TELEMETRY_MONGO_URI','LUMINAR_WORKER_TELEMETRY_ENABLED'}}
    env['PYTHONPATH']=str(CAND)
    # Imports that precede owned fixtures must never use the production Mongo.
    env.update({'MONGO_URI':'mongodb://127.0.0.1:1','MONGO_DB_NAME':'luminar_v2o2_unavailable_guard','LUMINAR_MONGO_MODE':'DEVELOPMENT'})
    for name,targets in groups.items():
        xml=R/f'institution_v2o2_candidate_{name}.xml';start=time.perf_counter()
        with xml.with_suffix('.log').open('w',encoding='utf8') as out:
            p=subprocess.run([sys.executable,'-m','pytest',*targets,'-q','--junitxml='+str(xml)],cwd=CAND,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=900)
        cases=list(ET.parse(xml).iter('testcase'));failed=sum(any(n.tag in {'failure','error'} for n in c) for c in cases);skip=sum(any(n.tag=='skipped' for n in c) for c in cases)
        rows.append({'group':name,'exit':p.returncode,'passed':len(cases)-failed-skip,'failed':failed,'skipped':skip,'seconds':time.perf_counter()-start,'xml':xml.name,'targets':targets})
        (R/'institution_v2o2_candidate_backend.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows[-1]),flush=True)
    return any(row['exit'] for row in rows)


def refresh():
    assert CAND.resolve().is_relative_to(OWN.resolve())
    assert Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],cwd=PARENT,text=True).strip()).resolve()==PARENT.resolve()
    for n in ('tests/institution_v2j/test_diagnostics.py','tests/test_assistant_backend.py'):
        shutil.copyfile(ROOT/n,CAND/n)
    for n in ('staff_boundary_v2o2.py','staff_boundary_v2o2.cjs','staff_boundary_v2o2.json','rag_grounding_v2o2.py'):
        path=CAND/'tests/contracts'/n
        assert path.resolve().is_relative_to(CAND.resolve())
        if path.exists():path.unlink()
    for label in ('j','rag'):
        subprocess.run(['git','apply','--ignore-space-change',str(R/f'institution_v2o2_{label}_approval.patch')],cwd=PARENT,check=True)


if __name__=='__main__':
    if sys.argv[1]=='setup':setup()
    elif sys.argv[1]=='refresh':refresh()
    else:raise SystemExit(run())
