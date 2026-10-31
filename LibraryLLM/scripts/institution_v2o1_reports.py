"""Close O.1 evidence without applying protected-contract proposals."""
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
R = ROOT / 'reports'
P = 'institution_v2o1_'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((R / (P + name + '.json')).read_text(encoding='utf-8-sig'))


def write(name, data):
    (R / (P + name + '.json')).write_text(json.dumps(data, indent=2, default=str) + '\n', encoding='utf8')


def md(name, text):
    (R / (P + name + '.md')).write_text(text.strip() + '\n', encoding='utf8')


def xml_summary(path):
    cases = list(ET.parse(path).iter('testcase'))
    failures = [{'test': c.get('classname', '') + '::' + c.get('name', ''),
                 'kind': n.tag, 'message': n.get('message', '')}
                for c in cases for n in c if n.tag in {'failure', 'error'}]
    skipped = sum(any(n.tag == 'skipped' for n in c) for c in cases)
    return {'passed': len(cases) - len(failures) - skipped, 'failed': len(failures),
            'skipped': skipped, 'failures': failures, 'xml': path.name}


def main():
    baseline = read('baseline')
    source = read('source_review')
    raw_backend = read('final_backend')
    backend = [dict(row) for row in raw_backend]
    assert backend[-1]['group'] == 'events', 'Full independent backend run has not finished'
    assert {r['group'] for r in backend} >= {'institution_v2o', 'institution_v2o1', 'institution_v2n'}
    for row in backend:
        assert 'tests' in row, row
    frozen_failures = {
        'tests.test_assistant_backend::test_protected_rag_files_match_original_hashes',
        'tests.institution_v2j.test_diagnostics::test_existing_staff_status_unchanged',
    }
    failures = []
    for row in backend:
        s = xml_summary(R / f'{P}final_{row["group"]}.xml')
        assert s['failed'] == row['failed']
        failures.extend(s['failures'])
    initial_failures = list(failures)
    # Keep the complete first-run evidence. One isolated auth fixture had a
    # redacted qualification failure and then passed its whole unchanged group.
    confirmation = xml_summary(R / (P + 'o_confirmation.xml'))
    o_row = next(row for row in backend if row['group'] == 'institution_v2o')
    o_initial = xml_summary(R / (P + 'final_institution_v2o.xml'))
    auth_failure = 'tests.institution_v2o.test_authentication::test_application_runtime_permissions'
    if o_initial['failed']:
        assert {f['test'] for f in o_initial['failures']} == {auth_failure}, o_initial
        assert confirmation['passed'] == o_row['tests'] == 30 and confirmation['failed'] == 0
        o_row['initial_attempt'] = dict(o_row)
        o_row['initial_failures'] = o_initial['failures']
        o_row.update({key: confirmation[key] for key in ('passed', 'failed', 'skipped')})
        o_row['exit'] = 0
        o_row['confirmation_xml'] = confirmation['xml']
        o_row['confirmation_note'] = 'Whole unchanged group rerun in fresh isolated fixture. Initial qualification error retained; underlying driver cause unproven.'
        failures = [f for f in failures if f['test'] != auth_failure]
    new = [f for f in failures if f['test'] not in frozen_failures]
    totals = {key: sum(r[key] for r in backend) for key in ('passed', 'failed', 'skipped')}
    backend_result = {'status': 'FAIL' if any(r['exit'] for r in backend) else 'PASS',
        'inventory': 'Full accepted independent product inventory through O, plus O.1; every group retained. Separate processes preserve existing fixture isolation.',
        'groups': backend, 'totals': totals, 'failures': failures,
        'initial_run_totals': {key: sum(r[key] for r in raw_backend) for key in ('passed', 'failed', 'skipped')},
        'initial_run_failures': initial_failures,
        'nonreproducing_fixture_failure': {'test': auth_failure, 'confirmation': confirmation,
            'classification': 'Initial auth readiness qualification failed closed; no assertion/test/product changes. Entire 30-test group passed on immediate confirmation. Driver error redacted by existing security code; underlying cause unproven.'},
        'new_failures_relative_to_O1_start': new,
        'prior_O_checkpoint': {'passed': 2603, 'failed': 2, 'skipped': 20},
        'frozen_tests_suppressed': False,
        'events_clock_alignment': 'Existing runner sets Events NOW to current UTC, preserving all assertions; no fixture file edited.',
        'broader_RAG_inventory': 'Additional controlled RAG cases are separately reported in rag_behavior.json; not a duplicate addition to full-suite counts.'}
    write('backend_tests', backend_result)

    frontend = read('final_frontend')
    text = (R / (P + 'final_frontend.log')).read_text(encoding='utf8')
    front_totals = {name: sum(map(int, re.findall(r'^. ' + name + r' (\d+)\s*$', text, re.M)))
                    for name in ('tests', 'pass', 'fail', 'skipped')}
    assert front_totals['tests'] == 959, front_totals
    lint = (R / (P + 'final_lint.log')).read_text()
    old_lint = (R / 'institution_v2o_final_lint.log').read_text()
    warnings = lambda value: sorted(line for line in value.splitlines() if ': warning ' in line)
    frontend_result = {'status': 'PASS' if not any(r['exit'] for r in frontend) else 'FAIL',
        'totals': front_totals, 'commands': frontend, 'production_build': 'PASS' if frontend[1]['exit'] == 0 else 'FAIL',
        'lint_exit': frontend[2]['exit'], 'lint_warnings': len(warnings(lint)),
        'new_lint_warning_lines_relative_to_O': sorted(set(warnings(lint)) - set(warnings(old_lint))),
        'note': 'No frontend source, package, CSS or existing test changed in O.1. Existing O test unused-import warnings remain visible.'}
    write('frontend_tests', frontend_result)

    review = xml_summary(R / (P + 'review_tests.xml'))
    backend_result['post_run_review_confirmation'] = review
    backend_result['post_run_review_note'] = 'Review-only tests refined after full sweep to check frozen before-copy evidence, avoiding a new permanent whole-page freeze. Current 19 checks pass; full initial group remains recorded.'
    write('backend_tests', backend_result)
    lexical = xml_summary(R / (P + 'lexical.xml'))
    assert lexical['failed'] == 0
    write('lexical_regression', {'status': 'PASS', 'focused': lexical,
        'full_search_group': next(r for r in backend if r['group'] == 'search'),
        'checks': ['Missing/corrupt/stale optional lexical provider falls back with HTTP 200',
                   'Public response omits diagnostics and lexical internals',
                   'Deleted catalogue entries excluded, current Mongo metadata hydrated',
                   'Unauthorized request still HTTP 401',
                   'Find-only optional facets return empty facets',
                   'Actual Mongo OperationFailure propagates, never disguised as optional-provider absence'],
        'unchanged_ranking_sources': True, 'global_search_rebuilt': False,
        'authenticated_fail_closed_evidence': ['final_institution_v2n.xml', 'final_institution_v2o.xml']})

    rag = read('rag_behavior')
    rag['status'] = 'PASS' if all(g['exit'] == 0 for g in rag['groups']) and review['failed'] == 0 else 'FAIL'
    rag['totals'] = {k: sum(g[k] for g in rag['groups']) for k in ('passed', 'failed', 'skipped')}
    rag['source_hash_contract'] = 'REQUIRES_APPROVAL; behavioral PASS does not approve protected source drift'
    rag['coverage'] = {
        'ownership_sessions_personal_isolation': 'test_private_document_cache: active owner/session, cross-account bundles, logout/expiry/error invalidation; real HTTP ask adapter private/global/book/failure boundaries',
        'selected_document_only': 'test_urgent_document_rag: current asset only; cross-owner/document denied; definition selection excludes foreign candidates',
        'grounding_citations_unsupported': 'Supported and unsupported definitions, source pages/chunk identity, catalogue validator contract and document citation tests',
        'prompt_models': 'test_document_rag_latency verifies original extraction/decoding settings, classifier fallback, bounded scoped caches and no second Qwen instance',
        'library_asset_isolation': 'Full institution v2f/v2g plus separate controlled asset recovery group; explicit owner consent, library evidence and no personal history migration',
        'errors_missing_documents': 'Private cache/API missing or unowned documents return denial; ask failures clear selected runtime; no unauthorized context expansion',
    }
    rag['newly_exposed_preexisting_issue'] = {
        'test': 'tests.test_rag_query_types::test_overview_rule_never_accepts_added_premises[What are the major themes of this book?]',
        'initial': {'passed': 241, 'failed': 1, 'log': P + 'rag_initial_theme_bypass.log', 'xml': P + 'rag_initial_theme_bypass.xml'},
        'cause': 'Recognized themes question plus three substantial generic passages bypassed the existing evidence validator.',
        'repair': 'Unprotected rag/query_types.py refuses the themes overview shortcut; existing validator decides support. Grammar stays factual.',
        'authorization': 'Part H Case 4 permits a behavior fix outside protected sources.',
        'additional_actual_qa_checks': 'Four O.1 tests; three grammar forms and actual LuminaRAG.ask with controlled generation/validator fixture',
        'final': 'PASS', 'new_O1_regression': False,
    }
    rag['limits'] = 'Controlled retrieval/model fixtures establish code-path and isolation contracts; no new live Qwen quality benchmark. Three persistent personal-document-dependent research cases were not selected for this extra targeted run; no accepted product group or frozen test was removed.'
    write('rag_behavior', rag)

    from scripts.institution_v2i_baseline import capture_state
    from scripts.institution_v2l_baseline import capture_indexes
    state = capture_state()
    assert 'database_unavailable' not in state, state
    state['global_KG_metadata'] = {p.relative_to(ROOT).as_posix(): {'bytes': p.stat().st_size, 'mtime_ns': p.stat().st_mtime_ns}
                                   for p in (ROOT / 'knowledge_graph/data').glob('*') if p.is_file()}
    indexes = capture_indexes()
    # Frozen JSON uses default=str for BSON/datetimes. Compare the same representation.
    normalize = lambda x: json.loads(json.dumps(x, default=str))
    comparisons = {key: normalize(value) == baseline['state'][key] for key, value in state.items()}
    changed = [{'path': name, 'before': old, 'after': sha(ROOT / name) if (ROOT / name).is_file() else None}
               for name, old in baseline['source_sha256'].items()
               if not (ROOT / name).is_file() or sha(ROOT / name) != old]
    old_report_changes = [name for name, old in baseline['frozen_reports_sha256'].items()
                          if not (ROOT / name).is_file() or sha(ROOT / name) != old]
    protected_changes = [row for row in changed if row['path'] != 'rag/query_types.py']
    write('preservation', {'status': 'PASS' if all(comparisons.values()) and not protected_changes and not old_report_changes and normalize(indexes) == baseline['mongo_indexes'] else 'FAIL',
        'baseline': P + 'baseline.json', 'captured_at': datetime.now(timezone.utc).isoformat(),
        'state_components_equal': comparisons, 'after_state': state,
        'mongo_index_contracts_equal': normalize(indexes) == baseline['mongo_indexes'], 'mongo_index_collections': len(indexes),
        'baseline_source_files': len(baseline['source_sha256']), 'existing_sources_changed': changed,
        'unexpected_source_changes': protected_changes,
        'frozen_prior_reports': len(baseline['frozen_reports_sha256']), 'prior_report_changes': old_report_changes,
        'I_status_store_sha256': sha(ROOT / 'backend/services/library_intelligence_store.py'),
        'native_protocol': baseline['native_contract'],
        'protected_hash_manifest_sha256_unchanged': sha(ROOT / 'reports/assistant_backend_baseline/hashes.json') == baseline['source_sha256']['reports/assistant_backend_baseline/hashes.json'] if 'reports/assistant_backend_baseline/hashes.json' in baseline['source_sha256'] else (ROOT / 'reports/assistant_backend_baseline/hashes.json').read_bytes() == (ROOT / '.scratch/institution-v2o1/before/reports/assistant_backend_baseline/hashes.json').read_bytes(),
        'no_production_actions': {'global_hnsw_rebuild': False, 'global_kg_rebuild': False, 'mongo_auth_cutover': False,
            'credential_acl_service_firewall_change': False, 'telemetry_activation': False, 'commit': False, 'deploy': False},
        'environment_classification': 'UNKNOWN; continue is not ownership or cutover approval. No live authentication or exposure reclassification claimed.'})
    browser = read('browser')
    security_groups = [r for r in backend if r['group'] in {'security', 'institution_v2b', 'institution_v2f', 'institution_v2g', 'institution_v2i', 'institution_v2j', 'institution_v2l', 'institution_v2n', 'institution_v2o', 'institution_v2o1'}]
    write('j_security_regression', {'functional_status': 'PASS' if not new and browser['status'] == 'PASS' and review['failed'] == 0 else 'FAIL',
        'frozen_J_contract_status': 'REQUIRES_APPROVAL', 'frozen_J_guard_retained_and_failing': True,
        'groups': security_groups, 'review_and_mutation_tests': review,
        'coverage': {
            'operator_only_diagnostics': 'J tests: explicit read role, platform-only denial, outside private library denial, read-only Mongo enforcement and redaction',
            'canonical_tenant_membership': 'B/G authenticated API tests and Chromium actual JWT/membership revocation/library-switch checks',
            'role_matrix': 'Admin manual confirmation/build; Librarian status read and build denied; General User and Platform-only denied',
            'fencing_and_last_good': 'G/L tests and native fixture browser builds: serial owner fences, publication acknowledgement, failure/recovery and retained last-good',
            'mongo_fail_closed': 'N/O isolated real authorization on separate Mongo port: absent/invalid/revoked credentials, wrong DB/authSource, anonymous denial, no anonymous retry',
            'no_secret_worker_fence_output': 'J redaction and staff response schema tests plus source review; React has no operator infrastructure request',
            'no_automatic_commands': 'J no mutation/recovery/global-control test, G job dedupe/fencing, frontend cancel/confirmation and browser no-auto-build',
            'frontend_boundary_candidate': 'Six mutation checks reject operator fetch, foreign scope, extra command, shell import, raw fence and endpoint changes; candidate only, frozen guard not changed'},
        'limits': 'AST allowlist is an additional review guard, not a proof against all possible JavaScript. Backend authority, helper fingerprints, actual behavior tests and review remain required.'})

    approval = read('approval_manifest')
    assert all(not approval[k]['applied'] for k in ('J', 'RAG'))
    j = source['J']
    md('j_hash_analysis', f'''# Part 2J source-contract review

Status: REQUIRES_APPROVAL. `tests.institution_v2j.test_diagnostics::test_existing_staff_status_unchanged` still fails, unchanged. Its page assertion compares raw SHA256 with the J baseline.

Expected: `{j['expected']}`. Actual accepted O page: `{j['actual']}`.

The original page was recovered from the preserved pre-O copy and matches the J hash exactly. `institution_v2o1_j_page_review.diff` contains the complete J-to-O page diff. J's completion/changed-files evidence describes an operator-only read diagnostics phase that intentionally left existing staff/runtime paths untouched. Whole-file identity proved that phase's non-interference. It also pinned security-sensitive code, but cannot express the later authorized UX evolution. No documentation found establishes permanent byte immutability as a product requirement. This purpose assessment is an inference from J's explicit scope and code; it does not grant approval to alter its frozen test.

Complete intentional differences (all six diff hunks):

| Difference | Classification and review |
|---|---|
| Import `stageProgress`; remove unsupported CANCELLED label; handle missing/invalid dates | AUTHORIZED PART 2O UX CHANGE. No new backend job state or operation. |
| Remount session on current role as well as tenant/token | AUTHORIZED PART 2O UX CHANGE + SECURITY-SENSITIVE CHANGE. Revocation clears mounted status; authority still rechecked server-side. |
| Guard every load by staff role/visibility; add 10-second deadline, abort sequencing and visibility cleanup; retain 3-second active polling | AUTHORIZED PART 2O UX CHANGE + SECURITY-SENSITIVE CHANGE. Bounds requests and prevents stale/session/library responses. |
| Use validated stage counters, indeterminate unknown totals and explicit stage/publication distinction | AUTHORIZED PART 2O UX CHANGE. No invented overall completion or worker health. |
| Condition last-good claim on artifact verification; show latest attempt timestamps and unavailable worker activity | AUTHORIZED PART 2O UX CHANGE. Retained pointer alone is not called validated. |
| Show durable heartbeat and accessible progress explanation | AUTHORIZED PART 2O UX CHANGE. Durable records are distinguished from native process liveness. |

The existing explicit Admin `build()` action, confirmation/abort handling, tenant transport and backend routes are unchanged. The three existing backend hashes remain exact J matches. No unrelated or suspicious/unexplained page hunk was found. No page or transport edit was made in O.1. The separate O progress helper is also byte-identical to the O.1 starting checkpoint.

Current enforcement remains the original whole-page assertion plus all backend/frontend/browser security checks. Additional passing tests cannot make a raw mismatching SHA equal. Restoring the J page would discard accepted O functionality and is outside this task's preservation requirement. The exact candidate patch is offered for explicit approval only.
''')
    md('j_contract_options', '''# J contract alternatives

| Option | Decision |
|---|---|
| A: retain exact whole-page identity | Strong detection of every byte, including harmless UX. Current guard retained pending approval; incompatible with accepted O source. Reverting O is rejected. |
| B: behavioral security invariants | Expresses role/membership, canonical scope, no automatic commands, races and isolation. Alone does not detect every source-level infrastructure addition. |
| C: narrow reviewed fingerprints | Pins tenant GET/POST transport and active-state interpretation; retains original exact backend hashes. Alone does not prove UI session or confirmation behavior. |
| D: B + C, with reviewed AST boundary | Recommended smallest appropriate combined contract. Retain three backend SHA guards; pin test helpers, protect reviewed transport, reject unreviewed page capabilities, run existing behavior suites and actual browser checks. |

Before: original backend and entire frontend page bytes must match J; all operational security tests continue separately. After proposed approval: backend bytes still exact, unchanged native protocol guard retained, helper code pinned before import, exact canonical tenant transport preserved, page imports and command locations checked with TypeScript AST. Current role/membership authority, Admin build confirmation/deduplication, Librarian read-only, General User/Platform-only denial, cross-library/session race protection, no auto rebuild/shell/operator API/secret output remain behavioral requirements.

The three transport export lines are identical in the original accepted J/O checkpoint and current O helper, fingerprint `2ea2e6e79c2d4767438a0d40442fe493838c81df20b13b6725592ee6db4dc091`. Candidate tests accept O and reject six concrete unauthorized mutations. This is a narrower contract, deliberately allowing reviewed presentation evolution. It is not a JavaScript sandbox or a substitute for reviewing future transport/store changes.

No proposed helper is installed under tests/contracts and no frozen assertion changed. `institution_v2o1_j_approval.patch` contains the complete exact change. Applying it requires the explicit approval required by Part E. Until then the original failure remains a release gate.
''')

    rag_rows = '\n'.join(f"| `{Path(row['path']).relative_to(ROOT).as_posix()}` | `{row['expected']}` | `{row['actual']}` | {'yes' if row['asserted_by_frozen_test'] else 'no: existing explicit exclusion'} |" for row in source['RAG'])
    history = '\n'.join('- `' + line + '`' for line in source['qa_history'])
    md('rag_hash_analysis', f'''# Protected RAG source review

Status: REQUIRES_APPROVAL. The unchanged assistant guard still fails for `rag/qa.py`. This predates O and O.1. Original hash manifest and protected sources remain byte-identical to the O.1 starting checkpoint. Passing behavior does not authorize a protected source exception.

| Path | Expected SHA256 | Actual SHA256 | Asserted by existing guard |
|---|---|---|---|
{rag_rows}

`rag/api.py` is already explicitly excluded by the existing test for the previously accepted secure transport change. O.1 adds no exclusion. The remaining four protected files match; only qa.py fails among asserted paths.

Relevant Git history:

{history}

Current raw qa.py has 39,923 bytes. Its LF-normalized content exactly matches the 38,793-byte HEAD Git blob; parsed ASTs are equal. The mixed line endings account for raw working-tree/Git differences, but do not by themselves explain the legacy hash. There is no current uncommitted semantic drift in qa.py.

The complete committed delta is in `institution_v2o1_qa_committed.diff`; `institution_v2o1_qa_worktree.diff` is empty. Added imports are valid_work_id and document_grounding helpers. The ask path identifies selected private document IDs distinct from work IDs, narrows document evidence with select_definition_evidence, uses document-specific definition category, and omits document citations after NOT_SUPPORTED. Catalogue retrieval/generation/prompt construction remain on the original paths. Exact reversal of these hunks, including the original CRLF on the citation loop, reconstructs the original frozen SHA `0E78A7C780F691B14C8E3A3337F62054E4C117F0C2DF7828099D80DA90A793C6`. The recovered bytes are a review artifact, never copied over protected code.

This establishes the specific committed source delta and its document-grounding intent. Commit message and matching behavioral fixtures do not prove human authorization of the protected-source change. The historical approval gap therefore remains open (Part H Case 2 candidate, approval unproven). No model, architecture, prompt, protected retriever, reranker or LLM source was changed in O.1.

Controlled validation covers source pages/chunk identity, unsupported evidence, exact selected-document ownership, cross-user and tenant isolation, missing-document/error cleanup, personal cache encryption/session isolation, original classifier/prompt contracts and assistant integration. See rag_behavior.json and independent full assistant/private-knowledge/institution groups. The broader inventory exposed a pre-existing themes shortcut bug in unprotected query_types.py; the narrow repair restores the existing validator without changing protected qa.py.

Candidate approval uses an exact reviewed-current-byte pin plus exact reverse projection to the original frozen bytes. Original hashes.json and all other protected assertions remain unchanged. Unknown byte changes, including whitespace, are rejected. This remains an approval-required contract exception; it is not resolution until explicitly authorized and applied/tested.
''')
    md('proposed_approval_patches', f'''# Exact changes awaiting explicit approval

Neither patch has been applied. User Part E says “DO NOT apply a changed expected hash or weaken/remove the frozen guard without explicit approval”; Part H does not treat investigation or passing behavior as protected-source authorization. No explicit approval was received.

1. `institution_v2o1_j_approval.patch` — SHA256 `{approval['J']['sha256']}`. Modifies only the J guard and adds two pinned test contract helpers. Keeps three exact backend hashes and the independent native protocol guard; replaces whole-page identity with reviewed transport fingerprint, AST restrictions and existing behavior validation. Original J expected hash remains preserved in its baseline report.
2. `institution_v2o1_rag_approval.patch` — SHA256 `{approval['RAG']['sha256']}`. Modifies only the assistant guard's qa.py payload check and adds one pinned test helper. Original manifest is untouched. The helper accepts exact original bytes or exact reviewed current bytes only, and proves the reviewed delta reverses to the original hash. No protected implementation or model edit.

Both exact patches pass `git apply --check --ignore-space-change` from D:\\SDC. The option accommodates Windows context line endings; it does not change application or test assertions. Helpers are staged only under .scratch/institution-v2o1/proposed for candidate tests. Review tests pass: {review['passed']} passed, {review['failed']} failed. They verify exact original recovery, frozen before-copy evidence, accepted O transport/AST, six frontend security mutations, five actual RAG source mutations and four themes-validator cases. The final preservation scan independently proves protected sources/guards were unchanged by O.1; that scan creates no new permanent whole-page freeze. No claim is made that the modified frozen tests ran in the real tree: they are deliberately unapplied.

Approval would authorize each specified test-contract exception, including the historical document-grounding delta for RAG. It would not authorize a new implementation change or future arbitrary hash update. Next bounded scope after approval: apply the approved patch(es), run their exact original failing tests and affected/full regressions, then report the remaining gate truthfully. Current exact failing assertions are retained in backend_tests.json and original XML/logs.
''')

    preservation = read('preservation')
    regression = {'result': 'PARTIAL', 'backend': totals, 'full_backend_status': backend_result['status'],
        'original_O1_failures': sorted(frozen_failures), 'current_failures': failures, 'new_backend_failures': len(new),
        'resolved_behavior_issue': 'Pre-existing themes evidence-validator bypass outside accepted full inventory, now covered by controlled RAG and O.1 tests',
        'protected_contracts': {'J': 'REQUIRES_APPROVAL', 'RAG': 'REQUIRES_APPROVAL'},
        'protected_hashes_rebased_without_approval': False, 'frozen_tests_suppressed': False,
        'part_O_frontend_preserved': not any(c['path'].startswith('frontend/') for c in changed),
        'lexical': 'PASS', 'RAG_behavior': rag['status'], 'review_tests': review,
        'frontend': front_totals, 'browser': browser['status'], 'production_build': frontend_result['production_build'],
        'lint_exit': frontend_result['lint_exit'], 'new_lint_warnings': len(frontend_result['new_lint_warning_lines_relative_to_O']),
        'preservation': preservation['status']}
    write('regression', regression)
    qa = {
        'PART_2O1_RESULT': 'PARTIAL', 'J_HASH_GUARD': 'REQUIRES_APPROVAL', 'RAG_HASH_DRIFT': 'REQUIRES_APPROVAL',
        'PROTECTED_HASHES_REBASED_WITHOUT_APPROVAL': 'NO', 'FROZEN_TESTS_SUPPRESSED': 'NO',
        'PART_2O_UX_PRESERVED': 'YES', 'LEXICAL_FALLBACK_PASS': 'YES', 'RAG_BEHAVIOR_PASS': 'YES',
        'FULL_BACKEND_REGRESSION': backend_result['status'], 'NEW_BACKEND_FAILURES': len(new),
        'FRONTEND_TESTS': f"{front_totals['pass']} passed / {front_totals['fail']} failed / {front_totals['skipped']} skipped",
        'BROWSER_VALIDATION': browser['status'], 'PRODUCTION_BUILD': frontend_result['production_build'],
        'GLOBAL_HNSW_REBUILT': 'NO', 'GLOBAL_KG_REBUILT': 'NO', 'PRODUCTION_AUTH_CHANGED': 'NO', 'PRODUCTION_TELEMETRY_ENABLED': 'NO'}
    qa_text = '\n'.join(f'{k}: {v}' for k, v in qa.items())
    md('completion', f'''# LuminaR Part 2O.1 — Frozen Contract Review & Regression Closure

A. FINAL RESULT: PARTIAL. Authorized investigation, behavior repair, regression and preservation work complete. Both protected-contract approvals remain unavailable.

B. EXECUTIVE SUMMARY: Exact evidence replaces conjecture. The J failure is an accepted O UX/whole-file immutability conflict. RAG qa.py drift is a specific historical committed grounding delta with exact original-byte recovery; its protected-source approval remains unproven. No frozen guard or protected source changed.

C. J ROOT CAUSE: Original whole-page SHA {j['expected']} differs from O {j['actual']}; original J page recovered exactly. See j_hash_analysis.md and complete diff.

D. ACCEPTED O CHANGES: Stage progress, unknown totals, generation/last-good/attempt details, truthful lifecycle, 3-second polling, 10-second deadline, hidden-tab and tenant/token/role protections, accessibility/responsive behavior preserved byte-for-byte.

E. PROPOSED J CONTRACT: D (behavioral invariants + exact backend/transport/helper fingerprints + TS AST boundary); original operator authorization and native job protocol checks retained.

F. J FIX STATUS: REQUIRES_APPROVAL. Complete patch prepared and apply-check validated; original failing guard still executes.

G. RAG ROOT CAUSE: Document-only grounding selection/category/citation changes committed before O. Current normalized source equals HEAD; exact reverse delta matches original frozen hash. Human authorization not proven.

H. RAG BEHAVIOR: {rag['totals']['passed']} controlled checks passed, zero failed; four additional themes grammar/actual QA validator checks passed. Generation/validation are controlled fixtures, not a new live model benchmark. Three persistent personal-document research cases are explicitly outside this extra targeted inventory.

I. RAG FIX STATUS: Protected hash REQUIRES_APPROVAL. Actual pre-existing themes evidence bypass fixed in unprotected rag/query_types.py under Part H Case 4. Original prompts/model/protected implementation retained.

J. APPROVAL PATCHES: Exact J and RAG patches with hashes, proposed helpers and mutation evidence are described in proposed_approval_patches.md. Neither applied; no manifest rebasing or frozen-test suppression.

K. LEXICAL: Focused {lexical['passed']} passed; full Search group passed; optional provider failures preserve public schema/fallback and real Mongo authorization errors propagate.

L. STAFF INTELLIGENCE: O page/helper/CSS/package and all existing tests unchanged; full frontend and real browser checks preserve role, context, lifecycle and progress behavior.

M. SECURITY: Actual JWT/membership denial, private isolation, read-only diagnostics, authenticated Mongo fail-closed, native fences/last-good and no automatic commands verified. J guard remains separately blocked by approval. See j_security_regression.json.

N. BROWSER: PASS, {len(browser['steps'])} checks, actual Chromium/ASGI/JWT/isolated real authenticated Mongo/manual native Search/KG builds, six viewport/keyboard checks and focused axe. Deterministic intermediate counter states are explicitly marked controlled durable states; no native timing claim for them. No page JavaScript or unexpected HTTP errors. Disposable fixture cleaned.

O. BACKEND: {totals['passed']} passed / {totals['failed']} failed / {totals['skipped']} skipped across {len(backend)} independent accepted product groups plus O.1 after an unchanged full O-group confirmation. First sweep: {backend_result['initial_run_totals']['passed']} passed / {backend_result['initial_run_totals']['failed']} failed / {backend_result['initial_run_totals']['skipped']} skipped. One auth qualification failure did not reproduce in all 30 tests on fresh fixture; root cause unproven and original evidence retained. Both known contract failures remain; {len(new)} current new failures relative to O.1 start. Full regression is FAIL, not PASS.

P. FRONTEND: {front_totals['pass']} passed / {front_totals['fail']} failed / {front_totals['skipped']} skipped. Production build PASS. Lint exit {frontend_result['lint_exit']}, {frontend_result['lint_warnings']} existing warnings, no new warning lines compared with O.

Q. GLOBAL PRESERVATION: {preservation['status']}. TEST {state['TEST']['current_eligible_books']} eligible books / {state['TEST']['holdings']} holdings / {state['TEST']['assets']} assets, global estimated {state['global_book_count']:,}; {len(indexes)} institution index contracts equal. All tenant documents/pointers/jobs/generations/artifacts, global HNSW/KG metadata, private artifacts and personal logical registries equal. I store fingerprint, J operator code, L protocol, N gate, Qwen/assistant/ranking/recommendation code preserved. {len(baseline['frozen_reports_sha256'])} prior reports unchanged.

R. EXACT FILES: Only pre-existing source edited is rag/query_types.py (five-line narrow validator gate). Added O.1 scripts, three test files, reports, review patches and disposable proposal/browser fixtures are inventoried with SHA256 in changed_files.json. None of the accepted uncommitted user work was overwritten; starting git status remains in baseline.json. No commit/deploy.

S. BLOCKERS: Explicit approval for the J guard contract and historical RAG source exception. Their failures remain visible and prevent overall PASS.

T. NEXT SCOPE: Review the two exact patches; only after explicit approval apply approved changes and rerun affected/full regressions. Stop O.1 here. No later phase, live Mongo auth change, telemetry activation or global rebuild.

FINAL QA:

```text
{qa_text}
```
''')
    # query_types was not in the selected before-copy list; baseline hash and
    # committed tracked source establish the exact small behavior delta instead.
    old = subprocess.check_output(['git', 'show', 'HEAD:LibraryLLM/rag/query_types.py'], cwd=ROOT).decode()
    current = (ROOT / 'rag/query_types.py').read_text()
    (R / (P + 'query_types_fix.diff')).write_text(''.join(difflib.unified_diff(old.splitlines(True), current.splitlines(True), fromfile='HEAD/rag/query_types.py', tofile='O1/rag/query_types.py')), encoding='utf8')
    paths = sorted({*ROOT.glob('scripts/institution_v2o1*.py'), *ROOT.glob('tests/institution_v2o1/*.py'), *R.glob(P + '*'),
                    *(p for p in (ROOT / '.scratch/institution-v2o1').rglob('*') if p.is_file() and '__pycache__' not in str(p))}, key=str)
    entries = [{'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p), 'bytes': p.stat().st_size,
                'kind': 'review_and_validation_artifact'} for p in paths if p.is_file() and p.name != P + 'changed_files.json']
    write('changed_files', {'base_branch': baseline['branch'], 'base_HEAD': baseline['head'],
        'preexisting_source_edits': changed, 'new_O1_files': entries,
        'self_hash_excluded': 'This inventory excludes its own SHA to avoid recursive hashing.',
        'temporary_scope': '.scratch/institution-v2o1 contains test-owned harnesses/screenshots/staged proposed helpers, never applied to protected targets.',
        'git_status_before': P + 'baseline.json',
        'git_status_after': subprocess.check_output(['git', 'status', '--porcelain=v1', '-uall'], cwd=ROOT, text=True).splitlines(),
        'preserved_existing_user_work': not protected_changes and not old_report_changes,
        'protected_guard_source_hashes_changed': False, 'commit_or_deploy': False})
    assert not new and all(comparisons.values()) and preservation['status'] == 'PASS'
    print(json.dumps({'result': 'PARTIAL', 'backend': totals, 'frontend': front_totals,
                      'review': review['passed'], 'RAG_controlled': rag['totals'], 'preservation': preservation['status']}))


if __name__ == '__main__':
    main()
