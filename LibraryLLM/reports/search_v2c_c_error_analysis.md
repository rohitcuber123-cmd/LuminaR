# Development safety stop

First evaluation:3742 development parser rows;352 native rows not evaluated through parser. False filters566/3742 (15.1256%); unsafe118/867 blocked cases (13.6101%); contradiction recall96/154 (62.3377%); protected837/873 (95.8763%); comparators344/442 (77.8281%). Mandatory thresholds fail. No tuning/relabeling followed.

AI-reviewed authored examples include fiction by George Orwell producing additional title_text=fiction, and by Terry Pratchett about witches treating the topical phrase as part of author. Negative subject composition adds exclude_terms beyond authored excluded-subject labels. Extra exclusions may enforce a broader meaning; representation/taxonomy differences require independent diagnosis, not a claim that every atom is a confirmed production defect.

Supported conflicts rating at least4.5 but below4.5 and rating no more than1 and no less than4 returned AMBIGUOUS instead of CONTRADICTORY. Execution is still blocked, but strict typed contradiction recall fails. Two authored rating-domain assumptions were preflagged; a separate diagnostic excludes them using the same existing observations and still fails100%. Raw labels/scores remain unchanged.

Safe guarded/semantic misses are separate from unsafe strict execution. Seeded framing is unreviewed and not independent evidence. Exact match also penalizes semantic/intent/soft-preference differences. Known label cautions, split overlap and incomplete native coverage prevent real-world accuracy claims.

Security preflight remains PASS with no observed workspace corruption, revocation regression or private disclosure. Parser benchmark failure does not imply C1 regressed. V2C-C PARTIAL; calibration, native benchmark, heldout, optional model and final Chromium checks stopped.


Closure audit:raw files contain7112 rows with unique IDs, but mode-alias normalization revealed7 duplicate query contexts. Effective counts are7105 unique cases (4087 development/1611 calibration/1407 heldout),611 distinct AI-reviewed core cases and6494 distinct unreviewed derivatives. Annotated stored counts remain612/6500; human review0. Unique paraphrase/noise categories are1996/998, short of2000/1000. The dataset therefore fails category/dedup quality gates in addition to parsing gates. See search_v2c_c_resume_duplicate_audit.json. Corpus and first-evaluation data were not regenerated or rescored after discovery; the raw3742-row development metrics include the7 duplicates and are provisional, not unique-case accuracy. A future benchmark version must normalize mode aliases before generation. Active Search continues appending its existing C1 stdout journal; archived historical snapshots and structured C1/B1 evidence remain preserved.
