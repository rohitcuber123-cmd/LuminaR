# Institution Part 2B architecture

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
