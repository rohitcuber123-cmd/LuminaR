"""Production mutation, configuration and transport contracts; no router corpora."""
import asyncio
import builtins
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
import httpx
import pytest
from pydantic import ValidationError

from assistant.api import install_assistant
from assistant.orchestrator import AssistantOrchestrator
from assistant.qwen import QwenGateway, QwenUnavailable
from assistant.schemas import AssistantIntent, AssistantRequest, Intent
from assistant.state import ConversationStore
from backend.dependencies import get_current_user
from test_assistant_part3 import FakeTools, FakeQwen

ADD = Intent.ADD_TO_READING_LIST
REMOVE = Intent.REMOVE_FROM_READING_LIST

def fixture(intent=ADD, present=False):
    tools = FakeTools(rl_items=[{'work_id': 'OL1W'}] if present else [])
    qwen = FakeQwen(AssistantIntent(intent=intent, confidence=1))
    return AssistantOrchestrator(qwen, ConversationStore()), tools

def call(orch, tools, owner='17:session-a', **kwargs):
    return asyncio.run(orch.chat(AssistantRequest(message='Reading list request', **kwargs), owner, tools))

def propose(orch, tools, action=None):
    return call(orch, tools, selected_work_ids=['OL1W'], **({'action': action} if action else {}))

def confirm(orch, tools, pending, **kwargs):
    return call(orch, tools, conversation_id=pending.conversation_id,
                pending_action_id=pending.pending_action.action_id, action='CONFIRM_ACTION', **kwargs)

def test_assistant_reading_list_add_creates_pending_action():
    orch, tools = fixture()
    result = propose(orch, tools)
    assert result.pending_action.type == ADD
    assert result.pending_action.work_id == 'OL1W'
    assert result.pending_action.requires_confirmation and 'Add Dracula' in result.message
    assert {a.type.value for a in result.actions} == {'CONFIRM_ACTION', 'CANCEL_ACTION'}

def test_assistant_reading_list_add_does_not_write_before_confirm():
    orch, tools = fixture()
    assert propose(orch, tools).pending_action
    assert tools.reading_list.added == []

def test_assistant_reading_list_add_confirm_writes():
    orch, tools = fixture()
    pending = propose(orch, tools)
    assert not confirm(orch, tools, pending).errors
    assert tools.reading_list.added == ['OL1W']
    assert confirm(orch, tools, pending).clarification
    assert tools.reading_list.added == ['OL1W']

def test_assistant_reading_list_add_cancel_no_write():
    cancellation(ADD)

def test_assistant_reading_list_remove_creates_pending_action():
    orch, tools = fixture(REMOVE, present=True)
    result = propose(orch, tools)
    assert result.pending_action.type == REMOVE and 'Remove Dracula' in result.message

def test_assistant_reading_list_remove_does_not_write_before_confirm():
    orch, tools = fixture(REMOVE, present=True)
    assert propose(orch, tools).pending_action and tools.reading_list.removed == []

def test_assistant_reading_list_remove_confirm_writes():
    orch, tools = fixture(REMOVE, present=True)
    pending = propose(orch, tools)
    assert not confirm(orch, tools, pending).errors
    assert tools.reading_list.removed == ['OL1W']

def test_assistant_reading_list_remove_cancel_no_write():
    cancellation(REMOVE)

def cancellation(intent):
    orch, tools = fixture(intent, present=True)
    pending = propose(orch, tools)
    result = call(orch, tools, conversation_id=pending.conversation_id, action='CANCEL_ACTION',
                  pending_action_id=pending.pending_action.action_id)
    assert 'cancelled' in result.message and not tools.reading_list.added and not tools.reading_list.removed
    assert confirm(orch, tools, pending).clarification

def test_reading_list_confirmation_wrong_user_rejected():
    ownership('18:session-b')

def test_reading_list_confirmation_wrong_session_rejected():
    ownership('17:session-b')

def ownership(owner):
    orch, tools = fixture()
    pending = propose(orch, tools)
    with pytest.raises(HTTPException) as exc:
        confirm(orch, tools, pending, owner=owner)
    assert exc.value.status_code == 404 and not tools.reading_list.added
    assert not confirm(orch, tools, pending).errors  # Unauthorized attempt doesn't consume A's action.

def test_reading_list_confirmation_wrong_conversation_rejected():
    orch, tools = fixture()
    pending = propose(orch, tools)
    other = orch.store.get(None, '17:session-a')
    result = call(orch, tools, conversation_id=other.conversation_id, action='CONFIRM_ACTION',
                  pending_action_id=pending.pending_action.action_id)
    assert result.clarification and not tools.reading_list.added

def test_reading_list_confirmation_expired_rejected():
    orch, tools = fixture()
    pending = propose(orch, tools)
    state = orch.store.get(pending.conversation_id, '17:session-a')
    state.pending_deadline = 0
    assert confirm(orch, tools, pending).clarification and not tools.reading_list.added
    assert state.pending is None

