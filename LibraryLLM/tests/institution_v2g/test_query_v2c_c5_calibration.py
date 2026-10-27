"""Authorized calibration lifecycle rows; real isolated API/Mongo, no heldout."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
import json,os,time
from pathlib import Path
import pytest
from test_query_v2a import query_library
from test_query_v2c_c4_native import native_context
from test_query_v2c_c1 import capture,unchanged_scope
from search.session_store import collection
from search.query_execution import tenant_search

R=Path('reports/search_v2c_c5_native');R.mkdir(exist_ok=True)
CASES=[json.loads(x) for x in Path('reports/search_v2c_c5_calibration.jsonl').read_text().splitlines()]
assert len(CASES)==280 and all(x['split']=='calibration' for x in CASES)
CASES=[x for x in CASES if x.get('requires_native_execution') and x.get('sequence_steps')]
assert len(CASES)==220

@pytest.mark.parametrize('native_context',CASES,ids=lambda x:x['query_id'],indirect=True)
def test_calibration_native_sequence(native_context,database):
    row,lid,other,worker,ctx,api=native_context
    who=ctx['A']['owner'];body=ctx['A']['body'];headers={'x-user':who['sub'],'x-sid':who['sid']}
    action=row['expected_action'];boundaries=[];record={'query_id':row['query_id'],'family_id':row['family_id'],'scope':row['scope_type'],'action':action,'database':database.name,'raw_expected_status':row.get('expected_http_status'),'boundaries':boundaries,'result':'UNFINISHED','state_failures':[],'private_leaks':[]}
    def request(payload=body,request_headers=None):
        before=capture();start=time.perf_counter();response=api.post('/query/resolve',json=payload,headers=request_headers or headers)
        boundaries.append({'state_before':before,'state_after':capture(),'status':response.status_code,'body':response.json(),'elapsed_ms':(time.perf_counter()-start)*1000})
        return response
    try:
        if action=='resolve_another_users_clarification':
            response=request(request_headers={'x-user':'2' if who['sub']=='4' else '4','x-sid':'different-user-login'})
            assert response.status_code==404 and response.json()=={'detail':'Library resource not found.'}
            assert boundaries[-1]['state_before']==boundaries[-1]['state_after']
            before=deepcopy(collection().find_one({'_id':ctx['A']['sid']}))
            valid=request();assert valid.status_code==200,valid.text
            committed=collection().find_one({'_id':ctx['A']['sid']});assert committed['version']==before['version']+1
            assert committed['current_plan']['rating_min']==4 and committed['current_plan']['subjects']==['Fiction']
            assert request().status_code==409 and collection().find_one({'_id':ctx['A']['sid']})==committed
        elif action=='submit_valid_choice_then_replay_identical_choice':
            before=deepcopy(collection().find_one({'_id':ctx['A']['sid']}))
            assert request().status_code==200
            committed=collection().find_one({'_id':ctx['A']['sid']});assert committed['version']==before['version']+1
            assert committed['current_plan']['rating_min']==4 and committed['current_plan']['subjects']==['Fiction']
            response=request();assert response.status_code==409
            assert boundaries[-1]['state_before']==boundaries[-1]['state_after']
        elif action=='submit_expired_or_superseded_clarification':
            collection().update_one({'_id':ctx['A']['cid']},{'$set':{'expires_at':datetime.now(timezone.utc)-timedelta(seconds=1)}})
            response=request();assert response.status_code in (404,410)
            before,after=boundaries[-1]['state_before'],boundaries[-1]['state_after']
            assert before['accepted']==after['accepted'] and before['profiles']==after['profiles']
            # Mongo TTL may delete only the expired pending row.
            assert [r for r in before['pending'] if r['_id']!=ctx['A']['cid']]==[r for r in after['pending'] if r['_id']!=ctx['A']['cid']]
        elif action=='apply_suggestion_from_older_revision':
            tenant_search(worker,lid,who,'books about newer accepted topic',session_id=ctx['A']['sid'],staff=ctx['A']['staff'])
            response=request();assert response.status_code==409
            assert boundaries[-1]['state_before']==boundaries[-1]['state_after']
            record['operational_binding']='Existing issued-choice/suggestion action after accepted version advances; no invented client plan or new route.'
        elif action=='apply_correction_after_context_switch':
            # Existing issued correction choices have identical workspace binding.
            response=request({**body,'library_id':other})
            assert response.status_code==404 and response.json()=={'detail':'Library resource not found.'}
            assert boundaries[-1]['state_before']==boundaries[-1]['state_after']
            record['operational_binding']='Existing issued choice submitted in another owned library; exact pending/accepted/profile state invariant. Original labels do not specify correction text.'
        else:raise AssertionError('No executor for '+action)
        for boundary in boundaries:
            if boundary['status']>=400 and boundary['body'] not in [{'detail':'Library resource not found.'},{'detail':'Search context changed. Retry your search.'},{'detail':'This clarification is no longer available. Search again.'}]:
                # Exact endpoint error texts differ by lifecycle; forbid actual
                # private canonical content rather than guessing a generic string.
                serialized=json.dumps(boundary['body']).casefold()
                assert not any(x in serialized for x in ['neural networks','fiction','romance','library_book_id','subjects'])
        before=boundaries[0]['state_before'];after=boundaries[-1]['state_after']
        for key in ['B','GLOBAL','S2']:unchanged_scope(ctx[key],before,after)
        record['result']='PASS_CURRENT_API_STATE_INVARIANTS'
    except Exception as error:
        record['result']='FAIL';record['error']=repr(error);raise
    finally:
        record['raw_status_match']=(boundaries[0]['status'] in row['expected_http_status'] if isinstance(row.get('expected_http_status'),list) else boundaries[0]['status']==row.get('expected_http_status')) if boundaries else None
        path=R/'observations.jsonl'
        with path.open('a',encoding='utf8') as out:out.write(json.dumps(record,default=str)+'\n')
