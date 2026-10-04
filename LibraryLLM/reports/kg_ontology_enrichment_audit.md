# KG3.1 full catalogue ontology audit

Read-only streaming scan of all **5,000,000** Mongo catalogue books, bounded batches and disk-backed degree aggregation. Duration **227.52 s**. Every candidate field and alias was checked; absent fields have no degree distribution (`None` means not applicable, not a measured zero). The JSON records per-field normalization difficulty, semantic usefulness and quality issues. Raw measurements are preserved in `kg31_ontology_audit_raw.json`.

| Field / alias | Non-null books | Coverage | Unique normalized values | Degree median / p90 / p99 / max | Decision |
|---|---:|---:|---:|---|---|
| series | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| series_name | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| publisher | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| publishers | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| language | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| languages | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| first_publish_date | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| first_publish_year | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| publication_year | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| publication_date | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| publish_date | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| genre | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| genres | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| format | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| type | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| edition_of | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| editions | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| isbn | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| isbn_10 | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| isbn_13 | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| classifications | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| dewey_decimal_class | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| lc_classifications | 0 | 0% | 0 | None / None / None / None | REJECT: structured source absent; do not infer from titles or descriptions |
| description | 1,732,337 | 34.6467% | 1,660,088 | 1 / 1 / 2 / 4573 | PILOT ONLY; both topic policies fail qualitative usefulness gate. No production topic edges. |
| shelf_location | 1 | 2e-05% | 1 | 1 / 1 / 1 / 1 | REJECT graph feature; retain authoritative display |
| created_at | 10,001 | 0.20002% | 2 | 1 / 10000 / 10000 / 10000 | REJECT |

Series, publisher, language and publication era were evaluated first and rejected because their structured sources do not exist. Genre, format, edition, ISBN and classification aliases are likewise absent. No series is inferred from a title. Ingestion timestamps are not publication dates. Shelf, copies, circulation, ratings and popularity do not form semantic graph edges.

Description is populated for **1,732,337 books (34.64674%)**; **1,291,480 (25.8296%)** contain at least 20 tokens. Among populated descriptions, token lengths median/p90/p99 are **49 / 195 / 386**, maximum **58,401**. There are **440,857** short descriptions, **6** exact boilerplate descriptions, **27,826** with markup, **1,660,088** normalized unique descriptions, **33,857** duplicate groups involving **106,106** books (**72,249** duplicate excess). Complete-description degrees are **1 / 1 / 2 / 4,573**. Empty-whitespace count is zero among populated strings; remaining **3,267,663** books have no populated description. Language coverage is zero; the non-English rate is **unknown**, not estimated. Examples visibly include several languages.

Descriptions qualified for a bounded deterministic pilot, not automatic production acceptance. Both unrestricted phrases and the stricter existing-subject-vocabulary policy fail usefulness review. Stop at the pilot as allowed by Phase 32. Product queries continue using the original V1 graph.
