# Search convergence

Header and catalogue search resolve explicit URL context. Global Search retains the accepted HNSW semantic candidate/rank pipeline: pool 50, page 10, continuation offsets and existing availability semantics. Category/author constrain the hydrated accepted pool before slicing; rank cache/model/algorithm remain unchanged. The availability checkbox is explicitly labelled legacy catalogue availability.

Local Search remains tenant-safe lexical search of the chosen library, using shared CatalogueSurface/BookCard. Empty local results offer Search all LuminaR explicitly; no mixed results, tenant HNSW or KG. Global category browsing applies database filters before paging and uses bounded honest counts.

Frozen Search/rank continuation tests, global server-filter tests and local isolation tests pass. Runtime Search loads 5M vectors but reports STALE, baseline_verified=false, pending=false; no rebuild or manifest rewrite performed. An unauthenticated live Search probe returned 401, so authenticated runtime Search is NOT_VERIFIED. See full_product_search_runtime.json. Browser/visual flows remain pending.
