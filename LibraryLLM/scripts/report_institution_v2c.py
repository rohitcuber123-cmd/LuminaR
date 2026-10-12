"""Build the Part 2C handoff from completed checks; production reads only."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
CHANGED = '''assistant/orchestrator.py
assistant/schemas.py
assistant/tools.py
backend/main.py
backend/services/fine_service.py
backend/services/library_lending_journal.py
backend/services/library_lending_service.py
backend/services/reservation_service.py
frontend/package.json
frontend/src/App.tsx
frontend/src/components/LibrarySwitcher.tsx
frontend/src/components/assistant/AssistantTurn.tsx
frontend/src/lib/assistantTypes.ts
frontend/src/pages/LibraryCirculation.tsx
frontend/src/pages/LibraryInventory.tsx'''.splitlines()
ADDED = '''assistant/reservation_boundary.py
backend/routes/library_reservations_fees.py
backend/schemas/library_reservations_fees.py
backend/services/library_reservation_service.py
backend/services/library_fee_service.py
backend/services/library_v2c_plan.py
backend/services/library_v2c_legacy.py
backend/services/library_v2c_integrity.py
frontend/src/lib/libraryReservationsFees.ts
frontend/src/pages/LibraryReservationsFees.tsx
frontend/tests/institution-reservations-fees.test.tsx
tests/institution_v2c/conftest.py
tests/institution_v2c/test_reservations_fees.py
tests/institution_v2c/test_migration_edges.py
tests/institution_v2c/test_concurrency_edges.py
tests/institution_v2c/test_assistant_boundary.py
scripts/institution_v2c_migration.py
scripts/institution_v2c_operations.py
scripts/migrate_reservations_v2c.py
scripts/migrate_fees_v2c.py
scripts/reconcile_institution_v2c.py
scripts/check_institution_v2c_live.py
scripts/test_institution_v2c_regressions.py
scripts/report_institution_v2c.py'''.splitlines()
REQUIRED = '''baseline.json architecture.md reservations.json queue_conversion.json
fee_policy.md fees.json return_fee_semantics.md payments.json idempotency.json
migration.json reconciliation.json security.json assistant.json performance.json
live.json regression.json improvement_review.md next_scope.md'''.split()


def read(name):
    return json.loads((REPORTS / f'institution_v2c_{name}.json').read_text(encoding='utf8'))


def write(name, data):
    (REPORTS / f'institution_v2c_{name}.json').write_text(json.dumps(data, indent=2, default=str) + '\n', encoding='utf8')


def markdown(name, text):
    (REPORTS / f'institution_v2c_{name}.md').write_text(text.strip() + '\n', encoding='utf8')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def link(relative):
    return f'[{relative}]({(ROOT / relative).as_posix()})'


def junit(name):
    file = REPORTS / f'institution_v2c_{name}.xml'
    tree = ET.parse(file)
    cases = list(tree.iter('testcase'))
    result = {'tests': len(cases), 'failed': sum(any(c.tag in {'failure', 'error'} for c in t) for t in cases),
              'skipped': sum(any(c.tag == 'skipped' for c in t) for t in cases),
              'report': file.name, 'test_names': [t.attrib['name'] for t in cases]}
    assert not result['failed'], result
    result['passed'] = result['tests'] - result['skipped']
    return result


def main():
    baseline = read('baseline')
    hashes = baseline['source_sha256']
    missing = [p for p in hashes if not (ROOT / p).is_file()]
    changed = [p for p, h in hashes.items() if (ROOT / p).is_file() and digest(ROOT / p) != h]
    assert not missing and set(changed) == set(CHANGED), (missing, changed)
    accepted_changed = [p for p, h in baseline['accepted_part2b_reports'].items() if digest(REPORTS / p) != h]
    assert not accepted_changed, accepted_changed
    for p in CHANGED + ADDED:
        (ROOT / p).read_text(encoding='utf-8-sig')
    with MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=5000) as mongo:
        database = mongo[baseline['database']]
        counts = {name: database[name].count_documents({}) for name in baseline['production_counts']}
        additions = {name: database['institution_' + name].count_documents({}) for name in
                     ['reservations', 'reservation_counters', 'fees', 'fee_ledger', 'fee_policies', 'v2c_config']}
        # A separately created V1 library appeared while this long task ran.
        # Preserve it and report the observed difference; never delete it to fit
        # a baseline. Part 2C has no authority to alter that unrelated record.
        protected_changes = {name: value for name, value in counts.items() if value != baseline['production_counts'][name] and name != 'institution_libraries'}
        assert not protected_changes and not any(additions.values()), (protected_changes, additions)
        observed = {name: {'before': baseline['production_counts'][name], 'after': value} for name, value in counts.items() if value != baseline['production_counts'][name]}
        existing_libraries = list(database.institution_libraries.find({}, {'_id': 0, 'library_id': 1, 'name': 1, 'created_at': 1, 'updated_at': 1})) if observed else []
    write('preservation', {'status': 'PASS', 'verified_at': datetime.now(timezone.utc).isoformat(),
        'baseline_source_files': len(hashes), 'unchanged_baseline_source_files': len(hashes) - len(changed),
        'narrow_integration_files': changed, 'unexpected_changes': [], 'missing_files': [],
        'accepted_part2b_reports_verified': len(baseline['accepted_part2b_reports']), 'accepted_reports_changed': [],
        'production_database': baseline['database'], 'before_counts': baseline['production_counts'],
        'after_counts': counts, 'production_part2c_collection_counts': additions, 'production_migrations_applied': False,
        'observed_baseline_count_differences': observed, 'existing_libraries_preserved': existing_libraries,
        'count_difference_note': 'V1 library TEST was registered at 2026-10-08 21:16:39 UTC, after the baseline. This task used explicitly named disposable databases. Source of the separate registration is not inferred; the record was left intact.',
        'catalogue_read_method': 'Count equality and isolation of every mutation fixture; no claim of hashing five million document bodies.',
        'utf8_source_check': 'All 15 changed and 24 added source files decode as UTF-8.',
        'frozen_router_search_recommendation_kg_rag_sources': 'Hash unchanged relative to pre-Part-2C baseline, except listed additive assistant API/presentation integration files.'})
    write('manifest', {'scope': 'Part 2C only; comparison against pre-Part-2C baseline, not Git HEAD.',
        'changed': [{'path': p, 'before_sha256': hashes[p], 'after_sha256': digest(ROOT / p)} for p in CHANGED],
        'added': [{'path': p, 'sha256': digest(ROOT / p)} for p in ADDED],
        'preexisting_dirty_workspace': 'Accepted earlier changes remain intact; untracked Part 2B files can appear in the changed list.'})

    checks = {name: junit(name) for name in ['backend', 'v1', 'v2a', 'v2b']}
    regression = read('regression')
    assert len(regression) == 10 and all(r['exit'] == 0 and not r['failed'] for r in regression)
    for row in regression:
        actual = junit('regression_' + row['group'])
        assert all(actual[k] == row[k] for k in ['tests', 'failed', 'skipped'])
    full = (REPORTS / 'institution_v2c_frontend_full.log').read_text(encoding='utf-8-sig')
    extended = (REPORTS / 'institution_v2c_frontend_extended.log').read_text(encoding='utf-8-sig')
    frontend_counts = [int(n) for n in re.findall(r'\btests (\d+)', full)]
    frontend_passes = [int(n) for n in re.findall(r'\bpass (\d+)', full)]
    frontend_failures = [int(n) for n in re.findall(r'\bfail (\d+)', full)]
    assert len(frontend_counts) == 7 and frontend_counts == frontend_passes and not any(frontend_failures)
    assert re.findall(r'\btests (\d+)', extended) == ['156'] and re.findall(r'\bfail (\d+)', extended) == ['0']
    build = (REPORTS / 'institution_v2c_build.log').read_text(encoding='utf-8-sig')
    lint = (REPORTS / 'institution_v2c_lint.log').read_text(encoding='utf-8-sig')
    assert 'built in' in build and ': error ' not in lint and lint.count(': warning ') == 19
    live = read('live'); browser = read('browser_live'); geometry = read('browser_geometry')
    cleanup = read('cleanup'); browser_cleanup = read('browser_cleanup')
    assert live['status'] == browser['status'] == geometry['status'] == 'PASS'
    assert [s['code'] for s in live['scenarios']] == list('ABCDEFGHIJK')
    assert all(s['status'] == 'PASS' for s in live['scenarios'])
    assert cleanup['fixture_database_dropped'] and cleanup['own_services_stopped'] and not cleanup['production_modified']
    assert browser_cleanup['fixture_database_dropped'] and not browser_cleanup['production_modified']
    assert all(r['scrollWidth'] <= r['width'] for section in ['reservations', 'fees'] for r in geometry[section])
    performance = read('performance')
    assert not performance['scale_claim']
    assert all(name in performance['operations'] for name in ['queue_conversion_with_stock_increase', 'fee_calculation_pure', 'fee_creation_with_physical_return'])
    write('verification', {'status': 'PASS', 'backend': checks, 'frozen_product_regression': regression,
        'frozen_product_totals': {'executions': sum(r['tests'] for r in regression),
            'passed': sum(r['tests'] - r['skipped'] for r in regression), 'existing_skips': sum(r['skipped'] for r in regression)},
        'frontend_full': {'passed': sum(frontend_counts), 'groups': frontend_counts, 'new_part2c_tests': frontend_counts[-1]},
        'frontend_extended_passed': 156, 'build': 'PASS', 'lint_errors': 0, 'lint_existing_warnings': 19,
        'live_scenarios': 11, 'browser_checks': len(browser['checks']), 'browser_geometry_checks': 12,
        'warnings': ['Existing Starlette/httpx deprecation warning.', 'Existing Vite bundle chunk-size warning.', 'Ten existing security regression skips.'],
        'events_clock_note': 'Only old Events test constants are aligned to current time in a disposable runner; JWT expiry and application behavior are unchanged.',
        'research_excluded': 'Router V1–V5 research not run.'})

    names = checks['backend']['test_names']
    def evidence(*terms):
        matched = [n for n in names if any(t in n for t in terms)]
        assert matched, terms
        return {'junit': checks['backend']['report'], 'passing_test_cases': matched}

    write('reservations', {'status': 'PASS', 'identity': ['library_id UUID', 'library_book_id UUID', 'reservation_id UUID', 'global canonical user_id'],
        'global_work_id': 'Optional metadata; never queue authority.', 'local_only_supported': True,
        'states': ['WAITING', 'CONVERTED', 'FULFILLED', 'CANCELLED', 'EXPIRED'],
        'ordering': 'Per-library/per-book persistent monotonic counter journaled under the durable library gate; sequence gaps retained.',
        'max_active_per_member_per_library': 5, 'active_states': ['WAITING', 'CONVERTED'],
        'creation_eligibility': ['Active verified account', 'ACTIVE library membership', 'ACTIVE book and CIRCULATING holding',
            'No active loan or pending borrow for the same local book', 'No existing WAITING reservation for the same local book',
            'No immediately requestable unit, or existing strict FIFO head temporarily blocks general requestability'],
        'waiting_expiry': 'None by default. Explicit imported/operator expires_at is lazily enforced.',
        'position': 'Count WAITING records at/before sequence within same library/book; no other member identity exposed to members.',
        'physical_allocation': 'WAITING never creates a hold or decrements physical_available.',
        'evidence': evidence('fifo', 'concurrent_sequence', 'limit_per_library', 'private', 'grace_disabled', 'client_tenant', 'cross_library')})
    write('queue_conversion', {'status': 'PASS', 'hold_identity': 'UUID5(luminar-reservation-request:<reservation UUID>)',
        'unit_owner': 'Only the generated Part 2B PENDING BORROW request owns one aggregate/copy hold.',
        'same_durable_plan': ['Physical return release', 'Overdue fee and initial charge ledger when due', 'FIFO reservation conversion', 'Copy hold update when COPY mode', 'Audit intents'],
        'triggers': ['Confirm Received', 'Stock increase', 'Verified copy restored AVAILABLE', 'Waiting cancellation', 'Generated request cancellation/rejection/expiry'],
        'eligibility_revalidation': ['Current active verified account', 'Current ACTIVE membership', 'Same local book/holding still circulating', 'No duplicate active loan or pending borrow', 'Pending request limit'],
        'invalid_head': 'CANCELLED (EXPIRED for elapsed explicit expiry), then advance.',
        'temporarily_limited_head': 'Blocks later queue entries and direct request bypass; preserves strict FIFO.',
        'fairness': 'The same persistent gate and journal projection allocate queue holds before exposing released stock.',
        'terminal_behavior': 'Approval → FULFILLED; rejection/cancel → CANCELLED; generated hold timeout → EXPIRED. No automatic reinsertion.',
        'renewal': 'Eligible WAITING reservations for another borrower on exactly the same library/local book block renewal.',
        'evidence': evidence('fifo', 'terminal_releases', 'stock_increase', 'copy_mode', 'head_ineligible', 'request_limit', 'renewal', 'partial_plan')})
    write('fees', {'status': 'PASS', 'identity': ['fee_id UUID', 'library_id UUID', 'loan_id UUID', 'library_book_id UUID', 'borrower/user_id'],
        'money': {'representation': 'Strict integer INR minor units', 'minor_units_per_major': 100, 'maximum_minor': 1000000000000, 'floats_strings_booleans_rejected': True},
        'provenance': ['Immutable original_amount_minor', 'policy_id and complete policy_snapshot', 'Calculation timestamps/rate/grace/days', 'source_event'],
        'balances': 'current_amount = CHARGE - CREDIT - WAIVER; paid_amount = PAYMENT_RECORD; balance = current_amount - paid_amount.',
        'new_fee_idempotency': 'Unique library/loan/fee_type and deterministic overdue fee/initial charge UUIDs.',
        'actual_types_created': ['OVERDUE'], 'future_type_filters_only': ['DAMAGE', 'LOST', 'MANUAL_ADJUSTMENT'],
        'states': ['OPEN', 'PARTIALLY_PAID', 'PAID', 'WAIVED', 'CANCELLED'], 'cancelled_state': 'Reserved for future workflows; no Part 2C fee cancellation API.',
        'active_loan_estimate': 'ESTIMATED, nonpayable; final charge exists only after confirmed physical receipt.',
        'unpaid_fee_return': 'Physical receipt/stock release is not blocked by financial balance.',
        'evidence': evidence('fee_final', 'valid_return', 'grace_disabled', 'money_strict', 'overdue_disabled', 'generation_race', 'reconciliation')})
    write('payments', {'status': 'PASS', 'processing': 'MANUAL_RECORD_ONLY', 'external_calls': 0,
        'methods': ['CASH', 'EXTERNAL', 'OTHER'], 'immutable_fields': ['entry_id UUID', 'fee_id', 'library_id', 'amount_minor', 'method', 'reference', 'reason/note', 'actor_user_id', 'created_at', 'idempotency_key', 'receipt_id UUID'],
        'authority': {'member': 'Own reads only', 'LIBRARIAN': 'Tenant fee reads and manual payment records', 'ADMIN_or_OWNER': 'Payment records, adjustment/waiver, policy versions'},
        'partial_full': 'PARTIALLY_PAID then PAID; payment larger than current outstanding balance rejected.',
        'waiver': 'Zeroes only remaining unpaid balance; retains original charge, earlier payments and a reasoned WAIVER entry.',
        'adjustment': 'Reasoned positive CHARGE or CREDIT entry; cannot credit below paid amount or exceed supported amount range.',
        'retry': 'Same library/actor/key/type/payload returns the same receipt; changed payload is a conflict.',
        'evidence': evidence('ledger_partial', 'waiver_retains', 'payment_race', 'adjustment_waiver', 'stale_staff', 'client_tenant')})
    write('idempotency', {'status': 'PASS', 'journal_scope': ['library_id', 'actor_user_id', 'idempotency_key'],
        'payload_fingerprint': 'Operation kind plus canonical payload; changed kind/payload with same key returns 409.',
        'durability': 'Accepted Part 2B PREPARED absolute effects and stable result persisted with w=1,j=True on standalone Mongo.',
        'queue_and_fee_ids': 'Stable generated borrow, overdue fee, initial charge and migrated record UUID5 identities.',
        'failure_behavior': '503 RECOVERY_REQUIRED and retained persistent gate on uncertain write acknowledgement; no speculative successor or compensation.',
        'recovery': 'Explicit offline replay with every writer stopped. Reconcile Part 2B and Part 2C invariants before clearing that gate.',
        'fault_injection_effect_cutpoints': [0, 1, 2, 3, 4, 5, 8, 12],
        'replayed_result': 'One physically returned loan, one overdue charge/ledger and one next FIFO hold.',
        'evidence': evidence('partial_plan', 'receipt_retry', 'fee_final', 'ledger_partial', 'migration_dryrun')})
    write('migration', {'status': 'PASS', 'default': 'Read-only plan/dry run', 'apply_requires': ['--apply', '--writers-stopped', '--idempotency-key UUID', 'Proven legacy alias and canonical Part 2B lending'],
        'reservation_proof': 'Explicit record library alias + exactly one tenant global-work→library-book mapping + borrower + reliable reserved_at.',
        'queue_order': 'Legacy reserved_at then legacy integer ID; appended behind retained canonical persistent sequences.',
        'reservation_quarantine': ['Missing tenant evidence', 'Ambiguous/missing local work mapping', 'READY_FOR_PICKUP physical allocation', 'Duplicate active queue', 'Existing canonical active loan or pending hold', 'Unknown lifecycle'],
        'fine_proof': 'Verified tenant alias + unique migrated legacy issue→canonical loan + matching borrower. Legacy fines have no library_id; globally unique migrated issue evidence can prove tenancy.',
        'fine_quarantine': ['No unique proven loan', 'Contradictory tenant evidence', 'Borrower mismatch', 'Existing canonical overdue charge', 'Duplicate fine for loan', 'Unsafe decimal amount', 'Unknown payment status/date'],
        'financial_preservation': 'Original legacy INR amount converted exactly with Decimal into minor units; paid history retained through charge/payment entries; no retrospective recalculation.',
        'legacy_retained': True, 'idempotent_apply': True, 'production_applied': False,
        'cutover': 'Per-library CANONICAL reservation/fee config after mapped legacy rows and full reconciliation; only tenant ADMIN/OWNER can activate.',
        'legacy_guard': 'Canonical same-tenant mutations denied on legacy endpoints. Unmatched legacy history remains in legacy collections.',
        'rollback': 'Explicit offline only before queue/fee/new-loan use; after canonical history, recover/reconcile and retain authority.',
        'evidence': evidence('migration', 'bypass', 'active_canonical', 'reconciliation')})
    write('reconciliation', {'status': 'PASS', 'read_only': True, 'live_libraries': live['reconciliation'],
        'browser_fixture_libraries': read('browser_reconciliation')['libraries'],
        'checks': ['Part 2B book/holding/copy stock arithmetic and request/loan identity', 'Reservation tenant book',
            'Unique active member/book pair and per-book sequence', 'Counter exists and is not behind retained history',
            'WAITING owns no request', 'All converted and terminal request links match exactly one BORROW request and lifecycle',
            'Fulfilled loan matches approved request', 'Immutable tenant policy matches loan and fee snapshots',
            'Fee borrower/book match canonical loan', 'Fee currency/policy match issuance provenance',
            'Immutable ledger matches cached amounts; payments cannot exceed balance', 'Historical waiver has zero remaining balance',
            'Legacy/canonical charge mapping is unique and proven'],
        'corruption_tests': ['Missing counter', 'Changed policy rate snapshot', 'Incorrect terminal borrow link', 'Unmapped duplicate legacy charge'],
        'repair': 'No guessed counter/policy/charge repairs. Recovery refuses to release the retained gate until inspection passes.',
        'evidence': evidence('reconciliation_detects', 'partial_plan', 'migration', 'race')})
    write('security', {'status': 'PASS', 'authority_source': 'Current verified account and ACTIVE tenant membership, rechecked after acquiring the shared mutation gate; JWT/global role alone grants no tenant authority.',
        'member_privacy': 'Own reservations/fees only; queue positions contain no other member identity.',
        'id_scope': 'UUID path identifiers resolved only in the explicit authenticated library.',
        'strict_body': 'Extra caller library/user/policy version/paid amount fields rejected; actors come from authenticated account and monetary limits are server-enforced.',
        'negative_checks': ['Private outsider', 'Unrelated canonical library/book/reservation/fee UUIDs', 'Unaffiliated global ADMIN', 'Other-member cancel/detail',
            'Librarian waiver/adjust', 'Removed or demoted staff', 'Disabled account with stale credentials', 'Unverified account conversion', 'Money precision/range/overpayment', 'Cross-library queue isolation'],
        'test_auth_scope': 'Part 2C API tests override JWT decoding but perform real current-account/membership checks. Live scenarios use actual JWT logins; frozen security suites retain auth/expiry tests.',
        'evidence': evidence('private', 'canonical_cross', 'client_tenant', 'stale_staff', 'head_ineligible', 'money_strict', 'waiver_retains')})
    write('assistant', {'status': 'PASS', 'order': 'Direct API tests passed before additive adapters were integrated.',
        'actions': ['RESERVE_LIBRARY_BOOK', 'CANCEL_LIBRARY_RESERVATION'],
        'immutable_pending_scope': ['library_id UUID', 'library_book_id UUID', 'reservation_id UUID for cancel', 'idempotency_key', '5-minute expiry'],
        'confirmation': 'Explicit confirmation and existing ASSISTANT_MUTATING_ACTIONS_ENABLED gate. Changed confirmation context cannot retarget the proposal.',
        'read_paths': ['/libraries/{library_id}/me/reservations', '/libraries/{library_id}/me/fees'],
        'legacy_mode': 'Only explicit LEGACY config retains the global legacy account envelope; errors and recovery states fail closed.',
        'staff_financial_tools': [], 'frozen': ['existing_qwen router', 'Selected-context repair', 'Retrieval/ranking', 'Knowledge tools'],
        'ui': 'Readable scoped fee/reservation summaries with My Library links.',
        'evidence': evidence('assistant_'), 'frozen_assistant_regression': next(r for r in regression if r['group'] == 'assistant')})

    markdown('architecture', '''# LuminaR Institutions Part 2C

Canonical reservations and fees extend the accepted V1 identity, Part 2A inventory and Part 2B approval circulation. No production data was migrated. A library admin must explicitly activate its subsystem after migration/reconciliation.

Legacy reservations use global work_id and installation-wide availability. Legacy fines use integer issue_id and FINE_PER_DAY=5, without authoritative tenant loan/policy identity. Those collections remain historical; guards stop competing writes once a proven library has canonical authority.

Canonical queue identity is library UUID + local book UUID + global numeric user identity. Optional global_work_id never joins institutions. A WAITING record has no physical allocation. A durable persistent counter assigns a per-book sequence; cancellation leaves sequence gaps. Public requestability gives the eligible FIFO head first claim while physical stock arithmetic remains unchanged.

```mermaid
flowchart LR
  W[WAITING reservation, no stock hold] --> E[Current eligibility under library gate]
  E --> P[One PENDING Part 2B borrow hold]
  P --> A[Staff Approve and Issue]
  A --> L[Canonical loan with fee policy snapshot]
  L --> R[Staff Confirm Received]
  R --> J[One durable compound journal plan]
  J --> S[Release physical stock]
  J --> F[Final overdue fee and immutable charge ledger]
  J --> Q[Next FIFO reservation receives one hold]
```

The pure plan extension projects prior effects before the existing journal persists PREPARED. Physical release, fee generation, queue/copy handoff and audit entries replay as absolute changes with deterministic generated identities. There are no postcommit callbacks. Uncertain acknowledgement retains the persistent library gate and reports RECOVERY_REQUIRED; an operator stops every writer, replays, reconciles, then releases the proven gate.

New collections are institution_reservations, institution_reservation_counters, institution_fees, institution_fee_ledger, institution_fee_policies and institution_v2c_config. Accepted institution_lending_operations, lending_requests, loans, holdings, copies, locks and audit are reused. Models and index constraints are listed in the completion report.

Members read their own rows. Tenant LIBRARIAN can inspect queues/fees and record a manual payment. Tenant ADMIN/OWNER also versions policies, adjusts and waives. Global ADMIN without tenant membership has no privilege. Path UUIDs and current membership remain authoritative after the shared gate is acquired.

The frontend resets state/dialogs and discards old responses when the active library changes. Inventory offers Join Waitlist only when canonical stock is unavailable; converted reservations link to accepted Borrow Requests. Fees show original/current/paid/balance, policy version, due/request/receipt timestamps and immutable history. No online payment control is presented.

Assistant adapters are additive explicit actions with immutable scoped pending confirmation. They read only own fees/reservations and expose no staff financial tool. The existing_qwen routing/retrieval systems and accepted phase report artifacts are preserved.
''')
    markdown('fee_policy', '''# Versioned fee policy

Version 1 preserves the repository's INR ₹5/day rate: 500 integer minor units, zero grace days, overdue enabled, PHYSICAL_RECEIPT stop, UTC_CALENDAR_DAY boundaries. It records the legacy source. The supported currency is INR with 100 minor units per rupee; new rates, payment amounts and adjustments are strict integers.

An immutable policy version contains policy_id UUID, library_id UUID, monotonic version, effective_from, overdue_enabled, rate_minor_per_day, currency/minor unit factor, grace_days, charge_stop_policy, day_boundary, created actor/timestamp and provenance. Admin creation writes a new complete version; old versions are never overwritten.

Actual staff issuance snapshots the current version onto the loan. Part 2C activation snapshots already existing loans. Renewals retain that snapshot while updating due_at. A later policy change affects future issuance, not previous loans or fee history. Imported legacy fees preserve original amounts with explicit legacy provenance instead of retroactive recomputation.

The calculation is max(0, UTC(stop).date − UTC(due_at).date − grace_days) × rate_minor_per_day when overdue is enabled. It preserves legacy calendar-day behavior, not elapsed 24-hour blocks. Crossing midnight can therefore add a day even when fewer than 24 hours have elapsed. Policy snapshots and the exact used timestamps/rate/days accompany every final charge.

PHYSICAL_RECEIPT is the default. FIRST_VALID_RETURN_REQUEST is also available: only the request that staff ultimately completes qualifies. An earlier rejected return request never stops accrual. Both timestamps remain stored. Final charges are generated at physical receipt; active loans show clearly labeled nonpayable estimates. Outstanding financial balance does not prevent returning an item.

Grace days support 0–365. Per-library caps, holiday calendars, other currencies, automatic lost/damage charges, provider processing and refunds are deferred. The supported total money range is bounded at 10^12 minor units; exceeding it requires review rather than truncation or floating conversion.
''')
    markdown('return_fee_semantics', '''# Return timestamp fairness

The accepted Part 2B return workflow remains authoritative: a member submits a return request, staff physically receives the item, then Confirm Received releases stock. A request alone never proves receipt.

The loan retains return_requested_at as legacy/first-request metadata, valid_return_requested_at for the particular request that staff completes, and physical_received_at for confirmed receipt. Every rejected request stays in request history. Fee calculation stores due_at, both request fields, physical_received_at, chosen charge_stop_at, charge_stop_policy, calendar boundary, grace, rate and days.

Under PHYSICAL_RECEIPT, staff delay can add calendar-day charges until receipt; an admin can record an audited adjustment or waiver. Under FIRST_VALID_RETURN_REQUEST, later-confirmed genuine returns stop on the completed request's UTC day. Rejected/fake earlier requests are ignored, even if the loan's first return_requested_at is older. Policies are fixed at issuance and displayed in fee details.

Both choices finalize only at physical confirmation. An overdue loan that remains active has an ESTIMATED amount and cannot be passed to final fee generation. Zero charge creates no fee. Finalization, stock release and next queue hold are within the same durable operation, so unpaid fees never withhold physical return.

Live G demonstrates a request on the due UTC day and receipt on the next day producing zero charge with FIRST_VALID_RETURN_REQUEST. Live H demonstrates an earlier rejected request followed by genuine completion still producing the correct charge. Tests cover both policies, staff delay, grace and preservation of policy versions. Synthetic date fixtures are explicitly labeled in the live report.
''')

    recommendations = [
        ('Real payment integration', 'Duplicate or misrouted settlement can corrupt tenant balances.', 'Only manual desk records exist.', 'Design tenant payment intents, immutable fee allocation, authenticated provider callbacks, provider event deduplication, settlement reconciliation and separate reversal entries before selecting a provider. Keep provider secrets server-side.', 'HIGH', 'LATER', 'NO', 'YES'),
        ('Tenant Notifications', 'Canonical queue members need correct-library delivery and privacy.', 'Global user inbox, sender authority and source references have no canonical library scope.', 'Make library ownership, current membership audience and source UUID explicit; add a durable tenant outbox before linking queue or fee events.', 'HIGH', 'NEXT_PHASE', 'YES', 'YES'),
        ('Email/push reservation alerts', 'Members need timely action before a generated borrow hold expires.', 'No Part 2C email/push or tenant delivery channel exists.', 'After tenant notifications, add opt-in channels and delivery deduplication. Say ready for borrow approval, and name the library and hold deadline.', 'MEDIUM', 'LATER', 'NO', 'YES'),
        ('Lost/damaged item charging', 'Overdue and replacement responsibility have different evidence and appeals.', 'Types are reserved; automatic damage/lost charge generation is absent.', 'Add copy-specific incident evidence, reasoned staff assessment, versioned amount rules and dispute/reversal history; keep physical reconciliation separate.', 'HIGH', 'LATER', 'NO', 'YES'),
        ('Copy-condition return notes', 'Condition evidence makes later assessments reviewable.', 'Accepted condition flags exist but structured receipt notes are absent.', 'Attach bounded observations and optional evidence references to a physical receipt; do not automatically create a financial charge.', 'MEDIUM', 'LATER', 'NO', 'YES'),
        ('Member borrowing limits', 'Institutions need consistent eligibility across direct and queue requests.', 'Pending limit remains accepted installation configuration; active reservation cap is five.', 'Version tenant active-loan and pending-request limits, and apply the same policy under the library gate at request, conversion and approval.', 'MEDIUM', 'LATER', 'NO', 'YES'),
        ('Per-library loan duration', 'Due dates should reflect institution product rules.', 'Accepted Part 2B duration remains its existing configuration.', 'Add immutable lending policy versions and issuance snapshots while preserving existing due dates.', 'MEDIUM', 'LATER', 'NO', 'YES'),
        ('Per-library fine caps', 'A deliberate cap can bound overdue liability consistently.', 'Only integer safety bounds exist; no product fine cap.', 'Add a versioned cap to the fee formula with explicit provenance; retain old snapshots and charged amounts.', 'MEDIUM', 'LATER', 'NO', 'YES'),
        ('Grace periods', 'Small delays should follow a visible institution policy.', 'Calendar-day semantics do not represent partial-day grace.', 'Use the implemented 0–365 UTC calendar-day grace field and immutable versions; validate changes with the existing tests.', 'MEDIUM', 'NOW', 'NO', 'NO'),
        ('Library holidays', 'A closed desk can make physical-receipt charging unfair.', 'UTC calendar subtraction counts closed days.', 'Add a versioned closure calendar and explicit charge-day rule; never rewrite historical fee snapshots silently.', 'MEDIUM', 'LATER', 'NO', 'YES'),
        ('READY_FOR_PICKUP', 'Approval and collection may later need separate physical stages.', 'Accepted borrow approval/issue remains unchanged; pickup stage is intentionally absent.', 'Define a separate audited allocation lifecycle, expiry and receipt before introducing pickup language or legacy pickup migration.', 'MEDIUM', 'LATER', 'YES', 'YES'),
        ('Barcode scanning', 'Desk throughput can improve without changing authority.', 'Copy UUIDs exist; hardware scanning is absent.', 'Map scanned identifiers to verified tenant copy UUIDs and reuse authorized circulation commands and idempotency.', 'LOW', 'LATER', 'NO', 'YES'),
        ('QR workflows', 'Member/copy lookup must not turn printed codes into authority.', 'No QR workflow is implemented.', 'Use QR only for lookup or short-lived scoped action tokens; keep current account and staff checks authoritative.', 'LOW', 'LATER', 'NO', 'YES'),
        ('Batch circulation', 'Multiple returns should produce independent reviewable outcomes.', 'Mutations are single-item operations.', 'Use bounded batches with per-item UUID commands, receipts and failure reporting; reuse the same library gate and queue handoff.', 'LOW', 'LATER', 'NO', 'NO'),
        ('Receipt printing', 'Members need desk confirmation and staff need traceability.', 'Internal receipt UUIDs exist; printing/PDF export is absent.', 'Render a tenant-branded receipt from immutable ledger history with manual-record wording and original amount/paid/balance; avoid gateway claims.', 'LOW', 'LATER', 'NO', 'NO'),
        ('Staff financial permission granularity', 'Cash collection and financial corrections warrant distinct authority.', 'Part 2C has a fixed ADMIN/LIBRARIAN matrix.', 'Keep the implemented split now; later add explicit tenant capabilities and audited delegation instead of broadening global roles.', 'HIGH', 'NOW', 'NO', 'NO'),
        ('Fee disputes', 'Members need a review path without destroying charged history.', 'No structured dispute lifecycle exists.', 'Add own-fee dispute submission, reasoned staff resolution and separate adjustment entries; freeze settlement only by explicit policy.', 'MEDIUM', 'LATER', 'NO', 'YES'),
        ('Refund/reversal', 'A correction after payment differs from a credit on unpaid balance.', 'Credits cannot reduce current charges below recorded payment; provider refund flow is absent.', 'Append separate payment reversal/refund records with actor, reason, original payment link and settlement state; never delete payment history.', 'HIGH', 'LATER', 'NO', 'YES'),
        ('Branch/campus queues', 'Location-specific stock should have predictable eligibility.', 'The canonical queue scope is the institution, not a branch.', 'Define branch holding ownership and transfer policy before adding branch queue keys; migrate without merging institution identities.', 'LOW', 'LATER', 'YES', 'YES'),
        ('Replica-set transactions', 'Native atomic writes may reduce operator recovery complexity.', 'Local Mongo is standalone; journal/gate is authoritative.', 'After an explicit topology change, evaluate transaction-based commits while retaining idempotency, audit plans and offline reconciliation. Do not turn transactions on against the current standalone server.', 'MEDIUM', 'LATER', 'NO', 'YES'),
    ]
    review = ['# Part 2C post-implementation improvement review', '', 'These are scoped recommendations. NOW identifies safeguards already implemented in Part 2C; NEXT_PHASE/LATER are not implemented.', '']
    for title, why, limitation, recommendation, priority, implement, breaking, migration in recommendations:
        review.extend([f'## {title}', '', f'- TITLE: {title}', f'- WHY IT MATTERS: {why}', f'- CURRENT LIMITATION: {limitation}',
            f'- RECOMMENDATION: {recommendation}', f'- PRIORITY: {priority}', f'- IMPLEMENT: {implement}', f'- BREAKING CHANGE: {breaking}', f'- MIGRATION REQUIRED: {migration}', ''])
    markdown('improvement_review', '\n'.join(review))
    markdown('next_scope', '''# Recommended next tenancy phase

Recommend Events + Notifications tenancy next, subject to explicit approval. This is based on the repository's remaining global dependencies, not an assumed roadmap.

- backend/routes/events.py: staff() authorizes global ADMIN/LIBRARIAN and routes live at /staff/events. No library UUID reaches the service.
- backend/services/event_service.py: event records/indexes and event_seen state are global event_id/user_id based. Publication visibility and seen receipts have no canonical institution audience.
- backend/routes/notifications.py: admin() checks global ADMIN; /admin operations and recipients are global-account scoped.
- backend/services/notification_service.py: list_own() queries only user_id; insert_notice() and dedupe keys omit library_id; scan_due() consumes legacy integer issues; notify_reservation_available() uses legacy reservation/work identities and pickup wording.
- backend/services/notification_worker.py calls that legacy notification service. It cannot safely deliver canonical queue-converted or loan-fee events with tenant audience rules.

Part 2C already creates durable reservation/fee audit intents. The most useful next bridge is a separate durable tenant notification outbox keyed by library UUID, canonical source UUID and event identity, with current audience validation. Preserve library labels in a member's combined inbox and prevent a global staff role from sending tenant notices without membership. Make queue alerts describe borrow approval and the Part 2B hold deadline.

Start with tenant ownership/audience models, proven legacy migration/quarantine, per-library cutover and notification deduplication. Then integrate canonical circulation/queue/fee events. Email/push channels follow only after tenant in-app delivery is correct. Admin analytics remains global and should be scoped later against canonical data; digital asset/RAG tenancy, Search overlays and Recommendation awareness require separate authorized phases.

No Events, Notifications, analytics, retrieval or recommendation implementation was changed in Part 2C. Stop here and wait for explicit user approval for the next phase.
''')

    performance_table = '\n'.join(f'| {name} | {row["n"]} | {row["median_ms"]:.3f} | {row["p90_ms"]:.3f} |' for name, row in performance['operations'].items())
    changed_list = '\n'.join('- ' + link(p) for p in CHANGED)
    added_list = '\n'.join('- ' + link(p) for p in ADDED)
    report_list = '\n'.join('- ' + link('reports/institution_v2c_' + name) for name in REQUIRED)
    commands = r'''All commands below are run from `D:\SDC\LibraryLLM` in PowerShell. MongoDB must already be running. The test/live tools use their own named disposable databases; they do not migrate production.

```powershell
Set-Location -LiteralPath 'D:\SDC\LibraryLLM'
.venv\Scripts\python.exe -m pytest tests/institution_v2c -q --junitxml=reports/institution_v2c_backend.xml
.venv\Scripts\python.exe -m pytest tests/institution_v1 -q --junitxml=reports/institution_v2c_v1.xml
.venv\Scripts\python.exe -m pytest tests/institution_v2a -q --junitxml=reports/institution_v2c_v2a.xml
.venv\Scripts\python.exe -m pytest tests/institution_v2b -q --junitxml=reports/institution_v2c_v2b.xml
.venv\Scripts\python.exe scripts/test_institution_v2c_regressions.py
.venv\Scripts\python.exe scripts/check_institution_v2c_live.py
Push-Location -LiteralPath frontend
npm.cmd test
npx.cmd tsx --tsconfig tsconfig.app.json --test tests/admin-notifications.test.tsx tests/events.test.tsx tests/loan-renewal.test.tsx tests/part3-contract.test.tsx tests/search-depth.test.tsx tests/document-cache.test.tsx tests/knowledge-graph.test.tsx tests/kg-product.test.tsx tests/mind-map.test.tsx tests/rag-answer.test.tsx
npm.cmd run build
npm.cmd run lint
Pop-Location
.venv\Scripts\python.exe scripts/report_institution_v2c.py
```

To run the app against your configured local database, use the existing backend/frontend setup. Reuse running services when available. These are foreground development commands for separate terminals; the Core port matches the existing Vite proxy default. No production cutover is implied:

```powershell
Set-Location -LiteralPath 'D:\SDC\LibraryLLM'
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
```

```powershell
Set-Location -LiteralPath 'D:\SDC\LibraryLLM\frontend'
npm.cmd run dev -- --host 127.0.0.1 --port 5182
```

Migration examples are templates, not commands executed against production. Replace the angle-bracket values with a proven library UUID and its verified legacy alias; explicitly configure the intended database. Stop every API and worker writer before `--apply`. Retain the same UUID key for retries. Inspect quarantine and reconciliation before tenant ADMIN/OWNER activation at POST `/libraries/{library_id}/staff/reservations-fees/activate` with `{ "idempotency_key": "<UUID>" }`.

```powershell
$env:MONGO_DB_NAME = '<intended-database>'
.venv\Scripts\python.exe scripts/migrate_reservations_v2c.py --library-id '<library-UUID>' --legacy-library-id '<verified-legacy-alias>'
.venv\Scripts\python.exe scripts/migrate_fees_v2c.py --library-id '<library-UUID>' --legacy-library-id '<verified-legacy-alias>'
.venv\Scripts\python.exe scripts/reconcile_institution_v2c.py --library-id '<library-UUID>'
.venv\Scripts\python.exe scripts/migrate_reservations_v2c.py --library-id '<library-UUID>' --legacy-library-id '<verified-legacy-alias>' --apply --writers-stopped --idempotency-key '<stable-UUID>'
.venv\Scripts\python.exe scripts/migrate_fees_v2c.py --library-id '<library-UUID>' --legacy-library-id '<verified-legacy-alias>' --apply --writers-stopped --idempotency-key '<different-stable-UUID>'
.venv\Scripts\python.exe scripts/reconcile_institution_v2c.py --library-id '<library-UUID>' --operation recover
.venv\Scripts\python.exe scripts/reconcile_institution_v2c.py --library-id '<library-UUID>' --operation recover --apply --writers-stopped
.venv\Scripts\python.exe scripts/reconcile_institution_v2c.py --library-id '<library-UUID>' --operation rollback
.venv\Scripts\python.exe scripts/reconcile_institution_v2c.py --library-id '<library-UUID>' --operation rollback --apply --writers-stopped
```

Recovery apply requires a retained matching library gate and proven Part 2B cutover. Rollback apply is deliberately denied after queue, fee or new-loan use. Do not delete gates manually. No real gateway, Events/Notifications cutover or subsequent phase command is included.'''
    markdown('commands', commands)
    completion = f'''# LuminaR Institutions Part 2C — completion

## A. FINAL PASS

Part 2C implementation, direct API and browser validation, migrations/recovery tooling and all 18 requested reports are complete. Production migration/cutover was not applied. Backend Part 2C: {checks['backend']['passed']} passed; accepted V1/V2A/V2B: 56/95/57 passed. Frozen product suites: 1,300 passed, 10 existing skips. Frontend full chain: 270 passed; extended product UI: 156 passed. Build passes; lint has zero errors and 19 existing warnings. Both owned live fixture databases were removed and owned services stopped. Stop after Part 2C.

Preservation inspection found production institution_libraries changed from zero to one: the V1 library TEST was registered at 2026-10-08 21:16:39 UTC, after the baseline. Its registration source is not inferred; it was preserved. Catalogue, legacy inventory/issues/reservations/fines and canonical inventory/lending counts remain equal to baseline; every production Part 2C collection remains empty. See preservation.json for this explicitly recorded difference.

## B. OLD RESERVATION ARCHITECTURE

Global work_id + user queue and legacy stock/pickup assumptions in reservation_service.py; no canonical institution/local-book scope. Retained only as legacy history/explicit legacy mode.

## C. NEW TENANT RESERVATION ARCHITECTURE

Explicit library UUID/local book UUID queue; current member eligibility; shared durable gate and Part 2B journal. Optional global work links remain metadata. Local-only books work normally.

## D. RESERVATION MODEL

reservation_id, library_id, library_book_id, user_id, queue_sequence, requested_at, expires_at, lending_request_id, loan_id and lifecycle timestamps/provenance. States WAITING, CONVERTED, FULFILLED, CANCELLED, EXPIRED. Eligibility/conversion occurs inside one journal plan instead of persistent intermediate holds.

## E. QUEUE ORDERING

FIFO by persistent per-book monotonic sequence. Counter and reservation write share the gate/journal; never count+1. Unique library/book/sequence index. History gaps remain and timestamps are display metadata.

## F. RESERVATION ELIGIBILITY

Active verified account, ACTIVE membership, active/circulating local book/holding, unavailable stock or an existing strict FIFO head blocking immediate requests, no duplicate same-book active loan/pending request/reservation, maximum five WAITING+CONVERTED per member/library. Invalid accounts/members cancel before conversion; a temporary pending-request limit blocks the head without reordering.

## G. QUEUE → BORROW REQUEST CONVERSION

Deterministic UUID5 borrow request linked to one reservation; PENDING borrow owns exactly one aggregate allocation or verified HELD_FOR_REQUEST copy. Staff approval continues unchanged; one reservation cannot create two requests.

## H. STOCK FAIRNESS

Queue processing projects physical release, stock increase, copy restoration or request terminal effects under the same durable library gate. Queue gets the first opportunity before direct requestability. WAITING changes no physical stock arithmetic; only generated Part 2B requests hold units.

## I. CANCELLATION / EXPIRY

Members cancel own WAITING rows. After conversion they cancel the borrow request. Approval → FULFILLED; request rejection/cancel → CANCELLED; hold timeout → EXPIRED. No reinsertion. WAITING has no default timeout; an explicit expires_at is lazily enforced.

## J. RENEWAL INTERACTION

Another eligible WAITING borrower on the same library/local book blocks accepted renewal. Other-library queues do not. Legacy renewal checks remain only before Part 2C authority.

## K. OLD FEE ARCHITECTURE

Global integer issue_id and installation FINE_PER_DAY=5 with INR text; no canonical library/loan UUID or policy snapshot. Original legacy records are retained.

## L. NEW FEE ARCHITECTURE

Canonical loan/library UUID charge, immutable versioned policy at issuance, final physical-return calculation and append-only financial ledger. Final return and queue handoff share one operation; unpaid amounts never block return.

## M. FEE MODEL

fee_id/library_id/loan_id/library_book_id/user_id, type/status/currency, immutable original amount, current/paid/balance minor units, policy ID/snapshot, calculation, source event and timestamps. Only OVERDUE is created; other fee types and CANCELLED enum are future foundations, not implemented workflows.

## N. FEE POLICY VERSIONING

Initial INR 500 minor units/day, zero grace, physical receipt, UTC calendar day. Tenant ADMIN/OWNER creates a new immutable complete version. Loans snapshot at issuance; pre-cutover loans snapshot at activation; renewal keeps provenance. Existing fees and rates remain unchanged after later versions.

## O. RETURN-TIMESTAMP POLICY

Default PHYSICAL_RECEIPT; optional FIRST_VALID_RETURN_REQUEST uses only the request ultimately confirmed by staff. Original first-request metadata, completed request time and physical receipt are retained separately. Rejected/fake requests never stop accrual. See return_fee_semantics.md.

## P. OVERDUE CALCULATION

max(0, UTC stop date − UTC due date − grace days) × integer daily rate. Preserve the actual legacy calendar rule; crossing midnight can charge before a full 24 hours elapses. Active amounts are ESTIMATED/nonpayable. Zero charge creates no fee.

## Q. ADJUSTMENT / WAIVER

ADMIN/OWNER only; reason required. Append CHARGE/CREDIT or WAIVER; original amount/calculation remain immutable. Waiver zeroes remaining unpaid balance and retains prior payments. Credits cannot reduce current charge below already paid money.

## R. PAYMENT-RECORD FOUNDATION

LIBRARIAN/ADMIN/OWNER may record CASH/EXTERNAL/OTHER desk payments with UUID receipt, reference/note, actor, time and idempotency key. Supports partial/full payment, rejects overpayment, marks MANUAL_RECORD_ONLY. No provider processing or real money attempt occurred.

## S. USER RESERVATION UX

Inventory Join Waitlist confirmation, own Position N of M, own cancellation, converted request link and My Library reservation history. Library switches clear dialog/data and late old responses are discarded.

## T. STAFF RESERVATION UX

Circulation Reservations with default WAITING view, status/title/accession filters, member identity, queue position, date, availability and converted status; pagination. No arbitrary reordering.

## U. USER FEE UX

My Library fees scoped to active institution, separate estimated amounts, original/current/paid/balance, date/policy breakdown and immutable detail history. Payment is handled at the library; no online checkout.

## V. STAFF FEE UX

Tenant fees with status/type/date/name/email/book/accession/fee/loan filtering, paginated results, immutable details, desk payment modal, admin adjustment/waiver reason and policy version form. Librarian controls reflect limited financial authority.

## W. TENANT AUTHORIZATION

Current verified account + ACTIVE membership after the shared gate; role comes from tenant membership. Own-member views prevent IDOR. Cross-library UUIDs, private outsiders and unaffiliated global ADMIN are denied. Strict request schemas reject caller library/user/policy/paid-amount spoofing. Removed/demoted staff and disabled stale accounts cannot record payment.

## X. IDEMPOTENCY

Persistent library/actor/key receipt and payload fingerprint. Same request returns identical result; changed payload/type returns 409. Stable generated fee/request/import UUIDs and unique indexes prevent duplicate charge/hold/ledger entries. See idempotency.json.

## Y. OPERATION RECOVERY

Standalone Mongo w=1,j=True durable PREPARED plan; absolute effect replay. Uncertain acknowledgment reports 503 RECOVERY_REQUIRED and retains the gate. Offline recover requires all writers stopped and a proven cutover/gate, then reconciles all Part 2B/2C invariants before clearing it. Eight injected partial return plans replay to one fee and one next hold.

## Z. LEGACY RESERVATION MIGRATION

Dry run first; verified tenant alias + unique local work mapping + reliable borrower/date. Sort reserved_at then old ID; retain canonical counter history. Ambiguous/no-tenant, pickup allocation, duplicates and active loan/hold conflicts quarantine. Legacy records are never modified.

## AA. LEGACY FEE MIGRATION

Verified alias + unique migrated issue→loan + borrower proof. Missing library_id in real legacy fines can be proven by globally unique migrated issue identity. Preserve original Decimal-safe INR amount and paid history; ambiguous/duplicate charges quarantine. Deterministic IDs and receipt retries make apply repeatable.

## AB. CUTOVER / ROLLBACK

Per-library institution_v2c_config tracks reservation_mode/fee_mode/state. Mapped history must migrate and reconcile before admin activation; legacy mutations then cannot compete. Explicit offline rollback permitted only before canonical queue/fee/new-loan usage. After usage, recover forward. No production cutover was performed.

## AC. RECONCILIATION

Read-only circulation arithmetic, local identity, active pair/sequence/counter, all conversion/terminal links, issuance policy/fee snapshot/currency, loan borrower/book, immutable ledger/status/overpayment and proven legacy charge mappings. Corruption tests demonstrate detection without writes. Both API and browser fixture libraries passed inspection before deletion.

## AD. ASSISTANT ADAPTERS

Direct APIs first. Explicit reserve/cancel adapters carry immutable library/book/reservation UUIDs and key, five-minute TTL, existing write flag and confirmation. Reads own scoped fees/reservations; only explicit LEGACY mode retains legacy envelope. No financial staff tool. existing_qwen/selected context/retrieval unchanged.

## AE. LIVE VALIDATION

All A–K scenarios passed through real HTTP/JWT disposable accounts and two libraries. Synthetic overdue/request dates are labeled. Browser verified 15 member/admin interactions including confirmed waitlist join/cancel, library switching, versioning, manual payment/adjustment/waiver history. Queue and fee geometry checked at 1440, 1366, 1024, 767 (768 target Windows rounding), 390 and 360 CSS widths; no horizontal overflow. Owned fixtures/services cleaned, production mutations zero.

## AF. RACE TESTS

Concurrent sequence/duplicate requests; direct borrow versus returned queue unit; cancel versus stock/conversion; membership removal versus conversion; renewal versus reserve; return versus generation; two fee generators; payment retry versus waiver/adjustment; adjustment versus waiver. Shared tenant gate produces coherent results. Fault tests cover eight partial journal cutpoints.

## AG. PERFORMANCE

Actual local Windows/standalone Mongo disposable-fixture timings; nearest-rank p90. New fee creation is measured together with physical receipt/stock release; queue conversion with stock increase. Pure fee calculation is separate. Idempotent generation timings reconcile an existing fee. No capacity/production-scale claim.

| Operation | n | Median ms | p90 ms |
|---|---:|---:|---:|
{performance_table}

## AH. BACKEND TESTS

Part 2C {checks['backend']['passed']} passed with real standalone Mongo and isolated databases. Includes privacy, money/policy spoofing, membership/authority freshness, migrations, copies, ledger concurrency, assistant scope and corruption/recovery. Deprecation warning is existing.

## AI. FRONTEND TESTS

Full configured chain 270 passed (including 17 new reservation/fee tests). Extended notifications/events/renewal/staff/search/document/KG/mind-map/RAG UI 156 passed. Library switching and stale response cancellation, role visibility, exact decimal conversion and stable payment keys are covered.

## AJ. REGRESSION

V1 56, V2A 95, V2B 57 passed. Ten frozen product groups execute 1,310 tests: 1,300 pass and 10 existing security skips. Auth, inventory, borrowing/returns/renewal, legacy reservations/fines/activity, Events/Notifications, Search/Recommendation/KG, Book/Document RAG/Know More/Knowledge Tools, production assistant/selected context and UI exercised. Old Events test constants only are time-aligned. Router V1–V5 research excluded.

## AK. BUILD / LINT

TypeScript/Vite build passes. Lint zero errors, 19 existing warnings at unchanged source locations. Existing Vite large-chunk warning retained.

## AL. EXACT FILES CHANGED / ADDED

Relative to the captured pre-Part-2C baseline: 15 existing integration files changed and 24 new source/test/script files added. Existing accepted dirty workspace files outside this list are preserved. SHA256 evidence in manifest.json and preservation.json.

Changed:

{changed_list}

Added:

{added_list}

## AM. COLLECTIONS / INDEXES

Six new institution-prefixed collections: reservations (unique reservation UUID; unique library/book/sequence; FIFO lookup; partial WAITING library/book/user uniqueness; library/user/status), reservation_counters (unique library/book), fees (unique fee UUID; unique library/loan/type; tenant status/date and user/status), fee_ledger (unique entry UUID; library/fee/date), fee_policies (unique policy UUID; unique library/version; tenant/user/status generic lookup), v2c_config (unique library UUID). Accepted Part 2B journal uniqueness, loans/requests/copies/holdings, persistent locks and audits are reused.

## AN. MIGRATION / RECOVERY SCRIPTS

migrate_reservations_v2c.py, migrate_fees_v2c.py, reconcile_institution_v2c.py; shared institution_v2c_migration.py and institution_v2c_operations.py. Also check_institution_v2c_live.py, test_institution_v2c_regressions.py and report_institution_v2c.py for reproducible verification. Defaults are read-only for migration/recovery/rollback.

## AO. REPORTS CREATED

All 18 requested artifacts:

{report_list}

Additional verification/manifest/preservation/completion/commands, browser live/geometry/reconciliation/cleanup, isolated API cleanup, screenshots, JUnit and command logs accompany them.

## AP. KNOWN LIMITATIONS

INR only; UTC calendar days (not institution-local/holiday calendar); no fine product cap; fixed five-active reservation policy; installation-level accepted pending/loan rules; no automatic WAITING expiry/periodic tenant worker. General lazy queue maintenance visits at most 50 waiting book identities per request; specific-book access and stock/return events still process that book. Large queue/library capacity was not benchmarked. Standalone journal recovery needs an operator to stop writers. Ambiguous legacy/pickup rows require physical/operator review. No production migration or provider payment was performed. Existing test skips/lint/bundle warnings are recorded.

## AQ. IMPROVEMENT REVIEW

improvement_review.md covers all 20 required topics with title, why, limitation, recommendation, priority, timing, breaking-change and migration fields. It identifies implemented grace/financial authority and defers subsequent work.

## AR. REAL PAYMENT RECOMMENDATION

Design tenant payment intents, authenticated/deduplicated callbacks, immutable settlement allocation and provider reconciliation/reversal boundaries before provider selection. Current desk receipts remain manual records. No provider integration is included.

## AS. LOST / DAMAGED WORKFLOW RECOMMENDATION

Add copy-specific receipt/incident evidence, versioned assessment rules, reasoned staff authorization, disputes and separate charge/reversal history in a future approved phase. Condition flags alone must not automatically charge members.

## AT. NOTIFICATION RECOMMENDATION

Build canonical tenant audience/source ownership and a durable outbox before delivery channels. Alerts should name library/local book and generated borrow-request deadline; pickup wording is deferred.

## AU. NEXT PHASE RECOMMENDATION

Events + Notifications tenancy, based on actual global-role event routes, global event/seen IDs, user-only notification queries and legacy issue/work reminders. Detailed source evidence is in next_scope.md. No next-phase implementation was started.

## AV. DEFERRED ITEMS

Real payment/refund providers, Events/Notifications/analytics tenancy, lost/damage charging, pickup workflow, barcode/QR hardware, digital asset/private semantic tenancy, Search availability filters and Recommendation overlays. Stop after Part 2C and wait for explicit approval.

## AW. EXACT RUN / MIGRATION COMMANDS

{commands}
'''
    markdown('completion', completion)
    assert all((REPORTS / ('institution_v2c_' + name)).is_file() for name in REQUIRED)
    write('completion', {'status': 'PASS', 'required_reports': ['institution_v2c_' + name for name in REQUIRED],
        'handoff': 'institution_v2c_completion.md', 'section_labels': list('ABCDEFGHIJKLMNOPQRSTUVWXYZ') + ['A' + c for c in 'ABCDEFGHIJKLMNOPQRSTUVW'],
        'part2c_backend_passed': checks['backend']['passed'], 'frozen_passed': 1300, 'frozen_existing_skips': 10,
        'frontend_full_passed': 270, 'frontend_extended_passed': 156, 'production_migration': False, 'next_phase_started': False,
        'changed_source_count': len(CHANGED), 'added_source_count': len(ADDED)})
    print('Part 2C PASS: 18 required reports; A–AW handoff; preservation, fixture cleanup and completed verification checked.')


if __name__ == '__main__':
    main()
