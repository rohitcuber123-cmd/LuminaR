"""Final actual-tree evidence for the two exact approved contract applications."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
R=ROOT/'reports';P='institution_v2o3_closure_'
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
def get(name):return json.loads((R/(P+name+'.json')).read_text(encoding='utf-8-sig'))
def put(name,value):(R/(P+name+'.json')).write_text(json.dumps(value,indent=2,default=str)+'\n',encoding='utf8')
def md(name,text):(R/(P+name+'.md')).write_text(text.strip()+'\n',encoding='utf8')


def xml(name):
    path=R/(P+name+'.xml');cases=list(ET.parse(path).iter('testcase'))
    failures=[{'test':c.get('classname','')+'::'+c.get('name',''),'kind':n.tag,'message':n.get('message','')} for c in cases for n in c if n.tag in {'failure','error'}]
    skipped=[{'test':c.get('classname','')+'::'+c.get('name',''),'reason':n.get('message','')} for c in cases for n in c if n.tag=='skipped']
    return {'passed':len(cases)-len(failures)-len(skipped),'failed':len(failures),'skipped':len(skipped),'failures':failures,'skips':skipped,'xml':path.name}


def main():
    baseline=get('baseline');application=get('application')
    manifest=json.loads((R/'institution_v2o3_approval_manifest.json').read_text())
    backend=get('final_backend');front=get('final_frontend')
    assert backend[-1]['group']=='events','Full current-tree backend still running'
    assert {'institution_v2o2','institution_v2o3','institution_v2o3_closure'}<={r['group'] for r in backend}
    assert len(front)==3,'Frontend/build/lint still running'
    assert all('tests' in row for row in backend),backend
    failures=[];skips=[]
    for row in backend:
        result=xml('final_'+row['group']);assert result['failed']==row['failed']
        failures+=result['failures'];skips+=result['skips']
    totals={key:sum(row[key] for row in backend) for key in ('passed','failed','skipped')}
    old_backend=json.loads((R/'institution_v2o2_final_backend.json').read_text())
    old_skips=set()
    for row in old_backend:
        for c in ET.parse(R/f'institution_v2o2_final_{row["group"]}.xml').iter('testcase'):
            if any(n.tag=='skipped' for n in c):old_skips.add(c.get('classname','')+'::'+c.get('name',''))
    original={'J':xml('original_j'),'RAG':xml('original_rag')}
    mutation=xml('mutations')
    actual_full_mutations=xml('final_institution_v2o3_closure')
    mutation_names=[c.get('name','') for c in ET.parse(R/(P+'mutations.xml')).iter('testcase')]
    directive_names=[n for n in mutation_names if n.startswith('test_installed_guard_rejects_compiler_affecting_comment_directive')]
    assert len(directive_names)==8 and mutation['passed']==75 and mutation['failed']==0
    put('mutations',{'status':'PASS','scope':'Installed actual-tree guard assertion bodies and installed pinned helpers; no historical candidate source or helper used in these 75 cases.',
        'focused_run':mutation,'full_backend_group':actual_full_mutations,'compiler_comment_directives':directive_names,
        'directive_count':8,'inherited_security_and_JSX_cases':67,
        'coverage':['Full transport bodies/dependency modules','Canonical tenant scope, foreign IDs and alternate context',
            'Direct/computed/escaped/generated network access and aliases','Imports, re-exports, namespace, dynamic and CommonJS paths',
            'Manual build flow, read-only Librarian guards and backend authority','Raw credentials, worker fences and process/shell access',
            'Custom React props and native semantic/interactive identities','Permitted passive native layout/class/copy/formatting evolution',
            'Exactly two RAG versions and reverse projection; unknown/whitespace/newline/prompt/retrieval/citation/manifest/helper changes rejected'],
        'implementation_change_for_directives':'None. Approved empty source-comment-marker envelope rejects suppression/comment directives; approved pragma/executable checks remain intact.',
        'limits':'Finite adversarial corpus and reviewed source boundary, not a universal JavaScript sandbox. Backend authority and behavior suites remain essential.'})
    text=(R/(P+'final_frontend.log')).read_text(encoding='utf8')
    ft={key:sum(map(int,re.findall(r'^. '+key+r' (\d+)\s*$',text,re.M))) for key in ('tests','pass','fail','skipped')}
    assert ft['tests']==959,ft
    lint=(R/(P+'final_lint.log')).read_text()
    warnings=lambda value:sorted(line for line in value.splitlines() if ': warning ' in line)
    new_warnings=sorted(set(warnings(lint))-set(warnings((R/'institution_v2o2_final_lint.log').read_text())))
    frontend_result={'status':'PASS' if all(row['exit']==0 for row in front) else 'FAIL','totals':ft,'commands':front,
        'production_build':'PASS' if front[1]['exit']==0 else 'FAIL','lint_exit':front[2]['exit'],
        'existing_warning_count':len(warnings(lint)),'new_warning_lines':new_warnings,
        'fresh_actual_tree':True,'frontend_source_modified':False}
    put('frontend_tests',frontend_result)
    backend_result={'status':'PASS' if not failures and all(row['exit']==0 for row in backend) else 'FAIL','totals':totals,
        'groups':backend,'failures':failures,'skipped_tests':skips,
        'skipped_test_ids_equal_O2':{s['test'] for s in skips}==old_skips,
        'original_two_tests_ran_first':original,'fresh_actual_tree':True,
        'inventory':'Complete accepted independent product groups through O.3 plus installed-guard closure tests. Includes all established backend domains and new review/security checks. Not a flat invocation of unrelated model-training/research suites.',
        'prior_actual_O2':{'passed':2689,'failed':2,'skipped':20},'previous_failures_resolved':[
            'tests.institution_v2j.test_diagnostics::test_existing_staff_status_unchanged',
            'tests.test_assistant_backend::test_protected_rag_files_match_original_hashes'],
        'frozen_tests_disabled_or_suppressed':False,
        'events_date_alignment':'Existing accepted runner aligns fixture NOW with current UTC; assertions/fixture source unchanged.'}
    put('backend_tests',backend_result)
    rag=get('rag_grounding_tests');assert len(rag['groups'])==3
    rag['status']='PASS' if all(g['exit']==0 for g in rag['groups']) else 'FAIL'
    rag['totals']={key:sum(g[key] for g in rag['groups']) for key in ('passed','failed','skipped')}
    rag['fresh_actual_tree']=True;rag['no_protected_implementation_change']=True
    rag['scope']='Production grounding/private ownership/session/API tests, all urgent document cases, full institution 2F private assets and lexical fallback. Actual filter/selection/routes and controlled model/validator fixtures; no live Qwen quality benchmark claimed.'
    put('rag_grounding_tests',rag)
    browser=get('browser');assert browser['status']=='PASS'

    # Application is exactly the approved patch; retain its historical proposal
    # metadata rather than editing approved helper bytes to relabel the status.
    approved_files=application['existing_files_modified']+application['new_approved_helpers']
    postimages={}
    for name in application['existing_files_modified']:
        expected=ROOT/'.scratch/institution-v2o3/candidate/LibraryLLM'/name
        same=(ROOT/name).read_bytes().replace(b'\r\n',b'\n')==expected.read_bytes().replace(b'\r\n',b'\n')
        postimages[name]={'sha256':sha(ROOT/name),'matches_exact_approved_staged_postimage_except_checkout_line_endings':same}
        assert same,name
    helper_pins={**manifest['helper_sha256'],'tests/contracts/rag_grounding_v2o2.py':'0f2e567796978ada7ee066fb417d72d74ada76b92f7119244702f9b63c3611b5'}
    helpers_equal={name:hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==digest for name,digest in helper_pins.items()}
    assert all(helpers_equal.values())
    for key,patch in application['patches'].items():assert sha(R/patch['path'])==patch['sha256']
    from scripts.institution_v2i_baseline import capture_state
    from scripts.institution_v2l_baseline import capture_indexes
    state=capture_state();assert 'database_unavailable' not in state
    state['global_KG_metadata']={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in (ROOT/'knowledge_graph/data').glob('*') if p.is_file()}
    norm=lambda value:json.loads(json.dumps(value,default=str))
    state_equal={key:norm(value)==baseline['state'][key] for key,value in state.items()}
    indexes_equal=norm(capture_indexes())==baseline['mongo_indexes']
    changed=[{'path':name,'before':old,'after':sha(ROOT/name) if (ROOT/name).is_file() else None} for name,old in baseline['source_sha256'].items() if not (ROOT/name).is_file() or sha(ROOT/name)!=old]
    unexpected=[row for row in changed if row['path'] not in application['existing_files_modified']]
    prior_report_edits=[name for name,old in baseline['frozen_reports_sha256'].items() if not (ROOT/name).is_file() or sha(ROOT/name)!=old]
    manifest_path='reports/assistant_backend_baseline/hashes.json'
    original_manifest_unchanged=(ROOT/manifest_path).read_bytes()==(ROOT/'.scratch/institution-v2o3/before'/manifest_path).read_bytes()
    all_preserved=all(state_equal.values()) and indexes_equal and not unexpected and not prior_report_edits and original_manifest_unchanged and all(helpers_equal.values())
    preservation={'status':'PASS' if all_preserved else 'FAIL','captured_at':datetime.now(timezone.utc).isoformat(),
        'baseline':P+'baseline.json','state_components_equal':state_equal,'after_state':state,'mongo_index_contracts_equal':indexes_equal,
        'institution_index_collections':len(baseline['mongo_indexes']),'existing_source_edits':changed,'unexpected_source_edits':unexpected,
        'approved_guard_postimages':postimages,'approved_helper_pins_equal':helpers_equal,
        'original_RAG_hash_manifest_unchanged':original_manifest_unchanged,'protected_RAG_qa_raw_sha256':sha(ROOT/'rag/qa.py'),
        'protected_RAG_implementation_changed':False,'Part2I_status_service_sha256':sha(ROOT/'backend/services/library_intelligence_service.py'),
        'native_store_sha256':sha(ROOT/'backend/services/library_intelligence_store.py'),'native_protocol':baseline['native_contract'],
        'prior_reports_verified':len(baseline['frozen_reports_sha256']),'prior_report_edits':prior_report_edits,
        'production_changes':{'global_HNSW_rebuilt':False,'global_KG_rebuilt':False,'Mongo_auth_cutover':False,'production_telemetry_enabled':False,'automatic_rebuild_enabled':False,'commit':False,'deployment':False},
        'environment_classification':'UNKNOWN as previously recorded; no production ownership/exposure/auth-mode change inferred or performed.'}
    put('preservation',preservation)
    passed=backend_result['status']=='PASS' and frontend_result['status']=='PASS' and not any(v['failed'] for v in original.values()) and mutation['failed']==0 and rag['status']=='PASS' and browser['status']=='PASS' and all_preserved and not new_warnings
    final='PASS' if passed else 'FAIL'
    regression={'result':final,'J_guard':'PASS' if not original['J']['failed'] else 'FAIL','RAG_guard':'PASS' if not original['RAG']['failed'] else 'FAIL',
        'full_backend':totals,'full_frontend':ft,'new_regressions':len(failures),'frozen_tests_disabled':False,'unapproved_source_changes':bool(unexpected),
        'production_build':frontend_result['production_build'],'lint_exit':front[2]['exit'],'new_lint_warning_count':len(new_warnings),
        'installed_guard_mutations':mutation,'fresh_browser':browser['status'],'RAG_private_lexical':rag['totals'],'preservation':preservation['status'],
        'approved_patch_hashes':{key:p['sha256'] for key,p in application['patches'].items()},'all_results_from_current_tree':True}
    put('regression',regression)
    md('approval_record',f'''# Part 2O.3 explicit authorization and exact application

The latest user message explicitly approved both narrowly scoped exceptions and the exact digests below. This supersedes the historical pending-approval O.3 preparation reports; those reports remain unchanged evidence.

J: `{application['patches']['J']['sha256']}`

RAG: `{application['patches']['RAG']['sha256']}`

Both hashes were verified before application. Original reviewed frozen-test preimages, three transport modules, backend authority and protected qa.py bytes matched exactly; new helper targets did not already exist. Both patches passed one combined git apply --check --ignore-space-change and were applied together with git apply --ignore-space-change from D:\\SDC. The option was the previously reviewed Windows CRLF context method, with strict byte preimage checks preventing acceptance of source drift. Neither patch was reconstructed or altered.

Applied at {application['applied_at']}. Only the two existing test guards and four helper files from the exact patches changed. The first tests after application were the two original failing assertions, each passing. Original hashes.json and protected rag/qa.py remain unchanged. No later helper/hash exception or authorization weakening was added.

Exact approved helper bytes retain historical proposal/status comments. They were deliberately not relabeled, since that would alter the approved patch. This record and application.json state current approval/application status.

No production authentication, telemetry, global rebuild, commit or deployment authorized or performed. Stop after O.3 closure.
''')
    md('j_contract',f'''# Applied J contract and actual-tree enforcement

Original test name and three exact backend authority hashes retained. The obsolete whole-page hash was replaced only by the exact approved contract. It pins full libraryIntelligence.ts, institutions.ts and api.ts bytes, the Python/analyzer/manifest helpers, complete executable page sections, imports/bindings/control/calls and native worker protocol protection.

Only reviewed passive native HTML ignores fixed literal presentation attributes. Custom React props and native interactive/semantic tags preserve full fingerprints. Passive layout/copy/class/spacing still pass; custom props, button/progress/tag and interaction changes fail.

Actual installed-guard mutation run: {mutation['passed']} passed / {mutation['failed']} failed, including eight TypeScript/compiler comment directives (@ts-ignore, @ts-expect-error, @ts-nocheck, @ts-check, block forms and JSX import source). No helper change or fingerprint recalculation beyond the approved bytes was needed: the approved empty comment-marker envelope and pragma/executable checks already reject these directives. Full regression independently reran this installed-guard group.

Current tenant authority, Admin manual build, Librarian read-only, General User/Platform-only denial, revoked membership, library/session response isolation, no automatic build and native fencing/last-good behavior were validated in fresh backend/frontend/Chromium checks. The boundary is reviewed static source protection plus finite behavioral/security coverage, not a universal JavaScript sandbox.
''')
    md('rag_contract',f'''# Applied exact historical RAG exception

Approved patch `{application['patches']['RAG']['sha256']}` applied unchanged. Original manifest remains raw-byte identical and pinned. Protected rag/qa.py is unchanged, raw SHA256 `{sha(ROOT/'rag/qa.py')}`.

Only LEGACY `0e78a7c780f691b14c8e3a3337f62054e4c117f0c2df7828099d80da90a793c6` or REVIEWED `4a1141649a4ce9b4bce6413627c27557f5817bb8718a4e842a4d12021bd89de3` is accepted. The exact reverse projection still verifies the original frozen hash. Unknown bytes, third versions/newline-only/whitespace changes and attempted manifest/helper/other protected-source rebasing fail. The existing api.py exclusion was not expanded.

The original assertion now passes in the actual tree. Fresh production grounding/private-data/asset/lexical checks: {rag['totals']['passed']} passed / {rag['totals']['failed']} failed / {rag['totals']['skipped']} skipped. Original retrieval/reranking/Qwen/Assistant routing implementation and ownership paths remain unchanged. Selection, session ownership and filter/route contracts are real; model/validator verdict fixtures are controlled, not a new live-model quality guarantee.
''')
    approved_text='\n'.join('- `'+name+'`' for name in approved_files)
    qa={'PART_2O3_RESULT':final,'J_GUARD':regression['J_guard'],'RAG_GUARD':regression['RAG_guard'],
        'FULL_BACKEND':f"{totals['passed']} passed / {totals['failed']} failed / {totals['skipped']} skipped",
        'FULL_FRONTEND':f"{ft['pass']} passed / {ft['fail']} failed / {ft['skipped']} skipped",'NEW_REGRESSIONS':len(failures),
        'FROZEN_TESTS_DISABLED':'NO','UNAPPROVED_SOURCE_CHANGES':'NO' if not unexpected else 'YES','PROTECTED_SOURCE_MODIFIED':'NO',
        'GLOBAL_HNSW_REBUILT':'NO','GLOBAL_KG_REBUILT':'NO','PRODUCTION_AUTH_CHANGED':'NO','PRODUCTION_TELEMETRY_ENABLED':'NO'}
    qa_text='\n'.join(f'{key}: {value}' for key,value in qa.items())
    md('completion',f'''# LuminaR Part 2O.3 protected-contract regression closure

Result: {final}. Both explicitly approved patches applied exactly, with no protected RAG implementation or unrelated application edit. Both original failing assertions ran first and passed. All results below are fresh actual-tree executions, not historical candidate counts.

Full backend: {totals['passed']} passed / {totals['failed']} failed / {totals['skipped']} skipped across {len(backend)} independent accepted product groups through O.3/closure. Existing skipped test IDs match the prior O.2 full suite: {backend_result['skipped_test_ids_equal_O2']}. No frozen test disabled or assertion suppressed. The accepted full inventory spans all established product domains; focused RAG coverage is additional and not double-added to full totals.

Frontend: {ft['pass']} passed / {ft['fail']} failed / {ft['skipped']} skipped. Production build {frontend_result['production_build']}. Lint exit {front[2]['exit']}, {len(warnings(lint))} existing warnings, {len(new_warnings)} new warning lines. Installed current-tree security/mutation checks: {mutation['passed']} passed; eight suppression/compiler comment directive cases included. Additional fresh grounding/private asset/lexical checks: {rag['totals']['passed']} passed.

Fresh Chromium: {browser['status']}, {len(browser['steps'])} checks using actual ASGI/JWT/disposable authenticated Mongo and manually requested native Search/KG fixture builds. Responsive/keyboard/axe, status/progress, unknown denominator, reload, failure/recovery/last-good, current role and tenant switching/revocation checks passed. Intermediate durable counter states are explicitly controlled fixture states, not claimed native timing observations. No unexpected HTTP or page JavaScript errors. Owned DB/artifacts cleaned.

Application patch hashes:

- J: `{application['patches']['J']['sha256']}`
- RAG: `{application['patches']['RAG']['sha256']}`

Exact approved contract files:

{approved_text}

Additional new closure-only test/scripts/reports are listed with hashes in changed_files.json. No pre-existing application source changed. Approved historical helper-status labels are preserved as exact approved bytes; approval_record.md/application.json supersede their preparation status.

Preservation: {preservation['status']}. TEST {state['TEST']['current_eligible_books']} eligible books / {state['TEST']['holdings']} holdings / {state['TEST']['assets']} assets; global estimated {state['global_book_count']:,}; {len(baseline['mongo_indexes'])} institution index contracts equal. All measured native jobs/pointers/generations/artifacts, tenant records, private logical/filesystem state and global HNSW/KG metadata match the pre-application snapshot. I service/store, J operator authorization, L native worker, N fail-closed logic, O page/transport/progress and protected RAG implementation preserved. {len(baseline['frozen_reports_sha256'])} prior reports unchanged. No production cutover, telemetry activation, automatic/global rebuild, commit or deployment. No Part 2P started.

```text
{qa_text}
```

Stop after Part 2O.3 closure.
''')
    paths=set(ROOT.glob('scripts/institution_v2o3_closure*.py'))|set((ROOT/'tests/institution_v2o3_closure').rglob('*'))|set(R.glob(P+'*'))|{ROOT/name for name in approved_files}
    entries=[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(paths,key=str) if p.is_file() and '__pycache__' not in str(p) and p.name!=P+'changed_files.json']
    put('changed_files',{'base_branch':baseline['branch'],'base_HEAD':baseline['head'],'approved_existing_guard_edits':changed,
        'approved_contract_files':approved_files,'new_validation_and_report_files':'All listed closure files outside approved_contract_files are new test/validation/evidence artifacts, not application feature code.',
        'files':entries,'inventory_self_hash_excluded':True,'unexpected_source_changes':unexpected,'prior_report_changes':prior_report_edits,
        'git_status_before':P+'baseline.json','git_status_after':subprocess.check_output(['git','status','--porcelain=v1','-uall'],cwd=ROOT,text=True).splitlines(),
        'commit_or_deploy':False})
    print(json.dumps({'result':final,'backend':totals,'frontend':ft,'installed_mutations':mutation['passed'],'RAG_private_lexical':rag['totals'],'browser':browser['status'],'preservation':preservation['status']}))
    assert passed,'Executed checks or preservation failed; do not claim closure PASS'


if __name__=='__main__':main()
