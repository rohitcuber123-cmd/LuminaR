"""Check live CUDA RAG serialization, event-loop responsiveness and isolation."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
import requests

URL = 'http://127.0.0.1:8005'
barrier = Barrier(3)


def ask(question, document):
    barrier.wait()
    started = time.perf_counter()
    response = requests.post(URL + '/rag/ask', json={
        'query': question, 'document_id': document}, timeout=180)
    response.raise_for_status()
    result = response.json()
    assert result['sources'] and all(s['work_id'] == document for s in result['sources'])
    return {'document_id': document, 'total_ms': (time.perf_counter() - started) * 1000,
            'queue_ms': result['profile']['queue_ms'], 'result': result}


with ThreadPoolExecutor(max_workers=2) as pool:
    futures = [pool.submit(ask, 'What is the author of this book?', 'OL35758281W'),
               pool.submit(ask, 'What is an autoencoder?', 'AI-CSE-III-I-AUTOENCODER-NOTES')]
    barrier.wait()
    health = []
    while not all(f.done() for f in futures):
        started = time.perf_counter()
        response = requests.get(URL + '/health', timeout=5)
        response.raise_for_status()
        health.append((time.perf_counter() - started) * 1000)
        time.sleep(.2)
    runs = [f.result() for f in futures]

assert max(r['queue_ms'] for r in runs) > 10, 'Expected the shared GPU lock to serialize overlapping requests.'
unknown = requests.post(URL + '/rag/ask', json={
    'query': 'What is the summary of this book?', 'document_id': 'OL00000000W'}, timeout=30)
unknown.raise_for_status()
assert not unknown.json()['sources'], 'Unknown selected book must not fall back to another document.'
assert requests.post(URL + '/rag/ask', json={'query': ''}, timeout=10).status_code == 400
assert requests.post(URL + '/rag/ask', json={'query': 'test', 'depth': 'invalid'}, timeout=10).status_code == 400
report = {'passed': True, 'runs': runs, 'health_ms': health,
          'max_health_ms': max(health), 'unknown_book_sources': unknown.json()['sources'],
          'empty_query_and_invalid_depth_rejected': True}
Path('reports/rag_latency_runtime_checks.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k not in {'runs', 'health_ms'}}), flush=True)
