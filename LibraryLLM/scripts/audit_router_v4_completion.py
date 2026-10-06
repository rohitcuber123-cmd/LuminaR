"""Post-evaluation evidence audit only: never train or rerun frozen routing."""
import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]


def read(name):
    return json.loads((ROOT / 'reports' / f'assistant_router_v4_{name}.json').read_text(encoding='utf8'))


def write(name, value):
    (ROOT / 'reports' / f'assistant_router_v4_{name}.json').write_text(json.dumps(value, indent=2), encoding='utf8')


async def restored_smoke():
    import httpx
    import psutil
    from check_router_v4_live import identities_and_books, identifiers
    from backend.utils.jwt_utils import create_access_token
    books, first, _ = identities_and_books()
    pair = [b['work_id'] for b in books[:2]]
    token = create_access_token(first['user_id'], first['email'], first['role'])
    output = {'mode': 'existing_qwen', 'health': [], 'smoke': []}
    async with httpx.AsyncClient(timeout=120) as client:
        for role, url in [('Core', 'http://127.0.0.1:8002/health'), ('Search', 'http://127.0.0.1:8003/health'),
                          ('Recommendation', 'http://127.0.0.1:8004/'), ('RAG', 'http://127.0.0.1:8005/health'),
                          ('Frontend', 'http://127.0.0.1:5173/')]:
            response = await client.get(url)
            data = response.json() if 'application/json' in response.headers.get('content-type', '') else {}
            output['health'].append({'role': role, 'status': response.status_code, 'health': data.get('status'),
                                    'index_state': data.get('index_state')})
        conversation = None
        for message, action, intent, expected in [('Compare selected books', 'COMPARE', 'COMPARE_BOOKS', pair),
                                                   ('is the first one available', None, 'CHECK_AVAILABILITY', pair[:1])]:
            body = {'message': message, 'selected_work_ids': pair, 'conversation_id': conversation}
            if action:
                body['action'] = action
            response = await client.post('http://127.0.0.1:8005/assistant/chat', headers={'Authorization': 'Bearer ' + token}, json=body)
            data = response.json()
            conversation = data.get('conversation_id')
            trace = response.headers.get('x-assistant-trace')
            profile = {}
            path = ROOT / 'reports/assistant_router_v4_restored_profiles.jsonl'
            for _ in range(30):
                if path.exists():
                    profile = next((json.loads(line) for line in reversed(path.read_text(encoding='utf8').splitlines())
                                    if json.loads(line).get('trace_id') == trace), {})
                if profile:
                    break
                await asyncio.sleep(.01)
            resolved = identifiers(data) if response.status_code == 200 else []
            output['smoke'].append({'message': message, 'http_status': response.status_code, 'actual_intent': data.get('intent'),
                                    'resolved_public_ids': resolved, 'qwen_calls': profile.get('qwen_call_count'),
                                    'v4_prediction_present': 'router_v4' in profile, 'trace_id': trace,
                                    'pass': response.status_code == 200 and data.get('intent') == intent and resolved == expected
                                            and not data.get('errors') and 'router_v4' not in profile})
    output['python_processes'] = []
    for process in psutil.process_iter(['pid', 'ppid', 'name', 'cmdline', 'memory_info']):
        if 'python' not in (process.info['name'] or '').lower():
            continue
        args = ' '.join(process.info['cmdline'] or [])
        role = next((r for r, part in [('Core', 'backend.main:app'), ('Search', 'search.api:app'),
                                      ('Recommendation', 'recommendation.api:app'), ('RAG', 'rag.api:app')]
                     if part in args), 'Other Python')
        info = process.info['memory_info']
        output['python_processes'].append({'pid': process.pid, 'parent_pid': process.ppid(), 'role': role,
                                           'router_spawn_child': 'multiprocessing.spawn' in args,
                                           'rss_mb': info.rss / 1048576, 'commit_mb': info.vms / 1048576})
    output['no_router_spawn_children'] = not any(p['router_spawn_child'] for p in output['python_processes'])
    output['host_available_mb'] = psutil.virtual_memory().available / 1048576
    output['default_smoke_passed'] = all(r['pass'] for r in output['smoke'])
    write('restored_smoke', output)
    print('RESTORED', output['default_smoke_passed'], 'NO ROUTER CHILD', output['no_router_spawn_children'], flush=True)


