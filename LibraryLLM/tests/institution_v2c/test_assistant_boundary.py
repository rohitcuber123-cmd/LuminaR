import asyncio
from types import SimpleNamespace
from uuid import uuid4
import pytest
from assistant.orchestrator import AssistantOrchestrator
from assistant.schemas import AssistantRequest
from assistant.state import ConversationStore
from assistant.tools import AssistantLoanTool, AssistantReservationTool, AssistantFeeTool
from test_reservations_fees import setup, cmd, call, issue, reserve, get, fee_fixture


@pytest.mark.parametrize('cancel', [False, True])
def test_assistant_immutable_scoped_reservation_confirmation(client, setup, monkeypatch, cancel):
    lib, book = setup; issue(client, lib, book); row = reserve(client, lib, book) if cancel else None
    calls = []
    class Transport:
        async def call(self, service, method, path, **kwargs):
            calls.append((method, path, kwargs))
            r = client.request(method, path, json=kwargs.get('json'), params=kwargs.get('params'), headers={'x-test-user': '3'})
            assert r.is_success, r.text
            return r.json()
    transport = Transport(); tools = SimpleNamespace(loans=AssistantLoanTool(transport), reservations=AssistantReservationTool(transport), fees=AssistantFeeTool(transport))
    orchestrator = AssistantOrchestrator(None, ConversationStore()); monkeypatch.setenv('ASSISTANT_MUTATING_ACTIONS_ENABLED', 'true')
    async def run():
        proposed = await orchestrator.chat(AssistantRequest(message='Please reserve', action='CANCEL_LIBRARY_RESERVATION' if cancel else 'RESERVE_LIBRARY_BOOK',
            lending_context={'library_id': lib, 'library_book_id': book, **({'reservation_id': row['reservation_id']} if row else {})}), 'user-3', tools)
        assert proposed.pending_action and not any(c[0] == 'POST' for c in calls)
        confirmed = await orchestrator.chat(AssistantRequest(message='Confirm', action='CONFIRM_ACTION', pending_action_id=proposed.pending_action.action_id,
            conversation_id=proposed.conversation_id, lending_context={'library_id': str(uuid4()), 'library_book_id': str(uuid4()), 'reservation_id': str(uuid4())}), 'user-3', tools)
        assert not confirmed.errors and ('cancelled' if cancel else 'waiting queue') in confirmed.message
        assert calls[-1][1].startswith(f'/libraries/{lib}/reservations')
        replay = await orchestrator.chat(AssistantRequest(message='Confirm', action='CONFIRM_ACTION', conversation_id=proposed.conversation_id, pending_action_id=proposed.pending_action.action_id), 'user-3', tools)
        assert replay.clarification
    asyncio.run(run())


def test_assistant_fees_use_own_library_endpoint_and_no_staff_tools(client, setup, database):
    lib, fee = fee_fixture(client, setup, database); calls = []
    class Transport:
        async def call(self, service, method, path, **kwargs):
            calls.append((method, path))
            return client.request(method, path, params=kwargs.get('params'), headers={'x-test-user': '2'}).json()
    tool = AssistantFeeTool(Transport()); result = asyncio.run(tool.library_fees(lib))
    assert result['library_id'] == lib and result['results'][0]['fee_id'] == fee['fee_id']
    assert calls == [('GET', f'/libraries/{lib}/reservations-fees/config'), ('GET', f'/libraries/{lib}/me/fees')]
    assert not any(hasattr(tool, method) for method in ['waive', 'adjust', 'pay', 'payments'])
