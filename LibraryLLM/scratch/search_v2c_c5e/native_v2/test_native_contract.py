"""Versioned C5A native infrastructure: issued capabilities, real API and Mongo.

No repaired calibration population is read/scored. Old ten+220 native IDs are
retained for traceability. All reports go to a new per-attempt C5A path.
"""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request, HTTPException
from fastapi.testclient import TestClient
from backend.dependencies import get_current_user
from search.interaction_api import install
from search.lexical_store import LexicalSearchStore
from search.query_execution import GlobalQuerySearch, tenant_search
from search.session_store import collection, identity
from search import personalization as profiles, query_suggestions as suggestions
from scripts.search_v2c_c5a_native_audit import old_rows, MISSING_BINDINGS

R=Path(os.environ['LUMINAR_C5A_NATIVE_REPORT_DIR'])
assert 'c5a' in str(R).lower()
R.mkdir(parents=True,exist_ok=True)
OLD=old_rows()
HISTORICAL=[r for r in OLD if r.get('requires_native_execution') and r.get('sequence_steps')]
MISSING=[r for r in OLD if 'c04_correction_actions' in r['query_id']]
assert len(HISTORICAL)==220 and len(MISSING)==10
SCOPES=['GLOBAL','PUBLIC_PATRON','PUBLIC_STAFF','PRIVATE_PATRON','PRIVATE_STAFF']
VOCAB=['Science fiction','History','Romance','Networking','Fiction','Astronomy','Detective Fiction','Neural networks']

def snapshot(database):
    """Mongo records keep all fields; profiles are actually populated, not seeded."""
    return {'accepted':list(collection().find({'current_plan':{'$exists':True}}).sort('_id')),
            'pending':list(collection().find({'record_type':'CLARIFICATION'}).sort('_id')),
            'profiles':{repr(k):{'deadline':v[0],'value':{'subjects':dict(v[1].subjects),'authors':dict(v[1].authors)}} for k,v in profiles._cache.items()},
            'personalization_mongo':list(database.reading_list.find({}).sort('_id'))}

def save(record):
    path=R/'search_v2c_c5a_observations.jsonl'
    with path.open('a',encoding='utf8') as out:out.write(json.dumps(record,default=str)+'\n')

def actor(uid=2,sid='c5a-login'):
    return {'sub':str(uid),'sid':sid}

def scope_actor(scope):
    return actor(4 if scope.endswith('STAFF') else 2)

def other_actor(scope):
    return actor(5 if scope.endswith('STAFF') else 6,'other-user-login')

