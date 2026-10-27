# Tenant HNSW profile

384 normalized dimensions; M=16; efConstruction=80; efSearch=64; candidate count=120; reranking count=60. This bounded profile is separate from global tuning and avoids copying the 5M-scale workload. Batch encoding is 32 rows. No automatic tuning or incremental HNSW mutation is implemented.

The real 150-book TEST and disposable 1,000-book benchmark passed on the resident encoder/reranker. See `institution_v2g_benchmark.json` for actual build/query times and serialized sizes. The 50k record/64 MiB dataset cap and 256 MiB retained-cache budget fail safely; a 100k workload was not built and must not be inferred as benchmarked.
