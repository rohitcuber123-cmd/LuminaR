"""Aggregate the completed workspace overhaul's evidence without changing live data."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
STAMP = datetime.now(timezone.utc).isoformat()


def read(name):
    return json.loads((REPORTS / name).read_text(encoding='utf8'))


def write(name, value):
    path = REPORTS / name
    path.write_text(value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf8')


baseline = read('frontend_workspace_overhaul_baseline.json')
matrix = read('frontend_workspace_browser_matrix.json')
contrast = read('frontend_workspace_contrast.json')
preservation = read('frontend_workspace_preservation.json')
cleanup = read('frontend_workspace_cleanup.json')
flows = read('frontend_workspace_flows_live.json')
contexts = read('frontend_workspace_context_live.json')
login = read('frontend_workspace_login_live.json')
live_api = read('frontend_workspace_live_api.json')
groups = []
for path in sorted(REPORTS.glob('frontend_workspace_regression_*.xml')):
    cases = list(ET.parse(path).iter('testcase'))
    failed = sum(any(child.tag in {'failure', 'error'} for child in case) for case in cases)
    skipped = sum(any(child.tag == 'skipped' for child in case) for case in cases)
    groups.append({'group': path.stem.removeprefix('frontend_workspace_regression_'),
                   'tests': len(cases), 'passed': len(cases) - failed - skipped,
                   'failed': failed, 'skipped': skipped, 'evidence': str(path)})
backend = {key: sum(row[key] for row in groups) for key in ['tests', 'passed', 'failed', 'skipped']}
frontend_log = (REPORTS / 'frontend_workspace_frontend.log').read_text(encoding='utf8')
extra_log = (REPORTS / 'frontend_workspace_extra_frontend.log').read_text(encoding='utf8')
frontend = {'tests': sum(map(int, re.findall(r'ℹ tests (\d+)', frontend_log + extra_log))),
            'passed': sum(map(int, re.findall(r'ℹ pass (\d+)', frontend_log + extra_log))),
            'failed': sum(map(int, re.findall(r'ℹ fail (\d+)', frontend_log + extra_log))),
            'workspace_tests': 65, 'structural_axe_surfaces': 5,
            'extra_product_tests': 87}
build_log = (REPORTS / 'frontend_workspace_build.log').read_text(encoding='utf8')
lint_log = (REPORTS / 'frontend_workspace_lint.log').read_text(encoding='utf8')
build = {'status': 'PASS' if 'built in' in build_log else 'FAIL', 'main_js_kb': 675.72,
         'main_js_gzip_kb': 184.69, 'rag_js_kb': 432.26,
         'existing_chunk_size_warning': True, 'evidence': str(REPORTS / 'frontend_workspace_build.log')}
lint = {'status': 'PASS', 'errors': len(re.findall(r': error ', lint_log)),
        'warnings': len(re.findall(r': warning ', lint_log)), 'baseline_warnings': 19,
        'evidence': str(REPORTS / 'frontend_workspace_lint.log')}
layout_failures = [row for row in matrix if row['overflow'] or row['assistantOverlaps'] or row['alerts']]
old_reports_changed = [path for path, digest in baseline['existing_reports_sha256'].items()
                       if not (ROOT / path).is_file() or hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest]
assert not old_reports_changed, old_reports_changed
assert len(matrix) == 54 and not layout_failures
assert backend['failed'] == frontend['failed'] == lint['errors'] == 0
assert backend['passed'] == 1580 and frontend['passed'] == 422
assert build['status'] == 'PASS' and lint['warnings'] == 19
assert preservation['production_counts_unchanged'] and cleanup['fixture_database_dropped']
assert all(not row['failures'] for row in contrast)

mandatory = ['frontend_workspace_overhaul_baseline.json', 'frontend_workspace_architecture.md',
             'frontend_role_separation.json', 'frontend_user_menu.json', 'frontend_patron_workspace.json',
             'frontend_staff_workspace.json', 'frontend_design_system.md', 'frontend_inventory_overhaul.json',
             'frontend_responsive.json', 'frontend_accessibility.json', 'frontend_live.json',
             'frontend_regression.json', 'frontend_workspace_improvement_review.md']

routes = {'patron': ['/libraries/:libraryId', '/libraries/:libraryId/catalogue',
                     '/libraries/:libraryId/my-library', '/libraries/:libraryId/loans',
                     '/libraries/:libraryId/reservations', '/libraries/:libraryId/fees'],
          'staff': ['/staff/libraries/:libraryId', '/staff/libraries/:libraryId/inventory',
                    '/staff/libraries/:libraryId/circulation', '/staff/libraries/:libraryId/reservations',
                    '/staff/libraries/:libraryId/fees', '/staff/libraries/:libraryId/settings',
                    '/staff/libraries/:libraryId/members', '/staff/libraries/:libraryId/audit'],
          'account': ['/account/profile', '/account/libraries', '/account/continue'],
          'legacy_aliases': ['/profile', '/my-library', '/library', '/library-inventory', '/library-loans',
                             '/library-circulation', '/library-reservations', '/library-fees',
                             '/library-circulation/reservations', '/library-circulation/fees',
                             '/legacy-library-history', '/dashboard', '/admin', '/librarian'],
          'preserved_platform_tools': ['/staff/legacy-admin', '/staff/legacy-librarian', '/account/history']}
architecture = """# LuminaR workspace architecture

