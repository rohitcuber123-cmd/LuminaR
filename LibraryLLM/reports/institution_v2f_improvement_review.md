# Part 2F improvement review

These are the twenty requested future topics, assessed against the current implementation. All are deferred recommendations. This report adds no feature, permission, migration, worker, index or external integration. They require explicit approval of a concrete later scope.

The implemented foundation is PDF-only canonical library ownership, STAFF_ONLY/MEMBERS visibility, fresh membership/lifecycle authorization, isolated per-asset processing and RAG, shared Knowledge Tools, same-library book links, deletion tombstones and dry-run reconciliation/migration review. The existing personal corpus and global catalogue remain separate.

| Future topic | Assessment and prerequisite |
| --- | --- |
| 1. Public library digital resources | MEMBERS is membership visibility, not world-public access. A public publishing phase must separately define licensing, explicit publication/withdrawal, public metadata and download policy, and abuse controls. Do not turn PUBLIC_LIBRARY into public document permission. |
| 2. Patron uploads to institution repository | GENERAL_USER currently cannot upload library assets. Later submissions need a distinct pending submission state, quota and consent rules, staff review and a clear ownership transfer; they must not enter readable assets immediately. |
| 3. User-to-library document sharing | Personal/session ownership must remain unchanged by membership. A later share/transfer flow needs explicit source-owner consent, target staff acceptance, copy-versus-transfer semantics and revocation/retention rules. Historical migration review does not perform that transfer. |
| 4. Staff approval workflow for submitted documents | Useful only with an approved submissions model. Define reviewer roles, decisions, reasons, concurrent review and an auditable transition before adding a queue or notifications. |
| 5. Cross-document library RAG | Current Q&A loads one authorized asset. A future bounded corpus must intersect current asset visibility with current membership before retrieval and recheck every contributing source before returning output; citations and caches need corpus-version identity. |
| 6. Library-wide semantic document search | Distinct from catalogue book intelligence and metadata list search. Requires an approved document-corpus generation/permission design, validated source mapping and safe stale/deletion handling. No such index is built here. |
| 7. Library digital collections | Can organize resources after defining canonical collection ownership, asset membership, visibility inheritance and pagination. Collection membership must never broaden an asset's visibility by accident. |
| 8. Document versioning | Current reprocess generations fence derived artifacts for the same immutable source. User-facing source replacement/version history is a separate feature requiring immutable source versions, active version selection, audit and retention; do not treat retry as source replacement. |
| 9. Content retention policy | Deleted metadata and retired originals are currently retained without a hard-purge operation. Define lawful/user-approved retention durations, audit obligations, operator access and backups before scheduling deletion. |
| 10. Hard purge workflow | Must depend on an accepted retention policy, explicit authority, reviewable target inventory and recovery constraints. It must not infer ownership or recursively erase shared/global/personal paths. |
| 11. Malware scanning integration | PDF parser/type/size checks do not substitute for malware scanning. A later scanner needs quarantine state, bounded execution, fail-closed publication, safe error codes and operational ownership. No scanner is claimed in this phase. |
| 12. Object storage / S3 backend | Existing canonical storage keys provide a useful adapter seam. Preserve opaque tenant/asset/generation keys and fresh API authorization; do not expose permanent public object URLs. Define encryption, credentials, multipart recovery and signed URL expiry before adopting it. |
| 13. Per-library storage quota | Current per-file bounds limit a request, not aggregate tenant storage. Later quotas need an atomic reservation/accounting policy for uploads, retained originals and generations, plus release/recovery under acknowledgement loss. |
| 14. Document licensing metadata | Add provenance and an explicit bounded licence vocabulary only with product requirements and staff editing policy. A licence field alone must not automatically publish a document. |
| 15. Copyright/access restrictions | Need a defined policy for file access versus study tools, audience and jurisdiction/licence constraints. Enforce decisions server-side at each operation, without claiming that previously downloaded bytes can be recalled. |
| 16. Expiring access windows | Current library membership and lifecycle gates are immediate server checks. Later embargo/expiry windows require timezone rules, boundary tests and checks before retrieval and after generation; cache hits cannot bypass them. |
| 17. Branch-level document ownership | Current canonical tenant is the library UUID. Introduce branch authority only after a branch domain model and membership policy are approved; do not infer branch ownership from shelf location or filename. |
| 18. External institutional repositories | Requires explicit source credentials/consent, authoritative import provenance, bounded fetching, content validation and a mapping review. An external URL or shared work ID must not determine tenant ownership. |
| 19. Bulk digital-asset import | Reuse per-asset validation and idempotent submission after designing bounded batch manifests, per-item outcomes, ownership proof, quota and backpressure. Do not reuse inventory CSV import to ingest private files implicitly. |
| 20. Background processing worker scaling | Current durable jobs use claim leases and generation fencing with one worker loop per RAG process. Scaling needs shared-storage guarantees, aggregate model/GPU capacity, claim/retry limits, monitoring and concurrency tests. Preserve final current-authority checks and stale-worker fencing. |

Priorities for later discussion are operational retention/quota/scanning/storage policy before wider ingestion or public publication, and explicit corpus authorization before any multi-document AI capability. This ordering is a recommendation, not a new acceptance gate or automatic implementation commitment.

The requested next major phase is separately outlined in `institution_v2f_next_scope.md`: tenant **catalogue** intelligence infrastructure, using canonical book metadata rather than private document text. Stop after Part 2F until the user approves a later phase.


## Activity addendum: future identity snapshots

Current account email is hydrated for display while canonical actor/member IDs remain the historical authority. Existing invitation target-email snapshots retain event-time semantics. If historical actor email becomes a retention requirement, review bounded immutable snapshots for newly created events, privacy/access and account-change semantics in a separately approved scope. Do not backfill historical events or change the current persistence model automatically.
