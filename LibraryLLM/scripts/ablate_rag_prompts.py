"""Compare real legacy/compact prompts and token limits on the shared API."""
import json
import time
from pathlib import Path
import requests
from benchmark_rag_latency import QUESTIONS, metrics

session = requests.Session()
rows = []
cases = [(q, 'OL35758281W') for q in QUESTIONS]
cases.append(('What is an autoencoder?', 'AI-CSE-III-I-AUTOENCODER-NOTES'))
variants = [(compact, 600, cases) for compact in [False, True]]
variants += [(True, cap, [cases[2], cases[3]]) for cap in [128, 192, 256, 320]]
for compact, cap, selected in variants:
    for question, document in selected:
        started = time.perf_counter()
        response = session.post('http://127.0.0.1:8005/__latency/evaluate', json={
            'operation': 'ask', 'question': question, 'document_id': document,
            'compact_prompt': compact, 'max_tokens': cap}, timeout=600)
        response.raise_for_status()
        result = response.json()
        row = {'compact': compact, 'max_tokens': cap, 'question': question,
               'document_id': document, 'total_ms': (time.perf_counter() - started) * 1000,
               'result': result, **metrics(result)}
        rows.append(row)
        Path('reports/rag_latency_prompt_ablation.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
        print(compact, cap, question, round(row['total_ms']), row.get('generated_tokens'), flush=True)
