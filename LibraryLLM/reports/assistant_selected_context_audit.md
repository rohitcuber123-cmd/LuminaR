# Selected context pre-edit audit

Observed exactly: two visible selected books, natural text "what are the differences in these books", and "Choose the book you mean" with six unrelated M68000/MC68020 catalogue choices. Saved source before application edits in assistant_selected_source_baseline/. Actual browser request was captured by a temporary Vite observer without recording auth headers.

```json
{
  "message": "what are the differences in these books",
  "selected_work_ids": [
    "OL21640039W",
    "OL44077582W"
  ],
  "recent_work_ids": [],
  "page_context": {
    "work_ids": [
      "OL44077582W",
      "OL103586W",
      "OL17950564W",
      "OL15744700W"
    ]
  },
  "conversation_id": null,
  "action": null,
  "pending_action_id": null
}
```

Finding **B: backend routing bug** for ordinary typed messages. The visible pair and POST request contained both canonical IDs, in tray order: The Psychology of Money / Morgan Housel (OL21640039W), The Art Of Spending Money / Morgan Housel (OL44077582W). This was not a missing-selection request.

Existing fast routing matched only "compare these" and "compare these two"; the reported phrase invoked Qwen. The frozen-source resolver trace proves Qwen generated `mentioned_titles=["OL21640039W","OL44077582W"]`, instead of title strings or canonical bound arguments. The resolver's selected-title disambiguation found no selected title equal to an ID, cleared its selected pool, called catalogue title resolution for OL21640039W, and then semantic Search of OL21640039W with count=6. The unrelated processor manuals are those fuzzy search candidates. There is no M68000-specific fix.

```json
{
  "trace_id": "82bdffc0f72541bd83a2dc266af75703",
  "message": "what are the differences in these books",
  "selected_work_ids": [
    "OL21640039W",
    "OL44077582W"
  ],
  "parsed": {
    "intent": "COMPARE_BOOKS",
    "confidence": 1.0,
    "query": null,
    "mentioned_titles": [
      "OL21640039W",
      "OL44077582W"
    ],
    "mentioned_authors": [],
    "resolved_work_ids": [],
    "requested_result_count": 10,
    "filters": {
      "available_only": false,
      "author": null,
      "subject": null,
      "exclude_seed_authors": false,
      "sort_preference": "relevance"
    },
    "comparison_fields": [],
    "ordinal_references": [],
    "reference": "none",
    "requires_confirmation": false,
    "clarification_needed": false,
    "unsupported_filters": []
  },
  "title_resolution": [
    {
      "title": "OL21640039W",
      "author": null
    }
  ],
  "search": [
    {
      "query": "OL21640039W",
      "count": 6
    }
  ]
}
```

Additional frontend defects: explicit result/card actions supplied one-request selected_work_ids overrides (or [] for explain/paging), so those payloads could disagree with the visible tray. App initialization also called syncOwner(null) followed by syncOwner(current_owner), discarding same-owner restored selection on reload. Neither caused the captured typed-message failure, but both violate the requested selection contract.

Initial exact UI response profile: 23.189 seconds server total, 1 Qwen intent call, 0 Qwen response calls, title resolution + semantic fallback. Warm baseline comparison median: 11882.6 ms, always CLARIFICATION. Screenshot: assistant_selected_before.png. No catalogue/search/recommendation scoring was edited before these observations.
