# V2C-B.1 acceptance review

V2C-B corrective lifecycle patch PASS. V2C-B accepted for review. V2C-C may now be planned.

The original real-Mongo reproducer returned HTTP 404 for an unissued choice but deleted the accepted Search context. Full prepatch documents are retained in `search_v2c_b1_prepatch_reproducer.json`; the unchanged-state assertion failed before edits.

`authorized()` wrapped both `catalogue.read_context` and its `yield` in one HTTPException handler. The endpoint's choice lookup raised 404 after yield; Python propagated it back into that handler, which interpreted it as access loss and called invalidation. `tenant_search` had a second status-only invalidation path.

The patched dependency catches only context entry failures. `ExitStack` retains normal lock release while endpoint exceptions propagate outside the authorization handler. In both paths a fresh canonical patron/staff guard must confirm access loss before invalidating affected tenant context and personalization. A resource/choice/session 404 alone never proves access loss. Existing role policy remains unchanged.

Resolution loads a scope-bound issued choice, previews and validates it, releases the catalogue lock, obtains a one-use Mongo claim, and enters the existing executor with fresh authority. The accepted-context version CAS prevents stale overwrite. A pending deadline check and server-clock expiry predicate fence existing-context commits. The accepted document records a receipt; only after successful commit is pending marked used. Errors before commit release the claim, while errors after commit cannot make it reusable. No delete/recreate rollback or distributed transaction was added. A crashed claim requires resubmission after its bounded TTL rather than unsafe claim stealing.

Context-limit eviction now occurs only after successful insertion. A late expiry before first insertion cannot evict any other accepted context. Deterministic real-Mongo tests cover that edge, duplicate submissions, forged/valid overlap, expiry, revocation, a newer accepted plan, and errors before and after commit.

Chip addresses remain removal-only and backend validated. Multi-value subject/exclusion addresses remove one exact item; unknown/injected addresses cannot add fields, change scope, generation, identity or personalization owner. The accepted parser source is unchanged.


Fresh verification: 1307 planner (1253+54 disjoint cases);252 tenant;88 catalogue;35 retrieval. Original83+cache test=84 pass, overlapping. Focused counts are not added. Frontend903/903; focused18/18; TypeScript/build pass. Lint completes with established warnings. No overlapping counts summed.

Real Chromium covered all six required identities/scopes. Final server PID29156 passed the Mongo-correlated forged/valid sequence and four chip edits. Exact widths320/375/390/768/1024/1440 have no horizontal overflow and >=44px target heights. Original user restored; QA490/491 disabled, memberships removed, QA library archived.

Typos/corrections remain explicitly PARTIAL for subject-only bounded breadth. Accessibility is PARTIAL only for untested hardware touch/screen-reader/contrast scope; tested keyboard/ARIA/focus/IME/geometry pass. No broad product accessibility claim. Global latency tail variation remains visible; no speedup claimed.

Authoritative Mongo luminar_library retains5,000,000 books and STALE/degraded baseline_verified=false health. No HNSW/KG/model/reco/MLT/Inventory changes or rebuilds. No destructive migration.

Original PARTIAL evidence: search_v2c_b1_history/manifest.json, all68 archived hashes verified unchanged. Current B reports point to this corrective evidence; raw historical runs are not relabelled.

