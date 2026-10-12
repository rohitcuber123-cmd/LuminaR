# Institution Part 2D — final PASS

2026-10-11T13:14:34.831184+00:00

| Requested result | Evidence-backed outcome |
|---|---|
| A. FINAL | PASS — Institution Part 2D complete; all 56 acceptance gates verified. |
| B. Existing Events audit | 67 pre-change production matches inventoried; useful Events V1 implementation reused. |
| C. Existing Notifications audit | 28 pre-change matches inventoried; account inbox, global reminders and explicit platform sender retained. |
| D. Final event model | One collection; immutable UUID, canonical tenant library UUID, content/schedule, visibility, lifecycle, revision and provenance. |
| E. Event authorization | Current LibraryMembership ADMIN/LIBRARIAN manages own library; GENERAL_USER reads; Platform-only, legacy role and cross-library management denied. |
| F. Event visibility | Private members only; optional PUBLIC publication on public/public-mode libraries; staff-only drafts; cancelled history safe. |
| G. Staff Events | Canonical list/detail/new/edit routes, upcoming/draft/past/cancelled views and shared editor/dialogs. |
| H. Patron Events | Canonical list/detail, context-aware header/footer and bounded optional Home upcoming section. |
| I. Global Events | Explicit global API and Platform-managed global Events retained; tenant publications excluded from global listing/badge. |
| J. Event migration | Dry-run default; one legacy global record classified, preserved, zero applied changes. Explicit review/mapping required. |
| K. Final notification model | Existing user-owned inbox with explicit GLOBAL/PLATFORM/LIBRARY, canonical source, audience and library UUID only for LIBRARY. |
| L. Notification types | Borrow created/approved/rejected; return requested/confirmed; reservation created/cancelled/expired/ready; fee assessed/waived/adjusted/payment recorded. |
| M. Staff recipients | Current exact-library ADMIN/LIBRARIAN recipients; no unrelated staff or platform-role fanout. |
| N. Patron recipients | Canonical domain target with current exact-library GENERAL_USER membership. |
| O. Deduplication | Immutable audit + library + recipient key; approval, return, rejection and payment retries produced no duplicate inbox records. |
| P. Outbox / durability | Intents persisted in existing Part 2B/2C plans before execution; COMMITTED-only bounded retry worker; durable inbox upsert and acknowledgement-loss tests. |
| Q. Notification bell | Account-owned inbox, source labels, pagination, correct badge and mark-one/all retained. |
| R. Routing | Fresh server authorization plus one canonical source-based resolver; active UI context cannot override source UUID/role. |
| S. Multi-library behavior | Same QA user validated as A GENERAL_USER, B ADMIN and C LIBRARIAN; every bell action opened the correct workspace. |
| T. Suspended / removed behavior | Tenant activities denied; historical notices retained with Library unavailable; restores retained exact event/inbox data. |
| U. Legacy notification migration | Dry-run: two account/platform compatibility records and one ambiguous SYSTEM source preserved; no inferred UUID or auto production mutation. |
| V. Security / privacy | Owner/cross-library protections, private event isolation, fresh revocation checks and platform activity tenant-inbox exclusion verified. |
| W. Responsive | 60 phase checks plus 96 frozen product checks passed all six requested viewport sizes. |
| X. Accessibility | 156 rendered axe audits: zero violations. 100 rendered contrast measurements passed; initial dialog focus, Tab trap, Escape and focus restore verified. |
| Y. Live event scenarios | Admin and librarian draft/edit/publish; same title in separate libraries; cancellation reason/history, private patron view, Home link and global event preservation. |
| Z. Live notification scenarios | Real canonical commands and worker delivery: approval/rejection, return request/confirmation, reservation readiness, overdue fee assessment, waiver and desk payment. |
| AA. Backend tests | 1690 unique PASS, 10 existing security skips, zero failures; includes all 45 new Part 2D tests and 18 frozen suite groups. |
| AB. Frontend tests | 693 PASS, zero failures; includes 21 new Part 2D checks. |
| AC. Browser validation | Real Chromium 151.0.7922.34; 32 product navigation steps and nine TEST Staff context checks passed; no runtime page errors. |
| AD. Regression | Institution V1/2A/2B/2C, workspace/platform authority, Events V1, inbox, catalogue, Search, Reading List, Select for AI and Ask LuminaR passed. |
| AE. Build / lint | Build PASS. Lint zero errors; 14 existing warnings retained. |
| AF. TEST preservation | 150 ACTIVE records and 150 holdings; exact library/membership/book/holding/lending/cutover snapshots unchanged. Owner ADMIN and patron GENERAL_USER preserved. |
| AG. Global catalogue | 5,000,000 estimated documents, matching baseline; no complete 5M row digest was computed. |
| AH. Global HNSW / KG | All 196 accepted artifact size/mtime entries unchanged; 156 protected ranking/assistant/router source digests unchanged. No builds/rebuilds. |
| AI. Exact files changed | [institution_v2d_files_changed.json](D:/SDC/LibraryLLM/reports/institution_v2d_files_changed.json) — 48 source/test/operator files; zero deletions. Reports are separately inventoried. |
| AJ. Reports | All 21 required/baseline/audit reports present; full report/evidence inventory below. |
| AK. Known limitations | Standalone Mongo replay durability, not a cross-document transaction. Migration remains dry-run/review-only. No tenant scheduled reminders, broadcast fanout, external push/email, preferences or RSVP. Existing skips/warnings and preservation measurement limits are disclosed. |
| AL. Improvement review | [institution_v2d_improvement_review.md](D:/SDC/LibraryLLM/reports/institution_v2d_improvement_review.md) — all requested follow-up ideas reviewed without implementation. |
| AM. Recommended next phase | [institution_v2d_next_scope.md](D:/SDC/LibraryLLM/reports/institution_v2d_next_scope.md) — tenant analytics authorization audit, or a separate private-document RAG tenancy audit, only after explicit approval. |

