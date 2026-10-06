"""Read-only normal startup smoke; no router evaluation or private report data."""
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
from backend.database.mongodb import books_collection, users_collection
from backend.services.identity_service import current_identity
from backend.utils.jwt_utils import create_access_token

async def main():
    user = next(u for u in users_collection.find({'is_email_verified': True, 'role': 'GENERAL_USER'})
                if current_identity({'sub': str(u['user_id'])}))
    token = create_access_token(user['user_id'], user['email'], user['role'])
    ids = [r['work_id'] for r in books_collection.find({'work_id': {'$exists': True}}, {'work_id': 1}).limit(2)]
    headers = {'Authorization': 'Bearer ' + token}
    out = {'router': 'existing_qwen', 'health': {}, 'checks': []}
    async with httpx.AsyncClient(timeout=90) as client:
        for _ in range(30):
            try:
                if (await client.get('http://127.0.0.1:8005/health', timeout=3)).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)
        for label, url in [('core','http://127.0.0.1:8002/health'), ('search','http://127.0.0.1:8003/health'),
                           ('recommendation','http://127.0.0.1:8004/'), ('rag','http://127.0.0.1:8005/health'),
                           ('frontend','http://127.0.0.1:5173/')]:
            out['health'][label] = (await client.get(url)).status_code
        for payload in [{'message': 'Compare', 'action': 'COMPARE', 'selected_work_ids': ids},
                        {'message': 'Availability', 'action': 'CHECK_AVAILABILITY', 'selected_work_ids': ids[:1]}]:
            response = await client.post('http://127.0.0.1:8005/assistant/chat', json=payload, headers=headers)
            data = response.json()
            trace = response.headers.get('x-assistant-trace')
            profile = {}
            for _ in range(25):
                path = ROOT/'reports/assistant_production_profiles.jsonl'
                if path.exists():
                    profile = next((r for r in map(json.loads, reversed(path.read_text(encoding='utf8').splitlines()))
                                    if r.get('trace_id') == trace), {})
                    if profile:
                        break
                await asyncio.sleep(.01)
            expected = 'COMPARE_BOOKS' if payload['action'] == 'COMPARE' else 'CHECK_AVAILABILITY'
            actual_ids = [b['work_id'] for b in (data.get('comparison') or {}).get('books', [])] or [b['work_id'] for b in data.get('books', [])]
            out['checks'].append({'action': payload['action'], 'status': response.status_code,
                'intent': data.get('intent'), 'qwen_calls': profile.get('qwen_call_count'),
                'experimental_profile_present': any(k.startswith('router_v') for k in profile),
                'pass': response.status_code == 200 and data.get('intent') == expected and actual_ids == payload['selected_work_ids']
                    and not data.get('errors') and profile.get('qwen_call_count') == 0})
    out['pass'] = all(v == 200 for v in out['health'].values()) and all(r['pass'] for r in out['checks'])
    (ROOT/'reports/assistant_production_smoke.json').write_text(json.dumps(out, indent=2), encoding='utf8')
    print('SMOKE', out['pass'], out['health'])

if __name__ == '__main__':
    asyncio.run(main())
