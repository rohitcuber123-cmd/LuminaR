# Search Query Understanding V1

The backend owns a typed, deterministic QueryPlan in `search/query_plan.py`. All four modes share this parser, canonical predicates, presentation interpretation, strict filtering and sorting. Clients send raw query, mode and validated normal filters, never authoritative plans. Explicit controls override parsed bounds. Chip removal uses a named omission list while retaining the original raw input.

Normalization uses NFKC, case, punctuation and whitespace. Canonical subject values remain intact. A small taxonomy-dependent alias layer precedes conservative fuzzy matching. Ambiguous standalone words (science, education, research, law, computers, networks, war, love, women, men, general) remain semantic with a subject suggestion. Explicit subject mode resolves only the selected library's canonical vocabulary.

No Qwen call, embedding model, vector index or graph dependency was added. Semantic topic execution reuses the accepted global/tenant HNSW and CrossEncoder. Pure facets and identifiers bypass vector retrieval. Operational inventory keeps its separate exact lookup.

Global structured lookup uses existing Mongo and lexical author/title sidecars, at most 1,000 candidate documents and a 6-second Mongo limit. Final global ranking preserves the accepted 50-result pagination envelope. Tenant metadata hydration is bounded at 1,000 records, reauthorizes before index access and again before hydration, and checks source fingerprints. Results are strictly checked before reranking. Sorts apply within the retrieved candidate universe; these are not exhaustive global-corpus sorts or corpus counts.

This phase adds no result cache. The existing artifact cache remains scoped by library, generation and target. Frontend result/facet state keys include session, library and staff authority; obsolete responses are aborted or hidden. Protected tenant HTTP reads use private, no-store.
