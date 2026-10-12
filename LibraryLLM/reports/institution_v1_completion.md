# LuminaR Institutions / Private Libraries Part 1 completion

**FINAL: PASS for the requested Part 1 scope.** Completed 8 October 2026. No Part 2 domain migration, production legacy migration, SSO, mail-provider installation or model changes were performed.

The existing working tree was already dirty. Changes from this phase are precisely recorded in `institution_v1_manifest.json`; `institution_v1_preservation.json` confirms 705 of 712 baseline source files unchanged, seven intended integration changes, and all 213 source files under assistant/search/recommendation/rag/knowledge_graph unchanged. Dependency declarations and the frontend test command are the other three modified existing files. Earlier RAG/Knowledge Tools work was preserved.

## Requested A–BG handoff

| Item | Result |
|---|---|
| A. Final status | PASS. All requested Part 1 onboarding, access, membership, invitation, staff, migration and tested security behavior passes. This does not assert completed domain tenancy. |
| B. Old architecture | Global numeric users and installation-wide User.role/JWT roles; shared catalogue; legacy inventory string LIB001; no canonical institution/membership boundary. |
| C. New architecture | Global identity + UUID Library + unique library/user membership. Current membership authorizes new institution operations. Shared bibliography, vectors, KG and ranking remain global. |
| D. Library model | UUID, name, normalized unique slug, description, type/access, numeric owner, public contact/address, status and timestamps. PROVISIONING is a private intermediate registration state; ACTIVE/SUSPENDED/ARCHIVED are supported guards. Names need not be unique. |
| E. Public/private access | PUBLIC_LIBRARY/PUBLIC allows direct join. PRIVATE_INSTITUTION/PRIVATE_CODE requires a separate code. Private profile metadata is discoverable; protected resources require active membership. |
| F. Membership model | UUID, library UUID, canonical user_id, GENERAL_USER/LIBRARIAN/ADMIN, ACTIVE/SUSPENDED/REMOVED, dates/attribution and invitation grant proof when applicable; unique library + user. |
| G. Owner model | Server-derived owner_user_id plus ACTIVE ADMIN membership. Owner is not a fourth role. Staff cannot alter owner membership; ownership transfer is deferred. |
| H. Code security | Separate security collection; Argon2id 64 MiB/t=3/p=4 random-salt profile; exact case-sensitive 8–128 Unicode characters. No plaintext, reversible storage or returned hash. Request validation omits submitted secret input/context. |
| I. Rotation | Owner/Admin/Librarian may rotate a private code; GENERAL_USER cannot. Old code fails, new code succeeds, existing members remain. Join rechecks the verified hash under the Mongo gate. |
| J. Registration | Any authenticated eligible account can register; server creates owner ADMIN membership and frontend selects that library. User.role remains unchanged; no manual Mongo provisioning. |
| K. Discovery | Mongo literal name/slug/city/region search, all/public/private/mine filters, bounded pagination and safe metadata with only the caller's membership. |
| L. Public join | Authenticated POST join without code → one ACTIVE GENERAL_USER membership; repeat is idempotent. |
| M. Private join | Code budget consumed before Argon2 verification → serialized current-mode/hash recheck → GENERAL_USER membership. Wrong code 403; exceeded budget 429. Staff removal/suspension cannot be undone by self-join. |
| N. Multi-library users | Same account can join many libraries and have independent roles. Integration/live/browser checks demonstrate different roles without global role escalation. |
| O. Active context | Account-bound frontend store and UUID convenience persistence; GET context verifies the selected library. Login/logout clear state, stale responses are ignored, focus refresh reconciles membership, scoped pages remount on session change. |
| P. Invitation model | UUID, library/email, optional canonical target account, inviter/role, 256-bit random token hash, seven-day configurable expiry, status and acceptance/revocation attribution. |
| Q. Admin creation | Owner invites ADMIN by email; target accepts under current verified identity. Non-owner ADMIN/LIBRARIAN cannot create ADMIN. |
| R. Librarian creation | Owner or current ADMIN invites LIBRARIAN by email. Known accounts accept from their pending dashboard/link; unknown accounts signup/verify and reopen the link. No passwords are assigned by staff. |
| S. Authorization matrix | Owner: settings/code/admin+lib invites/non-owner staff. Admin: settings/code/lib invites/member+lib management. Librarian: code rotation. General: protected member context only. Full matrix in architecture report. |
| T. Cross-library security | Every new resource mutation includes UUID library predicate and current role/status. Wrong-library IDs and outsider/global ADMIN access are denied; cached frontend/JWT role grants no authority. |
| U. Private-resource foundation | Central membership/staff/owner guard ready for future library resources; private 404 for outsiders, 403 for insufficient member role. Existing global holdings/RAG/events are explicitly not relabeled private. |
| V. Registration UI | Integrated public/private choices, masked new/confirm fields, profile/contact/location, validation, errors and owner explanation. |
| W. Explore UI | Search/filter, bounded cards/pages, Public/Private labels, member role, direct public join and masked private-code dialog. |
| X. Switcher | Integrated header selector with library name/role/Owner badge; Explore, Register, invitations and role-appropriate settings links. Server validates changes. |
| Y. Staff UI | Existing Admin/Librarian dashboard Institution tab; members/staff/invitations/audit pages; permitted invite/role/status actions. New library staff do not call legacy global staff APIs. |
| Z. Access settings UI | Role-appropriate rotation; Owner/Admin mode conversion with explicit confirmation and new code for private. No old code, hash or reveal/recovery control. |
| AA. Audit | Library-scoped immutable application event IDs, actor/target/membership, allowlisted metadata and timestamps. Registration, access/code, join, invite, role/status operations recorded. No credential data. DB-level audit hardening is recommended. |
| AB. Mongo indexes | Unique UUIDs/slug/membership pair/pending email/token; query indexes for member/user/status, invitations and audit; attempts TTL. Existing definitions inspected; conflicts fail startup for review, no index drops. Gates/proofs have no TTL. |
| AC. Legacy role compatibility | Global role/session/staff flows retained. New institution authority uses membership only. Complete source reference classifications are in legacy role audit. |
| AD. Legacy migration | Read-only default; explicit access policy and safe owner resolution. Apply upserts stable canonical library/memberships/audit and retains User.role. No inventory/circulation/domain backfill. Production DB untouched. |
| AE. Migration dry-run | Real CLI dry-run created no collections/indexes; disposable apply created 1 library/3 memberships; repeat created 0 memberships; domain records unchanged. Dry-run UUID is a proposal; apply reserves its own stable UUID, used on all later runs. |
| AF. Live validation | A–J passed over actual uvicorn/HTTP/disposable Mongo. Real browser verified switching/account isolation/role controls/keyboard dialogs and 18 responsive page-size combinations. Test accounts/database cleaned up; browser fixture services stopped. |
| AG. Performance | Local HTTP means: register 68.075 ms, public join 13.694, private join 95.926, invite 17.713, accept 20.662, rotate 109.846, me 12.907, discovery 9.224, search 10.137, staff 11.910, guard 9.133, role change 11.352. KDF mean 74.913 ms. Small fixtures/samples, not production p95/load figures. |
| AH. Concurrency | 20-worker tests: exactly one invite acceptance; one membership after duplicate joins; protected owner; isolated cross-user contexts; 5 wrong-code 403 + 15 rate-limited 429. Contention can produce retryable 503. Mongo state is authoritative across instances. |
| AI. Backend tests | Institution: 56 passed on real disposable Mongo. Frozen product regression groups: 1,310 cases, 1,300 passes, 10 existing skips, no failures. Group totals intentionally overlap; Router V1–V5 research excluded. |
| AJ. Frontend tests | 28 new institution interactions; full npm test 204 passed; extended product frontend group 156 passed. Tests include registration/join/switching/logout, stale-session isolation, staff controls, invitations, mode dialogs and legacy API separation. |
| AK. Build/lint | tsc/Vite build passed. Lint passed with zero errors and 19 existing warnings in unchanged legacy files. Existing >500 KiB entry-chunk advisory remains. |
| AL. Exact files changed | Ten existing files modified; 20 implementation/test/report-generator files added. Exact lists and source SHA-256 values are in manifest and reproduced below. No reset/stash/commit was made. |
| AM. Reports | All requested baseline, architecture, security, registration, discovery, membership, private_access, staff, invitations, migration, performance, live, regression, phase2_scope, legacy_role_audit and improvement_review reports created; logs/XML/screenshots/preservation/manifest/completion accompany them. Manifest lists every report. |
| AN. Known limitations | Existing domains remain legacy scoped; no mail sending, owner transfer, institution lifecycle UI, organization verification, production-scale benchmark or automatic abandoned-gate recovery. Fixed-window join budgets bound all verification attempts. |
| AO. Architecture review | Separate 16-section production review; each recommendation has reason, current risk, change, priority, NOW/PART_2/LATER, breaking-change and migration flags. No advisory Part 2 changes were implemented. |
| AP. Critical improvements | Implemented NOW: secret-safe validation, current-membership tenant authority and accepted-proof protection for partial invitation grants. No open immediate critical defect found in tested Part 1 paths. |
| AQ. High priority | Approved Part 2 domain isolation; replica-set transactions/recovery; individual affiliation policy; owner recovery; registration abuse quotas; telemetry redaction; distributed global-auth limits; durable audit/backup policy. |
| AR. Medium priority | Required TenantContext repositories/jobs; indexed/keyset discovery; searchable switcher; email-change semantics; delivery abstraction; optional access-manager permissions; step-up auth; contention/rolling budgets; archive retention; issuer+subject SSO; failure/load coverage; scoped assistant jobs. |
| AS. Nice-to-have | Favorites/recent libraries, unlisted discovery, scoped exports, integrated audit presentation and measured bundle splitting. |
| AT. Open security risks | Shared-code redistribution, stolen bearer session exposure, registration abuse, infrastructure/proxy body logging, database operator/audit tampering and owner account loss. Mitigations/recommendations are explicit in review, no hidden production-hardening claim. |
| AU. Open tenant risks | Legacy inventory/circulation/events/notifications/analytics/private institutional assets still need UUID scope. New Part 1 APIs enforce tenancy; selecting a library does not scope old endpoints. |
| AV. Shared code/future alternatives | Possession of a shared secret is not proof of affiliation. Rotation affects future joins; removal/suspension revokes existing membership. Later options: individual invitation, verified domain, requested approval or SSO policy. Librarian rotation remains as explicitly requested. |
| AW. Data model improvements | Global work_id + UUID holding overlay, accountable physical copies, typed scoped repositories, explicit aliases, separate personal/library assets, source-bound jobs, optional future capabilities and owner transfer. |
| AX. Frontend/UX improvements | Searchable picker at larger membership counts, safer automatic read retry after transactional topology, favorites, delivery status, archive workflow and optional step-up for sensitive actions. Current keyboard/focus/mobile checks passed. |
| AY. Scalability | Indexed point membership/unique writes are suitable foundations; 10/100 libraries should fit ordinary Mongo use. 1k/10k directories require measured regex/offset/N+1 costs, stronger discovery indexes, keyset pagination and batch hydration. No 10k scale claim. |
| AZ. Deployment | Replica-set transactions/majority writes, monitored reconciliation, least-privilege DB accounts, backup/retention, redacted telemetry, distributed existing auth limiter and explicit allowed origins. Institution gates/budgets are already persistent, not process memory. |
| BA. Coverage gaps | True multi-process kill/partition/stepdown and recovery, production-size data/load, mail delivery/retry, complete signup/email-provider browser flow, external SSO, proxy redaction and full assistive-technology matrix. Classified in improvement review. |
| BB. Part 2 architecture | Preserve global work catalogue; recommend both LibraryHolding and LibraryCopy, starting with current quantity overlay and explicit LIB001/other alias mapping. Library-required repositories and library/user-owned resource contracts; preserve personal RAG session isolation. |
| BC. Part 2 order | Alias/holdings → availability and atomic circulation together → reservations → fees → private assets/RAG → explicitly approved events/notifications/analytics/jobs → assistant/search/recommendation availability overlays. Actual collection/service/frontend/test map is in phase2_scope. |
| BD. Intentional deferrals | Holdings/copies/circulation/reservations/fees/events/notification tenancy, assistant institution awareness, search/recommendation overlays, SSO, email provider, ownership transfer, unlisted institutions and institution deletion/export. |
| BE. Recommendations not implemented | All HIGH/MEDIUM/NICE_TO_HAVE review rows remain advisory outside this phase, except the three critical NOW protections already applied. No model/router/training/index-corpus rewrite. |
| BF. Production readiness | Passing onboarding/membership foundation with documented standalone fail-closed behavior. Full private institution material hosting requires Part 2 resource tenancy; sustained production availability needs transactional topology/recovery and deployment hardening. |
| BG. Exact commands | PowerShell commands below start the core/frontend, reproduce checks and perform deliberate dry-run/apply migration. Original production migration was not run. |

