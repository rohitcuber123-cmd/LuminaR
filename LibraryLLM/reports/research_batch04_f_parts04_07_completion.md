# LuminaR Parts 04–07 consolidated remediation

## A. Result

**PARTIAL.** All completed scoped checks passed after correcting harness setup and permission assumptions. The complete role/resource/async matrix requested in Prompt F remains incomplete. No new application defect was confirmed in the exercised paths. No application or test source changed.

## B. Baseline and research reconciliation

The accepted current baseline is Prompt D and Prompt E regression results. Backend had 3,191 passes, zero failures and 20 skips. Frontend had 1,032 passes. Build and lint passed with 16 warnings, and protected contracts had 75 passes. Preflight records dirty status, HEAD and 1,719 raw hashes, incorporating Prompt A/C/D and Part 2Q. Prompt E's four protected recovery/publication defects remain open.

Parts 04–07 historical research files were reconciled against current routes. The old Part 04 result was a guard-only harness. Announcement and targeted-notification implementation already exists in Parts 2P/2P.1.

## C. Security model

PRIVATE_INSTITUTION profiles remain discoverable to authenticated accounts. PRIVATE_CODE controls admission. Argon2id entry credentials are separate from account passwords. Account role, owner identity, tenant membership role, platform assignment, Mongo principal and document identity remain separate authorities.

The actual JWT decoder verifies signature, expiry, subject, session revocation and current active verified account. Tenant guards check current library, membership and invitation proof. Mutations and protected operations recheck under the accepted tenant barrier.

## D. Actual JWT role matrix

The accepted run used a fresh per-fixture signing key and made **386 logged HTTP checks** using the existing create_access_token signer, real decoder, session ledger, account lookup and institution dependencies. Core, Search, document AI and Assistant had zero authentication dependency overrides. Synthetic identities exercised owner ADMIN, other ADMIN, librarian, patron, outsider, suspended/removed members, platform-only account and members of A/B or A only.

| Surface | Allowed fixture scope | Denied fixture scope |
|---|---|---|
| Public profile | Signed-in accounts | Sensitive security fields absent |
| Library context | Active selected-library member | Outsider, suspended, removed, platform-only |
| Membership, invitation and audit lists | ADMIN | Librarian, patrons and nonmembers |
| Staff activity/access settings | ADMIN/LIBRARIAN | Patrons and nonmembers |
| Inventory list/detail | Active member | Nonmember |
| Inventory writes | Staff | Member reads do not grant mutation authority |
| Patron catalogue, Search, loans and reservations | GENERAL_USER | Staff using patron-only context and nonmembers |
| Staff catalogue/Search/Intelligence/KG | ADMIN/LIBRARIAN | Patrons and nonmembers |
| Asset metadata, member events and announcements | Active member | Nonmember |
| Announcement administration and recipient search | ADMIN | Librarian, patrons and nonmembers |

The initial harness assumed staff-only inventory reads, librarian announcement administration, and an incorrect KG route. Current code explicitly supports member inventory reads, requires ADMIN for announcement management, and exposes /intelligence/graph. Corrected expectations passed. Earlier mismatches and invalid invitation-email setup are retained.

## E. Cross-tenant authorization

Actual B book, membership, import, announcement and notification identifiers presented under A or a wrong recipient received denials. A foreign digital asset and cross-library Assistant conversation were also denied. Existing regression cases cover holding/copy/loan/reservation and generation namespaces. The new JWT matrix does not cover every foreign resource under every principal. Existing identity-injected integration cases are recorded separately.

## F. Private codes

Correct case-sensitive verification passed. Five incorrect attempts returned 403 and a sixth returned 429. Oversized input returned 422. A simulated later window admitted valid code. A separate synthetic library counter was prefilled to 199, then the 200th attempt and rejection of the next account were tested without performing 200 Argon2 hashes.

Two concurrent correct joins created one membership. Verification was paused after Argon2 while an ADMIN rotated the code. Admission then returned 409 under the mutation barrier. Old code failed and new code succeeded. Rotation and PUBLIC conversion retained existing membership. Suspended membership could not self-reactivate. Defaults are five account/library attempts, 200 library attempts and 900-second fixed buckets.

## G. Invitations and owner governance

Actual JWT requests passed owner ADMIN grants, other ADMIN librarian grants, wrong-recipient denial, expired/revoked invitation, acceptance replay, inviter downgrade and inactive inviter denial. Non-owner ADMIN could not grant ADMIN. A librarian could not grant staff. Duplicate pending invitation was rejected.

Registration stages PROVISIONING, security, owner membership, canonical defaults and audit before ACTIVE. Separate institution approval, owner transfer and membership expiry are not established product contracts and were not added. Existing regression covers owner protection and default initialization. General operator recovery of uncertain provisioning was not newly qualified.

