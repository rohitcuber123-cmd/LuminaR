# KG V2 metadata audit

Fresh full Mongo scan: 5,000,000 books in 265.15s. Raw source evidence: kg_v2_metadata_audit_raw.json. This is a full scan, not a sample. No structured relation is invented from title or description text.

| Field | Non-null | Coverage | Unique normalized values | Degree median / p90 / p99 / max |
|---|---:|---:|---:|---|
| series | 0 | 0.00000% | 0 | None / None / None / None |
| series_name | 0 | 0.00000% | 0 | None / None / None / None |
| publisher | 0 | 0.00000% | 0 | None / None / None / None |
| publishers | 0 | 0.00000% | 0 | None / None / None / None |
| language | 0 | 0.00000% | 0 | None / None / None / None |
| languages | 0 | 0.00000% | 0 | None / None / None / None |
| first_publish_date | 0 | 0.00000% | 0 | None / None / None / None |
| first_publish_year | 0 | 0.00000% | 0 | None / None / None / None |
| publication_year | 0 | 0.00000% | 0 | None / None / None / None |
| publication_date | 0 | 0.00000% | 0 | None / None / None / None |
| publish_date | 0 | 0.00000% | 0 | None / None / None / None |
| genre | 0 | 0.00000% | 0 | None / None / None / None |
| genres | 0 | 0.00000% | 0 | None / None / None / None |
| format | 0 | 0.00000% | 0 | None / None / None / None |
| type | 0 | 0.00000% | 0 | None / None / None / None |
| edition_of | 0 | 0.00000% | 0 | None / None / None / None |
| editions | 0 | 0.00000% | 0 | None / None / None / None |
| isbn | 0 | 0.00000% | 0 | None / None / None / None |
| isbn_10 | 0 | 0.00000% | 0 | None / None / None / None |
| isbn_13 | 0 | 0.00000% | 0 | None / None / None / None |
| classifications | 0 | 0.00000% | 0 | None / None / None / None |
| dewey_decimal_class | 0 | 0.00000% | 0 | None / None / None / None |
| lc_classifications | 0 | 0.00000% | 0 | None / None / None / None |
| description | 1,732,337 | 34.64674% | 1,660,088 | 1 / 1 / 2 / 4573 |
| shelf_location | 1 | 0.00002% | 1 | 1 / 1 / 1 / 1 |
| created_at | 10,001 | 0.20002% | 2 | 1 / 10000 / 10000 / 10000 |

Absent fields have no meaningful degree distribution: null is not a measured zero-degree population. Existing graph authors and subjects remain the only production relations. Series could be strong, publisher moderate/weak and language/era weak if audited structured evidence existed; none exists here. Genre remains represented by source subjects, not a guessed new field. Shelf location remains display only. created_at is an import timestamp.

Descriptions: 1,732,337 present (34.64674%); 1,291,480 have at least 20 tokens (25.8296% of all books). Token lengths median49 / p90195 / p99386 / maximum58,401. There are 440,857 short descriptions, 6 exact boilerplate values, 27,826 markup-containing descriptions, 33,857 duplicate groups involving 106,106 books and 72,249 excess duplicates. Normalized description degree median1 / p901 / p992 / maximum4,573. Non-English rate is unknown; missing language fields do not justify a numerical estimate. Representative source excerpts and field value types are in the JSON.

The existing deterministic pilot strips markup, caps scanning at 512 tokens, accepts descriptions with at least20 tokens, and extracts adjacent Unicode2–3-word phrases with NFKC/casefold/whitespace normalization. English/generic stop words, corpus degree3–0.1%, TF-IDF ordering, lexical ties, no nested phrases, and at most5 topics per book bound noise and degree. Refined pilot also requires membership in the full V1 subject vocabulary. Original phrase and description hash remain provenance. This global policy does not select per-seed phrases or fit the frozen evaluation seeds.

Topics remain pilot only: incidental medical-doctor mentions and non-semantic French “qui est” survived even the subject-vocabulary filter. Weak fields cannot qualify a pair alone; no weak edges exist. No Qwen, embedding model, downloaded dataset, cloud service or new model was used. No full5M V2 promotion is justified.
