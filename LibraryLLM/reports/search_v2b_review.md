# LuminaR Search Intelligence V2B review

Generated 2026-10-15T05:43:55.947681+00:00.

## A. FINAL PASS / PARTIAL / FAIL

PASS for scoped V2B acceptance; limitations below.

## B. V2A BROWSER CLOSURE STATUS

PASS: all four modes, typo, negative/rating/online constraints, KG disclosure, outsider denial and exact six-size matrix.

## C. SESSION ARCHITECTURE

Server UUID context bound to user + JWT sid + library + workspace; Mongo shared with fallback.

## D. SESSION REFINEMENT RULES

Deterministic field edits; independent topics reset; explicit instead retains other constraints; see rules JSON.

## E. SESSION EXPIRY / CLEARING

30-minute idle / 60-minute hard, request-time enforcement + Mongo TTL cleanup; clear current context and logout preclear tested.

## F. GLOBAL SESSION BEHAVIOR

PASS: topic/rating/format retained and clear starts fresh.

## G. PUBLIC TENANT SESSION BEHAVIOR

PASS: TEST member refinement, strict ownership, empty means empty.

## H. PRIVATE TENANT SESSION BEHAVIOR

PASS: member plan restored only within exact private scope; outsider denied.

## I. PERSONALIZATION SIGNAL AUDIT

Own Reading List only; audited alternatives intentionally unused; see signal audit.

## J. PERSONALIZATION PROFILE DESIGN

Temporary bounded canonical subject/author counts; exact scope cache, 60 seconds, 256 entries.

## K. PERSONALIZATION WEIGHTS / BOUNDS

0.02; <=2 positions in adjacent <=3-row bands, raw CE gap <=0.1; strict filters/sorts remain authoritative

## L. GLOBAL PERSONALIZATION

PASS: ON/OFF same candidate set; canonical reasons; controlled tests prove bounded order change, cold/OFF neutral.

## M. PUBLIC TENANT PERSONALIZATION

PASS: authorized public metadata only, no foreign holdings introduced.

## N. PRIVATE TENANT PERSONALIZATION

PASS: local-only profile reason observed; private words never enter Global/foreign scope.

## O. MULTI-LIBRARY ISOLATION

PASS: browser restored distinct TEST/private plans; account/workspace/JWT injections denied in tests.

## P. MEMBERSHIP REVOCATION

Active private membership removed by normal institution service; next browser refinement showed Current membership is required. No private cards/chips/reasons; affected server context count 0.

## Q. EXPLAINABILITY

At most two literal canonical reasons; no scores/confidence or invented history.

## R. PERSONALIZATION TOGGLE

Default OFF; account boolean; OFF skips lookup and preserves baseline ranking while session/NLU/KG remain active.

## S. KG INTERACTION

Existing expansion recomputed from current plan; strict filters and primary/secondary ranking boundaries preserved.

## T. HNSW / CROSSENCODER INTERACTION

Accepted retrieval and CE retained; personalization only bounded post-CE reordering; no model/index builds.

## U. SECURITY / PRIVACY

Fresh auth before state/cache; ephemeral plans, own saves only, private/no-store headers, logout clearing.

## V. PERFORMANCE

5 samples/group: Global p50 235.38→199.56ms session /163.92ms profile; TEST 628.47→625.07/730.41; private 204.12→204.02/201.94. Not a load test or speedup claim.

## W. BROWSER VALIDATION

PASS through approved Chromium 5174; member/outsider, Global/public/private, switching, clear and revocation.

## X. ACCESSIBILITY

PASS for scoped search UI: structural axe, keyboard/focus, measured text contrast; see report.

## Y. RESPONSIVE

PASS: 18 exact measurements across six CSS viewports; no horizontal overflow.

## Z. BACKEND TESTS

163 tenant regressions; 103 planner; 53 global engine; 88 recommendation/catalogue; 12 More Like This. Suites overlap.

## AA. FRONTEND TESTS

883 full-suite tests passed; latest session 5/5, private 9/9; TypeScript/Vite build passed. Existing unrelated warnings retained.

## AB. RECOMMENDATION REGRESSION

PASS: 88 tests; algorithm source checksum preserved.

## AC. MORE LIKE THIS REGRESSION

PASS: 12 tests; implementation unchanged.

## AD. PRESERVATION

5,000,000 global books; protected source hashes and large artifact size/mtime unchanged; accepted tenant artifacts unchanged. Synthetic fixtures cleaned.

## AE. EXACT FILES CHANGED

See search_v2b_changed_files.json. Existing shared-file changes are retained; no reset/commit/blanket staging.

## AF. REPORTS

