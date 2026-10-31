"""Freeze Part2L source/data/index inputs read-only, before any native integration."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,platform,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.institution_v2i_baseline import capture_state


def capture_indexes():
    from dotenv import dotenv_values
    from pymongo import MongoClient
    env={**dotenv_values(ROOT/'.env'),**os.environ}
    client=MongoClient(env.get('MONGO_URI','mongodb://127.0.0.1:27017'),serverSelectionTimeoutMS=3000)
    try:
        db=client[env.get('MONGO_DB_NAME','luminar_library')];assert db.name=='luminar_library'
        return {n:list(db[n].list_indexes()) for n in sorted(db.list_collection_names()) if n.startswith('institution_')}
    finally:client.close()


def main():
    out=ROOT/'reports/institution_v2l_baseline.json';assert not out.exists(),'Frozen baseline already exists'
    names=subprocess.check_output(['rg','--files','--hidden','-g','!.git','-g','!.venv','-g','!node_modules','-g','!.scratch','-g','!scratch','-g','!dist','-g','!datasets'],cwd=ROOT,text=True).splitlines()
    sources={}
    for name in names:
        p=ROOT/name
        if not name.replace('\\','/').startswith('reports/') and p.suffix in {'.py','.ts','.tsx','.css','.json','.md','.html','.toml','.ps1','.mjs','.cjs'} and p.stat().st_size<32*1024*1024:
            sources[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    state=capture_state();state['global_KG_metadata']={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in (ROOT/'knowledge_graph/data').glob('*') if p.is_file()}
    frozen={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for prefix in ['institution_v2i_','institution_v2j_','institution_v2k_'] for p in (ROOT/'reports').glob(prefix+'*') if p.is_file()}
    before=ROOT/'.scratch/institution-v2l/before'
    for name in ['search/library_intelligence.py','search/library_intelligence_api.py','scratch/institution_v2k_telemetry/telemetry.py','scratch/institution_v2k_telemetry/observer.py']:
        p=before/name;assert not p.exists();p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/name).read_bytes())
    data={'captured_at':datetime.now(timezone.utc).isoformat(),'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'git_status':subprocess.check_output(['git','status','--porcelain=v1','-uall'],cwd=ROOT,text=True).splitlines(),
        'source_sha256':sources,'frozen_reports_sha256':frozen,'state':state,'mongo_indexes':capture_indexes(),
        'environment':{'python':sys.version,'platform':platform.platform(),'node':subprocess.check_output(['node','--version'],text=True).strip()},
        'enablement_at_start':{'explicit_flag_present':bool(os.getenv('LUMINAR_WORKER_TELEMETRY_ENABLED')),'separate_writer_uri_present':bool(os.getenv('LUMINAR_WORKER_TELEMETRY_MONGO_URI'))},
        'native_contract':{'lease_seconds':90,'renewal_seconds':10,'idle_wait_seconds':2,'serial':True,'close_joins_native_thread':False},
        'telemetry_contract':{'collection':'institution_worker_telemetry_v2k','singleton':'resident-tenant-worker-v1','schema':1,'max_bytes':16384,'entries_per_instance':8,'pulse_seconds':10,'poll_seconds':1},
        'policy':'Review first. Fresh baseline suites finish before editing native/K files. Native integration disabled by default. No production accounts/roles/indexes/config changes, no commit/deploy.'}
    out.write_text(json.dumps(data,indent=2,default=str),encoding='utf8')
    print(json.dumps({'source_files':len(sources),'frozen_reports':len(frozen),'TEST':state.get('TEST',{}).get('current_eligible_books'),'indexes_collections':len(data['mongo_indexes'])}))


if __name__=='__main__':main()
