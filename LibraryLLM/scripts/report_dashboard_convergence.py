"""Generate convergence evidence without changing product data or earlier reports."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
BASE = json.loads((REPORTS / 'dashboard_convergence_baseline.json').read_text(encoding='utf8'))


def read(name):
    return json.loads((REPORTS / name).read_text(encoding='utf-8-sig'))


def write(name, value):
    target = REPORTS / name
    assert str(target.relative_to(ROOT)) not in BASE['prior_reports_sha256'], 'Earlier evidence must stay frozen.'
    target.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# Each row describes an actual repository feature, rather than a proposed future module.
# Route paths use {library_id} to emphasize that the selected canonical UUID is required.
FEATURES = [
    ('StaffDashboard.tsx: AdminDashboard /admin', 'Mixed global/tenant dashboard shell', 'OBSOLETE', 'PlatformShell or StaffLibraryShell after authority resolution', False, True, True, 'One transition period for bookmarks; no old UI'),
    ('StaffDashboard.tsx: LibrarianDashboard /librarian', 'Independent librarian shell', 'OBSOLETE', '/staff/libraries/{library_id} or staff selector', False, True, True, 'Exactly one staff membership or selector; no inferred library'),
    ('StaffDashboard.tsx: LegacyStaffDashboard /staff', 'Independent staff shell', 'OBSOLETE', '/staff/libraries/{library_id} or staff selector', False, True, True, 'Exactly one staff membership or selector; otherwise deny'),
    ('StaffDashboard.tsx + lib/nav.ts', 'Admin/Librarian navigation, role-based login destinations', 'OBSOLETE', 'Account menu and membership-based account landing', False, True, False, 'None'),
    ('StaffDashboard.tsx: Admin summary', 'Global accounts/catalogue summary', 'PLATFORM_GLOBAL', '/platform: PlatformOverview', True, True, True, 'Old /admin entry only redirects'),
    ('StaffDashboard.tsx: Admin summary', 'Mixed tenant stock/loans/fees metrics', 'LIBRARY_TENANT', '/staff/libraries/{library_id}: StaffOverviewPage', True, True, True, 'Old dashboard entry only redirects'),
    ('StaffForms.tsx: BookManagement', 'Global book metadata create/edit/delete', 'PLATFORM_GLOBAL', '/platform/catalogue: PlatformCatalogue; /books metadata API', True, True, True, 'Old dashboard entry only redirects'),
    ('StaffForms.tsx + book_service.py', 'Physical copy counts and shelf on global book editor', 'LIBRARY_TENANT', 'Canonical Staff Inventory stock/copy/shelf commands', True, True, False, 'Global metadata mutation rejects physical stock fields'),
    ('StaffForms.tsx: InventoryManagement', 'Library inventory CRUD', 'LIBRARY_TENANT', '/staff/libraries/{library_id}/inventory', True, True, False, 'Legacy mutation endpoints return 410'),
    ('StaffForms.tsx: DatasetImport', 'Local physical inventory CSV preview/confirm', 'LIBRARY_TENANT', 'Canonical Staff Inventory import preview/confirm', True, True, False, 'Legacy import endpoints return 410'),
    ('StaffDashboard.tsx: Issues', 'Loan directory and issuance/approval', 'LIBRARY_TENANT', '/staff/libraries/{library_id}/circulation', True, True, False, 'Legacy issue writer returns 410'),
    ('AdminOperations.tsx + issue_service.py', 'Staff-assisted physical return', 'LIBRARY_TENANT', 'Canonical staff receive command and lending journal', True, True, True, '/admin API redirects to /platform; retired return target returns 410'),
    ('LoanRenewalControl.tsx + loan_renewal_service.py', 'Staff-assisted renewal', 'LIBRARY_TENANT', 'Canonical staff loan renewal; shared renewal policy and journal', True, True, True, 'Old /admin API redirect has a retired 410 target'),
    ('StaffDashboard.tsx: Reservations', 'Tenant reservation queue', 'LIBRARY_TENANT', '/staff/libraries/{library_id}/reservations', True, True, False, 'Legacy reservation writer returns 410'),
    ('StaffDashboard.tsx: Fines', 'Tenant fee ledger and settlement', 'LIBRARY_TENANT', '/staff/libraries/{library_id}/fees', True, True, False, 'Legacy fee writer returns 410'),
    ('StaffDashboard.tsx: InstitutionPanel', 'Library members, local staff invitations and role changes', 'LIBRARY_TENANT', '/staff/libraries/{library_id}/members (local ADMIN)', True, True, True, 'Old dashboard entry only redirects; shared scoped panel remains canonical'),
    ('StaffDashboard.tsx: InstitutionPanel', 'Local library settings and policies', 'LIBRARY_TENANT', '/staff/libraries/{library_id}/settings', True, True, True, 'Old dashboard entry only redirects; shared scoped panel remains canonical'),
    ('StaffDashboard.tsx: InstitutionPanel', 'Membership/security audit', 'LIBRARY_TENANT', '/staff/libraries/{library_id}/audit (local ADMIN)', True, True, True, 'Old dashboard entry only redirects'),
    ('StaffDashboard.tsx: Activity', 'Librarian operational activity', 'LIBRARY_TENANT', '/staff/libraries/{library_id}/activity: LibraryActivityPage', True, True, False, 'Canonical scoped read-only audit projection, excluding membership/security admin events'),
    ('StaffManagement.tsx + staff_service.py', 'Installation-wide account directory and provisioning', 'PLATFORM_GLOBAL', '/platform/accounts: identity CRUD and verification', True, True, False, 'Old /staff API retired; new accounts have GENERAL_USER identity only'),
    ('StaffManagement.tsx + staff_service.py', 'Setting global ADMIN/LIBRARIAN as management authority', 'OBSOLETE', 'Independently reviewed PlatformRoleAssignment or local invitations/migration', False, True, False, 'No role editor and no automatic privilege grants'),
    ('AdminOperations.tsx', 'Global notification recipient search/compose/history', 'PLATFORM_GLOBAL', '/platform/notifications: PlatformNotifications and NotificationComposer', True, True, True, '/admin notification API is a guarded 307 redirect only'),
    ('AdminOperations.tsx', 'Read-only historical operations and account inspection', 'PLATFORM_GLOBAL', '/platform/history: LegacyOperationHistory', True, True, True, '/admin history API is a guarded 307 redirect only'),
    ('ManageEventsPage.tsx /staff/events', 'Global event lifecycle and publication', 'PLATFORM_GLOBAL', '/platform/events: existing event editor and management', True, True, True, 'Old frontend event links redirect; API authority now explicit platform assignment'),
    ('StaffSetupPage.tsx /staff/setup', 'Personal email verification/password setup', 'PERSONAL', '/account/setup: AccountSetupPage', True, True, True, 'Old credential setup bookmark redirects, granting no authority'),
    ('ProfilePage.tsx: legacy loan controls', 'Own borrowing/return/renewal', 'PERSONAL', '/libraries/{library_id}/my-library with GENERAL_USER membership', True, True, False, 'Old issue/renew writers return 410; personal history stays read-only'),
    ('ProfilePage.tsx: legacy reservation controls', 'Own reservation create/cancel', 'PERSONAL', '/libraries/{library_id}/reservations', True, True, False, 'Legacy reservation mutations return 410'),
    ('ProfilePage.tsx: legacy fine controls', 'Own fee settlement', 'PERSONAL', '/libraries/{library_id}/fees', True, True, False, 'Legacy payment writer returns 410'),
    ('ProfilePage.tsx + /issues/my /reservations/my /fines/my /activity/my', 'Own legacy historical records', 'PERSONAL', '/account/history (read-only)', True, False, False, 'No redirect; authenticated owner-only historical projection is retained'),
    ('issue/reservation/fine/activity GET APIs', 'Legacy installation history', 'PLATFORM_GLOBAL', 'Platform Historical Records, read-only compatibility APIs', True, False, False, 'No redirect; explicit platform assignment or owner-only detail, no stock writes'),
    ('inventory_service.py GET /inventory', 'Read legacy inventory with explicit library mapping', 'LIBRARY_TENANT', 'Read-only compatibility: selected UUID/approved alias + active LibraryMembership', True, False, False, 'No redirect; unresolved aliases fail closed and CRUD/import always 410'),
    ('issue_service.py reservation_service.py fine_service.py', 'Duplicate legacy circulation writers', 'OBSOLETE', 'Canonical library lending/reservations/fees services only', False, True, False, 'Only read projections and 410 retirement stubs remain'),
    ('inventory_import_service.py inventory_service.py', 'Duplicate legacy inventory/import writers', 'OBSOLETE', 'Canonical institution inventory/import services only', False, True, False, 'Import parsing/write implementation removed; retirement stubs return 410'),
    ('AdminPlaceholder.tsx', 'Unused future-dashboard placeholder', 'OBSOLETE', 'Removed', False, True, False, 'No legitimate caller remains'),
    ('backend/scripts/bootstrap_admin.py', 'Legacy ADMIN role bootstrap', 'OBSOLETE', 'Retired CLI; scripts/migrate_management_authority.py with reviewed mapping', False, True, False, 'Role labels are not management authority'),
    ('backend/scripts/reset_admin_password.py', 'Offline operator personal credential recovery for legacy-labeled accounts', 'PERSONAL', 'Explicit offline credential recovery compatibility only', False, False, False, 'Not a dashboard/API; does not insert any membership or assignment and was not executed'),
    ('backend/scripts/migrate_users.py', 'SQL identity import retaining historical role metadata', 'PERSONAL', 'Offline identity migration compatibility only', False, False, False, 'No authority creation; not executed in this phase'),
    ('users user_id=2, legacy LIBRARIAN', 'Unapproved legacy account scope', 'UNKNOWN_REVIEW_REQUIRED', 'Authority review report; manual approved library mapping required', False, False, False, 'Account retained; no membership inferred and no deletion'),
    ('users user_id=3, legacy ADMIN', 'Unapproved legacy account scope', 'UNKNOWN_REVIEW_REQUIRED', 'Authority review report; platform/local scope needs independent justification', False, False, False, 'Account retained; no platform promotion and no deletion'),
]
FIELDS = ['OLD COMPONENT / ROUTE', 'OLD FUNCTION', 'CLASSIFICATION', 'NEW DESTINATION', 'MIGRATED',
          'OLD IMPLEMENTATION REMOVED', 'REDIRECT REMAINING', 'WHY REDIRECT REMAINS', 'BACKEND AUTHORITY REPLACED']
ROWS = [dict(zip(FIELDS, [*row[:4], *['YES' if v else 'NO' for v in row[4:7]], row[7], 'YES'])) for row in FEATURES]

ROLE_FILES = {
    'scripts/migrate_management_authority.py': 'Offline manual legacy-account review query. Grant role fields identify independently approved membership/assignment models; no User.role inference.',
    'backend/services/identity_service.py': 'Legacy identity schema, supported label validation and public identity serialization; never a grant.',
    'backend/services/auth_service.py': 'Personal sign-in/signup/setup identity metadata. New identities use GENERAL_USER; no management grant.',
    'backend/routes/auth.py': 'JWT identity metadata; staff sign-in eligibility uses a LibraryMembership query or explicit platform assignment, not User.role.',
    'backend/utils/jwt_utils.py': 'Historical JWT role claim and conservative shorter lifetime for legacy labels. Claims cannot authorize management.',
    'backend/dependencies.py': 'Deprecated require_roles always denies. There are no product callers.',
    'backend/routes/models/user.py': 'Historical SQL identity schema default; no tenant/platform authority.',
    'backend/routes/platform.py': 'Legacy-account classification query/display for manual review. Assignment lookup is separate.',
    'backend/services/platform_account_service.py': 'Account directory metadata and GENERAL_USER-only identity creation. No role-edit fields or privilege creation.',
    'backend/services/notification_service.py': 'Legacy identity label projection for recipient/actor presentation; no role-based authorization.',
    'backend/services/admin_operation_service.py': 'Legacy read-only operation/actor projection, not a management permission.',
    'backend/scripts/bootstrap_admin.py': 'Retired role bootstrap with no account or authority creation.',
    'backend/scripts/reset_admin_password.py': 'Offline personal credential recovery selector for legacy labels. Not run; creates no management grants.',
    'backend/scripts/migrate_users.py': 'Offline SQL identity metadata import only. Not run; no membership/assignment provision.',
    'frontend/src/store/useAuthStore.ts': 'Identity type/session supported-label validation only. Workspace and console permissions come from separate fresh server stores.',
    'frontend/src/components/ProtectedRoute.tsx': 'UserRole is a type alias for the same literal values; runtime role comes from activeLibrary.membership, not identity.',
    'frontend/src/components/BookCapabilities.tsx': 'Unrelated legacy digital read UI helper input, with backend document capability checks; no institution authority.',
    'frontend/src/lib/readNow.ts': 'Personal historical digital-reading UI compatibility predicate; no lending/inventory writes and no library grant.',
    'frontend/src/lib/nav.ts': 'Deprecated role-named helper returns only My Libraries for any identity; no role-specific dashboard navigation.',
    'frontend/src/lib/authDestination.ts': 'Deprecated role argument is ignored; membership-based account landing chooses context.',
    'frontend/src/pages/PlatformAccounts.tsx': 'Explicitly marked legacy label display in migrated account directory; no authority editor.',
    'frontend/src/pages/PlatformOperations.tsx': 'Historical account label display in migrated read-only inspection; no authority or lending mutation.',
}

GATES = {
    52: ('Legacy Librarian is not an independent surface', 'Deleted StaffDashboard.tsx; App mounts ManagementRedirect only.'),
    53: ('Legacy Staff is not an independent surface', 'Deleted LegacyStaffDashboard with the old shell; canonical StaffLibraryShell remains.'),
    54: ('Old Librarian navigation removed', 'nav.ts/AccountMenu use membership destinations; browser oldNav arrays are empty.'),
    55: ('Old Staff navigation removed', 'App and shared CSS no longer mount the old staff shell or tabs.'),
    56: ('/librarian cannot render old dashboard', 'ManagementRedirect; real-browser single/multiple/no-membership cases.'),
    57: ('/staff cannot render old dashboard', 'ManagementRedirect; real-browser single/multiple/no-membership cases.'),
    58: ('Valid Librarian functionality in Staff Workspace', 'Inventory, circulation, reservations, fees, settings and scoped operational activity; canonical suites and browser activity proof.'),
    59: ('User.role=LIBRARIAN grants no institution authority', 'Fresh identity + active scoped membership guard; legacy-labeled account without membership denied.'),
    60: ('Old Admin no longer mixed global/library dashboard', 'Deleted AdminDashboard; global PlatformShell and scoped StaffLibraryShell are separate.'),
    61: ('Every old Admin feature classified', 'Complete feature table below and machine-readable classification.json; no unknown feature deleted.'),
    62: ('Valid tenant Admin features moved to Staff Workspace', 'Inventory/import, lending, reservations, fees, members, invitations, settings and audit use canonical library routes.'),
    63: ('Valid platform-global Admin features moved to Platform Console', 'Catalogue metadata, accounts, global notifications/history/events, health and authority review.'),
    64: ('Obsolete duplicate Admin features removed', 'Old dashboard/forms/account service removed; duplicate circulation/import writers reduced to read-only/stubs.'),
    65: ('No unexplained old Admin feature', 'Feature table distinguishes retained personal/offline/history compatibility and unapproved accounts.'),
    66: ('Old tenant mutations do not use global Admin role', 'All legacy stock/circulation writers return 410. Canonical writers use LibraryMembership.'),
    67: ('New library Admin operations require LibraryMembership', 'institution_dependencies + canonical services; GENERAL_USER identity with local ADMIN works, global ADMIN without membership fails.'),
    68: ('New platform operations require PlatformRoleAssignment', 'require_platform_admin checks current identity and approved active unexpired assignment on every request.'),
    69: ('Legacy Admin not automatically Platform Admin', 'Production dry run creates zero assignments; role-only HTTP tests denied.'),
    70: ('Legacy Librarian not automatically given membership', 'Production dry run creates zero memberships; no-library browser account denied.'),
    71: ('Ambiguous legacy accounts reported', 'user_id 2 and 3 UNKNOWN_REVIEW_REQUIRED, retained, no inferred scope.'),
    72: ('Old dashboard compatibility URLs redirects only', 'Authorized contexts redirect; unsupported context denies. No old UI component exists behind any compatibility URL.'),
    73: ('Multiple memberships never select first library', 'ManagementRedirect counts active staff memberships and sends >1 to selector, even with remembered Library A.'),
    74: ('Duplicate business logic removed or read-only compatibility', 'Explicit writer retirement, removed old algorithms, retained own/global historical reads only.'),
    75: ('Old/new inventory cannot both mutate stock', 'Legacy CRUD/import 410; global metadata rejects stock/shelf and does not rewrite physical counts.'),
    76: ('Old/new lending cannot both mutate canonical lending', 'Legacy issue/return/renew 410; staff/patron commands share canonical lock, journal and policy.'),
    77: ('Old/new reservations cannot both mutate reservations', 'Legacy create/cancel 410; canonical membership-scoped reservations service remains.'),
    78: ('Old/new fees cannot both mutate fees', 'Legacy creation/payment writer removed/410; canonical membership-scoped fees service remains.'),
    79: ('Platform Console cannot mutate library internals without membership', 'Platform-only fixture receives 404 on library staff endpoints; account API forbids grant fields; tenant commands require local membership.'),
    80: ('Complete legacy_dashboard_removal.md', 'This report includes classification, exact removal, routes, authority, migration, verification, preservation and remaining compatibility.'),
}


def main():
    changed_reports = [p for p, sha in BASE['prior_reports_sha256'].items() if not (ROOT / p).exists() or digest(ROOT / p) != sha]
    changed_source = [p for p, sha in BASE['source_sha256'].items() if (ROOT / p).exists() and digest(ROOT / p) != sha]
    removed_source = [p for p in BASE['source_sha256'] if not (ROOT / p).exists()]
    protected_roots = ('assistant/', 'chatbot/', 'search/', 'recommendation/', 'rag/', 'knowledge_graph/', 'data_pipeline/', 'training/', 'evaluation/', 'benchmarks/')
    protected = {p: sha for p, sha in BASE['source_sha256'].items() if p.startswith(protected_roots)}
    changed_protected = [p for p, sha in protected.items() if not (ROOT / p).exists() or digest(ROOT / p) != sha]
    # Direct Mongo reads avoid importing an application module with index/setup side effects.
    from dotenv import load_dotenv
    from pymongo import MongoClient
    import os
    load_dotenv(ROOT / '.env')
    mongo = MongoClient(os.getenv('MONGO_URI'), serverSelectionTimeoutMS=5000)
    database = mongo['luminar_library']
    actual_counts = {name: database[name].estimated_document_count() if name == 'books' else database[name].count_documents({}) for name in BASE['production_counts']}
    assert actual_counts == BASE['production_counts'], 'Production counts changed; review before declaring convergence.'
    assert not changed_reports and not changed_protected
    cleanup = read('dashboard_convergence_cleanup.json')
    first_cleanup = read('dashboard_convergence_cleanup_first_fixture.json')
    assert all(c['fixture_database_dropped'] and c['own_services_stopped'] and not c['production_modified'] for c in [cleanup, first_cleanup])
    assert cleanup.get('browser_temporary_tab_closed') and cleanup.get('browser_viewport_reset')
    owned_prefixes = ['luminar_dc_live_', 'luminar_dashboard_test_']
    owned_databases_remaining = [n for n in mongo.list_database_names() if any(n.startswith(p) for p in owned_prefixes)]
    assert not owned_databases_remaining, 'Owned convergence test database remains; inspect before declaring cleanup.'
    mongo.close()
    write('dashboard_convergence_preservation.json', {'status': 'PASS', 'prior_reports_checked': len(BASE['prior_reports_sha256']),
        'prior_reports_changed': changed_reports, 'protected_source_files_checked': len(protected), 'protected_source_changed': changed_protected,
        'source_changed_this_phase': changed_source, 'source_removed_this_phase': removed_source,
        'production_counts_before': BASE['production_counts'], 'production_counts_after': actual_counts,
        'production_document_mutations': 0, 'owned_databases_remaining': owned_databases_remaining,
        'limits': 'Count equality is not a full content hash of five million catalogue documents. No production document mutation or live service restart was performed in this phase.'})
    write('dashboard_convergence_classification.json', ROWS)
    product_paths = [ROOT / p for p in subprocess.check_output(['rg', '--files', 'backend', 'frontend/src'], cwd=ROOT, text=True, encoding='utf8').splitlines() if Path(p).suffix in {'.py', '.ts', '.tsx'}]
    old_symbols = ['StaffDashboard', 'StaffForms', 'StaffManagement', 'AdminOperations', 'AdminPlaceholder', 'StaffSetupPage', 'LoanRenewalControl', 'services.staff_service']
    callers = [{'path': str(p.relative_to(ROOT)).replace('\\', '/'), 'symbol': symbol} for p in product_paths for symbol in old_symbols if symbol in p.read_text(encoding='utf8')]
    assert not callers, callers
    role_audit = []
    for path, explanation in ROLE_FILES.items():
        rows = [{'line': i, 'source': line.strip()} for i, line in enumerate((ROOT / path).read_text(encoding='utf8').splitlines(), 1) if re.search(r'\b(role|ROLES|STAFF_ROLES|READER_ROLE|ADMIN_ROLE|UserRole)\b', line) and not re.search(r'role=["\'](?:alert|status|menu|dialog)', line)]
        role_audit.append({'file': path, 'remaining_usages': rows, 'reason': explanation, 'management_authority': False})
    retired = {}
    for path in ['backend/services/issue_service.py', 'backend/services/reservation_service.py', 'backend/services/fine_service.py', 'backend/services/inventory_service.py', 'backend/services/inventory_import_service.py', 'backend/services/loan_renewal_service.py']:
        tree = ast.parse((ROOT / path).read_text(encoding='utf8'))
        retired[path] = [{'function': n.name, 'line': n.lineno} for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == 'retirement' for c in ast.walk(n))]
    require_callers = []
    for p in product_paths:
        if p.suffix == '.py' and p.name != 'dependencies.py':
            tree = ast.parse(p.read_text(encoding='utf8'))
            for n in ast.walk(tree):
                if isinstance(n, ast.Name) and n.id == 'require_roles': require_callers.append({'path': str(p.relative_to(ROOT)), 'line': n.lineno})
    assert not require_callers
    write('dashboard_convergence_source_audit.json', {'status': 'PASS', 'old_product_callers': callers, 'require_roles_product_callers': require_callers,
        'legacy_role_usages': role_audit, 'retired_writer_stubs': retired,
        'scope_notes': ['Canonical membership.role and PlatformRoleAssignment.role are separate authority models, not User.role.',
            'HTML accessibility role attributes and chat message user/assistant roles are unrelated.',
            'Historical report generator scripts may mention deleted filenames as frozen audit evidence; they are not product callers.',
            'Shared StaffUI tables/dialogs and scoped InstitutionPanel remain legitimate canonical components; old shells/navigation are removed.']})
    groups = read('dashboard_convergence_regression.json')
    assert all(g['exit'] == 0 and g['failed'] == 0 for g in groups)
    backend_pass = sum(g['tests'] - g['skipped'] for g in groups)
    backend_skip = sum(g['skipped'] for g in groups)
    authority = list(ET.parse(REPORTS / 'dashboard_convergence_authority_final.xml').iter('testcase'))
    assert len(authority) == 38 and not any(any(c.tag in {'failure', 'error'} for c in t) for t in authority)
    frontend_logs = ['dashboard_convergence_frontend_final.log', 'dashboard_convergence_frontend_extra_final.log']
    frontend = []
    unique_names = set()
    for name in frontend_logs:
        content = (REPORTS / name).read_text(encoding='utf8')
        passed = sum(map(int, re.findall(r'ℹ pass (\d+)', content)))
        failures = sum(map(int, re.findall(r'ℹ fail (\d+)', content)))
        assert passed > 0 and failures == 0, name
        unique_names.update(re.findall(r'^✔ (.+?) \([\d.]+ms\)', content, re.M))
        frontend.append({'log': name, 'passed': passed, 'failed': failures})
    build = (REPORTS / 'dashboard_convergence_build.log').read_text(encoding='utf8')
    lint = (REPORTS / 'dashboard_convergence_lint.log').read_text(encoding='utf8')
    assert 'built in' in build and not re.search(r'error TS\d+', build)
    assert ': error ' not in lint
    matrix = read('dashboard_convergence_browser_matrix.json')
    assert len(matrix) == 42 and all(not r['oldNav'] and r['scroll'] <= r['width'] for r in matrix)
    flows = read('dashboard_convergence_browser_flows.json')
    write('dashboard_convergence_validation.json', {'status': 'PASS', 'backend': {'passed': backend_pass, 'skipped': backend_skip, 'failed': 0, 'groups': groups,
        'method': 'Frozen product suite groups in separate processes; counts use the existing grouped-report convention, not a unique-test census.',
        'latest_authority_tests': len(authority), 'post_removal_checks': 52}, 'frontend': {'runs': frontend, 'passed': sum(r['passed'] for r in frontend),
        'distinct_passed_test_names': len(unique_names), 'failed': 0}, 'build': 'PASS', 'lint': {'exit': 0, 'warnings': len(re.findall(r': warning ', lint)), 'errors': 0},
        'build_chunk_warning': 'Existing large frontend bundle warning remains; main bundle approximately 671 KB.',
        'browser': {'platform_responsive_checks': len(matrix), 'flows': len(flows), 'horizontal_document_overflows': 0,
            'viewport_requests': [1440, 1366, 1024, 768, 390, 375], 'rounding': 'Windows 125% display scaling can round the 768/1024 requests by one CSS pixel; actual dimensions are recorded.',
            'mutations': 'Synthetic accounts and canonical loans in disposable Mongo databases only; no real email delivery.'}})
    gates = [{'gate': n, 'status': 'PASS', 'requirement': title, 'evidence': evidence} for n, (title, evidence) in GATES.items()]
    write('dashboard_convergence_acceptance.json', {'status': 'PASS', 'gates_52_80': gates, 'unknown_features': [],
        'unknown_legacy_accounts': read('dashboard_convergence_account_review.json')['legacy_accounts'], 'production_grants_applied': 0})
    md = ['# Legacy dashboard removal and authority convergence', '',
        'Status: **PASS for acceptance gates 52–80**. Verified ' + datetime.now(timezone.utc).isoformat() + '.', '',
        'The final management product has Platform Console, Library Staff Workspace and Patron Workspace. Legacy management dashboards, navigation and independent writers have been retired. Existing ambiguous accounts remain unprivileged pending independently approved mapping; their records were retained.', '',
        '## Authority and routing', '',
        '- Platform Console requires the current active, verified identity and an ACTIVE PLATFORM_ADMIN assignment with nonblank approval reference, approving operator and valid approval time. Expired, revoked, incomplete, malformed and future-dated approvals fail closed.',
        '- Library Staff Workspace requires an active ADMIN or LIBRARIAN LibraryMembership for the explicit canonical library UUID. Patron Workspace requires a GENERAL_USER membership. A staff member cannot obtain patron mutation controls in that same library.',
        '- `/admin` uses explicit platform access when available, otherwise the same staff resolution as `/librarian` and `/staff`: exactly one staff membership goes to its workspace, several go to the selector, none deny. Remembered context never breaks a tie.',
        '- Frontend `/staff/events` and setup compatibility links redirect to `/platform/events` and `/account/setup`. The old `/admin/{path}` API is a guarded 307 redirect preserving method/query to the Platform API; retired circulation targets return 410.',
        '- Global metadata administration accepts no physical stock/shelf mutations. Platform account creation produces an ordinary identity and neither a membership nor a platform grant.', '',
        '## Complete feature classification', '',
        'YES/NO describes the identified implementation. OBSOLETE rows are intentionally not migrated. NO under removal explicitly identifies a retained read-only/personal/offline compatibility implementation, never a second tenant writer. UNKNOWN rows are account records kept for manual review, not unclassified features deleted from the product.', '',
        '| ' + ' | '.join(FIELDS) + ' |', '| ' + ' | '.join(['---'] * len(FIELDS)) + ' |']
    md += ['| ' + ' | '.join(str(row[k]).replace('|', '\\|') for k in FIELDS) + ' |' for row in ROWS]
    md += ['', 'Search infrastructure, global dataset administration and future HNSW/KG administration were not implemented old dashboard features. No speculative modules were invented, and their protected algorithm/training code was unchanged.', '',
        '## Exact implementation removal', '',
        'Removed after migration and regression:', '', *['- `' + p + '`' for p in removed_source], '',
        'The product source audit found no imports or callers of the deleted dashboard/forms/service symbols. Shared StaffUI controls and membership-scoped InstitutionPanel remain canonical dependencies. Old shell/navigation CSS was removed while shared table/dialog styles remain.', '',
        'Legacy issue, return, renewal, reservation, fee and inventory/import writer implementations were removed. Authenticated legacy mutation routes and direct service stubs return 410 and cannot mutate stock. Global and personal history remains explicitly read-only. No old ready-reservation/fine-creation/renewal write algorithm remains authoritative.', '',
        'Canonical staff-assisted renewal and physical receipt call the existing library lending service. They reuse its lock, durable operation journal, pinned renewal policy, stable command keys and receipt confirmation. Preparation failure leaves the loan pending receipt and retains allocation; replay resumes the same command. Staff cannot assist their own personal legacy loan or another library, and platform-only access cannot invoke these operations.', '',
        '## Every retained legacy User.role usage', '',
        'The source audit records exact lines and source text in [dashboard_convergence_source_audit.json](dashboard_convergence_source_audit.json). Remaining product usages are explained below. None authorizes institution or platform management.', '']
    for item in role_audit:
        lines = ', '.join(str(r['line']) for r in item['remaining_usages']) or 'No executable role usage remains'
        md += ['- `' + item['file'] + '` (' + lines + '): ' + item['reason']]
    md += ['', 'Canonical membership roles, explicit platform assignment roles, HTML accessibility roles and assistant conversation roles are separate concepts. Frozen historical report-generation scripts may reference old filenames to document earlier snapshots; they do not mount UI or grant access.', '',
        '## Legacy account migration and preserved records', '',
        'Production dry run found user_id **2 (LIBRARIAN)** and **3 (ADMIN)** without approved context. Both are `UNKNOWN_REVIEW_REQUIRED`; zero inferred memberships, zero platform promotions and zero production document mutations. Their identities and historical records were retained. Platform Console has a paginated read-only review screen.', '',
        '`scripts/migrate_management_authority.py` defaults to dry run. Apply requires an explicit mapping whose every grant has `approved=true`, `approved_by`, `approval_ref` and `reason`. A local grant requires an existing active canonical UUID and ADMIN/LIBRARIAN membership role; an installation grant requires independently justified PLATFORM_ADMIN. Optional legacy aliases are explicit, never guessed. Invalid identity, conflicting grant/alias, duplicate input and incomplete existing proof fail before writes. Apply uses an operator lock and does not overwrite grants; concurrent/partial failure requires operator review.', '',
        'No approved production mapping was supplied, so apply was not run. Existing legacy inventory, issues, reservations and fees remain historical read-only records. Existing canonical cutover migration tooling requires its own reviewed library mapping and stopped legacy writers; this phase does not silently convert those records or provision authority.', '',
        '## Verification', '',
        f'- Backend grouped product regressions: **{backend_pass} passed, {backend_skip} pre-existing skips, 0 failed**. Latest authority suite: **38 passed**; 52 post-removal search/access checks also passed. Group counts follow prior reporting conventions and are not claimed as a deduplicated census.',
        f'- Frontend: **{sum(r["passed"] for r in frontend)} passed, 0 failed** across the final default suite (including management tests) and supplementary Events/notifications/history/search/RAG-formatting suites.',
        '- TypeScript/Vite production build passed. Lint exited 0 with ' + str(len(re.findall(r': warning ', lint))) + ' warnings and no errors. Existing large-bundle and React hook/style warnings remain visible in logs.',
        '- Browser: **42 checks**, seven Platform sections across six requested widths, no document overflow and no old navigation. Actual dimensions record Windows display rounding. Real-browser proof covers platform-only access, legacy role-only denial, single-membership redirect, multiple-membership selector with remembered context, staff renewal and physical receipt, Librarian operational activity and patron separation.',
        '- Retired positive legacy-writer tests were replaced by HTTP 410/direct-service no-write assertions. Canonical V1/V2A/V2B/V2C business suites remain active. No Router V1–V5 research suite was substituted for product validation.',
        '- The pinned Events test wall clock was aligned to current time without disabling JWT expiry verification. A combined fixture run exposed incompatible per-suite DB prefixes; suites were rerun in separate processes. An initial timing-sensitive knowledge test passed unchanged on rerun. Final recorded results above are passing runs.', '',
        'Evidence: [validation](dashboard_convergence_validation.json), [backend groups](dashboard_convergence_regression.json), [latest authority XML](dashboard_convergence_authority_final.xml), [browser dimensions](dashboard_convergence_browser_matrix.json), [browser flows](dashboard_convergence_browser_flows.json), [classification](dashboard_convergence_classification.json), [production account review](dashboard_convergence_account_review.json).', '',
        '## Preservation and cleanup', '',
        f'All **{len(BASE["prior_reports_sha256"])}** earlier report hashes are unchanged. All **{len(protected)}** protected source/config/model files under assistant, chatbot, search, recommendation, RAG, KG, pipeline, training, evaluation and benchmark roots are unchanged. Production collection counts match the phase baseline, including five million catalogue books, 13 identities, 39 legacy issues and zero platform assignments. Count equality is not a full content hash; the phase performed no production document writes or original-service restart.', '',
        'Both owned disposable browser fixture databases were dropped and their services stopped. The temporary tab was closed and viewport restored. Other user tabs/services were left running. See [preservation](dashboard_convergence_preservation.json), [cleanup](dashboard_convergence_cleanup.json) and [first fixture cleanup](dashboard_convergence_cleanup_first_fixture.json).', '',
        '## Gates 52–80', '', '| Gate | Status | Requirement | Evidence |', '| --- | --- | --- | --- |']
    md += [f'| {g["gate"]} | PASS | {g["requirement"]} | {g["evidence"]} |' for g in gates]
    md += ['', '## Reviewable proof', '', 'Canonical physical return completed in an isolated fixture:', '',
        '![Canonical staff receipt](dashboard_convergence_staff_return_completed.png)', '',
        'Platform Console global overview:', '', '![Platform Console](dashboard_convergence_overview_1440.png)', '']
    target = REPORTS / 'legacy_dashboard_removal.md'
    assert str(target.relative_to(ROOT)) not in BASE['prior_reports_sha256']
    target.write_text('\n'.join(md), encoding='utf8')
    command_text = '''# Reproduce dashboard convergence verification

Run backend commands in D:\\SDC\\LibraryLLM with the project's virtual environment.

```powershell
.\\.venv\\Scripts\\python.exe -X utf8 scripts/test_dashboard_convergence_regressions.py
.\\.venv\\Scripts\\python.exe -X utf8 -m pytest tests/dashboard_convergence -q --junitxml=reports/dashboard_convergence_authority_final.xml
```

Each Mongo fixture suite must run in its own process; do not combine suites that own different database prefixes.

From the frontend directory:

```powershell
npm test
npx tsx --tsconfig tsconfig.app.json --test tests/events.test.tsx tests/admin-notifications.test.tsx tests/loan-renewal.test.tsx tests/search-depth.test.tsx tests/part3-regression.test.tsx tests/rag-answer.test.tsx
npm run build
npm run lint
```

Dry-run account review (no inferred grants):

```powershell
.\\.venv\\Scripts\\python.exe -X utf8 scripts/migrate_management_authority.py
```

An operator must supply an independently approved mapping before using --apply --mapping. No production apply was executed. Each row must identify an existing ready user, an explicit role, approval metadata and, for library membership, an existing active canonical library UUID. Both authorities require independent justification when one user receives both.

The live test harness is scripts/check_dashboard_convergence_live.py --serve. It owns only its generated luminar_dc_live_* database and ports 8086/5186, emits synthetic fixture credentials in .scratch only, and stops/drops its resources when its stop file appears. Never copy fixture credentials into reports. Browser proof must use the documented computer-use API.

scripts/report_dashboard_convergence.py reads the baseline, current production counts, test logs, browser records and cleanup evidence. It asserts preservation and writes only new phase reports. It cannot create authority grants.
'''
    (REPORTS / 'dashboard_convergence_commands.md').write_text(command_text, encoding='utf8')
    write('dashboard_convergence_completion.json', {'status': 'PASS', 'completed_at': datetime.now(timezone.utc).isoformat(),
        'report': 'reports/legacy_dashboard_removal.md', 'gates_passed': list(GATES), 'unclassified_dashboard_features': 0,
        'legacy_accounts_requiring_review': [2, 3], 'production_grants_applied': 0, 'backend_passed': backend_pass,
        'frontend_passed': sum(r['passed'] for r in frontend), 'prior_reports_preserved': len(BASE['prior_reports_sha256'])})
    print(f'PASS: gates 52–80; backend {backend_pass} passed/{backend_skip} skipped; frontend {sum(r["passed"] for r in frontend)} passed; prior reports {len(BASE["prior_reports_sha256"])} preserved.')


if __name__ == '__main__':
    main()
