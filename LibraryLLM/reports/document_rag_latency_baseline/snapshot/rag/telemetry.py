"""Request-local timings; never store prompts or documents in shared metrics."""
from contextvars import ContextVar
from functools import wraps
from time import perf_counter

_metrics = ContextVar('rag_metrics', default=None)


def stage(name):
    def decorate(fn):
        @wraps(fn)
        def measured(*args, **kwargs):
            start = perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                metrics = _metrics.get()
                if metrics is not None:
                    metrics[name + '_ms'] = metrics.get(name + '_ms', 0) + (perf_counter() - start) * 1000
                    metrics[name + '_calls'] = metrics.get(name + '_calls', 0) + 1
        return measured
    return decorate


def record_generation(input_tokens, generated_tokens, max_new_tokens, elapsed):
    metrics = _metrics.get()
    if metrics is not None:
        metrics['llm_calls'].append({
            'input_tokens': input_tokens, 'generated_tokens': generated_tokens,
            'max_new_tokens': max_new_tokens, 'generation_ms': elapsed * 1000,
            'tokens_per_second': generated_tokens / elapsed if elapsed else 0})


def profile_request(fn):
    @wraps(fn)
    def measured(*args, **kwargs):
        metrics = {'llm_calls': []}
        token = _metrics.set(metrics)
        start = perf_counter()
        try:
            result = fn(*args, **kwargs)
            metrics['total_ms'] = (perf_counter() - start) * 1000
            if 'profile' in result:
                result['profile']['outer_total_ms'] = metrics['total_ms']
            else:
                result['profile'] = metrics
            return result
        finally:
            _metrics.reset(token)
    return measured


def serialized_inference(fn):
    @wraps(fn)
    def serialized(self, *args, **kwargs):
        start = perf_counter()
        with self.inference_lock:
            metrics = _metrics.get()
            if metrics is not None:
                metrics['queue_ms'] = (perf_counter() - start) * 1000
            return fn(self, *args, **kwargs)
    return serialized
