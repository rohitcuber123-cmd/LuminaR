# Institution Part 2A completion

| Item | Topic | Result |
|---|---|---|
| A | FINAL STATUS | PASS — Part 2A only. No production migration applied. |
| B | ARCHITECTURE | Protected UUID-library catalogue + holdings snapshots + optional copies; accepted V1 guards and standalone persistent gate reused. |
| C | GLOBAL VS LOCAL | Shared books stays unchanged; each tenant owns local records with optional verified work reference. Local fields remain authoritative. |
| D | LIBRARYBOOKRECORD | UUID book/library, immutable accession/sequence, title+subjects, nullable ISBN/work, optional metadata, source/status/review/attribution. |
| E | LIBRARYHOLDING | One UUID holding per same-tenant local book; strict 0 <= available <= total; inventory snapshot semantics. |
| F | COPY FOUNDATION | UUID copy and same-tenant references, ordinal, optional barcode/date/status. Legacy known barcodes UNVERIFIED; no aggregate expansion. |
| G | ACCESSION | Persistent tenant counter, PREFIX-000001 with growing digits, stable prefix, immutable/no reuse. Preview allocates none. |
| H | ACCESSION CONCURRENCY | Direct 10/100-worker atomic allocation passes. Real 10/100-worker HTTP creation has zero duplicate accessions. |
| I | MINIMUM METADATA | Only nonempty title and at least one subject required. Unknown identifiers remain null; authors may be empty; quantity defaults to one. |
| J | MANUAL FLOW | Select membership → Add Book → title/subjects → server creates UUID/accession/holding. Other fields collapse as optional. |
| K | DATASET FLOW | Bounded CSV/XLSX → protected preview → explicit policy/confirm → row results. UTF-8/BOM, semicolon values, precise aliases. |
| L | PREVIEW | NEW_LOCAL/GLOBAL_MATCH/EXISTING_HOLDING/POSSIBLE_DUPLICATE/INVALID; actor/library/hash/expiry bound; no catalogue/holding/counter writes. |
| M | GLOBAL LINKING | Existing work must resolve; optional unique ISBN mapping plus compatible metadata; later link/unlink retains UUID/accession/local fields. |
| N | LOCAL ONLY | A valid unidentified book remains a first-class tenant record forever; no fake work/ISBN or mandatory author. |
| O | ISBN | Checksum-valid ASCII ISBN-10/13 only; optional read-only lookup; no leading-zero padding or generated identifiers. |
| P | DUPLICATES | Strong identity conflicts detected per tenant. Title-only remains separate/reviewed. Explicit skip/increase applies to existing holdings. |
| Q | SEARCH | Literal bounded tenant-scoped local title/subject/author/ISBN/accession/call search; no global Search API/vector changes. |
| R | PRIVATE SECURITY | ACTIVE members only; outsider 404, general write 403, revoked account 401. All predicates and imports bound to path UUID. |
| S | ROLES | Owner ADMIN, ADMIN/LIBRARIAN write, GENERAL_USER read. Global ADMIN is not a membership bypass. |
| T | ALIASES | Explicit LEGACY_ID=UUID only; no LIB001/name/global-role guessing. Ambiguous mappings reported. |
| U | LEGACY MIGRATION | Canonical overlay preserves old collection/loans. Trusted existing global metadata fallback allowed; missing required metadata quarantined. |
| V | DRY RUN | Default CLI read-only, including no new collection/index or accession allocation. Disposable four-row fixture: three ready, one missing subject. |
| W | APPLY | Explicit --apply creates three canonical records/holdings/accessions in fixture; a genuine barcode preserved UNVERIFIED. |
| X | IDEMPOTENCE | Repeated fixture apply creates zero; unique source markers/import row keys and stored result replay protect repeat operations. |
| Y | RECONCILIATION | All three live fixture libraries PASS: IDs/accessions/quantities/references/links/copies/counter high-water marks. |
| Z | INVENTORY UX | Current library context, server role, local/global/review/withdraw badges, filters/search/paging and stable identifiers. |
| AA | ADD UX | Two required fields; optional bibliographic/library/link details; immutable accession shown on edit; no Borrow/Read coupling. |
| AB | IMPORT UX | Minimal template, visible bounds/aliases, row errors/counts, explicit existing policy, retained partial/completed results. |
| AC | RESPONSIVE | 24 screen/size checks PASS; 1440,1366,1024,768,390,375 widths; actual CSS dimensions recorded, including one-pixel Windows scaling differences. |
| AD | LIVE | Scenarios 1–10 PASS over real HTTP/Mongo/Vite; browser minimal create and partial import pass; fixtures cleaned. |
| AE | CONCURRENCY | Two simultaneous 100-row tenant imports; 10/100-worker manual creates; 20-user isolation; zero duplicate accessions. |
| AF | PERFORMANCE | Local sequential create median 19.07 ms; list 18.136 ms; search 29.353 ms; 1000-row preview/apply 1913.373/11535.861 ms. Raw data and sample limits in performance.json. |
| AG | BACKEND | 95 new Part 2A tests PASS; final 10/100-worker allocation recheck PASS. |
| AH | FRONTEND | 230 full-chain + 156 extended = 386 passed executions, including 26 inventory tests. Final inventory-only rerun also passes. |
| AI | REGRESSION | 56 accepted V1 tests PASS; frozen groups: 1300 passed, 10 existing skips, zero failures. No Router V1–V5 runs. |
| AJ | BUILD/LINT | Build PASS; lint zero errors/new inventory warnings. Existing 19 lint warnings and >500 kB main-bundle advisory remain. |
| AK | EXACT FILES | See complete source listing below and manifest.json; eight existing integration sources changed. Prior user changes retained. |
| AL | COLLECTIONS/INDEXES | Eight new institution_* collections; exact table in architecture.md. Unique local identity/accession/holding/barcode/source keys; TTL only preview. |
| AM | SCRIPTS | assign_library_book_ids.py, migrate_inventory_v2a.py, inventory_v2a_migration.py, reconcile_inventory_v2a.py, check_institution_v2a_live.py, test_institution_v2a_regressions.py, report_institution_v2a.py. |
| AN | REPORTS | All requested JSON/Markdown reports plus XML/logs, source-preservation manifest, browser geometry/screenshots and cleanup artifacts; manifest lists exact names. |
| AO | LIMITS | Lending/availability/reservations/fees remain legacy. Snapshot counts are not lending truth. Synchronous import locks tenant reads; substring search unproven at 10k/100k; UI copy list is minimal. |
| AP | IMPROVEMENTS | Complete 15-section evidence-based review with every recommendation priority/phase/breaking/migration flags. |
| AQ | CRITICAL | Canonical lending cutover and durable unknown-commit recovery are Part 2B; current account eligibility already hardened in Part 2A. |
| AR | HIGH | Background resumable imports later; genuine copy verification/aggregate allocation in Part 2B. Bounded queue wait and explicit migration duplicate policy implemented now. |
| AS | MEDIUM | 10k/100k tenant search benchmark/indexing, reviewed duplicate merge, candidate-link confirmation, copy administration, authorized private search overlay and separate digital assets. |
| AT | NICE TO HAVE | Separate existing-accession aliases; branch/campus metadata only with evidence; opt-in public inventory policy; route bundle splitting. |
| AU | PART 2B ARCHITECTURE | One canonical availability source; aggregate holding + optional genuine copies; tenant-bound loan/allocation/receipt journal; exactly-once return and retained renewal CAS. |
| AV | PART 2B ORDER | Explicit mapping/quarantine → freeze/reconcile/backup → additive loan refs → availability/borrow → return → renewal → frontend → Assistant tool context → reconciliation/cutover retirement. |
| AW | DEFERRED | Availability/loans/reservations/fees, Events/Notifications, digital/RAG assets, Assistant tenant actions, semantic/global search and recommendations overlays; all model work. |
| AX | NOT IMPLEMENTED | All PART_2B/LATER recommendation rows remain plans. No automatic continuation beyond Part 2A. |
| AY | COMMANDS | Exact PowerShell run/test/dry-run/apply/reconcile commands below; an actual canonical UUID and explicit legacy alias are required. |

