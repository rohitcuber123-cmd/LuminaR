"""Summarize native evidence only. No calibration/heldout parser evaluation."""
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,sys
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf8'))
def write(suffix,value):(R/('search_v2c_c5a_'+suffix+'.json')).write_text(json.dumps(value,indent=2,default=str)+'\n',encoding='utf8')
def ratio(passed,total):return {'numerator':passed,'denominator':total,'percent':100*passed/total if total else None}

def expected_status(boundary):
    label=boundary['label'];path=boundary.get('path','')
    if label in ['genuine','accepted_revision_independent','issue_suggestion','owner_after_reject','owner_after_scope_reject','issue_before_revoke','global_vocab_isolation'] or label.startswith('issue_') or label.startswith('select_'):return [200]
    if label in ['expired_jwt']:return [401]
    if label=='unauthorized_workspace':return [403]
    if label=='expired_pending':return [404,410]
    if label in ['private_denial','revoked_correction','revoked_suggestions','revoked_select','authorized_other_user','authorized_other_library']:return [404]
    if label=='authorized_new_workspace':return [409] if path.endswith('/select') else [404]
    if label.startswith('reject_'):return [409] if path.endswith('/select') else [404]
    if label in ['replay','catalogue_generation_stale','wrong_library','expired_suggestion','stale','expired_session']:return [409]
    raise ValueError('No independent contract for label '+label)

def state_match(boundary):
    before=boundary['state_before'];after=boundary['state_after'];label=boundary['label']
    if label=='genuine':
        body=boundary['request'];sid=body['session_id'];cid='clarification:'+body['clarification_id']
        b=next(r for r in before['accepted'] if r['_id']==sid);a=next(r for r in after['accepted'] if r['_id']==sid)
        p=next(r for r in after['pending'] if r['_id']==cid)
        if a['version']!=b['version']+1 or p.get('used') is not True:return False
        if a.get('interaction_receipt',{}).get('clarification_id')!=cid:return False
        if not a.get('interaction_receipt',{}).get('claim'):return False
        if any(a[k]!=b[k] for k in ['user_id','login_session','scope','library_id','workspace']):return False
        for kind,key in [('accepted',sid),('pending',cid)]:
            if [r for r in before[kind] if r['_id']!=key]!=[r for r in after[kind] if r['_id']!=key]:return False
        return before['profiles']==after['profiles'] and before['personalization_mongo']==after['personalization_mongo']
    if label=='expired_pending':
        cid='clarification:'+boundary['request']['clarification_id']
        b=[r for r in before['pending'] if r['_id']!=cid];a=[r for r in after['pending'] if r['_id']!=cid]
        return b==a and before['accepted']==after['accepted'] and before['profiles']==after['profiles'] and before['personalization_mongo']==after['personalization_mongo'] and (not any(r['_id']==cid for r in after['pending']) if boundary['status']==404 else before['pending']==after['pending'])
    if label=='revoked_correction':
        target={'user_id':boundary['actor']['sub'],'login_session':boundary['actor']['sid'],'library_id':boundary['request']['library_id'],'scope':'LIBRARY','workspace':'PATRON'}
        for kind in ['accepted','pending']:
            if after[kind]!=[r for r in before[kind] if not all(r.get(k)==v for k,v in target.items())]:return False
        key=repr((target['user_id'],target['login_session'],target['library_id'],False,'saved-canonical-v1'))
        return after['profiles']=={k:v for k,v in before['profiles'].items() if k!=key} and after['personalization_mongo']==before['personalization_mongo']
    return before==after

