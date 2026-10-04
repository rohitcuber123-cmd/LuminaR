"""Read-only live Core checks; no model worker, account or circulation writes."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from backend.database.mongodb import db, users_collection
    from backend.services.identity_service import current_identity
    from backend.utils.jwt_utils import create_access_token
    from knowledge_graph.core import CatalogueGraph, canonical, terms
    from assistant.orchestrator import AssistantOrchestrator
    from assistant.schemas import AssistantRequest
    from assistant.state import ConversationStore
    from assistant.tools import AssistantTools

    graph = CatalogueGraph()
    frozen = json.loads((ROOT / 'reports/kg3_seeds.json').read_text(encoding='utf-8'))
    user = next(u for u in users_collection.find({'role': 'GENERAL_USER', 'is_email_verified': True})
                if current_identity({'sub': str(u['user_id'])}))
    authorization = 'Bearer ' + create_access_token(user['user_id'], user['email'], user['role'])
    collections = ['users', 'issues', 'reservations', 'reading_list', 'recommendation_feedbacks', 'library_inventory', 'fines', 'activity']

    def state():
        return {name: hashlib.sha256(json.dumps(list(db[name].find({}).sort('_id', 1)),
                                               sort_keys=True, default=str).encode()).hexdigest()
                for name in collections}

    before = state()
    cases = [('finance', graph.lookup('Rich Dad, Poor Dad', 1)[0]['work_id']),
             ('fiction/literature', graph.lookup('Dracula', 1)[0]['work_id']),
             ('technical', frozen[0]['work_id'])]
    cases += [(label, next(s['work_id'] for s in frozen if s['stratum'] == label))
              for label in ['no authors', 'no subjects', 'isolated']]
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'graph': graph.meta(), 'cases': [],
              'method': 'Actual authenticated loopback Core API; first observed request plus three warm requests per seed. Not a process-cold benchmark. Live Core book metadata validated outside timed intervals.',
              'qwen_worker_running_required': False}
    warm = []
    with httpx.Client(timeout=120, headers={'Authorization': authorization}) as client:
        for label, wid in cases:
            timings = []
            for repeat in range(4):
                started = time.perf_counter()
                response = client.get(f'http://127.0.0.1:8002/kg/books/{wid}/more-like-this')
                timings.append((time.perf_counter() - started) * 1000)
                response.raise_for_status()
                data = response.json()
            seed = client.get(f'http://127.0.0.1:8002/books/{wid}').json()
            failures = []
            for card in data['recommendations']:
                live_response = client.get(f"http://127.0.0.1:8002/books/{card['work_id']}")
                live_response.raise_for_status()
                live = live_response.json()
                for field in ['title', 'average_rating', 'rating_count', 'shelf_location', 'available_copies', 'total_copies']:
                    if card.get(field) != live.get(field): failures.append([card['work_id'], field])
                for field in ['authors', 'subjects']:
                    if set(terms(card.get(field))) != set(terms(live.get(field))): failures.append([card['work_id'], field])
                assert card['work_id'] != wid
                for path in card['reason_paths']:
                    assert len(path['provenance']) == 2
                    for evidence in path['provenance']:
                        source = seed if evidence['work_id'] == wid else live
                        assert canonical(evidence['value']) in {canonical(t) for t in terms(source.get(evidence['field']))}
            assert not failures, failures
            warm.extend(timings[1:])
            report['cases'].append({'category': label, 'work_id': wid, 'title': seed['title'],
                'first_observed_ms': timings[0], 'warm_ms': timings[1:], 'results': len(data['recommendations']),
                'candidate_count': data['candidate_count'],
                'largest_returned_reason_degree': max((path['catalogue_degree'] for card in data['recommendations'] for path in card['reason_paths']), default=0),
                'metadata_availability_correct': True, 'reason_paths_source_verified': True,
                'recommendations': data['recommendations']})
            print(json.dumps({'category': label, 'work_id': wid, 'results': len(data['recommendations']), 'warm_ms': timings[1:]}), flush=True)

    class ForbiddenQwen:
        async def parse(self, *args, **kwargs): raise AssertionError('Qwen forbidden')
        async def respond(self, *args, **kwargs): raise AssertionError('Qwen forbidden')

    async def forbidden(*args, **kwargs): raise AssertionError('Existing recommender or RAG forbidden')

    async def assistant_probe():
        calls = []
        async def log(request): calls.append({'method': request.method, 'path': request.url.path})
        async with httpx.AsyncClient(timeout=120, event_hooks={'request': [log]}) as client:
            tools = AssistantTools(client, authorization, forbidden)
            tools.recommendation.recommend = forbidden
            orchestrator = AssistantOrchestrator(ForbiddenQwen(), ConversationStore())
            started = time.perf_counter()
            response = await orchestrator.chat(AssistantRequest(message='more like this', selected_work_ids=[cases[2][1]]),
                                               str(user['user_id']), tools)
            elapsed = (time.perf_counter() - started) * 1000
            assert response.intent == 'MORE_LIKE_THIS' and not response.errors
            assert all(call['method'] == 'GET' for call in calls)
            assert any(call['path'].startswith('/kg/books/') for call in calls)
            return {'method': 'Real assistant orchestrator and HTTP adapters calling live Core; forbidden Qwen/recommender/RAG sentinels. Not a live port-8005 request.',
                    'intent': response.intent, 'elapsed_ms': elapsed, 'books': len(response.books), 'calls': calls,
                    'qwen_calls': 0, 'existing_recommender_calls': 0}

    report['assistant_live_core_probe'] = asyncio.run(assistant_probe())
    report['warm_summary'] = {'requests': len(warm), 'median_ms': statistics.median(warm),
                              'p95_ms': sorted(warm)[int(.95 * (len(warm) - 1))], 'max_ms': max(warm)}
    report['read_only_state_unchanged'] = before == state()
    assert report['read_only_state_unchanged']
    (ROOT / 'reports/kg_product_performance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__': main()
