"""Freeze 2K inputs with direct read-only capture; no production runtime imports."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.institution_v2i_baseline import capture_state


def main():
    out=ROOT/'reports/institution_v2k_baseline.json'
    if out.exists():raise SystemExit('Frozen baseline already exists')
    names=subprocess.check_output(['rg','--files','--hidden','-g','!.git','-g','!.venv','-g','!node_modules','-g','!.scratch','-g','!scratch','-g','!dist','-g','!datasets'],cwd=ROOT,text=True).splitlines()
    sources={}
    for name in names:
        p=ROOT/name
        if not name.replace('\\','/').startswith('reports/') and p.suffix in {'.py','.ts','.tsx','.css','.json','.md','.html','.toml','.ps1','.mjs','.cjs'} and p.stat().st_size<32*1024*1024:
            sources[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    state=capture_state()
    state['global_KG_metadata']={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in (ROOT/'knowledge_graph/data').glob('*') if p.is_file()}
    frozen={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for prefix in ['institution_v2i_','institution_v2j_'] for p in (ROOT/'reports').glob(prefix+'*') if p.is_file()}
    data={'captured_at':datetime.now(timezone.utc).isoformat(),'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
          'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'git_status':subprocess.check_output(['git','status','--porcelain=v1','-uall'],cwd=ROOT,text=True).splitlines(),
          'source_sha256':sources,'frozen_reports_sha256':frozen,'state':state,
          'implementation_policy':'Review/design/authentication/failure/resource gates first; isolated fixture-only prototype next. Production integration disabled unless all gates independently pass. No secrets or commit.',
          'test_baseline':'Fresh institution_v2k_baseline_* product suites, including all 2I and 2J focused tests; existing two failures remain enabled.'}
    out.write_text(json.dumps(data,indent=2,default=str),encoding='utf8')
    print(json.dumps({'source_files':len(sources),'frozen_I_J_reports':len(frozen),'TEST_eligible':state.get('TEST',{}).get('current_eligible_books')}))


if __name__=='__main__':main()
