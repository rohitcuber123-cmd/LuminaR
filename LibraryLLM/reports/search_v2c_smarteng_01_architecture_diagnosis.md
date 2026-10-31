# Architecture diagnosis
All150 frozen C5E-R rows were traced before implementation: [search_v2c_smarteng_baseline_traces.jsonl](D:/SDC/LibraryLLM/reports/search_v2c_smarteng_baseline_traces.jsonl). Baseline57/150 typed,97/150 execution,8/100 unsafe and45/50 missed.

Confirmed defects: modality was assigned after scalar extraction and covered only a few advisory adjectives; unquoted category/classification ownership missed common syntax and repairs; sort wording entered the missing-rating guard; deferred relationships were reduced to scalar matches; capability validation overwrote more informative unresolved decisions; negative domains depended on narrow phrase templates.

The first incorrect transformations and actual functions are recorded in [search_v2c_smarteng_architecture_diagnosis.json](D:/SDC/LibraryLLM/reports/search_v2c_smarteng_architecture_diagnosis.json). These are source-backed defects, not a claim that every strict text mismatch changes meaning. Frozen gold and all old predictions remain intact.

Fresh acceptance still found structural failures: delimited omitted values, inherited incidental facet matches, missing WITHOUT whole-word ownership and overly narrow frame proof. The architecture is not qualified for production.
