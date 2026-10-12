# Institution V1 production improvement review

## 1. Executive Summary

Part 1 passes its tested functional/security scope. Canonical library identity, memberships, private join credentials, staff grants, discovery, switching and safe legacy migration are implemented. All recommendations below are advisory unless marked implemented NOW. No Part 2 writes, SSO, mail-provider installation, speculative role enums or model changes were made.

The foundation can be used for onboarding and staff organization. It is not sufficient to market existing holdings, circulation, RAG material, events or analytics as institution-private. The current standalone Mongo deployment also needs an operator recovery plan for abandoned mutation gates.

Every suggestion is classified in the following tables. Later sections explain those same IDs; they do not introduce unclassified implementation commitments.

## 2. Critical Findings

No open immediate Part 1 critical defect was found in the implemented/tested paths. Prevented defects are recorded as completed NOW:

| ID / Title | Why it matters | Current risk / limitation | Recommended change | Priority | Implement | Breaking change | Migration required |
|---|---|---|---|---|---|---|---|
| C1 Secret-safe validation | Default request validation can echo codes/tokens | Addressed for institution endpoints | Remove submitted input/context from validation responses; retain generic secret errors | CRITICAL | NOW (done) | NO | NO |
| C2 Membership-backed authority | Global staff privileges must not authorize unrelated tenants | Addressed in new institution operations; legacy domain scope intentionally separate | Central current-membership guard, private 404, status checks and strict actor derivation | CRITICAL | NOW (done) | NO | NO |
| C3 Partial invitation grant protection | A membership write must not grant authority before invite consumption commits | Addressed with Mongo serialization and accepted-grant proof | Require same-library/user ACCEPTED proof; retain gate on unknown commit; block replay | CRITICAL | NOW (done) | NO | NO |

H1 remains the boundary for full data tenancy, not an undisclosed Part 1 defect.

## 3. High Priority

| ID / Title | Why it matters | Current risk / limitation | Recommended change | Priority | Implement | Breaking change | Migration required |
|---|---|---|---|---|---|---|---|
| H1 Migrate domain tenancy before private-material rollout | Institutions expect holdings/files and activity isolation | Legacy stock, circulation, events, notifications, analytics and book assets are not canonically tenant-private | Execute the explicit overlay/query/migration plan in institution_v1_phase2_scope.md; preserve global works | HIGH | PART_2 | YES | YES |
| H2 Transactional writes and supervised crash recovery | Safe recovery and uptime are distinct requirements | Unexpected write outcomes retain a persistent gate; affected protected APIs return 503 until reconciled | Deploy replica-set Mongo, use transactions for related writes/audit, keep a reviewed recovery runbook and fault injection | HIGH | LATER | NO | YES (deployment topology) |
| H3 Strong individual private access | A shared passphrase cannot prove institutional affiliation | Members can share the code externally; ex-members may remember it; join attribution identifies account, not how code was obtained | Offer individual invites, verified institutional domain or SSO as policy options; continue rotation/audit and staff removal controls | HIGH | LATER | NO (optional modes) | YES |
| H4 Owner recovery and transfer | Organizations outlive an owner account | Owner cannot be changed by staff; a disabled/lost owner can block admin appointments | Explicit transfer with strong reauthentication, destination acceptance, active-admin invariant and audited operator recovery | HIGH | LATER | NO | YES |
| H5 Registration abuse controls | Self-service creation can be used for spam/impersonation or KDF/resource exhaustion | Authentication/email verification exist; institution creation has no per-account quota or organization verification | Add creation quotas, monitoring and optional verified-domain/organization workflow; do not require blanket approval for normal V1 registration | HIGH | LATER | NO | YES |
| H6 Central secret-aware observability | App code cannot control all proxy/APM telemetry | Backend audit/log paths tested; external proxies/APM may capture POST bodies or browser state | Configure body redaction for access_code/token/password and auth headers, restrict logs, test export paths and retain only safe metrics | HIGH | LATER | NO | NO |
| H7 Distributed global authentication limits | Limits should hold across replicas and support legitimate volumes | Institution join budgets are persistent; existing auth limiter is per-process; shared-IP login can throttle legitimate users | Move existing auth limits to distributed account/IP budgets and preserve email-enumeration-safe behavior | HIGH | LATER | NO | NO |
| H8 Durable audit/backup policy | Application immutability does not stop DB operators or compromised DB credentials | No edit/delete API; DB accounts can still alter documents; standalone writes use normal local acknowledgement | Least-privilege DB credentials, replica-set majority write concern, encrypted backups, retention and protected audit export | HIGH | LATER | NO | YES |

## 4. Medium Priority