@pytest.fixture
def fixture(client,library,database):
    assert database.name.startswith('luminar_search_c5e_test_')
    profiles._cache.clear();suggestions._projections.clear();suggestions._issued.clear()
    # No dataset/index/KG build. All semantic tenant tests use the actual
    # NOT_BUILT fallback. Global semantic keep tests use bounded fixture IDs.
    database.books.update_one({'work_id':'OL1W'},{'$set':{
      'title':'Neural C5A global primer','authors':['Ada Global C5A'],
      'subjects':'|'.join(VOCAB+['Global exclusive C5A']),
      'average_rating':4.5,'rating_count':2,'book_id':1}})
    database.book_categories.insert_many([{'name':v,'count':1} for v in VOCAB+['Global exclusive C5A']])
    database.reading_list.insert_one({'user_id':2,'target_type':'GLOBAL_WORK','work_id':'OL1W','added_at':datetime.now(timezone.utc)})
    lexical=LexicalSearchStore(enabled=False)
    lexical.db=sqlite3.connect(':memory:',check_same_thread=False)
    lexical.db.execute('CREATE TABLE lexical_values(value_type TEXT, normalized_value TEXT, work_id TEXT)')
    lexical.db.executemany('INSERT INTO lexical_values VALUES(?,?,?)',[
        ('TITLE','neural c5a global primer','OL1W'),('AUTHOR','ada global c5a','OL1W')])
    lexical.manifest={'sidecar_version':'c5a-isolated-sqlite-v1'}
    engine=SimpleNamespace(books_collection=database.books,lexical_store=lexical,
      search=lambda **kwargs:{'results':[{'work_id':'OL1W','rerank_score':1.0}],'diagnostics':{'candidate_count':1}})
    api_app=FastAPI();api_app.state.tenant_intelligence=None;install(api_app,engine)
    def current(request:Request):return actor(request.headers.get('x-user','2'),request.headers.get('x-sid','c5a-login'))
    api_app.dependency_overrides[get_current_user]=current
    api=TestClient(api_app)
    created={}
    def tenant(scope):
        if scope in created:return created[scope]
        private=scope.startswith('PRIVATE');lid=library(private=private,name='C5A isolated '+scope)
        for uid in [2,4,5,6]:
            response=client.post(f'/libraries/{lid}/join',headers={'x-test-user':str(uid)},json={'access_code':'Isolated fixture access code'} if private else {})
            assert response.status_code==200,response.text
        # Both libraries and both test identities genuinely own staff authority.
        from backend.schemas.institutions import MembershipChange
        from backend.services.institution_service import change_membership
        for uid in [4,5]:
            member=database.institution_memberships.find_one({'library_id':lid,'user_id':uid})
            change_membership(lid,member['membership_id'],MembershipChange(role='LIBRARIAN'),{'sub':'1'})
        payload={'title':'Neural C5A tenant primer','subjects':VOCAB+['Private exclusive C5A' if private else 'Public exclusive C5A'],
          'authors':['Ada Tenant C5A'],'description':'C5A isolated fixture','create_physical_holding':True,
          'copies':2,'shelf_location':'C5A','idempotency_key':str(uuid4()),'global_work_id':'OL1W'}
        row=client.post(f'/libraries/{lid}/inventory/books',json=payload)
        assert row.status_code==201,row.text
        result=(lid,scope.endswith('STAFF'))
        created[scope]=result
        return result
    def scope(scope):return (None,False) if scope=='GLOBAL' else tenant(scope)
    def search(q,who,lid,staff,sid,personalized=True):
        opts={'session_id':sid,'personalized':personalized,'diagnostics':True}
        if lid:return tenant_search(None,lid,who,q,staff=staff,**opts)
        return GlobalQuerySearch(engine).search(q,who,kg_enabled=False,**opts)
    result=SimpleNamespace(db=database,api=api,app=api_app,scope=scope,search=search,engine=engine,tenant=tenant)
    yield result
    lexical.close()

def boundary(record,fixture,label,method,path,*,body=None,params=None,who=None):
    who=who or record.get('actor') or actor();before=snapshot(fixture.db)
    params={k:v for k,v in (params or {}).items() if v is not None}
    response=getattr(fixture.api,method)(path,json=body,headers={'x-user':who['sub'],'x-sid':who['sid']}) if method!='get' else fixture.api.get(path,params=params,headers={'x-user':who['sub'],'x-sid':who['sid']})
    record['boundaries'].append({'label':label,'method':method,'path':path,'request':body if body is not None else params,
      'actor':who,'status':response.status_code,'body':response.json(),'state_before':before,'state_after':snapshot(fixture.db)})
    return response

def correction(fixture,record,scope='GLOBAL',query='detectve fiction',operation='correction_apply',who=None):
    who=who or scope_actor(scope);record['actor']=who;lid,staff=fixture.scope(scope);sid=str(uuid4())
    response=fixture.search('include History',who,lid,staff,sid)
    assert response['interpretation']['session']['version']==1
    before=snapshot(fixture.db)
    response=fixture.search(query,who,lid,staff,sid)
    after=snapshot(fixture.db)
    public=response['interpretation'].get('clarification')
    record.setdefault('issuances',[]).append({'kind':'correction','scope':scope,'query':query,'actor':who,'library_id':lid,'staff':staff,'session_id':sid,
      'response':response,'state_before':before,'state_after':after})
    assert public,'Actual service produced no correction: '+query
    pending=collection().find_one({'_id':'clarification:'+public['clarification_id']})
    assert pending and pending['choices'] and all(pending[k]==v for k,v in identity(who,lid,staff).items())
    assert {'correction_apply','correction_keep'}<={r['operation'] for r in pending['choices']}
    choice=next(r for r in pending['choices'] if r['operation']==operation)
    assert choice['correction']['kind']=='typo' and choice['correction']['from'].casefold()==query.casefold()
    record['issuances'][-1].update(pending=pending,actual_operation=operation,actual_choice_id=choice['choice_id'],actual_correction=choice['correction'])
    return {'query':query,'session_id':sid,'library_id':lid,'staff':staff,'clarification_id':public['clarification_id'],'choice_id':choice['choice_id']}

def unchanged(record):
    b=record['boundaries'][-1]
    assert b['state_before']==b['state_after'], 'Denied/selection request mutated exact native state'

