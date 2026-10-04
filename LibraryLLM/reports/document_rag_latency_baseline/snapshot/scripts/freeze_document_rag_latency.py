"""Freeze the accepted state before the document-only latency experiment."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'reports/document_rag_latency_baseline'

def main():
    if DEST.exists():
        raise RuntimeError('Baseline already exists; refusing to overwrite evidence.')
    files = []
    for folder in ('rag', 'assistant', 'backend', 'tests', 'frontend/src',
                   'frontend/tests', 'scripts', 'reports', 'search', 'recommendation'):
        for path in (ROOT / folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and '.pytest_cache' not in path.parts:
                files.append(path)
    manifest = {}
    for path in sorted(set(files)):
        relative = path.relative_to(ROOT)
        target = DEST / 'snapshot' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        manifest[relative.as_posix()] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                      'bytes': path.stat().st_size}
    (DEST / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'files': len(manifest), 'bytes': sum(r['bytes'] for r in manifest.values()),
                      'baseline': str(DEST)}))

if __name__ == '__main__':
    main()