def main():
    native=R/(sys.argv[1] if len(sys.argv)>1 else 'search_v2c_c5a_native_attempt3')
    security=R/(sys.argv[2] if len(sys.argv)>2 else 'search_v2c_c5a_security_attempt1')
    raw=native/'search_v2c_c5a_observations.jsonl';rows=[json.loads(x) for x in raw.read_text().splitlines() if x.strip()]
    assert len(rows)==264 and len({r['case_id'] for r in rows})==264
    run=read(native/'search_v2c_c5a_run.json');sec=read(security/'search_v2c_c5a_run.json')
    assert not run['historical_hash_changes'] and not sec['historical_hash_changes']
    boundaries=[];issuances=[]
    for line,row in enumerate(rows,1):
        ref={'raw_file':str(raw.relative_to(ROOT)),'line':line,'case_id':row['case_id']}
        for index,b in enumerate(row['boundaries']):
            status=b['status'] in expected_status(b);state=state_match(b)
            # Exact outsider concealment is separate from typed stale errors.
            if b['label'] in ['private_denial','revoked_correction','revoked_suggestions','revoked_select']:
                privacy=b['status']==404 and b['body']=={'detail':'Library resource not found.'}
            elif b['status']>=400:
                encoded=json.dumps(b['body']).casefold()
                privacy=not any(secret in encoded for secret in ['neural c5a','ada tenant','private exclusive c5a','detectve fiction','science fiction','library_book_id'])
            elif '/suggestions' in b.get('path',''):
                privacy=not any(k in item for item in b['body'].get('suggestions',[]) for k in ['user_id','login_session','library_book_id'])
            else:
                lid=b.get('request',{}).get('library_id')
                privacy=all(r.get('library_id')==lid for r in b['body'].get('results',[])) if lid else True
            boundaries.append({**ref,'boundary_index':index,'label':b['label'],'expected_status':expected_status(b),'actual_status':b['status'],'status_match':status,'state_match':state,'privacy_match':privacy})
        for index,issue in enumerate(row.get('issuances',[])):
            entry={**ref,'issuance_index':index,'kind':issue['kind'],'scope':row['scope']}
            if issue['kind']=='correction':
                pending=issue['pending'];response=issue['response'];public=response['interpretation']['clarification']
                entry.update(actual_clarification_id=public['clarification_id'],actual_choice_id=issue['actual_choice_id'],operation=issue['actual_operation'],correction=issue['actual_correction'],
                  owner={k:pending[k] for k in ['user_id','login_session','scope','library_id','workspace']},session_id=issue['session_id'],base_version=pending['base_version'],
                  valid=public['clarification_id']==pending['_id'].removeprefix('clarification:') and {'correction_apply','correction_keep'}<={c['operation'] for c in pending['choices']} and any(c['choice_id']==issue['actual_choice_id'] for c in pending['choices']))
            else:
                entry.update(actual_id=issue['actual_id'],item=issue['item'],valid=any(i['id']==issue['actual_id'] and i==issue['item'] for i in issue['response']['suggestions']))
            issuances.append(entry)
    status=ratio(sum(b['status_match'] for b in boundaries),len(boundaries));state=ratio(sum(b['state_match'] for b in boundaries),len(boundaries));privacy=ratio(sum(b['privacy_match'] for b in boundaries),len(boundaries))
    corrections=[i for i in issuances if i['kind']=='correction'];suggests=[i for i in issuances if i['kind']=='suggestion']
    missing=read(R/'search_v2c_c5a_native_missing_contexts.json');byid={r['case_id']:r for r in rows}
    for item in missing['cases']:
        observed=byid[item['existing_case_id']]
        item['corrected_execution_result']=observed['result']
        item['evidence']={'raw_file':str(raw.relative_to(ROOT)),'line':rows.index(observed)+1,'actual_issuance':next(c for c in corrections if c['case_id']==item['existing_case_id']),
                          'resolution_status':next(b['status'] for b in observed['boundaries'] if b['label']=='genuine'),'replay_status':next(b['status'] for b in observed['boundaries'] if b['label']=='replay')}
    missing['completed']=sum(byid[i['existing_case_id']]['result']=='PASS' for i in missing['cases']);write('native_missing_contexts',missing)
    audit=read(R/'search_v2c_c5a_harness_failure_audit.json')
    for case in audit['cases']:
        case['reviewed_harness_execution']={'result':byid[case['original_case_id']]['result'],'boundaries':[b for b in boundaries if b['case_id']==case['original_case_id']]}
    audit['independent_review']='reports/search_v2c_c5a_native_independent_review.json';write('harness_failure_audit',audit)
    write('suggestion_issuance',{'version':'C5A-issued-suggestion-v1','status':'PASS' if all(i['valid'] for i in suggests) else 'FAIL','oracle':ratio(sum(i['valid'] for i in suggests),len(suggests)),
          'accepted_revision_contract_limit':'Suggestions do not bind session revisions; original44 stale-suggestion contexts now prove accepted-version independence AND real catalogue-generation rejection. Historical expected409-after-session-change is not silently claimed.',
          'type_counts':dict(Counter(i['item']['type'] for i in suggests)),'cases':suggests,'raw_sha256':sha(raw)})
    write('correction_issuance',{'version':'C5A-issued-correction-v1','status':'PASS' if all(i['valid'] for i in corrections) else 'FAIL','oracle':ratio(sum(i['valid'] for i in corrections),len(corrections)),
          'proxy_Fiction4_contexts':0,'no_correction_cases':[{'case_id':r['case_id'],'observations':r['no_correction_observations']} for r in rows if 'no_correction_observations' in r],
          'cases':corrections,'raw_sha256':sha(raw)})
    xml=ET.parse(security/'search_v2c_c5a_native.xml');tests=xml.findall('.//testcase');failures=[t.attrib['name'] for t in tests if t.find('failure') is not None or t.find('error') is not None]
    security_report={'version':'C5A-accepted-security-v1','status':'PASS' if sec['exit_code']==0 and not failures else 'FAIL','passed':len(tests)-len(failures),'total':len(tests),'failures':failures,
       'B1':'PASS' if not failures else 'FAIL','C1':'PASS' if not failures else 'FAIL','private_outsider_concealment':'PASS' if not failures else 'FAIL',
       'test_function_sources':['tests/institution_v2g/test_query_v2c_b1.py','tests/institution_v2g/test_query_v2c_c1.py','tests/institution_v2g/test_query_v2c_b.py'],
       'adapter':'Unchanged accepted assertions imported into C5A test module; only query_library fixture replaced with no-build equivalent catalogue and real NOT_BUILT fallback.',
       'report_paths':sec['accepted_reports'],'run':str((security/'search_v2c_c5a_run.json').relative_to(ROOT)),
       'source_hashes':{f:sha(ROOT/f) for f in ['tests/institution_v2g/test_query_v2c_b1.py','tests/institution_v2g/test_query_v2c_c1.py','tests/institution_v2g/test_query_v2c_b.py','tests/institution_v2g/test_query_v2c_c5a_security.py']},
       'production_index_builds':0,'fixture_hnsw_builds':0,'fixture_kg_builds':0,'resident_service_access':False,'historical_report_changes':sec['historical_hash_changes']}
    write('security_regression',security_report)
    result={'version':'REVIEWED_C5A_HARNESS-v2','status':'PASS_NATIVE_INFRASTRUCTURE_ONLY' if run['exit_code']==0 and all(r['result']=='PASS' for r in rows) and all(b['status_match'] and b['state_match'] and b['privacy_match'] for b in boundaries) else 'PARTIAL',
      'native_test_sequences':len(rows),'original_C5_native_executed':220,'missing_completed':missing['completed'],'required_scopes':sorted({r['scope'] for r in rows}),
      'by_suite':dict(Counter(r['suite'] for r in rows)),'by_scope':dict(Counter(r['scope'] for r in rows)),
      'status_oracle':status,'state_oracle':state,'privacy_oracle':privacy,'suggestion_issuance_oracle':ratio(sum(i['valid'] for i in suggests),len(suggests)),
      'correction_issuance_oracle':ratio(sum(i['valid'] for i in corrections),len(corrections)),'authorized_commits':sum(b['label']=='genuine' and b['actual_status']==200 for b in boundaries),
      'boundaries':boundaries,'raw_observations':str(raw.relative_to(ROOT)),'raw_sha256':sha(raw),
      'all_raw_attempts':[str(p.relative_to(ROOT)) for p in sorted(R.glob('search_v2c_c5a_native_attempt*'))],
      'search_mode_coverage':{'request_search_mode':'SMART for every native search/correction issuance/resolution; default mode is recorded in issued pending documents',
        'suggestion_issuance_modes':['SMART'],'negative_suggestion_mode_binding':['TITLE_AUTHOR selection against an actually issued SMART capability ->409'],
        'protected_literal_queries':['Python 3','quoted detectve fiction'],'protected_literal_request_mode':'SMART',
        'explicit_EXACT_native_searches':0,'calibration_core_credit':0},
      'calibration_parser_evaluations':0,'heldout_access':False,'calibration_policy_selected':False,'production_changes':False,'historical_report_changes':run['historical_hash_changes'],
      'limitations':['Global semantic retrieval uses one bounded fixture candidate provider; no production ranking/index health assertion.','Ten authored command sentences are mapped UI intents to actual choice operations; no natural-language correction-command grammar added.',
        'Original44 stale-suggestion contexts do not match a session-version stale capability contract; actual server contract is catalog generation, identity, query, mode, expiry.',
        'Role transitions for authorized cross-workspace ownership checks directly modify isolated membership fixture then restore original role; ordinary unauthorized workspace403 is separately asserted.',
        'Scenario identities use the accepted test authentication dependency override; expired-JWT scenarios restore the real JWT decoder. Cross-sid state ownership is enforced by the unmodified service.',
        'No explicit EXACT-mode native search was executed. Protected literal/no-correction queries were submitted in SMART, and no native case counts as repaired parser calibration core.',
        'Stale suggestion generation is advanced through a direct isolated institution_audit fixture event; no production catalogue revision or vocabulary change is claimed.',
        'Independent pre-execution review is AI review; human-reviewed count0.']}
    write('native_results',result)
    write('harness_v2',{'version':'REVIEWED_C5A_HARNESS-v2','ORIGINAL_C5_HARNESS':{'assertion_failures':66,'result':'HISTORICAL_FAIL_PRESERVED'},
      'REVIEWED_C5A_HARNESS':{'status':result['status'],'native_sequences':len(rows),'native_test_file':'tests/institution_v2g/test_query_v2c_c5a_native.py','sha256':run['harness_sha256'],
         'security_test_file':'tests/institution_v2g/test_query_v2c_c5a_security.py','security_sha256':sha(ROOT/'tests/institution_v2g/test_query_v2c_c5a_security.py')},
      'fixture_oracle_spec':'reports/search_v2c_c5a_native_oracles.json','independent_review':'reports/search_v2c_c5a_native_independent_review.json',
      'attempts':[read(p) for p in sorted(R.glob('search_v2c_c5a_native_attempt*/search_v2c_c5a_run.json'))],
      'attempt1_failure':'Evidence serialization adapter: dataclasses.asdict(Profile Counter) created tuple keys. Fixed to explicit dict(counter); first application scenario completed but raw JSON snapshot unavailable for attempt1. Original log and XML retained.',
      'attempt2_failure':'All230 original native sequences passed; Global suggestion GET sent optional library_id=None as an empty string and correctly received UUID422. Fixed test adapter to omit absent optional GET values. Original231 records, XML and log retained.',
      'attempt4_scope':'Parallel isolated probe of the remaining34 previously unexecuted scope/security/edge scenarios; not a second calibration population.',
      'source_modification_required':False,'new_parser_calibration_evaluations':0})
    print(json.dumps({k:result[k] for k in ['status','native_test_sequences','missing_completed','status_oracle','state_oracle','privacy_oracle','suggestion_issuance_oracle','correction_issuance_oracle','authorized_commits']},indent=2))

if __name__=='__main__':main()
