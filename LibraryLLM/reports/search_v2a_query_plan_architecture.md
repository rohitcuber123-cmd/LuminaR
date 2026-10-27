# Canonical V2A plan

QueryPlan now includes raw_query, normalized_query, mode, intent, parser_version, semantic_text, exact/title/author text, strict subjects, expanded_subjects, include_terms, exclude_terms, exclude_subjects, rating/year bounds with explicit exclusivity, formats, availability, language, sort, confidence, corrections, soft_preference, kg_expansion_used and kg_generation. include_terms is reserved and currently empty; V2A does not invent inclusion grammar. The backend constructs and validates the plan. Clients submit raw text, modes, typed controls and named chip omissions only.

Flow: normalize → deterministic parse/intent → optional same-scope KG projection → primary HNSW plus at most one secondary retrieval → canonical strict predicates → bounded existing CrossEncoder → canonical validation/hydration → presentation. Pure exact/facet requests bypass unnecessary HNSW/KG. No Qwen, new model/index, personalization or conversational state was added.

There is no new result cache. Plan.cache_key includes scope, parser version, intent, mode, constraints/exclusions, sort, KG generation and supplied HNSW generation. Existing artifact caches remain scoped by library/generation/target. Each request reauthorizes and checks freshness. Existing recommendation MACHINE calls keep the accepted cached ranking path and bypass human parsing.