def commit(fixture,record,body,who=None,label='genuine'):
    prior=collection().find_one({'_id':body['session_id']})
    response=boundary(record,fixture,label,'post','/query/resolve',body=body,who=who)
    assert response.status_code==200,response.text
    after=collection().find_one({'_id':body['session_id']})
    pending=collection().find_one({'_id':'clarification:'+body['clarification_id']})
    assert after['version']==prior['version']+1 and pending['used'] is True
    assert response.json()['choice_applied'] is True
    assert after['interaction_receipt']['clarification_id']==pending['_id']
    assert isinstance(after['interaction_receipt']['claim'],str) and after['interaction_receipt']['claim']
    assert all(after[k]==prior[k] for k in ['user_id','login_session','scope','library_id','workspace'])
    expected=next(i for i in record['issuances'] if i.get('actual_choice_id')==body['choice_id'])
    target=expected['actual_correction']['to'];original=expected['actual_correction']['from']
    if expected['actual_operation']=='correction_apply':assert target in after['current_plan']['subjects']
    else:assert original.casefold() in after['current_plan']['semantic_text'].casefold() and target not in after['current_plan']['subjects']
    before=record['boundaries'][-1]['state_before'];latest=record['boundaries'][-1]['state_after']
    assert before['profiles']==latest['profiles'] and before['personalization_mongo']==latest['personalization_mongo']
    for kind,key in [('accepted',body['session_id']),('pending','clarification:'+body['clarification_id'])]:
        assert [r for r in before[kind] if r['_id']!=key]==[r for r in latest[kind] if r['_id']!=key]
    replay=boundary(record,fixture,'replay','post','/query/resolve',body=body,who=who)
    assert replay.status_code==409;unchanged(record)

@pytest.mark.parametrize('row',MISSING,ids=lambda r:r['query_id'])
def test_ten_missing_correction_contexts(fixture,row):
    index=int(row['query_id'].rsplit('-',1)[1])-1;query,target,operation=MISSING_BINDINGS[index]
    record={'case_id':row['query_id'],'suite':'missing_context','scope':'GLOBAL','original_ui_intent':row['query_text'],'boundaries':[],'result':'UNFINISHED'}
    try:
        body=correction(fixture,record,query=query,operation=operation)
        assert record['issuances'][-1]['actual_correction']['to']==target
        commit(fixture,record,body);record['result']='PASS'
    finally:save(record)

@pytest.mark.parametrize('row',HISTORICAL,ids=lambda r:r['query_id'])
def test_reviewed_historical_native(fixture,row):
    scope=row['scope_type'];action=row['expected_action']
    record={'case_id':row['query_id'],'suite':'reviewed_historical','scope':scope,'historical_action':action,'boundaries':[],'result':'UNFINISHED'}
    try:
        if action=='apply_suggestion_from_older_revision':
            lid,staff=fixture.scope(scope)
            record['actor']=scope_actor(scope)
            result=boundary(record,fixture,'issue_suggestion','get','/query/suggestions',params={'q':'neur','library_id':lid,'staff':staff})
            assert result.status_code==200
            item=next(x for x in result.json()['suggestions'] if x['type']=='SUBJECT' and x['display']=='Neural networks')
            record['issuances']=[{'kind':'suggestion','actual_id':item['id'],'item':item,'response':result.json()}]
            body={'suggestion_id':item['id'],'q':'neur','library_id':lid,'staff':staff}
            # Suggestions do not bind accepted context versions in current API.
            fixture.search('include History',record['actor'],lid,staff,str(uuid4()))
            selected=boundary(record,fixture,'accepted_revision_independent','post','/query/suggestions/select',body=body)
            assert selected.status_code==200;unchanged(record)
            # Exercise genuine catalogue-generation staleness, no invented token.
            fixture.db.institution_audit.insert_one({'library_id':lid,'created_at':datetime.now(timezone.utc),'action':'C5A_FIXTURE_CATALOGUE_REVISION'})
            response=boundary(record,fixture,'catalogue_generation_stale','post','/query/suggestions/select',body=body)
            assert response.status_code==409;unchanged(record)
            record['historical_contract_limit']='Accepted-session revision does not invalidate issued suggestion capability; actual source generation does. No production promise or parser score inferred.'
        else:
            body=correction(fixture,record,scope=scope)
            if action=='submit_valid_choice_then_replay_identical_choice':commit(fixture,record,body)
            elif action=='resolve_another_users_clarification':
                response=boundary(record,fixture,'authorized_other_user','post','/query/resolve',body=body,who=other_actor(scope))
                assert response.status_code==404 and response.json()=={'detail':'Search choice is unavailable. Submit the query again.'};unchanged(record)
                commit(fixture,record,body)
            elif action=='submit_expired_or_superseded_clarification':
                collection().update_one({'_id':'clarification:'+body['clarification_id']},{'$set':{'expires_at':datetime.now(timezone.utc)-timedelta(seconds=1)}})
                response=boundary(record,fixture,'expired_pending','post','/query/resolve',body=body)
                assert response.status_code in (404,410)
                b=record['boundaries'][-1]
                assert b['state_before']['accepted']==b['state_after']['accepted'] and b['state_before']['profiles']==b['state_after']['profiles'] and b['state_before']['personalization_mongo']==b['state_after']['personalization_mongo']
                pending_key='clarification:'+body['clarification_id']
                if response.status_code==404:assert not any(x['_id']==pending_key for x in b['state_after']['pending'])
                else:assert b['state_before']['pending']==b['state_after']['pending']
                assert [x for x in b['state_before']['pending'] if x['_id']!='clarification:'+body['clarification_id']]==[x for x in b['state_after']['pending'] if x['_id']!='clarification:'+body['clarification_id']]
            elif action=='apply_correction_after_context_switch':
                other,_=fixture.scope('PUBLIC_STAFF' if scope.startswith('PRIVATE') else 'PRIVATE_STAFF')
                response=boundary(record,fixture,'authorized_other_library','post','/query/resolve',body={**body,'library_id':other})
                assert response.status_code==404 and response.json()=={'detail':'Search choice is unavailable. Submit the query again.'};unchanged(record)
                commit(fixture,record,body)
            else:raise AssertionError('Unknown original native action: '+action)
        record['result']='PASS'
    finally:save(record)