| ID / Title | Why it matters | Current risk / limitation | Recommended change | Priority | Implement | Breaking change | Migration required |
|---|---|---|---|---|---|---|---|
| M1 Library-required repository methods | Missing tenant predicates are easy to introduce during domain migration | New guards centralize authorization; future domain reads still need scoped queries | Require TenantContext/library_id in library repositories and job DTOs; test omitted tenant and mismatched resource IDs | MEDIUM | PART_2 | YES | YES |
| M2 Discovery scale and keyset paging | Large directories make regex/offset scans and N+1 hydration more expensive | Bounded pagination and escaped literal regex are safe; name/city/region regex is not a full indexed search engine | Measure 1k/10k fixtures; batch hydrate memberships; add normalized search fields/text or a justified search index and keyset pagination | MEDIUM | LATER | NO | YES |
| M3 Searchable switcher | Choosing a library becomes hard at 20–50 memberships | Role labels and native select work at small sizes; frontend loads bounded membership pages into a full list | Add accessible searchable picker with server-backed paging when usage warrants it | MEDIUM | LATER | NO | NO |
| M4 Email identity change semantics | Bound invites must not follow recycled/changed email accidentally | Known invites bind ID + current verified email; unknown invites depend on verified email ownership at acceptance | Add explicit email-change verification and revoke/reissue affected pending invites; do not transfer accepted memberships by email | MEDIUM | LATER | NO | YES |
| M5 Invitation delivery integration | Manual links are functional but inconvenient and hard to monitor | Existing Brevo OTP sender exists; no institution email is sent in V1 | Reuse a delivery abstraction/outbox with retry/idempotency and provider redaction; assess existing provider before adding a service | MEDIUM | LATER | NO | YES |
| M6 Fine-grained access-management permission | Staff who manage circulation may not need all access duties | Requested V1 permits every active Librarian to rotate entry codes | Retain V1 behavior; later consider ACCESS_MANAGER permission or Owner/Admin policy with explicit product approval | MEDIUM | LATER | YES (if authority removed) | YES |
| M7 Step-up authentication for sensitive administration | Stolen sessions can manage codes/staff until revoked | Existing bearer identity/status checks apply; no step-up factor | Integrate existing/future reauthentication for code rotation, admin grants and owner transfer; avoid an independent fragile password check | MEDIUM | LATER | NO | YES |
| M8 Smoother contention UX and budgets | Safe transient errors can disrupt users during bursts | Protected reads fail closed while gates exist; write contenders wait up to three seconds; fixed windows permit boundary bursts | After transactional topology, retry safe reads with bounded backoff, benchmark write hot spots, consider rolling/distributed budgets | MEDIUM | LATER | NO | NO |
| M9 Archival and retention workflow | Future loans/assets must not be orphaned by deletion | ARCHIVED/SUSPENDED model values are guarded; no lifecycle UI or hard-delete API | Add audited archive, retention and recovery policy; soft-delete libraries only after dependency inventory | MEDIUM | LATER | NO | YES |
| M10 External SSO identity mapping | Verified email is not an immutable external identity | Current user_id is global and suitable as an internal identity | Map issuer + subject to global user_id; scope organization/domain claims to library policy; support OIDC first and SAML via an appropriate federation layer | MEDIUM | LATER | NO | YES |
| M11 Failure and load coverage | Happy-path transactions and 20-worker tests do not simulate infrastructure faults | Unknown outcomes fail closed; no multi-process kill/partition/stepdown load harness | Add injected failures at each write, crash recovery drills, replica-set transaction tests, key rotation and 10k-library load fixtures | MEDIUM | LATER | NO | NO |
| M12 Job tenancy and personalized overlays | Jobs and assistant actions must not infer tenant from mutable UI state | Existing background scans and tool bindings are legacy global/user scoped | Add source library UUID to job inputs, action receipts, dedupe/cache keys and audience selectors during their approved migration | MEDIUM | PART_2 | YES | YES |

## 5. Nice-to-Have

