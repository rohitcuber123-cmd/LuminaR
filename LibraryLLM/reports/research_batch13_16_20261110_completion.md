# LuminaR Parts 13-16 plus Parts 04-07 consolidated completion

## A. Final result

PARTIAL. One reproducible analytics defect repaired. The initial full run contains one fencing failure; its unchanged-source 152-test group recheck passed. Four protected publication/recovery defects remain approval-required. Real Qwen and browser qualification remain unavailable.

## B. Current source baseline

Branch codex/search-v11-finalization; HEAD 606f0dfce3970bea8e6fc2b62d243433d1a66b8a. All 1,719 source/configuration hashes matched the completed Parts 08-12 tree before editing. Its raw grouped baseline was 3,197/0/20; unique testcase identities were 3,115/0/10. Extensive legitimate uncommitted changes, including the two prior ingestion/cache fixes, were retained. Preflight records dirty status, safe flags, protected hashes and 36 historical research fingerprints. No competing research/pytest runner was active.

## C. Part 13 analytics

Staff-only read-time aggregates remain canonical and tenant-scoped. ADMIN-only fee/member/outbox projections were preserved. The repaired defect was a valid PUBLISHED event with absent/null start and end being counted as completed because BSON null sorts before dates. event_metrics now requires a known effective date for completed counts. Publication-in-range counts remain independent of scheduling.

## D. Analytics metric oracle

The real-JWT fixture used literal independent expectations for one local book, quantity/requestable units 2, zero circulation/reservations/fees/events and five active memberships (1 ADMIN, 1 LIBRARIAN, 3 GENERAL_USER). Foreign B records were excluded. The approved 110-test analytics suite additionally compares explicit fee/ledger, allocation, committed activity, popularity, outbox and UTC-window expectations; it does not call the aggregator to calculate its oracle.

~~~json
{
  "active_books": 1,
  "total_holding_quantity": 2,
  "requestable_units": 2,
  "active_loans": 0,
  "pending_borrow_requests": 0,
  "pending_return_requests": 0,
  "active_reservations": 0,
  "upcoming_events": 0,
  "active_members": 5,
  "open_fee_balance_minor": "0"
}
~~~

## E. Analytics role and privacy

Current ADMIN/LIBRARIAN, patron, outsider, foreign owner, platform-only and expired-session cases used real JWT dependencies. Librarian role counts/outbox/waiver details were null. Small authorized cohorts are not anonymous; there is no approved minimum-cohort threshold. Privacy governance is POLICY_REQUIRED, not an authorization bypass or mandate for differential privacy.

## F. Analytics consistency

Controlled in-read role downgrade, removal, account disable, library suspension and audit-marker change were denied or rejected with retry behavior; an authorized next request recovered. An owned direct holding write bypassing audit/gates was intentionally invisible: the in-flight response reported quantity 2, the next reported 3. This reproduces the optimistic design boundary, not serializable isolation. No supported missing writer was proven; no broader lock or unbounded retry was added.

## G. Analytics performance

| Books | Holdings quantity | Aggregate calls | HTTP ms |
|---|---|---|
| 1 | 2 | 18 | 56.572 |
| 21 | 42 | 18 | 67.086 |

Single ADMIN requests on 1 and 21 synthetic books; caches not flushed and other regressions concurrent. maxTimeMS=10000 and allowDiskUse=False unchanged. Per-aggregate timings are in JWT summary. No p95, production scalability, peak-memory or full Mongo explain-plan claim.

## H. Part 14 frontend

No frontend application source changed. One axe-core 4.13.0 analytics structural regression was added using the already declared dependency. The analytics component run passed 32 checks. Complete frontend results are below.

## I. Role and route authorization

Existing ProtectedRoute/WorkspaceRoute and institution guards remain usability controls; backend remains authoritative. Component suites exercise login, role denial, source-role mismatch and invalid context. Current library membership is not granted by URL/localStorage. Token storage was not migrated and CSRF/session contracts were not redesigned.

## J. Library switch isolation

Existing scope keys, abort controllers, sequence checks and store reset behavior were preserved. Analytics tests cover range/account/library switch and revocation. Broader Search/Assistant/KG/notification stale-response tests execute in the full frontend suite. Complete real-browser switch coverage remains unqualified.

## K. Staff Intelligence UI

