"""Fixed-token A/B experiments on a caller's already-loaded real Qwen."""
import contextlib
import json
import time
from pathlib import Path
import torch
from rag.attention import install_compatible_sdpa


def compare_attention(engine, prompt, log):
    rows = []
    for mode in ['sdpa', 'luminar_sdpa']:
        if mode == 'sdpa':
            engine.llm.model.set_attn_implementation('sdpa')
        else:
            install_compatible_sdpa(engine.llm.model)
        for repeat in range(3):
            start = time.perf_counter()
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                answer = engine.llm.generate(prompt, max_new_tokens=20)
            rows.append({'attention': mode, 'repeat': repeat,
                         'elapsed_ms': (time.perf_counter() - start) * 1000,
                         'answer': answer})
            Path('reports/rag_attention_fixed_token_comparison.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
            print('fixed-token', mode, repeat, round(rows[-1]['elapsed_ms']), flush=True)


def compare_compute_dtype(engine, prompt, log):
    layers = [m for m in engine.llm.model.modules() if type(m).__name__ == 'Linear4bit']
    original = [m.compute_dtype for m in layers]
    rows = []
    try:
        for dtype in [torch.float16, torch.bfloat16]:
            for layer in layers:
                layer.compute_dtype = dtype
            for repeat in range(3):
                start = time.perf_counter()
                with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    answer = engine.llm.generate(prompt, max_new_tokens=20)
                rows.append({'compute_dtype': str(dtype), 'repeat': repeat,
                             'elapsed_ms': (time.perf_counter() - start) * 1000, 'answer': answer})
                Path('reports/rag_compute_dtype_comparison.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
                print('dtype', str(dtype), repeat, round(rows[-1]['elapsed_ms']), flush=True)
    finally:
        for layer, dtype in zip(layers, original):
            layer.compute_dtype = dtype


def compare_inference_mode(engine, prompt, log):
    rows = []
    for enabled in [False, True]:
        for repeat in range(3):
            start = time.perf_counter()
            with torch.inference_mode(enabled), contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                answer = engine.llm.generate(prompt, max_new_tokens=20)
            rows.append({'inference_mode': enabled, 'repeat': repeat,
                         'elapsed_ms': (time.perf_counter() - start) * 1000, 'answer': answer})
            Path('reports/rag_inference_mode_comparison.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
            print('inference_mode', enabled, repeat, round(rows[-1]['elapsed_ms']), flush=True)


def compare_embedding_reuse(engine, log):
    import gc
    from rag.services.document_service import DocumentService
    rows = []
    for shared in [False, True]:
        before = torch.cuda.memory_allocated()
        start = time.perf_counter()
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            service = DocumentService(embedding_model=engine.reranker.retriever.model if shared else None)
        rows.append({'shared': shared, 'initialization_ms': (time.perf_counter() - start) * 1000,
                     'extra_gpu_mb': (torch.cuda.memory_allocated() - before) / 2**20,
                     'same_model': service.model is engine.reranker.retriever.model})
        del service
        gc.collect()
    Path('reports/rag_embedding_reuse_comparison.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    print(rows, flush=True)
