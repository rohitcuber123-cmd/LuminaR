import asyncio
from types import SimpleNamespace
from uuid import uuid4
import pytest
from assistant.orchestrator import AssistantOrchestrator
from assistant.schemas import AssistantRequest
from assistant.state import ConversationStore
from assistant.tools import AssistantLoanTool
from tests.institution_v2b.test_lending import cmd, request, issued, review, avail, setup


def test_legacy_bypass_rejected_after_activation(client, setup, database):
    lib, book = setup
    assert client.post('/issues/issue', json={'work_id': 'OL-Networks'}, headers={'x-test-user': '2'}).status_code == 410
    database.institution_library_aliases.insert_one({'canonical_library_id': lib, 'legacy_library_id': 'LIB001'})
    assert client.post('/issues/issue', json={'work_id': 'OL-Networks'}, headers={'x-test-user': '30'}).status_code == 410


def test_canonical_metadata_creation_receipts(client, setup, database):
    lib, book = setup; path = f'/libraries/{lib}/inventory/books'; body = cmd(title='A second local book', subjects=['Lab'])
    row = client.post(path, json=body); assert row.status_code == 201, row.text
    assert client.post(path, json=body).json()['library_book_id'] == row.json()['library_book_id']
    assert client.post(path, json={'title': 'x', 'subjects': ['x']}).status_code == 422
    assert client.post(path, json=cmd(title='x', subjects=['x'], available_copies=1)).status_code == 422
    patch = cmd(shelf_location='North 3', title='Revised local title')
    assert client.patch(path + f'/{book}', json=patch).status_code == 200
    assert client.patch(path + f'/{book}', json=patch).status_code == 200
    assert avail(client, lib, book)['shelf_location'] == 'North 3'
    assert database.institution_audit.count_documents({'event': 'SHELF_UPDATED'}) == 1


def test_return_confirm_race_and_renew_return_race(client, setup, database):
    from concurrent.futures import ThreadPoolExecutor
    lib, book = setup; loan = issued(client, lib, book); path = f'/libraries/{lib}/loans/{loan["loan_id"]}'
    def operation(n):
        return client.post(path + ('/return-request' if n % 2 else '/renew'), json=cmd() if n % 2 else cmd(expected_due_at=loan['due_at']), headers={'x-test-user': '2'})
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(operation, range(6)))
    assert all(r.status_code in [200, 201, 409] for r in results)
    pending = database.institution_lending_requests.find_one({'request_type': 'RETURN', 'status': 'PENDING'})
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda n: review(client, lib, pending['lending_request_id'], 'confirm', kind='return'), range(5)))
    assert sum(r.status_code == 200 for r in results) == 1
    assert avail(client, lib, book)['requestable'] == 5
    assert database.institution_audit.count_documents({'event': 'RETURN_CONFIRMED'}) == 1


def test_cutover_migrates_explicit_legacy_source_and_reconciles(client, register, create, database):
    from backend.services.institution_repository import now
    from datetime import timedelta
    from scripts.migrate_lending_v2b import plan, apply
    from scripts.lending_v2b_operations import reconcile, rollback
    lib = register(); book = create(lib, copies=3, available_copies=2, global_work_id='OL-Networks')
    database.issues.insert_one({'issue_id': 71, 'library_id': 'LIB-OLD', 'inventory_source': 'physical', 'user_id': 2, 'work_id': 'OL-Networks', 'status': 'ISSUED', 'issued_at': now(), 'due_date': now() + timedelta(days=14)})
    assert not plan(lib, 'LIB-OLD')['ok']
    database.institution_library_aliases.insert_one({'canonical_library_id': lib, 'legacy_library_id': 'LIB-OLD'})
    proposed = plan(lib, 'LIB-OLD'); assert proposed['ok'] and database.institution_loans.count_documents({}) == 0
    key = str(uuid4()); result = apply(lib, 'LIB-OLD', writers_stopped=True, idempotency_key=key)
    assert result['ok'] and apply(lib, 'LIB-OLD', writers_stopped=True, idempotency_key=key)['operation_id'] == result['operation_id']
    assert database.institution_loans.count_documents({}) == 1 and result['loans'][0]['copy_id'] is None
    assert reconcile(lib)['ok'] and avail(client, lib, book['library_book_id'])['requestable'] == 2
    assert client.post('/issues/return/71', headers={'x-test-user': '2'}).status_code == 410
    # A migrated active loan makes rollback unsafe even before new requests.
    assert not rollback(lib)['safe']


@pytest.mark.parametrize('intent', ['REQUEST_BOOK', 'REQUEST_RETURN'])
def test_assistant_immutable_library_confirmation(client, setup, monkeypatch, intent):
    lib, book = setup; loan = issued(client, lib, book) if intent == 'REQUEST_RETURN' else None
    calls = []
    class Transport:
        async def call(self, service, method, path, **kwargs):
            calls.append((method, path, kwargs))
            r = client.request(method, path, json=kwargs.get('json'), params=kwargs.get('params'), headers={'x-test-user': '2'})
            assert r.is_success, r.text
            return r.json()
    tools = SimpleNamespace(loans=AssistantLoanTool(Transport()))
    store = ConversationStore(); orchestrator = AssistantOrchestrator(None, store)
    monkeypatch.setenv('ASSISTANT_MUTATING_ACTIONS_ENABLED', 'true')
    context = {'library_id': lib, 'library_book_id': book, **({'loan_id': loan['loan_id']} if loan else {})}
    async def run():
        response = await orchestrator.chat(AssistantRequest(message='Request this book', action=intent, lending_context=context), 'user-2', tools)
        assert response.pending_action and not any(c[0] == 'POST' for c in calls)
        confirmed = await orchestrator.chat(AssistantRequest(message='Confirm', action='CONFIRM_ACTION', pending_action_id=response.pending_action.action_id,
            conversation_id=response.conversation_id, lending_context={'library_id': str(uuid4()), 'library_book_id': str(uuid4())}), 'user-2', tools)
        assert not confirmed.errors and 'Awaiting librarian' in confirmed.message if intent == 'REQUEST_BOOK' else 'remains active' in confirmed.message
        assert calls[-1][1].startswith(f'/libraries/{lib}/')
        assert '/issues/' not in calls[-1][1]
        replay = await orchestrator.chat(AssistantRequest(message='Confirm', action='CONFIRM_ACTION', pending_action_id=response.pending_action.action_id, conversation_id=response.conversation_id), 'user-2', tools)
        assert replay.clarification
    asyncio.run(run())