Current source retains 3-second active-build polling, 10-second request deadline, hidden-tab abort/sequence rejection, ADMIN build authority and read-only LIBRARIAN state. Progress explicitly describes stage items; 100% does not prove publication. Last durable heartbeat is not OS-liveness evidence. No protected JSX/transport boundary was changed.

## L. Mobile viewport

NOT_RUN. No task-owned real-browser runtime/session was established. No 390px, innerWidth/clientWidth, touch-target, screenshot or responsive task-success result is claimed. JSDOM/CSS assertions are not a 390px browser test.

## M. Accessibility

PARTIAL. The new analytics axe check covers wcag2a/wcag2aa/wcag21aa structural rules in JSDOM. Color contrast is explicitly excluded because this environment has no visual layout. Existing component semantics/focus tests passed. Manual keyboard, screen reader, zoom and full-site accessibility certification were not performed.

## N. Part 15 Qwen orchestration

Production routing/inference architecture unchanged. Controlled blocking generators exercised timeout/cancellation ownership and recovery, not native Qwen. The approved parser double with real JWT/Core transport verified session revocation while parsing: HTTP 404, zero returned books, no auth overrides.

## O. Actual model configuration

Runtime evidence records installed Python/Node dependencies, cached revisions and actual GPU observation: NVIDIA GeForce RTX 5060 Laptop GPU, 8151 MiB total, 7899 MiB free at observation, driver 610.88. Core/Search/Recommendation/RAG/frontend ports were unavailable. Source references Qwen2.5-3B-Instruct, CUDA NF4/float16 or CPU float32 fallback, local-only loads, MiniLM embeddings/reranker. No resident model/source identity, loaded tokenizer/context or active quantization was established. No weights downloaded or new Qwen launched.

## P. Shared inference contention

Three controlled cases passed. Timeout and client cancellation retained the occupied slot until the generator ended; the next request then succeeded and maximum concurrent generators remained one. The existing executor/RLock was unchanged. Milliseconds in gateway evidence are thread/control timings, not GPU throughput or real ingestion contention.

## Q. Timeout/cancellation recovery

The controlled timeout/cancel cases and existing tests preserve late exception retrieval and serialized execution. Native GPU cancellation, actual full-response latency and model exception recovery remain NOT_RUN. No artificial first-token metric for a nonstreaming API.

## R. Router and reference correctness

The current approved default router and experimental freeze remain intact. Full controlled suites cover topic routing, singular selection, current page, comparison pairs, local-only identities, availability and explicit confirmation. No example answers were hardcoded, ranking changed, or experimental router activated.

## S. Live Part 2Q acceptance

NOT_RUN against real Qwen. No qualified resident process existed to prove current patched source. Controlled parser/reference tests and a real-JWT in-flight session-denial test are separately labelled; they are not native model acceptance.

## T. Prompt injection/logging safety

Real-model document/metadata injection experiments NOT_RUN. Full source/grounding authorization suites remain unchanged. A synthetic canary in an injected generator exception was absent from gateway error/log output; only exception type/stage was logged. Protected LUMINAR_DEBUG_PROMPT can print formatted prompts when explicitly enabled; its source default is off. No live debug enabled. Deployment logging/retention remain unqualified, and changing protected logging needs separate review.

## U. Part 16 durable jobs

90-second lease and 10-second renewal remain unchanged. Job/target/generation and barrier/fence rules were preserved. Current complete product groups and prior source-matching native evidence are distinguished. Filesystem rename, pointer update and acknowledgement are not one cross-resource ACID transaction.

## V. Multi-worker claim safety

Existing isolated claim/fencing tests ran; the approved 152-test group passed on recheck. Prior native worker evidence is reused only because protected source fingerprints match. New OS-process multi-worker load was not run, and global distributed serialization is not claimed.

## W. Manifest and pointer validation

Current validation rejects wrong scope/hash/shape and readers fail closed, but the existing post-validation/pre-pointer gap remains a confirmed defect. Pointer publication cannot receive PASS. No global or existing tenant artifact was mutated.

## X. E-01 retained lock

APPROVAL_REQUIRED. Previously reproduced terminal success before tagged-lock release blocks supported recovery. Exact source/functions, durable state and required negative tests are carried into the approval proposal. Protected bytes match the eight completed Parts 08-12 reproduction records.

