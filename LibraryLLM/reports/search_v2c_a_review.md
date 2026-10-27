# Search Intelligence V2C-A review

V2C-A is implemented and accepted for review. The original query now produces Fiction + rating >3 with no semantic remainder; the wizard variant retains only `wizards` as its topic. Typed rejections return zero results and leave the last accepted session unchanged.

Implementation extends the accepted QueryPlan, existing sessions and scoped execution. See `search_v2c_a_constraint_grammar.md` for source mapping, supported grammar and truthful capability decisions. No new retrieval engine, model or session store was introduced.

Validation: planner/legacy regression1261; tenant175; recommendation88; retrieval/MLT35; final integration41 passed. Counts overlap across focused reruns and must not be summed as unique tests. Full frontend885 passed; final session6 passed; production build and lint exit0. One initial combined-suite teardown fixture conflict was resolved by isolated-directory runs; earlier reports remain available.

Gold agreement136/136 in17 families, independently reviewed by a separate AI agent, plus1000 distinct seeded template assertions passed. Neither is human-verified or a real-world accuracy benchmark. Gold labels were authored independently of parser outputs. See independent review and adversarial reports.

Real Chromium ran all9 requested queries in Global, TEST patron/staff and private patron/staff views. Thirty exact responsive checks across320/375/390/768/1024/1440 had no horizontal overflow. Keyboard Enter/Space/Tab and named status notices were checked. Revocation removed access on the next request; outsider patron/staff access was denied with no private entities. Normal user session restored; disposable users disabled and private QA library archived.

Global search final p50/p95 189.634/222.640ms (baseline186.176/221.719); TEST 573.095/615.131ms (565.857/646.172); private READY 215.869/266.867ms (208.245/238.071). A material initial O(vocabulary) regex regression was found and removed. The private tail remains about12% above baseline in20 resident requests; no throughput/speedup claim. Final Global parser p50/p95 0.588/8.779ms across420 samples; query mixes differ from old parser baseline.

Preservation: all captured protected source/global/tenant fingerprints match. Multi-GB files compare size+nanosecondmtime, small files/manifests alsoSHA256. Global book count remains5,000,000. Global health remains STALE/degraded with baseline_verified=false; it was not masked. No production index rebuild, Qwen/router/recommendation/MLT/inventory algorithm change, commit or reset.

Known boundaries: deterministic grammar does not imply general language understanding; Global publication year/language/live availability restrictions return UNSUPPORTED where canonical enforcement is unavailable. Numeric page count, edition and per-copy not-on-loan filters remain unsupported. Existing `online only` selected-format presence semantics retained; explicit `online but not physical` enforces absence. Accessibility PASS is limited to changed surfaces and requested checks.

V2C-A accepted for review. V2C-B precondition may now be rerun.

## Exact final QA summary

```json
{
  "FINAL": "PASS",
  "V2C_A_IMPLEMENTED": "YES",
  "ORIGINAL_BUG_FIXED": "YES",
  "FICTION_ABOVE_RATING_3_PLAN": {
    "subjects": [
      "Fiction"
    ],
    "rating_min": 3.0,
    "rating_min_exclusive": true,
    "semantic_text": null
  },
  "WRONG_TOPIC_ABOVE_OF_3_PRESENT": "NO",
  "WIZARDS_TOPIC_PRESERVED": "YES",
  "ORDER_INDEPENDENT_GRAMMAR": "YES",
  "SOURCE_SPAN_PROVENANCE": "YES",
  "SEMANTIC_LEFTOVER_GUARD": "YES",
  "RATING_COMPARATOR_SEMANTICS": "PASS",
  "YEAR_COMPARATOR_SEMANTICS": "PASS",
  "AUTHOR_TITLE_PROTECTION": "PASS",
  "NUMERIC_TITLE_PROTECTION": "PASS",
  "FORMAT_EXCLUSIVITY": "PASS",
  "NEGATIVE_CONSTRAINTS": "PASS",
  "AMBIGUITY_DECISION": "PASS",
  "INCOMPLETE_DECISION": "PASS",
  "CONTRADICTION_DECISION": "PASS",
  "UNSUPPORTED_METADATA_SAFE": "PASS",
  "MANUAL_GOLD_QUERY_COUNT": 136,
  "SEEDED_VARIANT_COUNT": 1000,
  "GOLD_PLAN_ACCURACY": "136/136",
  "METAMORPHIC_PASS_RATE": "1000/1000",
  "GLOBAL_SEARCH": "PASS",
  "PUBLIC_TENANT_SEARCH": "PASS",
  "PRIVATE_TENANT_SEARCH": "PASS",
  "PRIVATE_OUTSIDER_DENIAL": "PASS",
  "MEMBERSHIP_REVOCATION": "PASS",
  "V2B_SESSION_REGRESSION": "PASS",
  "V2B_PERSONALIZATION_REGRESSION": "PASS",
  "KG_REGRESSION": "PASS",
  "HNSW_REGRESSION": "PASS",
  "CROSSENCODER_REGRESSION": "PASS",
  "RECOMMENDATION_REGRESSION": "PASS",
  "MORE_LIKE_THIS_REGRESSION": "PASS",
  "STAFF_INVENTORY_EXACT_SEARCH": "PASS",
  "BROWSER_ACCEPTANCE": "PASS",
  "ACCESSIBILITY": "PASS",
  "RESPONSIVE": "PASS",
  "PARSER_P50_P95": {
    "GLOBAL:PARSER": {
      "p50_ms": 0.588,
      "p95_ms": 8.779
    },
    "TEST_PATRON:PARSER": {
      "p50_ms": 0.595,
      "p95_ms": 2.471
    },
    "TEST_STAFF:PARSER": {
      "p50_ms": 0.618,
      "p95_ms": 2.751
    },
    "PRIVATE_PATRON:PARSER": {
      "p50_ms": 0.442,
      "p95_ms": 0.823
    },
    "PRIVATE_STAFF:PARSER": {
      "p50_ms": 0.408,
      "p95_ms": 0.704
    }
  },
  "SEARCH_P50_P95": {
    "GLOBAL": {
      "p50_ms": 189.634,
      "p95_ms": 222.64
    },
    "TEST": {
      "p50_ms": 573.095,
      "p95_ms": 615.131
    },
    "PRIVATE": {
      "p50_ms": 215.869,
      "p95_ms": 266.867
    },
    "PRIVATE_NOT_BUILT": {
      "p50_ms": 91.267,
      "p95_ms": 113.309
    }
  },
  "GLOBAL_SEARCH_HEALTH": "STALE/degraded; preserved baseline_verified=false; HTTP200, accepted retrieval functional.",
  "GLOBAL_HNSW_REBUILT": "NO",
  "GLOBAL_KG_REBUILT": "NO",
  "TENANT_HNSW_KG_REBUILT": "NO",
  "QWEN_CHANGED": "NO",
  "V2C_B_STARTED": "NO",
  "V2C_C_STARTED": "NO",
  "PART_2I_STARTED": "NO"
}
```
