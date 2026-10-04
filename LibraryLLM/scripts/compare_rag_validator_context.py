"""Compare attention on the actual selected evidence of failed E2E cases."""
import json
import time
from pathlib import Path
import requests

rows = json.loads(Path('reports/rag_latency_e2e_rejected_validator_attention.json').read_text())
outputs = []
for row in rows:
    if row['id'] not in {'gen_10', 'gen_12'}:
        continue
    metadata = json.loads(Path(f"rag/book_index/books/{row['work_id']}_metadata.json").read_text(encoding='utf-8'))
    if isinstance(metadata, dict):
        metadata = metadata.get('chunks', metadata.get('metadata', list(metadata.values())))
    lookup = {item['chunk_id']: item for item in metadata}
    evidence = [lookup[source['chunk_id']] for source in row['result']['sources'][:3]]
    for attention in ['luminar_sdpa', 'sdpa']:
        started = time.perf_counter()
        response = requests.post('http://127.0.0.1:8005/__latency/evaluate', json={
            'operation': 'validate', 'question': row['query'], 'intent_data': row['result']['intent_data'],
            'evidence': evidence, 'attention': attention}, timeout=180)
        response.raise_for_status()
        result = response.json()
        out = {'id': row['id'], 'attention': attention, 'result': result,
               'elapsed_ms': (time.perf_counter() - started)*1000,
               'chunk_ids': [e['chunk_id'] for e in evidence]}
        outputs.append(out)
        Path('reports/rag_latency_validator_context_comparison.json').write_text(json.dumps(outputs, indent=2), encoding='utf-8')
        print(row['id'], attention, result['verdict'], round(out['elapsed_ms']), flush=True)
