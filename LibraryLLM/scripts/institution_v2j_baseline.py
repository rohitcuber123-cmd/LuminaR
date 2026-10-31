"""Freeze Part 2J inputs without importing write-on-import application modules."""
from datetime import datetime,timezone
import hashlib,json,platform,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.institution_v2i_baseline import capture_state


def main():
    out=ROOT/'reports/institution_v2j_baseline.json'
    if out.exists():raise SystemExit('Frozen baseline already exists')
    names=subprocess.check_output(['rg','--files','--hidden','-g','!.git','-g','!.venv','-g','!node_modules','-g','!.scratch','-g','!scratch','-g','!dist','-g','!datasets'],cwd=ROOT,text=True).splitlines()
    sources={}
    for name in names:
        p=ROOT/name
        if not name.replace('\\','/').startswith('reports/') and p.suffix in {'.py','.ts','.tsx','.css','.json','.md','.html','.toml','.ps1','.mjs','.cjs'} and p.stat().st_size<32*1024*1024:
            sources[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    frozen={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'reports').glob('institution_v2i_*') if p.is_file()}
    state=capture_state()
    state['global_KG_metadata']={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in (ROOT/'knowledge_graph/data').glob('*') if p.is_file()}
    data={'captured_at':datetime.now(timezone.utc).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
          'git_status':subprocess.check_output(['git','status','--porcelain=v1','-uall'],cwd=ROOT,text=True).splitlines(),
          'source_sha256':sources,'frozen_2I_reports_sha256':frozen,'state':state,
          'environment':{'python':sys.version,'platform':platform.platform(),'node':subprocess.check_output(['node','--version'],text=True).strip()},
          'baseline_tests':'Fresh institution_v2j_baseline_* executions; expected 2I failures remain enabled.',
          'worker_and_schema':'Existing 2G/2H worker, jobs/targets/generations and 2I status helper frozen by source SHA256; no new telemetry fields planned.',
          'operator_authorization_review':'No infrastructure-operator application identity found. Existing library_intelligence_cli uses tenant JWT. New local command must independently authenticate a Mongo built-in read principal; no production grant/provisioning performed.'}
    out.write_text(json.dumps(data,indent=2,default=str),encoding='utf8')
    print(json.dumps({'sources':len(sources),'frozen_2I_reports':len(frozen),'TEST_books':state.get('TEST',{}).get('current_eligible_books'),'existing_tracked_change':'backend/services/library_intelligence_service.py (2I; preserved)'}))


if __name__=='__main__':main()
