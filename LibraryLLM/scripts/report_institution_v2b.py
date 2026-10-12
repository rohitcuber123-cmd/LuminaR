"""Build the Part 2B handoff from saved, successful executions and source hashes."""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
PREFIX = 'institution_v2b_'


def read(name):
    return json.loads((REPORTS / f'{PREFIX}{name}.json').read_text(encoding='utf8'))


def write(name, data):
    (REPORTS / f'{PREFIX}{name}.json').write_text(json.dumps(data, indent=2, default=str) + '\n', encoding='utf8')


def markdown(name, data):
    (REPORTS / f'{PREFIX}{name}.md').write_text(data.strip() + '\n', encoding='utf8')


def xml(name):
    filename = f'{PREFIX}{name}.xml'
    cases = list(ET.parse(REPORTS / filename).iter('testcase'))
    return {'artifact': filename, 'tests': len(cases),
        'passed': sum(not any(c.tag in ['failure', 'error', 'skipped'] for c in t) for t in cases),
        'failed': sum(any(c.tag in ['failure', 'error'] for c in t) for t in cases),
        'skipped': sum(any(c.tag == 'skipped' for c in t) for t in cases),
        'cases': [t.attrib.get('classname', '') + '::' + t.attrib['name'] for t in cases]}


NEW = '''backend/routes/library_lending.py
backend/schemas/library_lending.py
backend/services/library_lending_service.py
backend/services/library_lending_journal.py
backend/services/library_lending_legacy.py
assistant/lending_boundary.py
frontend/src/lib/libraryLending.ts
frontend/src/pages/LibraryCirculation.tsx
frontend/src/components/LibraryStockEditor.tsx
frontend/src/components/LibraryCopyControls.tsx
frontend/src/components/AssistantLibraryRequestButton.tsx
frontend/tests/institution-lending.test.tsx
tests/institution_v2b/conftest.py
tests/institution_v2b/test_lending.py
tests/institution_v2b/test_boundaries.py
tests/institution_v2b/test_recovery_edges.py
scripts/lending_v2b_operations.py
scripts/migrate_lending_v2b.py
scripts/reconcile_lending_v2b.py
scripts/check_institution_v2b_live.py
scripts/test_institution_v2b_regressions.py
scripts/report_institution_v2b.py'''.splitlines()


