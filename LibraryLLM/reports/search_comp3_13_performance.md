# Profiling and matched performance

Profile source: [search_comp3_profile_before.txt](D:/SDC/LibraryLLM/reports/search_comp3_profile_before.txt); indexed source profile: [search_comp3_final_profile_after.txt](D:/SDC/LibraryLLM/reports/search_comp3_final_profile_after.txt). Repeated full vocabulary scans and duplicate edit-distance enumeration dominated avoidable work; the indexed version preserves candidate eligibility and exact complete plan hashes for150/150 matched queries.

Same exposed C5E-R150 workload: serial p50 20.79 → 20.52 ms; p95 147.73 → 65.92; max 364.78 → 188.82. Four-worker p95 413.07 → 204.19; max 1231.73 → 1056.87. Each revision300 calls (150 serial+150 concurrent), errors0/300, deterministic150/150. Final CPU 8015.62ms, RSS 36302848 → 37109760 bytes.

Single shared host and fixed order limit inference. The initial comparison used an earlier semantic revision and failed a complete-plan-hash assertion; it is preserved and not used as an optimization claim. Corrected matched measurement restores preoptimization scans into otherwise identical final code. No agreed SLO exists; no operational PASS. Full-search, Mongo and real-vector latency N/A. [search_comp3_final_performance.json](D:/SDC/LibraryLLM/reports/search_comp3_final_performance.json).
