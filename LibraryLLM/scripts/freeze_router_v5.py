"""Preserve pre-V5 sources and evidence; never overwrite prior experiments."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / 'reports/assistant_router_v5_baseline.json'
    if output.exists():
        raise SystemExit('V5 baseline already exists; refusing to overwrite.')
    files = {}
    for folder in ['assistant', 'backend', 'rag', 'search', 'recommendation', 'scripts', 'tests', 'training', 'reports', 'frontend/src']:
        for path in (ROOT / folder).rglob('*'):
            rel = path.relative_to(ROOT).as_posix()
            if not path.is_file() or '__pycache__' in path.parts or 'router_v5' in rel or path.suffix in {'.pyc', '.pyo'}:
                continue
            files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    snapshot = ROOT / 'reports/assistant_router_v5_baseline_snapshot'
    for relative in ['assistant/api.py', 'assistant/profiling.py', 'assistant/qwen.py', 'assistant/semantic.py', 'tests/test_document_rag_latency.py']:
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    data = {'created_at': datetime.now(timezone.utc).isoformat(), 'frozen_files': files,
            'default': 'existing_qwen', 'v4_status': 'FAIL', 'v3_status': 'FAIL',
            'v4_manifest_sha256': hashlib.sha256((ROOT / 'assistant/models/router_v4/manifest.json').read_bytes()).hexdigest(),
            'services_before_freeze': 'No Core/Search/Recommendation/RAG/Vite listeners active; prior experiment services stopped.'}
    output.write_text(json.dumps(data, indent=2), encoding='utf8')
    print('V5 BASELINE', len(files), 'files preserved', flush=True)


if __name__ == '__main__':
    main()