## H. Revocation and async behavior

Revoked session and disabled account requests returned 401 while an unrelated valid session continued to work. A suspended notification recipient received 404. Membership revocation during document generation withheld the answer and cleared runtime state. The code-rotation race used controlled synchronization.

Existing suites cover Search and recommendation waits, post-wait revocation, stale Assistant context and frontend response cancellation. Fresh real-JWT races across every event, circulation, polling and asset operation, plus live browser switching, were NOT_RUN.

## I. Search/KG isolation

The actual tenant Search route was installed with its existing model-unavailable local fallback and real JWT dependency. Staff Intelligence and unbuilt KG used the real Core routes. No index build was requested in this task. Search/KG publication source and guards were preserved. Prompt E defects remain separate unresolved findings.

## J. Private document authorization

The approved test_asset_pipeline.Engine fixture supplied a deterministic model/generator, synthetic PDF and task-owned FAISS artifacts. Production LibraryAssetPipeline and routes used real JWT dependencies. An authorized member received 200. Outsider, foreign member and platform-only identities received 404 before generation. A foreign asset path was denied. Revocation during generation returned 404 and cleared the runtime index.

This qualifies tested authorization and document scope. Real Qwen generation, answer quality and resident private content were NOT_RUN.

## K. Assistant context

The production Assistant API and tool adapters used generated test JWTs and real Core authorization. The approved deterministic parser and unavailable Search/empty recommendation doubles isolated model behavior. An A/B member opened each context. Reusing A's conversation in B returned 404, and an outsider could not open A. Full regression includes local-only borrowing and canonical recommendation intersection.

## L. Announcements and notifications

Owned targeted and all-member announcements were published and delivered through the existing inbox service. The selected recipient could read a targeted announcement, while a different member could not. Wrong library and recipient IDs returned 404. Read marking was idempotent, and suspension removed access to the notice.

Parts 2P/2P.1 tests cover publication snapshots, later members, recipient revocation, directory scope, deduplication and the shared bell. No SMTP was activated. Recipient search remains restricted to eligible accounts in the authorized institution.

## M. Parts 04–07 issue register

| Research question | Classification | Current evidence |
|---|---|---|
| Guard-only validation gap | MISSING_VALIDATION partly resolved | 386 real-JWT API checks plus generation assertions and 14 extra checks |
| Private profile discoverability | EXPECTED_PRODUCT_POLICY | Current public-field whitelist and authenticated profile responses |
| Member inventory reads | EXPECTED_PRODUCT_POLICY | Membership guard and staff projection |
| Librarian announcement administration | EXPECTED_PRODUCT_POLICY, denied | ADMIN service guard and actual 403 |
| Rotation resets active members | EXPECTED_PRODUCT_POLICY, false assumption | Membership retained, stale admission rejected |
| Announcement/member notification roadmap unknown | ALREADY_FIXED in later accepted work | 2P/2P.1 and current delivery tests |
| Active loan becomes unreturnable after withdrawal | Not reproduced in tested aggregate fixture | Real JWT canonical withdrawal followed by completed return |
| New-work import replay duplicates records | Not reproduced in tested canonical skip import | Same apply result and exactly one work |
| Reservation/stock/fee/journal reliability | Existing implementation with regression evidence | Parts 2B/2C integration and replay suites |
| Every async endpoint/role pair | MISSING_VALIDATION | Broader than fresh cases executed |
| Protected Prompt E defects | UNRESOLVED | Prior exact repros, protected code retained |
| Production network/TLS/Mongo qualification | RESEARCH_ONLY_LIMITATION | NOT_QUALIFIED |

## N. Exact source changes

None. No passing behavior justified an authorization or policy change. New run-specific scripts, logs and reports are under existing scratch/report locations. No protected manifest was regenerated.

## O. Inventory, circulation and negative tests

The real JWT lifecycle created an approved canonical loan, replayed its approval receipt, withdrew the catalogue entry and completed the loan return. The loan remained addressable and ended RETURNED. Withdrawal is a status change rather than deletion. The import test applied a new-work preview twice with skip policy, received the same result and retained one record. A cross-library apply was denied.

Full integration groups cover tenant stock constraints, copy identity, reservations, returns, journal receipts/replay, fees and notification materialization. Their source and fixture tests do not establish arbitrary OS-crash recovery or external payment settlement. Failed uncertain mutations retain their existing recovery gate.

Logs contain synthetic user numbers, route paths, expected/actual statuses and elapsed times. Tokens, invite secrets and PDF contents are not recorded. Harness setup errors remain in earlier run logs and are excluded from accepted-pass totals. Earlier JWT runs could inherit the repository signing setting. The accepted reruns explicitly generated a fresh test-only signing key for each fixture. All calls remained inside disposable apps and databases.