## Y. E-02 fence recovery

APPROVAL_REQUIRED. Interrupted target/job fence writes are not replayable. Proposal persists exact old/next intent under ownership CAS and verifies both writes before release. No fence bypass or lock takeover applied.

## Z. E-03 corrupt pointer risk

APPROVAL_REQUIRED, highest priority. Previously changing an owned manifest after validation moved the pointer and marked SUCCEEDED on Search and KG; reader status became RECOVERY_REQUIRED. Proposal binds publication to the validated digest and validates final identity/file set before CAS. No cross-tenant serving was demonstrated and no repair is claimed.

## AA. E-04 untagged barrier

APPROVAL_REQUIRED. A crash between generic lock insertion and intelligence tagging leaves an unknown barrier. Proposal includes reviewed intelligence ownership at insertion. Unknown/untagged locks must still reject unsafe takeover.

## AB. Operator diagnostics

Eight authenticated owned-Mongo checks passed: read principal accepted, write denied by server, row limit enforced, broad writer rejected as reader, restricted telemetry boot accepted, telemetry job mutation/provisioning denied, native job unchanged. New principals existed only in a separate ephemeral --auth mongod; no production credentials used.

## AC. Optional telemetry

Production disabled/unmodified. The actual ACL fixture exercised a restricted base Actor boot; full existing observer tests cover epoch/fence/payload rules. This is not production observer qualification or a process-liveness monitor. Auxiliary heartbeat remains evidence, not proof a process is alive.

## AD. Status performance

No new isolated status-cost benchmark. Source preserves prior Part 2I optimizations and current privilege rechecks. Prior timings remain historical; analytics request timings are not relabelled as status timings. No cache/duration changes made.

## AE. Parts 04-07 follow-up

Prior 386 JWT and 14 control checks were reused where source hashes match. New work targets selected gaps rather than a count-inflating full Cartesian matrix. Existing withdrawal/return, import replay, code budgets, invitations, governance and notification semantics remain unchanged.

## AF. Real-JWT coverage

82 HTTP calls inclusive of setup in the accepted new fixture. Current role projection, expired token, cross-tenant denial, controlled analytics authority changes and last-copy/FIFO assertions passed with zero dependency overrides and a fresh signing key. This is not 82 independent security test cases or complete endpoint coverage.

## AG. Async revocation

New analytics recheck boundaries and Assistant session revocation passed. Prior source-matching document mid-generation denial and existing Search/recommendation revocation tests are retained. Not every polling/circulation/publication race or every possible revocation instant was newly qualified.

## AH. Last-copy concurrency

Real JWT AGGREGATE and COPY runs each had two competing eligible borrowers: exactly one pending hold succeeded, the other was denied. Concurrent same-key approvals returned the same loan; one active loan and zero requestable/physical units remained. No negative stock or foreign allocation observed. This qualifies the tested race, not arbitrary worker schedules.

## AI. Reservation FIFO

After actual return in each stock mode, the first reservation became CONVERTED and the second remained WAITING. Current approved suites cover expiry/cancel/reject/ineligible-head/replay policy. Complete new real-JWT coverage of every queue transition remains partial; no priority/pickup-window policy changed.

## AJ. Journal recovery

Accepted independent v2b/v2c groups passed, including replay/fault cases. Unknown outcomes retain their existing recovery gates; no uncertain real lock stolen. No new arbitrary OS-kill journal qualification or protected journal redesign.

## AK. Import/fee replay

Existing matching-source replay and exact-minor-unit suites ran. The prior successful import replay and withdrawal-return observations remain valid within their scope. Fee reconciliation checks compare explicit values and reject corrupt state; desk payment is not external settlement.

## AL. Canonical due reminders

POLICY_REQUIRED. Located DUE_SOON/DUE_TODAY/OVERDUE scanners operate on global issues/due_date. No canonical institution_loans/due_at reminder producer was found in the inspected path. Existing tenant outbox consumes committed intents. No new worker, scheduling or reminder policy invented.

## AM. Cross-module tests

Analytics-role/canonical-state, current membership, real-JWT last-copy/FIFO, Assistant session denial, auxiliary Mongo ACLs and frontend analytics/route state were exercised. Inference injection, native GPU profiling, mobile/screen reader and independent process-liveness scenarios were not performed.

