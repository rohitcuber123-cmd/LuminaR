# V2C-C resume dataset inventory

External downloads0; external query records copied0; external relevance labels reused0; benchmark data ingested into production Mongo0.

Original540 authored rows are unchanged. Independent agent reviewed them without parser/evaluator/runtime outputs and added72 core rows.612 AI_REVIEWED,6500 UNREVIEWED generated derivatives,0 human-reviewed. Original files retain historical annotations; review overlay and expanded corpus record new review separately.

7112 rows,6528 unique query texts,72 families. Parent families retain split; no original heldout moved into development. Review cautions and exposure appear in design/summary. Generated variants are not independently authored or individually reviewed. Existing136 V2C-A gold and1000 seeded regressions are not counted as new C benchmark rows.

Frozen canonical vocabularies remain scope-specific. Archived synthetic legacy private snapshot is used offline only. Fresh private fixture was used for live security/timing and then archived. Private ready semantic Search was unavailable; local catalogue fallback was measured. Broad regressions and final browser checks were not run after mandatory stop.


Closure audit:raw files contain7112 rows with unique IDs, but mode-alias normalization revealed7 duplicate query contexts. Effective counts are7105 unique cases (4087 development/1611 calibration/1407 heldout),611 distinct AI-reviewed core cases and6494 distinct unreviewed derivatives. Annotated stored counts remain612/6500; human review0. Unique paraphrase/noise categories are1996/998, short of2000/1000. The dataset therefore fails category/dedup quality gates in addition to parsing gates. See search_v2c_c_resume_duplicate_audit.json. Corpus and first-evaluation data were not regenerated or rescored after discovery; the raw3742-row development metrics include the7 duplicates and are provisional, not unique-case accuracy. A future benchmark version must normalize mode aliases before generation. Active Search continues appending its existing C1 stdout journal; archived historical snapshots and structured C1/B1 evidence remain preserved.