## P–R. Regression, build and lint

| Check | Actual result |
|---|---|
| Full backend, 38 groups | 3,191 passed / 0 failed / 20 skipped |
| Full frontend | 1,032 passed / 0 failed / 0 skipped |
| Protected contracts | 75 passed / 0 failed / 0 skipped |
| Real-JWT matrix | 386 passed / 0 failed |
| Budget, concurrent join and invite controls | 14 passed / 0 failed |
| Production build | PASS |
| Lint | PASS, 16 existing warnings |

## S. Preservation and cleanup

All 1,719 preflight source fingerprints matched. Existing tenant pointers, job metadata, catalogue digests, Mongo indexes, communications and Global HNSW/KG observations matched the accepted read-only reference. All eight fixture runs recorded stopped Mongo processes and removed owned temporary roots. Prior failed harness attempts were retained. No account or membership reset, production authentication change, telemetry activation, index rebuild, deployment, commit or unrelated rollback occurred. Large index preservation is based on metadata and pointer checks, not a new full index-byte hash.

## T. Remaining limitations

The result is PARTIAL because the requested endpoint-wide real-JWT and async matrix is incomplete. No new source defect remains from the passing scoped tests. Prompt E's protected findings remain open. Production Mongo remains NOT_QUALIFIED. Browser-only races, every foreign-ID/resource pairing and deployed network security remain unverified.

The carried-forward Prompt E findings concern a terminal job retaining its tagged lock (E-01), interrupted two-write fence recovery (E-02), manifest identity corruption after validation (E-03), and an untagged barrier after interrupted claim (E-04). They were not retested or repaired here. Their original source locations and reproductions remain in [Prompt E evidence](D:/SDC/LibraryLLM/reports/research_batch03_01_e_completion.md).

## Evidence

- [Starting dirty-tree baseline](research_batch04_f_preflight.json)
- [Accepted real-JWT matrix](research_batch04_f_auth_20261110_04.jsonl)
- [Matrix totals](research_batch04_f_auth_20261110_04_summary.json)
- [Document, Assistant, import and notice assertions](research_batch04_f_auth_20261110_04_extra.json)
- [Concurrent join, budgets and invitation checks](research_batch04_f_budget_20261110_03.json)
- [Full backend groups](institution_v2q_research_batch04_f_backend.json)
- [Frontend, build and lint](institution_v2q_research_batch04_f_front_frontend.json)
- [Preservation](research_batch04_f_preservation.json)
- [Exact task evidence files and SHA-256 hashes](research_batch04_f_changed_files.json)

## Final QA

~~~json
{
  "BATCH04_RESULT": "PARTIAL",
  "scope": "Consolidated Parts 04\u201307",
  "REAL_API_AUTH_MATRIX": "PARTIAL",
  "PRIVATE_CODE_ROTATION": "PASS",
  "STAFF_INVITATIONS": "PASS",
  "CROSS_TENANT_ISOLATION": "PASS",
  "MEMBERSHIP_REVOCATION": "PARTIAL",
  "PRIVATE_RAG_AUTH": "PASS",
  "NOTIFICATION_ISOLATION": "PASS",
  "PRODUCTION_MONGO_QUALIFIED": "NO",
  "BACKEND": {
    "passed": 3191,
    "failed": 0,
    "skipped": 20
  },
  "FRONTEND": {
    "passed": 1032,
    "failed": 0,
    "skipped": 0
  },
  "BUILD": "PASS",
  "LINT": "PASS",
  "lint_warnings": 16,
  "protected_contracts": {
    "passed": 75,
    "failed": 0,
    "skipped": 0
  },
  "NEW_REGRESSIONS": 0,
  "GLOBAL_INDEX_REBUILT": "NO",
  "PROTECTED_RAG_CHANGED": "NO",
  "DEPLOYED": "NO",
  "COMMITTED": "NO",
  "real_jwt_http_checks": 386,
  "additional_budget_checks": 14,
  "auth_extra": {
    "targeted_notifications": "PASS",
    "import_replay": "PASS",
    "jwt_private_rag": "PASS",
    "rag_mid_generation_revocation": "PASS",
    "jwt_assistant_scope": "PASS",
    "model": "Approved deterministic test doubles, no Qwen or external service",
    "auth_overrides": 0
  },
  "source_changes": 0,
  "owned_fixture_cleanup_runs": 8,
  "limitations": "Complete real-JWT endpoint/role and async revocation matrix and live browser race coverage are incomplete. Prior Prompt E protected defects remain open.",
  "regression_delta": {
    "passed": 0,
    "failed": 0,
    "skipped": 0
  }
}
~~~
