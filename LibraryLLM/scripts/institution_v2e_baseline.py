"""Immutable, read-only Part 2E preservation baseline without credentials."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEST = 'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'


def digest(rows):
    encoded = [json.dumps(row, sort_keys=True, default=str) for row in rows]
    return hashlib.sha256('\n'.join(sorted(encoded)).encode()).hexdigest()


def capture():
    target = ROOT / 'reports/institution_v2e_baseline.json'
    if target.exists():
        return json.loads(target.read_text(encoding='utf8'))
    from backend.database.mongodb import db
    assert db.name == 'luminar_library' and db.client.address[0] in ('localhost', '127.0.0.1', '::1')
    names = subprocess.check_output(['rg', '--files', '--hidden', '-g', '!.git', '-g', '!.venv', '-g', '!node_modules', '-g', '!.scratch', '-g', '!scratch', '-g', '!dist', '-g', '!datasets'], cwd=ROOT, text=True).splitlines()
    sources = {}
    for name in names:
        name = name.replace('\\', '/')
        path = ROOT / name
        if not name.startswith('reports/') and path.suffix in {'.py', '.ts', '.tsx', '.css', '.json', '.md', '.html', '.toml', '.ps1', '.cjs', '.mjs'} and path.stat().st_size < 32 * 1024 * 1024:
            sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            if name.startswith(('backend/', 'frontend/src/')):
                copy = ROOT / '.scratch/institution-v2e/before' / name
                copy.parent.mkdir(parents=True, exist_ok=True)
                copy.write_bytes(path.read_bytes())
    previous = json.loads((ROOT / 'reports/institution_v2d_baseline.json').read_text(encoding='utf8'))
    artifacts = {name: {'bytes': (ROOT / name).stat().st_size, 'mtime_ns': (ROOT / name).stat().st_mtime_ns} for name in previous['artifact_metadata']}
    snapshots = {}
    for name in db.list_collection_names():
        if name.startswith('institution_') or name in ('events', 'notifications', 'notification_outbox'):
            rows = list(db[name].find({'library_id': TEST}, {'_id': 0}))
            snapshots[name] = {'count': len(rows), 'sha256': digest(rows)}
    books = db.institution_library_books.count_documents({'library_id': TEST, 'status': 'ACTIVE'})
    holdings = db.institution_holdings.count_documents({'library_id': TEST})
    data = {'captured_at': datetime.now(timezone.utc).isoformat(), 'scope': 'Institution Part 2E read-only tenant Analytics and Reporting', 'source_sha256': sources, 'artifact_metadata': artifacts, 'TEST': {'library_id': TEST, 'ACTIVE_books': books, 'holdings': holdings, 'collection_digests': snapshots}, 'global_count': db.books.estimated_document_count(), 'global_count_method': 'estimated_document_count'}
    assert books == holdings == 150
    target.write_text(json.dumps(data, indent=2), encoding='utf8')
    return data


if __name__ == '__main__':
    value = capture()
    print(json.dumps({'sources': len(value['source_sha256']), 'artifacts': len(value['artifact_metadata']), 'TEST_books': value['TEST']['ACTIVE_books'], 'TEST_holdings': value['TEST']['holdings'], 'global_books': value['global_count']}))
