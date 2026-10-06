"""Events V1 baseline/preservation utilities; no router evaluation/model loading."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT/'reports'

def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(4194304), b''):
            h.update(block)
    return h.hexdigest()

def sources():
    for folder in ['assistant','backend','search','recommendation','rag','frontend','tests','training','evaluation','scripts']:
        for directory, dirs, names in os.walk(ROOT/folder):
            dirs[:] = [d for d in dirs if d not in {'node_modules','.venv','__pycache__','.git','dist','.pytest_cache'}]
            for name in names:
                p = Path(directory)/name
                if p.suffix in {'.py','.ts','.tsx','.css','.json','.md','.ps1','.safetensors','.pt','.bin'}:
                    yield p
    for p in REPORTS.glob('assistant*router*'):
        if p.is_file() and p.suffix in {'.md','.json'}:
            yield p

def save(name, data):
    (REPORTS/name).write_text(json.dumps(data, indent=2), encoding='utf8')

if __name__ == '__main__':
    baseline = REPORTS/'events_baseline.json'
    if not baseline.exists():
        save('events_baseline.json', {'files': {p.relative_to(ROOT).as_posix(): digest(p) for p in sources()}})
        print('Events baseline frozen')
    else:
        previous = json.loads(baseline.read_text(encoding='utf8'))['files']
        current = {p.relative_to(ROOT).as_posix(): digest(p) for p in sources()}
        save('events_file_audit.json', {'existing_changed': [p for p,h in previous.items() if current.get(p) != h],
            'new_files': sorted(set(current)-set(previous)), 'baseline_files': len(previous),
            'deleted': sorted(set(previous)-set(current))})
        print('Events source audit saved')