## Exact modified files

```text
backend/main.py
frontend/package.json
frontend/src/App.tsx
frontend/src/components/Header.tsx
frontend/src/components/ProtectedRoute.tsx
frontend/src/pages/LoginPage.tsx
frontend/src/pages/StaffDashboard.tsx
frontend/src/store/useAuthStore.ts
requirements-local.txt
requirements.txt
```

## Exact added implementation/test files

```text
backend/institution_dependencies.py
backend/routes/institutions.py
backend/schemas/institution_models.py
backend/schemas/institutions.py
backend/services/institution_repository.py
backend/services/institution_security.py
backend/services/institution_service.py
frontend/src/components/LibrarySwitcher.tsx
frontend/src/lib/institutions.ts
frontend/src/pages/InstitutionPanel.tsx
frontend/src/pages/Institutions.css
frontend/src/pages/Institutions.tsx
frontend/src/store/useInstitutionStore.ts
frontend/tests/institutions.test.tsx
scripts/check_institution_v1_live.py
scripts/migrate_institution_v1.py
scripts/report_institution_v1.py
scripts/test_institution_v1_regressions.py
tests/institution_v1/conftest.py
tests/institution_v1/test_institutions.py
```

Reports are enumerated in `institution_v1_manifest.json`. Temporary fixture/diagnostic files under `.scratch/institution-v1` are recorded separately and contain no active production account. The live database and validation services were removed/stopped; other preexisting source/report work is preserved.

