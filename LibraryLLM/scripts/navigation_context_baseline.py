"""Read-only phase baseline; no application import, grants or catalogue mutations."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / 'reports/navigation_context_baseline.json'
if target.exists():
    raise SystemExit('Baseline already exists; never recapture it after edits.')
load_dotenv(ROOT / '.env')
paths = subprocess.check_output(['rg', '--files', '--hidden', '-g', '!.git', '-g', '!.venv', '-g', '!node_modules', '-g', '!.scratch', '-g', '!scratch', '-g', '!dist', '-g', '!datasets'], cwd=ROOT, text=True).splitlines()
suffixes = {'.py', '.tsx', '.ts', '.css', '.json', '.md', '.html', '.yaml', '.yml', '.toml', '.txt', '.ps1'}
source = {}
for name in paths:
    name = name.replace('\\', '/')
    path = ROOT / name
    if not name.startswith('reports/') and path.suffix in suffixes and path.stat().st_size < 32 * 1024 * 1024:
        source[name] = hashlib.sha256(path.read_bytes()).hexdigest()
reports = {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / 'reports').rglob('*') if p.is_file()}
client = MongoClient(os.getenv('MONGO_URI'), serverSelectionTimeoutMS=5000)
database = client['luminar_library']
counts = {name: database[name].estimated_document_count() if name == 'books' else database[name].count_documents({}) for name in database.list_collection_names()}
client.close()
artifacts = {}
for directory in ['datasets', 'search', 'knowledge_graph', 'assistant/models']:
    for p in (ROOT / directory).rglob('*'):
        if p.is_file() and p.suffix in {'.index', '.faiss', '.hnsw', '.bin', '.npz', '.npy', '.duckdb', '.safetensors', '.pkl'}:
            stat = p.stat()
            artifacts[str(p.relative_to(ROOT)).replace('\\', '/')] = {'bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
target.write_text(json.dumps({'captured_at': datetime.now(timezone.utc).isoformat(), 'source_sha256': source,
    'prior_reports_sha256': reports, 'production_counts': counts, 'artifact_metadata': artifacts,
    'artifact_limits': 'Size/mtime preservation evidence; no claim of hashing every multi-gigabyte index.',
    'accepted_authority': 'PlatformRoleAssignment and scoped LibraryMembership, unchanged.'}, indent=2), encoding='utf8')
print(f'Captured {len(source)} source hashes, {len(reports)} prior report hashes, {len(artifacts)} artifact records; global catalogue {counts.get("books")} books.')


