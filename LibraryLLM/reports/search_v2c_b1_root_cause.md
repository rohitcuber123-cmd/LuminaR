# V2C-B.1 verified root cause and repair

The original real-Mongo reproducer returned HTTP 404 for an unissued choice but deleted the accepted Search context. Full prepatch documents are retained in `search_v2c_b1_prepatch_reproducer.json`; the unchanged-state assertion failed before edits.

`authorized()` wrapped both `catalogue.read_context` and its `yield` in one HTTPException handler. The endpoint's choice lookup raised 404 after yield; Python propagated it back into that handler, which interpreted it as access loss and called invalidation. `tenant_search` had a second status-only invalidation path.

The patched dependency catches only context entry failures. `ExitStack` retains normal lock release while endpoint exceptions propagate outside the authorization handler. In both paths a fresh canonical patron/staff guard must confirm access loss before invalidating affected tenant context and personalization. A resource/choice/session 404 alone never proves access loss. Existing role policy remains unchanged.

Resolution loads a scope-bound issued choice, previews and validates it, releases the catalogue lock, obtains a one-use Mongo claim, and enters the existing executor with fresh authority. The accepted-context version CAS prevents stale overwrite. A pending deadline check and server-clock expiry predicate fence existing-context commits. The accepted document records a receipt; only after successful commit is pending marked used. Errors before commit release the claim, while errors after commit cannot make it reusable. No delete/recreate rollback or distributed transaction was added. A crashed claim requires resubmission after its bounded TTL rather than unsafe claim stealing.

Context-limit eviction now occurs only after successful insertion. A late expiry before first insertion cannot evict any other accepted context. Deterministic real-Mongo tests cover that edge, duplicate submissions, forged/valid overlap, expiry, revocation, a newer accepted plan, and errors before and after commit.

Chip addresses remain removal-only and backend validated. Multi-value subject/exclusion addresses remove one exact item; unknown/injected addresses cannot add fields, change scope, generation, identity or personalization owner. The accepted parser source is unchanged.
