"""Local Part 2 review harness. One worker per backend, cached real Qwen.

Uses an existing eligible reader via the project's JWT utility, as Part 1's
smoke does. A temporary local session bootstrap uses only the existing frontend
auth keys. It is removed on exit; no credentials are included in reports.
No accounts, loans, reservations or document indexes are created.
"""
import json
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reuse', action='store_true', help='Use services already started by the operator; never stop them.')
    parser.add_argument('--minutes', type=float, default=30, help='Maximum review lifetime before automatic cleanup.')
    args = parser.parse_args()
    for port in (8002, 8003, 8004, 8005):
        with socket.socket() as probe:
            if not args.reuse and probe.connect_ex(('127.0.0.1', port)) == 0:
                raise RuntimeError(f'Port {port} already in use. No new model was loaded.')
    from backend.database.mongodb import users_collection
    from backend.services.identity_service import current_identity
    from backend.utils.jwt_utils import create_access_token
    reader = next((u for u in users_collection.find({'role': 'GENERAL_USER', 'is_email_verified': True})
                   if current_identity({'sub': str(u['user_id'])})), None)
    if not reader:
        raise RuntimeError('No existing eligible reader for local integration review.')
    token = create_access_token(reader['user_id'], reader['email'], reader['role'])
    user = {key: reader[key] for key in ('user_id', 'email', 'role', 'full_name') if key in reader}
    bootstrap = ROOT / 'frontend' / 'public' / ('local-review-' + uuid4().hex + '.html')
    processes, logs = [], []
    env = dict(os.environ, PYTHONUTF8='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               ASSISTANT_ENABLED='true', ASSISTANT_MUTATING_ACTIONS_ENABLED='false',
               LUMINAR_MOCK_LLM='0', LUMINAR_DEBUG_PROMPT='0')
    try:
        bootstrap.write_text('<!doctype html><title>Local review session</title><script>'
            + 'localStorage.setItem("luminar_token",' + json.dumps(token) + ');'
            + 'localStorage.setItem("luminar_user",' + json.dumps(json.dumps(user)) + ');'
            + 'sessionStorage.removeItem("luminar_assistant_session");location.replace("/catalog");</script>', encoding='utf-8')
        for module, port in ([] if args.reuse else [('backend.main', 8002), ('search.api', 8003), ('recommendation.api', 8004), ('rag.api', 8005)]):
            log = open(ROOT / f'reports/assistant_frontend_{port}.log', 'w', encoding='utf-8')
            logs.append(log)
            processes.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', module + ':app',
                '--host', '127.0.0.1', '--port', str(port), '--workers', '1'], cwd=ROOT,
                env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW))
        print('Review session URL: http://127.0.0.1:5173/' + bootstrap.name, flush=True)
        print('Using operator services.' if args.reuse else 'Backend processes started once. Stop this harness to clean up.', flush=True)
        deadline = time.monotonic() + args.minutes * 60
        while time.monotonic() < deadline:
            if any(p.poll() is not None for p in processes):
                raise RuntimeError('An owned service exited; inspect the local service log.')
            time.sleep(1)
    except KeyboardInterrupt:
        print('Stopping owned review services.', flush=True)
    finally:
        if bootstrap.exists():
            bootstrap.unlink()
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        for log in logs:
            log.close()


if __name__ == '__main__':
    main()
