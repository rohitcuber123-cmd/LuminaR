"""Install in the existing 8005 process after its Qwen/RAG engine loads."""
import asyncio
import logging
import os
from time import perf_counter
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.routing import APIRoute
import httpx
from starlette.concurrency import run_in_threadpool

from assistant.orchestrator import AssistantOrchestrator, enabled
from assistant.qwen import QwenGateway
from assistant.schemas import AssistantRequest, AssistantResponse
from assistant.state import ConversationStore
from assistant.tools import AssistantTools, ToolFailure
from backend.dependencies import get_current_user, security
from assistant.profiling import ProfileMiddleware, current, observe_model, timed


class ProfileRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()
        async def measured(request):
            result = await original(request)
            profile = current.get()
            if profile is not None and 'handler_finished' in profile:
                profile['stages_ms']['response_serialization'] = (
                    perf_counter() - profile.pop('handler_finished')) * 1000
            return result
        return measured


def install_assistant(app, engine, rag_ask, rag_request):
    mode = os.getenv('ASSISTANT_ROUTER_MODE', 'existing_qwen')
    # Router research is frozen. These modes are EXPERIMENTAL / NOT
    # PRODUCTION APPROVED and import only after explicit configuration.
    if mode not in {'existing_qwen','router_v3','router_v3_shadow','router_v4','router_v4_shadow','router_v5'}:
        raise ValueError('Unsupported ASSISTANT_ROUTER_MODE')
    observe_model(engine.llm)
    app.add_middleware(ProfileMiddleware)
    gateway = QwenGateway(engine.llm, engine.inference_lock,
                          timeout=float(os.getenv('ASSISTANT_QWEN_TIMEOUT', '60')), allow_experimental=False)
    app.state.assistant_router_mode = mode
    if mode != 'existing_qwen':
        if mode == 'router_v5':
            from assistant.router_v5.gateway import HybridGateway
        elif mode.startswith('router_v4'):
            from assistant.router_v4 import HybridGateway
        else:
            from assistant.router_v3 import HybridGateway
        gateway.router_variant = ''
        gateway.router_retry = False
        gateway = HybridGateway(gateway, mode)
    orchestrator = AssistantOrchestrator(gateway, ConversationStore())
    app.state.assistant = orchestrator
    # Construct once during installation, before accepting traffic. TLS trust
    # store setup is synchronous (~390ms on this Windows host). Per-request
    # construction blocked the event loop for ~8s at twenty-way concurrency.
    # Headers remain request-local in AssistantTools; this client has no user
    # credentials or shared cookies from the internal bearer-only APIs.
    client = httpx.AsyncClient(timeout=httpx.Timeout(40, connect=3),
                              limits=httpx.Limits(max_connections=40, max_keepalive_connections=20))
    app.state.assistant_http_client = client
    router = APIRouter(prefix='/assistant', tags=['Assistant'], route_class=ProfileRoute)

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

        tools = AssistantTools(client, f'Bearer {credentials.credentials}', rag_callback)
        result = await orchestrator.chat(request, f"{current_user['sub']}:{current_user.get('sid', 'legacy')}", tools)
        profile = current.get()
        if profile is not None:
            profile['handler_finished'] = perf_counter()
            try:
                import psutil
                import torch
                profile['memory'] = {'process_rss_mb': psutil.Process().memory_info().rss / 1048576,
                    'cuda_allocated_mb': torch.cuda.memory_allocated() / 1048576,
                    'cuda_reserved_mb': torch.cuda.memory_reserved() / 1048576}
            except ImportError:
                pass
            # Memory observation is handler work, not response serialization.
            profile['handler_finished'] = perf_counter()
        return result

    app.include_router(router)
    app.router.add_event_handler('shutdown', gateway.close)
    app.router.add_event_handler('shutdown', client.aclose)
    if os.getenv('ASSISTANT_PROFILE_PATH') and getattr(engine.llm, 'model', None) is not None:
        import torch
        import transformers
        runtime = {'attention_backend': engine.llm.model.config._attn_implementation,
            'torch': torch.__version__, 'transformers': transformers.__version__,
            'cuda': torch.version.cuda, 'device': str(engine.llm.model.device),
            'gpu': torch.cuda.get_device_name() if torch.cuda.is_available() else None,
            'flash_available': torch.backends.cuda.is_flash_attention_available(),
            'sdpa_flash_enabled': torch.backends.cuda.flash_sdp_enabled(),
            'sdpa_mem_efficient_enabled': torch.backends.cuda.mem_efficient_sdp_enabled(),
            'model_resident_id': id(engine.llm.model), 'pid': os.getpid()}
        import sys
        import psutil
        process = psutil.Process()
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        runtime.update(router_mode=mode,
            experimental_router_modules=[name for name in sys.modules if name.startswith(
                ('assistant.router_v2', 'assistant.router_v3', 'assistant.router_v4', 'assistant.router_v5'))],
            process_rss_bytes=process.memory_info().rss,
            child_processes=[{'pid': child.pid, 'name': child.name()} for child in process.children(recursive=True)],
            host_available_bytes=memory.available, host_total_bytes=memory.total,
            psutil_swap_used_bytes=swap.used, psutil_swap_total_bytes=swap.total,
            cuda_allocated_bytes=torch.cuda.memory_allocated(), cuda_reserved_bytes=torch.cuda.memory_reserved())
        if os.getenv('ASSISTANT_ROUTER_V2_HARDWARE_AUDIT') == '1':
            # Explicit local experiment observation; no second model or tensors
            # retained, and no changes to RAG generation or device placement.
            runtime['model_footprint_bytes'] = engine.llm.model.get_memory_footprint()
            if torch.cuda.is_available():
                free, total = torch.cuda.mem_get_info(engine.llm.model.device)
                runtime.update(cuda_free_bytes=free, cuda_total_bytes=total,
                    cuda_allocated_bytes=torch.cuda.memory_allocated(engine.llm.model.device),
                    cuda_reserved_bytes=torch.cuda.memory_reserved(engine.llm.model.device))
        try:
            Path(os.environ['ASSISTANT_PROFILE_PATH'] + '.runtime.json').write_text(json.dumps(runtime, indent=2))
        except OSError:
            pass
    logger = logging.getLogger('luminar.assistant')
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
        logger.addHandler(handler)
        logger.propagate = False
    return orchestrator
