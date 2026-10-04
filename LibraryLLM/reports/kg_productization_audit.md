# KG productization audit — current implementation before edits

The requested product feature and V2 pilot work are already implemented. Preserve and validate them; do not restart KG1/KG2/KG3, Search depth, or Know More. Prior evidence: kg31_final.json, kg_product_more_like_this.md, kg_ontology_enrichment.md, kg31_integrity_preservation.json. Production V1; both V2 pilots failed useful-reason review and were not promoted.

| Surface / layer | Exact files | Existing behavior |
|---|---|---|
| Book Detail | frontend/src/pages/BookDetailPage.tsx | Borrow / Reading List / More Like This in flex-wrap action row; canonical workId, inline results below metadata |
| Loader | frontend/src/hooks/useMoreLikeThis.ts | GET by work_id, abort stale requests, loading/auth/stale/error/hide states |
| Inline section / cards | frontend/src/components/MoreLikeThisSection.tsx; RelatedBookCard.tsx; BookCover.tsx; BookSelectButton.tsx | native themed reusable related card, deterministic WhyRelated + existing Show Connection, View/Select, live availability/rating/shelf; no scores in normal UI |
| Small-card action | frontend/src/components/BookDiscoveryMenu.tsx | disclosure link to /book/:work_id?related=1#more-like-this |
| Catalogue cards | frontend/src/pages/CatalogPage.tsx (CatalogBookCard) | existing discovery menu |
| Search / ForYou | frontend/src/pages/SearchPage.tsx; frontend/src/components/ForYou.tsx | existing menu; keep paging/ranking frozen |
| Reading List | frontend/src/pages/ReadingListPage.tsx | existing menu |
| Assistant cards | frontend/src/components/assistant/AssistantTurn.tsx | existing menu and graph-specific action |
| Graph Lab | frontend/src/pages/KnowledgeGraphPage.tsx (inline SVG graph; no separate graph component); frontend/src/lib/knowledgeGraph.ts | /experimental/kg?seed=<work_id>; retained experimental graph/explanation/evaluation interface |
| Product API | backend/routes/knowledge_graph.py product_router | authenticated GET /kg/books/{work_id}/more-like-this?limit=10; no recommender/Search/Qwen |
| Experimental API | same router | /experimental/kg books/meta/more-like-this/compare; only explicit compare calls existing recommender |
| Core hydration | search/catalogue.py current_books; backend/services/availability_service.py get_availability_context | current active Mongo metadata and physical inventory precedence, not graph availability |
| KG repository/query | knowledge_graph/core.py CatalogueGraph | SQLite mode=ro, query_only; two-hop weighted cosine, score DESC/internal book_id tie (stable artifact order); candidates excluded/freshness-checked by API |
| Schema/build | scripts/build_catalogue_graph.py; scripts/build_kg_topics.py | books/features/edges/norms/meta, separate staged+atomic V2; source provenance and description hashes |
| Relations/topics | knowledge_graph/relations.py; knowledge_graph/topics.py | author2/subject1/topic0.5; bounded deterministic phrases, pilot only; absent weak fields not imported |
| Assistant KG routing | assistant/kg_routing.py; assistant/tools.py; assistant/orchestrator.py | dedicated MORE_LIKE_THIS, no SHOW_MORE edits required |

Product response: seed_work_id, seed, graph_version, candidate_count, recommendations, limit, has_more=false, snapshot_at. Cards: work_id/title/authors/subjects/book_id/rating/count/shelf/current copies/availability_source/score/reason_paths. Reason paths: nodes=[seed,typed SHA256 entity,candidate], kind,label,predicates,catalogue_degree,contribution,provenance (work_id,source field,value; topics also description SHA256/extractor). Missing trace fields: explicit relation multiplier and importance; these can be added without score changes. Existing exact assistant phrases omit user-specified “show related books” and “what books are connected to this?”; add only those graph fast routes.

Primary UX already meets layout/location/inline/action separation. Empty text currently says “book” instead of requested “title”; Graph Lab link currently says “Explore connections in Graph Lab” instead of requested “Explore full graph”. These small wording changes preserve navigation and behavior. Existing product high-degree audit previously used six live cases; add explicit same-author/high-degree cases to current validation.

Before application edits, source hashes saved in kg_productization_baseline.json. A fresh full 5M Mongo metadata audit will write kg_v2_metadata_audit.json using the existing streaming audit logic to separate new measurements from preserved KG31 evidence. No new field/edge is accepted before that audit; neither existing failed V2 pilot is promoted.
