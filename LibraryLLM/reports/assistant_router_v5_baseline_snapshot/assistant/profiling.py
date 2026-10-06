"""Numeric request-local observations. Never collect prompts, tokens or account data."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import json
import os
from pathlib import Path
from time import perf_counter
from uuid import uuid4

current = ContextVar('assistant_profile', default=None)
generation_stage = ContextVar('assistant_generation_stage', default='rag')


@contextmanager
def timed(name):
    start = perf_counter()
    try:
        yield
    finally:
        profile = current.get()
        if profile is not None:
            stages = profile['stages_ms']
            stages[name] = stages.get(name, 0) + (perf_counter() - start) * 1000


def measured(name):
    def decorate(fn):
        @wraps(fn)
        async def call(*args, **kwargs):
            with timed(name):
                return await fn(*args, **kwargs)
        return call
    return decorate


def observe_model(llm):
    """Observe exact formatted input and output tensor lengths, including EOS.

    Install once on the injected model; no loaders, altered settings or tensors
    retained. Context propagates to assistant executor and existing RAG worker.
    """
    model = getattr(llm, 'model', None)
    if model is None or getattr(model, '_assistant_observed', False):
        return
    original = model.generate

    @wraps(original)
    def generate(*args, **kwargs):
        profile = current.get()
        if profile is None:
            return original(*args, **kwargs)
        row = {'stage': generation_stage.get(), 'input_tokens': 0,
               'generated_tokens': 0, 'max_new_tokens': kwargs.get('max_new_tokens')}
        inputs = kwargs.get('input_ids', args[0] if args else None)
        if inputs is not None:
            row['input_tokens'] = int(inputs.shape[-1])
        profile['qwen_calls'].append(row)
        start = perf_counter()
        try:
            output = original(*args, **kwargs)
            sequences = getattr(output, 'sequences', output)
            row['generated_tokens'] = int(sequences.shape[-1]) - row['input_tokens']
            return output
        finally:
            row['generation_ms'] = (perf_counter() - start) * 1000
    model.generate = generate
    model._assistant_observed = True


class ProfileMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('path') != '/assistant/chat':
            return await self.app(scope, receive, send)
        profile = {'trace_id': uuid4().hex, 'stages_ms': {}, 'qwen_calls': []}
        token = current.set(profile)
        start = perf_counter()
        async def observed_send(message):
            if message['type'] == 'http.response.start':
                profile['status'] = message['status']
                message['headers'].append((b'x-assistant-trace', profile['trace_id'].encode()))
            await send(message)
        try:
            await self.app(scope, receive, observed_send)
        finally:
            profile['total_ms'] = (perf_counter() - start) * 1000
            profile['qwen_call_count'] = len(profile['qwen_calls'])
            profile['route_resolution_ms'] = profile['stages_ms'].get('intent_routing', 0) + profile['stages_ms'].get('intent_parsing', 0)
            profile['qwen_intent_calls'] = sum(c['stage'] in ('intent', 'repair', 'semantic_retry') for c in profile['qwen_calls'])
            profile['qwen_response_calls'] = sum(c['stage'] == 'response' for c in profile['qwen_calls'])
            profile['tool_ms'] = profile['stages_ms'].get('tool_execution', 0)
            for stage, name in [('intent', 'qwen_intent_generation'), ('response', 'qwen_response_generation'),
                                ('rag', 'qwen_rag_generation')]:
                profile['stages_ms'][name] = sum(c.get('generation_ms', 0) for c in profile['qwen_calls']
                                                if c['stage'] == stage or stage == 'intent' and c['stage'] in ('repair','semantic_retry'))
            if profile.get('router_v2'):
                profile['router_v2'].update(tool_ms=profile['tool_ms'],total_ms=profile['total_ms'],
                    qwen_calls=profile['qwen_call_count'])
            if profile.get('router_v3'):
                profile['router_v3'].update(tool_ms=profile['tool_ms'],total_ms=profile['total_ms'],
                    qwen_calls=profile['qwen_call_count'])
            if profile.get('router_v4'):
                profile['router_v4'].update(tool_ms=profile['tool_ms'],total_ms=profile['total_ms'],
                    qwen_calls=profile['qwen_call_count'])
            path = os.getenv('ASSISTANT_PROFILE_PATH')
            if path:
                # Opt-in local development sink; payload contains numeric metrics only.
                try:
                    with Path(path).open('a', encoding='utf-8') as handle:
                        handle.write(json.dumps(profile) + '\n')
                except OSError:
                    # Optional observability must not turn a successful request
                    # into an error when a development log path is unavailable.
                    pass
            current.reset(token)
