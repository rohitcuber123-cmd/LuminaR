# V2C-C data inventory

External dataset records downloaded:0. External relevance labels reused:0. External data ingested into production:0.

Independent authoring/review is performed by one separately delegated AI agent, with no access to parser implementation, parser outputs, or existing label corpora. Human review:0. AI self-review by that independent author is distinguished from a second independent reviewer. Parent agent builds seeded/adversarial derivatives from sealed labels with explicit provenance; these are not independently authored queries or real-world accuracy samples.

Existing136 AI-reviewed V2C-A labels and1000 deterministic assertions are regression-only, not newly authored V2C-C rows. Their original provenance remains unchanged.

Fresh fixtures: reports/search_v2c_c_fixture.json. Authorized live scope projections: reports/search_v2c_c_scope_vocabularies.json. Global4096 projected facets are bounded, not the full five-million-book vocabulary; public768; private7. Tenant vocabularies are never replaced with Global facets. Fixture metadata is synthetic; original libraries/books remain unchanged.

Final exact corpus counts, family/split membership and hashes are recorded in search_v2c_c_holdout_manifest.json. No dataset is uploaded to an external service.
