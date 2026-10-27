"""Read-only historical C5 native audit. Never opens new calibration/heldout data."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reports'

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(name, value):
    path=R/('search_v2c_c5a_'+name+'.json')
    path.write_text(json.dumps(value,indent=2,default=str)+'\n',encoding='utf8')
    return path

def old_rows():
    return [json.loads(line) for line in (R/'search_v2c_c5_calibration.jsonl').read_text().splitlines() if line.strip()]

MISSING_BINDINGS = [
 ('scince fiction','Science fiction','correction_keep'),
 ('scince fiction','Science fiction','correction_apply'),
 ('histroy','History','correction_keep'),
 ('histroy','History','correction_apply'),
 ('romnace','Romance','correction_keep'),
 ('romnace','Romance','correction_apply'),
 ('netwroking','Networking','correction_keep'),
 ('ficiton','Fiction','correction_apply'),
 ('astronmy','Astronomy','correction_keep'),
 ('astronmy','Astronomy','correction_apply'),
]

def main():
    original=old_rows(); byid={r['query_id']:r for r in original}
    native_path=R/'search_v2c_c5_native/observations.jsonl'
    observations=[json.loads(line) for line in native_path.read_text().splitlines() if line.strip()]
    failed=[r for r in observations if r['result']=='FAIL']
    xml=ET.parse(R/'search_v2c_c5_native.xml')
    xml_ids={t.attrib['name'].split('[',1)[1].rstrip(']') for t in xml.findall('.//testcase') if t.find('failure') is not None}
    assert len(failed)==66 and xml_ids=={r['query_id'] for r in failed}
    inventory=[]
    for r in failed:
        b=r['boundaries'][0]; action=r['action']; scope=r['scope']; staff='STAFF' in scope
        fixture=staff
        classification='FIXTURE_DEFECT' if fixture else 'TEST_ADAPTER_DEFECT'
        if action=='apply_correction_after_context_switch':
            expectation="status404 AND body {'detail':'Library resource not found.'}"
            assertion_line=60
            reason=('Second library actor4 joins as GENERAL_USER; native_context promotes only the first library to LIBRARIAN. Fresh staff authorization stops at403 before load_choice.' if staff else 'Second public library is authorized for patron. load_choice finds no matching owner+library pending row and correctly returns404 with Search choice is unavailable body; private library concealment text is inapplicable.')
            remediation=('Promote actor4 in both libraries when testing authorized wrong-library choice; also separately retain403 workspace-denial test.' if staff else 'Assert current choice-unavailable404 and exact non-mutation; obtain a real correction, not Fiction4 proxy.')
        else:
            expectation="status404 AND body {'detail':'Library resource not found.'}"
            assertion_line=31
            reason='Alternate user2 has GENERAL_USER membership; request inherits staff=True, so current authorization returns403 before the cross-user pending owner check. This never tested an authorized alternate staff user.'
            remediation='Give alternate actor2 staff membership for the wrong-user ownership scenario; retain separate403 unauthorized staff request. Execute genuine owner recovery and replay.'
        inventory.append({'original_assertion_id':r['query_id']+'::test_calibration_native_sequence:'+str(assertion_line),
          'original_case_id':r['query_id'],'original_expectation':expectation,'raw_authored_expected_status':r['raw_expected_status'],
          'actual_observation':{'status':b['status'],'body':b['body'],'error':r.get('error'),'boundary_count':len(r['boundaries']),
                                'exact_state_non_mutation':b['state_before']==b['state_after']},
          'classification':classification,'scope':scope,'action':action,'rationale':reason,
          'supporting_evidence':[{'file':'reports/search_v2c_c5_native/observations.jsonl','line':observations.index(r)+1,'sha256':digest(native_path)},
              {'file':'tests/institution_v2g/test_query_v2c_c5_calibration.py','line':assertion_line},
              {'file':'tests/institution_v2g/test_query_v2c_c4_native.py','lines':'33-43: staff membership promotion only lid; other retains patron'},
              {'file':'search/interaction_api.py','lines':'22-39,107-108: authorized before load_choice'},
              {'file':'search/query_interaction.py','lines':'123-130: owner tuple query and unavailable404'}],
          'proposed_remediation':remediation,'production_source_modification_required':False,
          'historical_proxy_limit':'All original C5 pending objects were Fiction4 ambiguous choices, not correction issuance.'})
    write('harness_failure_audit',{'version':'C5A-native-historical-audit-v1','status':'AUDITED_SOURCE_AND_EXACT_OBSERVATIONS',
      'ORIGINAL_C5_HARNESS':{'result':'FAIL_PRESERVED','historical_failed':66,'native_xml_sha256':digest(R/'search_v2c_c5_native.xml'), 'observations_sha256':digest(native_path)},
      'audited':len(inventory),'classifications':dict(Counter(x['classification'] for x in inventory)),
      'stale_historical_contract':0,'actual_application_defects':0,'indeterminate':0,
      'independent_review':'PENDING_SEPARATE_REVIEW','cases':inventory})
    missing=[]
    for number,binding in enumerate(MISSING_BINDINGS,1):
        ident=f'v2:v2cc-authored-c04_correction_actions-{number:02d}'; old=byid[ident]
        missing.append({'existing_case_id':ident,'scope':old['scope_type'],'actor':{'sub':'2','sid':'c5a-login','role':'GENERAL_USER'},
          'library':None,'workspace':'GLOBAL','input_query':old['query_text'],'issuance_query':binding[0],
          'required_fixture':{'global_category':binding[1],'global_book':{'title':binding[1]+' C5A fixture','subjects':binding[1]}},
          'expected_issuance':{'kind':'typo','from':binding[0],'to':binding[1],'operation':binding[2]},
          'expected_api_status':200,'expected_state_behavior':'Original server-issued correction operation commits once; same owner/JWT sid/Global workspace; rejected inputs do not consume pending.',
          'prior_failure':'Unexecuted; no sequence_steps, expected_action or prior offered correction existed.',
          'adapter_contract':'Authored sentence is recorded UI intent, not new natural-language command grammar. Adapter chooses correction_apply/keep from the genuine server-issued pending record.',
          'prior_label_limit':'Row07 preserves Networking spelling; row08 requests Fiction from ficiton. They intentionally do not share one fabricated prior.',
          'corrected_execution_result':'PENDING'})
    write('native_missing_contexts',{'version':'C5A-native-missing-v1','original_missing':10,'completed':0,'cases':missing})
    oracles={'version':'C5A-native-oracles-v1','written_before_native_execution':True,'review_status':'PENDING_INDEPENDENT_REVIEW',
      'scope_matrix':['GLOBAL','PUBLIC_TENANT_PATRON','PUBLIC_TENANT_STAFF','PRIVATE_TENANT_PATRON','PRIVATE_TENANT_STAFF'],
      'fixtures':{'database':'random luminar_institution_v2g_test_*; deleted by accepted conftest lifecycle',
                  'library_creation':'real register/join/inventory APIs; staff promoted in both libraries',
                  'indexes':'Only ordinary Mongo fixture indexes; no HNSW/KG builds, no production data access',
                  'global_lexical':'in-memory SQLite lexical_values fixture through production LexicalSearchStore._query',
                  'retrieval_limit':'Global semantic candidate provider is isolated fixture provider; no ranking/model/production index claims. Tenant NOT_BUILT path uses actual bounded catalogue fallback.',
                  'personalization':'Actual get_profile(... personalized=True) from isolated reading_list; snapshots include profile cache and Mongo reading_list, not only HTTP statuses'},
      'suggestion':{'issuance':'GET /query/suggestions; assert actual opaque id and type SUBJECT/AUTHOR/TITLE from scoped canonical fixture',
                    'selection':'POST /query/suggestions/select using exact issued id; status200 and insert_text/type; no accepted/pending/personalization mutation',
                    'staleness':'Suggestion capabilities bind actor/sid/library/workspace/query/mode/catalogue generation/expiry; no session_id or accepted context version exists. Original resume_stale_suggestion accepted-version premise is stale; record accepted revision selection separately and then test real generation staleness.',
                    'rejections':'forged/wrong user/sid/library/workspace/expired capability/generation each non-mutating; true owner can still select if capability unchanged'},
      'correction':{'issuance':'Actual GlobalQuerySearch.search or tenant_search; response clarification id; Mongo row must contain correction_apply AND correction_keep with typo from/to; no fabricated UUID or typed-choice proxy',
                    'commit':'200 exactly one accepted version increment and receipt; pending used=True; same user/sid/library/workspace; semantic wording remains typo on keep, canonical subject on apply',
                    'non_mutation':'Compare full accepted/pending Mongo rows, actual profile cache and reading_list before/after every denied request',
                    'expiry':'Expired pending410 (or404 only if Mongo TTL removed target); expired accepted session409; expired authentication401',
                    'recovery':'After forged, wrong user/sid/library/workspace rejection original genuine choice200, replay409 and exact state unchanged',
                    'revocation':'404 private membership loss removes only matching actor/library/workspace accepted,pending/profile ownership; independent Global/other-library/other-sid scopes retained',
                    'no_correction':'Protected literal and unrelated phrase produce no correction clarification'},
      'security':['private outsider and platform admin without membership generic404; no canonical vocabulary','staff unauthorized workspace403','JWT expiry401 before projection/choice loading','B1 forged-choice single-use and C1 ownership tuple remain unchanged'],
      'calibration_parser_evaluations':0,'heldout_access':False,'production_source_changes':False}
    write('native_oracles',oracles)
    print(json.dumps({'audited':66,'classes':dict(Counter(x['classification'] for x in inventory)),'missing_identified':10}))

if __name__=='__main__':main()
