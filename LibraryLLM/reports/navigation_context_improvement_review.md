# Navigation/context repair — PASS

A. Final PASS. All 32 acceptance gates and all 26 required named tests pass.
B. Logo root cause: Header's global-logo Link was hardwired to /; related header context used a potentially stale activeId.
C. Old behavior: Patron child → logo → global Home.
D. New behavior: /libraries/{URL UUID} and all children → logo → the same canonical library Home.
E. Global Home remains / and global data.
F. Patron links and search derive from URL, before remembered state and independent of loading order.
G. Staff logo → /; existing owner account navigates only to Staff Workspace for TEST.
H. Platform logo → /; existing PlatformRoleAssignment guard remains intact, no new grant.
I. Account discovery loss was not reproduced. Confirmed failure was the stale Core 8002 recommendations route; entry/menu refetch gaps were also corrected generically.
J. /me/libraries returns authoritative active memberships, all pages fetched, exact membership unchanged before/after.
K. Provided account: verified active user 10, GENERAL_USER membership at TEST, normal UI and direct access both pass.
L. Account fix: entry/menu refetch and wrong-session cache protection; no membership or email-specific change.
M. Member UUID destination /libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae; staff destination /staff/libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae.
N. Join, invitation acceptance, membership role/status changes await refresh; login/session and focus refresh remain. Entry/menu refetch discovers externally restored libraries.
O. All memberships render; remembered IDs cannot hide rows; pagination verified with 103 generic memberships.
P. Prior 404: POST scoped recommendations absent from running old Core 8002, while current 8088 registered it.
Q. Restarting Core with current source resolves it; both ports return 200. Proxy and canonical API unchanged.
R. TEST preserved: 150 ACTIVE books, 150 holdings, four local-only books, LIBRARY_LOCAL, Home links all canonical local IDs.
S. Global preserved: 5,000,000 records, 146 full sampled documents unchanged, 173 protected global source files unchanged, 196 index artifact size/mtime records unchanged. HNSW/KG not rebuilt.
T. Backend: 1671 passed, 10 established skips, 18 isolated groups; Part 2B/C and authority regression groups pass.
U. Frontend: 619 passed, including 31 navigation/context tests. All 26 prompt-required names verified across backend/frontend.
V. Browser: provided account normal login; account/menu/direct access, Home/My Library/Reservations/Fees/logo, Browse/New Arrivals, global root, 5173/5182, owner Staff and denied Platform access pass.
W. Build PASS; lint zero errors, 19 pre-existing warnings. An existing lazy document-answer test intermittently exceeded its default DOM deadline; its test now awaits the same exact answer with a bounded 10-second deadline. The complete final frontend run passes; 96 affected tests, build and lint passed again after effect dependency cleanup. No assistant product behavior changed.
X. Exact phase source changes (see navigation_context_changed_files.json):
- MODIFIED: frontend/package.json
- MODIFIED: frontend/src/components/AccountMenu.tsx
- MODIFIED: frontend/src/components/Header.tsx
- MODIFIED: frontend/src/lib/libraryWorkspace.ts
- MODIFIED: frontend/src/pages/AccountPages.tsx
- MODIFIED: frontend/tests/knowledge-artifacts.test.tsx
- ADDED: frontend/tests/navigation-context.test.tsx
- ADDED: scripts/navigation_context_live.py
- ADDED: scripts/report_navigation_context.py
- ADDED: scripts/test_navigation_context_frontend.py
- ADDED: scripts/test_navigation_context_regressions.py
- ADDED: tests/institution_v1/test_navigation_context.py
Y. Required reports: navigation_context_baseline.json; navigation_logo_routing.md; account_library_access_audit.md; account_membership_navigation.json; library_route_404_investigation.md; navigation_context_browser.json; navigation_context_regression.json; navigation_context_improvement_review.md. Additional QA summary, preservation, changed-files, live response, route baseline, logs, XML and screenshots provide evidence. All 4281 prior report files remain byte-identical.
Z. Limits: preservation does not claim full hashing of 5M documents or multi-gigabyte artifacts. Supplied missing-membership history could not be reproduced; findings report that honestly. No real multi-library membership was granted to the provided account; generic disposable DB and frontend fixtures cover switching/pagination. Normal Core runs without reload and requires a restart after backend route additions. No Events/Notifications/Analytics tenancy, tenant indexing or next phase begun.

```text
KARTHIKEYA_NORMAL_UI_LIBRARY_ACCESS: YES
KARTHIKEYA_DIRECT_URL_ACCESS: YES
BOTH_ACCESS_PATHS_EQUIVALENT: YES
TEST_VISIBLE_IN_ACCOUNT_PAGE: YES
ROOT_HOME_REMAINS_GLOBAL: YES
TEST_HOME_REMAINS_LOCAL: YES
TEST_ACCOUNT_PAGE_DESTINATION: /libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae
LUMINAR_LOGO_FROM_TEST_HOME: /libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae
LUMINAR_LOGO_FROM_TEST_MY_LIBRARY: /libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae
LUMINAR_LOGO_FROM_TEST_RESERVATIONS: /libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae
LUMINAR_LOGO_FROM_TEST_FEES: /libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae
HARDCODED_5173_OR_5182_NAVIGATION: NO
PRIOR_404_REPRODUCIBLE: NO
PRIOR_404_ROOT_CAUSE: Reproduced before repair: POST scoped catalogue/recommendations on stale Core 8002 returned 404. Current runtime returns 200 after restart.
GLOBAL_BOOK_COUNT: 5000000
GLOBAL_HNSW_REBUILT: NO
GLOBAL_KG_REBUILT: NO
TEST_LOCAL_BOOK_COUNT: 150
```

Improvement review: one shared URL resolver keeps the brand, browsing, arrivals and search in agreement. Membership authority remains entirely server-side. Fresh discovery on account entry avoids confusing stale navigation while preserving every authorized membership. A future development-only Core reload command could reduce stale-route incidents; no launcher policy change or extra phase was made here.