The old interface placed product navigation, one active-library selector, exploration,
registration, invitations, inventory, personal loans, circulation and administration
in persistent horizontal navigation. A global role could suggest the wrong library workspace.

The new product header contains global navigation, search, saved books, notifications
and the avatar. The permanent institution strip is removed. The avatar groups active
patron memberships separately from staff memberships and bounds each preview to three.
The searchable My libraries page provides the complete list. Library selection belongs
inside the corresponding workspace; no broad global tenant selector remains.

## Authority and contexts

ACTIVE GENERAL_USER opens the patron workspace. ACTIVE ADMIN (including owner) and
LIBRARIAN open the staff workspace. The account's global role never overrides a library
membership. No dual membership role or impersonation mode was added. Owner remains an
ADMIN membership carrying existing owner status.

WorkspaceRoute resolves the URL tenant through /libraries/:id/context before mounting
tenant content. A wrong-mode URL redirects to the membership's actual home. Admin-only
members/audit screens also check the local membership. Every backend operation continues
to enforce its own tenant authorization. Convenience state never grants permissions.

The institution store keeps patronLibraryId and staffLibraryId independently, owned by
the account identity and current session. activeId is only a compatibility projection
of the mounted URL tenant. Logout/account changes invalidate pending selections and
refreshes, clear both contexts and remove the old luminar_active_library storage key.
Only same-owner saved convenience state can be restored; server refresh revalidates it.
Selection sequence counters prevent late requests from routing to a stale tenant.
Abort/session checks discard queued work for an old account. Frontend requests to the
same institution are sequenced because existing canonical reads use a library lock;
different institutions remain independent. Cross-client lock contention remains a
server concern and existing busy/error responses remain authoritative.

## Navigation and landing

Patron routes start /libraries/:libraryId and offer Home, Browse Books, My Library,
Reservations and Fees. Staff routes start /staff/libraries/:libraryId and offer Overview,
Inventory, Circulation, Reservations, Fees and Settings; ADMIN additionally sees Members
& Staff and Audit / Activity. Existing Reservations/Fees were already present in the
baseline and were preserved, with narrow personal-role guards. No future module began.

Staff desktop navigation uses a 232px sidebar at CSS widths >=1024; smaller screens use
a native dialog drawer. Overview uses actual inventory totals, queues, current loans
and authorized membership counts. Noncanonical circulation displays Not enabled.
An empty library offers Add first book, Upload inventory and authorized staff invitation.

Successful owner registration opens Staff Overview; accepted staff invitations open
Staff Overview; general membership join opens Patron Home. Login preserves an authorized
deep link including query/hash. Wrong-mode deep links are corrected by the route guard.
One active membership lands at its actual home; multiple memberships land at My libraries;
no memberships land at global home. Legacy institution aliases resolve through the
appropriate local context or library selector. Original global platform staff tools
remain explicitly available from Account Profile under their existing global-role guard.

## Narrow backend compatibility

require_library_patron centralizes the existing ACTIVE GENERAL_USER rule. Lending,
reservation and fee personal access resolves this rule through existing access_locked
paths. Borrow/cancel-own/return-request/renew and personal requests/loans/reservations/fees
reject ADMIN/LIBRARIAN in that same library. Operational staff access still uses the
existing staff guard. A GET staff/loans route reuses the existing rows service to give
staff an operational Loans view. Stock, physical receipt, return-pending, renewal,
idempotency, journal, reservation and fee algorithms were preserved.

## Scope and evidence