## Exact source changes

- `backend/main.py`
- `backend/routes/library_inventory.py`
- `backend/schemas/library_catalogue.py`
- `backend/services/institution_repository.py`
- `backend/services/inventory_upload_limit.py`
- `backend/services/library_catalogue_identity.py`
- `backend/services/library_catalogue_linking.py`
- `backend/services/library_catalogue_repository.py`
- `backend/services/library_catalogue_service.py`
- `backend/services/library_inventory_access.py`
- `backend/services/library_inventory_import.py`
- `backend/services/library_isbn_lookup.py`
- `frontend/package.json`
- `frontend/src/App.tsx`
- `frontend/src/components/LibrarySwitcher.tsx`
- `frontend/src/lib/libraryInventory.ts`
- `frontend/src/pages/InstitutionPanel.tsx`
- `frontend/src/pages/Institutions.tsx`
- `frontend/src/pages/LibraryInventory.css`
- `frontend/src/pages/LibraryInventory.tsx`
- `frontend/src/pages/StaffDashboard.tsx`
- `frontend/tests/institution-inventory.test.tsx`
- `scripts/assign_library_book_ids.py`
- `scripts/check_institution_v2a_live.py`
- `scripts/inventory_v2a_migration.py`
- `scripts/migrate_inventory_v2a.py`
- `scripts/reconcile_inventory_v2a.py`
- `scripts/report_institution_v2a.py`
- `scripts/test_institution_v2a_regressions.py`
- `tests/institution_v2a/conftest.py`
- `tests/institution_v2a/test_catalogue.py`
- `tests/institution_v2a/test_identity_edges.py`
- `tests/institution_v2a/test_import_migration.py`
- `tests/institution_v2a/test_legacy_compatibility.py`

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
