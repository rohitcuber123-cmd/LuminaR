"""Freeze/preservation inventory only; never load or evaluate router models."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
BASELINE = REPORTS / 'assistant_stabilization_baseline.json'
EXCLUDED = {'.venv', 'node_modules', '__pycache__', '.git', '.pytest_cache', 'dist'}

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def files():
    for folder in ['assistant', 'backend', 'rag', 'search', 'recommendation', 'frontend',
                   'tests', 'scripts', 'training', 'evaluation', 'reports']:
        for p in (ROOT / folder).rglob('*'):
            if p.is_file() and not EXCLUDED.intersection(p.relative_to(ROOT).parts) and p.suffix not in {'.pyc', '.tsbuildinfo'}:
                yield p

def category(relative):
    if relative.startswith('assistant/models/') or '/router_v4_candidates/' in relative:
        return 'C. Generated model artifacts'
    if relative.startswith(('training/assistant_router_', 'evaluation/assistant_router_')):
        return 'D. Generated experiment datasets'
    if relative.startswith('reports/'):
        return 'E. Reports/evidence'
    if 'router_v' in relative or relative.startswith('scripts/'):
        return 'B. Archived experiment source / diagnostic scripts'
    return 'A. Production/application source and tests'

def main():
    if '--freeze' in sys.argv:
        if BASELINE.exists():
            raise RuntimeError('Stabilization baseline already exists; refusing overwrite')
        rows = {p.relative_to(ROOT).as_posix(): {'bytes': p.stat().st_size, 'sha256': digest(p)} for p in files()}
        BASELINE.write_text(json.dumps({'files': rows}, indent=2), encoding='utf8')
        print('BASELINE', len(rows), 'files')
        return
    old = json.loads(BASELINE.read_text(encoding='utf8'))['files']
    changes = [name for name, row in old.items() if not (ROOT/name).exists() or digest(ROOT/name) != row['sha256']]
    live_logs = []
    # Existing live services keep appending their logs. Preserve the exact
    # baseline prefixes without truncating active files or stopping services.
    for name in changes:
        if name in {'reports/assistant_router_v5_core.out.log', 'reports/assistant_router_v5_recommendation.out.log',
                    'reports/assistant_router_v5_search_restarted.out.log', 'reports/assistant_router_v5_vite.out.log'}:
            data = (ROOT/name).read_bytes()[:old[name]['bytes']]
            if hashlib.sha256(data).hexdigest() == old[name]['sha256']:
                target = REPORTS/'assistant_router_archive_live_log_prefixes'/Path(name).name
                target.parent.mkdir(exist_ok=True)
                if target.exists() and target.read_bytes() != data:
                    raise RuntimeError('Preserved log prefix changed')
                target.write_bytes(data)
                live_logs.append({'file': name, 'baseline_bytes': len(data),
                    'current_bytes': (ROOT/name).stat().st_size, 'prefix_sha256': old[name]['sha256'],
                    'preserved_copy': target.relative_to(ROOT).as_posix()})
    inventory = {}
    for p in files():
        name = p.relative_to(ROOT).as_posix()
        kind = category(name)
        bucket = inventory.setdefault(kind, {'count': 0, 'bytes': 0})
        bucket['count'] += 1
        bucket['bytes'] += p.stat().st_size
    scopes = {}
    for scope in ['assistant/models/router_v3', 'assistant/models/router_v4', 'assistant/models/router_v4_candidates',
                  'assistant/models/router_v5', 'training/assistant_router_v3', 'training/assistant_router_v4',
                  'evaluation/assistant_router_v5', 'assistant/router_v3', 'assistant/router_v4', 'assistant/router_v5']:
        ps = [p for p in files() if p.relative_to(ROOT).as_posix().startswith(scope + '/')
              or p.relative_to(ROOT).as_posix() == scope + '.py']
        scopes[scope] = {'files': len(ps), 'bytes': sum(p.stat().st_size for p in ps)}
    added = [p.relative_to(ROOT).as_posix() for p in files() if p.relative_to(ROOT).as_posix() not in old]
    result = {'categories': inventory, 'experiment_scopes': scopes, 'existing_files_changed': changes,
              'new_files': added, 'deleted_files': [p for p in old if not (ROOT/p).exists()],
              'live_logs_appended': live_logs,
              'research_evidence_changed': [p for p in changes if ('router_v' in p and not p.startswith('tests/'))
                  and p not in {r['file'] for r in live_logs}]}
    (REPORTS/'assistant_stabilization_file_audit.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps({'changed': changes, 'new_count': len(added), 'research_evidence_changed': result['research_evidence_changed']}))

if __name__ == '__main__':
    main()
