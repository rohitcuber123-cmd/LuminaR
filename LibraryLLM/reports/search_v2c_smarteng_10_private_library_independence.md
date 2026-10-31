# Private/global dependency audit and future catalog reduction
Read-only native-function fixtures include own local unlinked books under public/private patron/staff contexts with global fixture EMPTY and INACCESSIBLE. Local results and exact/author/subject/negative constraints continue working; foreign-library rows are excluded; zero global collection reads occur for unlinked local books. This establishes no five-million-record precondition for that tested path. Full Mongo/API/current-membership qualification remains unavailable.

Source dependencies:
- `backend/services/library_catalogue_experience.py`: `usable`, `source_locked`, `hydrate` and `read_context`. Local rows live in library_books, keyed by library_id/library_book_id. Linked global_work_id optionally supplies ratings, description, cover seed and book capabilities; unavailable global reads can still affect linked metadata.
- `backend/services/library_intelligence_store.py`: `source_records`, `fingerprint`, `directory`. Tenant datasets/search/kg generations use library UUID namespaces. Optional global enrichment affects content fingerprints and stale/fallback behavior after a catalog change.
- `backend/services/library_intelligence_artifacts.py`: `VectorCache`, `ArtifactCache`. Tenant embedding cache is per library and content/model version, separate from global work cache. No embedding/index/KG build was performed.
- `search/query_execution.py`: tenant search starts with native authorization and local source; it does not search the global candidate universe on an empty tenant result. Personalization can still depend on global work metadata.
- `recommendation/recommendation_service.py:get_recommendations` and local catalogue recommendations use global candidates/metadata plus local intersection/discovery. Global reduction changes recommendation quality/universe and linked references; unchanged storage does not prove unchanged recommendations.
- `rag/services/library_asset_pipeline.py`: authorized asset_id/library_id/generation namespaces keep local uploaded-document artifacts separate. Linked global-book QA/assets remain dependencies; no RAG behavior was changed or end-to-end requalified.

Future migration PLAN ONLY (no execution authorized):
1. Obtain separate read/export/staging-write authorization and a consistent rollback snapshot of global records, metadata sidecars, model/index/KG manifests and referencing collections.
2. Inventory all work_id/global_work_id references in library_books, loans/issues/reservations/reading lists/book assets/recommendation signals. Protect institution-owned rows/assets; do not prune by global count.
3. Select the curated5000–20000 global universe and retain referenced records or design an independently reviewed archival/reference strategy. Snapshot required linked metadata; preserve stable IDs/aliases.
4. In a disposable authorized staging database, exercise linked/unlinked institution books with global-empty/missing and curated metadata, disabled/stale tenant indices, local assets, role/privacy and borrowing boundaries.
5. Under separate index-build authorization only, construct matching GLOBAL lexical/vector/KG artifacts and manifests for the curated generation. Do not simply delete Mongo books while leaving old global index IDs/counts.
6. Detect tenant source-fingerprint changes and use existing stale/fallback safeguards. Any tenant re-enrichment/rebuild needs explicit authorization and must preserve scope namespaces.
7. Requalify global/private/public search, recommendations/More Like This and global/local RAG independently. Compare relevance and latency using real judgments/providers.
8. Cut over a versioned generation with a reversible pointer/data snapshot plan. Roll back the paired metadata/index generation together. No migration step was performed in this phase.

Feasibility is CONDITIONAL, not an approval or proof that arbitrary global deletion is safe.
