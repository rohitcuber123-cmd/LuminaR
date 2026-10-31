"""No writes to active Mongo/Windows configuration; output sanitized metadata only."""
import json
import os
import shutil
import subprocess
from pathlib import Path
from dotenv import dotenv_values
from pymongo import MongoClient
ROOT = Path(__file__).resolve().parents[1]
env = {**dotenv_values(ROOT / '.env'), **os.environ}
host = json.loads((ROOT / 'reports/institution_v2n_host_audit.json').read_text())
payload = {'mongo_pid': host['mongo']['server_reported_pid']}
with MongoClient(env.get('MONGO_URI'), serverSelectionTimeoutMS=2000) as client:
    options = client.admin.command('getCmdLineOpts')['parsed']
    payload['dbpath'] = options.get('storage', {}).get('dbPath')
p = subprocess.run([shutil.which('pwsh.exe'), '-NoProfile', '-NonInteractive', '-File', str(ROOT / 'scripts/institution_v2n_boundary.ps1')],
                   input=json.dumps(payload), capture_output=True, text=True, timeout=45)
assert p.returncode == 0, 'Read-only bounded boundary audit unavailable; no raw errors persisted.'
(ROOT / 'reports/institution_v2n_boundary.json').write_text(json.dumps(json.loads(p.stdout), indent=2))
print('Read-only boundary metadata saved; external exposure remains UNKNOWN.')
