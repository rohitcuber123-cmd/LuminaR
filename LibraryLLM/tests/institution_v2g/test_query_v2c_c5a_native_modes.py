"""Five supplemental native mode flows, separate from the frozen 264 main flows.

The spelling comes from the established native fixture, never repaired parser
calibration. This proves native mode preservation and grants zero corpus credit.
"""
from copy import deepcopy
from uuid import uuid4
import pytest
from search.query_execution import GlobalQuerySearch,tenant_search
from search.session_store import collection,identity
from test_query_v2c_c5a_native import (
    fixture,SCOPES,scope_actor,snapshot,boundary,unchanged,correction,commit,save,
)

@pytest.mark.parametrize('scope',SCOPES)
def test_exact_literal_and_smart_issued_correction(fixture,scope):
    record={'case_id':'c5a-native-mode-'+scope,'suite':'native_mode_supplement','scope':scope,
            'actor':scope_actor(scope),'boundaries':[],'mode_steps':[],'result':'UNFINISHED'}
    try:
        query='detectve fiction';who=record['actor'];lid,staff=fixture.scope(scope);sid=str(uuid4())
        before=snapshot(fixture.db)
        options={'mode':'EXACT','session_id':sid,'personalized':True,'diagnostics':True}
        result=tenant_search(None,lid,who,query,staff=staff,**options) if lid else GlobalQuerySearch(fixture.engine).search(query,who,kg_enabled=False,**options)
        after=snapshot(fixture.db);exact=deepcopy(collection().find_one({'_id':sid}))
        record['mode_steps'].append({'mode':'EXACT','query':query,'session_id':sid,'response':result,
          'state_before':before,'state_after':after,'exact_accepted':exact})
        assert exact and exact['version']==1 and exact['last_query']==query
        assert all(exact[k]==v for k,v in identity(who,lid,staff).items())
        assert exact['current_plan']['mode']=='EXACT' and exact['current_plan']['exact_text']==query
        assert not exact['current_plan']['subjects'] and not exact['current_plan']['semantic_text']
        assert not result['interpretation'].get('clarification') and not result['interpretation'].get('corrections')
        assert not any(p['search_session_id']==sid for p in after['pending'])
        assert before['pending']==after['pending']
        assert before['accepted']==[r for r in after['accepted'] if r['_id']!=sid]
        assert len(after['accepted'])==len(before['accepted'])+1
        assert before['personalization_mongo']==after['personalization_mongo']
        profile_key=repr((who['sub'],who['sid'],lid,staff,'saved-canonical-v1'))
        assert {k:v for k,v in before['profiles'].items() if k!=profile_key}=={k:v for k,v in after['profiles'].items() if k!=profile_key}
        response=boundary(record,fixture,'exact_mode_suggestion_suppressed','get','/query/suggestions',params={'q':query,'mode':'EXACT','library_id':lid,'staff':staff})
        assert response.status_code==200 and response.json()['suggestions']==[];unchanged(record)
        body=correction(fixture,record,scope,query=query,operation='correction_apply')
        assert record['issuances'][-1]['actual_correction']['to']=='Detective Fiction'
        assert record['issuances'][-1]['pending']['mode']=='SMART'
        commit(fixture,record,body)
        assert collection().find_one({'_id':sid})==exact
        record['exact_context_preserved_after_smart_resolution']=True
        record['parser_calibration_core_credit']=0
        record['result']='PASS'
    finally:save(record)