## AN. Confirmed root causes

AN-01 is BSON null/missing date ordering without a known-date predicate. The initial regression failure is WORKER_FENCED during fixture build, prior to the reranker assertion, with group elapsed 1105.99 seconds. Lease expiry during interruption is plausible, not measured OS proof. The same approved 152 tests passed unchanged in 78.29 seconds; no source-causal regression established.

## AO. Exact source fixes

| Changed file | Before SHA-256 | After SHA-256 |
|---|---|---|
| [backend/services/library_analytics_service.py](D:/SDC/LibraryLLM/backend/services/library_analytics_service.py) | 1eb38d43c6a020fa1a9170bfb474245d70ec63e3dab4f62b17544e3512b95620 | e0d44bc7947897b6ef651f9910e860449944d7b4c24fb185a9b0aaa2bf2627b1 |
| [frontend/tests/institution-analytics.test.tsx](D:/SDC/LibraryLLM/frontend/tests/institution-analytics.test.tsx) | bb8de376adddecfd6aa0f916c8a204bbb6367e52d91df4d6318d974bd9aac831 | 7bf7df9e4d43ed3d5f8489788744d029122b347e87f23c3d329ba8bec8590337 |
| [tests/institution_v2e/test_analytics.py](D:/SDC/LibraryLLM/tests/institution_v2e/test_analytics.py) | f66dac06adc99049bce452309f6494f293fed7e0614469bc35905efaba6a25c6 | 0626c50b4c6547735eb3081f612e97bfbb706e135566c5fb04178cc6b4961c6f |

Only one application file changed, plus one parameterized backend function (two cases) and one frontend axe test. All previous accepted source changes remain. No migration/index/model/guard rebaseline.

## AP. Before/after results

Before: two missing/null-date cases failed (completed=2, expected=1). After: the 110-test analytics suite passed, including completed=1 while published-in-range=4. The 32 frontend analytics checks passed. An initial combined v2b/v2c/v2e run had 226 passing cases and a fixture teardown namespace error; separate established processes were retained instead of altering assertions. Initial ACL setup mistakes (wrong method, missing schema), JWT fixture mistakes (missing subjects, Response/JSON mismatch), and broad archival collection errors remain recorded.

## AQ. Backend regression

Initial full 38-group run, unique testcase identities: 3,116 passed / 1 failed / 10 skipped. Raw grouped executions: 3,198 passed / 1 failed / 20 skipped. The approved inventory repeats 92 testcase executions; these do not inflate the unique result.

Same-source 152-test group recheck: 152/0/0. Latest per-case outcomes after that recheck: 3,117 passed / 0 failed / 10 skipped. This is not an uninterrupted clean full run. The first failure was not deleted or overwritten. The wider-folder attempt also hit archived C3/C4 freeze assertions and missing C5a native environment; no protection was weakened.

## AR. Frontend regression

1,033 passed / 0 failed / 0 skipped. One repeated display name belongs to distinct tests in two different source files. No same-file duplicate was added to inflate counts. Frontend application source unchanged.

## AS. Build and lint

Production build PASS. Lint PASS with 16 existing warnings. Logs retain all errors/warnings. CRLF-aware source whitespace check passed.

## AT. Protected contracts

75 passed / 0 failed / 0 skipped. Frozen tests/manifests and protected RAG/worker/service/store/artifacts match preflight. Guard success is not a repair of E-01 through E-04.

## AU. Source/data preservation

1,719 source/configuration hashes checked; exactly three intended files changed, 1,716 unchanged. Both Parts 08-12 repairs preserved. HEAD, frontend application source, protected hashes, resident catalogue/communications digests, pointers/jobs/generations, index specifications and global/tenant artifact observations matched the accepted reference. Large artifacts use size/mtime and pointer hashes rather than a new full-byte scan.

## AV. Disposable cleanup

All 11 wrapper Mongo runs stopped their owned processes and removed temporary roots, including unsuccessful setup/test attempts. The successful authenticated ACL run has a direct cleanup receipt. The first two ACL setup failures lack per-run receipts; a retrospective check found no matching owned roots/processes. No unrelated resident process/data was reset. Credentials/tokens never recorded in reports.

## AW. Research measurements

