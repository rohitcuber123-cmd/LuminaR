# Operational staging prerequisites

Staging readiness is BLOCKED. Current authorization prohibits even disposable Mongo writes. Real JWT/API/membership, choice issuance and CAS/one-use/expiry durability, structural completion and >150 choice queries, actual vector relevance/health, concurrent end-to-end load and agreed SLOs remain required. No current resident health check ran; the last recorded health is STALE/degraded with baseline_verified=False.

Concrete future disposable staging plan: [search_comp3_staging_proposal.md](D:/SDC/LibraryLLM/reports/search_comp3_staging_proposal.md). It includes exact namespace safety, startup index writes, fixture role matrix, paired index generation, cleanup and rollback. No fake staging or ranking metric is provided.
