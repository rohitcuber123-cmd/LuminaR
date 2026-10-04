"""Read-only live smoke. Starts each existing service once; stops owned processes.

Uses an existing eligible DB user for read-only authenticated requests, without
printing credentials or identity. Does not create users, loans or reservations.
"""
import json
import argparse
import os
from pathlib import Path
import subprocess
import socket
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', nargs='+', help='Run only specified named smoke cases.')
    args = parser.parse_args()
    # Refuse before imports/startup if another service already owns a port.
    # In particular, never initialize another Qwen beside a running 8005 API.
    for port in (8002, 8003, 8004, 8005):
        with socket.socket() as probe:
            probe.settimeout(.2)
            if probe.connect_ex(('127.0.0.1', port)) == 0:
                raise RuntimeError(f'Port {port} is already in use; no service was started.')
    from backend.database.mongodb import users_collection, books_collection
    from backend.utils.jwt_utils import create_access_token
    from backend.services.identity_service import current_identity
    user = next((row for row in users_collection.find({'is_email_verified': True})
                 if current_identity({'sub': str(row['user_id'])})), None)
    if user is None:
        raise RuntimeError('No eligible existing user for read-only authenticated smoke.')
    seeds = []
    for title in ('Dracula', 'Frankenstein'):
        book = books_collection.find_one({'title': {'$regex': '^' + title + '$', '$options': 'i'}}, {'_id': 0})
        if book:
            seeds.append(book['work_id'])
    if len(seeds) < 2:
        seeds = [b['work_id'] for b in books_collection.find({}, {'work_id': 1}).limit(2)]
    token = create_access_token(user['user_id'], user['email'], user['role'])
    headers = {'Authorization': f'Bearer {token}'}
    processes, handles = [], []
    outcomes = []
    env = dict(os.environ, PYTHONUTF8='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               LUMINAR_MOCK_LLM='0', LUMINAR_DEBUG_PROMPT='0',
               ASSISTANT_ENABLED='true', ASSISTANT_MUTATING_ACTIONS_ENABLED='false')
    try:
        for module, port in [('backend.main', 8002), ('search.api', 8003),
                             ('recommendation.api', 8004), ('rag.api', 8005)]:
            log = open(ROOT / f'reports/assistant_smoke_{port}.log', 'w', encoding='utf-8')
            handles.append(log)
            processes.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', module + ':app',
                                               '--host', '127.0.0.1', '--port', str(port), '--workers', '1'],
                                              cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0))
        for index, port in enumerate((8002, 8003, 8004, 8005)):
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                if processes[index].poll() is not None:
                    raise RuntimeError(f'Service {port} exited; see its smoke log.')
                try:
                    if httpx.get(f'http://127.0.0.1:{port}/', timeout=2).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(2)
            else:
                raise RuntimeError(f'Service {port} failed startup deadline.')
            print(f'Service {port} ready', flush=True)
        cases = [
            ('search', {'message': 'Find books about neural networks', 'selected_work_ids': []}),
            ('compare', {'message': 'Compare these two', 'selected_work_ids': seeds}),
            ('availability', {'message': 'Is the second one available?', 'recent_work_ids': seeds}),
            ('recommend_default', {'message': 'Recommend', 'selected_work_ids': []}),
            ('recommend_one', {'message': 'Recommend', 'selected_work_ids': seeds[:1]}),
            ('recommend_multiple', {'message': 'Recommend', 'selected_work_ids': seeds}),
            ('fees', {'message': 'Do I have fines?'}),
            ('general', {'message': 'What is Gothic fiction?'}),
            ('reserve_proposal', {'message': 'Reserve the second one', 'recent_work_ids': seeds}),
        ]
        expected = {'search': 'SEARCH_BOOKS', 'compare': 'COMPARE_BOOKS', 'availability': 'CHECK_AVAILABILITY',
                    'recommend_default': 'RECOMMEND_BOOKS', 'recommend_one': 'RECOMMEND_FROM_BOOK',
                    'recommend_multiple': 'RECOMMEND_FROM_SELECTION', 'fees': 'USER_FEES',
                    'general': 'GENERAL_LIBRARY_HELP', 'reserve_proposal': 'RESERVE_BOOK'}
        if args.only:
            if set(args.only) - set(expected):
                raise ValueError('Unknown smoke case requested.')
            cases = [(name, payload) for name, payload in cases if name in args.only]
        with httpx.Client(timeout=150) as client:
            for name, payload in cases:
                started = time.monotonic()
                response = client.post('http://127.0.0.1:8005/assistant/chat', json=payload, headers=headers)
                result = response.json()
                row = {'case': name, 'status': response.status_code, 'intent': result.get('intent'),
                       'recommendation_mode': result.get('recommendation_mode'),
                       'seed_work_ids': result.get('seed_work_ids'), 'book_count': len(result.get('books', [])),
                       'errors': result.get('errors'), 'message': result.get('message'),
                       'clarification': result.get('clarification'),
                       'pending_action': bool(result.get('pending_action')),
                       'latency_seconds': round(time.monotonic()-started, 2)}
                outcomes.append(row)
                print(json.dumps({k: row[k] for k in ('case', 'status', 'intent', 'book_count', 'latency_seconds')}), flush=True)
                if name == 'compare':
                    followup = client.post('http://127.0.0.1:8005/assistant/chat', headers=headers,
                                           json={'message': 'Is the second one available?',
                                                 'conversation_id': result['conversation_id']}).json()
                    outcomes.append({'case': 'server_conversation_reference', 'status': 200,
                                     'intent': followup.get('intent'), 'errors': followup.get('errors'),
                                     'resolved_work_ids': [b['work_id'] for b in followup.get('books', [])],
                                     'passed': [b['work_id'] for b in followup.get('books', [])] == seeds[1:2]})
                if name == 'reserve_proposal' and result.get('pending_action'):
                    confirmation = client.post('http://127.0.0.1:8005/assistant/chat', headers=headers,
                                                json={'message': 'Confirm', 'conversation_id': result['conversation_id'],
                                                      'action': 'CONFIRM_ACTION',
                                                      'pending_action_id': result['pending_action']['action_id']}).json()
                    outcomes.append({'case': 'disabled_confirmation', 'status': 200,
                                     'intent': confirmation.get('intent'), 'errors': confirmation.get('errors'),
                                     'passed': any(e['code'] == 'MUTATIONS_DISABLED' for e in confirmation.get('errors', []))})
        logs = (ROOT / 'reports/assistant_smoke_8005.log').read_text(encoding='utf-8', errors='replace')
        evidence = {'qwen_load_count': logs.count('Loading Qwen2.5-3B-Instruct in 4-bit...'),
                    'model_name': 'Qwen/Qwen2.5-3B-Instruct', 'real_generation': 'Mode               : REAL' in logs,
                    'cases': outcomes}
        by_name = {row['case']: row for row in outcomes}
        evidence['passed'] = (evidence['qwen_load_count'] == 1 and evidence['real_generation']
            and all(row.get('passed', row.get('intent') == expected.get(row['case'])
                        and row.get('status') == 200 and not row.get('errors')) for row in outcomes)
            and ('recommend_default' not in by_name or by_name['recommend_default']['recommendation_mode'] == 'PERSONALIZED_EXISTING_FORMULA')
            and ('recommend_one' not in by_name or by_name['recommend_one']['seed_work_ids'] == seeds[:1])
            and ('recommend_multiple' not in by_name or by_name['recommend_multiple']['seed_work_ids'] == seeds))
        (ROOT / 'reports/assistant_backend_live_smoke.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print('Live smoke passed: ' + str(evidence['passed']), flush=True)
        if not evidence['passed']:
            raise RuntimeError('Live smoke assertions failed; inspect the result JSON.')
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        for handle in handles:
            handle.close()


if __name__ == '__main__':
    main()