Evidence tiers are SOURCE_OBSERVATION, MOCKED_COMPONENT_TEST, REAL_API_INTEGRATION and controlled thread/helper tests. Current package/device/cached-revision observations are distinct from real model execution. No real Qwen requests, first-token rate, p95, learning outcome, user-study, production ACL or deployment latency claim. Historical 36-file evidence is preserved and reconciled in the issue register, including blocked archival collection and the observed optimistic consistency boundary.

## AX. Approval-required patches

See exact protected approval proposal with source hashes, boundaries, preservation conditions, positive/negative/crash tests and rollback/recovery consequences. No protected source patch applied. E-03 first, then replayable E-01/E-02 recovery, then insertion-time E-04 ownership. Protected debug-logging changes also need separate review if requested.

## AY. Remaining engineering issues

Four protected failures remain. The initial full-run fencing failure remains visible and did not reproduce on retry; a clean uninterrupted full run is not claimed. Complete real-JWT endpoint/async matrix, all FIFO transitions, native model timeouts and actual mobile/accessibility workflows remain incomplete. Canonical reminders need policy.

## AZ. Remaining research limitations

Small-cohort governance unresolved; aggregates are not anonymous. Synthetic small-library request timings are not production capacity. One axe component is not WCAG certification. Current real-Qwen patched-code and Private B validation remain unavailable. Exact OS suspension during the initial failure was not measured.

## BA. Next recommended action

Review the protected E-03 proposal first. Arrange an owned current Qwen/browser acceptance environment separately. Investigate the interrupted-run fencing observation if it recurs without a pause; preserve native lease protections. Resolve canonical reminder/privacy policy before implementation. Stop after this consolidated phase; no Part 17, deployment or commit.

## Evidence

- [Issue register](D:/SDC/LibraryLLM/reports/research_batch13_16_20261110_issue_register.json)
- [Preflight](D:/SDC/LibraryLLM/reports/research_batch13_16_20261110_preflight.json)
- [Runtime](D:/SDC/LibraryLLM/reports/research_batch13_16_20261110_runtime.json)
- [JWT/oracle/measurements](D:/SDC/LibraryLLM/reports/research_batch13_16_20261110_jwt_03_summary.json)
- [Assistant revocation](D:/SDC/LibraryLLM/reports/research_batch13_16_20261110_assistant_01_result.json)
- [Gateway controls](D:/SDC/LibraryLLM/reports/research_batch13_16_20261110_gateway.json)
- [Authenticated ACLs](D:/SDC/LibraryLLM/reports/research_batch13_16_20261110_acl_03.json)
- [Consistency bound](D:/SDC/LibraryLLM/reports/research_batch13_16_20261110_bound_result.json)
- [Regression results](D:/SDC/LibraryLLM/reports/research_batch13_16_20261110_regression.json)
- [Protected proposals](D:/SDC/LibraryLLM/reports/research_batch13_16_20261110_approval_proposals.md)
- [Preservation](D:/SDC/LibraryLLM/reports/research_batch13_16_20261110_preservation.json)
- [Exact files and SHA-256](D:/SDC/LibraryLLM/reports/research_batch13_16_20261110_changed_files.json)

## Machine-readable final QA

