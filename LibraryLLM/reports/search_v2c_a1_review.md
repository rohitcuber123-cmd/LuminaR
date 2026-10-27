# V2C-A.1 corrective patch — 15 October 2026

PASS. The original query now retains canonical Romance inclusion and exclusion, returns CONTRADICTORY, and has no semantic topic. Both source spans survive. Valid distinct-subject clauses execute; scoped aliases and incomplete syntax are handled without importing Global metadata into tenants.

Original admission8/8. Planner1299passed including38new focused cases, unchanged136gold and1000seeded assertions. Tenant184passed; final focused integration51passed (overlapping suites). Recommendation88passed; retrieval/KG/depth/MLT35passed. Frontend885passed; TypeScript and production build passed. Original gold remains independently AI-reviewed, not human-verified accuracy.

Real Chromium covered Global, TEST patron/staff and private patron/staff: valid clauses, contradictions and quoted text. Global/TEST/private patron rejected-session retry retained wizards. Revocation and outsider denial removed private catalogue content. Original user restored; disposable fixtures cleaned. All120live scope probes passed with canonical predicate checks, plus five actual Mongo session flows and outsider API denial.

Parser p50/p95 before3.444/14.954ms; after1.385/18.451ms across600comparable samples each. Median decreased; tail increased3.497ms. New clause lookup is bounded by input, with no facet-regex compilation loop. Full measurements and limits are in performance.json; no general speedup claimed.

Protected captured artifacts/reports match their pre-patch fingerprints. Global count remains5,000,000; existing STALE/degraded baseline_verified=false health is preserved. No production rebuild, migration, new model, Qwen/router, recommendation/MLT, circulation, asset or inventory change. No commit or reset.

Known boundaries: include lists use existing ALL semantics; nested/disjunctive inclusion is unsupported. Unknown subjects are not fabricated. TEST lacks canonical Romance, so explicit inclusion there is unsupported while a text exclusion remains available. Protected quoted titles retain V2C-A's literal semantic behavior. The existing bounded subject projection can return503 when unavailable; it cannot silently fall back to a broad scan for multiple included subjects.

V2C-A.1 corrective patch PASS. The V2C-B precondition may now be rerun.

## Exact final QA summary

```json
{
  "FINAL": "PASS",
  "V2C_A1_PATCH_IMPLEMENTED": "YES",
  "ROOT_CAUSE_IDENTIFIED": "YES",
  "ORIGINAL_INCLUDE_EXCLUDE_FAILURE_FIXED": "YES",
  "ORIGINAL_ADMISSION_TESTS": "8/8 PASS",
  "INCLUDE_SUBJECT_RECOGNIZED": "PASS",
  "EXCLUDE_SUBJECT_RECOGNIZED": "PASS",
  "CANONICAL_CONTRADICTION_DETECTED": "PASS",
  "CLAUSE_ORDER_INDEPENDENCE": "PASS",
  "VALID_NONCONFLICTING_CLAUSES_PASS": "PASS",
  "SEMANTIC_LEFTOVER_CLEAN": "PASS",
  "QUOTED_TITLE_PROTECTION_PASS": "PASS",
  "CANONICAL_ALIAS_CONFLICT_PASS": "PASS",
  "INCOMPLETE_CLAUSE_DECISION_PASS": "PASS",
  "V2C_A_GOLD_REGRESSION": "136/136 PASS; unchanged AI-reviewed labels",
  "V2C_A_SEEDED_REGRESSION": "1000/1000 PASS",
  "V2A_V2B_REGRESSION": "PASS;1299 planner tests including38new; overlapping focused suites not summed",
  "DATABASE_BACKED_ADMISSION": "PASS;184tenant +51final focused tests (overlap)",
  "GLOBAL_SEARCH_PASS": "PASS",
  "PUBLIC_TENANT_SEARCH_PASS": "PASS",
  "PRIVATE_TENANT_SEARCH_PASS": "PASS",
  "PRIVATE_OUTSIDER_DENIAL_PASS": "PASS",
  "MEMBERSHIP_REVOCATION_PASS": "PASS",
  "V2B_SESSION_PRESERVED": "PASS",
  "V2B_PERSONALIZATION_PRESERVED": "PASS",
  "RECOMMENDATION_REGRESSION_PASS": "PASS",
  "MORE_LIKE_THIS_REGRESSION_PASS": "PASS",
  "STAFF_INVENTORY_PRESERVED": "PASS",
  "BROWSER_ACCEPTANCE": "PASS",
  "PRODUCTION_BUILD": "PASS",
  "CROSS_TENANT_LEAKS": "0 observed",
  "FRONTEND_FULL_SUITE": "885/885 PASS; TypeScript check PASS",
  "PARSER_P50_P95_BEFORE": {
    "p50_ms": 3.4435499992468976,
    "p95_ms": 14.953800000512274
  },
  "PARSER_P50_P95_AFTER": {
    "p50_ms": 1.3846499996361672,
    "p95_ms": 18.45089999915217
  },
  "GLOBAL_BOOK_COUNT": 5000000,
  "GLOBAL_SEARCH_HEALTH": "STALE/degraded; baseline_verified=false preserved; functional HTTP200 search.",
  "GLOBAL_HNSW_REBUILT": "NO",
  "GLOBAL_KG_REBUILT": "NO",
  "TENANT_HNSW_KG_REBUILT": "NO",
  "QWEN_CHANGED": "NO",
  "V2C_B_PRECONDITION_PASS": "YES",
  "V2C_B_IMPLEMENTATION_STARTED": "NO",
  "V2C_C_STARTED": "NO",
  "PART_2I_STARTED": "NO"
}
```
