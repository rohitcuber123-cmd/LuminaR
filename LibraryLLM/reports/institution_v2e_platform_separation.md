# Institution Part 2E: Platform and tenant analytics separation

Status: source audit complete. This report describes the authority boundary and convergence decisions; execution results belong to the phase security, browser and regression reports.

The accepted boundary remains explicit. Platform Console authority comes from a current, approved `PlatformRoleAssignment`. Staff Analytics authority comes from a current, active `LibraryMembership` for the canonical library UUID. Legacy `User.role` grants neither authority. An account with both grants uses each independently.

## Audited surfaces and decisions

| Surface / metric | Classification | Authority and canonical source | Part 2E decision |
| --- | --- | --- | --- |
| Platform Overview: account count | PLATFORM_GLOBAL | `/platform/summary`; explicit platform guard; installation `users` collection. | Retain the installation count. Do not use it as a library membership total. |
| Platform Overview: catalogue count | PLATFORM_GLOBAL | `/platform/summary`; global `books.estimated_document_count()`. | Retain the approximate global catalogue count. It never supplies a tenant collection card. |
| Platform Overview: global event count | PLATFORM_GLOBAL | Shared `event_service.scope_match()` restricts the Events collection to explicit/compatible global scope. | Retain; canonical LIBRARY events are excluded. |
| Approved platform-role count returned by summary | PLATFORM_GLOBAL | Installation `platform_role_assignments` with active PLATFORM_ADMIN status; endpoint remains explicitly platform guarded. | Retain existing metadata. Fresh access decisions use the stricter approval/expiry guard, not this count. |
| Platform Libraries directory total and lifecycle filters | PLATFORM_GLOBAL | `/platform/libraries`; accepted directory query over canonical libraries, bounded to 50 rows. | Retain discovery and lifecycle administration; no detailed tenant activity aggregation added. |
| Platform Library detail: active general-member, staff and local-book counts | LIBRARY_TENANT, narrow accepted platform metadata exception | `platform_library_service.safe_summary()` uses the exact library UUID and ACTIVE status. Owner summary and cutover state are already accepted directory metadata. | Retain these existing safe counts. They do not authorize Staff Analytics, member histories, fee balances, loan titles or tenant mutations. |
| Platform Library detail: lifecycle audit summary | PLATFORM_GLOBAL | `/platform/libraries/{UUID}/audit`; COMMITTED platform lifecycle audit, bounded to 50 rows. | Retain actor/reason/state transitions. Do not substitute tenant business audits. |
| Platform Accounts and platform announcement delivery totals | PLATFORM_GLOBAL | Explicit platform guard; canonical account directory and platform notification sources. | Retain the accepted management surfaces. |
| Platform System health and retrieval/worker diagnostics | OPERATIONAL_HEALTH | Installation/operator health, kept separate from tenant business performance. | Retain existing health surfaces; no private library content or member behavioral profile is exposed. |
| Staff Overview current operational counts | LIBRARY_TENANT | Existing bounded canonical inventory/lending/membership APIs, guarded by the exact current membership. | Retain the accepted operational Overview. These are business-service counts, not an independent historical analytics authority. |
| Staff Analytics collection, circulation, reservation, fee and event aggregates | LIBRARY_TENANT | One read-only `/libraries/{UUID}/analytics` resource, exact UUID predicates and lookups, current ADMIN/LIBRARIAN membership plus centralized lifecycle/recovery policy. | Centralize additional analytical aggregates here. No PlatformRoleAssignment fallback. |
| Staff Analytics role breakdown, waived/settled amounts and delivery health | LIBRARY_TENANT / OPERATIONAL_HEALTH | Same tenant resource; ADMIN-only capabilities. LIBRARIAN receives operational aggregates with sensitive sections omitted/null. | Keep role/capability decisions explicit in both server payload and frontend presentation. No recipient notification content is included. |
| Own reading history, Reading List, AI selections and account inbox | PERSONAL_USER | Current account ownership and existing personal authorization; notice actions additionally check source-library membership. | Exclude from Staff Analytics and platform fleet metrics. |
| Platform Historical Records and legacy global issues/reservations/fines/activity | LEGACY_AMBIGUOUS | Accepted read-only compatibility sources with no canonical tenant attribution. Existing Platform account activity explicitly excludes LIBRARY notices. | Preserve historical compatibility only. Never combine these rows with Part 2B/C tenant aggregates or guess a library from a work ID. |
| Legacy Admin/Librarian/Staff dashboard URLs | OBSOLETE | Accepted compatibility redirects; independent old dashboards are retired. | Keep redirects. Part 2E adds no replacement mixed-role dashboard. |
| Legacy role/membership review counts | UNKNOWN_REVIEW_REQUIRED | Explicit Platform authority review, historical role metadata and count of current memberships. | Report for operator review. No automatic platform or tenant grant. |

## Request and payload boundary

`GET /libraries/{UUID}/analytics` is the sole new analytics API. The route parses a canonical UUID and bounds the range to `7d`, `30d`, `90d` or `all`. The service checks current eligible identity, exact current membership and ACTIVE library before aggregation, and revalidates authority/lifecycle before returning. A retained update/recovery gate fails closed. GENERAL_USER, revoked membership, unrelated library membership and Platform Admin without a separate membership are denied.

Every aggregation root, correlated lookup and union branch binds `library_id`. The response contains scalars and bounded subject/book/trend lists, not member, loan or fee records. No platform endpoint calls the new tenant analytics service. No new fleet-wide sum of private tenant loans, fees, reading activity, documents or notifications is introduced.

The frontend route is `/staff/libraries/:libraryId/analytics` inside the accepted Staff shell and membership guard. Patron and Platform shells contain no Staff Analytics navigation granted by their respective roles. A dual-authority account can enter the Staff route only through its independently authorized library membership.

## Convergence proof and limits

The full prechange inventory classifies 272 actual metrics across 68 families in 231 metric-bearing source/test/script files. Existing Platform counts retain their installation or narrow directory purpose. Canonical tenant analytics excludes legacy compatibility collections and the global 5M catalogue. Existing Home popularity remains its accepted product-ranking implementation; Staff Analytics reuses the canonical book-level signals for an explicitly selected range without changing Home ranking.

There is one new historical tenant analytics service and one Staff route. Existing operational counters remain with their canonical business APIs; no second mutable stock, lending, reservation, fee, event or notification system was added. Legacy source ambiguity and older compatibility performance limits remain explicitly documented rather than silently treated as tenant analytics.

Relevant evidence:

- [Full existing analytics audit](D:/SDC/LibraryLLM/reports/institution_v2e_existing_analytics_audit.md)
- [Metric inventory](D:/SDC/LibraryLLM/reports/institution_v2e_metric_inventory.json)
- [Analytics architecture](D:/SDC/LibraryLLM/reports/institution_v2e_analytics_architecture.md)
- [Platform guards](D:/SDC/LibraryLLM/backend/platform_dependencies.py)
- [Platform directory/detail service](D:/SDC/LibraryLLM/backend/services/platform_library_service.py)
- [Platform summary](D:/SDC/LibraryLLM/backend/routes/notifications.py:83)
- [Tenant analytics service](D:/SDC/LibraryLLM/backend/services/library_analytics_service.py)
- [Tenant analytics tests](D:/SDC/LibraryLLM/tests/institution_v2e/test_analytics.py)