def test_pending_reading_list_target_immutable():
    orch, tools = fixture()
    pending = propose(orch, tools)
    with pytest.raises(ValidationError):
        pending.pending_action.work_id = 'OL2W'
    result = confirm(orch, tools, pending, selected_work_ids=['OL2W'], action_work_ids=['OL2W'])
    assert not result.errors and tools.reading_list.added == ['OL1W']

def test_confirm_does_not_call_qwen():
    orch, tools = fixture()
    pending = propose(orch, tools)
    orch.qwen.parse = AsyncMock(side_effect=AssertionError('Confirmation must not route'))
    orch.qwen.respond = AsyncMock(side_effect=AssertionError('Confirmation must not generate'))
    assert not confirm(orch, tools, pending).errors
    orch.qwen.parse.assert_not_awaited()
    orch.qwen.respond.assert_not_awaited()

def test_add_already_present_idempotent():
    orch, tools = fixture()
    pending = propose(orch, tools)
    tools.reading_list._items = [{'work_id': 'OL1W'}]  # Changed since proposal.
    result = confirm(orch, tools, pending)
    assert 'Already' in result.message and not tools.reading_list.added

def test_remove_absent_idempotent():
    orch, tools = fixture(REMOVE, present=True)
    pending = propose(orch, tools)
    tools.reading_list._items = []
    result = confirm(orch, tools, pending)
    assert 'No longer' in result.message and not tools.reading_list.removed

def test_catalogue_disappeared_after_proposal_no_write():
    orch, tools = fixture()
    pending = propose(orch, tools)
    from assistant.tools import ToolFailure
    tools.catalogue.books = AsyncMock(side_effect=ToolFailure('core', 'HTTP_404', 'Book not found'))
    assert confirm(orch, tools, pending).errors and not tools.reading_list.added
    assert confirm(orch, tools, pending).clarification

def test_new_message_invalidates_pending_reading_list():
    orch, tools = fixture()
    pending = propose(orch, tools)
    call(orch, tools, conversation_id=pending.conversation_id, action='USER_FEES')
    assert confirm(orch, tools, pending).clarification and not tools.reading_list.added

def test_pending_batch_targets_all_validated_before_write():
    orch, tools = fixture()
    pending = call(orch, tools, action='ADD_TO_READING_LIST', selected_work_ids=['OL1W', 'OL2W'])
    assert pending.pending_action.work_ids == ('OL1W', 'OL2W') and not tools.reading_list.added
    assert not confirm(orch, tools, pending, selected_work_ids=['OL3W']).errors
    assert tools.reading_list.added == ['OL1W', 'OL2W']

def test_batch_missing_second_book_performs_zero_writes():
    orch, tools = fixture()
    pending = call(orch, tools, action='ADD_TO_READING_LIST', selected_work_ids=['OL1W', 'OL2W'])
    from assistant.tools import ToolFailure
    tools.catalogue.books = AsyncMock(side_effect=ToolFailure('core', 'HTTP_404', 'Book not found'))
    assert confirm(orch, tools, pending).errors and not tools.reading_list.added

def test_concurrent_reading_list_confirmations_write_once():
    orch, tools = fixture()
    pending = propose(orch, tools)
    request = AssistantRequest(message='Confirm', action='CONFIRM_ACTION', conversation_id=pending.conversation_id,
                               pending_action_id=pending.pending_action.action_id)
    async def exercise():
        return await asyncio.gather(*(orch.chat(request, '17:session-a', tools) for _ in range(2)))
    results = asyncio.run(exercise())
    assert sum(bool(r.clarification) for r in results) == 1 and tools.reading_list.added == ['OL1W']

def test_reading_list_timeout_consumes_action_without_retry():
    orch, tools = fixture()
    pending = propose(orch, tools)
    from assistant.tools import ToolFailure
    tools.reading_list.add = AsyncMock(side_effect=ToolFailure('core', 'TIMEOUT'))
    assert confirm(orch, tools, pending).errors
    assert confirm(orch, tools, pending).clarification
    tools.reading_list.add.assert_awaited_once()

def installed(monkeypatch, mode=None):
    monkeypatch.delenv('ASSISTANT_PROFILE_PATH', raising=False)
    if mode is None:
        monkeypatch.delenv('ASSISTANT_ROUTER_MODE', raising=False)
    else:
        monkeypatch.setenv('ASSISTANT_ROUTER_MODE', mode)
    app = FastAPI()
    engine = SimpleNamespace(llm=SimpleNamespace(), inference_lock=RLock())
    orch = install_assistant(app, engine, lambda *args: {}, lambda **kw: kw)
    return app, orch