@pytest.mark.parametrize('scope',SCOPES)
def test_scoped_suggestion_issuance(fixture,scope):
    record={'case_id':'c5a-suggestions-'+scope,'suite':'suggestion','scope':scope,'boundaries':[],'result':'UNFINISHED'}
    try:
        lid,staff=fixture.scope(scope)
        record['actor']=scope_actor(scope)
        fixture.search('include History',record['actor'],lid,staff,str(uuid4()))
        for prefix,kind,display in [('neur','SUBJECT','Neural networks'),('ada','AUTHOR','Ada Tenant C5A' if lid else 'Ada Global C5A'),('neural c5a','TITLE','Neural C5A tenant primer' if lid else 'Neural C5A global primer')]:
            response=boundary(record,fixture,'issue_'+kind,'get','/query/suggestions',params={'q':prefix,'library_id':lid,'staff':staff})
            assert response.status_code==200;unchanged(record)
            item=next(i for i in response.json()['suggestions'] if i['type']==kind and i['display']==display)
            record.setdefault('issuances',[]).append({'kind':'suggestion','actual_id':item['id'],'item':item,'response':response.json()})
            assert item['id'] and not any(k in item for k in ['user_id','login_session','library_book_id'])
            body={'suggestion_id':item['id'],'q':prefix,'library_id':lid,'staff':staff}
            response=boundary(record,fixture,'select_'+kind,'post','/query/suggestions/select',body=body)
            assert response.status_code==200 and response.json()=={'insert_text':item['insert_text'],'type':kind};unchanged(record)
            who=record['actor']
            for label,payload,who in [('forged',{**body,'suggestion_id':'forged'},who),('sid',body,{**who,'sid':'other-login'}),('user',body,other_actor(scope)),('query',{**body,'q':'different'},who),('mode',{**body,'mode':'TITLE_AUTHOR'},who)]:
                response=boundary(record,fixture,'reject_'+label,'post','/query/suggestions/select',body=payload,who=who)
                assert response.status_code==409;unchanged(record)
            response=boundary(record,fixture,'owner_after_reject','post','/query/suggestions/select',body=body)
            assert response.status_code==200;unchanged(record)
            if lid:
                other,_=fixture.scope('PRIVATE_STAFF' if scope.startswith('PUBLIC') else 'PUBLIC_STAFF')
                response=boundary(record,fixture,'wrong_library','post','/query/suggestions/select',body={**body,'library_id':other})
                assert response.status_code==409;unchanged(record)
                response=boundary(record,fixture,'unauthorized_workspace','post','/query/suggestions/select',body={**body,'staff':not staff})
                assert response.status_code==403;unchanged(record)
                member={'library_id':lid,'user_id':int(record['actor']['sub'])}
                fixture.db.institution_memberships.update_one(member,{'$set':{'role':'GENERAL_USER' if staff else 'LIBRARIAN'}})
                response=boundary(record,fixture,'authorized_new_workspace','post','/query/suggestions/select',body={**body,'staff':not staff})
                assert response.status_code==409;unchanged(record)
                fixture.db.institution_memberships.update_one(member,{'$set':{'role':'LIBRARIAN' if staff else 'GENERAL_USER'}})
                response=boundary(record,fixture,'owner_after_scope_reject','post','/query/suggestions/select',body=body)
                assert response.status_code==200;unchanged(record)
            # Test-only clock expiry of ACTUALLY issued cache record.
            suggestions._issued[item['id']]['expires']=0
            response=boundary(record,fixture,'expired_suggestion','post','/query/suggestions/select',body=body)
            assert response.status_code==409;unchanged(record)
        if lid:
            response=boundary(record,fixture,'global_vocab_isolation','get','/query/suggestions',params={'q':'global','library_id':lid,'staff':staff})
            assert response.status_code==200 and not response.json()['suggestions'];unchanged(record)
        record['result']='PASS'
    finally:save(record)