~~~json
{
  "BATCH13_16_PLUS_04_07": "PARTIAL",
  "ANALYTICS_METRIC_CORRECTNESS": "PASS",
  "ANALYTICS_ROLE_ISOLATION": "PASS",
  "ANALYTICS_CONCURRENT_CONSISTENCY": "PARTIAL",
  "ANALYTICS_PRIVACY": "POLICY_REQUIRED",
  "ANALYTICS_PERFORMANCE": "MEASURED",
  "FRONTEND_ROLE_GATES": "PASS",
  "LIBRARY_SWITCH_ISOLATION": "PARTIAL",
  "STAFF_INTELLIGENCE_UI": "PARTIAL",
  "MOBILE_390PX": "NOT_RUN",
  "KEYBOARD_ACCESSIBILITY": "PARTIAL",
  "AUTOMATED_AXE": "PARTIAL",
  "SCREEN_READER": "NOT_RUN",
  "LIVE_QWEN": "NOT_RUN",
  "PATCHED_ASSISTANT_VERIFIED": "PARTIAL",
  "QWEN_TIMEOUT_RECOVERY": "PARTIAL",
  "SHARED_INFERENCE_CONTENTION": "PARTIAL",
  "PROMPT_INJECTION_NEGATIVES": "NOT_RUN",
  "DEBUG_PROMPT_PRIVACY": "PARTIAL",
  "DURABLE_JOB_CLAIMS": "PARTIAL",
  "LEASE_FENCING": "PARTIAL",
  "MANIFEST_INTEGRITY": "PARTIAL",
  "POINTER_PUBLICATION": "FAIL",
  "E01_RETAINED_LOCK": "APPROVAL_REQUIRED",
  "E02_FENCE_RECOVERY": "APPROVAL_REQUIRED",
  "E03_CORRUPT_POINTER": "APPROVAL_REQUIRED",
  "E04_UNTAGGED_BARRIER": "APPROVAL_REQUIRED",
  "OPERATOR_DIAGNOSTICS": "PASS",
  "OPTIONAL_TELEMETRY": "PARTIAL",
  "PRODUCTION_TELEMETRY_ENABLED": "NO",
  "PART04_07_ROUTE_COVERAGE": "PARTIAL",
  "ASYNC_REVOCATION": "PARTIAL",
  "LAST_COPY_CONCURRENCY": "PASS",
  "RESERVATION_FIFO": "PARTIAL",
  "JOURNAL_RECOVERY": "PARTIAL",
  "IMPORT_REPLAY": "PASS",
  "FEE_LEDGER": "PASS",
  "CANONICAL_DUE_REMINDERS": "POLICY_REQUIRED",
  "CROSS_TENANT_SECURITY": "PARTIAL",
  "UNREQUESTED_LOAN_MUTATIONS": 0,
  "REAL_MODEL_REQUESTS": 0,
  "BROWSER_WORKFLOWS": "NOT_RUN",
  "BACKEND": {
    "passed": 3116,
    "failed": 1,
    "skipped": 10
  },
  "FRONTEND": {
    "passed": 1033,
    "failed": 0,
    "skipped": 0
  },
  "PROTECTED_CONTRACTS": {
    "passed": 75,
    "failed": 0,
    "skipped": 0
  },
  "BUILD": "PASS",
  "LINT": "PASS",
  "NEW_REGRESSIONS": 1,
  "GLOBAL_HNSW_REBUILT": "NO",
  "GLOBAL_KG_REBUILT": "NO",
  "EXISTING_TENANT_INDEX_REBUILT": "NO",
  "PROTECTED_RAG_CHANGED": "NO",
  "PROTECTED_PUBLICATION_SOURCE_CHANGED": "NO",
  "PRODUCTION_MONGO_AUTH_CHANGED": "NO",
  "PRODUCTION_MONGO_QUALIFIED": "NO",
  "DEPLOYED": "NO",
  "COMMITTED": "NO",
  "INITIAL_FULL_BACKEND_EXECUTIONS": {
    "passed": 3198,
    "failed": 1,
    "skipped": 20
  },
  "BACKEND_AFTER_UNCHANGED_SOURCE_GROUP_RECHECK": {
    "passed": 3117,
    "failed": 0,
    "skipped": 10
  },
  "V2G_RECHECK": {
    "passed": 152,
    "failed": 0,
    "skipped": 0
  },
  "REPRODUCIBLE_NEW_SOURCE_REGRESSIONS": 0,
  "LINT_WARNINGS": 16,
  "NEW_APPLICATION_REPAIRS": 1,
  "NEW_BACKEND_CASES": 2,
  "NEW_FRONTEND_CASES": 1,
  "QUALIFICATIONS": {
    "BACKEND": "Deduplicated testcase identities from initial full run; initial failure remains visible. Latest per-case outcomes after the unchanged-source 152-test recheck are separate. No uninterrupted clean full run is claimed.",
    "NEW_REGRESSIONS": "Conservative count of one initially failing existing testcase absent from baseline. It did not reproduce in the 152-test retry; source causation and OS suspension are unproven.",
    "FRONTEND": "1033 distinct file/test cases. One repeated display name belongs to two different files, not a duplicated execution.",
    "PASS": "Limited to executed fixture scope, not production or a complete authorization/race proof.",
    "AXE": "Analytics component in JSDOM; color-contrast excluded because layout is unavailable."
  }
}
~~~
