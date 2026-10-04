"""Install in the existing 8005 process after its Qwen/RAG engine loads."""
import asyncio
import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import httpx
from starlette.concurrency import run_in_threadpool

from assistant.orchestrator import AssistantOrchestrator, enabled
from assistant.qwen import QwenGateway
from assistant.schemas import AssistantRequest, AssistantResponse
from assistant.state import ConversationStore
from assistant.tools import AssistantTools, ToolFailure
from backend.dependencies import get_current_user, security


def install_assistant(app, engine, rag_ask, rag_request):
    gateway = QwenGateway(engine.llm, engine.inference_lock,
                          timeout=float(os.getenv('ASSISTANT_QWEN_TIMEOUT', '60')))
    orchestrator = AssistantOrchestrator(gateway, ConversationStore())
    app.state.assistant = orchestrator
    router = APIRouter(prefix='/assistant', tags=['Assistant'])

    @router.post('/chat', response_model=AssistantResponse)
    async def chat(request: AssistantRequest,
                   current_user=Depends(get_current_user),
                   credentials: HTTPAuthorizationCredentials = Depends(security)):
        if not enabled('ASSISTANT_ENABLED', True):
            raise HTTPException(503, 'Assistant is disabled.')

        async def rag_callback(message, work_id=None, document_id=None):
            try:
                return await asyncio.wait_for(run_in_threadpool(
                    rag_ask, rag_request(query=message, work_id=work_id, document_id=document_id), credentials),
                    timeout=float(os.getenv('ASSISTANT_RAG_TIMEOUT', '120')))
            except HTTPException as exc:
                raise ToolFailure('rag', f'HTTP_{exc.status_code}',
                                  exc.detail if exc.status_code < 500 else 'RAG is unavailable.') from exc
            except Exception as exc:
                raise ToolFailure('rag', 'RAG_UNAVAILABLE', 'RAG could not complete this question.') from exc

        async with httpx.AsyncClient(timeout=httpx.Timeout(40, connect=3),
                                     limits=httpx.Limits(max_connections=20)) as client:
            tools = AssistantTools(client, f'Bearer {credentials.credentials}', rag_callback)
            return await orchestrator.chat(request, str(current_user['sub']), tools)

    app.include_router(router)
    app.router.add_event_handler('shutdown', gateway.close)
    logger = logging.getLogger('luminar.assistant')
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
        logger.addHandler(handler)
        logger.propagate = False
    return orchestrator
