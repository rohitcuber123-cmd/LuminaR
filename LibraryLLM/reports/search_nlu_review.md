# Search Query Understanding V1 review

Implementation and API/component validation are complete. Full acceptance is pending Chromium and six-size visual review due to the saved browser origin restriction.

```json
{
  "SMART_SEARCH_IMPLEMENTED": "YES",
  "GENRE_SUBJECT_MODE": "YES",
  "TITLE_AUTHOR_MODE": "YES",
  "EXACT_MODE": "YES",
  "FICTION_QUERY_PLAN": {
    "raw_query": "fiction",
    "mode": "SMART",
    "semantic_text": null,
    "title_text": null,
    "author_text": null,
    "subjects": [
      "Fiction"
    ],
    "rating_min": null,
    "rating_max": null,
    "rating_min_exclusive": false,
    "rating_max_exclusive": false,
    "year_min": null,
    "year_max": null,
    "year_min_exclusive": false,
    "year_max_exclusive": false,
    "formats": [],
    "availability": null,
    "language": null,
    "exact_text": null,
    "sort": "RELEVANCE",
    "interpretation_confidence": 1.0,
    "corrections": [],
    "unknown_subject": false,
    "suggested_subject": null
  },
  "FICTION_GENRE_FALSE_POSITIVES": 0,
  "SEMANTIC_RATING_QUERY_PLAN": {
    "raw_query": "books about wizards with rating above 4",
    "mode": "SMART",
    "semantic_text": "wizards",
    "title_text": null,
    "author_text": null,
    "subjects": [],
    "rating_min": 4.0,
    "rating_max": null,
    "rating_min_exclusive": true,
    "rating_max_exclusive": false,
    "year_min": null,
    "year_max": null,
    "year_min_exclusive": false,
    "year_max_exclusive": false,
    "formats": [],
    "availability": null,
    "language": null,
    "exact_text": null,
    "sort": "RELEVANCE",
    "interpretation_confidence": 1.0,
    "corrections": [],
    "unknown_subject": false,
    "suggested_subject": null
  },
  "WIZARDS_RATING_ABOVE_4_PASS": "YES",
  "RATING_FILTER_STRICT": "YES",
  "FORMAT_FILTER_PASS": "YES",
  "YEAR_FILTER_PASS": "YES (tenant canonical fields); NOT_SUPPORTED globally",
  "TYPO_FACET_MATCH_PASS": "YES",
  "QUERY_CHIPS_PASS": "YES (component tests); browser pending",
  "TENANT_HNSW_USED_FOR_SEMANTIC": "YES",
  "PRIVATE_LIBRARY_SMART_SEARCH_PASS": "YES",
  "PRIVATE_LIBRARY_FACET_LEAK": "NO",
  "RECOMMENDATION_REGRESSION_PASS": "YES",
  "INVENTORY_EXACT_SEARCH_PASS": "YES",
  "GLOBAL_BOOK_COUNT": 5000000,
  "GLOBAL_HNSW_REBUILT": "NO",
  "GLOBAL_KG_REBUILT": "NO",
  "ACTUAL_BROWSER_REVIEW": "BLOCKED",
  "OVERALL_ACCEPTANCE": "PENDING_BROWSER_REVIEW",
  "PART_2I_STARTED": "NO"
}
```

See search_nlu_before_after.md, search_query_plan_architecture.md, search_nlu_performance.json, search_nlu_regression.json and search_nlu_preservation.json for evidence.
