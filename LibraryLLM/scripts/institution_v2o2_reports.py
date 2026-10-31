"""O.2 final evidence: candidate and current-tree results stay distinct."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
R=ROOT/'reports';PREFIX='institution_v2o2_'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def get(name):return json.loads((R/(PREFIX+name+'.json')).read_text(encoding='utf-8-sig'))
def put(name,obj):(R/(PREFIX+name+'.json')).write_text(json.dumps(obj,indent=2,default=str)+'\n',encoding='utf8')
def md(name,text):(R/(PREFIX+name+'.md')).write_text(text.strip()+'\n',encoding='utf8')


def xml(name):
    path=R/(PREFIX+name+'.xml');cases=list(ET.parse(path).iter('testcase'))
    fail=[{'test':c.get('classname','')+'::'+c.get('name',''),'type':n.tag,'message':n.get('message','')} for c in cases for n in c if n.tag in {'failure','error'}]
    skip=sum(any(n.tag=='skipped' for n in c) for c in cases)
    seconds=sum(float(s.get('time','0')) for s in ET.parse(path).iter('testsuite'))
    return {'passed':len(cases)-len(fail)-skip,'failed':len(fail),'skipped':skip,'failures':fail,'xml':path.name,'seconds':seconds}


def main():
    base=get('baseline');approval=get('approval_manifest')
    backend=get('final_backend');assert backend[-1]['group']=='events','Full current-tree run unfinished'
    assert {'institution_v2o1','institution_v2o2'}<={r['group'] for r in backend}
    assert all('tests' in r for r in backend),backend
    failures=[]
    for row in backend:failures+=xml('final_'+row['group'])['failures']
    totals={k:sum(r[k] for r in backend) for k in ('passed','failed','skipped')}
    expected={'tests.test_assistant_backend::test_protected_rag_files_match_original_hashes','tests.institution_v2j.test_diagnostics::test_existing_staff_status_unchanged'}
    unexpected=[f for f in failures if f['test'] not in expected]
    front=get('final_frontend');log=(R/(PREFIX+'final_frontend.log')).read_text(encoding='utf8')
    ft={k:sum(map(int,re.findall(r'^. '+k+r' (\d+)\s*$',log,re.M))) for k in ('tests','pass','fail','skipped')}
    assert ft['tests']==959,ft
    lint=(R/(PREFIX+'final_lint.log')).read_text()
    lintlines=lambda s:sorted(line for line in s.splitlines() if ': warning ' in line)
    new_lint=sorted(set(lintlines(lint))-set(lintlines((R/'institution_v2o1_final_lint.log').read_text())))
    mutations=xml('mutations');assert mutations['failed']==0,mutations
    tree=ET.parse(R/(PREFIX+'mutations.xml'))
    names=[c.get('name','') for c in tree.iter('testcase')]
    mutation_result={'status':'PASS','execution_scope':'Isolated source fixtures execute the actual proposed frozen-test assertion bodies with their pinned helpers/imports; no current-tree guard modified.',
        **mutations,'J_positive':sum(n.startswith('test_proposed_J_guard_accepts') for n in names),
        'J_negative':sum(n.startswith('test_proposed_J_guard_rejects') for n in names),
        'RAG_exact_positive':sum(n.startswith('test_proposed_RAG_guard_accepts') for n in names),
        'RAG_negative':sum(n.startswith('test_proposed_RAG_guard_rejects') for n in names),
        'grounding_behavior_checks':sum(n.startswith(('test_work_id','test_document_definition','test_no_authorized','test_claims')) for n in names),
        'cases':names,'early_harness_repairs':['Missing frozen J baseline input added to temporary mutation fixture; tests initially failed before enforcement, never counted as rejections.',
            'Patch output switched to binary LF writing to prevent Windows CRCRLF; no source-protection normalization added.',
            'A later wall-clock stall caused one probe TimeoutExpired. All original timeouts retained, unchanged full mutation inventory rerun.'],
        'retained_initial_evidence':[PREFIX+'mutations_initial.xml',PREFIX+'mutations_stalled.xml'],
        'valid_alias_and_namespace_confirmation':xml('alias_confirmation'),
        'limits':'Finite negative corpus, not universal adversarial JavaScript proof. Executable-source boundary, pinned dependencies and backend authority remain the guarantee within reviewed scope.'}
    put('j_mutation_tests',mutation_result)

    candidates=get('candidate_backend');assistant=get('candidate_assistant_owned')
    final_j=xml('candidate_j_confirmed')
    confirmed=[]
    for row in candidates:
        if row['group']=='assistant':confirmed.append(assistant)
        elif row['group']=='j':confirmed.append({**row,**final_j,'exit':0})
        else:confirmed.append(row)
    ct={k:sum(r[k] for r in confirmed) for k in ('passed','failed','skipped')}
    assert not ct['failed'] and all(r['exit']==0 for r in confirmed),confirmed
    candidate={'status':'PASS','scope':'Bounded complete J, Assistant backend module, tenant authority, native Search/KG and native protocol suites in isolated source checkout; not a run of all accepted product groups.',
        'root':str(ROOT/'.scratch/institution-v2o2/candidate/LibraryLLM'),'backend_totals':ct,'groups':confirmed,
        'contract_and_grounding_tests':mutation_result,'current_tree_contracts_applied':False,
        'initial_candidate_backend':candidates,
        'candidate_fixture_failures_resolved':{'assistant':'Three index-initialization imports failed with intentionally unavailable port-1 Mongo. Unchanged full module then passed 68 using owned authenticated Mongo.',
            'final_J_attempt':'54 fixture setup errors during shared wall-clock stall; unchanged final candidate suite then passed 54 in candidate_j_confirmed.xml.'},
        'candidate_product_sources':'Exact copies of starting product implementation; only proposed frozen tests/helpers differ.',
        'frontend_validation':'Actual-tree frontend suite exercises identical unchanged product sources. No separate candidate npm run claimed.'}
    put('candidate_tests',candidate)

    rag=get('rag_grounding_tests');rag['totals']={k:sum(g[k] for g in rag['groups']) for k in ('passed','failed','skipped')}
    rag['status']='PASS' if all(g['exit']==0 for g in rag['groups']) else 'FAIL'
    rag['guard_candidate']={'positive_versions':mutation_result['RAG_exact_positive'],'rejected_mutations':mutation_result['RAG_negative'],'original_manifest_pinned_and_unchanged':True,
        'accepted_sha256':['0e78a7c780f691b14c8e3a3337f62054e4c117f0c2df7828099d80da90a793c6','4a1141649a4ce9b4bce6413627c27557f5817bb8718a4e842a4d12021bd89de3'],
        'newline_normalized_third_version_accepted':False}
    rag['scope']='Focused production grounding/private-document/session/API/latency/attention/decoding, all urgent-document cases, full institution 2F asset security, and lexical fallback. Existing source tests run unchanged. No training/dataset-generation/experimental ranking research executed.'
    rag['model_scope']='Real selection, fast filter, private ownership and route code; controlled model answers/validator verdicts. No live Qwen quality benchmark or semantic perfection claim.'
    rag['persistent_documents']='Existing urgent-document read-only fixtures ran successfully; no user content copied into approval package.'
    rag['additional_coverage']=['Full real fast filter reaches unchanged validator for document definitions; supported and unsupported verdicts propagated.',
        'Foreign evidence excluded before validation and generation; no selected evidence means neither called.',
        'Claim-bearing questions receive no definition category. Work-ID discriminator grants no ownership.',
        'PrivateDocuments.owned checks current owner, session, ACTIVE state and expiry before index access; selected runtime is lock-scoped and cleared.',
        'Full private cache/API tests verify cross-account denial, logout, missing documents, error cleanup and no context leakage.']
    put('rag_grounding_tests',rag)
    put('current_regression',{'result':'PARTIAL','backend_status':'FAIL','backend_totals':totals,'groups':backend,'failures':failures,
        'known_unapplied_contract_failures':sorted(expected),'unexpected_failures':unexpected,
        'current_tree_unapplied_proposals_not_reported_as_pass':True,
        'frontend':ft,'frontend_commands':front,'production_build':'PASS' if front[1]['exit']==0 else 'FAIL',
        'lint_exit':front[2]['exit'],'existing_lint_warnings':len(lintlines(lint)),'new_lint_warnings':new_lint,
        'extra_focused_RAG':rag['totals'],'extra_lexical':next(g for g in rag['groups'] if g['group']=='lexical_fallback'),
        'browser':'O.1 actual Chromium evidence retained and product source identity reverified; no fresh O.2 Chromium run claimed.',
        'events':'Accepted UTC date-alignment runner unchanged; no Events assertion or fixture source edit.'})

    from scripts.institution_v2i_baseline import capture_state
    from scripts.institution_v2l_baseline import capture_indexes
    state=capture_state();assert 'database_unavailable' not in state
    state['global_KG_metadata']={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in (ROOT/'knowledge_graph/data').glob('*') if p.is_file()}
    norm=lambda value:json.loads(json.dumps(value,default=str))
    same={k:norm(v)==base['state'][k] for k,v in state.items()}
    indexes=capture_indexes();index_same=norm(indexes)==base['mongo_indexes']
    edits=[n for n,h in base['source_sha256'].items() if not (ROOT/n).is_file() or sha(ROOT/n)!=h]
    frozen_edits=[n for n,h in base['frozen_reports_sha256'].items() if not (ROOT/n).is_file() or sha(ROOT/n)!=h]
    manifest_before=ROOT/'.scratch/institution-v2o2/before/reports/assistant_backend_baseline/hashes.json'
    manifest_unchanged=(ROOT/'reports/assistant_backend_baseline/hashes.json').read_bytes()==manifest_before.read_bytes()
    candidate_changes=[n for n,h in base['source_sha256'].items() if (ROOT/'.scratch/institution-v2o2/candidate/LibraryLLM'/n).is_file() and sha(ROOT/'.scratch/institution-v2o2/candidate/LibraryLLM'/n)!=h]
    preservation={'status':'PASS' if all(same.values()) and index_same and not edits and not frozen_edits and manifest_unchanged else 'FAIL',
        'captured_at':datetime.now(timezone.utc).isoformat(),'state_components_equal':same,'after_state':state,
        'mongo_index_contracts_equal':index_same,'institution_index_collections':len(indexes),'starting_source_files':len(base['source_sha256']),
        'existing_source_edits':edits,'prior_frozen_reports':len(base['frozen_reports_sha256']),'prior_report_edits':frozen_edits,
        'original_RAG_manifest_unchanged':manifest_unchanged,'actual_protected_guard_or_source_changed':False,
        'candidate_baseline_source_differences':candidate_changes,
        'I_status_store_sha256':sha(ROOT/'backend/services/library_intelligence_store.py'),'native_protocol':base['native_contract'],
        'production_changes':{'global_HNSW_rebuild':False,'global_KG_rebuild':False,'Mongo_authorization_cutover':False,'credential_ACL_service_firewall_changes':False,'telemetry_activation':False,'commit':False,'deploy':False},
        'environment_classification':'UNKNOWN; no newly inferred ownership, live authentication or external exposure approval.'}
    put('preservation',preservation)

    transport='\n'.join(f"| `{n}` | `{h}` |" for n,h in approval['full_transport_modules'].items())
    md('j_guard_review',f'''# Part 2O.2 J guard review

The original O.1 proposals were located, SHA256-verified against the user's two supplied digests, and left unchanged. Neither was applied to the actual tree. The direction is retained, with the two material gaps corrected: selected export-line protection is replaced by complete transport/dependency module fingerprints; identifier-name heuristics are replaced by a complete executable AST source boundary.

The original J assertion still runs and fails on the actual accepted O page. The proposed test keeps all three original backend exact hashes and the existing L native protocol protection. Before importing anything new, it verifies the Python helper, analyzer and reviewed boundary manifest fingerprints. No whole-page byte hash is introduced. Passive JSX text, layout wrappers and fixed presentation attributes may evolve; all executable expressions, callbacks, branches, declarations, imports, call structure and binding names remain reviewed/pinned.

Candidate actual full J suite: {final_j['passed']} passed / {final_j['failed']} failed. Candidate current O presentation passes; copy/layout/formatting variations pass; {mutation_result['J_negative']} unauthorized source mutations are rejected by executing the complete proposed assertion body. Main-tree J failure is still a release gate pending separate approval.

Backend authorization remains authoritative. Candidate 2B/G/L suites verify current membership, Admin build rights, General User/Librarian/Platform-only denial, foreign jobs/generations/graphs, tenant identity, private isolation, publication acknowledgement, fencing and last-good retention. Actual frontend tests cover revoked role/session clearing and A-to-B stale response exclusion. O.1 actual Chromium with real JWT/membership is preserved, not re-run in O.2.
''')
    md('j_transport_contract',f'''# Complete reviewed transport contract

All bytes of the following modules are pinned, including function bodies, imports, declarations, state, retry policy and module-level executable code:

| Module | SHA256 |
|---|---|
{transport}

libraryIntelligence calls institutionApi, which imports request/ApiError from api.ts. api.ts has no further static imports. Pinning all three modules closes that reviewed transport dependency chain, instead of protecting only one export line while permitting body/module changes. This intentionally requires explicit review for future changes to the shared transport modules; it does not freeze the UI page. Their original current bytes are unchanged in O.2.

The reviewed implementation preserves exact tenant GET/POST paths, abort signals, no-store requests, session matching before/after requests, per-session/per-tenant ordering, current-access revalidation on denial and bounded read retries. Build commands are not automatically retried. No frontend operator infrastructure endpoint or Mongo credential is introduced. Canonical UUID validity/current membership remain checked by backend authority.

Tests mutate actual helper bodies, multiline bodies, institutionApi dependency calls and generic API prefix; each fails the real proposed guard. A scope change in route parameters, request UUID, selected context or build helper similarly fails. The compiler and installed React/router/stores are trusted dependencies beyond this transport source chain; package/config/store preservation and full behavior checks are separately required.
''')
    md('j_ast_security',f'''# Executable AST boundary and bypass review

The previous name-matching denylist was insufficient for indirect references and computed access. O.2 does not attempt to recognize every possible spelling of network code. TypeScript parses the entire page, then every top-level statement's complete executable AST is projected and fingerprinted against a pinned reviewed manifest. Positions and spacing are omitted; kinds, identifiers, literal values, operators, declarations, bodies, binding patterns, imports/exports, computed access, callbacks and call arguments are retained. Unknown/new/deleted statements fail. Parse errors fail closed.

Only passive JSX text and permitted passive wrappers, plus fixed string-valued presentation attributes, are excluded from executable fingerprints. Expressions inside JSX, event handlers, component identities/props, spread props and conditional expressions remain protected. New network-capable HTML tags (iframe/script/img/form etc.) are rejected; they are not treated as passive wrappers. Compiler pragmas are rejected. The raw comment-marker envelope is pinned because compiler/bundler annotations can change behavior despite AST trivia removal. The current page has no comment markers; future comment/directive introduction needs review. Ordinary whitespace changes pass.

Direct/computed/escaped/generated fetch, window/globalThis references, destructured aliases, imported aliases/namespaces, dynamic import, CommonJS, re-exports, foreign transport modules, indirect status/build calls, alternate library context, raw credential reads, worker fences and shell/process additions all change the protected executable structure or transport bytes. They are rejected through complete proposed assertions, not text-appearance tests. {mutation_result['J_positive']} positive presentation variants and {mutation_result['J_negative']} negative mutations passed.

Limits: this is a reviewed source boundary with a finite mutation corpus, not a general JavaScript sandbox or proof of every browser/build/vendor behavior. Trusted TypeScript/build tools, React/router/stores, CSS and components remain outside this specific executable boundary. Passive prose can still contain manually pasted information and requires ordinary source review; this contract is not secret classification/DLP. Accessibility and semantic quality of future presentation changes require existing frontend/browser checks. Backend current membership and scope checks remain decisive, even if a client is malicious. No protection depends solely on identifier blacklist matches.
''')
    md('rag_source_review',f'''# Exact protected RAG delta and exception review

Original qa.py SHA: `0e78a7c780f691b14c8e3a3337f62054e4c117f0c2df7828099d80da90a793c6`. Reviewed current raw SHA: `4a1141649a4ce9b4bce6413627c27557f5817bb8718a4e842a4d12021bd89de3`. O.1 recovered the exact original bytes by reversing only the committed grounding hunks; that artifact and both complete diff reports remain frozen. Current raw bytes are unchanged. LF-normalized current source equals the committed HEAD blob (`d0738be6e73ff19b14e82bf386a02e0d2662fa80ead9c327fca852322df4db3e`); mixed checkout line endings are part of the strict reviewed byte version. That third LF-only representation is deliberately rejected, not normalized/accepted.

Complete source delta: import valid_work_id and document_grounding helpers; distinguish document IDs from catalogue work IDs; filter document evidence using select_definition_evidence; assign document-specific definition category; omit document citations after NOT_SUPPORTED. The rest projects exactly to the frozen original, including original line endings. No protected implementation, Qwen/model, ranking or Assistant routing changed in O.2.

valid_work_id is strict full-match OL[0-9]+W and grants no ownership. Actual private-document access uses PrivateDocuments.owned: current owner, current session, ACTIVE state, expiry/revocation, then selected lock-scoped runtime. That authorization precedes opening index/chunk files. select_definition_evidence only chooses candidates already in the authorized selected document, requires nonempty identified chunks and substantive definitions, and bounds explicit definition evidence to the existing top-three validation context. If there is no definition, it preserves same-document evidence and the original validator path; it never opens another source or index.

definition_category identifies evidence-sufficiency validation; it does not set SUPPORTED. The unchanged LLM validator uses its pre-existing informational prompt, which evaluates relevance/sufficiency rather than strict claim entailment. Real fast-filter tests verify definitions still reach that validator, support/non-support verdicts propagate, foreign passages do not enter generation and unsupported document citations are empty. No-evidence results call neither validator nor generation. Claim-bearing questions do not receive the definition category. Catalogue behavior and existing partial-support second-pass retrieval/ownership boundaries remain unchanged; no new source expansion is introduced by this delta.

Focused production validation: {rag['totals']['passed']} passed / {rag['totals']['failed']} failed / {rag['totals']['skipped']} skipped including full private asset security and lexical checks. Grounding group alone has 273 passing checks, including all existing urgent-document read-only cases. These are controlled model/validator tests and exact source review, not proof of all live generated answers. Original frozen LLM/retriever/reranker/document_service hashes remain exact. Semantic evidence supports presenting this narrow exception for review; it is not historical authorization or automatic approval.

Candidate guard accepts only exact original or exact reviewed-current bytes, then reverses the reviewed delta and checks the original SHA. Eleven negative tests reject prompt/retrieval/citation/grounding/identity changes, whitespace, LF-only/third versions, original-manifest tampering, helper changes and another protected source change. Original manifest bytes are now also pinned. Immutable legacy manifest paths are resolved relative to the tested checkout so candidate guard tests cannot accidentally read the actual tree's qa.py. Existing api.py exclusion remains exactly the existing exclusion, with no new excluded file.

Decision: prepare the exact reviewed RAG test-contract exception, require separate approval, do not apply to the actual tree. The protected-source failure remains visible.
''')
    changed_assertions='''J: remove only the frontend page from the original four-file byte loop; preserve three backend hashes; add pins for three test-only boundary files, then execute full transport/executable authority checks; keep the L protocol comment/guard unchanged. RAG: pin unchanged original manifest, resolve its immutable paths within the tested checkout, pin one test helper before import, allow only qa.py's exact two-version projection, retain every other original protected-file assertion and existing api.py exclusion.'''
    md('approval_patches',f'''# Corrected approval package — NOT APPLIED TO ACTUAL TREE

J patch: `{approval['J']['path']}`

SHA256: `{approval['J']['sha256']}`

RAG patch: `{approval['RAG']['path']}`

SHA256: `{approval['RAG']['sha256']}`

Both exact patches pass git apply --check --ignore-space-change from D:\\SDC. Actual application occurred only under the independently initialized Git root .scratch/institution-v2o2/candidate, verified before application. No actual frozen test, protected source, original manifest or old O.1 proposal was edited. New patch files use LF bytes; no broad production source newline normalization exists.

Changed assertions: {changed_assertions}

Files affected after approval: tests/institution_v2j/test_diagnostics.py; tests/contracts/staff_boundary_v2o2.py, .cjs, .json; tests/test_assistant_backend.py; tests/contracts/rag_grounding_v2o2.py. No product file change. Complete before/after coverage is in j_guard_review.md, j_transport_contract.md, j_ast_security.md and rag_source_review.md.

Before: whole page bytes and three backend files fixed at J; RAG exact original hashes (api.py already excepted). Proposed after: three backend hashes/protocol unchanged; complete reviewed transport chain plus all executable page logic pinned while passive presentation evolves; RAG only original/reviewed exact bytes plus original projection and manifest pin. Positive product/authority/protocol suites and explicit negative mutants are separately recorded.

Candidate bounded backend: {ct['passed']} passed / {ct['failed']} failed / {ct['skipped']} skipped. Contract/grounding checks: {mutations['passed']} passed / {mutations['failed']} failed. Actual-tree backend: {totals['passed']} passed / {totals['failed']} failed / {totals['skipped']} skipped. The latter still includes both original contract failures. Unapplied candidate successes are not main-tree successes.

Unresolved approvals: user Part G explicitly says “Any frozen-test patch requires the user's separate approval before application.” Approval must name the exact J and/or RAG patch hashes above. RAG approval must accept the reviewed historical grounding-source exception, not arbitrary current bytes. This request's favorable direction is not that separate approval.

Expected bounded next action only after approval: apply approved patches, rerun exact frozen failures, all affected product/security/mutation suites and accepted full regression. Expected two historical contract failures then resolve; any other failure remains independently investigated, never suppressed. Do not infer universal security or a guaranteed full green result from finite candidate checks. No deployment/cutover/telemetry/global rebuild authorized.
''')
    qa={'PART_2O2_RESULT':'PARTIAL','J_GUARD_HARDENED':'YES','FULL_TRANSPORT_BODY_PROTECTED':'YES',
        'INDIRECT_ACCESS_MUTATIONS_REJECTED':'YES','TENANT_SCOPE_PROTECTED':'YES','RAG_EXACT_VERSION_GUARD':'PASS',
        'RAG_GROUNDING_SECURITY':rag['status'],'PART_2O_UX_PRESERVED':'YES','J_APPROVAL_REQUIRED':'YES','RAG_APPROVAL_REQUIRED':'YES',
        'CURRENT_TREE_BACKEND':f"{totals['passed']} passed / {totals['failed']} failed / {totals['skipped']} skipped",
        'CANDIDATE_BACKEND':f"{ct['passed']} passed / {ct['failed']} failed / {ct['skipped']} skipped",
        'FRONTEND_TESTS':f"{ft['pass']} passed / {ft['fail']} failed / {ft['skipped']} skipped",'PROTECTED_GUARDS_CHANGED_WITHOUT_APPROVAL':'NO',
        'GLOBAL_HNSW_REBUILT':'NO','GLOBAL_KG_REBUILT':'NO','PRODUCTION_AUTH_CHANGED':'NO','PRODUCTION_TELEMETRY_ENABLED':'NO'}
    qa_text='\n'.join(f'{k}: {v}' for k,v in qa.items())
    md('completion',f'''# LuminaR Part 2O.2 — Corrected approval package

A. FINAL RESULT: PARTIAL. Candidate hardening and review complete; separate protected-contract approvals still required. Neither patch is applied to the actual tree.

B. J GUARD REVIEW: Original O.1 patch identities verified and preserved. Export-line and identifier-scan gaps closed; original backend/protocol protections retained.

C. TRANSPORT: Full libraryIntelligence.ts, institutions.ts and api.ts bytes pinned, including implementation bodies and their reviewed transport dependency chain. No whole-page source hash added.

D. AST BYPASS: Complete executable AST sections pinned with all expressions, binding/call/control/import structure. Passive JSX presentation may evolve. Unsafe HTML/parse/compiler directives rejected; comment-marker envelope protects bundler semantics. This is a reviewed boundary, not a JavaScript sandbox.

E. MUTATIONS: {mutation_result['J_positive']} positive UI variants, {mutation_result['J_negative']} rejected J mutations, {mutation_result['RAG_exact_positive']} accepted exact RAG versions, {mutation_result['RAG_negative']} rejected RAG mutations and {mutation_result['grounding_behavior_checks']} grounding checks. Total {mutations['passed']} passed. Harness/startup/timeouts retained and resolved without changing assertion deadlines.

F. O UX: Actual frontend {ft['pass']} passed / {ft['fail']} failed / {ft['skipped']} skipped; stage/unknown progress, attempt/last-good/error/recovery, polling/deadline/visibility, library/token/role switching, responsive/accessibility behavior preserved. No actual frontend source edit. Production build {('PASS' if front[1]['exit']==0 else 'FAIL')}; lint exit {front[2]['exit']}, {len(lintlines(lint))} existing warnings, {len(new_lint)} new warning lines. Prior Chromium evidence remains; no fresh O.2 browser run claimed.

G. RAG DELTA: Complete exact original-byte reverse projection, specific committed grounding imports/selection/category/unsupported citations, original ownership/validator path reviewed. No implementation/model/ranking/router edit.

H. RAG VALIDATION: {rag['totals']['passed']} focused production/asset/lexical checks passed, zero failed/skipped; grounding group alone 273. Real fast filter and ownership/selected-runtime paths, controlled model responses. No live semantic perfection claim.

I. RAG DECISION: Narrow candidate exception justified for explicit review only. Two exact versions, original projection, unchanged pinned manifest, other protected files exact, no third version accepted.

J. PATCHES: J SHA256 `{approval['J']['sha256']}`; RAG SHA256 `{approval['RAG']['sha256']}`. Exact diffs and assertion explanations in approval_patches.md; both apply-check pass. No actual application.

K. CANDIDATE REGRESSION: {ct['passed']} passed / {ct['failed']} failed / {ct['skipped']} skipped across bounded complete J/Assistant/tenant-authority/native Search-KG/native protocol suites, plus {mutations['passed']} contract/grounding tests. Owned Mongo replaced unavailable candidate import dependency; shared wall-clock stall caused later fixture/probe timeouts, followed by unchanged passing confirmation. All original failures/logs retained.

L. ACTUAL TREE: {totals['passed']} passed / {totals['failed']} failed / {totals['skipped']} skipped across {len(backend)} independent accepted groups through O.2. Both known frozen-contract failures remain; {len(unexpected)} unexpected failures. Candidate outcomes are not merged into these totals.

M. EXACT FILES: No pre-existing source edited. Added scripts/institution_v2o2*.py, tests/institution_v2o2 tests/templates, reports/institution_v2o2* and owned isolated candidate/proposal fixtures. Exact file/hash inventory in changed_files.json. No original O.1 artifact or accepted user work overwritten.

N. PRESERVATION: {preservation['status']}. TEST {state['TEST']['current_eligible_books']} eligible / {state['TEST']['holdings']} holdings / {state['TEST']['assets']} assets; global estimated {state['global_book_count']:,}; {len(indexes)} index collection contracts equal. All measured tenant records/pointers/jobs/generations/artifacts, private logical state/files and global HNSW/KG metadata equal. I/J/L/N/O code unchanged; {len(base['frozen_reports_sha256'])} prior reports unchanged. No production auth/telemetry/rebuild/deployment.

O. REMAINING APPROVALS: Separate explicit approval for the exact revised J patch and exact reviewed RAG exception. Your Part G requires it; this phase does not authorize applying frozen-test changes.

P. RECOMMENDATION: Review both exact patches and their limits. After separate approval, apply only approved diffs and validate frozen/affected/full suites. Stop O.2 here; no next infrastructure phase or production operation.

FINAL QA:

J hardening/full transport/indirect mutation and RAG exact-version results refer to the isolated candidate. These proposals remain unapplied to the actual tree. Candidate backend counts cover the bounded suites specified above.

```text
{qa_text}
```
''')
    paths=set(ROOT.glob('scripts/institution_v2o2*.py'))|set((ROOT/'tests/institution_v2o2').rglob('*'))|set(R.glob(PREFIX+'*'))
    paths.update(p for p in (ROOT/'.scratch/institution-v2o2/proposed').rglob('*') if p.is_file())
    entries=[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(paths,key=str) if p.is_file() and '__pycache__' not in str(p) and p.name!=PREFIX+'changed_files.json']
    put('changed_files',{'branch':base['branch'],'HEAD':base['head'],'existing_source_edits':edits,'new_O2_files':entries,
        'candidate_checkout_manifest':PREFIX+'candidate_setup.json','candidate_product_source_differences':candidate_changes,
        'inventory_self_hash_excluded':True,'baseline_before_copies':'.scratch/institution-v2o2/before (exact source evidence only)',
        'git_status_after':subprocess.check_output(['git','status','--porcelain=v1','-uall'],cwd=ROOT,text=True).splitlines(),
        'actual_guard_or_protected_implementation_edits':False,'commit_or_deploy':False})
    assert preservation['status']=='PASS' and not unexpected and rag['status']=='PASS' and not any(r['exit'] for r in front)
    print(json.dumps({'result':'PARTIAL','actual':totals,'candidate':ct,'mutation_and_grounding':mutations['passed'],'frontend':ft,'preservation':preservation['status']}))


if __name__=='__main__':main()
