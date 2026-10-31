# profiling

Matched exposed C5ER150 workload,300 calls per architecture: final serial p50 22.53ms, p95 54.39ms; four-worker p95 239.02ms, max 518.27ms. Errors0/300; serial/concurrent plan hashes150/150 equal. Architecture output hashes need not equal V3. Profile: [search_proof4_recorded_profile_after.txt](D:/SDC/LibraryLLM/reports/search_proof4_recorded_profile_after.txt). No safety check was removed to improve timings; no further optimization without confirmed bottleneck. Shared host/order limits inference; no agreed SLO.