## Exact start commands

Existing environment: Windows PowerShell, project `.venv`, local MongoDB at the configured `.env` MONGO_URI, existing Node/npm and frontend dependencies. Argon2-cffi 25.1.0 is installed in this venv and declared in both requirement files. To provision only the newly required dependency on an otherwise existing setup:

```powershell
Set-Location -LiteralPath 'D:\SDC\LibraryLLM'
.\.venv\Scripts\python.exe -m pip install 'argon2-cffi>=23.1,<26'
```

Terminal 1 (uses the configured database; normal startup adds only required Part 1 indexes):

```powershell
Set-Location -LiteralPath 'D:\SDC\LibraryLLM'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
```

Terminal 2:

```powershell
Set-Location -LiteralPath 'D:\SDC\LibraryLLM\frontend'
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173/libraries` to explore, `/libraries/register` to register, `/invitations` for pending invitations, and `/admin?tab=Institution` or `/librarian?tab=Institution` for membership-appropriate settings. Existing search/recommendation/RAG services retain their established ports 8003/8004/8005 and start procedure; core Institution flows do not require model services. No model selection change is necessary.

## Exact migration commands

Choose the existing verified canonical owner account and database explicitly. These interactive prompts collect nonsecret identifiers. First dry-run, review output, and choose **one** access policy for first apply. Private codes never appear in shell arguments.

