# Knowledge Graph relationship to catalogue Search

Classification: **E — USED_ONLY_FOR_GRAPH_LAB / KNOWLEDGE_EXPLORATION**. Ordinary global and tenant Search: **NOT_USED_BY_SEARCH**.

`search/luminar_search.py`, `search/ranked_pages.py` and `TenantIntelligence.semantic` do not load/traverse graph artifacts. Tenant semantic reads request only `SEARCH_INDEX`; graph reads separately request `KNOWLEDGE_GRAPH` in `backend/services/library_intelligence_service.py:graph`. `LibraryGraphPage` calls `/api/libraries/{id}/intelligence/graph`. Search and graph have independent generation pointers and jobs; this agrees with the accepted Part 2G completion, sections R/U. UI links to Graph Lab are navigation, not query expansion.

The actual TEST Graph Lab browser response contains graph nodes and edges from generation `957f604b-b484-4abf-86f0-307a4c85a084`. The disposable library's HNSW query succeeded with KG NOT_BUILT. Isolated tests additionally cover KG FAILED and a graph-cache loader that raises if Search tries to use it.

## Bounded augmentation review

Evaluated deterministic two-hop subject/author/classification neighbors from the first five real HNSW candidates, bounded to 20 additional canonical eligible IDs in TEST. All four independently selected relevant books already occur within the existing 60-candidate rerank pool. Candidate recall gain: **0/4**. See `search_kg_candidate_evaluation.json` for actual additions. The exploratory Mobility paraphrase also already has the relevant book as vector rank 1 and rerank rank 44; adding graph candidates would not repair its existing CrossEncoder score.

**KG_SEARCH_INTEGRATION_IMPLEMENTED: NO.** These observations do not justify changing the accepted ranking. Current graph contains metadata relationships, not a curated synonym/query-understanding ontology. Shared generic subjects can add less specific neighbors and cost more reranking; there is no measured relevance improvement here. This small coverage review is not a general search-quality benchmark.

HNSW remains primary discovery retrieval. Exact operational identifiers/filters remain deterministic. KG remains scoped relationship exploration. Graph unavailability never blocks Search. No document chunks, member records, foreign tenant graph, or global graph entered this evaluation.