@pytest.mark.parametrize('scope',SCOPES)
@pytest.mark.parametrize('operation',['correction_apply','correction_keep'])
def test_correction_rejection_recovery(fixture,scope,operation):
    record={'case_id':'c5a-recovery-'+scope+'-'+operation,'suite':'correction_security','scope':scope,'boundaries':[],'result':'UNFINISHED'}
    try:
        body=correction(fixture,record,scope,operation=operation)
        lid,staff=fixture.scope(scope)
        alternate=None
        who=record['actor']
        for label,payload,who in [('forged',{**body,'choice_id':str(uuid4())},who),('sid',body,{**who,'sid':'other-login'}),('user',body,other_actor(scope))]:
            response=boundary(record,fixture,'reject_'+label,'post','/query/resolve',body=payload,who=who)
            assert response.status_code==404;unchanged(record)
        if lid:
            other,_=fixture.scope('PRIVATE_STAFF' if scope.startswith('PUBLIC') else 'PUBLIC_STAFF')
            response=boundary(record,fixture,'reject_library','post','/query/resolve',body={**body,'library_id':other})
            assert response.status_code==404;unchanged(record)
            # An actor cannot simultaneously be a patron and staff in the
            # accepted API. First assert ordinary wrong-workspace403. Then
            # simulate a role transition in the isolated membership fixture so
            # fresh authority permits the other workspace and ownership404 is
            # actually reached. Restore fixture role before genuine recovery.
            response=boundary(record,fixture,'unauthorized_workspace','post','/query/resolve',body={**body,'staff':not staff})
            assert response.status_code==403;unchanged(record)
            member={'library_id':lid,'user_id':int(record['actor']['sub'])}
            fixture.db.institution_memberships.update_one(member,{'$set':{'role':'GENERAL_USER' if staff else 'LIBRARIAN'}})
            response=boundary(record,fixture,'authorized_new_workspace','post','/query/resolve',body={**body,'staff':not staff})
            assert response.status_code==404;unchanged(record)
            fixture.db.institution_memberships.update_one(member,{'$set':{'role':'LIBRARIAN' if staff else 'GENERAL_USER'}})
        commit(fixture,record,body)
        record['result']='PASS'
    finally:save(record)

@pytest.mark.parametrize('scope',SCOPES)
@pytest.mark.parametrize('scenario',['stale','expired_session','no_correction'])
def test_correction_edges(fixture,scope,scenario):
    record={'case_id':'c5a-edges-'+scope+'-'+scenario,'suite':'correction_edges','scope':scope,'boundaries':[],'result':'UNFINISHED'}
    try:
        lid,staff=fixture.scope(scope)
        record['actor']=scope_actor(scope)
        if scenario=='no_correction':
            for query in ['Python 3','"detectve fiction"','unrelated lunar word']:
                result=fixture.search(query,record['actor'],lid,staff,str(uuid4()))
                assert not result['interpretation'].get('clarification')
                record.setdefault('no_correction_observations',[]).append({'query':query,'response':result})
        else:
            body=correction(fixture,record,scope)
            if scenario=='stale':fixture.search('include Astronomy',record['actor'],lid,staff,body['session_id'])
            else:collection().update_one({'_id':body['session_id']},{'$set':{'expires_at':datetime.now(timezone.utc)-timedelta(seconds=1)}})
            response=boundary(record,fixture,scenario,'post','/query/resolve',body=body)
            assert response.status_code==409;unchanged(record)
        record['result']='PASS'
    finally:save(record)

