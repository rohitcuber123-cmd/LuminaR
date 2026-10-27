# Twenty-point review — recommendations only

1. Move durable jobs to a dedicated worker only with an explicit later deployment design.
2. Add bounded per-library scheduling fairness before multi-worker throughput.
3. Measure memory/latency at 10k/50k; 1k results do not prove larger capacities.
4. Benchmark recall before changing M or ef parameters.
5. Define combined Search/KG cache budget for production capacity planning.
6. Instrument resident cache bytes, loads and evictions without exposing them to Patrons.
7. Keep immutable reference handoff during eviction; native allocators can retain RSS.
8. Add explicit maintenance retention for orphan/temp generations after review.
9. Bound total tenant disk usage/embedding cache growth with an operator-approved retention policy.
10. Add a source fingerprint index if dataset history lookup becomes material.
11. Batch freshness observation safely before very large tenant deployments.
12. Preserve final canonical hydration when optimizing freshness checks.
13. Add semantic retrieval quality fixtures with actual domain query relevance judgments.
14. Keep public-work enrichment allowlisted and versioned.
15. Add model revision migration policy before switching encoders/rerankers.
16. Offer concise human-readable status explanations when the next UI phase is approved.
17. Add recoverable job history/status UI only for active authorized Staff.
18. Preserve native form accessibility and measure visual regressions after future shared control changes.
19. Keep read-only tenant graph distinct from private document graph products.
20. Schedule heavy regression processes separately from live global model services on this host.

None of these recommendations introduces automatic rebuilding, incremental mutation, distributed workers, tenant ranking experiments, Qwen/router changes or a later domain phase in Part 2G.
