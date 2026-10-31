"""Close the authorization-gated O.3 preparation; no protected patch applied."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
R=ROOT/'reports';P='institution_v2o3_'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def get(name):return json.loads((R/(P+name+'.json')).read_text())
def put(name,value):(R/(P+name+'.json')).write_text(json.dumps(value,indent=2,default=str)+'\n',encoding='utf8')
def md(name,text):(R/(P+name+'.md')).write_text(text.strip()+'\n',encoding='utf8')


def xml(name):
    path=R/(P+name+'.xml');cases=list(ET.parse(path).iter('testcase'))
    failures=[{'test':c.get('classname','')+'::'+c.get('name',''),'message':n.get('message','')} for c in cases for n in c if n.tag in {'failure','error'}]
    skips=sum(any(n.tag=='skipped' for n in c) for c in cases)
    return {'passed':len(cases)-len(failures)-skips,'failed':len(failures),'skipped':skips,'failures':failures,'xml':path.name}


def frontend(name):
    text=(R/(P+name+'.log')).read_text(encoding='utf8')
    return {key:sum(map(int,re.findall(r'^. '+key+r' (\d+)\s*$',text,re.M))) for key in ('tests','pass','fail','skipped')}


def main():
    base=get('baseline');approval=get('approval_manifest');mut=xml('candidate_mutations');behavior=get('jsx_behavior')
    assert mut['failed']==0 and behavior['status']=='PASS'
    j=xml('current_j');rag=xml('current_rag')
    expected={'tests.institution_v2j.test_diagnostics::test_existing_staff_status_unchanged','tests.test_assistant_backend::test_protected_rag_files_match_original_hashes'}
    assert {f['test'] for row in (j,rag) for f in row['failures']}==expected
    staff=[frontend(name) for name in ('staff_intelligence','staff_controls')]
    fresh_front={k:sum(row[k] for row in staff) for k in staff[0]};assert fresh_front['tests']==78 and fresh_front['fail']==0
    old=json.loads((R/'institution_v2o2_current_regression.json').read_text())
    put('mutations',{'status':'PASS','scope':'Exact proposed assertions in scratch source fixtures, not applied main guards.',**mut,
        'jsx_specific_cases':13,'inherited_security_cases':54,'existing_frontend_assertions_on_JSX_fixtures':behavior,
        'limits':'Finite mutation corpus; trusted compiler/React/dependencies and future presentation accessibility require separate behavior review. No JavaScript sandbox claim.'})
    put('backend_tests',{'authorization':'AWAITING_EXPLICIT_APPROVAL','fresh_original_guard_tests':{'J':j,'RAG':rag},
        'fresh_current_totals':{'passed':0,'failed':2,'skipped':0},'candidate_assertion_fixtures':mut,
        'full_backend_this_phase':'NOT_RUN: Step 1 requires preparing final patches and stopping when approval is unavailable.',
        'last_verified_full_backend':{'phase':'2O.2','totals':old['backend_totals'],'evidence':'institution_v2o2_current_regression.json','fresh_O3_run':False},
        'post_approval_pending':['Original two guards','J mutations','RAG grounding/security','tenant authority','lexical fallback','native HNSW/KG protocol','full backend'],
        'frozen_tests_suppressed':False,'new_observed_regressions':0})
    put('frontend_tests',{'fresh_focused':fresh_front,'commands':['npm run test:intelligence','npm run test:intelligence-controls'],
        'owned_mutant_behavior_fixtures':behavior,'last_verified_full_frontend':{'phase':'2O.2','totals':old['frontend'],'fresh_O3_run':False},
        'full_frontend_this_phase':'NOT_RUN pending approval, per Step 1 stop condition.','production_build_this_phase':'NOT_RUN','lint_this_phase':'NOT_RUN',
        'last_verified_build':old['production_build'],'last_verified_lint_exit':old['lint_exit'],
        'harness_repairs':'Initial Windows .cmd pipe parsing and out-of-src JSX React binding errors preserved in initial/transform_error logs. Corrected fixture runner uses node directly and an explicit fixture-only React import. No product or test assertion changed.'})
    from scripts.institution_v2i_baseline import capture_state
    from scripts.institution_v2l_baseline import capture_indexes
    state=capture_state();assert 'database_unavailable' not in state
    state['global_KG_metadata']={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in (ROOT/'knowledge_graph/data').glob('*') if p.is_file()}
    norm=lambda x:json.loads(json.dumps(x,default=str))
    equal={k:norm(v)==base['state'][k] for k,v in state.items()}
    source_changes=[n for n,h in base['source_sha256'].items() if not (ROOT/n).exists() or sha(ROOT/n)!=h]
    report_changes=[n for n,h in base['frozen_reports_sha256'].items() if not (ROOT/n).exists() or sha(ROOT/n)!=h]
    indexes_equal=norm(capture_indexes())==base['mongo_indexes']
    manifest='reports/assistant_backend_baseline/hashes.json'
    manifest_equal=(ROOT/manifest).read_bytes()==(ROOT/'.scratch/institution-v2o3/before'/manifest).read_bytes()
    preservation={'status':'PASS' if all(equal.values()) and indexes_equal and not source_changes and not report_changes and manifest_equal else 'FAIL',
        'captured_at':datetime.now(timezone.utc).isoformat(),'state_components_equal':equal,'after_state':state,'index_contracts_equal':indexes_equal,
        'existing_source_changes':source_changes,'prior_report_changes':report_changes,'prior_reports_verified':len(base['frozen_reports_sha256']),
        'original_RAG_manifest_unchanged':manifest_equal,'protected_RAG_source_modified':False,'actual_frozen_guards_modified':False,
        'I_status_optimization_sha256':sha(ROOT/'backend/services/library_intelligence_store.py'),
        'native_protocol':base['native_contract'],'no_actions':{'global_HNSW_rebuild':True,'global_KG_rebuild':True,'production_auth_cutover':True,'production_telemetry_activation':True,'automatic_rebuild':True,'commit':True,'deploy':True}}
    put('preservation',preservation);assert preservation['status']=='PASS'
    put('regression',{'result':'PARTIAL','J_guard':'AWAITING_APPROVAL','RAG_guard':'AWAITING_APPROVAL',
        'candidate_mutations':mut,'fresh_frontend':fresh_front,'known_current_guard_failures':[j,rag],
        'full_backend_last_verified':old['backend_totals'],'full_frontend_last_verified':old['frontend'],
        'full_suites_fresh_this_phase':False,'reason':'Step 1 stop condition without explicit approvals. No protected change applied.',
        'new_observed_regressions':0,'preservation':preservation['status']})
    md('approval_record',f'''# Part 2O.3 approval record

Authorization: NOT RECEIVED for either protected exception. The latest request supplies context hashes and conditional application instructions; it does not say that either exception is approved. Earlier continue messages likewise do not identify/approve protected changes.

Step 1 explicitly requires: “If approval is not available, prepare the final patches and stop without applying protected changes.” That condition governs this phase. No patch was applied anywhere; exact proposed assertion text was staged/compiled only in owned scratch fixtures. Neither actual frozen test was changed or disabled. Steps 3/4 and the post-application full Step 5 sequence remain pending.

Original O.2 J patch SHA `{approval['J']['supersedes']}` was verified and preserved. The audited O.3 JSX correction changes the proposed helper and its proposed manifest, so approval of that earlier digest would not approve the revised candidate.

Final J candidate: {approval['J']['path']}

SHA256: `{approval['J']['sha256']}`

Final RAG candidate: {approval['RAG']['path']}

SHA256: `{approval['RAG']['sha256']}` (byte-identical to O.2's RAG proposal).

Both pass git apply --check --ignore-space-change against the actual unchanged tree. This is a check, not application. Proposed reviewed helper fingerprints were generated only for the audited candidate from the byte-verified accepted O page and unchanged transport/backend hashes. No accepted manifest or original hashes.json was updated.

Separate explicit authorization must identify the final J exception and/or the exact RAG exception above. No production deployment, Mongo authentication cutover, telemetry or rebuild approval is inferred.
''')
    md('j_contract',f'''# J JSX exception audit and final candidate

Status: AWAITING_APPROVAL; actual J guard remains unchanged and failing. Final candidate SHA `{approval['J']['sha256']}`.

The O.2 analyzer skipped literal className/title/aria-label/aria-describedby/htmlFor/id attributes without first requiring a native passive element. That wrongly exempted custom React component props. The O.3 analyzer ignores those literals only when tag is in the reviewed native passive allowlist. PageHeading, StatePanel, Modal, TargetCard and any other custom component retain every prop in their complete executable fingerprint.

Native details/summary/label/progress/button are separated from passive layout elements. They retain tag identity and all attributes, including literal presentation attributes. This catches button-to-span, progress-to-div, summary-to-paragraph and click-to-hover changes. Passive section/article layout and container-class edits still pass. All executable expressions, events, bindings, imports, compiler/comment checks remain protected. No whole-page byte identity check is reintroduced.

Full raw fingerprints remain exactly unchanged for libraryIntelligence.ts, institutions.ts and api.ts. Original three backend authority hashes and the native protocol guard remain in the proposed assertion. The actual working page, helpers, CSS, backend and native worker are unchanged.

Candidate checks: {mut['passed']} passed, including inherited 54 source/security/exact-RAG cases and 13 new JSX cases. Existing complete Staff frontend groups: {fresh_front['pass']} passed. Original existing behavior assertions also ran in owned page fixtures: original and allowed passive layout passed; native button/progress/interaction mutants caused their intended role/dialog/progress failures. Those expected mutant failures and early harness setup failures are retained separately from real-product results.

The helper/manifest are proposed audited revisions, not approved contracts. Static fingerprints and finite behavior tests do not prove every future accessibility/vendor/runtime condition. Full post-application regression remains pending explicit approval under Step 1.
''')
    md('rag_contract',f'''# Exact RAG exception retained

Status: AWAITING_APPROVAL. Final patch SHA `{approval['RAG']['sha256']}` is unchanged from O.2. Original hashes.json, protected rag/qa.py, Qwen, retrieval/ranking and Assistant routing are untouched.

Allowed qa.py raw SHA256 values only:

- LEGACY_SHA256: 0e78a7c780f691b14c8e3a3337f62054e4c117f0c2df7828099d80da90a793c6
- REVIEWED_SHA256: 4a1141649a4ce9b4bce6413627c27557f5817bb8718a4e842a4d12021bd89de3

The exact reverse projection to the original frozen bytes is retained. The unchanged original manifest is pinned by the proposal. Unknown bytes, whitespace/newline-only variants, changed prompts/retrieval/citations/grounding/identity, modified helpers/manifests and other protected source changes fail. Both exact positive versions and all eleven RAG negative cases passed again in O.3 candidate fixtures.

Actual original RAG guard still fails against the historic source delta. Passing candidate tests do not authorize it. Prior semantic grounding/ownership evidence is preserved in institution_v2o2_rag_source_review.md and institution_v2o2_rag_grounding_tests.json; that focused run had 273 grounding checks plus 183 asset-security and 3 lexical checks passing. It was not rerun or represented as fresh O.3 semantic validation. After explicit approval, run the original assertion first, then the full requested grounding/security/regression sequence without suppressing failures.
''')
    md('completion',f'''# LuminaR Part 2O.3 — authorization-gated final preparation

PART_2O3_RESULT: PARTIAL. Both protected exceptions await separate explicit authorization. Step 1 requires stopping after final patch preparation when approval is unavailable; neither protected change was applied.

The J candidate now limits ignored literal presentation attributes to reviewed passive native tags. Custom React props and interactive/semantic native tags remain fully fingerprinted. Full transport, backend authority and native protocol protections remain. Final J SHA256: `{approval['J']['sha256']}`.

The RAG candidate is byte-identical to O.2 and retains exactly the two allowed qa.py versions, exact original reverse projection and unchanged original manifest. RAG SHA256: `{approval['RAG']['sha256']}`.

Fresh O.3 checks: original two assertions both still fail as expected; candidate mutation suite {mut['passed']} passed / {mut['failed']} failed; complete focused Staff frontend groups {fresh_front['pass']} passed / {fresh_front['fail']} failed / {fresh_front['skipped']} skipped. Existing role/dialog/progress tests passed on original and allowed passive layout fixtures and detected native/interaction mutants. Expected mutant failures and harness repairs are explicitly recorded.

Last full actual-tree result is O.2: 2689 passed / 2 failed / 20 skipped. Last full frontend is O.2: 959 passed / 0 failed / 0 skipped, with production build and lint passing. Those full suites/build/lint were NOT rerun in O.3 because no application was authorized. They are historical verified results, not fresh O.3 full-pass claims. New observed product regressions: 0 within this review scope.

Preservation: {preservation['status']}; no pre-existing source edits, no accepted report edits, original manifest and protected RAG bytes unchanged, TEST {state['TEST']['current_eligible_books']} eligible / {state['TEST']['holdings']} holdings / {state['TEST']['assets']} assets and global estimated {state['global_book_count']:,}. Native/job/tenant/private state and global artifact metadata equal the O.3 starting snapshot. {len(base['frozen_reports_sha256'])} prior reports preserved. No auth cutover, telemetry activation, automatic or global rebuild, commit or deployment.

Exact new files and checksums are in changed_files.json. Approval record and both final patches are ready. After approval, apply only the specifically approved revision, run the original two assertions first, then every requested focused/full suite, build and lint. Stop O.3 here.

```text
PART_2O3_RESULT: PARTIAL
J_GUARD: AWAITING_APPROVAL
RAG_GUARD: AWAITING_APPROVAL
FULL_BACKEND: 2689 passed / 2 failed / 20 skipped
FRONTEND: 959 passed / 0 failed / 0 skipped
NEW_REGRESSIONS: 0
PROTECTED_SOURCE_MODIFIED: NO
GLOBAL_HNSW_REBUILT: NO
GLOBAL_KG_REBUILT: NO
PRODUCTION_AUTH_CHANGED: NO
PRODUCTION_TELEMETRY_ENABLED: NO
```

FULL_BACKEND and FRONTEND above are the last verified O.2 full runs. Fresh O.3 results are separately stated above and in backend_tests.json/frontend_tests.json.
''')
    paths=set(ROOT.glob('scripts/institution_v2o3*.py'))|set((ROOT/'tests/institution_v2o3').rglob('*'))|set(R.glob(P+'*'))
    paths.update(p for p in (ROOT/'.scratch/institution-v2o3/proposed').rglob('*') if p.is_file())
    paths.update(p for p in (ROOT/'.scratch/institution-v2o3/candidate').rglob('*') if p.is_file() and 'node_modules' not in p.parts)
    paths.update(p for p in (ROOT/'frontend/.scratch/institution-v2o3').rglob('*') if p.is_file())
    entries=[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(paths,key=str) if p.is_file() and '__pycache__' not in str(p) and p.name!=P+'changed_files.json']
    put('changed_files',{'existing_source_edits':source_changes,'new_O3_files':entries,'inventory_self_hash_excluded':True,
        'owned_candidate_root':'.scratch/institution-v2o3/candidate','owned_UI_fixtures':'frontend/.scratch/institution-v2o3 (only isolated copies; no actual frontend edit)',
        'compiler_copy_excluded_from_inventory':'Unmodified installed TypeScript tooling copied into owned candidate node_modules; no new dependency or vendor edit.',
        'actual_protected_changes_applied':False,'prior_report_changes':report_changes,'git_status_before':P+'baseline.json',
        'git_status_after':subprocess.check_output(['git','status','--porcelain=v1','-uall'],cwd=ROOT,text=True).splitlines()})
    print(json.dumps({'result':'PARTIAL','approval':'AWAITING','mutations':mut['passed'],'fresh_frontend':fresh_front,'preservation':preservation['status'],'protected_applied':False}))


if __name__=='__main__':main()
