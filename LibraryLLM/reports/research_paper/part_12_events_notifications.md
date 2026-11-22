# Part 12 — Institution events, announcements and member communication

## Research motivation and scope

An institution library needs to explain event changes, service notices and ordinary updates to its own members without granting platform-wide publishing authority. Motivating failure modes include disconnected email lists, stale membership exports, duplicate retries, unread counters that disagree with delivered copies, and links opening the wrong library after a workspace switch. These are engineering questions evaluated here, not claims supported by fabricated survey statistics.

LuminaR already had global Events, tenant Events and account notifications before Part2P. A useful research contribution is an incremental integration that retains those working paths while adding explicit immutable publications, canonical member targeting and observable retry behavior. This documentation describes the implementation and its finite evaluated corpus; it is not an IEEE paper or a novelty claim against all prior systems.

## Audited existing behavior

`event_service.create/edit/transition/listing` and `library_event_service.access/mutate` provide UUID event identity, first-publish history, editable details, cancellation reasons and institution access controls. The existing LIBRARY_NOTICE category supports undated event notices. `event_user_state` tracks global event-seen receipts separately from inbox notifications; these semantics are preserved, not merged into a contradictory second unread count.

`notification_service.insert_notice/list_own/unread/mark_read/read_all/get_own/present_own` stores durable account-owned notices with a globally unique dedupe key. `tenant_notification_service.append_intents/materialize` consumes committed lending journal intents for circulation, reservations and fees. The single `NotificationCenter.tsx` already polls, paginates, marks read, displays source-library labels and revalidates navigation. Part2P extends these components rather than replacing them.

## Actual implementation

`backend/schemas/library_announcements.py` defines plain-text DraftCreate, DraftUpdate and Revision. `library_announcement_service.py` owns create/update/publish/withdraw/detail/listing, batched eligible_recipients and bounded deliver_one/deliver_pending/retry_delivery. `backend/routes/library_announcements.py` maps those functions into the existing authenticated institution API. The announcement collection exists because the existing editable published-event model cannot enforce immutable delivered content without changing accepted Event behavior.

The lifecycle is DRAFT → PUBLISHED → WITHDRAWN. Only drafts can be edited, with a revision token. Published corrections use withdrawal and a new draft/publication; no hidden revisions. Creator, library and timestamps are server-derived. Category GENERAL/EVENT/LIBRARY_UPDATE/IMPORTANT_NOTICE and priority NORMAL/IMPORTANT affect presentation only. An optional canonical tenant event reference connects to existing Event detail. No automatic event-transition broadcast, RSVP or scheduling is added.

Recipient policy: all currently eligible active institution roles can read published content. Notification copies go only to the server-resolved publication-time snapshot, capped at20,000 membership records. New members may read earlier publications without receiving historical copies. Revoked users cannot fetch protected content or new private notification copies, including their unread count. Multi-institution users retain the existing explicitly labeled aggregated inbox.

## Data and API contracts

| Mongo field / group | Representation | Authority |
|---|---|---|
| announcement_id, library_id | Canonical UUID strings | Server UUID and validated authorized route; immutable |
| created_by_user_id, updated_by_user_id | Numeric canonical user IDs | Current verified identity, never submitted ownership |
| published_by_user_id, withdrawn_by_user_id | Numeric canonical user IDs | Server identity at the lifecycle transition; staff history only |
| request_id | UUID | Draft-create retry identity, unique with library and creator |
| title, body | Plain text, at most140/5000 characters | Validated author input; no raw HTML rendering |
| category, priority | Four categories; NORMAL/IMPORTANT | Validated presentation enums, no privilege effect |
| status, revision | DRAFT/PUBLISHED/WITHDRAWN; integer CAS token | Server state machine |
| linked_event_id | Optional same-library event UUID | Existing canonical event identity |
| audience | ALL_ACTIVE_MEMBERS | Server constant |
| created_at, updated_at, published_at, withdrawn_at | UTC timestamps stored at Mongo millisecond precision | Server clock; first publication immutable |
| delivery.recipients | Bounded numeric snapshot, at most20,000 membership records | Canonical publication-time eligibility; not serialized |
| delivery.state, cursor, total, delivered, suppressed | Durable enum and counters | Existing worker adapter / authorized bounded retry |
| delivery.attempts, last_error_code, next_attempt_at | Up to10 persisted failed attempts, safe code, UTC | Detectable bounded recovery |
| notifications.notification_id, dedupe_key | Existing notification identity and unique key | Shared insert_notice; key includes tenant/publication/recipient/type |
| notifications.read_at | Existing nullable UTC timestamp | Authenticated recipient ownership and current new-type visibility |

