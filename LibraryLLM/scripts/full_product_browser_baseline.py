"""Capture this browser closure phase without overwriting earlier evidence."""
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
BASELINE = REPORTS / 'full_product_browser_closure_baseline.json'

def capture():
    if BASELINE.exists():
        print('Browser closure baseline already exists; preserved.')
        return
    paths = subprocess.check_output(['rg', '--files', '--hidden', '-g', '!.git', '-g', '!.venv', '-g', '!node_modules', '-g', '!.scratch', '-g', '!scratch', '-g', '!dist', '-g', '!datasets'], cwd=ROOT, text=True).splitlines()
    source = {}
    for name in paths:
        name = name.replace('\\', '/')
        p = ROOT / name
        if not name.startswith('reports/') and p.suffix in {'.py', '.ts', '.tsx', '.css', '.json', '.md', '.html', '.toml', '.ps1', '.cjs'} and p.stat().st_size < 32*1024*1024:
            source[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    prior = json.loads((REPORTS/'full_product_convergence_baseline.json').read_text(encoding='utf8'))
    artifacts = {}
    for name in prior['artifact_metadata']:
        p = ROOT/name
        if p.is_file():
            stat = p.stat()
            artifacts[name] = {'bytes':stat.st_size, 'mtime_ns':stat.st_mtime_ns}
    load_dotenv(ROOT/'.env')
    with MongoClient(os.getenv('MONGO_URI'), serverSelectionTimeoutMS=5000) as client:
        db = client['luminar_library']
        query = {'library_id':'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'}
        records = list(db.institution_library_books.find(query, {'_id':0}).sort('library_book_id',1))
        holdings = list(db.institution_holdings.find(query, {'_id':0}).sort('library_book_id',1))
        count = db.books.estimated_document_count()
    old_walk = REPORTS/'full_product_browser_walkthrough.json'
    (REPORTS/'full_product_browser_walkthrough_before_closure.json').write_bytes(old_walk.read_bytes())
    value = {'captured_at':datetime.now(timezone.utc).isoformat(), 'source_sha256':source, 'global_count':count, 'global_count_method':'estimated_document_count', 'test_records':records, 'test_holdings':holdings, 'artifact_metadata':artifacts, 'prior_walkthrough_snapshot':'reports/full_product_browser_walkthrough_before_closure.json', 'authority':'Existing memberships and explicit platform assignments only; no grants or migrations.'}
    BASELINE.write_text(json.dumps(value,indent=2,default=str),encoding='utf8')
    print(f'Baseline captured: {len(source)} sources, {len(records)} TEST books, {len(holdings)} holdings, {count} global books, {len(artifacts)} artifacts.')

if __name__ == '__main__':
    capture()
