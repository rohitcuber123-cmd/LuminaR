"""Normal production smoke: disposable accounts, list-only writes, cleanup finally."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
import psutil
from backend.database.mongodb import users_collection, reading_list_collection, books_collection
from backend.services.identity_service import next_user_id
from backend.utils.jwt_utils import create_access_token

REPORT = ROOT / 'reports/assistant_production_live.json'
PROFILE = ROOT / 'reports/assistant_production_profiles.jsonl'

def write(data):
    REPORT.write_text(json.dumps(data, indent=2), encoding='utf8')

async def main():
    out = {'router': 'existing_qwen', 'scenarios': [], 'natural_language': [], 'cleanup': False}
    accounts = []
    marker = 'stabilization-' + uuid4().hex
    try:
        for index in range(2):
            user_id = next_user_id()
            row = {'user_id': user_id, 'email': f'{marker}-{index}@test.invalid', 'name': 'Disposable stabilization reader',
                   'role': 'GENERAL_USER', 'is_email_verified': True, 'is_active': True,
                   'password_setup_required': False, 'stabilization_marker': marker,
                   'created_at': datetime.now(timezone.utc)}
            users_collection.insert_one(row)
            accounts.append(row)
        tokens = [create_access_token(u['user_id'], u['email'], u['role']) for u in accounts]
        other_session = create_access_token(accounts[0]['user_id'], accounts[0]['email'], accounts[0]['role'])
        books = list(books_collection.find({'work_id': {'$exists': True}}, {'_id': 0, 'work_id': 1}).limit(2))
        assert len(books) == 2
        a, b = [r['work_id'] for r in books]
        out['public_work_ids'] = [a, b]
        async with httpx.AsyncClient(timeout=180) as client:
            for label, url in [('core','http://127.0.0.1:8002/health'), ('search','http://127.0.0.1:8003/health'),
                               ('recommendation','http://127.0.0.1:8004/'), ('rag','http://127.0.0.1:8005/health'),
                               ('frontend','http://127.0.0.1:5173/')]:
                response = await client.get(url)
                out.setdefault('health', {})[label] = response.status_code
            async def chat(payload, token=None):
                response = await client.post('http://127.0.0.1:8005/assistant/chat', json=payload,
                    headers={'Authorization': 'Bearer ' + (token or tokens[0])})
                data = response.json()
                trace = response.headers.get('x-assistant-trace')
                profile = {}
                for _ in range(25):
                    if PROFILE.exists():
                        profile = next((row for row in map(json.loads, reversed(PROFILE.read_text(encoding='utf8').splitlines()))
                                        if row.get('trace_id') == trace), {})
                        if profile:
                            break
                    await asyncio.sleep(.01)
                return response.status_code, data, profile
            async def saved(token=None):
                response = await client.get('http://127.0.0.1:8002/reading-list/my',
                    headers={'Authorization': 'Bearer ' + (token or tokens[0])})
                assert response.status_code == 200
                return [row['work_id'] for row in response.json()['items']]
            async def proposal(message, operation, conversation=None):
                payload = {'message': message, 'selected_work_ids': [a], 'conversation_id': conversation}
                status, data, profile = await chat(payload)
                success = status == 200 and data.get('intent') == operation and bool(data.get('pending_action'))
                out['natural_language'].append({'message': message, 'pass': success, 'status': status,
                    'actual_intent': data.get('intent'), 'errors': [e['code'] for e in data.get('errors', [])],
                    'qwen_calls': profile.get('qwen_call_count')})
                if not success:
                    # Observe natural failure honestly. Continue testing the
                    # executor through a supported explicit assistant action.
                    status, data, profile = await chat({**payload, 'action': operation})
                assert status == 200 and data.get('pending_action'), data.get('intent')
                return data
            async def finish(data, cancel=False, token=None, selected=None):
                return await chat({'message': 'Cancel' if cancel else 'Confirm',
                    'action': 'CANCEL_ACTION' if cancel else 'CONFIRM_ACTION',
                    'conversation_id': data['conversation_id'], 'pending_action_id': data['pending_action']['action_id'],
                    'selected_work_ids': selected or []}, token)
            def record(name, okay, **details):
                out['scenarios'].append({'name': name, 'pass': bool(okay), **details})
                write(out)
            add = await proposal('add this to my reading list', 'ADD_TO_READING_LIST')
            before = await saved()
            status, result, profile = await finish(add)
            after = await saved()
            record('add no write before confirm; confirm adds once', before == [] and after == [a]
                   and status == 200 and not result['errors'] and profile.get('qwen_call_count') == 0,
                   before_count=len(before), after_count=len(after), confirm_qwen_calls=profile.get('qwen_call_count'))
            _, replay, _ = await finish(add)
            record('confirm replay rejected', bool(replay.get('clarification')) and await saved() == [a])
            remove = await proposal('remove this from my reading list', 'REMOVE_FROM_READING_LIST')
            unchanged = await saved() == [a]
            status, result, profile = await finish(remove, cancel=True)
            record('remove proposal and cancel never write', unchanged and status == 200 and await saved() == [a]
                   and profile.get('qwen_call_count') == 0)
            remove = await proposal('remove this from my reading list', 'REMOVE_FROM_READING_LIST')
            unchanged = await saved() == [a]
            status, result, profile = await finish(remove)
            record('remove confirmation', unchanged and status == 200 and not result['errors'] and await saved() == []
                   and profile.get('qwen_call_count') == 0, confirm_qwen_calls=profile.get('qwen_call_count'))
            immutable = await proposal('add this to my reading list', 'ADD_TO_READING_LIST')
            status, result, profile = await finish(immutable, selected=[b])
            record('selection B cannot retarget stored A', status == 200 and await saved() == [a]
                   and profile.get('qwen_call_count') == 0)
            # Direct frontend/Core writes keep their original intentional behavior.
            direct = await client.delete('http://127.0.0.1:8002/reading-list/' + a,
                headers={'Authorization': 'Bearer ' + tokens[0]})
            record('ordinary direct Core remove unchanged', direct.status_code == 200 and await saved() == [])
            owned = await proposal('add this to my reading list', 'ADD_TO_READING_LIST')
            status, _, _ = await finish(owned, token=tokens[1])
            record('wrong account private rejection', status == 404 and await saved() == [] and await saved(tokens[1]) == [], status=status)
            status, _, _ = await finish(owned, token=other_session)
            record('wrong session private rejection', status == 404 and await saved() == [], status=status)
            await finish(owned, cancel=True)
            idempotent = await proposal('add this to my reading list', 'ADD_TO_READING_LIST')
            direct = await client.post('http://127.0.0.1:8002/reading-list/', json={'work_id': a},
                headers={'Authorization': 'Bearer ' + tokens[0]})
            status, result, profile = await finish(idempotent)
            record('add already present; direct Core add unchanged', direct.status_code == 200 and status == 200
                   and 'Already' in result['message'] and await saved() == [a] and profile.get('qwen_call_count') == 0)
            remove = await proposal('remove this from my reading list', 'REMOVE_FROM_READING_LIST')
            await client.delete('http://127.0.0.1:8002/reading-list/' + a, headers={'Authorization': 'Bearer ' + tokens[0]})
            status, result, profile = await finish(remove)
            record('remove now absent is idempotent', status == 200 and 'No longer' in result['message']
                   and await saved() == [] and profile.get('qwen_call_count') == 0)
            pending = await proposal('add this to my reading list', 'ADD_TO_READING_LIST')
            await chat({'message': 'Fees', 'action': 'USER_FEES', 'conversation_id': pending['conversation_id']})
            _, result, _ = await finish(pending)
            record('unrelated turn invalidates pending action', bool(result.get('clarification')) and await saved() == [])
            status, result, profile = await chat({'message': 'Compare', 'action': 'COMPARE', 'selected_work_ids': [a,b]})
            record('production structured comparison smoke', status == 200 and result.get('comparison') is not None
                   and not result['errors'] and profile.get('qwen_call_count') == 0)
            out['experimental_profile_fields_present'] = any(k.startswith('router_v') for k in profile)
    finally:
        for account in accounts:
            reading_list_collection.delete_many({'user_id': account['user_id']})
            users_collection.delete_one({'user_id': account['user_id'], 'stabilization_marker': marker})
        out['cleanup'] = users_collection.count_documents({'stabilization_marker': marker}) == 0 and all(
            reading_list_collection.count_documents({'user_id': a['user_id']}) == 0 for a in accounts)
        out['disposable_accounts_created_and_removed'] = len(accounts)
        out['pass'] = bool(out['scenarios']) and all(r['pass'] for r in out['scenarios']) and out['cleanup']
        write(out)
    print('LIVE', out['pass'], sum(r['pass'] for r in out['scenarios']), '/', len(out['scenarios']),
          'NATURAL', sum(r['pass'] for r in out['natural_language']), '/', len(out['natural_language']), 'CLEANUP', out['cleanup'])

if __name__ == '__main__':
    asyncio.run(main())