| Current institution role | Published announcements | Draft/publication history | Manage |
|---|---|---|---|
| Owner with ADMIN membership / ADMIN | Read in Staff workspace | Yes | Create/edit draft/publish/withdraw/retry |
| LIBRARIAN | Published-only reader in Staff workspace | No | No new grant |
| GENERAL_USER | Member library reader | No | No |
| Other-library/platform-only admin or private outsider | No absent eligible membership | No | No |
| Revoked/ineligible account or invalid invitation proof | No | No | No |

The full field table is in `part_12_announcements_architecture.md` and `../institution_v2p_database_contract.md`. Core fields are canonical announcement_id/library_id, creator, request_id, plain-text content, enums, status/revision, linked_event_id, server timestamps and delivery snapshot/counters/error state. The existing notifications collection adds no parallel unread field: read_at remains the authority. Unique dedupe keys include tenant, publication, user and event type.

Read endpoints live under `/libraries/{id}/announcements` and staff endpoints under `/staff/announcements`; create/patch/publish/withdraw/retry use the same institution convention. UUID validation, forbidden extras and bounded pagination follow existing conventions. Backend access is current account + membership + accepted invitation proof + role + shared tenant lock; see the security document for the exact matrix. Client-provided recipient lists, creator IDs and publication history are rejected.

## Consistency and failure handling

One Mongo document atomically captures publication plus its durable recipient snapshot/cursor. Existing worker slices materialize copies through the existing notification service. The copy and cursor are separate documents: cursor replay after a crash is expected, and unique dedupe keys prevent duplicate logical delivery. Ten failures stop automatic retries and expose FAILED state; authorized manual repair processes one bounded slice. No transaction claim, external messaging system or new worker is introduced.

A published response may report delivery PENDING. Staff sees processed/delivered/suppressed totals separately; the UI never claims fan-out completion based solely on publication. Withdrawal stops further delivery and disables generic-copy navigation. Unknown-outcome domain mutations retain the project's fail-closed library lock for operator reconciliation; this implementation never silently clears it.

## Frontend architecture

`LibraryAnnouncements.tsx` adds Staff/member pages using existing WorkspaceRoute, LibraryShells, PageHeading, StatePanel, Modal, Pager and LuminarSelect styling. `libraryAnnouncements.ts` imports the canonical institutionApi; protected transport modules remain unchanged. Draft validation, preview, confirmation, stale revision/error presentation, pending/failed delivery, linked-event availability and member detail are implemented as one context-keyed workspace. It checks session/library/role and aborts obsolete reads. The existing bell gains only a new canonical action type and priority presentation.

## Verification, measurements and research interpretation

The authoritative executed results are in `part_12_events_notifications_evaluation.md` and `../institution_v2p_{security,backend_tests,frontend_tests,browser,performance,regression,preservation}.json`. Source inspection and successful test execution have distinct labels in the feature matrix. No baseline count is reused as a final result. Disposable local Mongo performance is not production throughput, and a read receipt does not demonstrate comprehension or engagement.

## Limitations and ongoing work

The20,000-recipient ceiling and per-library bounded serialization constrain large institutions. One generic copy is available in the existing account inbox; external messaging, preferences and a dedicated scheduler are absent. The editor's linked-event menu lists at most50 published events, while an existing saved reference is retained; it is not a full event-search workflow. Plain-text input cannot identify every secret written by a person. Browser revalidation can deny new access but cannot erase content already copied while authorized. Operator recovery of unknown-outcome domain locks remains an existing deployment responsibility.

Part2P is the active implementation scope until final evidence is written. Future communication features are explicitly NOT_IMPLEMENTED/PLANNED in the roadmap. Nothing here authorizes another phase, production auth/telemetry activation, deployment, commit or intelligence rebuild.


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
