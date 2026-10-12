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
