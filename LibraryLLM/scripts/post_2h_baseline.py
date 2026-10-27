"""Read-only baseline for the post-Part-2H presentation closure."""
import hashlib, json, sys
from pathlib import Path
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.database.mongodb import db
from scripts.institution_v2f_baseline import digest
from scripts.institution_v2f_preservation import personal_snapshot
TEST = 'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'

def snapshot():
    assert db.name == 'luminar_library' and db.client.address[0] in ('localhost','127.0.0.1','::1')
    previous = json.loads((ROOT/'reports/institution_v2h_baseline.json').read_text())
    source = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ['backend','frontend/src','frontend/tests','search','knowledge_graph','assistant','rag','recommendation']
        for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in ['.py','.tsx','.ts','.css'] and '__pycache__' not in p.parts}
    artifacts = list(previous['global_artifact_metadata'])
    artifacts += [p.relative_to(ROOT).as_posix() for p in (ROOT/'data').rglob('*') if p.is_file() and TEST in str(p)] if (ROOT/'data').exists() else []
    return {'captured_at':datetime.now(timezone.utc).isoformat(), 'source_sha256':source,
        'TEST': {n:{'count':db[n].count_documents({'library_id':TEST}),'sha256':digest(list(db[n].find({'library_id':TEST},{'_id':0})))} for n in ['institution_library_books','institution_holdings','institution_library_assets','institution_intelligence_targets','institution_intelligence_jobs','institution_intelligence_generations']},
        'global_book_count':db.books.estimated_document_count(),
        'artifacts':{n:{'bytes':(ROOT/n).stat().st_size,'mtime_ns':(ROOT/n).stat().st_mtime_ns} for n in artifacts},
        'personal_logical':personal_snapshot(ROOT/'rag/private_documents/registry.sqlite')}

if __name__ == '__main__':
    path=ROOT/'reports/post_2h_baseline.json'
    if not path.exists():path.write_text(json.dumps(snapshot(),indent=2,default=str),encoding='utf8')
    value=json.loads(path.read_text()); print(json.dumps({'TEST':value['TEST'],'global_book_count':value['global_book_count']}))