The canonical frontend remains running at http://127.0.0.1:5173; Core, Search, Recommendation and RAG health checks returned 200. No next phase was started. Disposable QA libraries were soft-removed with data retained, normal fixture accounts disabled, and the temporary platform grant revoked (403 verified). The prior accepted platform QA grant and both human QA accounts were unchanged. No credentials were persisted.

## Required reports

- [institution_v2d_baseline.json](D:/SDC/LibraryLLM/reports/institution_v2d_baseline.json)
- [institution_v2d_events_notifications_baseline.json](D:/SDC/LibraryLLM/reports/institution_v2d_events_notifications_baseline.json)
- [institution_v2d_existing_event_audit.md](D:/SDC/LibraryLLM/reports/institution_v2d_existing_event_audit.md)
- [institution_v2d_existing_notification_audit.md](D:/SDC/LibraryLLM/reports/institution_v2d_existing_notification_audit.md)
- [institution_v2d_event_architecture.md](D:/SDC/LibraryLLM/reports/institution_v2d_event_architecture.md)
- [institution_v2d_notification_architecture.md](D:/SDC/LibraryLLM/reports/institution_v2d_notification_architecture.md)
- [institution_v2d_event_authorization.json](D:/SDC/LibraryLLM/reports/institution_v2d_event_authorization.json)
- [institution_v2d_notification_authorization.json](D:/SDC/LibraryLLM/reports/institution_v2d_notification_authorization.json)
- [institution_v2d_notification_sources.md](D:/SDC/LibraryLLM/reports/institution_v2d_notification_sources.md)
- [institution_v2d_notification_dedupe.json](D:/SDC/LibraryLLM/reports/institution_v2d_notification_dedupe.json)
- [institution_v2d_notification_outbox.md](D:/SDC/LibraryLLM/reports/institution_v2d_notification_outbox.md)
- [institution_v2d_event_migration.json](D:/SDC/LibraryLLM/reports/institution_v2d_event_migration.json)
- [institution_v2d_notification_migration.json](D:/SDC/LibraryLLM/reports/institution_v2d_notification_migration.json)
- [institution_v2d_frontend.json](D:/SDC/LibraryLLM/reports/institution_v2d_frontend.json)
- [institution_v2d_browser.json](D:/SDC/LibraryLLM/reports/institution_v2d_browser.json)
- [institution_v2d_security.json](D:/SDC/LibraryLLM/reports/institution_v2d_security.json)
- [institution_v2d_performance.json](D:/SDC/LibraryLLM/reports/institution_v2d_performance.json)
- [institution_v2d_regression.json](D:/SDC/LibraryLLM/reports/institution_v2d_regression.json)
- [institution_v2d_preservation.json](D:/SDC/LibraryLLM/reports/institution_v2d_preservation.json)
- [institution_v2d_improvement_review.md](D:/SDC/LibraryLLM/reports/institution_v2d_improvement_review.md)
- [institution_v2d_next_scope.md](D:/SDC/LibraryLLM/reports/institution_v2d_next_scope.md)

## Exact source and operator files

