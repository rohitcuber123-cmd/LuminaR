"""Assemble Part 2Q.3 closure evidence without changing application state."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'


def read(name):
    return json.loads((REPORTS / f'institution_v2q3_{name}.json').read_text(encoding='utf8'))


def write(name, value):
    (REPORTS / f'institution_v2q3_{name}.json').write_text(json.dumps(value, indent=2), encoding='utf8')


def browser_report():
    observations = read('browser_observations')
    network = read('browser_network')
    events = [e for batch in network for e in batch.get('events', [])]
    failures = [e for e in events if e.get('status', 0) >= 400 or (e.get('error') and not e.get('canceled'))]
    console = read('browser_console')
    cases = [
        ('Global catalogue/chatbot', 'PASS', 'Global_catalogue_ForYou, Global_return, Global_digital_answer; real Qwen UNKNOWN response'),
        ('Global For You', 'PASS', 'Global_catalogue_ForYou; controlled Global candidate provider'),
        ('Private A catalogue', 'PASS', 'A_no_match, A_local_book_relogin'),
        ('Private A chatbot', 'PASS', 'A_digital_complete; real Qwen and authorized canonical PDF'),
        ('Private A For You', 'PARTIAL', 'A_ForYou and sequential API repeat pass; intermittent 503 retained'),
        ('Private B catalogue', 'PASS', 'B_catalogue, B_local_book'),
        ('Private B chatbot', 'PASS', 'B_digital_answer, B_physical_followup; real Qwen'),
        ('Private B For You', 'PARTIAL', 'B_ForYou, 84/84 B book links; intermittent 503 followed by 200 retained'),
        ('Physical availability', 'PASS', 'B_physical_followup: 2 available / 2 total'),
        ('Digital availability', 'PASS', 'A_digital_complete, B_digital_answer, B_PDF_open_complete, Global_digital_answer'),
        ('Local-only navigation', 'PASS', 'A_local_book_relogin, B_local_book use canonical local IDs'),
        ('Conversation follow-up', 'PASS', 'B PDF question followed by physical availability, same book'),
        ('Global -> A -> B -> Global', 'PASS', 'Global_catalogue_ForYou, A_ForYou, B_ForYou, Global_return'),
        ('Stale request cancellation', 'PASS', 'browser_cancellation.json, browser_cancel_events.json: held HTTP200, matching ERR_ABORTED, clean B conversation; controlled transport'),
        ('Unauthorized asset denial', 'PASS', 'outsider_denial: private library/resource not found'),
        ('Revoked membership', 'PASS', 'revoked_denial: removed member cannot open A resource'),
        ('No-match Search', 'PASS', 'A_no_match: no local matches, separate explicit Global discovery link'),
        ('Logout/relogin', 'PASS', 'Member -> outsider -> revoked -> member, verified current identity and access'),
        ('Mobile target390', 'PARTIAL', 'Requested390x844; actual inner487/client469/scroll469; no exact 390 claim'),
        ('Keyboard accessibility', 'PARTIAL', 'Tab reaches Skip to content; Enter focuses MAIN#main-content. Existing structural axe tests pass; no exhaustive keyboard audit'),
        ('Console/API errors', 'PARTIAL', 'Last console sample empty; network retains503, expected404 denials, two502 during owned lab restart; event buffer truncated in5batches'),
    ]
    data = {
        'result': 'PARTIAL', 'environment': 'Owned disposable DB and HTTP18005/Vite18017, stable Chromium session',
        'cases': [{'case': name, 'result': status, 'evidence': evidence} for name, status, evidence in cases],
        'actual_model': 'Qwen2.5-3B NF4 CUDA unchanged, genuine A/B/Global book questions',
        'controlled_parts': 'Synthetic books/assets; controlled Global candidate metadata; cancellation holds real completed explicit RECOMMEND response, without Qwen intent inference',
        'network_errors': failures, 'truncated_network_batches': sum(bool(x.get('truncated')) for x in network),
        'console_sample': console, 'observations': observations, 'cancellation': read('browser_cancellation'),
        'api_error_interpretation': '404 private context denials expected.502 events/notifications correspond to Vite ECONNREFUSED during owned lab reload.503 catalogue recommendations also occurred during ordinary read/switch concurrency; retry200, cause not fully attributed; no guard weakened.',
        'proof_image': 'reports/institution_v2q3_browser_B_digital.png',
        'cleanup': read('service_cleanup'), 'fixture_cleanup': read('fixture_cleanup'),
        'limits': 'Not a production-data or5M retrieval benchmark. Browser errors, bounded keyboard coverage and observed viewport prevent full PASS.',
    }
    write('browser_qa', data)
    return data


def closure_report():
    browser = browser_report()
    backend = read('backend_tests')
    frontend = read('frontend_tests')
    preservation = read('preservation')
    patch = read('patch_review')
    checkpoint = read('checkpoint')
    assert backend['source_stable'] and backend['group_count'] == 38
    assert backend['exit'] == 0 and backend['counts']['failed'] == 0
    assert frontend['counts']['failed'] == 0 and all(x['exit'] == 0 for x in frontend['checks'])
    current_sha = lambda p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
    assert all(current_sha(p) == h for p, h in backend['source_sha256'].items())
    assert current_sha('reports/institution_v2q3_changes.patch') == patch['patch_sha256']
    reverse = subprocess.run(['git', 'apply', '--reverse', '--check', 'reports/institution_v2q3_changes.patch'], cwd=ROOT, capture_output=True, text=True)
    assert reverse.returncode == 0, reverse.stderr
    old_review = json.loads((REPORTS / 'institution_v2q2_relevance_review.json').read_text(encoding='utf8'))
    review = read('relevance_review')
    review_checks = {k: review[k] == old_review[k] for k in ['rows', 'additional_private_rows', 'human_reviewed_rows', 'metrics']}
    assert all(review_checks.values()) and len(review['rows']) + len(review['additional_private_rows']) == 70
    regression = {
        'baseline_backend': [3102, 0, 20], 'baseline_frontend': [1028, 0, 0],
        'actual_backend': backend['counts'], 'actual_frontend': frontend['counts'],
        'backend_source_stable': backend['source_stable'], 'backend_group_count': backend['group_count'],
        'new_backend_tests': backend['counts']['passed'] - 3102, 'new_frontend_tests': frontend['counts']['passed'] - 1028,
        'new_automated_regressions': backend['counts']['failed'] + frontend['counts']['failed'],
        'build_exit': next(x['exit'] for x in frontend['checks'] if x['check'] == 'build'),
        'lint_exit': next(x['exit'] for x in frontend['checks'] if x['check'] == 'lint'),
        'lint_warnings': frontend['lint_actual_warnings'], 'existing_lint_warnings': 16,
        'frozen_tests_disabled': False, 'protected_rag_changed': False,
        'initial_errors_retained': ['digital_complete fixture 422 missing subjects', 'digital_closed fixture physical holding default', 'backend_runner_initial_error nonexistent harness path'],
        'preliminary_backend': 'First full run retained separately because source changed during it; final frozen rerun is authoritative.',
        'browser': 'PARTIAL; retained intermittent503 and restart502, not counted as zero-error live QA',
        'known_model_limits': 'Private B validator abstains 2/2; plural comparison after one-book focus clarifies; borrow-physically question produces a confirmation proposal rather than informational selection. No circulation action executed.',
        'relevance_preservation': review_checks, 'human_reviewed_rows': 0, 'relevance_metrics': 'NOT_MEASURED',
    }
    write('regression', regression)
    live, final, repeats = read('live'), read('live_final'), read('sequential_rechecks')
    linked_forms = [x for x in live['cases'] if x['question'] in ['Is there a digital version?', 'Can I read this online?', 'Does this book have a PDF?', 'Can I access the ebook?', 'Is it available digitally?']]
    assert len(linked_forms) == 10
    form_passes = [x['http'] == 200 and x['response'].get('availability') == [] and
                   len(x['response'].get('digital_availability', [])) == 1 and
                   x['response']['digital_availability'][0]['status'] == 'AUTHORIZED' for x in linked_forms]
    model_summary = {
        'result': 'PARTIAL', 'model': final['runtime']['qwen_model'], 'model_and_lock_changed': False,
        'initial_runtime': 'Seven turns in each of Global/A/B/I plus five linked-resource forms in each of A/B; before final topic-negative modality refinement.',
        'initial_http_cases': len(live['cases']), 'initial_http_errors': [x for x in live['cases'] if x['http'] != 200],
        'linked_forms': {'cases': len(linked_forms), 'authorized_without_physical_answer': sum(form_passes)},
        'final_runtime': final['runtime'], 'final_cases': final['cases'], 'sequential_rechecks': repeats,
        'browser_final_runtime': ['A digital question -> authorized PDF', 'B digital question -> authorized PDF -> actual viewer', 'B physical follow-up ->2 available/2total', 'Global digital question ->UNKNOWN'],
        'private_rag_verdicts': [{'library': x['library'], 'iteration': x['iteration'], 'http': x['http'], 'verdict': x.get('response', {}).get('verdict'), 'protected_candidate_used': x['protected_candidate_used']} for x in final['private_rag']],
        'conversation_cases': [{'library': x['library'], 'question': x['question'], 'http': x['http'],
            'intent': x.get('response', {}).get('intent'), 'message': x.get('response', {}).get('message'),
            'book_ids': [b['work_id'] for b in x.get('response', {}).get('books', [])]} for x in live['cases'][:28]],
        'limits': ['Global search/candidate provider controlled; database query returned all 10 synthetic Global books, not a relevance success.',
                   'Plural comparison after one-book focus clarifies, sometimes with an unhelpful position message.',
                   'Borrow-physically question routes to confirmation proposal; actions disabled and no borrow executed.',
                   'Actual B private-RAG intent still leads to NOT_SUPPORTED2/2 despite direct authored-intent positive validator probes.',
                   'No inference first-token time was measured; elapsed request and stage timings are retained.'],
    }
    write('real_qwen_validation', model_summary)
    protected = {p: {'before': checkpoint['source_sha256'][p], 'after': current_sha(p)} for p in ['rag/llm.py', 'rag/qa.py']}
    assert all(x['before'] == x['after'] for x in protected.values())
    qa = {
        'PART_2Q3_RESULT': 'PARTIAL', 'DIGITAL_AVAILABILITY': 'PASS', 'PHYSICAL_AVAILABILITY': 'PASS',
        'PRIVATE_DIGITAL_AUTHORIZATION': 'PASS', 'CONVERSATIONAL_REFERENCE': 'PARTIAL', 'TENANT_OWNERSHIP': 'PASS',
        'PRIVATE_FOR_YOU': 'PARTIAL', 'OLD_VALIDATOR_PATCH': 'REJECTED_AND_UNAPPLIED', 'NEW_VALIDATOR_CANDIDATE': 'REVIEW_ONLY',
        'PROTECTED_RAG_CHANGED': 'NO', 'REAL_QWEN_VALIDATION': 'PARTIAL', 'BROWSER_QA': 'PARTIAL',
        'BACKEND_TESTS': backend['counts'], 'FRONTEND_TESTS': frontend['counts'], 'NEW_REGRESSIONS': regression['new_automated_regressions'],
        'GLOBAL_HNSW_REBUILT': 'NO', 'GLOBAL_KG_REBUILT': 'NO', 'PRODUCTION_AUTH_CHANGED': 'NO',
        'PRODUCTION_TELEMETRY_ENABLED': 'NO', 'DEPLOYED': 'NO', 'COMMITTED': 'NO',
    }
    write('qa', qa)
    write('approval_record', {
        'old_validator_patch_sha256': '53a4bbd40eb950622b28a7e5b2b2c0daf9390d1f9dc5d16c5de3ed5031a31c92',
        'old_validator_patch': 'REJECTED_AND_UNAPPLIED', 'new_validator': 'Isolated prompt experiment only; unsafe, no source patch proposed.',
        'protected_files': protected, 'manifest_or_guard_changed': False, 'digital_fix_patch_sha256': patch['patch_sha256'],
        'authorization': 'User Part2Q.3 request authorizes scoped unprotected digital availability implementation and isolated evaluation. Earlier2O approval does not approve validator changes.',
    })
    changed = []
    for p in patch['paths']:
        changed.append({'path': p, 'absolute_path': str(ROOT / p), 'status': 'modified' if p in checkpoint['source_sha256'] else 'added',
                        'before_sha256': checkpoint['source_sha256'].get(p), 'after_sha256': current_sha(p),
                        'before_snapshot': str(ROOT / '.scratch/institution-v2q/digital-review/before' / p) if p in checkpoint['source_sha256'] else None})
    artifacts = sorted(set(list(ROOT.glob('scripts/institution_v2q3*')) + list(REPORTS.glob('institution_v2q3*')) + list(REPORTS.glob('institution_v2q_2q3_*'))))
    write('changed_files', {
        'relative_to': 'Immutable Part2Q.3 continuation checkpoint; existing pre-task dirty work preserved.',
        'application_and_tests': changed, 'patch_sha256': patch['patch_sha256'], 'patch_reverse_check_exit': reverse.returncode,
        'new_supporting_artifact_paths': [p.relative_to(ROOT).as_posix() for p in artifacts if p.is_file()],
        'transient_removed': ['frontend/.scratch/q3-vite.config.ts', '.scratch/institution-v2q/digital-review/lab'],
        'source_scope': 'Nine application files plus two test files; no other checkpoint source changes.',
    })
    backend_count = backend['counts']; front_count = frontend['counts']
    b = '/'.join(str(backend_count[k]) for k in ['passed', 'failed', 'skipped'])
    f = '/'.join(str(front_count[k]) for k in ['passed', 'failed', 'skipped'])
    body = f'''# LuminaR Part 2Q.3 completion

| Item | Executed result |
|---|---|
| A. Result | PARTIAL. Primary digital availability defect fixed; model-reference, validator and browser limitations remain. |
| B. Baseline | Backend 3102/0/20; frontend 1028/0/0. Legitimate dirty work retained. |
| C. Root cause | Digital questions entered physical CHECK_AVAILABILITY; the Book projection and renderer retained stock counts but had no fresh digital authorization signal. |
| D. Exact fix | Narrow request-modality detection, original finite book resolver, fresh authenticated Core digital lookup, strict typed evidence, deterministic response and digital-specific rendering. No new AI intent or persistence. |
| E. Contract | Catalogue presence, physical totals/available counts, canonical resource link, asset presence, access authorization and full-text accessibility are separate. UNKNOWN carries no hidden asset hints. See digital_contract.md. |
| F. Local-only books | Exact library UUID + local book UUID; no Global identity substitute. Tests include authorized digital-only book with no physical holdings. |
| G. Private authorization | Existing membership/code proof, asset visibility, READY state, source/artifact checks and authority barrier; repeat check on open. Foreign/revoked/forged access denied. |
| H. Follow-ups | Real Qwen seven-turn sequence in Global/A/B/I plus 10 linked A/B wording probes. Digital/physical evidence separate. Broader plural comparison and physical-borrow semantics remain partial. |
| I. Global chatbot | Final-runtime and browser Qwen PDF question gives UNKNOWN, no tenant assets or stock-only answer. Global retrieval/provider controlled in lab; production ranking/source unchanged. |
| J. Private chatbot | A/B authorized PDF answers and actual B PDF viewer pass. Final-runtime A/B/I checks retained. Private RAG A supported 2/2; B abstains 2/2 with unchanged protected validator. |
| K. Validator investigation | Isolated alternative failed safety review. No protected patch proposed/applied. Direct authored-intent positives do not establish a fix for actual B pipeline intent. |
| L. Negative evidence | All 25 Part 2Q.2 base cases unchanged. 31 runs/variant: original 6/25 negative acceptances; candidate 10/25. Six positive runs per variant, zero missed positives. Repeat strata/oracle ambiguity prevent universal or cross-phase accuracy claims. |
| M. Approval status | Old 53a4... patch rejected and unapplied; new prompt REVIEW_ONLY, unsafe. No RAG source/manifest/guard changes. |
| N. Browser | All 21 requested areas exercised to bounded extent; overall PARTIAL. A/B/Global genuine Qwen, authorized PDF open, physical follow-up, stale cancellation, unauthorized/revoked denials, no-match and relogin evidence retained. Actual viewport 487 inner/469 client, exact 390 unavailable; keyboard limited to Skip navigation plus existing component checks. |
| O. Backend | {b}, 38 groups, exit 0, final source stable. New focused tests 22/22. Frozen/security/native/RAG/tenant/physical/Assistant suites included. |
| P. Frontend | {f}, exit 0; two added rendering tests. |
| Q. Build/lint | Both exit 0. 16 existing lint warnings, no increase. |
| R. Preservation | {preservation['result']}. Read-only comparison and source hashes retained. Large global artifacts checked by size/mtime, not full multi-GB content rehash. No existing tenant/global rebuild, production auth/telemetry change, deployment or commit. Owned disposable DB/files/listeners removed; ordinary services stayed in initial off-state. |
| S. Exact files | See changed_files.json for 11 source/test paths with before/after hashes and all supporting report/script paths. Patch SHA256 {patch['patch_sha256']}; reverse check exit 0. |
| T. Product defects | B evidence validator still abstains on sufficient synthetic evidence; plural semantic references partial; informational physical-borrow question can yield an unexecuted confirmation proposal. Intermittent recommendation 503 during read/switch concurrency needs separate diagnosis. External full-text entitlements lack canonical signal, safely UNKNOWN. |
| U. Research limits | 70 review rows preserved, zero human labels; no Precision@K/MRR/nDCG. Synthetic controlled Global candidates are not 5M ranking evaluation. Greedy bounded model repeats are not calibrated safety metrics. Historical live metadata drift remains unattributed; no snapshot rollback. |
| V. Next action | Separately diagnose existing recommendation 503 and actual B intent/evidence interaction while preserving authorization; obtain independent relevance judgments. Do not apply either unsafe validator prompt. No Part 2R started. |

The preliminary full backend run is retained separately because application source changed during it. Only the final frozen run above is used for closure. Initial fixture 422/default-holding failures were corrected in fixtures and their logs retained. API 503 responses, lifecycle 502 responses and model abstentions remain visible in the raw evidence; zero automated regressions does not mean zero live errors.

The initial API A PDF 503 and A For You 503 were followed by sequential 200 checks after fixture writes completed. A later B recommendations 503 during ordinary switch/read concurrency was followed by 200. No authorization relaxation was made, and the latter cause is not fully attributed. Unauthorized/revoked browser 404s are expected denials. Two 502 poll errors correspond to the owned lab reload and ECONNREFUSED in Vite stderr. Network-buffer truncation in five batches prevents an exhaustive console/network claim.

Three initial native Search fixture generations were explicitly built for the owned A/B/I test libraries and removed with the disposable lab. No existing tenant or Global generation was rebuilt.

Protected source SHA256:

- rag/llm.py: {protected['rag/llm.py']['after']}
- rag/qa.py: {protected['rag/qa.py']['after']}

![Authorized PDF answer in Private B]({(REPORTS / 'institution_v2q3_browser_B_digital.png').as_posix()})

Final QA is recorded in institution_v2q3_qa.json. Tests, browser, model, preservation, fixture cleanup and exact file hashes are separate evidence artifacts. This work stops at Part 2Q.3.
'''
    (REPORTS / 'institution_v2q3_completion.md').write_text(body, encoding='utf8')
    # Refresh supporting paths after all final reports are created.
    manifest = read('changed_files')
    artifacts = sorted(set(list(ROOT.glob('scripts/institution_v2q3*')) + list(REPORTS.glob('institution_v2q3*')) + list(REPORTS.glob('institution_v2q_2q3_*'))))
    manifest['new_supporting_artifact_paths'] = sorted(set([p.relative_to(ROOT).as_posix() for p in artifacts if p.is_file()] + ['reports/institution_v2q3_artifact_manifest.json']))
    write('changed_files', manifest)
    manifest_files = sorted(set([ROOT / x['path'] for x in changed] + [p for p in artifacts if p.is_file()]))
    before_files = [p for p in (ROOT / '.scratch/institution-v2q/digital-review/before').rglob('*') if p.is_file()]
    write('artifact_manifest', {'generated_at': datetime.now(timezone.utc).isoformat(), 'files': [
        {'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in sorted(set(manifest_files + before_files)) if p.name != 'institution_v2q3_artifact_manifest.json'
    ], 'self_hash': None, 'self_hash_reason': 'Manifest cannot contain its own content hash.'})
    print(json.dumps({'qa': qa, 'preservation': preservation['result'], 'source_files': len(changed), 'patch': patch['patch_sha256']}))


if __name__ == '__main__':
    import sys
    if '--browser-only' in sys.argv:
        browser_report()
    else:
        closure_report()