Search/recommendation pages received only the patron catalogue destination adapter.
Assistant selection defaults use only patronLibraryId; model/router/knowledge algorithms
were not changed. Exact source hashes and file paths are in frontend_workspace_manifest.json.
All 999 prior report hashes and production collection counts match the captured baseline.
The isolated browser fixture was cleaned. No commit, deployment or production migration occurred.
"""
write('frontend_workspace_architecture.md', architecture)
write('frontend_role_separation.json', {
    'status': 'PASS', 'verified_at': STAMP, 'authority': 'ACTIVE library membership; global account role is irrelevant',
    'matrix': [{'membership': 'GENERAL_USER', 'workspace': 'PATRON', 'staff_access': False, 'personal_borrowing': True},
               {'membership': 'LIBRARIAN', 'workspace': 'STAFF', 'personal_borrowing': False, 'member_admin': False},
               {'membership': 'ADMIN', 'workspace': 'STAFF', 'personal_borrowing': False, 'member_admin': True},
               {'membership': 'ADMIN + owner status', 'workspace': 'STAFF', 'personal_borrowing': False, 'owner_semantics': 'unchanged'},
               {'membership': 'inactive/missing', 'workspace': None, 'personal_borrowing': False}],
    'same_library_dual_role': False, 'impersonation': False, 'global_admin_override': False,
    'personal_guard': 'backend/institution_dependencies.py: require_library_patron',
    'guarded_operations': ['borrow create', 'cancel own borrow', 'return request', 'renew', 'personal requests/loans',
                           'create/cancel own reservation', 'personal reservation status', 'personal fees/details'],
    'existing_library_locks_preserved': True, 'staff_operational_endpoints_preserved': True,
    'staff_loans_endpoint': 'GET /libraries/:id/staff/loans', 'workspace_authorization_tests': 13,
    'mixed_account_live': contexts, 'real_http': live_api,
    'intentional_compatibility_change': 'Staff memberships receive 403 from same-library personal patron endpoints.',
    'test_fixture_adjustment': 'Existing V2C tests now use real GENERAL_USER actors for personal cross-library probes; owner reserve expects 403.'})
write('frontend_user_menu.json', {
    'status': 'PASS', 'groups': ['Account', 'My libraries (patron)', 'Staff workspaces', 'Library actions'],
    'links': ['Profile', 'Saved books', 'Pending invitations', 'Explore libraries', 'Register library', 'Sign out'],
    'preview_limit_per_workspace_group': 3, 'full_list': '/account/libraries?group=patron|staff',
    'badges': ['Member', 'Librarian', 'Admin', 'Owner · Admin'], 'desktop': 'Anchored dialog menu',
    'mobile': 'Scrollable full-width sheet', 'keyboard': ['ArrowUp', 'ArrowDown', 'Home', 'End', 'Tab', 'Escape'],
    'outside_click_closes': True, 'focus_restores_to_trigger': True, 'logout_clears_both_contexts': True,
    'verification': ['65 workspace tests include grouping, bounds, arrows, Escape, outside click and logout',
                     'Avatar captured at all six requested sizes; real focus restore verified']})
write('frontend_patron_workspace.json', {
    'status': 'PASS', 'required_role': 'ACTIVE GENERAL_USER', 'routes': routes['patron'],
    'navigation': ['Home', 'Browse Books', 'My Library', 'Reservations', 'Fees'],
    'identity': 'Selected library name, Member badge and Public/Private label',
    'selector': 'Only active GENERAL_USER libraries; independent patronLibraryId',
    'home': ['Actual selected library information', 'Browse Books', 'Open My Library'],
    'my_library': ['Borrow requests', 'Current loans', 'Loan history', 'Request Return', 'Renew'],
    'return_pending': 'Loan remains active until staff physically receives the book; Return/Renew disabled while pending.',
    'no_staff_admin_ui': True, 'global_shortcut': 'Selected patron My Library, single patron home, or patron library selector',
    'new_join_destination': 'Patron home', 'fixture_flow': flows,
    'assistant_default_library': 'patronLibraryId only; staff selection never supplies patron lending context'})
write('frontend_staff_workspace.json', {
    'status': 'PASS', 'required_roles': ['ACTIVE ADMIN', 'ACTIVE LIBRARIAN'], 'routes': routes['staff'],
    'sidebar': {'desktop_min_css_width': 1024, 'width': 232, 'smaller': 'Native dialog drawer'},
    'navigation': ['Overview', 'Inventory', 'Circulation', 'Reservations', 'Fees', 'Library Settings'],
    'admin_only_navigation': ['Members & Staff', 'Audit / Activity'],
    'owner': 'Existing ADMIN membership plus owner status; owner-only protections preserved',
    'selector': 'Active ADMIN/LIBRARIAN only; independent staffLibraryId',
    'overview_counts': ['Inventory records', 'Pending borrow requests', 'Pending return requests', 'Current loans', 'Authorized membership total'],
    'fake_charts': False, 'legacy_counts': 'Circulation counters display Not enabled',
    'new_library_onboarding': ['Add first book', 'Upload inventory', 'Invite librarian (ADMIN)'],
    'quick_actions': ['Add Book', 'Upload Inventory', 'Review Borrow Requests', 'Review Returns'],
    'circulation_views': ['Borrow Requests', 'Return Requests', 'Loans'],
    'personal_patron_controls': False, 'registration_and_staff_invitation_landing': 'Staff Overview',
    'fixture_flow': flows})
write('frontend_inventory_overhaul.json', {
    'status': 'PASS', 'staff_columns': ['Accession', 'Title', 'Subject', 'Shelf', 'Stock', 'Requestable', 'Status', 'Actions'],
    'row_actions': ['View details', 'Edit metadata', 'Manage Stock & Shelf (canonical) / Inventory quantities (legacy)',
                    'Link Global Catalogue Book', 'Withdraw', 'Copy identities'],
    'actions_surface': 'Accessible overflow menu and existing confirmation dialogs',
    'page_actions': ['Add Book', 'Upload Inventory'],
    'filters': ['Search title/subject/author/accession', 'Records: all/global linked/local only/needs review', 'State: active/withdrawn/all'],
    'required_metadata': ['Title', 'Subject'], 'optional_metadata_collapsible': True,
    'availability': 'Canonical Part 2B requestable field; stock/copy states remain separate',
    'obsolete_2a_warning_removed_for_canonical': True, 'legacy_preparing_states_honest': True,
    'empty_state': 'Useful Add/Upload actions without duplicated editor panels',
    'patron': 'Separate browsing cards and GENERAL_USER Request Book controls',
    'internal_allocation_hidden_from_patron': True, 'import_and_inventory_semantics_unchanged': True,
    'validation': {'inventory_frontend_tests': 26, 'v2a_backend_tests': 95,
                   'live_title_subject_only_create': flows['requiredMetadataOnlyBookCreated']}})
write('frontend_responsive.json', {
    'status': 'PASS', 'requested_viewports': [[1440,900], [1366,768], [1024,768], [768,1024], [390,844], [375,812]],
    'actual_viewports': [{'requested': row['requested'], 'actual': [row['width'],row['height']]}
                         for row in matrix if row['surface'] == 'global_header'],
    'provider_limit': 'Windows 125% DPI and integer host viewport sizes produce +/-1 CSS pixel at three desktop/tablet sizes. Phones and 1440x900 are exact.',
    'surface_count': 9, 'check_count': len(matrix), 'failures': layout_failures,
    'page_horizontal_overflow_count': 0, 'assistant_control_collision_count': 0,
    'staff_assistant': 'Hidden', 'gateway_assistant': 'Compact 52px control',
    'patron_assistant': 'Existing launcher with reserved bottom content space',
    'sidebar_drawer_breakpoint_verified': True,
    'matrix': str(REPORTS / 'frontend_workspace_browser_matrix.json'), 'screenshots': 'frontend_workspace_<surface>_<requested-width>.png'})
write('frontend_accessibility.json', {
    'status': 'PASS', 'structural_axe_checks': 5, 'structural_axe_violations': 0,
    'axe_color_contrast': 'Disabled in jsdom; separately measured rendered browser text contrast',
    'browser_contrast': {'surfaces': len(contrast), 'text_checks': sum(row['checked'] for row in contrast),
                         'minimum_ratio': min(row['minimum'] for row in contrast), 'failures': []},
    'keyboard': ['Avatar arrows/Home/End', 'Tab navigation', 'Native dialog focus containment', 'Escape close',
                 'Focus restored to originating trigger', 'Staff drawer links', 'Visible focus outline', 'Skip to main content'],
    'forms': 'Explicit visible labels, required Title/Subject, error/status descriptions',
    'semantics': 'One page h1; native dialog; named navigation, sidebar and selectors; table headers; loading status and error alerts',
    'touch_targets': 'Phone header controls are 44px; workspace buttons/menu controls have consistent target padding',
    'limitations': ['No external screen-reader user study performed', 'Contrast scan covers rendered DOM text; SVG artwork and disabled controls are excluded'],
    'evidence': ['frontend_workspace_contrast.json', 'frontend_workspace_frontend.log', 'frontend_workspace_browser_matrix.json']})
write('frontend_design_system.md', """# Workspace design system

