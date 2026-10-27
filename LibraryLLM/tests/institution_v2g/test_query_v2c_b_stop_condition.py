"""Reproducer retained for the user-mandated V2C-B stop condition.

This retained test asserts the original required state-integrity invariant.
It uses only the isolated institutional test database and its disposable fixtures.
"""
from copy import deepcopy
from uuid import uuid4
from pathlib import Path
import json,os
from search.query_execution import tenant_search
from search.session_store import collection
from test_query_v2a import query_library
from test_query_v2c_b import interaction_client, ACTOR


def test_forged_choice_must_not_delete_previous_accepted_context(query_library,database):
    lid,_,_,worker,_,_=query_library
    sid=str(uuid4());query='include Romance but exclude Romance'
    tenant_search(worker,lid,ACTOR,'books about neural networks',session_id=sid)
    before=deepcopy(collection().find_one({'_id':sid}));assert before
    rejected=tenant_search(worker,lid,ACTOR,query,session_id=sid)
    assert collection().find_one({'_id':sid})==before
    public=rejected['interpretation']['clarification'];client=interaction_client(database,worker)
    result=client.post('/query/resolve',json={'clarification_id':public['clarification_id'],
        'choice_id':str(uuid4()),'query':query,'session_id':sid,'library_id':lid})
    after=collection().find_one({'_id':sid})
    evidence={'isolated_database':database.name,'accepted_context_existed_before':True,
              'rejected_query_preserved_previous_context':True,'forged_choice_http_status':result.status_code,
              'accepted_context_exists_after_forged_choice':bool(after),
              'accepted_context_unchanged':after==before,
              'cause':'authorized() catches the yielded body HTTPException(404) and calls invalidate(actor, library_id), deleting the caller contexts and pending choices.',
              'production_catalogue_modified':False,'required_invariant':'A forged choice must not mutate accepted Search state.'}
    target=Path(os.getenv('LUMINAR_SECURITY_REPORT_DIR',str(Path(__file__).resolve().parents[2]/'reports')))/'search_v2c_b1_retained_reproducer.json'
    target.write_text(json.dumps(evidence,indent=2),encoding='utf8')
    assert result.status_code==404
    assert after==before,'STOP: forged choice deleted the previous accepted V2B context'