```powershell
Set-Location -LiteralPath 'D:\SDC\LibraryLLM'
$institutionDatabase = Read-Host 'Mongo database name to migrate'
$institutionOwnerId = [int](Read-Host 'Existing canonical owner user_id')
.\.venv\Scripts\python.exe scripts\migrate_institution_v1.py --database $institutionDatabase --owner-user-id $institutionOwnerId --name 'LuminaR Legacy Library' --slug 'luminar-legacy-library' --access-mode public
```

Public apply:

```powershell
.\.venv\Scripts\python.exe scripts\migrate_institution_v1.py --database $institutionDatabase --owner-user-id $institutionOwnerId --name 'LuminaR Legacy Library' --slug 'luminar-legacy-library' --access-mode public --apply
```

Alternative **first migration policy**, private dry-run/apply:

```powershell
.\.venv\Scripts\python.exe scripts\migrate_institution_v1.py --database $institutionDatabase --owner-user-id $institutionOwnerId --name 'LuminaR Legacy Library' --slug 'luminar-legacy-library' --access-mode private
.\.venv\Scripts\python.exe scripts\migrate_institution_v1.py --database $institutionDatabase --owner-user-id $institutionOwnerId --name 'LuminaR Legacy Library' --slug 'luminar-legacy-library' --access-mode private --prompt-access-code --apply
```

