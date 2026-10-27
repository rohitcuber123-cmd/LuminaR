# Search Intelligence V2A review

## A. Final result

PARTIAL: implementation/API/component checks complete; browser acceptance pending

## B. Root limitation

V1 lacked explicit intents, negative constraints and KG retrieval contribution; V1 canonical facets/ratings already worked.

## C. Query plan

Typed deterministic plan with parser version, intent, constraints/exclusions, preferences and KG provenance.

## D. Intent model

FIND_EXACT, FIND_AUTHOR, BROWSE_CATEGORY, DISCOVER_TOPIC, LEARN, REFERENCE, RESEARCH, FIND_AVAILABLE, FIND_ONLINE, DISCOVER_RELATED

## E. Search UX

Four themed modes; Smart default; Global/patron/staff routes retained.

## F. Facets

Actual canonical subjects, same-scope vocabulary; no invented genre field.

## G. Corrections

Exact → supported alias → conservative bounded typo; visible truthful correction.

## H. Ratings

Strict > versus >=, bounds and missing-value exclusions preserved.

## I. Negatives

Canonical phrase matching in title/authors/subjects/description; removable exclusion chip.

## J. Format/availability

Real current capabilities and authoritative Part 2B stock; no staff-only patron assets.

## K. HNSW

Accepted MiniLM/FAISS with one optional secondary search, canonical strict checks, existing CrossEncoder.

## L. KG

Actual global and TEST graph generations used; no new graph.

## M. Expansion rules

One projected subject hop/two actual edges; ≤64 books/1,024 edges/6 concepts; primary priority.

## N. Global

Actual 5M catalogue; strict filters and exact lookup; global graph only.

## O. Public tenant

TEST uses exact tenant HNSW and graph; four readable Online results in live query.

## P. Private tenant

Authorized live staff scope works; outsiders 404; disposable private member expansion/privacy tested.

## Q. Interpretation

Intent, topic, genre, numeric/format/exclusion chips, correction and related-concept disclosure.

## R. Explanations

Minimal interpretation plus existing rating/format availability badges; no internal scores or node IDs shown.

## S. Cache isolation

No new result cache; scope/generations/parser/constraints included in plan identity and accepted artifact keys.

## T. Performance

See live five-sample performance report; candidate counts and graph cost recorded.

## U. Browser

PARTIAL: the original 5173 origin remained denied, but the in-app browser opened the app on loopback port 5174. Browser-observed scenarios passed for Global category/author/typo/exclusion/rating/Online-only searches, TEST context selection and results, and Private Archive QA A online results with a Know More action. The detailed evidence is in `search_v2a_browser.json`.

## V. Accessibility

Structural axe and labeled controls pass. Browser accessibility trees exposed the page headings, form labels, query chips, result links, and pagination. The compact workspace menu opened and exposed its navigation links. Full keyboard-only traversal, contrast measurement, and the exact six-size viewport matrix remain pending because the active in-app browser controls expose no explicit viewport override.

## W. Backend tests

{"search_v2a_global_engine.xml": {"tests": 23, "failures": 0, "errors": 0}, "search_v2a_global_regression.xml": {"tests": 23, "failures": 0, "errors": 0}, "search_v2a_initial_regression.xml": {"tests": 77, "failures": 0, "errors": 0}, "search_v2a_more_like_this.xml": {"tests": 12, "failures": 0, "errors": 0}, "search_v2a_planner.xml": {"tests": 72, "failures": 0, "errors": 0}, "search_v2a_private_targeted.xml": {"tests": 10, "failures": 0, "errors": 0}, "search_v2a_recommendation_catalogue.xml": {"tests": 88, "failures": 0, "errors": 0}, "search_v2a_tenant.xml": {"tests": 16, "failures": 0, "errors": 0}, "search_v2a_tenant_regression.xml": {"tests": 150, "failures": 0, "errors": 0}}

## X. Frontend tests

{"tests": 879, "failures": 0, "command": "npm test", "log": ".local/v2a-frontend-full.log"}; TypeScript/build pass; no new lint errors.

## Y. Recommendation

MACHINE contract/algorithms retained; recommendation and More Like This regression pass.

## Z. Preservation

5M count, global HNSW/KG and captured tenant artifact sizes/mtimes/hashes checked; Qwen/router source unchanged.

## AA. Exact files changed

