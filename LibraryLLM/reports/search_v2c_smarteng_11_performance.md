# Performance and operations
Exposed C5E-R150 parser-only serial timing: p5020.35ms, p95147.30ms. Four worker timings: p5086.73ms, p95438.60ms;150/150 serial/concurrent plan fingerprints match. CPU10859.38ms for the combined300 calls; RSS32772096→35160064 bytes. Thread results include GIL/scheduling contention.

Fresh single-capture parser timing: p5016.47ms,p95130.00ms,max191.06ms. These are parser calls, not full search. Read-only fixture call timings are separately recorded in native reports and include in-memory dependencies.

Historical C5E10.19/20.63ms and real-native59.48/143.35ms came from different populations/providers/conditions; do not infer a matched speed improvement. Current tail/contended latency requires profiling and a declared staging SLO. Real Mongo, vector lookup, embedding/relevance and live end-to-end latency are N/A. No Qwen/model calls, network or index loads/builds occurred. Last known global health remains STALE/degraded; baseline_verified=False. No resident endpoint repoll.
