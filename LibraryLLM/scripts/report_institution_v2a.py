"""Assemble the Part 2A handoff from saved tests, live checks and source hashes."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import xml.etree.ElementTree as ET
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'


def read(name):
    return json.loads((REPORTS / ('institution_v2a_' + name + '.json')).read_text(encoding='utf8'))


def write(name, data):
    (REPORTS / ('institution_v2a_' + name + '.json')).write_text(json.dumps(data, indent=2, default=str) + '\n', encoding='utf8')


def markdown(name, body):
    (REPORTS / ('institution_v2a_' + name + '.md')).write_text(body.strip() + '\n', encoding='utf8')


def xml_summary(filename):
    tree = ET.parse(REPORTS / filename); cases = list(tree.iter('testcase'))
    return {'artifact': filename, 'tests': len(cases), 'passed': sum(not any(c.tag in ('failure', 'error', 'skipped') for c in t) for t in cases),
            'failed': sum(any(c.tag in ('failure', 'error') for c in t) for t in cases), 'skipped': sum(any(c.tag == 'skipped' for c in t) for t in cases),
            'cases': [t.attrib.get('classname', '') + '::' + t.attrib['name'] for t in cases]}


def main():
    baseline = read('baseline'); live = read('live'); migration = read('migration'); geometry = read('browser_geometry')
    backend = xml_summary('institution_v2a_backend_final.xml'); v1 = xml_summary('institution_v2a_regression_institution_v1.xml')
    atomic = xml_summary('institution_v2a_concurrency.xml')
    assert backend['tests'] == backend['passed'] == 95 and v1['tests'] == v1['passed'] == 56 and atomic['failed'] == 0
    assert live['status'] == geometry['status'] == read('browser_live')['status'] == 'PASS'
    assert all(r['status'] == 'PASS' for r in live['reconciliation'])
    groups = [xml_summary('institution_v2a_regression_' + name + '.xml') for name in
              ('unit', 'assistant', 'security', 'staff', 'notifications', 'circulation', 'search', 'private_knowledge_ocr', 'kg', 'events')]
    assert all(g['failed'] == 0 for g in groups)
    frontend_log = (REPORTS / 'institution_v2a_frontend_full.log').read_text(encoding='utf8')
    extended = (REPORTS / 'institution_v2a_frontend_extended.log').read_text(encoding='utf8')
    frontend = {'full_chain': sum(map(int, re.findall(r'ℹ pass (\d+)', frontend_log))),
                'extended': sum(map(int, re.findall(r'ℹ pass (\d+)', extended))), 'new_inventory': 26,
                'final_inventory_artifact': 'institution_v2a_frontend.log'}
    assert frontend['full_chain'] == 230 and frontend['extended'] == 156
    assert not re.search(r'ℹ fail [1-9]', frontend_log + extended + (REPORTS / 'institution_v2a_frontend.log').read_text(encoding='utf8'))
    build = (REPORTS / 'institution_v2a_build.log').read_text(encoding='utf8')
    lint = (REPORTS / 'institution_v2a_lint.log').read_text(encoding='utf8')
    assert 'built in' in build and ': error ' not in lint
    assert not any('institution-inventory' in line or 'LibraryInventory' in line for line in lint.splitlines() if ': warning ' in line)
    changed = [p for p, value in baseline['source_hashes'].items() if not (ROOT / p).is_file() or hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != value]
    allowed = ['backend/main.py', 'backend/services/institution_repository.py', 'frontend/package.json', 'frontend/src/App.tsx',
               'frontend/src/components/LibrarySwitcher.tsx', 'frontend/src/pages/InstitutionPanel.tsx', 'frontend/src/pages/Institutions.tsx', 'frontend/src/pages/StaffDashboard.tsx']
    assert set(changed) == set(allowed), changed
    write('preservation', {'status': 'PASS', 'baseline_files': len(baseline['source_hashes']), 'unchanged': len(baseline['source_hashes']) - len(changed),
        'changed_integration_files': changed, 'unexpected_changes': [], 'global_search_recommendation_kg_rag_assistant_models_unchanged': True,
        'institution_v1_behavior': 'Default mutation wait remains 3s. Only inventory callers opt into a 30s bounded wait; audit metadata allows safe inventory IDs/counts.'})
    mongo = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=5000)
    production = mongo[baseline['topology']['database']]
    production_state = {'database': production.name, 'global_books': production.books.estimated_document_count(),
        'legacy_inventory': production.library_inventory.count_documents({}), 'institutions': production.institution_libraries.count_documents({}),
        'canonical_inventory': production.institution_library_books.count_documents({})}
    assert all(production_state[k] == baseline['topology'][k] for k in ('global_books', 'legacy_inventory', 'institutions', 'canonical_inventory'))
    assert [dict(index['key']) for index in production.books.list_indexes()] == baseline['topology']['book_indexes']
    remaining = [n for n in mongo.list_database_names() if n.startswith('luminar_institution_v2a_live_')]
    assert not remaining, remaining
    mongo.close()
    write('regression', {'status': 'PASS', 'backend_part2a': backend, 'institution_v1': v1, 'concurrency_recheck': atomic, 'frozen_groups': groups,
        'frozen_totals': {'cases': sum(g['tests'] for g in groups), 'passed': sum(g['passed'] for g in groups), 'skipped': sum(g['skipped'] for g in groups), 'failed': 0},
        'count_note': 'Suite executions; frozen groups overlap in some KG/private-document cases. Counts are not a unique-test claim.',
        'frontend': frontend, 'build': 'PASS', 'lint': {'status': 'PASS', 'errors': 0, 'warnings': lint.count(': warning '), 'new_inventory_warnings': 0},
        'legacy_inventory_reading_list_reservation_fee_compatibility': 'test_legacy_compatibility.py plus frozen staff/circulation suites',
        'events_clock_note': 'Only obsolete fixture NOW timestamps are aligned to UTC now; source files, expiry checks and JWT verification are unchanged.',
        'isolation_note': 'Institution V1 and V2A fixtures require separate processes. An attempted combined run passed 145 cases but tripped the V1 teardown database-name guard. Both suites were rerun in their required isolated processes; final artifacts above pass.',
        'production_after': production_state, 'router_v1_v5_research_rerun': False, 'models_called_or_trained': False})
    def evidence(name, terms, detail, scenarios=()):
        matched = [case for case in backend['cases'] if any(term in case for term in terms)]
        write(name, {'status': 'PASS', **detail, 'test_artifact': backend['artifact'], 'test_cases': matched,
            'live_scenarios': [row for row in live['scenarios'] if row['number'] in scenarios]})
    evidence('accession_numbers', ['accession', 'concurrent', 'failed_validation'], {'format': 'PREFIX-000001', 'prefix': 'First three ASCII alphanumeric uppercase characters of the original library name, or LIB; persisted on first allocation.',
        'atomic_primitive': 'Mongo find_one_and_update + $inc + upsert, ReturnDocument.AFTER', 'sequence_key': ['library_id', 'BOOK_ACCESSION'],
        'immutable': True, 'preview_allocates': False, 'reuse': False, 'padding_minimum': 6, 'larger_example': 'AUR-1000000',
        'concurrent_manual': live['concurrent_manual'], 'prefix_stable_on_rename': live['prefix_rename_stable'], 'gaps': 'Allowed after issued counters, failures or explicit allocation checks; never decrement/reuse.'}, (1, 4, 7))
    evidence('minimal_metadata', ['required', 'optional', 'minimum', 'minimal', 'normalization'], {'required': ['title', 'subjects (one or more)'],
        'optional': ['authors', 'ISBN', 'global_work_id', 'publisher', 'publication_year', 'edition', 'language', 'description', 'shelf', 'call number', 'tags', 'note', 'barcode'],
        'quantity_default': 1, 'unknown_isbn': None, 'unknown_global_work': None, 'unknown_authors': [], 'invented_metadata_or_ids': False,
        'metadata_sources': ['Explicit submitted metadata', 'Verified existing global metadata fallback in legacy migration only']}, (1, 2, 4, 5))
    evidence('holdings', ['holding', 'quantit', 'copy', 'legacy_inventory'], {'book_key': ['library_id', 'library_book_id'], 'unique_holding_per_book': True,
        'invariant': '0 <= available_copies <= total_copies; strict integers', 'quantity_semantics': 'INVENTORY_SNAPSHOT_NOT_CIRCULATION',
        'legacy_dual_write': False, 'copy_foundation': 'UUID copy/holding/book references, monotonic local copy ordinal, optional same-tenant unique barcode; aggregate quantities are not expanded.',
        'legacy_barcode_status': 'UNVERIFIED', 'reconciliation': live['reconciliation']}, (1, 3, 10))
    evidence('dataset_import', ['import', 'preview', 'minimum', 'csv', 'xlsx', 'row', 'formula'], {'formats': ['UTF-8 CSV (BOM supported)', 'XLSX'], 'bounds': {'bytes': 5242880, 'rows': 2000, 'columns': 40, 'xlsx_expanded_bytes': 26214400},
        'aliases': {'title': ['title', 'book_title', 'name'], 'subjects': ['subject', 'subjects', 'genre', 'category']}, 'classifications': ['NEW_LOCAL', 'GLOBAL_MATCH', 'EXISTING_HOLDING', 'POSSIBLE_DUPLICATE', 'INVALID'],
        'bindings': ['Canonical library UUID', 'Current actor user_id', 'File SHA-256', 'One-hour expiry'], 'apply_rechecks': ['Current account eligibility', 'Current library membership/role', 'Global work existence', 'Current same-tenant duplicate state'],
        'existing_policy': ['skip (default)', 'increase_quantity (explicit)'], 'idempotency': 'Stored completed/partial result plus unique per-row import source key', 'formula_execution': False,
        'preview_business_writes': False, 'preview_persistence': 'Protected job/preview documents only, TTL for preview rows', 'large_import': live['large_import']}, (4, 5, 6, 7))
    evidence('duplicates', ['duplicate', 'title', 'isbn', 'existing'], {'strong_identity': ['Verified explicit global work', 'Checksum-valid ISBN plus compatible title/authors/publisher/year/edition'],
        'title_only': 'Possible duplicate; retains separate UUID/accession', 'conflicts': 'No silent merge. Existing strong identity requires an explicit skip/increase import policy; manual create returns 409.',
        'tenant_scoped': True}, (6,))
    evidence('local_global_linking', ['link', 'isbn', 'identity'], {'local_identity': 'UUID library_book_id is primary even for global-linked books', 'global_metadata': 'The existing books collection remains the shared catalogue; no clone of five million records.',
        'isbn_lookup': 'Optional existing read-only DuckDB mapping; only a unique work with compatible metadata and a verified live Mongo work can link. Missing/ambiguous mapping stays local.',
        'isbn_validation': 'ASCII ISBN-10/13 checksum, 978/979 prefix for ISBN-13, X only as ISBN-10 final check character; strips whitespace/hyphens only.',
        'later_link_unlink': 'Preserves UUID, accession, holding and local metadata', 'title_only_global_link': False, 'isbn_fabricated': False,
        'display_precedence': 'Explicit library-local metadata; linked work is a reference, not a live field-overwrite source.'}, (1, 3, 5, 9))
    evidence('legacy_aliases', ['alias', 'mapping', 'migration'], {'source_collection': 'library_inventory', 'alias_collection': 'institution_library_aliases', 'explicit_only': True,
        'default_legacy_identifier': 'No default in new inventory; LIB001 requires explicit UUID mapping.', 'ambiguous': 'Quarantine/report; never infer from library names or global roles.',
        'production_aliases_created': False, 'disposable_alias_apply': migration['apply']['aliases']}, (10,))
    evidence('private_inventory_security', ['roles', 'private', 'spoof', 'revocation', 'status', 'bound', 'account'], {'reads': 'ACTIVE members of the selected library, including GENERAL_USER; public inventory also uses this conservative rule.',
        'writes': 'ACTIVE ADMIN/LIBRARIAN membership; owner holds ADMIN. JWT global role never supplies tenant authority.',
        'current_account': 'Active, email-verified, known global identity role, no pending password setup; checked again inside inventory mutation gate.',
        'outsider_response': 404, 'general_write_response': 403, 'revoked_account_response': 401,
        'trusted_actor_and_tenant': 'Server JWT identity and path UUID; body library_id/actor/book UUID/accession/role are forbidden.',
        'search': 'Literal escaped regex inside mandatory library predicate; no global/private vector insertion.', 'audit': 'Allowlisted IDs, migration/version and numeric count summaries; no raw CSV rows, secrets or tokens.',
        'legacy_scope_limit': 'Legacy /inventory GET routes remain legacy compatibility behavior and are not claimed to provide private inventory isolation. They cannot query new canonical collections.'}, (8,))
    perf = read('performance'); raw = perf['metrics']['manual_book_create']['raw_ms']
    perf['metrics']['manual_book_create']['note'] = 'Contains sequential creates and queuing during 10/100-worker tests.'
    samples = raw[:4] + raw[-1:]
    perf['metrics']['manual_sequential_create'] = {'samples': len(samples), 'median_ms': round(statistics.median(samples), 3), 'p90_ms': sorted(samples)[math.ceil(.9 * len(samples)) - 1], 'raw_ms': samples,
        'derivation': 'First four manual samples and final prefix-rename creation; all other manual samples are concurrent.'}
    write('performance', perf)
    markdown('architecture', ARCHITECTURE)
    markdown('local_catalogue_architecture', LOCAL_ARCHITECTURE)
    markdown('part2b_scope', PART2B)
    markdown('improvement_review', REVIEW)
    audit_path = REPORTS / 'institution_v1_legacy_role_audit.md'
    marker = '\n## Part 2A inventory integration\n'
    audit_text = audit_path.read_text(encoding='utf8').split(marker)[0]
    audit_path.write_text(audit_text + marker + '\nThe accepted Part 1 classifications above remain the historical baseline. The following additions classify only the new inventory path.\n\n'
        '| Location | Classification | Authority and scope |\n|---|---|---|\n'
        '| backend/routes/library_inventory.py; library_inventory_access.py | NEW MEMBERSHIP-BASED | Current account eligibility and current UUID-library member/staff guards. |\n'
        '| library_catalogue_service.py; library_inventory_import.py | NEW MEMBERSHIP-BASED | Staff guards rechecked inside the persistent mutation gate; every repository predicate contains library_id. |\n'
        '| LibraryInventory.tsx; LibrarySwitcher.tsx; Institutions.tsx; InstitutionPanel.tsx | NEW MEMBERSHIP-BASED | Selected membership and server role control inventory admission; backend remains authoritative. |\n'
        '| StaffDashboard.tsx inventory navigation | NEW MEMBERSHIP-BASED | Opens current-library inventory; preserved old tabs are labelled Legacy global inventory / Legacy dataset import. |\n'
        '| backend/routes/inventory.py; inventory_service.py; inventory_import_service.py | MUST MIGRATE PART 2B | Preserved legacy APIs/collections use work_id and global staff roles; legacy GET inventory is public. New private records never enter that collection. |\n'
        '| Availability, issues, reservations, fines, events, notifications, digital assets | MUST MIGRATE THEIR LATER PHASE | No authority or storage migration in Part 2A. |\n', encoding='utf8')
    # Manifest names every changed/new first-party source and every delivered report.
    extensions = {'.py', '.ts', '.tsx', '.css', '.json'}
    paths = []
    for folder in ('backend', 'frontend/src', 'frontend/tests', 'scripts', 'tests'):
        paths.extend(p for p in (ROOT / folder).rglob('*') if p.is_file() and p.suffix in extensions and '__pycache__' not in p.parts)
    # The original source scan excluded data folders, including these two tracked
    # frontend fixture modules. They predate this work and are unchanged in Git.
    excluded = ['frontend/src/data/books.ts', 'frontend/src/data/categories.ts']
    for p in excluded:
        assert subprocess.run(['git', 'diff', 'HEAD', '--quiet', '--', p], cwd=ROOT).returncode == 0
    new = sorted(str(p.relative_to(ROOT)).replace('\\', '/') for p in paths if str(p.relative_to(ROOT)).replace('\\', '/') not in baseline['source_hashes'] and str(p.relative_to(ROOT)).replace('\\', '/') not in excluded)
    files = sorted(set(changed + new))
    manifest = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'changed_existing_source': changed, 'new_source': new,
                'additional_modified_report': 'reports/institution_v1_legacy_role_audit.md', 'baseline_excluded_unchanged_tracked_data': excluded,
                'source_hashes': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files},
                'reports': sorted(p.name for p in REPORTS.glob('institution_v2a_*') if p.is_file())}
    write('manifest', manifest)
    markdown('completion', completion(backend, v1, groups, frontend, live, perf, files, manifest))
    # Include the manifest and completion report themselves in the exact filename inventory.
    manifest['reports'] = sorted(p.name for p in REPORTS.glob('institution_v2a_*') if p.is_file())
    write('manifest', manifest)
    print(f'Part 2A reports: PASS; {len(changed)} existing source integrations, {len(new)} new source files, {len(manifest["reports"])} artifacts.')


ARCHITECTURE = r'''
# Institution Part 2A architecture

Part 2A adds a private catalogue and inventory snapshots to the accepted Institution V1 membership model. It does not migrate lending availability. Production `luminar_library` retains its five million global books, three legacy inventory rows and zero canonical libraries/catalogue rows; all migration/apply validation used disposable databases.

```mermaid
flowchart LR
  User[Authenticated current account] --> Guard[Current UUID library membership]
  Guard --> Inventory[Library-private inventory API]
  Inventory --> Local[LibraryBookRecord: UUID + accession]
  Local --> Holding[One canonical holding / inventory snapshot]
  Holding --> Copy[Optional known copy identities]
  Local -. optional verified reference .-> Global[Existing global books / work_id]
  Import[Bound CSV/XLSX preview] --> Inventory
  Legacy[Preserved library_inventory] --> Plan[Explicit alias + dry-run migration]
  Plan --> Inventory
```

## Models and boundaries

- `LibraryBookRecord`: UUID `library_book_id` + UUID `library_id`, immutable accession/sequence, optional `global_work_id`, title and at least one subject, optional bibliographic/local fields, source/status/review flag, timestamps and actor attribution. Local records can remain unlinked forever. Only local metadata is copied into canonical records; the shared catalogue is referenced.
- `LibraryHolding`: UUID holding ID, same-library book UUID, one holding per book, strict nonnegative total/available with available <= total, local shelf/call/tags/note, attribution and `INVENTORY_SNAPSHOT_NOT_CIRCULATION`. There is no write to the legacy availability source.
- `LibraryCopy`: UUID copy/book/holding/tenant references, monotonically allocated copy ordinal, optional barcode/date, status foundation. Only known barcodes are preserved during migration, with `UNVERIFIED` status. Aggregate historical quantities are not turned into invented copies. Borrowed/reserved states are storage foundations; the Part 2A API does not issue those transitions.

## Collections and indexes

| New collection | Indexes (in addition to Mongo `_id`) |
|---|---|
| institution_library_books | Unique library_book_id; unique library_id+accession_number; unique library_id+accession_sequence; partial library_id+work/ISBN10/ISBN13; library_id+normalized_title; library_id+status+sequence; partial unique library_id+source_key |
| institution_holdings | Unique holding_id; unique library_id+library_book_id |
| institution_copies | Unique copy_id; library_id+library_book_id; partial unique library_id+barcode; unique library_id+holding_id+copy_number |
| institution_sequences | Unique library_id+sequence_type |
| institution_library_aliases | Unique explicit legacy_library_id |
| institution_inventory_imports | Unique import_id; library_id+actor_user_id+created_at |
| institution_inventory_previews | Unique import_id; expires_at TTL |
| institution_inventory_migrations | Unique library_id+source_key |

V1 institution_libraries, memberships, invitations, security, audit and persistent locks are reused. Existing conflicting index specifications fail with an operator-review error; no existing index is dropped. Global books indexes and data remain unchanged.

## Atomic accession and mutation behavior

The sequence document is unique for `(library_id, BOOK_ACCESSION)`. `find_one_and_update` applies `$inc` atomically and returns the updated document; the prefix is frozen by `$setOnInsert`. A racing initial upsert that hits the unique index retries the increment against the existing counter. Mongo documents its [single-document atomic updates](https://www.mongodb.com/docs/manual/core/write-operations-atomicity/) and [`findAndModify` behavior](https://www.mongodb.com/docs/manual/reference/method/db.collection.findandmodify/).

Accessions use a stable first-three-character uppercase ASCII alphanumeric prefix or `LIB`, a hyphen and at least six digits. Numbers can exceed six digits. Prefixes may coincide across institutions; only the tuple with canonical library UUID is unique. UUIDs remain the external resource identity. Numbers are never decremented/reused, even after withdrawal or failed writes. Preview has no sequence call.

The local Mongo server is standalone. Multi-document mutations therefore reuse V1's cross-worker persistent lock. Inventory callers wait up to 30 seconds; V1 callers retain their accepted three-second default. Authorization is checked inside the lock. Reads fail closed while a mutation is in progress. Records start `PROVISIONING` and become `ACTIVE` after their holding and audit writes. Unknown write outcomes retain the lock: an operator must stop workers, inspect/reconcile the specific tenant, and only then repair/unlock. No stale-lock TTL grants a competing writer authority. This favors correctness over availability; it is not a replica-set transaction guarantee.

## HTTP and UI

All new routes start `/libraries/{UUID}/inventory`. They support list/create/detail/metadata patch/soft withdrawal, holding snapshot update, explicit global link/unlink, paginated copy list and copy registration, protected import preview/apply/status. Search is bounded literal matching over local title/subjects/authors/ISBN/accession/call number. Body fields cannot supply library/actor/accession/book IDs or roles.

ACTIVE members may read; ADMIN/LIBRARIAN may write; the owner is an ADMIN membership. The account must remain active and verified with no unfinished password setup. Public inventory uses the same conservative member-only visibility. A global ADMIN without membership is an outsider. Current role and eligibility are rechecked on import apply. Audit records contain allowlisted identifiers and counts, never raw datasets/credentials.

`/library-inventory` integrates with the active-library switcher, library home and Institution staff panel. The add form requires only title/subjects and collapses optional fields. Dataset upload supplies a minimal template, preview classifications and row errors, explicit existing-item policy and retained apply results. Legacy inventory/import tabs remain usable and are clearly labelled. UI admission is backed by server role responses; library/session changes clear stale inventory.

## Import and migration

CSV UTF-8/BOM and XLSX are bounded to 5 MiB, 2,000 rows and 40 columns; XLSX expansion is capped at 25 MiB. Formulas are never executed. Explicit header aliases and bounded field normalization apply the same metadata rules as manual creation. IDs, tenancy and accession headers are rejected.

Preview persists only a protected job and normalized rows, bound to actor, library, SHA-256 and one-hour expiry. Apply rechecks eligibility, membership, work references and current duplicate state, stores row outcomes and a replayable result. New rows use per-import/per-row source keys. Invalid rows are isolated. Same title never merges records. Verified work or validated ISBN plus compatible metadata is strong identity; existing-item quantity increase is explicit and audited.

Migration/ID assignment default to a read-only plan. They require an existing active canonical library UUID and explicit aliases. Missing title/subject is reported; a verified legacy work can supply genuinely existing missing metadata. No LLM runs. Apply creates canonical overlays and leaves legacy inventory/loans untouched. Per-source migration markers make repeat apply idempotent. Reconciliation checks same-tenant references, quantities, identities/accessions, links, copy counts and sequence high-water marks.

## Validation and limits

See regression/live/performance/browser reports for the exact measurements and suite evidence. No Router V1–V5 research evaluations or model work ran. Global search, recommendations, KG, RAG and Assistant algorithms match the 754-file baseline; only eight existing integration files changed. Inventory counts must not be presented as tenant lending availability before Part 2B.
'''

LOCAL_ARCHITECTURE = r'''
# Local catalogue and global catalogue

The global `books` collection keeps its existing work IDs and five million records. Each library owns a separate local UUID catalogue, including books with no ISBN, author or external identifier. Its holding references the local UUID. A `global_work_id` is an optional verified reference; it is never the tenant book's primary identity.

Local metadata is authoritative for inventory display. An explicit link preserves title, subjects, ISBN and local details, holding, copy IDs, UUID and accession. Unlink preserves the entire local record. A link does not confer PDF access, Borrow/Read eligibility or a digital capability. Those require separate assets/circulation architecture.

ISBN-10/13 validation checks length, ASCII digits/check character, checksum and ISBN-13's 978/979 prefix. Missing values stay null. No leading zeros or ISBNs are fabricated. The [International ISBN Agency](https://www.isbn-international.org/content/what-isbn/10) describes the ISBN structure and check digit. Optional existing read-only DuckDB mappings can identify a unique work, which must also exist in Mongo and have compatible title/authors/publisher/year/edition. Conflicts, missing mappings and ambiguous mappings remain local. Explicit staff links must resolve to a live work. Title alone never supplies a global identity.

Tenant duplicate checks use verified work identity or validated ISBN with compatible metadata. Same-title-only records are retained separately and flagged for review. Work/ISBN indexes are not globally unique local-record constraints: editions, withdrawals and future reviewed reconciliation need a safe representation. Service serialization enforces active strong-identity conflict handling.

Local search requires current membership and always includes canonical `library_id`. It escapes regex input and searches a stored local text field; no user regex or global vector insertion occurs. Tests measure about 1.5k records. The current substring scan is not established as sufficient at 10k/100k. Benchmark indexed tenant/token/text options before larger deployments. A future authorized search overlay should retrieve global semantic results independently, retrieve only the selected authorized local tenant, then combine results in the caller's response. Never put private records in the shared HNSW/FAISS index.
'''

PART2B = r'''
# Recommended Part 2B scope — planned only

Part 2A is complete. No implementation below has begun. Current inventory snapshots are not lending availability. Inspection of actual code shows why the next migration must cover the whole lending mutation, rather than add a UI filter.

## Current dependencies

| File/flow | Actual current behavior | Required Part 2B change |
|---|---|---|
| backend/services/availability_service.py | DEFAULT_LIBRARY_ID=`LIB001`; work-ID lookup in library_inventory, then global books fallback | Require authorized library UUID/local book UUID; canonical holding/copy availability; remove cross-tenant fallback for physical lending |
| backend/services/issue_service.py | issue_book defaults LIB001; loan stores work_id/book_id/source/library_id; conditional decrement in legacy physical inventory or global books precedes issue insert | Store canonical library/book/holding IDs, optional copy ID and global reference snapshot; same-tenant conditional allocation and durable idempotent loan write |
| backend/services/issue_service.py return_book | Returns to loan inventory_source and library_id, defaults missing fields to catalogue/LIB001; increments old source, then advances a work-ID reservation queue | Persist and use original canonical source; single-return receipt/CAS; release exactly one allocated unit/copy; prevent double increment |
| backend/services/loan_renewal_service.py | Optimistic due-date CAS + renewal receipts already exist; reservations are queried by work_id across readers | Keep renewal idempotency/policy, add library+local-book predicates and same-tenant staff/borrower authorization |
| backend/services/reservation_service.py | Work-ID availability/queue and notification source references | Define a compatible transition adapter so allocation cannot release a copy into another library's legacy queue; broader reservation migration remains explicitly separately approved |
| backend/routes/issues.py | POST /issues/issue, /issues/return/{issue_id}; global-role assisted operations | Add required current library context and centralized membership/loan ownership guards |
| backend/routes/renewals.py | GET /issues/{issue_id}/renewal, POST /issues/{issue_id}/renew, assisted staff endpoint | Reauthorize loan tenant and preserve receipts; do not infer authority from JWT ADMIN |
| backend/routes/inventory.py | Legacy inventory GET is public; mutations use global staff role | Protect/retire or explicitly restrict legacy reads for migrated inventory; keep rollback adapter until cutover completes |
| frontend/src/lib/api.ts; book detail/card, My Library, staff issue screens, LoanRenewalControl | Borrow actions and availability use shared work IDs/legacy APIs | Pass explicit selected UUID context; render canonical physical availability separately from global digital capabilities |
| Assistant library operation tools | Existing availability/actions target current legacy flows | Keep existing_qwen/routing; bind authorized selected-library arguments at tool boundary only after new lending endpoints pass gates |

## Recommended architecture

Continue **aggregate holding + optional copies** initially. Actual issue/return code allocates aggregate quantities and stores no historical copy ID. Forcing every quantity into a copy record would invent borrower/copy associations and lose an honest migration path. Where genuine copy/barcode records exist, allocate a known AVAILABLE copy with conditional state transition; otherwise allocate an aggregate unit and mark that loan's allocation mode explicitly. Materialize all future individually tracked acquisitions through controlled staff workflows. Resolve `UNVERIFIED` historical barcodes before treating them as circulating copies.

Make one canonical availability service own transitions. LibraryHolding total is physical stock; circulation availability must be derived/maintained consistently with active loans, reservations and unavailable copy states under the chosen allocation mode. The Part 2A snapshot needs a reconciled cutover baseline, not continuous dual writes from two masters. Prefer replica-set transactions across holding/copy/loan/receipt when deployed. On standalone Mongo retain durable serialization and an explicit recoverable journal; never expire a lease without fencing a stale writer. Separate tenant/profile lock granularity only after membership revocation and allocation ordering remain safe.

Collections involved: institution_library_books, institution_holdings, institution_copies, institution_library_aliases, sequences, audit, current issues/borrow_locks and their new receipt/journal/index schema; reservations/fines/notifications only through deliberate compatibility boundaries. Each loan requires UUID library/book/holding references and optional copy reference, while retaining legacy IDs and source attribution for traceability. Unique idempotency keys include tenant and actor/action identity. No actor or library authority comes from request body fields.

## Recommended migration order

1. Inventory all legacy sources and active/returned issues by library_id, inventory_source and work_id. Resolve explicit aliases and quarantine unmapped/missing/ambiguous loans; inspect reservations that can affect allocation. No default LIB001 assignment for missing evidence.
2. Stop lending writes during a rehearsed cutover window, back up exact involved collections, reconcile canonical stock versus legacy current quantities and active loans. Freeze the previously independent Part 2A snapshot.
3. Add canonical loan references/receipts/indexes additively in a dry run, then explicit apply; preserve historical IDs and counts. Do not assign invented copy IDs to old aggregate loans. Resolve known copy status through actual evidence/operator verification.
4. Implement/test canonical availability + borrow conditional allocation and durable idempotent loan creation, including compensation/recovery on unknown commit outcomes. Switch one library at a time behind a rollback boundary; never decrement global books for that library's physical loan.
5. Migrate return against the original canonical source, exactly-once increment/release; adapt reservation handoff enough to prevent cross-tenant allocation, with explicit scope approval for any wider reservation behavior.
6. Bind renewal eligibility/receipts and staff operations to the canonical loan's library; preserve existing due-date/renewal policy and notification idempotency.
7. Cut frontend physical availability and borrow/return/renew actions over to new endpoints; verify multi-membership switching, stale requests and membership removal.
8. Bind Assistant tool actions to authorized selected context after direct APIs pass. Reconcile stock/loans/copies after concurrency and failure injection; disable old mutation paths for migrated libraries. A rollback must restore a consistent source snapshot, never run both availability masters.

## Required race and regression checks

Two borrowers/last aggregate unit; two requests/last copy; duplicate borrow request; issue insert failure after decrement; stale writer/recovery; double return; return concurrent with another borrow; member removal/role change during mutation; same global work in two libraries; private outsider/global ADMIN without membership; old missing tenant loan; cross-tenant reservation blocks; renewed loan returned while stale renewal retries; exactly-once activity/notification/fine side effects. Preserve existing staff/auth, 40 renewal tests, reservation/fine checks, frontend actions and Assistant selected-context behavior. Never change Qwen, embeddings, global ranking or RAG algorithms for this cutover.

Fees, full reservation tenancy, Events, Notifications, RAG assets, private semantic vectors and recommendation/search overlays require their own explicit later scope. Part 2B recommendations here do not authorize their implementation.
'''

REVIEW = r'''
# Institution Part 2A improvement review

## Executive Summary

The shipped foundation supports honest local identity with minimal metadata, stable atomic accessions, protected catalogue/holding snapshots and explicit migration. It passes the requested foundation gates. Lending remains legacy and must not be described as tenant isolated. Recommendations below are based on current code; deferred items were not implemented.

Every recommendation row states title, why, current limitation, recommended change, priority, implementation phase, breaking change and migration requirement. NOW rows describe completed Part 2A hardening.

## Critical Findings

| Title | Why it matters | Current limitation | Recommended change | Priority | Implement | Breaking change | Migration required |
|---|---|---|---|---|---|---|---|
| Tenant lending cutover | Physical borrow/return must never affect another institution | availability_service still defaults LIB001 and falls back to global books; issues mutate those sources | Execute the staged canonical availability/loan cutover in part2b_scope.md; guard legacy public inventory reads for migrated tenants | CRITICAL | PART_2B | YES | YES |
| Unknown multi-document outcome recovery | Interrupted writes must not grant partial authority or duplicate stock | Standalone Mongo lacks a transaction across book/holding/audit; V1 lock remains on unexpected errors | Preserve fail-closed gate now; add operator recovery runbook and tested journal/transaction cutover before lending | CRITICAL | PART_2B | NO | YES |
| Current account revocation | A stale valid JWT must not admit a disabled account to private inventory | JWT alone is insufficient | Implemented current_identity eligibility wrapper before V1 member/staff guards, rechecked inside inventory writes/apply | CRITICAL | NOW | NO | NO |

## High Priority

| Title | Why it matters | Current limitation | Recommended change | Priority | Implement | Breaking change | Migration required |
|---|---|---|---|---|---|---|---|
| Long import orchestration | 1000-row apply takes seconds and holds tenant gate | Synchronous HTTP and one tenant-wide gate; reads fail closed | Add resumable background jobs with durable per-row journal and explicit membership rechecks before each safe batch; preserve allocation/replay semantics | HIGH | LATER | NO | YES |
| Known copy verification | Historical barcodes do not establish borrower/status identity | Migration correctly stores UNVERIFIED; old loans lack copy_id | Use aggregate allocation first; verify real copy states and add controlled copy tracking for new stock in Part 2B | HIGH | PART_2B | YES | YES |
| Mutation queue capacity | Concurrent imports/creates should not time out after a short profile-edit deadline | Inherited gate default was three seconds | Implemented bounded 30-second inventory wait; retained V1 default and fail-closed recovery | HIGH | NOW | NO | NO |
| Explicit source duplicate reconciliation | Multiple legacy rows can refer to one strong book identity | Default skip preserves safety but does not infer desired quantity aggregation | Implemented explicit increase_quantity option, audit and preservation of a known same-tenant barcode; operator chooses policy | HIGH | NOW | NO | NO |

## Medium Priority

| Title | Why it matters | Current limitation | Recommended change | Priority | Implement | Breaking change | Migration required |
|---|---|---|---|---|---|---|---|
| Local search at 10k/100k | Bounded responses do not make an unanchored substring scan scale | Only ~1.5k records measured; search scans tenant text | Benchmark 10k/100k with query plans; consider tenant-aware token/text indexes, seek pagination and query timeout | MEDIUM | LATER | NO | YES |
| Reviewed duplicate merge | Same titles legitimately remain separate | No merge/redirect UI and no accession alias model | Add human-confirmed merge preserving holdings/copies/audit/history and old accession aliases; never silent title-only merge | MEDIUM | LATER | YES | YES |
| Bibliographic match confirmation | ISBN metadata can differ across editions/authors | Only unique mapping plus compatible fields auto-links; explicit staff work reference can still be mistaken | Add candidate selection with author/title/year evidence and human confirmation; retain local UUID and metadata | MEDIUM | LATER | NO | NO |
| Copy list administration | Large genuine copy registers need full navigation | API is paginated; minimal UI displays first 100 and no editing workflow | Add copy pagination/verification/lost/damaged/withdraw actions with lending-aware checks after allocation is defined | MEDIUM | PART_2B | NO | NO |
| Private authorized search overlay | Local books should be discoverable without leaking vectors | New records are isolated from global search | Add independent authorized tenant retrieval and response-layer overlay; optional per-tenant index ACLs only after measured need | MEDIUM | LATER | NO | YES |
| Asset identity separation | Book metadata does not prove permission to read a PDF | No tenant digital asset model yet | Define LibraryDigitalAsset with asset ownership, ACL, retention and content-source references; keep catalogue linking independent | MEDIUM | LATER | NO | YES |

## Nice to Have

| Title | Why it matters | Current limitation | Recommended change | Priority | Implement | Breaking change | Migration required |
|---|---|---|---|---|---|---|---|
| Legacy accession alias | Institutions may already label physical stock | Auto accessions generated; imported accession fields rejected to protect immutable numbering | Add separate existing_accession_number/alias with tenant uniqueness and reviewed preservation mode; keep auto default | NICE_TO_HAVE | LATER | NO | YES |
| Branch/campus labels | Staff may need shelf routing across sites | Stable three-character prefix can coincide; no branch entity/evidence in current repository | Keep current scheme; add separate branch/campus metadata if product evidence justifies it, without renumbering existing accessions | NICE_TO_HAVE | LATER | NO | YES |
| Library-only visibility opt-in | Some public libraries may choose public stock discovery | Conservative member-only inventory is intentional | Add explicit public-inventory policy with field redaction, tests and staff consent; PRIVATE remains member-only | LOW | LATER | NO | NO |
| Split inventory UI bundle | Additional inventory code joins the main app chunk | Existing main chunk remains over 500 kB | Measure route use and lazy-load large staff/inventory routes without changing accepted header flows | LOW | LATER | NO | NO |

## Data Model Review

UUID local book identity is adequate for unidentified and linked books. One holding per local book prevents work-ID coupling. Optional known copies match actual aggregate circulation code; compulsory copy expansion would fabricate history. Local metadata attribution is retained and global links never overwrite it. Copy status is a foundation, not current lending authority. Add concurrency/versioned edit protection when simultaneous catalogue staff edits become a demonstrated product issue; current serialized edits are intentionally last-successful-write.

## Accession Review

`PREFIX-000001` remains adequate within a canonical UUID tenant. Unique scoped indexes and atomic persistent counters pass direct 10/100-worker allocation and real create stress. Numbers expand beyond six digits, never reset/reuse, and prefix survives rename. Shared prefixes across institutions are acceptable because accession strings are not global IDs. Do not redesign for hypothetical campuses. Future imported accession aliases should be separate from immutable generated numbers.

## Migration Review

Explicit aliases, existing active library/staff attribution, read-only dry run, per-source markers and reconciliation are implemented. No production apply happened. Missing subject/title and conflicting/unresolved identities require operator correction or trusted existing global metadata. Legacy collection preservation is essential until whole lending cutover. For very large migrations, stream report details/batch reconciliation and attach backup/checkpoint manifests; current report and reconcile lists grow with tenant/source size.

## Tenant Security Review

All new predicates include canonical tenant UUID. Account eligibility and current membership protect reads/writes; globally privileged users gain no tenant access without membership. Import jobs also require their original actor. Private records do not enter global search/RAG indexes. Current snapshots do not remove legacy API/global-role debt; it is explicit in the Part 2B plan and role audit. Administrative Mongo access remains outside application ACL guarantees.

## Import Review

UTF-8 CSV/XLSX, precise aliases, metadata/quantity validation, strict spoof rejection, file/row/column/expanded-archive bounds, inactive-link recheck, preview TTL/binding and replay are implemented. Optional ISBN lookup is read-only and fail-local. Preview duplicate comparison within a file is quadratic at the capped 2000 rows; replace with hash-based candidate buckets only if measured larger imports are introduced. Do not raise caps without load/failure testing.

## Duplicate Review

Verified work or validated ISBN with compatible bibliographic fields is strong identity. Same title is only a review hint, including same-title/different-subject cases. No silent merge is permitted. Manual merge tooling must preserve loan/copy/holding attribution and accession aliases after circulation semantics are established.

## Scalability Review

See raw median/p90 measurements in performance.json. Single 1000-row samples have no asserted p90. Mongo tenant/status/identity indexes bound the scope but do not accelerate arbitrary substring search. The measured 1k use case passes; 10k/100k sufficiency is unproven. Synchronous apply and tenant-wide read exclusion are the immediate operational limits. Replica-set transactions and background journals should precede a larger circulation workload, rather than private vector infrastructure.

## Part 2B Recommendation

Use aggregate holdings with optional genuinely known copies, explicit allocation mode and one canonical availability source. Add tenant-bound loan IDs, conditional allocation, exactly-once return and retained renewal receipts. Reconcile/freeze snapshots at cutover, preserve legacy traceability and stop competing legacy writes. Follow the collections/endpoints/frontend/race tests and ordered migration in part2b_scope.md. No Part 2B change has been implemented.

## Deferred Features

Availability/borrow/return/renew migration, broad reservation/fee tenancy, Events, Notifications, tenant RAG assets, Assistant actions, global-search availability overlays, recommendation overlays, merge tooling, branch entities, optional private vectors and model work are deferred.

## Things That Should NOT Be Changed Yet

Do not redesign Institution V1 hierarchy/private codes/invitations. Do not renumber local UUIDs/accessions, invent ISBN/subjects/authors/barcodes, clone the global catalogue, force historical quantities into known copies, insert private records into global HNSW, alter global ranking/KG/RAG/embeddings/Qwen, or turn stock metadata into digital read capabilities. Do not run Router V1–V5 research evaluations for this phase.
'''


def completion(backend, v1, groups, frontend, live, perf, files, manifest):
    metrics = perf['metrics']
    sections = [
        ('A', 'FINAL STATUS', 'PASS — Part 2A only. No production migration applied.'),
        ('B', 'ARCHITECTURE', 'Protected UUID-library catalogue + holdings snapshots + optional copies; accepted V1 guards and standalone persistent gate reused.'),
        ('C', 'GLOBAL VS LOCAL', 'Shared books stays unchanged; each tenant owns local records with optional verified work reference. Local fields remain authoritative.'),
        ('D', 'LIBRARYBOOKRECORD', 'UUID book/library, immutable accession/sequence, title+subjects, nullable ISBN/work, optional metadata, source/status/review/attribution.'),
        ('E', 'LIBRARYHOLDING', 'One UUID holding per same-tenant local book; strict 0 <= available <= total; inventory snapshot semantics.'),
        ('F', 'COPY FOUNDATION', 'UUID copy and same-tenant references, ordinal, optional barcode/date/status. Legacy known barcodes UNVERIFIED; no aggregate expansion.'),
        ('G', 'ACCESSION', 'Persistent tenant counter, PREFIX-000001 with growing digits, stable prefix, immutable/no reuse. Preview allocates none.'),
        ('H', 'ACCESSION CONCURRENCY', 'Direct 10/100-worker atomic allocation passes. Real 10/100-worker HTTP creation has zero duplicate accessions.'),
        ('I', 'MINIMUM METADATA', 'Only nonempty title and at least one subject required. Unknown identifiers remain null; authors may be empty; quantity defaults to one.'),
        ('J', 'MANUAL FLOW', 'Select membership → Add Book → title/subjects → server creates UUID/accession/holding. Other fields collapse as optional.'),
        ('K', 'DATASET FLOW', 'Bounded CSV/XLSX → protected preview → explicit policy/confirm → row results. UTF-8/BOM, semicolon values, precise aliases.'),
        ('L', 'PREVIEW', 'NEW_LOCAL/GLOBAL_MATCH/EXISTING_HOLDING/POSSIBLE_DUPLICATE/INVALID; actor/library/hash/expiry bound; no catalogue/holding/counter writes.'),
        ('M', 'GLOBAL LINKING', 'Existing work must resolve; optional unique ISBN mapping plus compatible metadata; later link/unlink retains UUID/accession/local fields.'),
        ('N', 'LOCAL ONLY', 'A valid unidentified book remains a first-class tenant record forever; no fake work/ISBN or mandatory author.'),
        ('O', 'ISBN', 'Checksum-valid ASCII ISBN-10/13 only; optional read-only lookup; no leading-zero padding or generated identifiers.'),
        ('P', 'DUPLICATES', 'Strong identity conflicts detected per tenant. Title-only remains separate/reviewed. Explicit skip/increase applies to existing holdings.'),
        ('Q', 'SEARCH', 'Literal bounded tenant-scoped local title/subject/author/ISBN/accession/call search; no global Search API/vector changes.'),
        ('R', 'PRIVATE SECURITY', 'ACTIVE members only; outsider 404, general write 403, revoked account 401. All predicates and imports bound to path UUID.'),
        ('S', 'ROLES', 'Owner ADMIN, ADMIN/LIBRARIAN write, GENERAL_USER read. Global ADMIN is not a membership bypass.'),
        ('T', 'ALIASES', 'Explicit LEGACY_ID=UUID only; no LIB001/name/global-role guessing. Ambiguous mappings reported.'),
        ('U', 'LEGACY MIGRATION', 'Canonical overlay preserves old collection/loans. Trusted existing global metadata fallback allowed; missing required metadata quarantined.'),
        ('V', 'DRY RUN', 'Default CLI read-only, including no new collection/index or accession allocation. Disposable four-row fixture: three ready, one missing subject.'),
        ('W', 'APPLY', 'Explicit --apply creates three canonical records/holdings/accessions in fixture; a genuine barcode preserved UNVERIFIED.'),
        ('X', 'IDEMPOTENCE', 'Repeated fixture apply creates zero; unique source markers/import row keys and stored result replay protect repeat operations.'),
        ('Y', 'RECONCILIATION', 'All three live fixture libraries PASS: IDs/accessions/quantities/references/links/copies/counter high-water marks.'),
        ('Z', 'INVENTORY UX', 'Current library context, server role, local/global/review/withdraw badges, filters/search/paging and stable identifiers.'),
        ('AA', 'ADD UX', 'Two required fields; optional bibliographic/library/link details; immutable accession shown on edit; no Borrow/Read coupling.'),
        ('AB', 'IMPORT UX', 'Minimal template, visible bounds/aliases, row errors/counts, explicit existing policy, retained partial/completed results.'),
        ('AC', 'RESPONSIVE', '24 screen/size checks PASS; 1440,1366,1024,768,390,375 widths; actual CSS dimensions recorded, including one-pixel Windows scaling differences.'),
        ('AD', 'LIVE', 'Scenarios 1–10 PASS over real HTTP/Mongo/Vite; browser minimal create and partial import pass; fixtures cleaned.'),
        ('AE', 'CONCURRENCY', 'Two simultaneous 100-row tenant imports; 10/100-worker manual creates; 20-user isolation; zero duplicate accessions.'),
        ('AF', 'PERFORMANCE', f"Local sequential create median {metrics['manual_sequential_create']['median_ms']} ms; list {metrics['inventory_list']['median_ms']} ms; search {metrics['inventory_search']['median_ms']} ms; 1000-row preview/apply {metrics['preview_1000_rows']['median_ms']}/{metrics['apply_1000_rows']['median_ms']} ms. Raw data and sample limits in performance.json."),
        ('AG', 'BACKEND', f"{backend['passed']} new Part 2A tests PASS; final 10/100-worker allocation recheck PASS."),
        ('AH', 'FRONTEND', '230 full-chain + 156 extended = 386 passed executions, including 26 inventory tests. Final inventory-only rerun also passes.'),
        ('AI', 'REGRESSION', f"{v1['passed']} accepted V1 tests PASS; frozen groups: {sum(g['passed'] for g in groups)} passed, {sum(g['skipped'] for g in groups)} existing skips, zero failures. No Router V1–V5 runs."),
        ('AJ', 'BUILD/LINT', 'Build PASS; lint zero errors/new inventory warnings. Existing 19 lint warnings and >500 kB main-bundle advisory remain.'),
        ('AK', 'EXACT FILES', 'See complete source listing below and manifest.json; eight existing integration sources changed. Prior user changes retained.'),
        ('AL', 'COLLECTIONS/INDEXES', 'Eight new institution_* collections; exact table in architecture.md. Unique local identity/accession/holding/barcode/source keys; TTL only preview.'),
        ('AM', 'SCRIPTS', 'assign_library_book_ids.py, migrate_inventory_v2a.py, inventory_v2a_migration.py, reconcile_inventory_v2a.py, check_institution_v2a_live.py, test_institution_v2a_regressions.py, report_institution_v2a.py.'),
        ('AN', 'REPORTS', 'All requested JSON/Markdown reports plus XML/logs, source-preservation manifest, browser geometry/screenshots and cleanup artifacts; manifest lists exact names.'),
        ('AO', 'LIMITS', 'Lending/availability/reservations/fees remain legacy. Snapshot counts are not lending truth. Synchronous import locks tenant reads; substring search unproven at 10k/100k; UI copy list is minimal.'),
        ('AP', 'IMPROVEMENTS', 'Complete 15-section evidence-based review with every recommendation priority/phase/breaking/migration flags.'),
        ('AQ', 'CRITICAL', 'Canonical lending cutover and durable unknown-commit recovery are Part 2B; current account eligibility already hardened in Part 2A.'),
        ('AR', 'HIGH', 'Background resumable imports later; genuine copy verification/aggregate allocation in Part 2B. Bounded queue wait and explicit migration duplicate policy implemented now.'),
        ('AS', 'MEDIUM', '10k/100k tenant search benchmark/indexing, reviewed duplicate merge, candidate-link confirmation, copy administration, authorized private search overlay and separate digital assets.'),
        ('AT', 'NICE TO HAVE', 'Separate existing-accession aliases; branch/campus metadata only with evidence; opt-in public inventory policy; route bundle splitting.'),
        ('AU', 'PART 2B ARCHITECTURE', 'One canonical availability source; aggregate holding + optional genuine copies; tenant-bound loan/allocation/receipt journal; exactly-once return and retained renewal CAS.'),
        ('AV', 'PART 2B ORDER', 'Explicit mapping/quarantine → freeze/reconcile/backup → additive loan refs → availability/borrow → return → renewal → frontend → Assistant tool context → reconciliation/cutover retirement.'),
        ('AW', 'DEFERRED', 'Availability/loans/reservations/fees, Events/Notifications, digital/RAG assets, Assistant tenant actions, semantic/global search and recommendations overlays; all model work.'),
        ('AX', 'NOT IMPLEMENTED', 'All PART_2B/LATER recommendation rows remain plans. No automatic continuation beyond Part 2A.'),
        ('AY', 'COMMANDS', 'Exact PowerShell run/test/dry-run/apply/reconcile commands below; an actual canonical UUID and explicit legacy alias are required.')]
    rows = '\n'.join(f'| {code} | {title} | {detail} |' for code, title, detail in sections)
    listed = '\n'.join('- `' + p + '`' for p in files)
    return '# Institution Part 2A completion\n\n| Item | Topic | Result |\n|---|---|---|\n' + rows + '\n\n## Exact source changes\n\n' + listed + r'''

Additional updated report: `reports/institution_v1_legacy_role_audit.md` (appended Part 2A-only inventory classification). `manifest.json` contains hashes and all report filenames. No dependency changes, production database writes, model calls or commits were made.

## Run and migration commands

```powershell
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
```

In another terminal (frontend existing Vite default API target is port 8002):

```powershell
Set-Location D:\SDC\LibraryLLM\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Register/join an Institution V1 library in the UI, select it, then open `http://127.0.0.1:5173/library-inventory`. Production currently has no canonical library, so migration requires an actual new registration or explicitly approved V1 migration first. Part 2A does not infer an owner/UUID from LIB001.

Read-only migration/ID planning, explicit apply, repeat and reconciliation:

```powershell
Set-Location D:\SDC\LibraryLLM
$targetLibraryId = 'REPLACE_WITH_ACTUAL_CANONICAL_LIBRARY_UUID'
.\.venv\Scripts\python.exe scripts\assign_library_book_ids.py --database luminar_library --library-id $targetLibraryId --alias "LIB001=$targetLibraryId" --report reports\inventory_id_plan.json
.\.venv\Scripts\python.exe scripts\migrate_inventory_v2a.py --database luminar_library --library-id $targetLibraryId --alias "LIB001=$targetLibraryId" --report reports\inventory_migration_plan.json
.\.venv\Scripts\python.exe scripts\migrate_inventory_v2a.py --database luminar_library --library-id $targetLibraryId --alias "LIB001=$targetLibraryId" --apply --report reports\inventory_migration_apply.json
.\.venv\Scripts\python.exe scripts\migrate_inventory_v2a.py --database luminar_library --library-id $targetLibraryId --alias "LIB001=$targetLibraryId" --apply --report reports\inventory_migration_repeat.json
.\.venv\Scripts\python.exe scripts\reconcile_inventory_v2a.py --database luminar_library --library-id $targetLibraryId --report reports\inventory_reconciliation.json
```

Default existing-item policy is `skip`. Add `--existing-policy increase_quantity` only when explicit quantity aggregation is the intended migration result. Scripts are idempotent overlays; do not run both assignment and migration apply expecting two copies of the same source. Dry-run is the default and the placeholder UUID intentionally fails until replaced.

Validation commands (separate processes are required for V1/V2A disposable database fixtures):

```powershell
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe -m pytest tests\institution_v2a -q --junitxml=reports\institution_v2a_backend_final.xml
.\.venv\Scripts\python.exe -m pytest tests\institution_v1 -q --junitxml=reports\institution_v2a_regression_institution_v1.xml
.\.venv\Scripts\python.exe scripts\test_institution_v2a_regressions.py
.\.venv\Scripts\python.exe scripts\check_institution_v2a_live.py
Set-Location D:\SDC\LibraryLLM\frontend
npm test
npx tsx --tsconfig tsconfig.app.json --test tests/events.test.tsx tests/admin-notifications.test.tsx tests/search-depth.test.tsx tests/knowledge-graph.test.tsx tests/kg-product.test.tsx tests/loan-renewal.test.tsx tests/document-cache.test.tsx tests/rag-answer.test.tsx tests/mind-map.test.tsx tests/part3-contract.test.tsx
npm run build
npm run lint
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe scripts\report_institution_v2a.py
```

Stop after Part 2A. Part 2B requires the user's explicit next instruction.
'''


if __name__ == '__main__': main()
