"""Real, offline RAG benchmark. Run with the project's CUDA virtualenv.

HTTP mode measures the deployed service. --local profiles one engine in-process;
stop the RAG service first to avoid loading a second Qwen onto the same GPU.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['LUMINAR_MOCK_LLM'] = '0'

QUESTIONS = [
    'What is the author of this book?',
    'What is this book about?',
    'What is the summary of this book?',
    'What are the major themes of this book?',
    'Does this book discuss quantum computing?',
]


def metrics(result):
    timing = result.get('timing_ms', {})
    retrieval = result.get('retrieval', {})
    stages = retrieval.get('stage_timing_ms', {})
    profile = result.get('profile', {})
    calls = profile.get('llm_calls', [])
    generation = calls[-1] if calls else {}
    return {
        'intent_ms': timing.get('intent_analysis'), 'embedding_ms': stages.get('embedding'),
        'retrieval_ms': stages.get('faiss'), 'rerank_ms': stages.get('reranking'),
        'fast_filter_ms': timing.get('fast_filter'), 'validator_ms': timing.get('validation'),
        'generation_ms': timing.get('generation'), 'response_ms': timing.get('response'),
        'preprocessing_ms': stages.get('preprocessing'), 'candidate_merge_ms': stages.get('candidate_merge'),
        'retrieved_count': retrieval.get('candidate_count'), 'reranked_count': retrieval.get('candidate_count'),
        'validator_called': profile.get('validator_calls', 0) > 0,
        'validator_calls': profile.get('validator_calls', 0), 'llm_calls': len(calls),
        'generated_tokens': generation.get('generated_tokens'), 'input_tokens': generation.get('input_tokens'),
        'max_new_tokens': generation.get('max_new_tokens'), 'tokens_per_second': generation.get('tokens_per_second')}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--local', action='store_true')
    p.add_argument('--url', default='http://127.0.0.1:8005')
    p.add_argument('--document', default='OL35758281W')
    p.add_argument('--query', action='append')
    p.add_argument('--runs', type=int, default=3)
    p.add_argument('--threads', type=int)
    p.add_argument('--thread-sweep', type=int, nargs='+')
    p.add_argument('--output', default='reports/rag_latency_benchmark.json')
    args = p.parse_args()
    report = {'mode': 'local' if args.local else 'http', 'runs': [],
              'started_at_unix': time.time(),
              'cold_definition': 'repeat=0 is first observed for this question in this benchmark, not necessarily a cold process or index. Startup and any service restart must be documented separately.'}
    if args.local:
        import torch
        if args.threads:
            torch.set_num_threads(args.threads)
        from rag.qa import LuminaRAG
        start = time.perf_counter()
        engine = LuminaRAG()
        report['model_loading_ms'] = (time.perf_counter() - start) * 1000
        report['torch_threads'] = torch.get_num_threads()
        report['device_map'] = str(getattr(engine.llm.model, 'hf_device_map', engine.llm.model.device))
        report['gpu'] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        ask = lambda q: engine.ask(q, document_id=args.document, depth='normal')
    else:
        import requests
        session = requests.Session()
        health = session.get(args.url + '/health', timeout=10)
        health.raise_for_status()
        report['service_health'] = health.json()
        def ask(q):
            response = session.post(args.url + '/rag/ask', json={
                'query': q, 'document_id': args.document, 'depth': 'normal'}, timeout=600)
            response.raise_for_status()
            result = response.json()
            result['server_timing'] = response.headers.get('Server-Timing')
            return result
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    for thread_count in args.thread_sweep or [args.threads]:
      if thread_count is not None and args.local:
        torch.set_num_threads(thread_count or report['torch_threads'])
      for question in args.query or QUESTIONS:
        for repeat in range(args.runs):
            start = time.perf_counter()
            result = ask(question)
            row = {'question': question, 'document_id': args.document,
                   'threads': thread_count,
                   'repeat': repeat, 'total_ms': (time.perf_counter() - start) * 1000,
                   'result': result}
            row.update(metrics(result))
            row['measured_at_unix'] = time.time()
            report['runs'].append(row)
            output.write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps({k: v for k, v in row.items() if k != 'result'}), flush=True)


if __name__ == '__main__':
    main()
