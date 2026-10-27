"""Read-only source/artifact and aggregate signal inventory for V2B."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from backend.database.mongodb import db

ROOT = Path(__file__).resolve().parents[1]

def fingerprint(path):
    path = Path(path)
    stat = path.stat()
    result = {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
    if stat.st_size < 10_000_000:
        result['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result

if __name__ == '__main__':
    assert db.name == 'luminar_library'
    old = json.loads((ROOT/'reports/search_v2a_baseline.json').read_text())
    paths = [*old['files'], 'search/query_expansion.py', 'search/api.py',
             'backend/routes/auth.py', 'frontend/src/components/SearchIntelligence.tsx']
    result = {'captured_at': datetime.now(timezone.utc).isoformat(), 'database': db.name,
              'global_count': db.books.count_documents({}),
              'files': {p: fingerprint(ROOT/p) for p in paths},
              'tenant_artifacts': {p: fingerprint(p) for p in old['tenant_artifacts'] if Path(p).exists()},
              'signals': {}}
    for name in ('reading_list', 'issues', 'reservations', 'search_history', 'recommendation_feedbacks',
                 'institution_loans', 'institution_reservations'):
        sample = db[name].find_one({}, {'_id': 0}) or {}
        result['signals'][name] = {'count': db[name].count_documents({}), 'fields': sorted(sample)}
    path = ROOT/'reports/search_v2b_baseline.json'
    if path.exists():
        raise SystemExit('Baseline already exists; do not overwrite pre-change evidence.')
    path.write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps({'baseline': str(path), 'global_count': result['global_count'], 'signals': result['signals']}))
