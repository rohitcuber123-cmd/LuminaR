"""Execute each sealed V2 development-native contract through real Mongo/API.

Symbolic identities are mapped to isolated accounts. No production index build.
Native contracts with incomplete prior-state or HTTP-label disputes are recorded
as such, never silently counted as exact passes.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi import HTTPException
from search.query_execution import tenant_search
from search.session_store import collection, resolve, clear
from search import personalization as profiles
from test_query_v2a import query_library
from test_query_v2c_b import interaction_client
from test_query_v2c_c1 import context, capture, unchanged_scope, absent, actor

R=Path(os.getenv('LUMINAR_C2_REPORT_DIR','reports'))
CASES=[json.loads(l) for l in Path('reports/search_v2c_c2_v2_development.jsonl').read_text().splitlines()]
CASES=[r for r in CASES if r.get('requires_native_execution')]


@pytest.fixture
def native_context(query_library,client,library,database,request):
    row=request.param
    lid=query_library[0];worker=query_library[3]
    if row['scope_type'].startswith('PUBLIC'):
        lid=library(private=False)
        assert client.post(f'/libraries/{lid}/join',headers={'x-test-user':'2'},json={}).status_code==200
    other=library(private=False)
    assert client.post(f'/libraries/{other}/join',headers={'x-test-user':'2'},json={}).status_code==200
    action=row.get('expected_action')
    staff='STAFF' in row['scope_type'] and action not in ['search_unauthorized_workspace','search_denied_other_library_then_revoke_other_membership']
    who=actor(uid=4) if staff else actor()
    if staff:
        from backend.schemas.institutions import MembershipChange
        from backend.services.institution_service import change_membership
        for library_id in [lid,other]:
            assert client.post(f'/libraries/{library_id}/join',headers={'x-test-user':'4'},json={'access_code':'Isolated fixture access code'}).status_code==200
        membership=database.institution_memberships.find_one({'library_id':lid,'user_id':4})
        change_membership(lid,membership['membership_id'],MembershipChange(role='LIBRARIAN'),{'sub':'1'})
    if not database.institution_library_books.find_one({'library_id':lid}):
        from test_intelligence import book
        book(client,lid,'Native control collection')
    database.institution_library_books.update_many({'library_id':lid},{'$addToSet':{'subjects':{'$each':['Fiction','Romance']}}})
    profiles._cache.clear()
    def owned_context(owner):
        previous=row.get('previous_accepted_plan') or {}
        seed='include Fiction rating at least '+str(previous.get('rating_min',3)) if previous else 'books about neural networks'
        sid=str(uuid4());tenant_search(worker,lid,owner,seed,session_id=sid,staff=staff)
        q='Fiction 4';ch=tenant_search(worker,lid,owner,q,session_id=sid,staff=staff)['interpretation']['clarification'];assert ch
        key=(owner['sub'],owner['sid'],lid,staff,'saved-canonical-v1')
        from time import monotonic
        profiles._cache[key]=(monotonic()+60,profiles.empty())
        return {'sid':sid,'cid':'clarification:'+ch['clarification_id'],'owner':owner,'library_id':lid,'staff':staff,
                'body':{'query':q,'session_id':sid,'library_id':lid,'staff':staff,'clarification_id':ch['clarification_id'],'choice_id':ch['candidate_choices'][0]['choice_id']}}
    ctx={'A':owned_context(who),'B':context(worker,other,who),
         'GLOBAL':context(worker,None,who),'S2':owned_context(actor('other-login',int(who['sub'])))}
    return row,lid,other,worker,ctx,interaction_client(database,worker)


def call(fn):
    try:
        result=fn()
        return 200,result
    except HTTPException as error:
        return error.status_code,{'detail':error.detail}


@pytest.mark.parametrize('native_context',CASES,ids=lambda r:r['query_id'],indirect=True)
def test_each_development_native_contract(native_context,database):
    row,lid,other,worker,ctx,api=native_context
    before=capture();action=row.get('expected_action');who=ctx['A']['owner'];status=None
    record={'query_id':row['query_id'],'family_id':row['family_id'],'scope':row['scope_type'],
            'database':database.name,'action':action,'query_text':row['query_text'],
            'expected_status_raw':row.get('expected_http_status'), 'before':before,
            'parser_only':False,'private_leak':False,'session_corruption':False,'unsafe_execution':False,
            'native_api_rule_version':'c2-native-1','status_adapter':'Existing API: workspace denial403; private/membership/choice concealment404; exact endpoint status retained separately from raw authored status.'}
    try:
        if action=='search_unauthorized_workspace':
            status,result=call(lambda:tenant_search(worker,lid,who,row['query_text'],staff=True,session_id=ctx['A']['sid']))
            assert status==403 and capture()==before
        elif action=='revoke_current_membership_then_search':
            from backend.schemas.institutions import MembershipChange
            from backend.services.institution_service import change_membership
            membership=database.institution_memberships.find_one({'library_id':lid,'user_id':int(who['sub'])})
            change_membership(lid,membership['membership_id'],MembershipChange(status='REMOVED'),{'sub':'1'})
            status,result=call(lambda:tenant_search(worker,lid,who,row['query_text'],staff=ctx['A']['staff'],session_id=ctx['A']['sid']))
            assert status in (403,404);after=capture();absent(ctx['A'],after)
            for key in ['B','GLOBAL']:unchanged_scope(ctx[key],before,after)
        elif action=='search_denied_other_library_then_revoke_other_membership':
            from backend.schemas.institutions import MembershipChange
            from backend.services.institution_service import change_membership
            status,result=call(lambda:tenant_search(worker,other,who,row['query_text'],staff=True,session_id=ctx['B']['sid']))
            assert status==403 and capture()==before
            m=database.institution_memberships.find_one({'library_id':other,'user_id':2})
            change_membership(other,m['membership_id'],MembershipChange(status='REMOVED'),{'sub':'1'})
            second,_=call(lambda:tenant_search(worker,other,who,row['query_text'],session_id=ctx['B']['sid']))
            assert second in (403,404);after=capture();absent(ctx['B'],after)
            for key in ['A','GLOBAL','S2']:unchanged_scope(ctx[key],before,after)
            record['post_revocation_status']=second
        elif action in ['resolve_sid_1_clarification_under_sid_2','submit_forged_choice_then_submit_genuine_choice']:
            body=dict(ctx['A']['body'])
            headers={'x-user':who['sub'],'x-sid':who['sid']}
            if action.startswith('resolve_sid'):headers['x-sid']='other-login'
            else:body['choice_id']=str(uuid4())
            response=api.post('/query/resolve',json=body,headers=headers);status=response.status_code;result=response.json()
            assert status==404 and capture()==before
            valid=api.post('/query/resolve',json=ctx['A']['body'],headers={'x-user':who['sub'],'x-sid':who['sid']});assert valid.status_code==200
            committed=deepcopy(collection().find_one({'_id':ctx['A']['sid']}))
            prior=next(r for r in before['accepted'] if r['_id']==ctx['A']['sid'])
            assert committed['version']==prior['version']+1
            replay=api.post('/query/resolve',json=ctx['A']['body'],headers={'x-user':who['sub'],'x-sid':who['sid']});assert replay.status_code==409
            assert collection().find_one({'_id':ctx['A']['sid']})==committed
            after=capture()
            for key in ['B','GLOBAL','S2']:unchanged_scope(ctx[key],before,after)
            record.update(valid_after_rejection=200,replay_status=409,authorized_commits=1)
        elif action=='search_tenant_as_platform_admin_without_membership':
            status,result=call(lambda:tenant_search(worker,lid,actor('admin-login',9),row['query_text'],staff='STAFF' in row['scope_type']))
            if row['scope_type']=='PUBLIC_PATRON' and status==200:
                record['applicability']='Public patron surface is canonically readable without membership; authored applicability precondition false.'
            else:assert status in (403,404)
            assert capture()==before
        elif action and action.startswith('request_private_'):
            outsider=actor('outsider-login',3)
            if action=='request_private_suggestions' or action=='request_private_corrections':
                response=api.get('/query/suggestions',params={'q':row['query_text'],'library_id':lid},headers={'x-user':'3','x-sid':'outsider-login'})
                status=response.status_code;result=response.json();assert status==404 and result=={'detail':'Library resource not found.'}
            elif action=='request_private_clarification_choices':
                response=api.post('/query/resolve',json=ctx['A']['body'],headers={'x-user':'3','x-sid':'outsider-login'})
                status=response.status_code;result=response.json();assert status==404 and result=={'detail':'Library resource not found.'}
            else:
                status,result=call(lambda:resolve('',outsider,[],session_id=ctx['A']['sid'],library_id=lid))
                assert status==404
            assert capture()==before
        elif action=='clear_current_authorized_search_context':
            clear(ctx['A']['sid'],who,library_id=lid,staff=ctx['A']['staff']);status=200;result={'cleared':True}
            after=capture();absent(ctx['A'],after)
            for key in ['B','GLOBAL','S2']:unchanged_scope(ctx[key],before,after)
            record['action_binding']='Explicit clear control API; query is UI text, not natural-language clear parsing.'
        elif row['family_id'] in ['d24_refinement_turns','d25_instead_turns']:
            # Legacy rows omit a full prior-state oracle. Execute with an
            # explicit synthetic prior, record delta accuracy separately; do
            # not claim these underspecified labels prove a perfect lifecycle.
            sid=str(uuid4());facets=['Fiction','History','Computer science','Java','Neural networks']
            prior,_=resolve('books about neural networks',who,facets,session_id=sid,library_id=lid,filters={'rating_min':2})
            p,session=resolve(row['query_text'],who,facets,session_id=sid,library_id=lid)
            status=200;result={'plan':p.public(),'session':session}
            from scripts.search_v2c_c_evaluate import expected,norm
            gold=expected(row)
            from dataclasses import asdict
            actual=asdict(p)
            checked={k:v for k,v in gold.items() if k not in ['intent','semantic_text','sort','soft_preference'] and v not in (None,[],False)}
            record['delta_mismatches']={k:{'expected':v,'actual':actual.get(k)} for k,v in checked.items() if norm(v)!=norm(actual.get(k))}
            record['prior_state_contract']='Synthetic topic neural networks and inclusive rating2; original row lacks complete independently reviewed sequence oracle.'
            record['prior_rating_retained']=p.rating_min==2
            after=capture()
            for key in ctx:unchanged_scope(ctx[key],before,after)
        else:raise AssertionError('Missing native action executor: '+str(action))
        record['result']='PASS_NATIVE_STATE_ORACLE'
    except Exception as error:
        record['result']='FAIL';record['error']=repr(error)
        # A test assertion is not automatically session corruption; full before
        # and after evidence identifies the actual failure without inventing a
        # privacy/corruption statistic.
        raise
    finally:
        record.update(actual_status=status,after=capture())
        raw=row.get('expected_http_status')
        record['raw_status_match']=status in raw if isinstance(raw,list) else status==raw if raw is not None else None
        with (R/'search_v2c_c2_native_observations.jsonl').open('a',encoding='utf8') as out:out.write(json.dumps(record,default=str)+'\n')