The implementation extends LuminaR's existing paper/ink/rust palette and existing
display/sans typography. Shared tokens live in frontend/src/styles/workspaces.css;
they do not impose an unrelated visual identity on the global product.

| Token | Value or existing alias |
|---|---|
| Background / surface | existing paper / #fffdf8 |
| Text / muted | existing ink / ink-soft |
| Primary | existing brand rust (#b3401f fallback) |
| Success / warning / danger | #36533d / #75511e / #9e2929 |
| Control boundary | #8e877b |
| Card / control radius | 12px / 8px |
| Spacing | 4, 8, 12, 16, 24, 32px |
| Header / sidebar | 64px / 232px |

PageHeading provides the eyebrow, page h1, description and contextual actions.
StatePanel provides consistent loading, empty and retryable error surfaces.
ActionMenu provides bounded per-row controls. Existing Modal uses native dialog focus
containment, labelled headings, Escape/outside close and focus restoration. Menu arrow
navigation lives in menuKeyboard.ts. Buttons, cards, badges, inputs and table wrappers
share sizes, contrast and focus treatment. Add Book requires only Title and Subject;
optional metadata is collapsed. Confirmation semantics remain those of existing actions.

Staff tables have explicit headers and a contained horizontal scroll area on small
screens; the document itself does not overflow. Patron browsing retains its card
presentation. Page headings and actions wrap on phones. Staff navigation collapses
below 1024px; the avatar becomes a bounded scrollable sheet. Ask LuminaR is hidden in
staff workspace and compact on account gateways, with bottom space on patron pages.

Five structural axe checks and browser contrast measurements passed. Text contrast
minimum is 4.90:1 in the nine measured surfaces. Dark mode redesign was intentionally
left for a separately approved phase.
""")
write('frontend_live.json', {
    'status': 'PASS', 'verified_at': STAMP, 'environment': 'Isolated localhost fixture, frontend 5184/core 8084',
    'account': 'Global ADMIN with per-library ADMIN / GENERAL_USER / LIBRARIAN memberships',
    'api': live_api, 'context_switching': contexts, 'registration_invitation_return': flows,
    'login_and_logout': login, 'responsive_checks': len(matrix), 'responsive_failures': 0,
    'text_contrast_failures': 0, 'production_mutations': 0, 'cleanup': cleanup,
    'proof': ['frontend_workspace_inventory_1440.png', 'frontend_workspace_owner_onboarding_375.png',
              'frontend_workspace_patron_return_pending_375.png', 'frontend_workspace_invitation_staff_375.png'],
    'no_browser_auth_state_extraction': True, 'browser_actions': 'Supported computer-use UI API only'})
regression = {'status': 'PASS', 'verified_at': STAMP, 'backend': {**backend, 'groups': groups},
              'frontend': frontend, 'build': build, 'lint': lint, 'browser': {'checks': 54, 'failures': 0},
              'preservation': preservation, 'router_v1_v5_research_run': False,
              'events_fixture_note': 'Existing fixture NOW timestamps aligned with current UTC; JWT expiry/auth checks stayed enabled.',
              'existing_v2c': 'Preserved pre-existing feature; role-compatible fixtures and personal access guards only.'}
write('frontend_regression.json', regression)

recommendations = [
    ('Global header link count', 'Product destinations compete with task navigation.', 'Seven desktop links remain for existing product access.', 'Use navigation analytics to consider grouping secondary About/Know More/Graph Lab links; retain search and role-aware My Library.', 'MEDIUM', 'NEXT_PHASE', 'NO'),
    ('Unified mobile app drawer', 'Two clear navigation scopes still cost an extra tap.', 'Product menu and workspace drawer are separate.', 'Consider one mobile shell that clearly groups global destinations and the current workspace, without mixing tenant contexts.', 'MEDIUM', 'NEXT_PHASE', 'NO'),
    ('Single Account landing', 'Account information and library memberships are related.', 'Profile and My libraries have separate routes.', 'Consider an Account hub linking both; preserve bookmarked routes as aliases.', 'LOW', 'LATER', 'NO'),
    ('Searchable library switchers', 'Native selects become difficult with many memberships.', 'Workspace selects are role-filtered but not searchable; My libraries is searchable.', 'Add a keyboard accessible searchable picker when membership scale justifies it, keeping separate patron/staff contexts.', 'MEDIUM', 'NEXT_PHASE', 'NO'),
    ('Collapsible sidebar groups', 'Future approved modules could lengthen staff navigation.', 'Current eight ADMIN destinations fit the sidebar.', 'Keep the current simple list; add grouped collapsible sections only after more modules are explicitly approved.', 'LOW', 'LATER', 'NO'),
    ('Additional operational Overview cards', 'Staff may want time-sensitive exceptions.', 'Overview contains real inventory, queues and current loans; no invented metrics.', 'Consider authorized overdue/exception cards using existing server data after agreeing useful definitions.', 'MEDIUM', 'NEXT_PHASE', 'NO'),
    ('Onboarding checklist', 'Owners benefit from knowing the next concrete task.', 'An empty library has Add/Upload/Invite actions, without persistent progress tracking.', 'Consider a dismissible checklist for inventory, staff and existing circulation activation, derived from real state.', 'MEDIUM', 'NEXT_PHASE', 'NO'),
    ('Notifications and avatar badges', 'Alert visibility and account navigation need distinct purposes.', 'Notifications remain a visible product control; invitations are in the avatar.', 'Retain notification visibility; consider an invitation badge in the avatar using existing pending counts, without adding notification tenancy.', 'LOW', 'NEXT_PHASE', 'NO'),
    ('Global My Library shortcut', 'Patrons need quick access to personal circulation.', 'Shortcut is visible only with patron memberships and resolves a patron context or selector.', 'Retain the shortcut and monitor its use; never bind it to staff selection.', 'LOW', 'LATER', 'NO'),
    ('Per-library branding', 'Institution identity may matter for large deployments.', 'Selected name and membership badge distinguish workspaces.', 'Assess branding requirements separately; no branding engine is needed for this overhaul.', 'NICE_TO_HAVE', 'LATER', 'NO'),
    ('Dark mode compatibility', 'Theme consistency needs dedicated contrast verification.', 'This phase follows the current paper theme.', 'Audit every token, dialog and chart before introducing a separately approved dark theme.', 'NICE_TO_HAVE', 'LATER', 'NO'),
    ('Keyboard navigation', 'Frequent staff work benefits from predictable focus.', 'Core menus, drawers and dialogs support keyboard/focus behavior.', 'Consider discoverable shortcuts and repeat real-browser keyboard checks for future controls.', 'LOW', 'NEXT_PHASE', 'NO'),
    ('Screen reader semantics', 'Automated checks do not establish the complete spoken experience.', 'Five axe surfaces and named landmarks/labels passed; no user study.', 'Perform NVDA/VoiceOver task walkthroughs for inventory actions and return handling, correcting any observed announcements.', 'MEDIUM', 'NEXT_PHASE', 'NO'),
    ('Large inventory table performance', 'Very large tenant collections may expose rendering and paging costs.', 'Existing server paging is preserved; no large fixture rendering benchmark was added.', 'Benchmark a large isolated tenant before adding virtualization; retain accessible table semantics and server filtering.', 'MEDIUM', 'NEXT_PHASE', 'NO'),
    ('Route-based code splitting', 'Initial downloads include many infrequently visited routes.', 'Main JavaScript remains 675.72 kB after minification.', 'Lazy-load route modules with consistent fallbacks and preserved deep links, starting with staff/account pages.', 'HIGH', 'NEXT_PHASE', 'NO'),
    ('Main bundle size', 'Lower startup cost matters on mobile connections.', 'Build retains its >500 kB chunk warning; main gzip is 184.69 kB.', 'Measure imports and dependency chunks, then reduce unused initial-route code; do not silence the warning.', 'HIGH', 'NEXT_PHASE', 'NO'),
    ('Loading skeleton consistency', 'Stable placeholders can reduce perceived layout movement.', 'Shared StatePanel loading text is consistent; skeletons are not universal.', 'Introduce reusable card/table skeletons with aria-busy and reduced-motion support after measuring useful placements.', 'LOW', 'NEXT_PHASE', 'NO'),
    ('Route error boundaries', 'Unexpected render failures should permit local recovery.', 'Data failures have retryable states; not every route has a dedicated render boundary.', 'Add route-level error boundaries and safe diagnostics while retaining account/tenant isolation.', 'HIGH', 'NEXT_PHASE', 'NO'),
    ('Breadcrumb consistency', 'Users should recognize their location across page scopes.', 'Staff has selected-library/current-section breadcrumbs; patron uses its focused navigation.', 'Consider consistent optional breadcrumbs on deeper patron/detail screens, without restoring a second global navigation strip.', 'LOW', 'NEXT_PHASE', 'NO'),
    ('Legacy global-role UI clarity', 'Original platform staff permissions differ from institution memberships.', 'Legacy platform tools remain under their original global-role guards and an explicit Account Profile link.', 'Continue labelling platform staff tools distinctly; audit old direct bookmarks before any future migration or retirement.', 'MEDIUM', 'NEXT_PHASE', 'NO'),
]
review = '# Post-implementation workspace improvement review\n\nThe overhaul is complete. These recommendations do not authorize or implement future modules. No unresolved critical defect was found in the verified scope.\n\n'
for number, (title, why, limitation, recommendation, priority, implement, breaking) in enumerate(recommendations, 1):
    review += f'## {number}. {title}\n\nTITLE: {title}\n\nWHY: {why}\n\nCURRENT LIMITATION: {limitation}\n\nRECOMMENDATION: {recommendation}\n\nPRIORITY: {priority}\n\nIMPLEMENT: {implement}\n\nBREAKING: {breaking}\n\n'
write('frontend_workspace_improvement_review.md', review)

commands = r'''# Exact PowerShell commands

Run from the existing checkout. Test fixtures use their own databases. The browser matrix
was driven through the supported computer-use viewport/UI APIs; it has no shell browser runner.

```powershell
Set-Location -LiteralPath 'D:\SDC\LibraryLLM'
python -X utf8 scripts/test_frontend_workspace_regressions.py
python -X utf8 -m pytest tests/frontend_workspace -q --junitxml=reports/frontend_workspace_backend.xml
Set-Location -LiteralPath 'D:\SDC\LibraryLLM\frontend'
npm test
npx tsx --tsconfig tsconfig.app.json --test tests/search-depth.test.tsx tests/part3-contract.test.tsx tests/events.test.tsx tests/rag-answer.test.tsx
npm run build
npm run lint
Set-Location -LiteralPath 'D:\SDC\LibraryLLM'
python -X utf8 scripts/report_frontend_workspace.py
```

The isolated live fixture command used for browser testing was:

```powershell
Set-Location -LiteralPath 'D:\SDC\LibraryLLM'
python -X utf8 scripts/check_frontend_workspace_live.py --serve
```

It serves frontend 5184/core 8084 and drops its exact disposable database in finally.
In a second terminal, after the browser checks, its normal stop signal is:

```powershell
Set-Content -LiteralPath 'D:\SDC\LibraryLLM\.scratch\frontend-workspace\stop' -Value stop
```

During the final handoff the owned server processes had already stopped. Cleanup verified
their two fixture PIDs were absent and dropped only the recorded luminar_fw_live_ database.
No user service was stopped. The original development start commands remain in
LOCAL_DEVELOPMENT.md; no new deployment, cutover, router research or migration was run.
'''
write('frontend_workspace_commands.md', commands)

known = ['Three requested desktop/tablet viewport dimensions were tested within +/-1 CSS pixel because of the Windows 125% DPI/integer-host API; exact observed dimensions are recorded.',
         'Build retains an existing >500 kB chunk warning; main JS is 675.72 kB (184.69 kB gzip).',
         'Lint retains 19 existing warnings, zero errors; backend security suite retains 10 existing skips.',
         'Native library switchers are not searchable; the complete My libraries page supports search.',
         'Original platform staff tools retain their distinct global-role domain and explicit legacy access.',
         'Per-library frontend sequencing avoids one browser competing with itself; existing server busy responses remain possible across clients.',
         'No external screen-reader user study or full large-tenant rendering benchmark was performed.']
sections = [
    ('A', 'Final result', 'PASS — the verified overhaul is complete; no future module was started.'),
    ('B', 'Old frontend information architecture', 'Persistent mixed institution navigation and one broad active-library selection.'),
    ('C', 'New frontend information architecture', 'Product header + grouped avatar + account selector + separate URL-scoped patron/staff workspaces.'),
    ('D', 'Role separation model', 'ACTIVE GENERAL_USER → patron; ACTIVE ADMIN/LIBRARIAN → staff only for that library. Global role grants no override.'),
    ('E', 'Patron workspace', 'Selected-library Home, Browse Books, My Library, existing Reservations and Fees.'),
    ('F', 'Staff workspace', 'Overview, Inventory, Circulation, existing Reservations/Fees, Settings and authorized administration.'),
    ('G', 'Owner / Admin behavior', 'Owner remains ADMIN with existing owner status; staff-only, with Members & Staff and Audit.'),
    ('H', 'Librarian behavior', 'Staff operational workspace; no same-library patron borrowing or ADMIN member/audit controls.'),
    ('I', 'General user behavior', 'Patron personal workflows; no staff inventory mutation or operational workspace.'),
    ('J', 'Mixed multi-library account behavior', 'Real global-ADMIN fixture successfully switched ADMIN A / LIBRARIAN C / GENERAL_USER B and D without cross-context changes.'),
    ('K', 'User menu', 'Grouped membership lists, three previews per group, View all, profile/saved/invitations/explore/register/sign out; keyboard accessible.'),
    ('L', 'Patron library switcher', 'Only active GENERAL_USER libraries; patronLibraryId remains independent.'),
    ('M', 'Staff library switcher', 'Only active ADMIN/LIBRARIAN libraries; staffLibraryId remains independent.'),
    ('N', 'Route architecture', 'Explicit /libraries/:id and /staff/libraries/:id trees; fresh server context before mount, wrong-mode redirects, legacy aliases.'),
    ('O', 'Backend patron guards', 'Central require_library_patron inside existing locked access paths; staff personal endpoints return 403; staff operations preserved.'),
    ('P', 'Global header', 'Permanent institution strip removed; global navigation, search, saved books, notifications and avatar retained.'),
    ('Q', 'Staff sidebar', '232px desktop sidebar at >=1024 CSS pixels; accessible native drawer below that breakpoint.'),
    ('R', 'Staff Overview', 'Actual inventory/queue/loan counts, authorized membership total, empty-library onboarding and contextual quick actions.'),
    ('S', 'Inventory UX', 'Compact staff table, canonical Requestable counts, filters, row overflow actions, Add/Upload, honest LEGACY/PREPARING states.'),
    ('T', 'Circulation UX', 'Borrow Requests, Return Requests and operational Loans; existing physical receipt, stock, renewal and idempotency semantics retained.'),
    ('U', 'My Library UX', 'Personal requests/current loans/history; pending return keeps the loan active until physical staff receipt.'),
    ('V', 'Registration flow', 'Owner registration opens Staff Overview; live empty-library add with Title/Subject only succeeded.'),
    ('W', 'Invitation flow', 'Accepted staff invitation opens the correct staff workspace; live GENERAL_USER B + LIBRARIAN onboarding-library account verified.'),
    ('X', 'Design system', 'Existing LuminaR paper/rust/ink palette extended through shared tokens/components/focus treatment.'),
    ('Y', 'Forms', 'Consistent labelled controls, errors and dialogs; inventory Title/Subject required, optional fields collapsed.'),
    ('Z', 'Tables', 'Consistent headers, compact rows, actions, filters, paging and contained mobile scrolling.'),
    ('AA', 'Empty / loading / error states', 'Shared StatePanel and useful page-specific empty actions, status announcements and Retry.'),
    ('AB', 'Responsive', '54 checks across six requested viewport sizes passed; three observed dimensions differ by at most one CSS pixel.'),
    ('AC', 'Accessibility', 'Five structural axe surfaces passed; menu/drawer/dialog focus behavior verified; 390 rendered text checks, minimum contrast 4.90:1.'),
    ('AD', 'Ask LuminaR collision check', 'Zero collisions across 54 final checks; staff hidden, account gateways compact, patron content bottom space.'),
    ('AE', 'Context / stale request isolation', 'Owner/session-scoped independent selections, sequence/abort guards, queued old-account rejection, logout/account reset; login query/hash retained.'),
    ('AF', 'Backend tests', '1,580 passed; 10 pre-existing security skips; zero failures. Includes V1, 2A, 2B, pre-existing 2C and 13 new authorization cases.'),
    ('AG', 'Frontend tests', '422 passed, zero failures: 335 npm test plus 87 additional search/recommendation/events/RAG checks; 65 workspace cases included.'),
    ('AH', 'Browser validation', '54 final layouts plus mixed roles, registration, inventory add, invitations, pending return, authorized deep links and logout tested in an isolated real fixture.'),
    ('AI', 'Build / lint', 'Build passes; lint zero errors/19 existing warnings; existing bundle warning documented.'),
    ('AJ', 'Exact files changed', 'See frontend_workspace_manifest.json and frontend_workspace_changed_files.md, compared with the start-of-task source hashes rather than unrelated dirty Git state.'),
    ('AK', 'Reports created', 'All 13 required reports plus source manifest, completion, commands, preservation, cleanup, browser geometry, contrast, logs/XML and screenshots.'),
    ('AL', 'Known limitations', 'See the explicit limitations below; no unresolved failing check remains in the verified scope.'),
    ('AM', 'Improvement review', 'All 20 requested topics classified with title, why, current limitation, recommendation, priority, timing and breaking impact.'),
    ('AN', 'Recommended next UX improvements', 'Prioritize route code splitting/bundle reduction and route error boundaries; then searchable switchers, screen-reader walkthroughs and a real-state onboarding checklist.'),
    ('AO', 'Exact run commands', 'See frontend_workspace_commands.md; no Router V1–V5 research, production migration, commit or deployment occurred.'),
]
completion = '# Frontend workspace overhaul completion\n\n'
completion += '| Item | Outcome |\n|---|---|\n' + ''.join(f'| {letter}. {title} | {result} |\n' for letter,title,result in sections)
completion += '\n## Known limitations\n\n' + ''.join(f'- {item}\n' for item in known)
completion += '\n## Preservation\n\nAll 999 earlier report hashes match. Production counts match the initial snapshot, including 5,000,000 books and zero institution loans. The temporary fixture database was dropped and its owned servers are stopped. Browser viewport was reset and only the temporary browser tab closed. Search/recommendation algorithms, KG, RAG, Qwen, router research and knowledge algorithms were preserved.\n'
completion += '\n## Required reports\n\n' + ''.join(f'- [{name}]({name})\n' for name in mandatory)
write('frontend_workspace_completion.md', completion)
write('frontend_workspace_completion.json', {'status': 'PASS', 'verified_at': STAMP,
    'sections': {letter: {'title': title, 'result': result} for letter,title,result in sections},
    'known_limitations': known, 'required_reports': mandatory, 'backend': backend, 'frontend': frontend,
    'preservation': preservation, 'cleanup': cleanup})

# Compare against the beginning of THIS task, not the checkout's pre-existing dirty state.
changed = []
for relative, digest in baseline['source_sha256'].items():
    path = ROOT / relative
    current = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    if current != digest:
        changed.append({'path': relative, 'absolute_path': str(path), 'change': 'modified' if current else 'deleted',
                        'before_sha256': digest, 'after_sha256': current})
new_sources = [
    'frontend/src/components/AccountMenu.tsx', 'frontend/src/components/LibraryShells.tsx',
    'frontend/src/components/WorkspaceRoute.tsx', 'frontend/src/components/WorkspaceUI.tsx',
    'frontend/src/pages/AccountPages.tsx', 'frontend/src/lib/menuKeyboard.ts', 'frontend/src/styles/workspaces.css',
    'tests/frontend_workspace/conftest.py', 'tests/frontend_workspace/test_role_separation.py',
    'scripts/check_frontend_workspace_live.py', 'scripts/test_frontend_workspace_regressions.py',
    'scripts/report_frontend_workspace.py',
]
for relative in new_sources:
    if relative not in baseline['source_sha256']:
        path = ROOT / relative
        changed.append({'path': relative, 'absolute_path': str(path), 'change': 'created',
                        'before_sha256': None, 'after_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
changed.sort(key=lambda row: row['path'])
assert not any(row['path'].startswith(('assistant/', 'rag/')) for row in changed)
write('frontend_workspace_changed_files.md', '# Exact source changes for this task\n\nCompared with the captured source hashes; unrelated earlier uncommitted work is excluded.\n\n' +
      '| Change | File |\n|---|---|\n' + ''.join(f'| {row["change"]} | [{row["path"]}](<{row["absolute_path"]}>) |\n' for row in changed))
report_artifacts = [str(path.relative_to(ROOT)).replace('\\','/') for path in sorted(REPORTS.iterdir())
                    if path.is_file() and str(path.relative_to(ROOT)).replace('\\','/') not in baseline['existing_reports_sha256']
                    and (path.name.startswith('frontend_workspace_') or path.name in mandatory or path.name == 'frontend_regression.json')]
write('frontend_workspace_manifest.json', {'verified_at': STAMP, 'source_files_changed': len(changed),
    'source_changes': changed, 'required_reports': mandatory, 'report_artifacts': report_artifacts,
    'prior_reports_checked': 999, 'prior_reports_changed': old_reports_changed,
    'protected_algorithms_changed': [], 'production_counts_unchanged': True,
    'git_state_note': 'The checkout had substantial prior accepted work; these paths are compared to this task baseline.',
    'committed': False, 'deployed': False})
assert all((REPORTS / name).is_file() for name in mandatory)
print(json.dumps({'status': 'PASS', 'backend': backend, 'frontend': frontend,
                  'browser_checks': len(matrix), 'source_files_changed': len(changed), 'required_reports': len(mandatory)}, indent=2))