Repeat the exact chosen apply command to confirm idempotence. Do not run both policies as successive migrations: completed configuration changes are rejected. Use authorized library settings for later access-mode changes. `--owner-email` may replace `--owner-user-id`; with neither selector the script requires exactly one eligible legacy ADMIN. Existing roles/domain records remain unchanged.

## Reproduce validation

Backend institution tests use their own disposable database and drop it on fixture teardown. Frozen regression groups intentionally run in separate processes to prevent historical cross-suite Mongo/mock contamination. Events fixture date is aligned to the current date by a temporary wrapper; stable event tests are not edited.

```powershell
Set-Location -LiteralPath 'D:\SDC\LibraryLLM'
.\.venv\Scripts\python.exe -m pytest tests\institution_v1 -q --junitxml=reports\institution_v1_backend.xml
.\.venv\Scripts\python.exe scripts\test_institution_v1_regressions.py
.\.venv\Scripts\python.exe scripts\check_institution_v1_live.py
.\.venv\Scripts\python.exe scripts\report_institution_v1.py
```

For browser fixtures, use `scripts\check_institution_v1_live.py --serve`; stop it after use so its `finally` tears down the fixture services/database. A forced process termination bypasses teardown; `fixture.json` and live report identify the exact disposable database for manual cleanup. Do not broadly delete databases by prefix.

Frontend:

```powershell
Set-Location -LiteralPath 'D:\SDC\LibraryLLM\frontend'
npm test
node node_modules\tsx\dist\cli.mjs --tsconfig tsconfig.app.json --test tests\events.test.tsx tests\admin-notifications.test.tsx tests\search-depth.test.tsx tests\knowledge-graph.test.tsx tests\kg-product.test.tsx tests\loan-renewal.test.tsx tests\document-cache.test.tsx tests\rag-answer.test.tsx tests\mind-map.test.tsx tests\part3-contract.test.tsx
npm run build
npm run lint
```

Consult the regression runner's group list and generated XML/logs for exact backend selection. Performance report retains raw samples and sample counts. Browser geometry records actual viewport sizes (some nominal dimensions differ by one pixel because of Windows scaling), with no page-wide overflow in all 18 checks.

## Review and stop boundary

Read `institution_v1_architecture.md` for model/index/API/atomicity details; `institution_v1_legacy_role_audit.md` for every classified role reference; `institution_v1_improvement_review.md` for the required 16-section recommendation review; and `institution_v1_phase2_scope.md` for actual Part 2 files/collections/dependencies.

Part 1 is complete. Part 2 remains an explicit future request.