| ID / Title | Why it matters | Current risk / limitation | Recommended change | Priority | Implement | Breaking change | Migration required |
|---|---|---|---|---|---|---|---|
| N1 Recent/favorite libraries | Repeated switching can be quicker for frequent multi-library users | Native picker provides roles but no recency/favorites | Add account-scoped favorites/recent choices only after searchable picker demand | NICE_TO_HAVE | LATER | NO | YES |
| N2 Unlisted institution discovery | Some research organizations do not want public discoverability | V1 private means code-gated membership, not a hidden public profile | Add orthogonal LISTED/UNLISTED visibility without confusing it with access mode | NICE_TO_HAVE | LATER | NO | YES |
| N3 Scoped institution export | Libraries may need portability and administration reports | No holdings/circulation tenant export exists | Add audited member/holdings/circulation/event exports after their tenant migration and retention policy | NICE_TO_HAVE | LATER | NO | NO |
| N4 Shared audit presentation | Operators can benefit from one view of library activity | New library audit and old Admin Operations intentionally differ in scope | Integrate display/filtering after H1; keep source authority and retention explicit | LOW | PART_2 | NO | YES |
| N5 Frontend bundle splitting | Faster initial loading improves mobile discovery | Existing frontend build reports a large entry chunk; new routes are eager imports | Measure bundle/route costs and lazy-load approved page groups; preserve stable Know More/RAG formatting | LOW | LATER | NO | NO |

## 6. Security

Reviewed tenant IDOR, role/owner spoofing, admin chaining, suspended/removed membership, stale JWT role, private-code storage/timing, rotation races, account/library verification budgets, invitation hash leakage, email matching, expired/revoked/declined/replayed grants, duplicate invitations/memberships, and owner/last-admin concurrency. Strict schema inputs and canonical UUID paths reduce mass assignment. New institution validation does not echo secrets. Audit metadata has an explicit allowlist. Current private code attempts and invite bodies are not logged by application handlers; H6 covers deployment telemetry.

Bearer authorization uses the existing account verifier and session revocation; browsers do not automatically attach an Authorization header on a cross-origin form, so new institution endpoints do not introduce cookie-auth CSRF. CORS remains the existing explicit loopback development origins. Production must configure its approved origin; do not broaden it to `*` with credentials. Cookies, if later introduced, require a deliberate CSRF/SameSite design. This phase did not switch authentication storage or alter CORS.

Owner membership protection implies a surviving active Admin under all supported staff changes. Account loss/disable is separate (H4). Two role-change requests cannot both remove all admins through institution APIs; unauthorized Admin-to-Admin chaining is denied even before the invariant check. DB-level tampering is covered by H8, not by a frontend control.

## 7. Tenant Isolation

New staff, member, invitation, access and audit queries carry UUID library predicates. Wrong-library membership/invitation IDs return 404. The global ADMIN claim does not substitute for membership. Protected context tests prove outsider/suspended/removed denial. Frontend selection is UX state only; server membership checks remain authoritative.

H1/M1/M12 describe the intentionally unfinished domain boundary. Existing `LIB001` inventory, reservation work queues, global admin directory, events and stock decoration cannot yet be advertised as privately isolated institutions. No member-code grant changes old global staff privileges.

## 8. Private Access Model

Shared institution codes satisfy the requested V1 behavior but are insufficient for high-assurance affiliation checks. Outsiders can obtain a shared code from members; former members can retain it; rotation affects future joining only. Staff suspension/removal remains necessary for already admitted members. Audit identifies the joining account but cannot attribute who shared the code.

H3 recommends independent user invitations, verified domain admission or SSO. Regular rotation and review of join/audit activity mitigate exposure but cannot undo admitted outsiders automatically. M6 explicitly preserves Librarian rotation now; any future Owner/Admin-only restriction needs product approval. No speculative permission enum was added.

## 9. Data Model

New indexes enforce library UUID/slug uniqueness, unique library-user membership, unique invitation IDs/random-token hashes, and one pending invitation per library/email across staff roles. Names remain nonunique. Accepted invitation proofs must remain retained while memberships reference them. Security hashes are separated from display metadata. Owner is a library property plus ADMIN membership; no OWNER role enum exists.

H1 recommends both aggregate holdings and identifiable copies for the actual quantity-based circulation implementation. See the A/B/C comparison in the Phase 2 inventory. M1/M9 address query safety and lifecycle retention; no framework rewrite is needed. C1–C3 are implemented within Part 1.

## 10. UX

Zero memberships present Explore Libraries, Register a Library and Pending Invitations. One membership selects automatically. At five, role-labeled native selection is sufficient. At twenty/fifty, M3 becomes useful; N1 is optional. Backend pages are bounded to at most 100 entries; UI discovery/member/invite/audit pages use twenty. The switcher aggregates membership pages for present V1 convenience.

Registration explains public/private access, labels masked code/confirmation fields, and clears secrets when switching to public. Join and rotation errors are accessible alerts. Native dialogs support keyboard focus, Escape cancellation, focus restoration, and modal interaction. Rotation confirms existing members survive. Owner controls are protected in UI and backend; non-owner Admin has Librarian invitations only, and Librarian sees access-code rotation alone.

