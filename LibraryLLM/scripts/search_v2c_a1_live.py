"""Fresh canonical-scope API/session checks and comparable parser timings."""
import json
import statistics
import time
from pathlib import Path
from uuid import uuid4

import httpx

from backend.database.mongodb import db
from backend.utils.jwt_utils import create_access_token, decode_access_token
from search.query_plan import parse_query, matches

ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports'
baseline=json.loads((R/'search_v2c_a1_baseline.json').read_text(encoding='utf8'))
fixture=json.loads((R/'search_v2c_a1_fixture.json').read_text())
assert db.name=='luminar_library'
actors={}
for name,uid in [('owner',4),('member',fixture['member_id']),('outsider',fixture['outsider_id'])]:
    u=db.users.find_one({'user_id':uid});t=create_access_token(uid,u['email'],u['role']);actors[name]=(t,decode_access_token(t))
client=httpx.Client(timeout=60)


def call(query,lid=None,actor='owner',staff=False,sid=None,personalized=False):
    headers={'Authorization':'Bearer '+actors[actor][0],'X-Luminar-V2B-QA':'bounded-search-review'}
    if lid:
        params={'search':query,'staff':str(staff).lower(),'limit':20,'personalized':str(personalized).lower()}
        if sid:params['session_id']=sid
        return client.get(f'http://127.0.0.1:8003/libraries/{lid}/catalogue/search',params=params,headers=headers)
    return client.post('http://127.0.0.1:8003/search',headers=headers,json={'query':query,'limit':10,'save_history':False,
        'personalized':personalized,**({'session_id':sid} if sid else {})})


try:
    observed={};sessions={};facets_by_scope={}
    scopes=[('GLOBAL',None,'owner',False),('TEST_PATRON',fixture['public_library_id'],'member',False),
        ('TEST_STAFF',fixture['public_library_id'],'owner',True),('PRIVATE_PATRON',fixture['library_id'],'member',False),
        ('PRIVATE_STAFF',fixture['library_id'],'owner',True)]
    for name,lid,actor,staff in scopes:
        url='http://127.0.0.1:8003/facets' if not lid else f'http://127.0.0.1:8002/libraries/{lid}/catalogue/facets'
        response=client.get(url,params={'staff':str(staff).lower()},headers={'Authorization':'Bearer '+actors[actor][0]})
        response.raise_for_status();facets=[r['subject'] for r in response.json()['results']];facets_by_scope[name]=facets
        rows=[]
        for query in baseline['queries']:
            p=parse_query(query,facets);response=call(query,lid,actor,staff);response.raise_for_status();body=response.json()
            decision=body['interpretation']['decision']['decision_type']
            assert decision==p.decision['decision_type']
            if decision not in ('EXECUTABLE','EXECUTABLE_WITH_NOTICE'):assert not body['results']
            else:assert all(matches(p,b) for b in body['results'])
            if lid:assert body['source']['catalogue_source']=='LIBRARY_LOCAL' and all(b['library_id']==lid for b in body['results'])
            assert 'diagnostics' not in body
            rows.append({'query':query,'http_status':response.status_code,'interpretation':body['interpretation'],
                'returned':len(body['results']),'foreign_rows':0,'strict_violations':0})
        observed[name]={'facet_count':len(facets),'Romance_present':'Romance'in facets,'rows':rows}
        sid=str(uuid4());response=call('books about wizards',lid,actor,staff,sid);response.raise_for_status()
        prior=db.search_sessions_v2b.find_one({'_id':sid});assert prior
        subject='Romance' if 'Romance'in facets else facets[0]
        response=call(f'include {subject} but exclude {subject}',lid,actor,staff,sid);response.raise_for_status()
        assert response.json()['interpretation']['decision']['decision_type']=='CONTRADICTORY' and not response.json()['results']
        assert db.search_sessions_v2b.find_one({'_id':sid})==prior
        response=call('rating above 3',lid,actor,staff,sid);response.raise_for_status()
        assert response.json()['interpretation']['session']['refined']
        assert any(c['label']=='Topic: wizards' for c in response.json()['interpretation']['chips'])
        response=client.delete(f'http://127.0.0.1:8002/search-context/{sid}',params={'library_id':lid,'staff':str(staff).lower()} if lid else {},
            headers={'Authorization':'Bearer '+actors[actor][0]});response.raise_for_status()
        assert not db.search_sessions_v2b.find_one({'_id':sid})
        response=call('books about networks',lid,actor,staff,str(uuid4()));response.raise_for_status()
        assert not any(c['key']=='rating_min' for c in response.json()['interpretation']['chips'])
        sessions[name]={'prior_stored':True,'rejected_results':0,'prior_unchanged':True,'later_refinement_kept_topic':True,
            'clear_deleted_context':True,'fresh_context_has_no_prior_rating':True}
    denied={}
    for staff in (False,True):
        response=call('include V2CA1 Private Orchid but exclude V2CA1 Private Orchid',fixture['library_id'],'outsider',staff)
        assert response.status_code==404
        denied['OUTSIDER_STAFF' if staff else 'OUTSIDER_PATRON']={'status':response.status_code,'body':response.json()}
        assert 'Orchid' not in response.text
    values=[]
    for _ in range(25):
        for query in baseline['queries']:
            start=time.perf_counter();parse_query(query,baseline['facets']);values.append((time.perf_counter()-start)*1000)
    performance={'method':baseline['method'],'samples_per_run':len(values),'before':{'p50_ms':baseline['parser_p50_ms'],
        'p95_ms':baseline['parser_p95_ms']},'after':{'p50_ms':statistics.median(values),'p95_ms':sorted(values)[int(.95*len(values))-1]},'after_samples_ms':values}
    (R/'search_v2c_a1_live.json').write_text(json.dumps({'scopes':observed,'sessions':sessions,'denied':denied,'authorized_facets':facets_by_scope},indent=2),encoding='utf8')
    (R/'search_v2c_a1_performance.json').write_text(json.dumps(performance,indent=2),encoding='utf8')
    print(json.dumps({'contexts':list(observed),'session_contexts':list(sessions),'performance':{k:performance[k] for k in ['samples_per_run','before','after']}}))
finally:
    for _,actor in actors.values():
        db.search_sessions_v2b.delete_many({'user_id':str(actor['sub']),'login_session':actor['sid']})
    client.close()
