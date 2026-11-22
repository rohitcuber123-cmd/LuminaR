"""Read-only preimplementation checkpoint; no application imports or deployment writes."""
from pathlib import Path
import hashlib, json, subprocess, sys
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.institution_v2i_baseline import capture_state, digest
from scripts.institution_v2l_baseline import capture_indexes
from dotenv import dotenv_values
from pymongo import MongoClient

def communication_state():
    env = dotenv_values(ROOT/'.env')
    with MongoClient(env.get('MONGO_URI'), serverSelectionTimeoutMS=5000) as client:
        db = client[env.get('MONGO_DB_NAME') or 'luminar_library']
        assert db.name == 'luminar_library'
        return {n: {'count': db[n].count_documents({}), 'sha256': digest(db[n].find({}))}
                for n in ['events', 'event_user_state', 'notifications', 'issues', 'reservations']}

def main():
    target = ROOT/'reports/institution_v2p_baseline.json'
    assert not target.exists(), 'Refusing to overwrite baseline'
    names = subprocess.check_output(['rg','--files','--hidden','-g','!.git','-g','!.venv','-g','!node_modules','-g','!.scratch','-g','!scratch','-g','!dist','-g','!datasets'],cwd=ROOT,text=True).splitlines()
    sources, reports = {}, {}
    for name in names:
        p = ROOT/name; name = p.relative_to(ROOT).as_posix()
        if p.stat().st_size > 32*1024*1024: continue
        if name.startswith('reports/'):
            reports[name] = hashlib.sha256(p.read_bytes()).hexdigest()
        elif p.suffix in {'.py','.ts','.tsx','.css','.json','.md','.html','.toml','.ps1','.mjs','.cjs'}:
            sources[name] = hashlib.sha256(p.read_bytes()).hexdigest()
            if name.startswith(('backend/','frontend/')):
                copy = ROOT/'.scratch/institution-v2p/before'/name
                copy.parent.mkdir(parents=True,exist_ok=True); copy.write_bytes(p.read_bytes())
    data = {'captured_at':datetime.now(timezone.utc).isoformat(), 'source_sha256':sources, 'reports_sha256':reports,
        'git_status':subprocess.check_output(['git','status','--porcelain=v1','-uall'],cwd=ROOT,text=True).splitlines(),
        'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'state':capture_state(), 'mongo_indexes':capture_indexes(), 'communication_state':communication_state()}
    data['state']['global_KG_metadata']={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in (ROOT/'knowledge_graph/data').glob('*') if p.is_file()}
    target.write_text(json.dumps(data,indent=2,default=str),encoding='utf8')
    print(json.dumps({'sources':len(sources),'reports':len(reports),'global_books':data['state'].get('global_book_count'),'communications':data['communication_state']}))
if __name__=='__main__': main()
