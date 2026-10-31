"""Part 2I evidence capture. Direct read-only production Mongo; no app imports."""
import hashlib
import json
import os
import platform
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from bson import json_util
from dotenv import dotenv_values
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
TEST = 'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
OUT = ROOT / 'reports/institution_v2i_baseline.json'


def digest(rows):
    lines = sorted(json_util.dumps(r, sort_keys=True) for r in rows)
    return hashlib.sha256('\n'.join(lines).encode()).hexdigest()


def files(directory, hashes=False):
    result = {}
    if directory.exists():
        for p in directory.rglob('*'):
            if p.is_file():
                s = p.stat()
                entry = {'bytes': s.st_size, 'mtime_ns': s.st_mtime_ns}
                if hashes and s.st_size < 256 * 1024 * 1024:
                    entry['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
                result[p.relative_to(ROOT).as_posix()] = entry
    return result


def capture_state():
    env = {**dotenv_values(ROOT / '.env'), **os.environ}
    client = MongoClient(env.get('MONGO_URI', 'mongodb://127.0.0.1:27017'),
                         serverSelectionTimeoutMS=4000)
    result = {}
    try:
        client.admin.command('ping')
        assert client.address[0] in ('localhost', '127.0.0.1', '::1')
        db = client[env.get('MONGO_DB_NAME', 'luminar_library')]
        assert db.name == 'luminar_library'
        result['database'] = db.name
        result['global_book_count'] = db.books.estimated_document_count()
        result['global_count_method'] = 'estimated_document_count; no global catalogue scan'
        result['tenant_collections'] = {}
        for name in sorted(db.list_collection_names()):
            if name.startswith('institution_'):
                count = db[name].count_documents({})
                result['tenant_collections'][name] = {'count': count}
                if count <= 100000:
                    result['tenant_collections'][name]['sha256'] = digest(db[name].find({}))
        eligible = {'library_id': TEST, 'status': 'ACTIVE', 'title': {'$type': 'string', '$regex': r'\S'}}
        result['TEST'] = {'library_id': TEST, 'historical_2H_eligible': 150,
                          'current_total_books': db.institution_library_books.count_documents({'library_id': TEST}),
                          'current_eligible_books': db.institution_library_books.count_documents(eligible),
                          'holdings': db.institution_holdings.count_documents({'library_id': TEST}),
                          'assets': db.institution_library_assets.count_documents({'library_id': TEST}),
                          'targets': list(db.institution_intelligence_targets.find({'library_id': TEST}, {'_id': 0})),
                          'latest_dataset': db.institution_intelligence_generations.find_one({'library_id': TEST}, {'_id': 0}, sort=[('sequence', -1)])}
        result['jobs_by_state'] = list(db.institution_intelligence_jobs.aggregate([
            {'$group': {'_id': '$state', 'count': {'$sum': 1}}}, {'$sort': {'_id': 1}}]))
        result['effective_active_jobs'] = db.institution_intelligence_jobs.count_documents({'effective_active': True})
        result['db_observation'] = 'Read-only MongoClient, never backend.database.mongodb (import creates index).'
    except Exception as error:
        result['database_unavailable'] = type(error).__name__
    finally:
        client.close()
    old = json.loads((ROOT / 'reports/institution_v2h_baseline.json').read_text())
    result['global_artifacts'] = {name: {'bytes': (ROOT / name).stat().st_size,
                                        'mtime_ns': (ROOT / name).stat().st_mtime_ns}
                                  for name in old['global_artifact_metadata'] if (ROOT / name).exists()}
    result['tenant_artifacts'] = files(Path(env.get('LIBRARY_INTELLIGENCE_ROOT') or ROOT / 'local-data/library-intelligence'), True)
    result['protected_files'] = {}
    for name in ('rag/private_documents', '.local/private_documents', 'local-data/library-assets', 'rag/indexes'):
        result['protected_files'].update(files(ROOT / name, False))
    result['personal_logical'] = {}
    for name in ('rag/private_documents/registry.sqlite', '.local/private_documents/registry.sqlite'):
        p = ROOT / name
        if p.exists():
            with sqlite3.connect(p.as_uri() + '?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
                result['personal_logical'][name] = {t: digest(dict(r) for r in conn.execute('SELECT * FROM "' + t.replace('"', '""') + '"')) for t in tables}
    return result


def main():
    if OUT.exists():
        raise SystemExit('Refusing to overwrite frozen baseline')
    names = subprocess.check_output(['rg', '--files', '--hidden', '-g', '!.git', '-g', '!.venv',
        '-g', '!node_modules', '-g', '!.scratch', '-g', '!scratch', '-g', '!dist', '-g', '!datasets'], cwd=ROOT, text=True).splitlines()
    sources = {}
    for name in names:
        p = ROOT / name
        if not name.replace('\\', '/').startswith('reports/') and p.suffix in {'.py', '.ts', '.tsx', '.css', '.json', '.md', '.html', '.toml', '.ps1', '.mjs', '.cjs'} and p.stat().st_size < 32 * 1024 * 1024:
            sources[p.relative_to(ROOT).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    before = ROOT / '.scratch/institution-v2i/before'
    before.mkdir(parents=True, exist_ok=True)
    for name in ('backend/services/library_intelligence_service.py', 'backend/services/library_intelligence_store.py',
                 'frontend/src/pages/LibraryIntelligence.tsx', 'frontend/src/lib/libraryIntelligence.ts'):
        p = before / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes((ROOT / name).read_bytes())
    status = subprocess.check_output(['git', 'status', '--porcelain=v1', '-uall'], cwd=ROOT, text=True)
    result = {'captured_at': datetime.now(timezone.utc).isoformat(),
              'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
              'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'git_status': status.splitlines(), 'source_sha256': sources,
              'environment': {'python': sys.version, 'platform': platform.platform(),
                              'node': subprocess.check_output(['node', '--version'], text=True).strip(),
                              'cwd': str(ROOT)},
              'config': {'worker': 'one resident Search API daemon thread; serial run_one, 2 second idle wait',
                         'lease_seconds': 90, 'renewal_seconds': 10, 'max_books': 50000,
                         'max_dataset_bytes': 67108864, 'status_active_poll_seconds': 3,
                         'automatic_rebuilds': False, 'scheduled_rebuilds': False},
              'state': capture_state(), 'test_baseline': 'See institution_v2i_baseline_* evidence; captured before production edits.'}
    OUT.write_text(json.dumps(result, indent=2, default=str), encoding='utf8')
    print(json.dumps({'sources': len(sources), 'preexisting_git_entries': len(result['git_status']),
                      'TEST': result['state'].get('TEST'), 'database_error': result['state'].get('database_unavailable'),
                      'artifacts': len(result['state']['tenant_artifacts'])}, default=str))


if __name__ == '__main__':
    main()