def test_missing_router_mode_uses_existing_qwen(monkeypatch):
    app, orch = installed(monkeypatch)
    with TestClient(app):
        assert app.state.assistant_router_mode == 'existing_qwen' and type(orch.qwen) is QwenGateway

@pytest.mark.parametrize('version', ['v2', 'v3', 'v4', 'v5'])
def test_rejected_router_not_loaded_in_default_mode(monkeypatch, version):
    original = builtins.__import__
    def reject(name, *args, **kwargs):
        if name.startswith('assistant.router_' + version):
            raise AssertionError('Rejected router imported at default startup')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', reject)
    app, orch = installed(monkeypatch)
    with TestClient(app):
        assert type(orch.qwen) is QwenGateway

@pytest.mark.parametrize('mode', ['newest', '', 'router_v6'])
def test_invalid_router_mode_safe_behavior(monkeypatch, mode):
    monkeypatch.setenv('ASSISTANT_ROUTER_MODE', mode)
    with pytest.raises(ValueError, match='Unsupported ASSISTANT_ROUTER_MODE'):
        install_assistant(FastAPI(), SimpleNamespace(), None, None)

def test_stale_v2_flags_cannot_override_production_mode(monkeypatch):
    monkeypatch.setenv('ASSISTANT_ROUTER_V2_VARIANT', 'E2')
    monkeypatch.setenv('ASSISTANT_ROUTER_V2_RETRY', 'true')
    app, orch = installed(monkeypatch)
    with TestClient(app):
        assert orch.qwen.router_variant == '' and orch.qwen.router_retry is False

def transport_app(monkeypatch):
    requests = []
    real_client = httpx.AsyncClient
    clients = []
    async def backend(request):
        await asyncio.sleep(.01)
        requests.append(request.headers['authorization'])
        return httpx.Response(200, json={'total_unpaid': 2 if request.headers['authorization'] == 'Bearer b' else 0})
    def factory(**kwargs):
        client = real_client(transport=httpx.MockTransport(backend), **kwargs)
        clients.append(client)
        return client
    monkeypatch.setattr('assistant.api.httpx.AsyncClient', factory)
    app, orch = installed(monkeypatch)
    def identity(request: Request):
        return {'sub': '18' if request.headers['authorization'] == 'Bearer b' else '17', 'sid': 'test'}
    app.dependency_overrides[get_current_user] = identity
    orch.qwen.parse = AsyncMock(side_effect=AssertionError('Structured fees need no Qwen'))
    return app, clients, requests

def send_fee(client, token):
    return client.post('/assistant/chat', headers={'Authorization': 'Bearer ' + token},
                       json={'message': 'Fees', 'action': 'USER_FEES'})

def test_shared_http_client_created_once(monkeypatch):
    app, clients, _ = transport_app(monkeypatch)
    with TestClient(app) as client:
        assert send_fee(client, 'a').status_code == 200
        assert len(clients) == 1 and clients[0] is app.state.assistant_http_client

def test_requests_reuse_http_client(monkeypatch):
    app, clients, headers = transport_app(monkeypatch)
    with TestClient(app) as client:
        for token in ['a', 'b', 'a']:
            assert send_fee(client, token).json()['account']['total_unpaid'] == (2 if token == 'b' else 0)
        assert len(clients) == 1 and headers == ['Bearer a', 'Bearer b', 'Bearer a']

def test_request_auth_headers_not_shared(monkeypatch):
    app, clients, headers = transport_app(monkeypatch)
    with TestClient(app) as client:
        send_fee(client, 'private-a')
        assert 'authorization' not in clients[0].headers
        send_fee(client, 'private-b')
        assert headers == ['Bearer private-a', 'Bearer private-b']

def test_concurrent_users_keep_auth_headers_isolated(monkeypatch):
    app, clients, headers = transport_app(monkeypatch)
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(send_fee, client, token) for token in ['a', 'b']]
        assert [f.result().json()['account']['total_unpaid'] for f in futures] == [0, 2]
        assert sorted(headers) == ['Bearer a', 'Bearer b'] and 'authorization' not in clients[0].headers

def test_http_client_closed_on_shutdown(monkeypatch):
    app, clients, _ = transport_app(monkeypatch)
    with TestClient(app):
        assert not clients[0].is_closed
    assert clients[0].is_closed

def test_qwen_busy_does_not_block_explicit_actions(monkeypatch):
    app, orch = installed(monkeypatch)
    with TestClient(app):
        orch.qwen.slot.acquire()
        try:
            with pytest.raises(QwenUnavailable, match='busy'):
                asyncio.run(orch.qwen.generate('Reasoning request'))
            result = asyncio.run(orch.chat(AssistantRequest(message='Fees', action='USER_FEES'), '17', FakeTools()))
            assert result.account['total_unpaid'] == 5 and not result.errors
        finally:
            orch.qwen.slot.release()
