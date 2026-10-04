"""Interactive real-model experiments; one GPU engine for all comparisons.

Run with python -u -i scripts/rag_latency_lab.py after stopping the RAG API.
All results are persisted immediately. No frozen evaluation files are overwritten.
"""
import ast
import contextlib
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
import torch
from rag.qa import LuminaRAG, DEPTH_CONFIG
from rag.fast_filter import run_fast_filter, compute_alignment_signals
from rag.telemetry import profile_request

log = (ROOT / 'reports/rag_latency_lab.log').open('a', encoding='utf-8')
started = time.perf_counter()
with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
    engine = LuminaRAG()
startup_ms = (time.perf_counter() - started) * 1000
records = []
latest_prompt = None
generate_original = engine.llm.generate


def capture_generate(prompt, **kwargs):
    global latest_prompt
    if kwargs.get('prefix_allowed_tokens_fn') is None:
        latest_prompt = prompt
    return generate_original(prompt, **kwargs)


engine.llm.generate = capture_generate


def save(name, data):
    (ROOT / 'reports' / (name + '.json')).write_text(json.dumps(data, indent=2), encoding='utf-8')


def audit_model():
    from collections import Counter
    data = {'parameter_devices': dict(Counter(str(p.device) for p in engine.llm.model.parameters())),
            'parameter_dtypes': dict(Counter(str(p.dtype) for p in engine.llm.model.parameters())),
            'attention': engine.llm.model.config._attn_implementation,
            'quantized_layers': sum(type(m).__name__ == 'Linear4bit' for m in engine.llm.model.modules()),
            'cache': str(engine.llm.model.generation_config.cache_implementation),
            'allocated_mb': torch.cuda.memory_allocated() / 2**20,
            'reserved_mb': torch.cuda.memory_reserved() / 2**20}
    save('rag_latency_model_audit', data)
    print(data, flush=True)


def profile_generation(tokens=20):
    assert latest_prompt
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU, torch.profiler.ProfilerActivity.CUDA], record_shapes=True) as prof:
            answer = generate_original(latest_prompt, max_new_tokens=tokens)
    (ROOT / 'reports/rag_latency_torch_profile.txt').write_text(prof.key_averages().table(sort_by='self_cpu_time_total', row_limit=35), encoding='utf-8')
    print('Profiler saved', answer, flush=True)


def run(label, query='What is the summary of this book?', document='OL35758281W', repeats=3, **config):
    previous = dict(DEPTH_CONFIG['normal'])
    DEPTH_CONFIG['normal'].update(config)
    try:
        for i in range(repeats):
            start = time.perf_counter()
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                result = engine.ask(query, document_id=document)
            row = {'label': label, 'repeat': i, 'config': dict(DEPTH_CONFIG['normal']),
                   'finished_at': time.time(),
                   'document_id': document, 'query': query,
                   'total_ms': (time.perf_counter() - start) * 1000, 'result': result}
            records.append(row)
            save('rag_latency_experiments', records)
            print(label, i, round(row['total_ms'] / 1000, 3), result.get('verdict'), flush=True)
    finally:
        DEPTH_CONFIG['normal'].update(previous)


def dataset(filename, variable):
    # Extract existing frozen test data without running module imports that set mock mode.
    module = ast.parse((ROOT / 'scratch' / filename).read_text(encoding='utf-8'))
    for node in module.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == variable for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError(variable)


def intent_regression():
    queries = dataset('run_v8_step7_intent_regression.py', 'TEST_QUERIES')
    results = []
    for q in queries:
        start = time.perf_counter()
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            actual = engine.llm.analyze_intent(q['query'])
        results.append({**q, 'actual': actual, 'correct': actual['intent'] == q['expected_intent'],
                        'latency_ms': (time.perf_counter() - start) * 1000})
        save('rag_latency_intent_regression', results)
        print('intent', q['id'], results[-1]['correct'], flush=True)


def retrieval_sweep():
    import rag.reranker as reranker_module
    queries = dataset('run_v8_step7_retrieval_regression.py', 'RETRIEVAL_QUERIES')
    results = []
    original = reranker_module.CANDIDATE_K
    try:
        for count in [3, 5, 8, 10, 15]:
            reranker_module.CANDIDATE_K = count
            for q in queries:
                start = time.perf_counter()
                with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    result = engine.reranker.search(q['query'], top_k=5, work_id=q['work_id'], intent_data={})
                items = result['results']
                score = lambda text, keys: sum(k.lower() in text.lower() for k in keys) / len(keys)
                top1 = score(items[0]['text'] if items else '', q['expected_top1_keywords'])
                top3 = score(' '.join(i['text'] for i in items[:3]), q['expected_top3_keywords'])
                rr = next((1 / rank for rank, item in enumerate(items, 1)
                           if score(item['text'], q['expected_top1_keywords']) >= .5), 0)
                results.append({'candidates': count, 'id': q['id'], 'top1_score': top1,
                                'top3_score': top3, 'rr': rr,
                                'top_chunks': [i['chunk_id'] for i in items],
                                'latency_ms': (time.perf_counter() - start) * 1000,
                                'timing': result.get('timing_ms')})
                save('rag_latency_retrieval_sweep', results)
            print('retrieval sweep', count, flush=True)
    finally:
        reranker_module.CANDIDATE_K = original


def validator_regression():
    cases = dataset('run_v8_step6_final_eval.py', 'ADVERSARIAL_CASES')
    results = []
    for case in cases:
        items = [{'text': case['evidence']}]
        start = time.perf_counter()
        ff = run_fast_filter(case['question'], case['intent_data'], items)
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            if ff['decision'] == 'NEEDS_LLM_VALIDATION':
                validation = engine.llm.validate_evidence(case['question'], case['intent_data'], items, mode='top-3-comb')
                supported = validation['verdict'] == 'SUPPORTED'
            else:
                validation = None
                supported = ff['decision'] == 'FAST_ACCEPT'
        results.append({**case, 'fast_filter': ff, 'validation': validation,
                        'actual_supported': supported, 'correct': supported == case['expected_supported'],
                        'latency_ms': (time.perf_counter() - start) * 1000})
        save('rag_latency_validator_regression', results)
        print('validator', case['id'], results[-1]['correct'], flush=True)


def e2e_regression():
    cases = dataset('run_v8_step7_e2e_generation.py', 'TEST_SUITE')
    results = []
    for case in cases:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            result = engine.ask(case['query'], work_id=case['work_id'])
        answer = result.get('answer', '').lower()
        verdict = result.get('verdict', 'NOT_SUPPORTED')
        unsupported = any(t in answer for t in ['does not support the premise', 'not establish', 'never', 'no evidence', 'false']) or verdict == 'NOT_SUPPORTED'
        if not case['is_premise_valid']:
            classification = 'UNSUPPORTED' if unsupported or 'not' in answer else 'HALLUCINATED'
        elif verdict == 'NOT_SUPPORTED':
            classification = 'UNSUPPORTED'
        else:
            classification = 'CORRECT' if any(t.lower() in answer for t in case['ground_truth_fact'].split() if len(t) > 3) else 'PARTIALLY_CORRECT'
        results.append({**case, 'actual_classification': classification, 'result': result})
        save('rag_latency_e2e_regression', results)
        print('e2e', case['id'], classification, flush=True)


save('rag_latency_lab_environment', {'startup_ms': startup_ms, 'threads': torch.get_num_threads(),
    'device': str(engine.llm.model.device), 'attention': engine.llm.model.config._attn_implementation,
    'torch': torch.__version__, 'gpu': torch.cuda.get_device_name(0)})
print('LAB READY', flush=True)
