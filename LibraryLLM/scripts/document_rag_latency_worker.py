"""Loopback-only experiment controls; never installed in the production app."""
import sys
from pathlib import Path
from contextvars import ContextVar
from functools import wraps
import hashlib
import json
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rag.api import app, engine
# A production installation may already exist. Experimental baseline always
# captures the original engine methods, without loading another model.
installed = getattr(engine, '_document_latency', None)
if installed is not None:
    engine.ask = installed.original_ask
    engine.llm.analyze_intent = installed.original_analyze
    engine.build_prompt = installed.original_prompt
    engine.llm.generate = installed.original_generate
    del engine._document_latency
from assistant.profiling import current
from rag.llm import SYSTEM_MESSAGE
from fastapi import HTTPException
from pydantic import BaseModel

trace = ContextVar('document_experiment_trace', default=None)
observations = ROOT / 'reports/document_rag_observations.jsonl'
original_ask = engine.ask

@wraps(original_ask)
def ask(*args, **kwargs):
    profile = current.get()
    row = {'trace_id': profile['trace_id'] if profile else None, 'retrieval': [],
           'validation': [], 'generations': [], 'prompts': []}
    token = trace.set(row)
    try:
        return original_ask(*args, **kwargs)
    finally:
        if row['trace_id']:
            with observations.open('a', encoding='utf-8') as f:
                f.write(json.dumps(row) + '\n')
        trace.reset(token)
engine.ask = ask

search = engine.reranker.search
@wraps(search)
def observed_search(*args, **kwargs):
    result = search(*args, **kwargs)
    row = trace.get()
    if row is not None:
        row['retrieval'].append({'intent_data': kwargs.get('intent_data'),
            'chunk_ids': [i['chunk_id'] for i in result['results']],
            'scores': [i['final_score'] for i in result['results']],
            'candidate_count': result['candidate_count'], 'timing_ms': result['timing_ms']})
    return result
engine.reranker.search = observed_search

validator = engine.llm.validate_evidence
@wraps(validator)
def observed_validator(question, intent_data, used_items, **kwargs):
    result = validator(question, intent_data, used_items, **kwargs)
    row = trace.get()
    if row is not None:
        mode = kwargs.get('mode', 'top-1')
        checked = used_items[:3] if mode == 'top-3-comb' else used_items[:1]
        row['validation'].append({'chunk_ids': [i['chunk_id'] for i in checked],
                                  'intent_data': intent_data, 'result': result, 'mode': mode})
    return result
engine.llm.validate_evidence = observed_validator

generate = engine.llm.generate
@wraps(generate)
def observed_generate(prompt, **kwargs):
    row = trace.get()
    purpose = ('semantic' if kwargs.get('max_new_tokens') in (180, 400) else 'validation') if kwargs.get('prefix_allowed_tokens_fn') else 'answer'
    if row is not None:
        tokenizer = engine.llm.tokenizer
        formatted = tokenizer.apply_chat_template([{'role':'system','content':SYSTEM_MESSAGE},
            {'role':'user','content':prompt}], tokenize=False, add_generation_prompt=True)
        prompt_row = {'purpose': purpose, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                      'formatted_tokens': len(tokenizer.encode(formatted, add_special_tokens=False)),
                      'system_tokens': len(tokenizer.encode(SYSTEM_MESSAGE, add_special_tokens=False))}
        if purpose == 'answer':
            # Counts only; evidence is never saved in the metrics file.
            for label, start, end in [('evidence','CONTEXT:','QUESTION:'),('evidence_compact','SOURCES:','QUESTION:')]:
                if start in prompt and end in prompt:
                    body = prompt.split(start,1)[1].rsplit(end,1)[0]
                    prompt_row[label+'_tokens'] = len(tokenizer.encode(body, add_special_tokens=False))
        row['prompts'].append(prompt_row)
    started = time.perf_counter()
    result = generate(prompt, **kwargs)
    if row is not None:
        row['generations'].append({'purpose': purpose, 'wall_ms': (time.perf_counter()-started)*1000,
                                  'output_tokens': len(engine.llm.tokenizer.encode(result, add_special_tokens=False))})
    return result
engine.llm.generate = observed_generate
BASE_METHODS={'ask':engine.ask,'analyze':engine.llm.analyze_intent,
              'prompt':engine.build_prompt,'generate':engine.llm.generate}

class Control(BaseModel):
    mode: str
    semantic_cap: int = 400
    reload_candidate: bool = False

@app.post('/__document_latency/control')
def control(request: Control):
    if request.mode not in {'baseline', 'answer_only', 'fast', 'cache'}:
        raise HTTPException(400, 'Unknown experiment mode')
    with engine.inference_lock:
        import importlib
        import rag.document_latency as candidate
        if request.reload_candidate:
            engine.ask=BASE_METHODS['ask']
            engine.llm.analyze_intent=BASE_METHODS['analyze']
            engine.build_prompt=BASE_METHODS['prompt']
            engine.llm.generate=BASE_METHODS['generate']
            if hasattr(engine,'_document_latency'):del engine._document_latency
            candidate=importlib.reload(candidate)
        controller = candidate.install_document_latency(engine, mode=request.mode)
        if not 180 <= request.semantic_cap <= 400:
            raise HTTPException(400, 'Unsafe experiment cap')
        controller.semantic_cap = request.semantic_cap
        controller.clear_cache()
    return {'mode': request.mode, 'pid': __import__('os').getpid(), 'model_id': id(engine.llm.model)}