Browser validation inspected 18 page/viewport combinations: discovery, private registration and dashboard at nominal 1440x900, 1366x768, 1024x768, 768x1024, 390x844 and 375x812. All had no page-wide horizontal overflow; tables scroll inside their labeled region. Some actual dimensions differ by one pixel because of Windows browser scaling. Account logout/reset and two-library role switching were verified in the real browser. Full automated assistive-technology coverage remains in M11.

## 11. Scalability

At 10/100 libraries, current UUID/member indexes and bounded queries are appropriate. At 1,000, measure regex search and per-row membership hydration. At 10,000, M2 recommends realistic datasets and indexed directory search/keyset paging after evidence. Library authorization is indexed on `(library_id,user_id)` with no cross-user active context. Staff listing hydrates only one bounded page of user identities.

Measured small local fixtures: discovery mean about 9ms, library search 10ms, /me/libraries 13ms, staff listing 12ms, public join 14ms, private join 96ms including KDF, and direct code verification 75ms. These are local samples, not a 10k-library capacity claim. Exact samples are in institution_v1_performance.json. Twenty concurrent read/guard flows showed no context crossover; same-account private attempts admitted exactly five verifications and rejected fifteen at the limit.

## 12. Deployment

New authoritative state is entirely Mongo-backed. Gates, counters, current memberships, grant proofs and migration identity do not depend on a single process. The frontend's active UUID is explicitly non-authoritative. Existing authentication limiter/worker status remain process-local legacy mechanisms (H7/M12).

The inspected server is standalone; the compensating strategy is fail-closed publication/proof plus persistent gates, not a hidden transaction claim. H2 recommends replica-set transactions and reconciliation tooling before availability-sensitive production. H8 covers durable acknowledgement/backups/audit retention. No automatic timed gate reclaim exists, because a paused old worker could resume after reclaim and violate serialization. Missing/conflicting indexes cause startup/operator review rather than silent weakening.

Email alternatives for M5: SMTP is flexible but delivery/retry/reputation operations remain the team's responsibility; existing Brevo avoids unnecessary provider churn; API providers Resend/SendGrid simplify delivery integration but introduce another external service; SES is attractive in an AWS deployment with operational setup/monitoring. No pricing comparison or provider-specific promise is made; verify current provider requirements during implementation. No provider was installed. SSO remains M10: OIDC issuer/subject mapping works with future Google Workspace or Microsoft Entra policy; SAML federation is a later integration, not a new internal account identity.

## 13. Migration Risks

Migration must never guess among zero/multiple global Admins or rewrite their user IDs. Dry-run adds no index/collection; apply is explicit; private input is hidden and confirmed. CLI apply was run on disposable Mongo only. Repetition deduplicates library/membership/audit; completed configuration cannot reassign owner or mode. Existing inventory strings and incomplete old circulation library IDs need explicit mapping in H1.

There is no automatic application of legacy migration on startup. Existing global role behavior remains functional; newly registered library staff receive no legacy staff rights. Known invitation email changes invalidate acceptance; accepted memberships remain attached to canonical user IDs, not email addresses (M4). Library archival/export should wait for dependency retention policy (M9/N3).

## 14. Part 2 Recommendation

Use canonical alias mapping and holdings first; availability and circulation next as one consistent dependency boundary; then reservations, fees, private assets/RAG, and approved events/notification/job migration. Only then add assistant confirmation context and recommendation/search availability overlays. Preserve global work IDs, vectors, retrieval, KG and model behavior. A single library-required service/repository boundary is preferable to a broad framework rewrite. Exact collections/endpoints/frontend/test scenarios are in institution_v1_phase2_scope.md.

## 15. Deferred Features

H1–H8, M1–M12 and N1–N5 were not automatically implemented. Specifically deferred: holdings/copy migration, circulation/reservation/fee tenancy, events and notifications tenancy, assistant institution awareness, recommendation/search availability filtering, SSO/OIDC/SAML, new mail delivery, transfer/recovery product workflows, hidden institutions, new roles, organization verification, archival/export and fleet-scale optimization.

## 16. Things That Should NOT Be Changed Yet

Do not duplicate global catalogue works, authors, subjects, vectors or KG per library. Do not delete `User.role` while legacy modules still use it. Do not grant old global ADMIN/LIBRARIAN merely because a library is registered or an invite is accepted. Do not replace existing_qwen, router/model research, RAG encoders or deterministic Knowledge Tools in this tenancy phase. Do not auto-revoke existing members on code rotation. Do not silently migrate LIB001 or bind personal session documents to a tenant. Do not install a new mail provider or add speculative staff roles. Do not drop indexes or introduce blind timed unlocking to hide standalone deployment limitations.