- [backend/main.py](D:/SDC/LibraryLLM/backend/main.py)
- [backend/routes/library_events.py](D:/SDC/LibraryLLM/backend/routes/library_events.py)
- [backend/routes/notifications.py](D:/SDC/LibraryLLM/backend/routes/notifications.py)
- [backend/schemas/events.py](D:/SDC/LibraryLLM/backend/schemas/events.py)
- [backend/schemas/notifications.py](D:/SDC/LibraryLLM/backend/schemas/notifications.py)
- [backend/services/admin_operation_service.py](D:/SDC/LibraryLLM/backend/services/admin_operation_service.py)
- [backend/services/event_service.py](D:/SDC/LibraryLLM/backend/services/event_service.py)
- [backend/services/library_event_service.py](D:/SDC/LibraryLLM/backend/services/library_event_service.py)
- [backend/services/library_lending_journal.py](D:/SDC/LibraryLLM/backend/services/library_lending_journal.py)
- [backend/services/notification_service.py](D:/SDC/LibraryLLM/backend/services/notification_service.py)
- [backend/services/tenant_notification_service.py](D:/SDC/LibraryLLM/backend/services/tenant_notification_service.py)
- [backend/services/tenant_notification_worker.py](D:/SDC/LibraryLLM/backend/services/tenant_notification_worker.py)
- [frontend/package.json](D:/SDC/LibraryLLM/frontend/package.json)
- [frontend/src/App.tsx](D:/SDC/LibraryLLM/frontend/src/App.tsx)
- [frontend/src/components/Footer.tsx](D:/SDC/LibraryLLM/frontend/src/components/Footer.tsx)
- [frontend/src/components/Header.tsx](D:/SDC/LibraryLLM/frontend/src/components/Header.tsx)
- [frontend/src/components/LibraryShells.tsx](D:/SDC/LibraryLLM/frontend/src/components/LibraryShells.tsx)
- [frontend/src/components/NotificationCenter.tsx](D:/SDC/LibraryLLM/frontend/src/components/NotificationCenter.tsx)
- [frontend/src/components/Notifications.css](D:/SDC/LibraryLLM/frontend/src/components/Notifications.css)
- [frontend/src/components/events/EventUI.tsx](D:/SDC/LibraryLLM/frontend/src/components/events/EventUI.tsx)
- [frontend/src/components/events/LibraryUpcomingEvents.tsx](D:/SDC/LibraryLLM/frontend/src/components/events/LibraryUpcomingEvents.tsx)
- [frontend/src/hooks/useProductContext.ts](D:/SDC/LibraryLLM/frontend/src/hooks/useProductContext.ts)
- [frontend/src/lib/events.ts](D:/SDC/LibraryLLM/frontend/src/lib/events.ts)
- [frontend/src/lib/notifications.ts](D:/SDC/LibraryLLM/frontend/src/lib/notifications.ts)
- [frontend/src/lib/productContext.ts](D:/SDC/LibraryLLM/frontend/src/lib/productContext.ts)
- [frontend/src/pages/EventDetailPage.tsx](D:/SDC/LibraryLLM/frontend/src/pages/EventDetailPage.tsx)
- [frontend/src/pages/EventEditorPage.tsx](D:/SDC/LibraryLLM/frontend/src/pages/EventEditorPage.tsx)
- [frontend/src/pages/Events.css](D:/SDC/LibraryLLM/frontend/src/pages/Events.css)
- [frontend/src/pages/EventsPage.tsx](D:/SDC/LibraryLLM/frontend/src/pages/EventsPage.tsx)
- [frontend/src/pages/Home.tsx](D:/SDC/LibraryLLM/frontend/src/pages/Home.tsx)
- [frontend/src/pages/ManageEventsPage.tsx](D:/SDC/LibraryLLM/frontend/src/pages/ManageEventsPage.tsx)
- [frontend/tests/admin-notifications.test.tsx](D:/SDC/LibraryLLM/frontend/tests/admin-notifications.test.tsx)
- [frontend/tests/full-product-convergence.test.tsx](D:/SDC/LibraryLLM/frontend/tests/full-product-convergence.test.tsx)
- [frontend/tests/institution-events-notifications.test.tsx](D:/SDC/LibraryLLM/frontend/tests/institution-events-notifications.test.tsx)
- [frontend/tests/library-catalogue.test.tsx](D:/SDC/LibraryLLM/frontend/tests/library-catalogue.test.tsx)
- [scripts/institution_v2d_audits.py](D:/SDC/LibraryLLM/scripts/institution_v2d_audits.py)
- [scripts/institution_v2d_baseline.py](D:/SDC/LibraryLLM/scripts/institution_v2d_baseline.py)
- [scripts/institution_v2d_browser_checks.py](D:/SDC/LibraryLLM/scripts/institution_v2d_browser_checks.py)
- [scripts/institution_v2d_browser_session.py](D:/SDC/LibraryLLM/scripts/institution_v2d_browser_session.py)
- [scripts/institution_v2d_migration.py](D:/SDC/LibraryLLM/scripts/institution_v2d_migration.py)
- [scripts/institution_v2d_regressions.py](D:/SDC/LibraryLLM/scripts/institution_v2d_regressions.py)
- [scripts/institution_v2d_reports.py](D:/SDC/LibraryLLM/scripts/institution_v2d_reports.py)
- [scripts/migrate_events_v2d.py](D:/SDC/LibraryLLM/scripts/migrate_events_v2d.py)
- [scripts/migrate_notifications_v2d.py](D:/SDC/LibraryLLM/scripts/migrate_notifications_v2d.py)
- [scripts/notification_outbox_v2d.py](D:/SDC/LibraryLLM/scripts/notification_outbox_v2d.py)
- [tests/institution_v2d/conftest.py](D:/SDC/LibraryLLM/tests/institution_v2d/conftest.py)
- [tests/institution_v2d/test_events_notifications.py](D:/SDC/LibraryLLM/tests/institution_v2d/test_events_notifications.py)
- [tests/institution_v2d/test_migration_and_recovery.py](D:/SDC/LibraryLLM/tests/institution_v2d/test_migration_and_recovery.py)