def cluster_audit():
    import numpy as np
    import torch
    from assistant.router_v3 import embedding_encoder
    from sklearn.cluster import MiniBatchKMeans
    from threadpoolctl import threadpool_limits
    torch.set_num_threads(2)
    groups = {}
    for version in ['v3', 'v4']:
        rows = [json.loads(line) for line in (ROOT / f'training/assistant_router_{version}/dataset.jsonl').read_text(encoding='utf8').splitlines()]
        groups[version] = list(dict.fromkeys(r['message'] for r in rows))
    for key, filename in [('frozen_116', 'existing'), ('frozen_121', 'hidden')]:
        rows = json.loads((ROOT / f'reports/assistant_router_v3_baseline_snapshot/{filename}_sealed.json').read_text(encoding='utf8'))
        groups[key] = list(dict.fromkeys(r['message'] for r in rows))
    encoder = embedding_encoder()
    assert str(encoder.device) == 'cpu'
    messages = list(dict.fromkeys(m for group in groups.values() for m in group))
    print('DESCRIPTIVE CLUSTER AUDIT', len(messages), 'cached CPU encoder', flush=True)
    vectors = encoder.encode(messages, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    index = {m: i for i, m in enumerate(messages)}
    with threadpool_limits(limits=2):
        model = MiniBatchKMeans(n_clusters=64, random_state=947, n_init=3).fit(vectors)
    output = {'method': 'Shared 64-cluster MiniBatchKMeans over unique message embeddings from cached base MiniLM on CPU; descriptive after evaluation only.',
              'not_used_for_training_or_calibration': True, 'groups': {}}
    for name, group in groups.items():
        counts = Counter(map(str, model.labels_[[index[m] for m in group]]))
        p = np.array(list(counts.values()), dtype=float) / len(group)
        output['groups'][name] = {'unique_messages': len(group), 'occupied_clusters': len(counts),
                                  'entropy_bits': float(-(p * np.log2(p)).sum()),
                                  'effective_clusters': float(2 ** (-(p * np.log2(p)).sum())),
                                  'largest_cluster_fraction': float(p.max()), 'counts': dict(counts)}
    gap = read('dataset_gap')
    gap['shared_embedding_cluster_audit'] = output
    write('dataset_gap', gap)
    print('CLUSTER AUDIT COMPLETE', flush=True)


def integrity():
    baseline = read('baseline')
    changed, missing = [], []
    for relative, old in baseline['frozen_files'].items():
        path = ROOT / relative
        if not path.exists():
            missing.append(relative)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != old:
            changed.append(relative)
    allowed = ['assistant/api.py', 'assistant/profiling.py', 'assistant/qwen.py', 'tests/test_document_rag_latency.py']
    runtime_paths = {'rag/private_documents/registry.sqlite'}
    runtime_changed = [p for p in changed if p in runtime_paths]
    source_changed = [p for p in changed if p not in runtime_paths]
    import sqlite3
    registry = ROOT / 'rag/private_documents/registry.sqlite'
    with sqlite3.connect('file:' + registry.as_posix() + '?mode=ro', uri=True) as connection:
        registry_rows = connection.execute('SELECT count(*) FROM documents').fetchone()[0]
    seal = read('candidate_seal')
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest_path = ROOT / 'assistant/models/router_v4/manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf8'))
    artifact_ok = all(sha(manifest_path.parent / p) == expected for p, expected in manifest['artifact_sha256'].items())
    output = {'baseline_files_checked': len(baseline['frozen_files']), 'changed_existing_files': source_changed,
              'changed_runtime_files': runtime_changed, 'private_document_registry_rows': registry_rows,
              'runtime_change_reason': 'Synthetic live upload/delete changed SQLite bytes; registry contains zero rows after removal.',
              'missing_files': missing,
              'only_authorized_shared_changes': set(source_changed) <= set(allowed), 'v3_sources_artifacts_data_evidence_unchanged':
              not any('router_v3' in p or p.startswith(('search/', 'recommendation/', 'kg/', 'rag/')) for p in source_changed + missing),
              'manifest_seal_matches': sha(manifest_path) == seal['manifest_sha256'],
              'runtime_seal_matches': sha(ROOT / 'assistant/router_v4.py') == seal['runtime_sha256'],
              'artifact_hashes_match': artifact_ok,
              'frozen_evaluations_complete': all(read(n)['complete'] for n in ['frozen_116', 'frozen_121']),
              'frozen_once_guard': read('frozen_started')}
    write('final_integrity', output)
    print('INTEGRITY', json.dumps(output), flush=True)


if __name__ == '__main__':
    if '--smoke' in sys.argv:
        asyncio.run(restored_smoke())
    if '--clusters' in sys.argv:
        cluster_audit()
    if '--integrity' in sys.argv:
        integrity()
