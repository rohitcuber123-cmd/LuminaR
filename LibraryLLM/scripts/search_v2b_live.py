"""Bounded existing-user API QA; never changes catalogue/history/memberships."""
import json
import math
from pathlib import Path
from time import perf_counter
from uuid import uuid4
import httpx
from backend.database.mongodb import db
from backend.utils.jwt_utils import create_access_token, decode_access_token

ROOT = Path(__file__).resolve().parents[1]
TEST = 'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
PRIVATE = 'c5d1f394-e053-426e-a7ff-75d0bb524c12'

def run():
    assert db.name == 'luminar_library'
    user = db.users.find_one({'user_id':4})
    token = create_access_token(user['user_id'],user['email'],user['role'])
    actor = decode_access_token(token)
    assert actor is not None
    headers = {'Authorization':'Bearer '+token,'X-Luminar-V2B-QA':'bounded-search-review'}
    results, performance = {}, {}
    client = httpx.Client(base_url='http://127.0.0.1:8003',headers=headers,timeout=90)
    def search(query, *, library=None, session=None, personalized=False):
        start = perf_counter()
        if library:
            response = client.get(f'/libraries/{library}/catalogue/search',params={
                'search':query,'staff':'true','limit':50,'personalized':str(personalized).lower(),
                **({'session_id':session} if session else {})})
        else:
            response = client.post('/search',json={'query':query,'limit':50,'save_history':False,
                'personalized':personalized,**({'session_id':session} if session else {})})
        elapsed = round((perf_counter()-start)*1000,2)
        if response.status_code != 200:
            raise RuntimeError(f'QA request failed {response.status_code}: {response.text[:200]}')
        body = response.json()
        assert 'diagnostics' not in body
        assert all(not any(k in row for k in ('rerank_score','hnsw_score','personalization_score','_search_relevance')) for row in body['results'])
        if library:
            assert all(row['library_id'] == library for row in body['results'])
        return body,elapsed
    try:
        for name,library,topic in [('GLOBAL',None,'books about machine learning'),('TEST',TEST,'books about computer networks'),('PRIVATE',PRIVATE,'books about archives')]:
            sid = str(uuid4())
            steps = []
            for query in [topic,'only highly rated','online only','remove rating filter','something different','ancient history']:
                body,elapsed = search(query,library=library,session=sid)
                steps.append({'input':query,'status':200,'returned':len(body['results']),
                              'interpretation':body['interpretation'],'elapsed_ms':elapsed})
                if query == 'only highly rated':
                    assert all((row.get('average_rating',row.get('rating')) or 0)>=4 for row in body['results'])
                if query == 'online only':
                    assert all(row.get('has_online') for row in body['results'])
            results[name] = steps
            for variant in ['V2A_BASELINE','SESSION_ONLY','PROFILE_COLD_WARM']:
                times = []
                sample_sid = str(uuid4()) if variant != 'V2A_BASELINE' else None
                for _ in range(5):
                    body,elapsed = search(topic,library=library,session=sample_sid,personalized=variant=='PROFILE_COLD_WARM')
                    times.append(elapsed)
                sorted_times = sorted(times)
                performance[name+':'+variant] = {'samples_ms':times,'p50_ms':sorted_times[2],
                    'p95_ms':sorted_times[math.ceil(.95*len(times))-1],
                    'measurement':'sequential resident-model local requests, not a load test'}
            off,_ = search(topic,library=library)
            on,_ = search(topic,library=library,personalized=True)
            key = 'library_book_id' if library else 'work_id'
            before,after = [r[key] for r in off['results']],[r[key] for r in on['results']]
            results[name+'_PERSONALIZATION'] = {'same_candidate_set':set(before)==set(after),'order_changed':before!=after,
                'off_reasons_have_personalization':any('Reading List' in reason for r in off['results'] for reason in r.get('search_reasons',[])),
                'on_reason_count':sum(bool(r.get('search_reasons')) for r in on['results'])}
            assert set(before) == set(after)
        (ROOT/'.local/search_v2b_live.json').write_text(json.dumps(results,indent=2),encoding='utf8')
        (ROOT/'reports/search_v2b_performance.json').write_text(json.dumps(performance,indent=2),encoding='utf8')
        print(json.dumps({'contexts':list(results),'performance':performance},indent=2))
    finally:
        # Only this script's own ephemeral login contexts. No real browser state.
        db.search_sessions_v2b.delete_many({'user_id':actor['sub'],'login_session':actor['sid']})
        client.close()

if __name__ == '__main__':
    run()
