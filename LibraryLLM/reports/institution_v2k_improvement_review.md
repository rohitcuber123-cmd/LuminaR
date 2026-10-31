# Improvement review

Evidence now separates native lease renewal, recent worker self-report, accepted durable progress observation and publication acknowledgement. Real Mongo roles restrict the auxiliary writer and preserve the independent read-only operator boundary. Singleton bounds prevent telemetry event/history growth; old-instance CAS prevents stale identity replacement. Native failures remain native failures.

Measured costs include one indexed auxiliary document, two extra singleton reads per supplement plus at most8 bounded job/pointer joins, six candidate idle writes/minute, coalesced active observations and500ms deadlines. performance.json gives equivalent indexed history scenarios and resource_overhead.json gives actual native idle/build pairs. Small single-pair runtime differences are noisy and establish no production speedup or SLO.

The principal weakness is sampled observation: native transitions can be missed and observation age is not exact commit age. A safe per-instance observer interface should receive trusted acknowledged transition data without blocking native work, support coalescing/backpressure and join-aware lifecycle, and undergo native race/failure qualification. Deployment secret ownership remains separate from operator authentication. No OS verification or CPU/RAM/GPU assignment should be marketed before a real supervisor identity is proven.