See report inventory below; baseline, live aggregate evidence, XML suites and full QA retained.

## AG. KNOWN LIMITATIONS

- Finite English refinement grammar; no fully conversational LLM.
- Opt-in Reading List only; no measured judged relevance improvement. Real queries may keep identical order.
- Profile cache may reflect saved-book changes after up to 60 seconds; authorization is always fresh.
- Search remains bounded by accepted candidate pools; rare facet fallback can still time out when required artifacts/indexes are unavailable.
- Browser private fixture used NOT_BUILT fallback; READY private semantic path covered separately by live API and actual FAISS/KG isolated tests.
- Existing unrelated lint/build warnings remain. Accessibility scope is the modified search UI.
- Search health returns HTTP 200 but status degraded / index_status STALE because the preserved September 24 active generation manifest has baseline_verified=false. Active vectors remain 5,000,000 and pending=false. No rebuild or health-status masking was performed.

## AH. RECOMMENDED NEXT SCOPE

Review V2B first; optional judged relevance evaluation and broader latency sampling. Part 2I not started.

## Final QA summary

```json
{
  "SESSION_AWARE_SEARCH": "YES",
  "SESSION_REFINEMENT_PASS": "YES",
  "SESSION_CLEAR_PASS": "YES",
  "GLOBAL_SESSION_ISOLATION": "YES",
  "PUBLIC_TENANT_SESSION_PASS": "YES",
  "PRIVATE_TENANT_SESSION_PASS": "YES",
  "PRIVATE_REVOCATION_PASS": "YES",
  "PERSONALIZED_SEARCH": "YES",
  "PERSONALIZATION_TOGGLE": "YES",
  "PUBLIC_TENANT_PERSONALIZATION_PASS": "YES",
  "PRIVATE_TENANT_PERSONALIZATION_PASS": "YES",
  "EXPLAINABLE_RESULT_REASONS": "YES",
  "KG_SESSION_INTEGRATION_PASS": "YES",
  "HNSW_PRESERVED": "YES",
  "CROSSENCODER_PRESERVED": "YES",
  "RECOMMENDATION_REGRESSION_PASS": "YES",
  "MORE_LIKE_THIS_REGRESSION_PASS": "YES",
  "MULTI_LIBRARY_SESSION_LEAK": "NO",
  "ACCOUNT_SWITCH_SESSION_LEAK": "NO",
  "PERSONALIZATION_OVERRIDES_STRICT_FILTER": "NO",
  "PRIVATE_PROFILE_CROSS_TENANT_LEAK": "NO",
  "GLOBAL_PRIVATE_OWNERSHIP_LEAK": "NO",
  "INTERNAL_SCORE_EXPOSED": "NO",
  "GLOBAL_HNSW_REBUILT": "NO",
  "GLOBAL_KG_REBUILT": "NO",
  "SESSION_EXPIRY": "30-minute idle / 60-minute hard, request-time enforcement + Mongo TTL cleanup",
  "PERSONALIZATION_SIGNALS": [
    "Own canonical saved global books",
    "Own local-only saved books within currently authorized tenant"
  ],
  "PERSONALIZATION_MAX_BOOST": "0.02; <=2 positions in adjacent <=3-row bands, raw CE gap <=0.1; strict filters/sorts remain authoritative",
  "V2A_BROWSER_ACCEPTANCE": "PASS"
}
```

## Report inventory

- search_v2b_accessibility.json
- search_v2b_baseline.json
- search_v2b_browser.json
- search_v2b_browser_fixture.json
- search_v2b_changed_files.json
- search_v2b_explanations.json
- search_v2b_final_browser.png
- search_v2b_final_qa.json
- search_v2b_global.json
- search_v2b_global_engine.xml
- search_v2b_membership_revocation.json
- search_v2b_more_like_this.xml
- search_v2b_multi_library.json
- search_v2b_next_scope.md
- search_v2b_performance.json
- search_v2b_personalization_architecture.md
- search_v2b_personalization_signal_audit.md
- search_v2b_personalization_weights.json
- search_v2b_planner.xml
- search_v2b_preservation.json
- search_v2b_privacy_security.json
- search_v2b_private_tenant.json
- search_v2b_public_tenant.json
- search_v2b_recommendation_catalogue.xml
- search_v2b_recommendation_regression.json
- search_v2b_regression.json
- search_v2b_responsive.json
- search_v2b_review.md
- search_v2b_services.json
- search_v2b_session_architecture.md
- search_v2b_session_rules.json
- search_v2b_tenant.xml
- search_v2b_tenant_regression.xml
- search_v2b_timezone_regression.xml
- search_v2b_v2a_browser_closure.json
