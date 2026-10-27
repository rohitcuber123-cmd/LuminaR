# Recommendation and Knowledge Graph relationship

**For You KG role: NOT_USED.** Neither `recommendation_service` nor `RankedRecommendationPages` traverses a graph or loads KG artifacts. Subject/author counters are catalogue/profile text signals, not graph signals. Tenant `/catalogue/recommendations` joins global preferred work IDs to usable local records and recent acquisitions; it does not load Search or KG artifacts.

Actual recommendations remain valid in the disposable libraries with KG NOT_BUILT; isolated tests make the artifact loader raise if invoked, while Search/KG states are FAILED. There is no tenant graph or document/member graph dependency. No KG enhancement was forced into the accepted recommender.

**More Like This is a different feature.** `useMoreLikeThis` calls `/api/kg/books/{work_id}/more-like-this`. Core `knowledge_graph.product_more_like_this` invokes `CatalogueGraph.more_like_this`, uses deterministic shared metadata relationships, refreshes canonical global records, rejects stale metadata and excludes active global issues/reservations. It is global discovery even when reached from a linked tenant title; it is not the tenant-owned For You rail. Runtime browser response: **HTTP 200**, AVAILABLE, graph version `kg1-2-metadata-cosine-v1`. No claim that this graph powers For You.

Assistant **Recommend Similar** separately calls `/recommendations/from-book`, reusing the existing hybrid recommender with an explicit global book metadata seed. Graph Lab comparison deliberately calls that recommender to compare two independent providers; this is not a graph signal inside normal recommendations.