- search/query_plan.py
- search/query_expansion.py
- search/query_execution.py
- search/luminar_search.py
- frontend/src/lib/searchNlu.ts
- frontend/src/components/SearchIntelligence.tsx
- frontend/src/styles/product.css
- frontend/tests/search-nlu.test.tsx
- tests/test_search_v2a.py
- tests/test_search_depth.py
- tests/institution_v2g/test_query_v2a.py
- scripts/search_v2a_audit_server.py
- scripts/search_v2a_live.py
- scripts/search_v2a_reports.py

## AB. Reports

- search_v2a_accessibility.json
- search_v2a_baseline.json
- search_v2a_before_after.md
- search_v2a_browser.json
- search_v2a_constraint_enforcement.json
- search_v2a_facet_vocabulary.json
- search_v2a_final_qa.json
- search_v2a_global_engine.xml
- search_v2a_global_regression.xml
- search_v2a_hnsw_integration.json
- search_v2a_initial_regression.xml
- search_v2a_intent_model.md
- search_v2a_kg_integration.md
- search_v2a_kg_runtime.json
- search_v2a_metadata_audit.md
- search_v2a_more_like_this.xml
- search_v2a_next_scope.md
- search_v2a_performance.json
- search_v2a_planner.xml
- search_v2a_preservation.json
- search_v2a_private_library.json
- search_v2a_private_targeted.xml
- search_v2a_query_plan_architecture.md
- search_v2a_recommendation_catalogue.xml
- search_v2a_recommendation_regression.json
- search_v2a_regression.json
- search_v2a_responsive.json
- search_v2a_review.md
- search_v2a_tenant.xml
- search_v2a_tenant_regression.xml
- search_v2a_typo_handling.md

## AC. Known limits

Finite grammar; literal exclusion; co-occurrence not synonymy; bounded recall/sorts; global year absent; cold graph IO/timeouts; browser review pending.

## AD. V2B scope

Review proposals only: consented personalization/session refinement, judged relevance and metadata coverage. Nothing from V2B or Part 2I implemented.

## Final QA

```json
{
  "FINAL": "PARTIAL: implementation/API/component checks complete; browser scenarios observed on 127.0.0.1:5174; exact six-size responsive and full keyboard review pending",
  "SMART_SEARCH": "YES",
  "NATURAL_LANGUAGE_QUERY_PLAN": "YES",
  "INTENT_AWARE_SEARCH": "YES",
  "QUERY_USES_QWEN": "NO",
  "SEARCH_MODES": [
    "SMART",
    "GENRE_SUBJECT",
    "TITLE_AUTHOR",
    "EXACT"
  ],
  "FICTION_QUERY_INTENT": "BROWSE_CATEGORY",
  "FICTION_QUERY_FILTER": "subjects contains canonical Fiction",
  "FICTION_TITLE_FALSE_POSITIVE_COUNT": 0,
  "SEMANTIC_QUERY_HNSW_USED": "YES",
  "KG_SEARCH_INTEGRATION": "YES",
  "KG_EXPANSION_BOUNDED": "YES",
  "KG_PRIMARY_CONCEPT_PRESERVED": "YES",
  "KG_UNAVAILABLE_SEARCH_PASS": "YES",
  "PRIVATE_KG_LEAK": "NO",
  "RATING_GT_4_PASS": "YES",
  "NEGATIVE_CONSTRAINT_PASS": "YES",
  "ONLINE_QUERY_PASS": "YES (tenant 4 public / 2 private authorized results; unsupported Global entitlement returns zero)",
  "QUERY_CHIPS_PASS": "YES (component tests and in-app browser observations on 127.0.0.1:5174)",
  "TYPO_SUGGESTION_PASS": "YES",
  "RECOMMENDATION_REGRESSION_PASS": "YES",
  "MORE_LIKE_THIS_REGRESSION_PASS": "YES",
  "GLOBAL_HNSW_REBUILT": "NO",
  "GLOBAL_KG_REBUILT": "NO",
  "BROWSER_CONTEXTS_OBSERVED": ["GLOBAL", "TEST", "Private Archive QA A"],
  "BROWSER_QUERY_SCENARIOS": "PASS for category, author, typo, rating chip, exclusion, Online-only empty state, private online holdings, and Know More on an online item",
  "BROWSER_EXACT_SIX_VIEWPORT_MATRIX": "PENDING: active in-app browser control has no explicit viewport override",
  "BROWSER_FULL_KEYBOARD_AND_CONTRAST_REVIEW": "PENDING"
}
```
