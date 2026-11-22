# Part 12 — Member communication security

Threat model: authenticated users may forge resource IDs, creator/recipient fields, role claims, event references, publication retries, notification routes and stale browser context. Platform administration does not imply institution membership. A private access code is only a membership admission mechanism, never a substitute for current authority. Browser hiding is presentation; every API action is enforced by backend services.

| Role / current authority | Published read | Draft/history read | Manage announcements |
|---|---|---|---|
| Institution owner with active ADMIN membership | Yes | Yes | Yes |
| Institution ADMIN | Yes | Yes | Yes |
| Institution LIBRARIAN | Yes | No | No; existing event permissions preserved |
| GENERAL_USER member | Yes | No | No |
| Other-library staff / platform-only admin | No without membership | No | No |
| Revoked/invalid proof/inactive account/private outsider | No | No | No |

`library_announcement_service.access` combines existing `eligible_actor`, `require_library_membership` and canonical `require_library_role`. Reads and domain mutations take `institution_repository.library_mutation`, retaining the established fail-closed recovery contract. Recipient selection uses ACTIVE canonical memberships, valid accepted invitation proof, active verified account role and password-setup eligibility. Membership is resolved at publication time for notification copies and again at delivery; current membership controls published-content access for later joiners and revoked users.

`announcement_notification_access.visible_query` applies recipient + library + current membership filtering to the new private type within the existing account inbox. Other generic tenant notification history preserves its accepted Part2D behavior. `present` reconstructs a route from canonical source IDs and current PUBLISHED state. `frontend/src/lib/notifications.ts` validates the exact route before navigation. Neither a stored external route nor the active workspace may redirect a notice to a different tenant.

Plain-text inputs have bounded title/body and enum values. Extra ownership/history/recipient fields are rejected. No raw HTML insertion, rich editor, external image embedding or auto-link interpretation is introduced. Private keys are rejected; staff UI warns against credentials/member secrets. Plain-text validation cannot detect every possible human-written secret, which remains a documented limitation. Generic notification copies contain no announcement body, internal Mongo IDs, filesystem paths or worker diagnostics.

The frontend uses the existing protected canonical transport without changing its fingerprints. A library/session/role/detail-keyed workspace discards stale async state; AbortController stops obsolete reads. Returned tenant IDs and member PUBLISHED state are checked before display. Existing WorkspaceRoute resolves the URL through the server. Focus refresh revalidates visible lists; backend reads/actions always revalidate authority. Already rendered content cannot be retroactively erased from an offline person's memory or screenshot; this is not a DRM claim.

Negative tests exercise real backend authority in uniquely owned Mongo databases, including forged roles/IDs, private outsiders, revoked membership, cross-user read, concurrent publication, stale revision, duplicate fan-out, failed cursor acknowledgment and unsafe content. Actual executed counts and failures belong in the evaluation report. Protected RAG, O.3 guards, intelligence protocols and production authentication/telemetry are outside the editable scope and are independently hashed for preservation.


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
