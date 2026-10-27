"""Read-only local baseline for Part 2H; never grant authority or rebuild globals."""
import hashlib, json, sys
from pathlib import Path
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.database.mongodb import db
from scripts.institution_v2f_baseline import digest
from scripts.institution_v2f_preservation import personal_snapshot
TEST = 'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'

def capture():
    path = ROOT / 'reports/institution_v2h_baseline.json'
    if path.exists(): return json.loads(path.read_text())
    assert db.name == 'luminar_library' and db.client.address[0] in ('localhost','127.0.0.1','::1')
    previous = json.loads((ROOT/'reports/institution_v2g_baseline.json').read_text())
    sources = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ['backend','frontend/src','frontend/tests','tests','search','knowledge_graph','assistant','rag','recommendation','scripts']
        for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in ['.py','.tsx','.ts','.css','.json'] and '__pycache__' not in p.parts}
    sources['frontend/package.json'] = hashlib.sha256((ROOT/'frontend/package.json').read_bytes()).hexdigest()
    rows = {n: {'count':db[n].count_documents({'library_id':TEST}), 'sha256':digest(list(db[n].find({'library_id':TEST},{'_id':0})))}
        for n in ['institution_library_books','institution_holdings','institution_library_assets']}
    result = {'captured_at':datetime.now(timezone.utc).isoformat(), 'TEST':rows,
        'global_book_count':db.books.estimated_document_count(), 'source_sha256':sources,
        'global_artifact_metadata':{n:{'bytes':(ROOT/n).stat().st_size,'mtime_ns':(ROOT/n).stat().st_mtime_ns} for n in previous['global_artifact_metadata']},
        'personal_logical':personal_snapshot(ROOT/'rag/private_documents/registry.sqlite'),
        'targets':list(db.institution_intelligence_targets.find({'library_id':TEST},{'_id':0})),
        'authority':'Existing exact ADMIN membership only; no grants.'}
    path.write_text(json.dumps(result,indent=2,default=str),encoding='utf8')
    print('Baseline preserved:', rows['institution_library_books']['count'], rows['institution_holdings']['count'], result['global_book_count'])
    return result
if __name__ == '__main__': capture()
