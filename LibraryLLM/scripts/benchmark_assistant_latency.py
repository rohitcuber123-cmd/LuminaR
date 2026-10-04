"""Real read-only benchmark; reuses Core/search/recommendation, owns one Qwen API.

Refuses an occupied 8005 before importing anything that could load a model.
Uses an existing eligible identity in memory; reports no tokens or account rows.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['baseline', 'optimized'], required=True)
    parser.add_argument('--supplement', action='store_true', help='Paired authorized-book RAG and exact typed fast routes.')
    parser.add_argument('--keep-service', action='store_true', help='Leave the single optimized service running for local review.')
    args = parser.parse_args()
    if args.keep_service and args.phase != 'optimized':
        parser.error('--keep-service requires --phase optimized')
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', 8005)) == 0:
            raise RuntimeError('8005 is occupied. Refusing to load another Qwen.')
    from backend.database.mongodb import users_collection, books_collection, issues_collection
    from backend.services.identity_service import current_identity
    from backend.utils.jwt_utils import create_access_token
    user = next((u for u in users_collection.find({'is_email_verified': True, 'role': 'GENERAL_USER'})
                 if current_identity({'sub': str(u['user_id'])})), None)
    if user is None:
        raise RuntimeError('No eligible existing identity')
    headers = {'Authorization': 'Bearer ' + create_access_token(user['user_id'], user['email'], user['role'])}
    config_path = ROOT / 'reports/assistant_latency_cases.json'
    if args.phase == 'baseline' and not args.supplement:
        seeds = [books_collection.find_one({'title': title})['work_id'] for title in ('Dracula', 'Frankenstein')]
        config = {'seeds': seeds, 'identity_digest': digest(str(user['user_id']))}
    else:
        config = json.loads(config_path.read_text())
        if config['identity_digest'] != digest(str(user['user_id'])):
            raise RuntimeError('Benchmark identity changed')
        seeds = config['seeds']
    suffix = args.phase + ('_supplement' if args.supplement else '')
    metrics_path = ROOT / f'reports/assistant_latency_{suffix}_profiles.jsonl'
    metrics_path.write_text('')
    env = dict(os.environ, PYTHONUTF8='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
        LUMINAR_MOCK_LLM='0', LUMINAR_DEBUG_PROMPT='0', ASSISTANT_ENABLED='true',
        ASSISTANT_MUTATING_ACTIONS_ENABLED='false', ASSISTANT_PROFILE_PATH=str(metrics_path))
    output = ROOT / ('reports/chatbot_latency_baseline.json' if args.phase == 'baseline'
                     else 'reports/chatbot_latency_benchmark.json')
    if args.supplement:
        output = ROOT / f'reports/chatbot_latency_{suffix}.json'
    results = {'phase': args.phase, 'cases': [], 'real_services': True,
               'mutations_enabled': False, 'privacy': 'No credentials, prompts or account rows retained.'}
    log_path = ROOT / f'reports/assistant_latency_{suffix}_8005.log'
    with log_path.open('w', encoding='utf-8') as log:
        command = ([sys.executable, str(ROOT / 'scripts/run_assistant_latency_service.py'), '--baseline']
            if args.phase == 'baseline' and args.supplement else
            [sys.executable, '-m', 'uvicorn', 'rag.api:app', '--host', '127.0.0.1', '--port', '8005', '--workers', '1'])
        process = subprocess.Popen(command, cwd=ROOT, env=env,
            stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('RAG startup failed; inspect benchmark service log')
                try:
                    if httpx.get('http://127.0.0.1:8005/health', timeout=2).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(2)
            else:
                raise RuntimeError('Startup deadline')
            print('One resident Qwen service ready', flush=True)
            with httpx.Client(timeout=180) as client:
                documents = client.get('http://127.0.0.1:8005/rag/documents').json()['documents']
                if args.phase == 'baseline' and not args.supplement:
                    document = next((d for d in documents if 'User Roles' in str(d)), documents[0])
                    config['document_id'] = document['document_id'] if isinstance(document, dict) else document
                    config_path.write_text(json.dumps(config, indent=2))
                cases = [
                    ('search', {'message': 'Find books about neural networks'}, None),
                    ('available_now', {'message': 'Show me books available now.'}, 'AVAILABLE_NOW'),
                    ('recommend_default', {'message': 'Recommend'}, 'RECOMMEND'),
                    ('recommend_one', {'message': 'Recommend', 'selected_work_ids': seeds[:1]}, 'RECOMMEND_SIMILAR'),
                    ('recommend_multiple', {'message': 'Recommend', 'selected_work_ids': seeds}, 'RECOMMEND_FROM_SELECTION'),
                    ('compare', {'message': 'Compare these two', 'selected_work_ids': seeds}, 'COMPARE'),
                    ('availability', {'message': 'Is this available?', 'selected_work_ids': seeds[:1]}, 'CHECK_AVAILABILITY'),
                    ('fees', {'message': 'Do I have fines?'}, 'USER_FEES'),
                    ('loans', {'message': 'Show my loans'}, 'USER_LOANS'),
                    ('reservations', {'message': 'Show my reservations'}, 'USER_RESERVATIONS'),
                    ('general', {'message': 'What is Gothic fiction?'}, None),
                    ('book_rag', {'message': 'Who is Victor Frankenstein in this book?',
                                  'selected_work_ids': seeds[1:2]}, 'BOOK_CONTENT_QUESTION'),
                    ('document_rag', {'message': 'According to this PDF, what is role-based access control?',
                                      'page_context': {'document_id': config['document_id']}}, 'DOCUMENT_QUESTION'),
                ]
                if args.supplement:
                    from rag.book_assets import indexed_books
                    indexed = set(indexed_books())
                    eligible = None
                    for candidate in users_collection.find({'role': 'GENERAL_USER', 'is_email_verified': True}):
                        if not current_identity({'sub': str(candidate['user_id'])}):
                            continue
                        loan = next((r for r in issues_collection.find({'user_id': candidate['user_id'], 'status': 'ISSUED'})
                                     if r.get('work_id') in indexed), None)
                        if loan:
                            eligible = candidate, loan['work_id']
                            break
                    if not eligible:
                        raise RuntimeError('No existing authorized indexed-book reader; no loan will be created.')
                    reader, book_id = eligible
                    headers = {'Authorization': 'Bearer ' + create_access_token(reader['user_id'], reader['email'], reader['role'])}
                    results['supplement_identity_digest'] = digest(str(reader['user_id']))
                    cases = [
                        ('book_rag_authorized', {'message': 'Who is the main character in this selected book?',
                            'selected_work_ids': [book_id]}, 'BOOK_CONTENT_QUESTION'),
                        ('typed_recommend', {'message': 'Recommend'}, None),
                        ('typed_compare', {'message': 'Compare these two', 'selected_work_ids': seeds}, None),
                        ('typed_fees', {'message': 'Show my fines'}, None),
                        ('typed_loans', {'message': 'Show my loans'}, None),
                    ]
                for name, payload, action in cases:
                    if args.phase == 'optimized' and action:
                        payload['action'] = action
                    started = time.perf_counter()
                    response = client.post('http://127.0.0.1:8005/assistant/chat', headers=headers, json=payload)
                    elapsed = (time.perf_counter() - started) * 1000
                    body = response.json()
                    trace = response.headers.get('x-assistant-trace')
                    # Middleware writes after the complete response; allow its tiny file write.
                    metrics = None
                    for _ in range(20):
                        profiles = [json.loads(line) for line in metrics_path.read_text().splitlines() if line]
                        metrics = next((p for p in profiles if p['trace_id'] == trace), None)
                        if metrics:
                            break
                        time.sleep(.05)
                    structured = {k: body.get(k) for k in ('intent', 'books', 'seed_work_ids',
                        'recommendation_mode', 'availability', 'account', 'errors')}
                    rag = body.get('rag') or {}
                    row = {'case': name, 'status': response.status_code, 'intent': body.get('intent'),
                        'client_total_ms': elapsed, 'profile': metrics,
                        'book_ids': [b['work_id'] for b in body.get('books', [])],
                        'seed_work_ids': body.get('seed_work_ids'), 'recommendation_mode': body.get('recommendation_mode'),
                        'structured_digest': digest(structured),
                        'component_digests': {k: digest(v) for k, v in structured.items()},
                        'comparison_fields': (body.get('comparison') or {}).get('requested_fields'),
                        'comparison_missing': (body.get('comparison') or {}).get('missing_fields'),
                        'rag_digest': digest({k: rag.get(k) for k in ('answer', 'verdict', 'sources')}),
                        'rag_verdict': rag.get('verdict'), 'rag_source_count': len(rag.get('sources', [])),
                        'error_codes': [e['code'] for e in body.get('errors', [])],
                        'clarification': bool(body.get('clarification'))}
                    results['cases'].append(row)
                    output.write_text(json.dumps(results, indent=2), encoding='utf-8')
                    print(json.dumps({'case': name, 'ms': round(elapsed), 'calls': metrics['qwen_call_count'] if metrics else None,
                        'intent': row['intent'], 'errors': row['error_codes']}), flush=True)
            results['runtime'] = json.loads(Path(str(metrics_path) + '.runtime.json').read_text())
            results['qwen_load_count'] = log_path.read_text(encoding='utf-8', errors='replace').count('Loading Qwen2.5-3B-Instruct in 4-bit...')
            results['health'] = httpx.get('http://127.0.0.1:8005/health').json()
            output.write_text(json.dumps(results, indent=2), encoding='utf-8')
        finally:
            if args.keep_service and process.poll() is None:
                print('Local review service remains running; owned launcher PID ' + str(process.pid), flush=True)
            else:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == '__main__':
    main()