@pytest.mark.parametrize('uid',[3,9])
def test_private_outsider_and_admin(fixture,uid):
    record={'case_id':'c5a-private-nonmember-'+str(uid),'suite':'privacy','scope':'PRIVATE_NONMEMBER','boundaries':[],'result':'UNFINISHED'}
    try:
        body=correction(fixture,record,'PRIVATE_PATRON')
        for method,path,payload in [('get','/query/suggestions',{'q':'neur','library_id':body['library_id']}),('post','/query/resolve',body)]:
            response=boundary(record,fixture,'private_denial','get' if method=='get' else 'post',path,params=payload if method=='get' else None,body=payload if method!='get' else None,who=actor(uid,'outsider-login'))
            assert response.status_code==404 and response.json()=={'detail':'Library resource not found.'};unchanged(record)
        commit(fixture,record,body)
        record['result']='PASS'
    finally:save(record)

def test_revocation_exact_scope(fixture):
    record={'case_id':'c5a-revocation-exact-scope','suite':'revocation','scope':'PRIVATE_PATRON','boundaries':[],'result':'UNFINISHED'}
    try:
        body=correction(fixture,record,'PRIVATE_PATRON')
        other=correction(fixture,record,'PUBLIC_PATRON')
        glob=correction(fixture,record,'GLOBAL')
        foreign=correction(fixture,record,'PRIVATE_PATRON',who=actor(sid='other-login'))
        record['actor']=actor()
        lid=body['library_id']
        suggestion=boundary(record,fixture,'issue_before_revoke','get','/query/suggestions',params={'q':'neur','library_id':lid})
        assert suggestion.status_code==200
        fixture.db.institution_memberships.update_one({'library_id':lid,'user_id':2},{'$set':{'status':'REMOVED'}})
        before=snapshot(fixture.db)
        response=boundary(record,fixture,'revoked_correction','post','/query/resolve',body=body)
        assert response.status_code==404 and response.json()=={'detail':'Library resource not found.'}
        after=snapshot(fixture.db)
        target=identity(actor(),lid,False)
        for kind in ['accepted','pending']:
            assert after[kind]==[r for r in before[kind] if not all(r.get(k)==v for k,v in target.items())]
        key=repr(('2','c5a-login',lid,False,'saved-canonical-v1'))
        assert after['profiles']=={k:v for k,v in before['profiles'].items() if k!=key}
        assert after['personalization_mongo']==before['personalization_mongo']
        response=boundary(record,fixture,'revoked_suggestions','get','/query/suggestions',params={'q':'neur','library_id':lid})
        assert response.status_code==404;unchanged(record)
        item=suggestion.json()['suggestions'][0]
        response=boundary(record,fixture,'revoked_select','post','/query/suggestions/select',body={'suggestion_id':item['id'],'q':'neur','library_id':lid})
        assert response.status_code==404;unchanged(record)
        record['preserved_other_session_ids']=[other['session_id'],glob['session_id'],foreign['session_id']]
        record['result']='PASS'
    finally:save(record)

def test_expired_authentication(fixture):
    from jose import jwt
    from backend.utils.jwt_utils import JWT_SECRET_KEY,JWT_ALGORITHM
    record={'case_id':'c5a-expired-authentication','suite':'authentication','scope':'GLOBAL','boundaries':[],'result':'UNFINISHED'}
    try:
        body=correction(fixture,record)
        fixture.app.dependency_overrides.clear()
        expired=jwt.encode({'sub':'2','sid':'c5a-login','exp':datetime.now(timezone.utc)-timedelta(seconds=2)},JWT_SECRET_KEY,algorithm=JWT_ALGORITHM)
        for method,path in [('get','/query/suggestions'),('post','/query/resolve')]:
            before=snapshot(fixture.db)
            response=fixture.api.get(path,params={'q':'neur'},headers={'Authorization':'Bearer '+expired}) if method=='get' else fixture.api.post(path,json=body,headers={'Authorization':'Bearer '+expired})
            record['boundaries'].append({'label':'expired_jwt','status':response.status_code,'body':response.json(),'state_before':before,'state_after':snapshot(fixture.db)})
            assert response.status_code==401;unchanged(record)
        record['result']='PASS'
    finally:save(record)
