# Part 12 — Evaluation methodology and evidence

Use the exact current-tree reports, raw pytest XML and frontend/browser logs referenced by the final evidence section. Counts copied from historical Part2O.3 are a comparison baseline, not experimental results for2P.

## Evaluation questions

1. Does every announcement/notification read and mutation preserve tenant and account isolation, including role claims, accepted invitation proof, private code, revocation and stale sessions?
2. Does a publication preserve first-publication history and immutable content under concurrent staff requests and stale edits?
3. Can fan-out resume after partial writes, cursor acknowledgment loss or process restart without duplicate logical copies?
4. Do the existing Events workflows, account-wide bell and read state remain coherent across refresh, library switching and logout?
5. What bounded operation counts and latency are observed on the actual local standalone Mongo fixture at several institution sizes?
6. Do the protected RAG/transport/intelligence contracts and existing product regressions remain intact?

## Executed-test design

`tests/institution_v2p/test_announcements.py` uses real Mongo indexes, actual route/service authorization and disposable canonical institutions. Negative parameterized cases cover missing auth, member/librarian/foreign admin/platform-only management, forged server-owned fields, unsafe/oversized input, foreign events, draft leaks, cross-user reads, revocation, invitation proofs and route spoofing. Concurrency uses independent requests with ThreadPoolExecutor. Fault injection deliberately fails insert_notice or the cursor write and verifies replay counts. These controlled faults are disclosed rather than described as observed production incidents.

`frontend/tests/institution-announcements.test.tsx` exercises the real React page/bell with transport fixtures: create/edit/validation/preview, confirmation/failure, role controls, status filtering, linked events, delayed stale-library results, logout/revocation and read states. Fixtures are not evidence of backend authority; backend tests separately exercise that boundary.

`scripts/institution_v2p_browser.py` runs actual Chromium, real JWT validation, production FastAPI ASGI routes and a uniquely owned real Mongo database. Browser HTTP bridges in-process to TestClient. Only unrelated search/recommendation/RAG/decorative requests are stubbed. Existing tenant notification materialization is invoked explicitly, not a new scheduler/worker. Distinct A/B admins, members, librarian and outsider fixtures separate tenant roles. Viewport checks and screenshots test1440/1366/1024/768/390/375 widths; focused axe and keyboard tests cover the new dialog. This finite scan is not a blanket accessibility certification.

`scripts/institution_v2p_intelligence_browser.py` re-executes the accepted O.3 owned browser harness with separate evidence names to preserve status/progress/last-good/role/tenant behaviors. Controlled intermediate durable progress states are labeled as fixture states; native fixture builds are manually requested and never global rebuilds.

## Performance protocol

`scripts/institution_v2p_performance.py` creates20/200/2000-recipient institutions in a uniquely owned real local database. It measures publication, complete bounded fan-out, member listing, unread count and inbox retrieval with perf_counter. PyMongo CommandListener records actual command counts. Listing/count/inbox operations each use five samples and report medians plus raw samples; no statistically unsupported production percentile is invented. Dataset setup/index creation is excluded from measured operations. Storage/caching/hardware effects limit generalization. There is no live model, email or provider cost in these measurements.

## Regression and preservation protocol

The full accepted product inventory through O.3 runs as separate existing fixture processes. The existing Events date-alignment harness is preserved. Historical skips and warning lines are compared by identity; no tests are suppressed. Production build and lint run after the complete frontend suite. Fresh baseline source/data/index/artifact/report snapshots are compared after cleanup. Any errors, harness defects and corrected reruns stay recorded in logs and the regression report.

No scientific citations or production metrics are fabricated. The final evidence section is generated only after executing the checks.

## Observed test-isolation qualification

Preservation inspection initially found an empty new announcement collection and one valid SYSTEM overdue reminder in the default database; the initiating process was not conclusively attributed. The empty schema was verified and removed before any live publication. Later, an existing TEST-library account outside the fixtures published an announcement and three copies appeared; this populated namespace and all records were retained. The original50 notification documents match the baseline after excluding new IDs. An old pending borrow request also expired through the existing committed actor0 journal. Its exact original creation receipt reconstructs the baseline in memory; the valid expiry was not reversed. Original event/loan/reservation records, audit/operation history and native/private artifacts are preserved. The clean runner now gives legacy default imports an owned database/session scope; frozen tests/assertions remain intact. No equality claim is made for global notification indexes because they were not snapshotted before the task. See ../institution_v2p_concurrent_activity.json and preservation.json; raw database equality is not a valid expectation under concurrent live use.


## Final executed Part2P evidence

Status: PASS. Final actual-tree backend2917 passed / 0 failed / 20 skipped; frontend988 passed / 0 failed / 0 skipped. Production buildPASS; lintPASS with16 pre-existing warnings and0 new warnings. Current feature checks84; legacy notification recheck51; existing installed protected mutation checks75. Supplementary checks are not double-counted.

Real communication Chromium23 checks; preserved Intelligence Chromium29 checks; isolated authenticated-Mongo10 checks. No unexpected HTTP/page JavaScript errors. Expected404 revocation responses are retained. Data/fixture cleanup is recorded in browser/auth evidence. No current2P implementation remains IN_PROGRESS after closure; future features remain NOT_IMPLEMENTED/PLANNED.

| Feature | Research status | Source/evidence |
|---|---|---|
| Immutable announcements and tenant lifecycle | IMPLEMENTED_VERIFIED | library_announcement_service create/update/publish/withdraw; final_clean_institution_v2p.xml |
| Canonical audience and delivery recovery | IMPLEMENTED_VERIFIED | eligible_recipients/deliver_one; security.json |
| Existing shared inbox and read state | IMPLEMENTED_VERIFIED | notification_service; notification_recheck.xml and browser.json |
| Staff/member/librarian UI | IMPLEMENTED_VERIFIED | LibraryAnnouncements.tsx; final5_frontend.log |
| Existing Events and native progress preservation | IMPLEMENTED_VERIFIED | final_events.xml and intelligence_browser.json |
| Production deployment | NOT_IMPLEMENTED | No deployment authorized or performed |
| Capacity at configured20,000-member ceiling | IMPLEMENTED_NOT_VERIFIED | Cap enforced/tested; largest measured fan-out2,000, no production throughput claim |
| Scheduling/RSVP/external messaging/preferences | NOT_IMPLEMENTED | Future roadmap only |

Measured real local standalone-Mongo fixture results (cohosted with regression workloads):

| Recipients | Publication ms | Full fan-out ms | List median ms | Unread median ms | Inbox median ms |
|---|---|---|---|---|---|
| 20 | 17.005 | 83.203 | 10.832 | 8.204 | 24.27 |
| 200 | 20.776 | 757.09 | 9.892 | 7.436 | 22.327 |
| 2000 | 59.042 | 7525.843 | 9.287 | 6.204 | 23.102 |

Each list/count/inbox median uses five actual samples; raw command counts/samples are in ../institution_v2p_performance.json. No production percentile/throughput or engagement outcome is claimed. Preservation resultPASS; approximately5M global catalogue, global/tenant artifacts and original event/notification records preserved. Concurrent live activity is explicitly recorded: a TEST-library announcement by existing creator4 and three copies, one valid SYSTEM overdue reminder, and a committed actor0 request-expiry transition. Original50 notices/audit/operation digests match; the original request receipt projection verifies the expiry without a DB reversal. The initial empty schema cleanup predates live publication; populated live records are retained. The final runner isolates fallback startup. No production auth/telemetry activation, automatic/global rebuild, commit or deployment.
