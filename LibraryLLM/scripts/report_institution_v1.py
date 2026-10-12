"""Build Institution V1 evidence and source-preservation reports; never touch Mongo."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'


def write_json(name, value):
    (REPORTS / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_preservation():
    baseline = json.loads((REPORTS / 'institution_v1_baseline.json').read_text(encoding='utf-8'))
    allowed = {
        'backend/main.py', 'frontend/src/App.tsx', 'frontend/src/components/Header.tsx',
        'frontend/src/components/ProtectedRoute.tsx', 'frontend/src/pages/LoginPage.tsx',
        'frontend/src/pages/StaffDashboard.tsx', 'frontend/src/store/useAuthStore.ts',
    }
    changed, unchanged, missing = [], [], []
    for name, expected in baseline['source_hashes'].items():
        path = ROOT / name
        if not path.exists():
            missing.append(name)
        elif sha(path) != expected:
            changed.append(name)
        else:
            unchanged.append(name)
    frozen_roots = ('assistant/', 'search/', 'recommendation/', 'rag/', 'knowledge_graph/')
    frozen = [name for name in baseline['source_hashes'] if name.startswith(frozen_roots)]
    unexpected = sorted(set(changed) - allowed)
    result = {
        'status': 'PASS' if not missing and not unexpected else 'FAIL',
        'baseline_source_files': len(baseline['source_hashes']),
        'unchanged_files': len(unchanged), 'changed_existing_source_files': sorted(changed),
        'missing_files': missing, 'unexpected_changes': unexpected,
        'frozen_source_files': len(frozen),
        'frozen_sources_unchanged': all(name in unchanged for name in frozen),
        'baseline_preexisting_dirty_work_preserved': not missing and not unexpected,
        'boundary': 'Baseline hashes cover first-party source, not model binaries/data. No model/data migration was performed.',
    }
    write_json('institution_v1_preservation.json', result)
    if result['status'] != 'PASS':
        raise RuntimeError('Unexpected baseline source change; inspect preservation report.')
    return result, baseline


def evidence():
    xml = ET.parse(REPORTS / 'institution_v1_backend.xml').getroot()
    cases = list(xml.iter('testcase'))
    if any(c.find('failure') is not None or c.find('error') is not None for c in cases):
        raise RuntimeError('Institution backend evidence contains a failure.')
    passed = [c.attrib['name'] for c in cases if c.find('skipped') is None]
    live = json.loads((REPORTS / 'institution_v1_live.json').read_text(encoding='utf-8'))
    browser = json.loads((REPORTS / 'institution_v1_browser_live.json').read_text(encoding='utf-8'))
    frontend = (REPORTS / 'institution_v1_frontend.log').read_text(encoding='utf-8')
    if (not passed or live.get('status') != 'PASS' or browser.get('status') != 'PASS'
            or not re.search(r'\bpass 28\b', frontend) or not re.search(r'\bfail 0\b', frontend)):
        raise RuntimeError('Completed passing backend/frontend/live/browser artifacts are required.')
    groups = {
        'registration': ('registration', 'duplicate_normalized_slug'),
        'discovery': ('discovery', 'inactive_library', 'pagination'),
        'membership': ('join_idempotent', 'multi_library', 'roles_differ', 'self_reactivation', 'staff_loses', 'real_jwt', 'concurrent', 'cross_library_membership'),
        'private_access': ('private_code', 'rotation', 'access_mode', 'unicode', 'partial_grants', 'general_user_denied', 'concurrent_private'),
        'staff': ('admin_chaining', 'owner_last_admin', 'staff_loses', 'stale_inviter', 'roles_differ', 'general_user_denied'),
        'invitations': ('invitation', 'unknown_email', 'invite_expiry', 'stale_inviter', 'double_accept', 'partial_grants', 'email_change'),
        'security': ('mass_assignment', 'secret_safe', 'spoof', 'cross_library', 'private_code', 'brute_force', 'real_jwt', 'audit_whitelist', 'partial_grants', 'owner_last_admin', 'unicode', 'email_change', 'stale_inviter', 'self_reactivation', 'general_user_denied', 'inactive_library', 'pagination', 'invitation_secrets', 'invite_expiry', 'double_accept', 'admin_chaining'),
    }
    assertions = {
        'registration': ['Public/private registration', 'Server-derived owner and ACTIVE ADMIN membership', 'No global role escalation', 'Unique normalized slug; duplicate names allowed', 'Strict forbidden fields and secret-safe validation'],
        'discovery': ['Escaped literal Mongo name/slug/city/region search', 'All/public/private/mine filters', 'Bounded limit/offset', 'Safe display metadata and requesting-user membership only', 'Inactive libraries excluded'],
        'membership': ['Unique library + canonical user membership', 'Public/private joins only GENERAL_USER', 'Idempotent repeat join', 'No self-reactivation after suspension/removal', 'Different roles for same account in different libraries', 'Session-scoped active context; backend remains authority'],
        'private_access': ['Argon2id salted password hash only', 'Case-sensitive 8-128 Unicode character codes', 'Owner/Admin/Librarian rotation', 'Old credential invalid; new credential valid; memberships preserved', 'Public-private conversion requires code; private-public clears hash', 'Persistent account/library and library-wide fixed-window verification budgets'],
        'staff': ['Owner can manage non-owner staff and invite Admin', 'Non-owner Admin can manage member/Librarian, not Admin', 'Librarian cannot manage staff', 'Owner cannot be removed/suspended/demoted', 'Serialized active-owner and last-admin invariant', 'Suspended/removed membership immediately loses authority'],
        'invitations': ['256-bit random token hashed with SHA-256', 'Known account canonical ID + verified exact email binding', 'Unknown account token + subsequently verified exact email', 'Expiration, revoke, decline, reissue, duplicate pending protection', 'Wrong email/token/library and replay fail', 'Acceptance rechecks inviter current authority', 'No raw token/hash in lists/audit; manual copy link returned once'],
        'security': ['Canonical UUID tenant predicates and active membership guard', 'Legacy global ADMIN cannot authorize new tenant operations', 'No secrets in API validation/audit/display serializers', 'Role/owner/user/status mass assignment rejected', 'Partial invitation grants and unknown commits fail closed', 'Cross-library resource IDs denied', 'Concurrency and stale JWT/current status tested'],
    }
    limitations = {
        'registration': ['No organization verification or institution creation quota yet.'],
        'discovery': ['Literal regex/offset search is not a 10k-library scale benchmark; directory profiles are public.'],
        'membership': ['Only Part 1 APIs use these membership guards; old domain data remains legacy scoped.'],
        'private_access': ['Shared code proves possession, not individual affiliation.', 'Fixed windows can allow adjacent-window bursts; all verification attempts consume budget.'],
        'staff': ['Ownership transfer and account recovery are deferred.', 'No additional fine-grained staff permission enum.'],
        'invitations': ['No external mail sent; new accounts signup/verify then reopen invitation link.', 'Bound invites fail closed after account email change.'],
        'security': ['Current globally scoped holdings/RAG/events are not made tenant-private.', 'Standalone Mongo uses persistent fail-closed gates; crashed holders require supervised offline reconciliation.', 'Proxy/APM secret redaction remains a deployment obligation.'],
    }
    for group, terms in groups.items():
        selected = [name for name in passed if any(term in name for term in terms)]
        write_json(f'institution_v1_{group}.json', {
            'status': 'PASS', 'evidence_type': 'derived from completed test artifacts, not a new test run',
            'backend_evidence': 'institution_v1_backend.xml', 'backend_total_passed': len(passed),
            'matched_backend_cases': len(selected), 'tests': selected,
            'frontend_evidence': 'institution_v1_frontend.log (28 institution component tests)',
            'live_evidence': 'institution_v1_live.json (A-J, real uvicorn + HTTP + disposable Mongo)',
            'live_status': live['status'], 'browser_status': browser['status'],
            'assertions': assertions[group], 'limitations': limitations[group],
            'note': 'Feature subsets intentionally overlap; do not add subset counts as unique tests.',
        })
    return len(passed)


def role_audit():
    pattern = r'GENERAL_USER|LIBRARIAN|\bADMIN\b|require_roles|\[.role.\]|\.role\b|\.get\([\x22\x27]role[\x22\x27]|JWT.*role|role.*JWT'
    command = ['rg', '-n', '--glob', '*.py', '--glob', '*.ts', '--glob', '*.tsx', pattern,
               'backend', 'frontend/src', 'search', 'recommendation', 'rag', 'assistant', 'knowledge_graph', 'scripts']
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr)
    rows, non_auth = [], []
    migrate_routes = {'activity', 'events', 'fines', 'inventory', 'issues', 'notifications', 'renewals', 'reservations'}
    migrate_frontend = {'EventsPage', 'EventDetailPage', 'BookCapabilities', 'readNow', 'AdminOperations'}
    for record in result.stdout.splitlines():
        found = re.match(r'(.+?):(\d+):(.*)', record)
        if not found:
            continue
        name, line, code = found.groups()
        name = name.replace('\\', '/')
        path = Path(name)
        if (path.stem in {'LLMPage', 'AIChatWidget', 'rag_domain_qa_v4'} and
                not re.search(r'GENERAL_USER|LIBRARIAN|\bADMIN\b', code)):
            non_auth.append((name, line, 'Chat-message role or domain text parser; not account/tenant authorization.'))
            continue
        if 'institution' in name or path.stem == 'LibrarySwitcher':
            category = 'NEW MEMBERSHIP-BASED'
            reason = 'Current UUID library membership authority or its request/UI contract.'
            if path.stem == 'migrate_institution_v1' and int(line) < 70:
                category = 'LEGACY GLOBAL'
                reason = 'Migration reads legacy roles to propose memberships; never escalates User.role.'
            elif path.stem == 'check_institution_v1_live' and int(line) < 80:
                category = 'CAN REMAIN GLOBAL'
                reason = 'Disposable global account/JWT fixture; not tenant authority.'
        elif name == 'frontend/src/components/ProtectedRoute.tsx' and ('libraryAllowed' in code or 'institution.membership' in code):
            category = 'NEW MEMBERSHIP-BASED'
            reason = 'Membership-backed UI admission; server still checks every institution request.'
        elif name == 'frontend/src/App.tsx' and 'libraryRoles=' in code:
            category = 'NEW MEMBERSHIP-BASED'
            reason = 'Adds library membership UI admission while retaining legacy global dashboard compatibility.'
        elif name == 'frontend/src/App.tsx' and '/staff/events' in code:
            category = 'MUST MIGRATE PART 2'
            reason = 'Event editor UI privilege must migrate with event ownership/query scope.'
        elif name == 'frontend/src/pages/StaffDashboard.tsx' and int(line) < 90:
            category = 'NEW MEMBERSHIP-BASED'
            reason = 'Compatibility wrapper admits current library staff to Institution panel without legacy API access.'
        elif name == 'frontend/src/pages/StaffDashboard.tsx':
            category = 'CAN REMAIN GLOBAL' if int(line) < 550 else 'MUST MIGRATE PART 2'
            reason = 'Global bibliography curator delete control.' if int(line) < 550 else 'Legacy inventory delete control; migrate with holdings and availability.'
        elif name.startswith('backend/routes/') and path.stem in migrate_routes:
            category = 'MUST MIGRATE PART 2'
            reason = 'Legacy domain privilege requires library-scoped resource predicates when that domain migrates.'
        elif path.stem == 'notification_service' or (name.startswith('frontend/') and path.stem in migrate_frontend):
            category = 'MUST MIGRATE PART 2'
            reason = 'Legacy audience/circulation UI or operation; scope together with corresponding domain.'
        elif name == 'backend/routes/books.py':
            category = 'CAN REMAIN GLOBAL'
            reason = 'Global bibliographic metadata curation; do not grant this global privilege to new library staff.'
        elif name.startswith(('backend/scripts/',)) or path.stem in {'staff', 'staff_service', 'StaffManagement', 'StaffLoginPage'}:
            category = 'LEGACY GLOBAL'
            reason = 'Existing installation-wide account provisioning/management compatibility, separate from institution invites.'
        elif path.stem in {'auth_service', 'identity_service', 'jwt_utils', 'dependencies', 'user', 'useAuthStore', 'SignUpPage'}:
            category = 'CAN REMAIN GLOBAL'
            reason = 'Global identity/session/legacy staff-login contract; new institution checks ignore this role as authority.'
        elif name.startswith('scripts/'):
            category = 'LEGACY GLOBAL'
            reason = 'Existing seed, fixture, report or validation script using legacy global accounts; audited only, not executed/rewritten.'
        else:
            category = 'LEGACY GLOBAL'
            reason = 'Compatibility navigation, role display or old staff control; do not reinterpret as current library role.'
        rows.append((name, line, category, reason, code.strip()))
    rows.sort(key=lambda row: (row[0], int(row[1])))
    non_auth.sort(key=lambda row: (row[0], int(row[1])))
    counts = Counter(row[2] for row in rows)
    text = '''# Institution V1 legacy role audit

8 October 2026. Read-only source audit; no Part 2 role/domain migration was performed.

The four required classifications are **LEGACY GLOBAL**, **NEW MEMBERSHIP-BASED**, **MUST MIGRATE PART 2**, and **CAN REMAIN GLOBAL**. MUST MIGRATE PART 2 also means the currently shipped behavior remains legacy global until the corresponding resource model/queries migrate. A preserved User.role is never sufficient for new institution authority.

Inventory scans all first-party `.py`, `.ts`, and `.tsx` files under backend, frontend/src, search, recommendation, rag, assistant, knowledge_graph and scripts. It covers role enums, role expressions, `.get('role')`, JWT-role references and dependencies. Test files outside those source roots are fixtures/evidence, not a second authority implementation. Research script references are listed but Router V1-V5 evaluations were not run. Re-run with the command below; this report is generated by `scripts/report_institution_v1.py`.

```powershell
rg -n --glob '*.py' --glob '*.ts' --glob '*.tsx' 'GENERAL_USER|LIBRARIAN|\\bADMIN\\b|require_roles|\\[.role.\\]|\\.role\\b|\\.get\\([\\x22\\x27]role[\\x22\\x27]|JWT.*role|role.*JWT' backend frontend/src search recommendation rag assistant knowledge_graph scripts
```

## Classification decisions

- Global user_id, email normalization, session status/revocation and JWT legacy role remain identity contracts. New guards derive canonical user_id and read current membership; JWT role does not authorize a tenant.
- Existing `/staff`, bootstrap/reset scripts and Staff Management retain installation-wide authority. Institution staff receive no global account promotion and use invitations instead.
- `/books` writes curate shared bibliography. This can retain explicit global catalogue-curator authorization. A later holding/copy API must have a different library-scoped guard; do not reuse global catalogue powers for library staff.
- Inventory, issues/returns/renewals, reservations, fines, activity, events and staff notifications must migrate their resource predicates and role checks together. Current routes stay intact for compatibility, with no claim of institution privacy.
- Header/profile/login/nav legacy role display remains distinct from the new switcher role. ProtectedRoute's membership branch is UI convenience; backend enforcement is mandatory. The StaffDashboard wrapper directs new library staff to the Institution panel and avoids old global staff calls.
- Personal document RAG remains user/session scoped. Chat-message `role` is not staff authority. Assistant circulation tools currently depend on old core domain endpoints; their tenant context changes belong to Part 2. Semantic routing, models and catalogue retrieval remain frozen.

## Inventory counts

'''
    text += '| Classification | Source reference count |\n|---|---:|\n'
    text += ''.join(f'| {category} | {counts[category]} |\n' for category in ('LEGACY GLOBAL', 'NEW MEMBERSHIP-BASED', 'MUST MIGRATE PART 2', 'CAN REMAIN GLOBAL'))
    text += '\n## Every matching authority/compatibility reference\n\n| Source | Class | Reason | Expression |\n|---|---|---|---|\n'
    for name, line, category, reason, code in rows:
        safe = code.replace('|', '&#124;').replace('`', '&#96;').replace('<', '&lt;').replace('>', '&gt;')
        if len(safe) > 280:
            safe = safe[:277] + '...'
        text += f'| `{name}:{line}` | {category} | {reason} | `{safe}` |\n'
    text += '\n## Non-authorization role matches\n\nThese matches were reviewed and classified **CAN REMAIN GLOBAL** (chat/schema/domain text); they must not become tenant authority. HTML ARIA role attributes are accessibility semantics and are outside account-role authorization.\n\n'
    for name, line, reason in non_auth:
        text += f'- `{name}:{line}` — CAN REMAIN GLOBAL: {reason}\n'
    (REPORTS / 'institution_v1_legacy_role_audit.md').write_text(text, encoding='utf-8')
    return counts


def manifest(preservation, baseline):
    modified = preservation['changed_existing_source_files'] + ['frontend/package.json', 'requirements.txt', 'requirements-local.txt']
    roots = ['backend', 'frontend/src', 'frontend/tests', 'scripts', 'tests/institution_v1']
    added = []
    for folder in roots:
        for path in (ROOT / folder).rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            name = path.relative_to(ROOT).as_posix()
            if ('institution' in name.lower() or name.endswith('LibrarySwitcher.tsx')) and name not in baseline['source_hashes'] and name not in modified:
                added.append(name)
    reports = sorted(p.relative_to(ROOT).as_posix() for p in REPORTS.glob('institution_v1*') if p.is_file())
    for name in ['reports/institution_v1_completion.md', 'reports/institution_v1_manifest.json']:
        if name not in reports:
            reports.append(name)
    result = {
        'status': 'PASS', 'phase': 'Institutions / Private Libraries Part 1 only',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'modified_existing_files': sorted(modified), 'added_implementation_and_test_files': sorted(added),
        'reports_created': sorted(reports),
        'sha256': {name: sha(ROOT / name) for name in modified + added},
        'preexisting_work': 'All other Git dirty/untracked content predates this phase; use baseline and preservation report, not git diff alone.',
        'temporary_validation_files': ['.scratch/institution-v1/fixture.json', '.scratch/institution-v1/core.log', '.scratch/institution-v1/frontend.log', '.scratch/institution-v1/events_regression.py'],
        'production_migration_applied': False, 'part2_implemented': False,
    }
    write_json('institution_v1_manifest.json', result)
    return result


def main():
    preservation, baseline = source_preservation()
    passed = evidence()
    counts = role_audit()
    result = manifest(preservation, baseline)
    print(json.dumps({'preservation': preservation, 'backend_passed': passed, 'role_audit_counts': counts,
                      'modified_files': len(result['modified_existing_files']), 'added_files': len(result['added_implementation_and_test_files']),
                      'reports': len(result['reports_created'])}, indent=2))


if __name__ == '__main__':
    main()
