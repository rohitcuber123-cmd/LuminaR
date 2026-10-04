"""Temporary loopback-only evaluation adapter sharing the production RAG engine.

Run uvicorn scripts.rag_evaluation_server:app --host 127.0.0.1 --port 8005
in place of rag.api during the evaluation. Restore rag.api afterwards.
No second model, altered evidence, or mock inference is used.
"""
from fastapi import HTTPException, Request
from pydantic import BaseModel
from rag.api import app, engine, document_service
from rag.telemetry import profile_request
from rag.qa import DEPTH_CONFIG


class EvaluationRequest(BaseModel):
    operation: str
    question: str = ''
    document_id: str | None = None
    work_id: str | None = None
    intent_data: dict | None = None
    evidence: list[dict] | None = None
    original_intent: bool = False
    attention: str | None = None
    top_k: int = 5
    compact_prompt: bool | None = None
    max_tokens: int | None = None


@profile_request
def evaluate(body):
    with engine.inference_lock:
        previous = engine.llm.model.config._attn_implementation
        previous_compact = engine.compact_prompt
        previous_tokens = DEPTH_CONFIG['normal']['max_tokens']
        try:
            if body.compact_prompt is not None:
                engine.compact_prompt = body.compact_prompt
            if body.max_tokens is not None:
                if body.max_tokens not in (128, 192, 256, 320, 600):
                    raise ValueError('Unsupported token ablation value')
                DEPTH_CONFIG['normal']['max_tokens'] = body.max_tokens
            if body.attention is not None:
                if body.attention not in ('sdpa', 'luminar_sdpa'):
                    raise ValueError('Unknown attention implementation')
                engine.llm.model.set_attn_implementation(body.attention)
            if body.operation == 'intent':
                fn = engine.llm._analyze_intent_uncached if body.original_intent else engine.llm.analyze_intent
                return {'intent_data': fn(body.question)}
            if body.operation == 'retrieve':
                return engine.reranker.search(body.question, top_k=body.top_k,
                    work_id=body.work_id, document_id=body.document_id, intent_data=body.intent_data or {})
            if body.operation == 'validate':
                return engine.llm.validate_evidence(body.question, body.intent_data or {}, body.evidence or [], mode='top-3-comb')
            if body.operation == 'ask':
                return engine.ask(body.question, document_id=body.document_id, work_id=body.work_id)
            if body.operation == 'diagnostics':
                return {'attention': engine.llm.model.config._attn_implementation,
                        'shared_embedding': document_service.model is engine.reranker.retriever.model,
                        'parameter_devices': sorted({str(p.device) for p in engine.llm.model.parameters()})}
            raise ValueError('Unknown evaluation operation')
        finally:
            engine.llm.model.set_attn_implementation(previous)
            engine.compact_prompt = previous_compact
            DEPTH_CONFIG['normal']['max_tokens'] = previous_tokens


@app.post('/__latency/evaluate')
def evaluation_endpoint(body: EvaluationRequest, request: Request):
    if request.client is None or request.client.host not in ('127.0.0.1', '::1'):
        raise HTTPException(403, 'Evaluation is loopback-only')
    return evaluate(body)
