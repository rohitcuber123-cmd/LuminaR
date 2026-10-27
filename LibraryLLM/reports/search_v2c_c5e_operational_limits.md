# C5E operational boundary and C5F prerequisites

The last recorded global catalogue metadata count is 5,000,000 books. The last known resident global search health is **STALE/degraded; baseline_verified=False**. C5E does not repoll the protected resident endpoint. Stable index hashes do not establish runtime health.

C5E parser timing uses explicit exposed probes across the five recorded capability profiles. Its independent acceptance capture also records one parser-only latency per logical context. Neither is full search latency. Separate native fixture timings include real native session/authorization, disposable Mongo lookup and serialization, a bounded in-memory SQLite lexical fixture, and unchanged tenant NOT_BUILT fallback. The fixture engine supplies fixed global semantic IDs; it is not a measured production HNSW/reranker service. HNSW/KG are not built or rebuilt. No live catalogue, inventory or account commit is authorized by these tests.

A separately authorized C5F health check would need to:

1. Verify the exact candidate, scorer, reviewed population and C5E freeze hashes; preserve any failed acceptance cases. Confirm the candidate remains disabled and that C4 routing/policy has not changed.
2. Authorize an explicit read-only resident health/metadata check with a bounded timeout, identifying the target process and data generation, recorded count, index/catalogue generations, readiness fields, and reasons for stale/degraded or unverified baseline. A responsive HTTP endpoint alone is insufficient.
3. Authorize a bounded read-only search smoke set for the global and public/private scopes under existing authorized patron/staff identities. Include SMART/EXACT, strict filters, empty results, pagination and denial behavior. Avoid inventory, model or document mutations. Use no real private query text in public evidence.
4. Measure full request latency separately from parser latency and report actual retrieval/lexical/index/model providers, fallback status, errors and resource usage. Do not substitute parser timings or synthetic fixture timings for production service measurements.
5. Require fresh independent validation for any revision made after this C5E acceptance capture. Do not reuse its exposed queries as new acceptance or change their labels to pass. Any observed critical execution error blocks readiness until a source-backed repair and genuinely independent validation qualify a new frozen revision.

C5E itself neither starts C5F nor authorizes production activation, Part 2I, Qwen/RAG/recommendation changes, catalogue regeneration or live inventory commits.
