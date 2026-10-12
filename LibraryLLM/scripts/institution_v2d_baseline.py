"""Read-only, immutable local Part 2D baseline; never captures credentials."""
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
TEST = 'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'


def capture():
    target = ROOT / 'reports/institution_v2d_baseline.json'
    if target.exists():
        return json.loads(target.read_text(encoding='utf8'))
    names = subprocess.check_output(['rg', '--files', '--hidden', '-g', '!.git', '-g', '!.venv', '-g', '!node_modules', '-g', '!.scratch', '-g', '!scratch', '-g', '!dist', '-g', '!datasets'], cwd=ROOT, text=True).splitlines()
    hashes = {}
    for name in names:
        name = name.replace('\\', '/')
        p = ROOT / name
        if not name.startswith('reports/') and p.suffix in {'.py', '.ts', '.tsx', '.css', '.json', '.md', '.html', '.toml', '.ps1', '.cjs', '.mjs'} and p.stat().st_size < 32 * 1024 * 1024:
            hashes[name] = hashlib.sha256(p.read_bytes()).hexdigest()
            if name.startswith(('frontend/src/', 'backend/')):
                copy = ROOT / '.scratch/institution-v2d/before' / name
                copy.parent.mkdir(parents=True, exist_ok=True)
                copy.write_bytes(p.read_bytes())
    previous = json.loads((ROOT / 'reports/platform_completion_baseline.json').read_text())
    artifacts = {name: {'bytes': (ROOT / name).stat().st_size, 'mtime_ns': (ROOT / name).stat().st_mtime_ns} for name in previous['artifact_metadata']}
    load_dotenv(ROOT / '.env')
    with MongoClient(os.getenv('MONGO_URI'), serverSelectionTimeoutMS=5000) as client:
        db = client['luminar_library']
        snapshots = {name: list(db['institution_' + name].find({'library_id': TEST}, {'_id': 0})) for name in ['libraries', 'memberships', 'library_books', 'holdings', 'lending_config', 'v2c_config']}
        for name, field in [('library_books', 'library_book_id'), ('holdings', 'library_book_id'), ('memberships', 'membership_id')]:
            snapshots[name].sort(key=lambda r: r[field])
        event_rows = list(db.events.find({}, {'_id': 0, 'event_id': 1, 'scope': 1, 'library_id': 1, 'status': 1, 'created_by_user_id': 1}))
        notice_groups = list(db.notifications.aggregate([{'$group': {'_id': {'scope': '$scope', 'source': '$source', 'type': '$type', 'has_library': {'$cond': [{'$ifNull': ['$library_id', False]}, True, False]}}, 'count': {'$sum': 1}}}]))
        count = db.books.estimated_document_count()
    data = {'captured_at': datetime.now(timezone.utc).isoformat(), 'source_sha256': hashes, 'TEST': snapshots, 'global_count': count, 'global_count_method': 'estimated_document_count', 'artifact_metadata': artifacts, 'events': event_rows, 'notification_groups': notice_groups, 'scope': 'Institution Part 2D Events and Notifications tenancy only; no automatic production migration.'}
    target.write_text(json.dumps(data, indent=2, default=str), encoding='utf8')
    (ROOT / 'reports/institution_v2d_events_notifications_baseline.json').write_text(json.dumps({'captured_at': data['captured_at'], 'events': event_rows, 'notification_groups': notice_groups}, indent=2, default=str), encoding='utf8')
    return data


if __name__ == '__main__':
    data = capture()
    print(json.dumps({'sources': len(data['source_sha256']), 'events': len(data['events']), 'notification_groups': len(data['notification_groups']), 'TEST_books': len(data['TEST']['library_books']), 'TEST_holdings': len(data['TEST']['holdings']), 'global_books': data['global_count']}))