| Field | Result |
|---|---|
| FINAL | PASS |
| V2C_B1_IMPLEMENTED | YES |
| ROOT_CAUSE_CONFIRMED | YES |
| AUTHORIZATION_BOUNDARY_FIXED | PASS |
| FORGED_CHOICE_REJECTED | PASS |
| VALID_CHOICE_AFTER_FORGED_REQUEST | PASS |
| EXPIRED_CLARIFICATION_STATE_SAFE | PASS |
| CROSS_CLARIFICATION_REJECTED | PASS |
| CROSS_USER_REJECTED | PASS |
| CROSS_SID_REJECTED | PASS |
| CROSS_LIBRARY_REJECTED | PASS |
| CROSS_WORKSPACE_REJECTED | PASS |
| DUPLICATE_CHOICE_SAFE | PASS |
| CONCURRENT_STALE_OPERATIONS_SAFE | PASS |
| MEMBERSHIP_REVOCATION_STILL_INVALIDATES | PASS |
| V2B_SESSION_PRESERVED | PASS |
| QUERY_CHIP_EDITING | PASS |
| RUNNING_SERVER_CHIP_EDITING | PASS |
| CORRECTED_ROLE_CHANGE_TEST | PASS |
| SUPPORTED_FILTER_TEMPLATES | PASS |
| INLINE_CLARIFICATION | PASS |
| CATALOGUE_AWARE_AUTOCOMPLETE | PASS |
| GLOBAL_SEARCH | PASS |
| PUBLIC_TENANT_SEARCH | PASS |
| PRIVATE_TENANT_SEARCH | PASS |
| PRIVATE_OUTSIDER_DENIAL | PASS |
| V2C_A_REGRESSION | PASS |
| V2C_A1_REGRESSION | PASS |
| RECOMMENDATION_REGRESSION | PASS |
| MORE_LIKE_THIS_REGRESSION | PASS |
| STAFF_INVENTORY_REGRESSION | PASS |
| TYPESCRIPT | PASS |
| PRODUCTION_BUILD | PASS |
| BROWSER_ACCEPTANCE | PASS |
| RESPONSIVE | PASS |
| DOWNSTREAM_404_CAUSES_INVALIDATION | NO |
| FORGED_CHOICE_MUTATED_ACCEPTED_STATE | NO |
| FORGED_CHOICE_MUTATED_PENDING_STATE | NO |
| TYPO_SUGGESTIONS | PARTIAL |
| TYPO_CORRECTION | PARTIAL |
| CORRECTIONS | PARTIAL |
| ACCESSIBILITY | PARTIAL |
| BACKEND_REGRESSION | 1307 planner (1253+54 disjoint cases);252 tenant;88 catalogue;35 retrieval. Original83+cache test=84 pass, overlapping. Focused counts are not added. |
| FRONTEND_FULL_SUITE | 903/903 PASS; focused18/18 overlaps. |
| PARSER_P50_P95 | 0.960 / 18.722 ms (n=600) |
| SUGGESTION_WARM_P50_P95 | {"GLOBAL": "9.509 / 12.432 ms (n=20)", "TEST": "53.104 / 77.601 ms (n=20)", "PRIVATE_PATRON": "26.995 / 30.474 ms (n=20)", "PRIVATE_STAFF": "28.749 / 32.562 ms (n=20)"} |
| CLARIFICATION_GENERATION_P50_P95 | 27.540 / 32.716 ms (n=20) |
| CLARIFICATION_RESOLUTION_P50_P95 | 301.489 / 354.000 ms (n=20) |
| GLOBAL_SEARCH_P50_P95 | 217.989 / 397.000 ms (n=20) |
| PUBLIC_SEARCH_P50_P95 | 543.496 / 611.471 ms (n=20) |
| PRIVATE_READY_SEARCH_P50_P95 | 203.827 / 235.619 ms (n=20) |
| PRIVATE_NOT_BUILT_SEARCH_P50_P95 | 88.769 / 108.148 ms (n=20) |
| GLOBAL_BOOK_COUNT | 5000000 |
| GLOBAL_SEARCH_HEALTH | STALE/degraded; baseline_verified=false; ordinary Search HTTP200 |
| GLOBAL_HNSW_REBUILT | NO |
| GLOBAL_KG_REBUILT | NO |
| TENANT_HNSW_KG_REBUILT | NO |
| EMBEDDING_MODEL_CHANGED | NO |
| CROSSENCODER_CHANGED | NO |
| QWEN_CHANGED | NO |
| RECOMMENDATION_CHANGED | NO |
| MORE_LIKE_THIS_CHANGED | NO |
| STAFF_INVENTORY_CHANGED | NO |
| V2C_C_STARTED | NO |
| PART_2I_STARTED | NO |