def main():
    baseline, live, browser, geometry, cleanup = [read(n) for n in ['baseline', 'live', 'browser_live', 'browser_geometry', 'cleanup']]
    backend, v1, v2a = [xml(n) for n in ['backend', 'v1', 'v2a']]
    assert backend['tests'] == backend['passed'] == 57
    assert v1['tests'] == v1['passed'] == 56 and v2a['tests'] == v2a['passed'] == 95
    assert live['status'] == browser['status'] == geometry['status'] == 'PASS'
    assert len(live['scenarios']) == 13 and all(s['status'] == 'PASS' for s in live['scenarios'])
    assert cleanup['fixture_database_dropped'] and cleanup['own_services_stopped']
    assert all(s['scrollWidth'] <= s['width'] for s in geometry['screens'])
    groups = [xml('regression_' + n) for n in ['unit', 'assistant', 'security', 'staff', 'notifications', 'circulation', 'search', 'private_knowledge_ocr', 'kg', 'events']]
    assert all(g['failed'] == 0 for g in groups)
    logs = [(REPORTS / f'{PREFIX}{n}.log').read_text(encoding='utf8') for n in ['frontend_full', 'frontend_extended', 'frontend', 'build', 'lint']]
    full, extended, lending, build, lint = logs
    assert not re.search(r'ℹ fail [1-9]', full + extended + lending)
    frontend = {'full_chain': sum(map(int, re.findall(r'ℹ pass (\d+)', full))),
        'extended': sum(map(int, re.findall(r'ℹ pass (\d+)', extended))),
        'lending_only_recheck': sum(map(int, re.findall(r'ℹ pass (\d+)', lending)))}
    assert frontend == {'full_chain': 253, 'extended': 156, 'lending_only_recheck': 23}, frontend
    assert 'built in' in build and ': error ' not in lint
    hashes = baseline['source_sha256']
    changed = [p for p, h in hashes.items() if not (ROOT / p).is_file() or hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h]
    allowed = '''backend/main.py
backend/routes/library_inventory.py
backend/schemas/library_catalogue.py
backend/services/institution_repository.py
backend/services/issue_service.py
backend/services/library_catalogue_service.py
backend/services/library_inventory_access.py
backend/services/library_inventory_import.py
backend/services/loan_renewal_service.py
frontend/src/App.tsx
frontend/src/components/ForYou.tsx
frontend/src/components/LibrarySwitcher.tsx
frontend/src/components/PopularBooks.tsx
frontend/src/hooks/useBookActionState.ts
frontend/src/lib/assistantTypes.ts
frontend/src/lib/libraryInventory.ts
frontend/src/pages/BookDetailPage.tsx
frontend/src/pages/CatalogPage.tsx
frontend/src/pages/InstitutionPanel.tsx
frontend/src/pages/LibraryInventory.css
frontend/src/pages/LibraryInventory.tsx
frontend/src/pages/ProfilePage.tsx
frontend/src/pages/SearchPage.tsx
frontend/src/store/useAssistantStore.ts
frontend/tests/loan-renewal.test.tsx
assistant/orchestrator.py
assistant/schemas.py
assistant/tools.py
frontend/package.json'''.splitlines()
    assert set(changed) == set(allowed), changed
    frozen = [p for p in hashes if p.startswith(('rag/', 'knowledge_graph/', 'assistant/router', 'assistant/llm')) or
        any(s in p.lower() for s in ['existing_qwen', 'embedding', 'cross_encoder', 'recommender', 'ranker', 'hnsw', 'faiss'])]
    assert not set(frozen).intersection(changed)
    mongo = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=5000)
    production = mongo[baseline['database']]
    counts = {n: production[n].estimated_document_count() if n == 'books' else production[n].count_documents({}) for n in baseline['production_counts']}
    assert counts == baseline['production_counts'], counts
    lending_counts = {n: production['institution_' + n].count_documents({}) for n in ['lending_config', 'lending_operations', 'lending_requests', 'loans']}
    assert all(n == 0 for n in lending_counts.values()), lending_counts
    remaining = [n for n in mongo.list_database_names() if n.startswith(('luminar_institution_v2b_live_', 'luminar_institution_v2b_test_'))]
    assert not remaining, remaining
    indexes = {n: [{'name': i['name'], 'key': list(i['key'].items()), 'unique': i.get('unique', False),
        **({'partialFilterExpression': i['partialFilterExpression']} if 'partialFilterExpression' in i else {})} for i in production[n].list_indexes()]
        for n in ['institution_lending_config', 'institution_lending_operations', 'institution_lending_requests', 'institution_loans']}
    mongo.close()
    write('preservation', {'status': 'PASS', 'baseline_files': len(hashes), 'unchanged_files': len(hashes) - len(changed),
        'modified_files': changed, 'protected_files_checked': frozen, 'protected_changed': [], 'production_before': baseline['production_counts'],
        'production_after': counts, 'production_lending_counts': lending_counts, 'production_cutovers': 0,
        'note': 'Global catalogue UI buttons gained a library request destination; search/recommendation computation is unchanged. Assistant edits are confined to request schemas, tool adapters and orchestrator boundaries. Selected-context logic is unchanged.'})
    write('regression', {'status': 'PASS', 'part2b': backend, 'institution_v1': v1, 'institution_v2a': v2a,
        'frozen_groups': groups, 'frozen_totals': {'tests': sum(g['tests'] for g in groups), 'passed': sum(g['passed'] for g in groups), 'skipped': sum(g['skipped'] for g in groups), 'failed': 0},
        'frontend': frontend, 'frontend_total_executions': frontend['full_chain'] + frontend['extended'],
        'count_note': 'Execution counts; some frozen groups overlap. Lending-only rerun is included in the full frontend chain and is not added again.',
        'build': 'PASS', 'lint': {'status': 'PASS', 'errors': 0, 'warnings': lint.count(': warning '), 'existing_warnings': 19},
        'notes': ['Existing security suite has ten skipped cases; see JUnit skip reasons.', 'Events fixtures align obsolete NOW timestamps to current UTC; production source and JWT validation remain unchanged.',
            'Loan renewal frontend harness now accepts CSS imports pulled in by the canonical Profile integration.', 'An earlier intermittent Knowledge Tools DOM wait failure was superseded by the successful full chain without changing Knowledge Tools source.',
            'Router V1–V5 research was not rerun; no model training or external inference was performed.'], 'production_after': counts})
    def evidence(name, terms, behavior, codes=''):
        cases = [c for c in backend['cases'] if any(t in c for t in terms)]
        assert cases, name
        write(name, {'status': 'PASS', 'behavior': behavior, 'test_artifact': backend['artifact'], 'test_cases': cases,
            'live_scenarios': [r for r in live['scenarios'] if r['code'] in codes], 'limits': 'Isolated fixture validation; no production migration performed.'})
    evidence('borrow_requests', ['pending_hold_then', 'releases_once', 'borrower_revalidated', 'pending_request_policy'],
        {'model': 'Unified LibraryLendingRequest with request_type BORROW/RETURN; strict UUID tenant/book/request IDs.', 'states': ['PENDING', 'APPROVED', 'REJECTED', 'CANCELLED', 'EXPIRED'],
        'pending': 'Exactly one hold, no loan and no due date.', 'policy': 'LIBRARY_BORROW_HOLD_HOURS default24 range1..168; LIBRARY_MAX_PENDING_REQUESTS default5 range1..100.'}, 'ABCDEI')
    evidence('return_requests', ['return_request_remains', 'return_confirm_race', 'each_transition'],
        {'pending': 'Loan remains ACTIVE and unavailable until physical receipt; pending_return_request_id prevents duplicate requests.', 'confirmed': 'COMPLETED request / RETURNED loan / allocation released once.',
        'rejected': 'Loan remains ACTIVE; re-request permitted; original return_requested_at retained.', 'removed_borrower': 'Current authorized staff can receive historical active loan.'}, 'FGI')
    evidence('availability', ['pending_hold_then', 'stock_shelf_status', 'known_copy_conditions', 'expiry_backlog'],
        {'formula': 'physical_total - active_loans - pending_borrow_holds - unavailable_stock - known unavailable copy conditions',
        'circulation_rule': 'Requestable is zero unless ACTIVE book and CIRCULATING holding.', 'authority': 'Canonical tenant holding/copy/request/loan records; no global books availability or LIB001 fallback.'}, 'AHJLM')
    evidence('stock_holds', ['twenty_requests', 'terminal_request_races', 'releases_once', 'stock_shelf_status', 'expiry_backlog'],
        {'aggregate': 'A pending BORROW document is the durable single-unit hold.', 'copy': 'Real identity AVAILABLE → HELD_FOR_REQUEST → BORROWED → AVAILABLE.',
        'expiry': 'Relevant reads/mutations expire at most50 requests per gate; backlog returns503 Retry-After3 so refresh continues.', 'identity': 'Aggregate stock never fabricates copy rows.'}, 'ABCDE')
    evidence('shelf_stock_management', ['stock_shelf_status', 'known_copy_conditions', 'canonical_metadata_creation', 'each_transition'],
        {'shelf': 'Add/edit prominent Shelf Location and Call Number; staff changes journal both book and holding.',
        'stock': 'Visible initial Copies(default1) and Circulation Status; canonical total/other-unavailable safe editor, no editable derived count.',
        'floor': 'Total cannot undercut active+pending+unavailable or existing copy identities.', 'copy_mode': 'All units must be verified and unallocated before mode conversion.'}, 'JKLM')
    evidence('loans', ['pending_hold_then', 'return_request_remains', 'stock_shelf_status', 'cutover_migrates', 'explicit_utc'],
        {'new_loan': 'UUID loan created only on authorized Approve & Issue, with borrower, reviewer, request, holding, copy and provenance.', 'due_policy': 'Existing14-day issue policy starts at approval.',
        'migration_exception': 'Proven historical physical issues preserve borrowed/due dates; no invented original reviewer, request or copy.',
        'timestamps': 'BSON-decoded UTC dates regain explicit UTC timezone at lending receipts/list boundaries; preview and stored due instants agree.'}, 'AFHI')
    evidence('renewal', ['renewal_proven', 'same_library_reservation', 'return_confirm_race', 'each_transition'],
        {'policy': 'Existing enabled/days/max renewal policy; expected_due_at compare and durable key.', 'blocked': 'Overdue, exhausted, disabled policy or pending return.',
        'reservations': 'Only explicit canonical library_id or verified Part2A alias can block; unknown and other tenant reservations ignored.'})
    evidence('idempotency', ['idempotency_payload', 'pending_hold_then', 'canonical_metadata_creation', 'unknown_commit', 'each_transition', 'recovery_and_rollback'],
        {'scope': 'library_id + authenticated actor_user_id + UUID key; operation kind + normalized payload fingerprint.', 'conflict': '409 on changed command under same key.',
        'replay': 'Stored COMMITTED receipt; deterministic plan IDs; no repeat allocation, release or audit.', 'covered_mutations': ['borrow', 'approve', 'reject', 'cancel', 'expiry', 'return_request', 'confirm_return', 'reject_return', 'renew', 'stock', 'shelf', 'copy_condition', 'canonical_add_edit_link_withdraw_copy', 'cutover', 'safe_rollback']})
    evidence('failure_recovery', ['unknown_commit', 'each_transition', 'recovery_and_rollback', 'invalid_migration'],
        {'journal': 'WriteConcern(w=1,j=True); PREPARED absolute effect plan then COMMITTED verified receipt.', 'unknown': 'HTTP503, retained non-expiring gate; config RECOVERY_REQUIRED when journal can be written; no stock fallback.',
        'apply': 'Explicit stopped writers required; replay unfinished plans, reconcile, then clear gate.', 'failure_injection': 'Before effects, after first effect and after committed receipt; nine circulation transitions plus request creation.',
        'limitation': 'Injected acknowledgement interruption is tested; no OS power-loss or storage-corruption test. Missing/tampered plans require operator review.'})
    evidence('migration', ['cutover_migrates', 'snapshot_cannot', 'invalid_migration', 'recovery_and_rollback'],
        {'default': 'Read-only plan. Apply requires explicit UUID library/verified legacy alias, --apply --writers-stopped --idempotency-key.', 'old_data': 'Legacy issues/inventory retained; no dual writing.',
        'refusal': 'Unknown scope, multiple mapped books, duplicate user/book loans, copy allocations, inconsistent snapshot.', 'production': 'No library activated/migrated in production.'})
    evidence('reconciliation', ['each_transition', 'cutover_migrates', 'expiry_backlog', 'unknown_commit'],
        {'checks': ['holding physical capacity', 'COPY state counts', 'pending borrow copy/holding identity', 'approved request matching loan', 'loan tenant book/holding references', 'pending return pointer', 'active loan copy identity'],
        'recovery_gate': 'Not removed unless reconciliation passes; cutover origin must be proven.'})
    evidence('security', ['staff_membership', 'current_staff_authority', 'borrower_revalidated', 'member_privacy', 'legacy_bypass', 'librarian_can'],
        {'authority': 'Current active account, active library and membership; scoped library+book+request+loan IDs; STAFF tenant roles only.',
        'private_data': 'Member lists own rows; aggregate availability reveals no other borrower identity; staff receives only needed borrower name/email/membership.', 'legacy': 'Global ADMIN is not tenant staff; canonical legacy issue/return/renew bypass denied.'})
    evidence('assistant', ['assistant_immutable'], {'boundary': 'Explicit REQUEST_BOOK/REQUEST_RETURN adapter; active library/book/loan UUIDs bound in frozen PendingAction with a durable key.',
        'confirmation': 'Mandatory existing Confirm/Cancel action; later library context cannot retarget it.', 'local_only': 'Real library record; no fake global catalogue ID or RAG book link.',
        'preserved': 'Existing router, selected-context repair and Qwen/model paths unchanged.', 'validation': 'Real backend API transport via TestClient; adapter request and confirm tests; external model not invoked.',
        'feature_flag': 'Existing mutation enable flag/default retained; tests enable it explicitly.'})
    write('operation_journal', {'status': 'PASS', 'collections': indexes, 'write_concern': {'w': 1, 'j': True}, 'replay': 'Absolute $set/$setOnInsert tenant effects with fixed IDs; audit intents in same plan.',
        'gate': 'Persistent institution_locks, shared with current membership and narrow legacy compatibility operations; no timeout takeover.'})
    source_files = sorted(changed + NEW)
    assert all((ROOT / p).exists() for p in source_files)
    write('manifest', {'status': 'PASS', 'captured_at': datetime.now(timezone.utc), 'modified_existing': changed, 'added_source': NEW,
        'source_files': [{'path': str(ROOT / p), 'sha256': hashlib.sha256((ROOT / p).read_bytes()).hexdigest()} for p in source_files], 'collections_indexes': indexes,
        'reports': sorted(p.name for p in REPORTS.glob(PREFIX + '*')), 'note': 'Relative to the Part2B baseline. Earlier dirty workspace changes are preserved and are not attributed to Part2B.'})
    documents(backend, frontend, groups, changed, indexes)
    print(json.dumps({'status': 'PASS', 'backend': backend['passed'], 'v1': v1['passed'], 'v2a': v2a['passed'], 'frontend': frontend, 'production_unchanged': True, 'source_files': len(source_files)}))


