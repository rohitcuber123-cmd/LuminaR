# Tenant semantic catalogue

The existing resident Search API injects its accepted all-MiniLM-L6-v2 encoder and ms-marco-MiniLM-L-6-v2 reranker into an independent tenant adapter. There is no second model per library, Qwen edge generation or global index rebuild. A degraded lexical-only Search process does not claim semantic builds.

Tenant HNSW vectors are normalized finite 384-dimensional float32 values with inner-product distance. Vector position maps to immutable canonical metadata and its library_book_id. Up to 120 neighbors produce at most 60 reranked candidates. Final rows are re-authorized and hydrated from current canonical inventory, permitted formats and availability; inactive/foreign/stale rows cannot be trusted from vector metadata alone.

Global `/search` remains global. Explicit library search uses the tenant route only when its current source fingerprint and validated manifest are READY. NOT_BUILT, BUILDING, FAILED, STALE, corruption and model mismatch use the current local lexical catalogue, with explicit source/status. An absent index never adds global filler to a populated usable library. The accepted genuinely empty catalogue discovery fallback is preserved.

Core and Search browser reads share the existing ordered tenant request helper, cancellation, account guard and bounded transient-503 retries. This prevents semantic reads colliding with concurrent canonical catalogue reads. Explicit global pages retain their old API.