def documents(backend, frontend, groups, changed, indexes):
    markdown('architecture', '''# Institution Part 2B architecture

General users create requests. Staff physically issue books by approving a borrow request, and physically receive books by confirming a return request. UUID library/book/holding identities from Part2A remain authoritative. Accessions remain unchanged; global_work_id is optional bibliographic linkage.

## State and allocation

A unified institution_lending_requests collection distinguishes BORROW and RETURN using request_type. Both need the same actor, tenant, state, queue, review and journal rules; return requests additionally bind a loan. A BORROW PENDING row is the aggregate unit hold. In verified COPY mode it also binds exactly one HELD_FOR_REQUEST identity. Approval changes that same allocation into an ACTIVE loan; it never releases and reacquires stock. Return PENDING has no independent unit allocation: its ACTIVE loan still owns the unit.

Requestable = total - ACTIVE loans - PENDING BORROW requests - other unavailable units - unavailable known copy conditions. Non-circulating book/holding status makes requestable zero. Physical capacity remains visible. Aggregate copies are counts, not fabricated historical identities. COPY mode requires complete verified identities and agrees with the derived count. Invalid counts fail closed.

## Standalone Mongo durability

The observed Mongo server is standalone, so no unsupported multi-document transaction is claimed. Current institution_locks serialize each library across workers, membership changes, canonical inventory and narrow legacy issue compatibility. Gates have no TTL or automatic takeover. Lending gates and journal effects use acknowledged journal writes (w=1,j=true). BSON-decoded UTC dates regain explicit timezone at lending response boundaries, so stored dates and approval previews refer to the same instant in any browser timezone.

Every new command has a UUID key scoped by library and authenticated actor, plus a kind/payload fingerprint. One durable PREPARED operation stores fixed IDs, the response receipt, absolute $set/$setOnInsert effects and audit intents. Effects are replayable. The operation becomes COMMITTED and its stored receipt is read before success. Unknown acknowledgement retains the gate and returns503; it cannot authorize another writer or use legacy/global availability. Offline recovery requires stopped writers, proven journal origin and successful reconciliation before releasing the gate. Missing evidence is an operator review case.

Read-triggered expiry processes at most50 requests, each with a deterministic system key. A remaining backlog returns503 Retry-After3; another relevant read advances the batch. No new worker is introduced. Request policy bounds: hold hours1..168 default24; maximum pending1..100 default5. Staff lists default20/max100, return oldest pending first and expose limited borrower information. All data admission rechecks current account, membership and active library.

## Compatibility and cutover

Per-library states are LEGACY, PREPARING, CANONICAL and RECOVERY_REQUIRED. Online ADMIN activation permits only stock-consistent holdings without active mapped legacy issues. Offline migration requires an explicit Part2A canonical_library_id alias and unique proven physical issue mapping. Historical dates are preserved, old records are retained, and no historical copy or approved request is invented. Canonical issue/return/renew bypass through legacy IDs is denied. Unknown legacy data is never guessed into a tenant.

Rollback is only available before canonical requests, loans or other post-cutover operations. Its own durable plan returns holdings to snapshot semantics. Repeat rollback returns the original result. Active migrated loans make rollback unsafe. Recovery reconciles instead of restoring stock blindly.

## Integration boundary

Institution inventory exposes canonical counts, prominent shelf and safe stock/copy controls. My Library separates requests, current loans and history. Staff Circulation Requests has borrow/return tabs, badges, filters and explicit physical transition dialogs. Global catalogue cards route active institution members to an exact local record; global search availability remains outside this phase.

The assistant adds explicit request actions, immutable tenant/book/loan PendingAction fields and tool adapters. Confirmation can only submit the request. The semantic router, selected-context repair, Qwen, retrieval, embeddings, ranking and KG remain unchanged. The existing mutation feature flag is preserved. New canonical loans do not generate legacy fee/payment records or run global reservation fulfillment; those need the tenant design in Part2C.
''')
    markdown('request_workflow', '''# Request workflows

| Trigger | Request state | Physical allocation | Loan |
|---|---|---|---|
| Member Request Book | BORROW PENDING | One unit held; copy HELD_FOR_REQUEST when verified | None; due date absent |
| Staff Approve & Issue | APPROVED, reviewer recorded | Same held unit converts; copy BORROWED | ACTIVE; borrowed/due dates start now |
| Staff reject / owner cancel / bounded expiry | REJECTED / CANCELLED / EXPIRED | Released once | None |
| Borrower becomes ineligible before approval | CANCELLED with reason | Released once | None |
| Book becomes non-circulating before approval | REJECTED with reason | Released once | None |
| Member Request Return | RETURN PENDING | Loan keeps its unit; copy BORROWED | Still ACTIVE and in Current Loans |
| Staff reject return | REJECTED | Unchanged | ACTIVE; re-request allowed |
| Staff Confirm Received | COMPLETED, reviewer recorded | Released once; copy AVAILABLE | RETURNED and in History |

Staff authority must be current in the same library. User actions cannot set reviewer, borrower or final physical status. Return confirmation is allowed for a historical loan even if its borrower lost membership. Request timestamps and received timestamps are distinct; the original return_requested_at survives rejection/re-request.

Renewal uses current policy, owning member, UUID loan, expected due date and idempotency key. Pending physical return blocks it. Reservation influence requires proven same-library UUID or an explicit alias; unknown/global reservations have no tenant authority.

All mutations are serialized and journaled. Repeated command keys return stored results; terminal-state commands with new keys cannot create a second allocation/release. Unknown commit returns503 and requires stopped-writer recovery. A normal busy gate uses Retry-After; UI Refresh/retry is safe with the original key. Browser testing observed a concurrent config read503 that recovered via Refresh.
''')
    review = [
        ('READY_FOR_PICKUP stage', 'Separate review from handing over only if staffed pickup is needed.', 'Approval currently means physical issue.', 'Keep current flow; evaluate pickup expiry and collected transition with product evidence.', 'MEDIUM', 'LATER', 'YES', 'YES'),
        ('Request priority / queueing', 'Fairness must be explicit.', 'Oldest pending first; no priority policy or unavailable-book queue.', 'Design tenant reservation ordering and auditable priority exceptions.', 'HIGH', 'PART_2C', 'NO', 'YES'),
        ('Library-specific expiry', 'Libraries have different opening hours.', 'Server-wide bounded24-hour default.', 'Version per-library policy and snapshot the chosen expiry on requests.', 'MEDIUM', 'LATER', 'NO', 'YES'),
        ('Maximum pending requests', 'Prevent excessive abandoned holds.', 'Bounded server maximum5 exists.', 'Keep bound now; later tenant overrides with a reviewed cap.', 'MEDIUM', 'LATER', 'NO', 'YES'),
        ('Member borrowing limits', 'Physical capacity and fairness differ by membership.', 'Duplicate same-book and pending cap enforced; no overall ACTIVE-loan cap.', 'Add tenant policy across ACTIVE loans and held requests with staff exception audit.', 'HIGH', 'LATER', 'NO', 'YES'),
        ('Fine return timestamp policy', 'Staff processing delay should not unfairly penalize a borrower.', 'Both request/received dates retained; no canonical fine calculation.', 'Specify verified hand-in evidence, rejected requests and staff delay before choosing charge-stop time.', 'HIGH', 'PART_2C', 'YES', 'YES'),
        ('Barcode issue/return', 'Exact physical identity improves staff accuracy.', 'Known optional genuine barcodes; no scan lookup/hardware workflow.', 'Prefer barcode lookup scoped to library and copy; open matching request, retain confirmation and key.', 'HIGH', 'LATER', 'NO', 'NO'),
        ('QR scanning', 'Can open an exact request on a phone.', 'No QR payload/signature lifecycle.', 'Use scoped signed short-lived lookup links after barcode flow; never encode authority in a QR.', 'LOW', 'LATER', 'NO', 'NO'),
        ('Batch issue/return', 'Reduce staff repetition.', 'Single request reviewed per operation.', 'Use explicit per-item receipts and validation; partial batch outcomes must remain visible.', 'MEDIUM', 'LATER', 'NO', 'NO'),
        ('Self-check kiosk', 'Useful for large circulation desks.', 'No kiosk credentials or device trust.', 'Design restricted devices and staff approval; keep physical transitions authorized.', 'LOW', 'LATER', 'NO', 'YES'),
        ('Email/push decisions', 'Members should learn review outcomes promptly.', 'Queue badges and My Library states; journal audit intents, no external delivery.', 'Add deduplicated tenant delivery outbox and preference-aware retries within existing notification design.', 'MEDIUM', 'LATER', 'NO', 'YES'),
        ('Copy-condition return notes', 'Physical verification needs a condition record.', 'Safe current condition management exists; receipt defaults to AVAILABLE.', 'Allow staff receipt condition/note in the same durable operation; keep notes bounded/private.', 'MEDIUM', 'LATER', 'NO', 'YES'),
        ('Damage/lost workflow', 'Exceptional losses affect responsibility and fees.', 'Unallocated copies may be marked LOST/DAMAGED; allocated copies cannot be rewritten.', 'Add explicit exceptional loan closure, condition history and reviewed charges after fee tenancy.', 'HIGH', 'PART_2C', 'NO', 'YES'),
        ('Reservation conversion', 'A waiting queue must not allocate stock twice.', 'Global work-based reservations remain separate.', 'Convert eligible tenant queue entry into one BORROW hold under the same gate and journal.', 'HIGH', 'PART_2C', 'YES', 'YES'),
        ('Fine tenancy', 'Charges require a real library and loan source.', 'Legacy fine records use integer issue_id and no library_id.', 'Canonical fine UUID with library_id, loan_id and charge policy provenance; explicit legacy mapping only.', 'HIGH', 'PART_2C', 'YES', 'YES'),
        ('Receipt printing', 'Useful for physical circulation evidence.', 'Journal/API receipt and UI dates; no printable staff receipt.', 'Add printable accessible loan/return receipt without borrower data outside tenant authorization.', 'LOW', 'LATER', 'NO', 'NO'),
        ('Branch/campus shelves', 'Free text cannot enforce transfers.', 'Prominent bounded shelf/call text on book and holding.', 'Introduce optional canonical locations when branches need transfer tracking; preserve old text.', 'MEDIUM', 'LATER', 'NO', 'YES'),
        ('Institution due policies', 'Different libraries need different loan periods.', 'Existing14-day issue and configurable renewal policy reused.', 'Version tenant due policy; snapshot borrowed policy on loan; do not recompute old due dates.', 'MEDIUM', 'LATER', 'NO', 'YES'),
        ('Holiday adjustment', 'Due dates may land on closed days.', 'No tenant calendar adjustment.', 'Add versioned calendars after tenant due policies; deterministic timezone and closure handling.', 'LOW', 'LATER', 'NO', 'YES'),
        ('Replica-set transactions', 'Improve multi-document atomicity and reduce recovery work.', 'Standalone durable journal/gate; per-library serialization limits throughput.', 'Benchmark a supported replica-set deployment and retain durable command receipts/audit recovery.', 'MEDIUM', 'LATER', 'NO', 'YES'),
    ]
    markdown('improvement_review', '# Part 2B improvement review\n\nNo Part2C work is implemented by this review. Current release blockers were repaired and validated within Part2B.\n\n| TITLE | WHY | CURRENT LIMITATION | RECOMMENDATION | PRIORITY | IMPLEMENT | BREAKING | MIGRATION |\n|---|---|---|---|---|---|---|---|\n' + '\n'.join('| ' + ' | '.join(r) + ' |' for r in review) + '\n\nBarcode lookup fits the genuine copy foundation. Start with keyboard-style scanner input and tenant-scoped barcode/accession lookup; accession alone identifies a book, so copy selection must remain explicit when multiple copies exist. Barcode and QR data select a record; they never replace staff authorization or confirmation. No hardware integration or READY_FOR_PICKUP is added in Part2B.')
    markdown('part2c_scope', '''# Recommended Part 2C: tenant reservations and fees

Repository evidence supports Reservations + Fees as the next phase. backend/services/reservation_service.py creates global work_id reservations using global availability with no tenant ID. backend/services/fine_service.py deduplicates on integer issue_id and charges overdue_days × FINE_PER_DAY (currently5), with no tenant policy or library_id. backend/routes/fines.py exposes legacy account/global staff views. New Part2B UUID loans and separate requested/received timestamps now provide a canonical source, but the old schemas cannot safely charge these loans or allocate tenant queues.

## Proposed authorized scope for the next phase

1. Introduce tenant UUID reservation and charge records bound to canonical library_book_id and loan_id; current membership/staff admission and private list isolation.
2. Define queue order, eligibility, cancellation and expiry. Convert a reservation into exactly one BORROW request hold under the existing gate/journal; approval still means physical issue. Do not make reservation and borrow request own the same unit.
3. Version a fee policy and choose charge-stop rules for first return request, rejected/re-requested returns, verified physical hand-in and staff delay. Preserve existing borrowed/due/requested/received times and immutable policy provenance.
4. Make charges, adjustment, waiver and payment-record state changes idempotent and audited. Design real payment processing separately before integrating a provider. No speculative financial transactions.
5. Migrate only proven library/loan associations; retain unknown/global legacy records in legacy history. Provide read-only planning, per-library cutover, reconciliation and explicit stopped-writer recovery.
6. Extend My Library and tenant staff dashboards with scoped queues/charges. Add assistant adapters only after direct API validation, with immutable IDs and confirmation.
7. Test two libraries sharing a global work, last-unit queue conversion, reservation/renewal/return races, rejected return fee behavior, membership removal, staff authority loss and unknown acknowledgement across charge transitions.

## Boundaries and dependencies

Part2B source of availability remains authoritative. Existing proven same-tenant reservations can block renewal; reservations with unknown scope cannot. Fees remain on the accepted legacy formula until an approved tenant fee implementation exists. Part2B does not automatically create legacy fines for new canonical loans. Physical return still releases stock independently of charge policy.

Notifications may receive narrow deduplicated decision intents after the existing architecture is inspected. Full Events, Notifications or analytics tenancy, READY_FOR_PICKUP, kiosk/hardware scanning, global search availability filters, recommendation overlays and RAG/vector tenancy remain separate future work. Replica-set transactions are an operational option to benchmark, not a prerequisite silently introduced in Part2C. User approval is required before beginning the next phase.
''')
    commands = r'''```powershell
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe -m pytest tests/institution_v2b -q --junitxml=reports/institution_v2b_backend.xml
.\.venv\Scripts\python.exe -m pytest tests/institution_v1 -q --junitxml=reports/institution_v2b_v1.xml
.\.venv\Scripts\python.exe -m pytest tests/institution_v2a -q --junitxml=reports/institution_v2b_v2a.xml
.\.venv\Scripts\python.exe scripts/test_institution_v2b_regressions.py
.\.venv\Scripts\python.exe scripts/check_institution_v2b_live.py
Set-Location D:\SDC\LibraryLLM\frontend
npm test
npx tsx --tsconfig tsconfig.app.json --test tests/admin-notifications.test.tsx tests/document-cache.test.tsx tests/events.test.tsx tests/knowledge-graph.test.tsx tests/kg-product.test.tsx tests/mind-map.test.tsx tests/loan-renewal.test.tsx tests/part3-contract.test.tsx tests/search-depth.test.tsx tests/rag-answer.test.tsx
npm run build
npm run lint
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe scripts/report_institution_v2b.py
```

Use a verified existing UUID and its explicit legacy alias; placeholders below must be replaced. Planning/reconciliation is read-only by default. Stop all API and worker writers before any apply; retain that downtime until reconciliation succeeds.

```powershell
$libraryUuid = '<verified-library-uuid>'
$legacyLibraryAlias = '<verified-Part2A-legacy-alias>'
.\.venv\Scripts\python.exe scripts/migrate_lending_v2b.py --library-id $libraryUuid --legacy-library-id $legacyLibraryAlias
# Explicit offline apply after reviewing the plan:
$cutoverKey = [guid]::NewGuid().ToString()
.\.venv\Scripts\python.exe scripts/migrate_lending_v2b.py --library-id $libraryUuid --legacy-library-id $legacyLibraryAlias --apply --writers-stopped --idempotency-key $cutoverKey
.\.venv\Scripts\python.exe scripts/reconcile_lending_v2b.py --library-id $libraryUuid
# Recovery review, then explicit application while writers remain stopped:
.\.venv\Scripts\python.exe scripts/reconcile_lending_v2b.py --library-id $libraryUuid --action recover
.\.venv\Scripts\python.exe scripts/reconcile_lending_v2b.py --library-id $libraryUuid --action recover --apply --writers-stopped
# Rollback eligibility review; apply only if reported safe:
.\.venv\Scripts\python.exe scripts/reconcile_lending_v2b.py --library-id $libraryUuid --action rollback
.\.venv\Scripts\python.exe scripts/reconcile_lending_v2b.py --library-id $libraryUuid --action rollback --apply --writers-stopped
```

Normal development services: `.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000` and frontend `npm run dev`. Keep the project's existing database/environment configuration. Opening a library does not activate canonical lending; ADMIN uses the reviewed Enable Approval Circulation action only when snapshot consistency and absence of mapped active legacy loans are proven. Assistant mutations retain the existing configured feature flag. No production migration command was run in this task.'''
    markdown('commands', commands)
    items = [
        ('A', 'FINAL PASS', 'PASS for the implemented Part2B scope. Production cutover is explicit and has not been applied.'),
        ('B', 'OLD CIRCULATION', 'Legacy user issue immediately created an ISSUED record and changed stock; user return closed it immediately.'),
        ('C', 'NEW ARCHITECTURE', 'Canonical tenant request → held unit → staff issue; return request → physical staff receipt.'),
        ('D', 'BORROW REQUEST', 'UUID unified request model, BORROW type, PENDING/review/terminal states and current tenant admission.'),
        ('E', 'BORROW HOLD', 'One aggregate unit or genuine HELD_FOR_REQUEST copy; no active loan or due date.'),
        ('F', 'REQUESTABLE AVAILABILITY', 'Derived from tenant totals minus holds, active loans and unavailable units; no global authority.'),
        ('G', 'BORROW FLOW', 'Request Book, review in My Library, cancellation permitted while pending.'),
        ('H', 'APPROVAL', 'Current OWNER/ADMIN/LIBRARIAN approves physical handover; same hold becomes one ACTIVE loan, due now+14 days.'),
        ('I', 'REJECT/CANCEL/EXPIRE', 'Terminal request releases once; default24h bounded server expiry, processed in50-row batches.'),
        ('J', 'LOAN MODEL', 'UUID library/book/holding/copy/borrower/reviewer/request and operation provenance; stable accession snapshot.'),
        ('K', 'RETURN MODEL', 'RETURN request binds an ACTIVE UUID loan; loan holds pending return pointer.'),
        ('L', 'RETURN FLOW', 'Request Return leaves ACTIVE loan/current visibility/responsibility/stock unchanged.'),
        ('M', 'CONFIRM RECEIVED', 'Authorized staff verifies physical receipt, records returned_at/reviewer, completes request and releases once.'),
        ('N', 'RETURN REJECTION', 'ACTIVE loan preserved; original request time retained; borrower may request again.'),
        ('O', 'RENEWAL', 'Owning member, expected due date and existing policy; pending return blocks; only proven same-tenant reservations influence.'),
        ('P', 'SHELF/LOCATION', 'Prominent add/edit fields and safe journaled staff shelf control; member/queue show current shelf.'),
        ('Q', 'STOCK MANAGEMENT', 'Visible default1 initial stock; canonical totals/status/unavailable editor; allocation and known-copy floor; no editable derived availability.'),
        ('R', 'CIRCULATION STATUS', 'CIRCULATING, REFERENCE_ONLY, TEMPORARILY_UNAVAILABLE, WITHDRAWN; only circulating books requestable.'),
        ('S', 'STAFF DASHBOARD', 'Borrow/return queues, badges, bounded paging/filtering, borrower essentials, availability and physical confirmation dialogs.'),
        ('T', 'MY LIBRARY', 'Separate requests/current/history; pending returns remain current and disable return/renew controls; library changes clear stale state.'),
        ('U', 'IDEMPOTENCY', 'Tenant+actor+UUID key and command fingerprint; stored receipt;409 on conflicting reuse.'),
        ('V', 'JOURNAL', 'Durable PREPARED plan with absolute tenant effects and audit intents; verified COMMITTED receipt.'),
        ('W', 'UNKNOWN RECOVERY', '503 retained gate; stopped-writer plan replay and reconciliation before reopening; no TTL takeover.'),
        ('X', 'SECURITY', 'Current account/membership/role; tenant IDOR and global ADMIN bypass denied; own request/loan scope and private inventory enforced.'),
        ('Y', 'LEGACY MIGRATION', 'Read-only default; explicit verified alias, physical issue mapping and preserved dates; old records retained.'),
        ('Z', 'CUTOVER', 'Per-library LEGACY/PREPARING/CANONICAL/RECOVERY_REQUIRED; empty consistent online activation or offline proven migration.'),
        ('AA', 'ROLLBACK', 'Durable rollback only before requests/loans/post-cutover operations; repeat receipt stable; migrated active loan prevents rollback.'),
        ('AB', 'ASSISTANT', 'Explicit immutable library/book/loan request actions with mandatory confirmation; existing router/models/context repair preserved.'),
        ('AC', 'LIVE VALIDATION', 'All real HTTP/Mongo/Vite A–M scenarios pass; browser owner/member workflows and six viewport sizes pass; fixture cleaned.'),
        ('AD', 'RACES', '20 users/5 units, two users/last unit, approve/reject/cancel/expiry and double staff receipt races; return/renew serialization; failure replay verified.'),
        ('AE', 'PERFORMANCE', 'Nine operations measured with actual local small-fixture samples; raw, median and p90 in performance.json. No production-scale claim.'),
        ('AF', 'BACKEND', f'{backend["passed"]} Part2B +56 V1 +95 Part2A passed; ten frozen groups1300 passed/10 existing skipped.'),
        ('AG', 'FRONTEND', f'{frontend["full_chain"]} full-chain +{frontend["extended"]} extended =409 passed executions;23 lending tests included.'),
        ('AH', 'REGRESSION', 'Auth, staff, legacy circulation/renewal/reservations/fines/activity, events, notifications, search/recommendations/KG, Book/private RAG/Knowledge Tools and assistant pass; research router benchmarks not run.'),
        ('AI', 'BUILD/LINT', 'Build passes; lint0 errors and19 existing warnings; existing Vite chunk-size warning retained.'),
        ('AJ', 'FILES', f'{len(changed)} modified existing +{len(NEW)} added source files; exact paths and SHA256 in manifest.json, compared with786 baseline files.'),
        ('AK', 'COLLECTIONS/INDEXES', 'institution_lending_requests, institution_loans, institution_lending_operations, institution_lending_config; shared holdings/copies/audit/locks. Exact unique/partial/query indexes in operation_journal.json.'),
        ('AL', 'SCRIPTS', 'migrate_lending_v2b.py and reconcile_lending_v2b.py use lending_v2b_operations.py; read-only default, explicit offline apply.'),
        ('AM', 'REPORTS', 'All21 required baseline/workflow/category/live/performance/regression/review/Part2C reports created; additional manifest, preservation, journal, browser, JUnit, logs, screenshots and commands.'),
        ('AN', 'LIMITS', 'Standalone serialized gates; occasional busy-read503 requires refresh; lazy expiry/no scheduled sweeping; small-fixture timing; no power-loss test; incomplete legacy tenant evidence needs operator review. New canonical fees/reservation fulfillment and external notification delivery are deferred. Existing assistant mutation flag retained.'),
        ('AO', 'REVIEW', '20 required topics assessed with Why/Current limitation/Recommendation/Priority/Implement/Breaking/Migration in improvement_review.md.'),
        ('AP', 'READY_FOR_PICKUP', 'Defer pending evidence for a separate approved collection stage. Approval currently means physical issue.'),
        ('AQ', 'BARCODE/QR', 'Genuine copy identity fits tenant barcode lookup, then matching request and confirmation. Hardware and QR authority infrastructure deferred.'),
        ('AR', 'NEXT PHASE', 'Repository evidence supports tenant Reservations+Fees; legacy work queues and issue_id fines cannot safely consume new UUID loans.'),
        ('AS', 'PART2C SCOPE', 'Canonical queues/one-hold conversion, versioned fee/timestamp policy, idempotent charge/adjustment records, proven migration and scoped UX/security tests; approval required.'),
        ('AT', 'DEFERRED', 'Full reservations/fees/events/notifications/analytics tenancy, pickup/kiosk/hardware, RAG/vector tenancy, global availability filters and recommendation overlays.'),
        ('AU', 'COMMANDS', 'Exact executed test/build/live/report commands and explicit parameterized offline migration/recovery/rollback commands are below.'),
    ]
    markdown('completion', '# Institution Part 2B completion\n\nValidated on 9 October 2026 (Asia/Calcutta). Stop after Part2B; no Part2C or production cutover performed.\n\n| Item | Topic | Result |\n|---|---|---|\n' + '\n'.join('| ' + ' | '.join(r) + ' |' for r in items) + '\n\n' + commands)


if __name__ == '__main__':
    main()
