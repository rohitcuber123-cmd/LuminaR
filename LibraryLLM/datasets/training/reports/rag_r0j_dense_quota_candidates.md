# R0J — Dense-quota-preserving candidate construction

**FINAL R0J DECISION: G. R0J MIXED / INCONCLUSIVE.**

The coverage-first winner adds accepted candidate coverage but no new Top20 query and has worse CE Hit20 than dense60. The experiment does not establish that its extra retrieval/CE cost is justified.

Experimental engineering result on frozen DRAFT DEV labels. No production change, training, downloads, composite scoring, or TEST evaluation.

## Frozen controls and models

Before/after verification: `{'verified_file_count': 405, 'historical_files_changed': 0, 'cross_encoder_cache_changes': 0, 'production_files_changed': 0}`. G1/G2/G3/R0/R0I, tokens_220, source map, labels, models, and all64 production files remain unchanged. Full SHA ledger: `rag_r0j_preflight.json`.

G3: `D:\SDC\LibraryLLM\datasets\training\models\minilm_g3_gooaq_50k_full`, SHA-256 `93e147de5e7a18998bff9a6cd9478ff6322553288403482bf6514792a0c940cd`; normalized384-dimensional embeddings, window256, unchanged per-book IndexFlatIP indexes.

CE: `cross-encoder/ms-marco-MiniLM-L-6-v2`, revision `233902d25c440f23af6f7d6e94d2946bac0bee0a`, weights SHA-256 `821d1aa69520101d6e0737f78a042ae25b19e5cb9160701909d10434f4aeb0ae`. Exact R0/R0I local cache; actual6layers/384hidden, float32, max512, batch16, explicit Identity raw logits. Legacy config name says L-12; actual weights/cache/architecture are the frozen L-6. Inputs are the original DEV question and exact tokens_220 passage. Sort descending raw logit, chunk-ID ascending for ties.

Python: `D:\SDC\LibraryLLM\.venv\Scripts\python.exe`. GPU: NVIDIA GeForce RTX 5060 Laptop GPU. Other GPU usage observed before loading: `29364, C:\Program Files\Python311\python.exe, [N/A]`. No unrelated process was terminated.

Reproduction: `{'all_DEV_queries': 30, 'evaluable': 29, 'exact_Top50_ID_match': True, 'protected_TEST_encoded': False, 'exact_R0I_Top80_ID_match': True, 'Top80_comparison_queries': 29, 'non_evaluable_DEV_note': 'Frozen R0I has Top80 pools for 29 evaluable queries; all30 reproduce frozen Top50.'}`. All30 DEV queries reproduce frozen Top50; all29 evaluable Top80 pools reproduce R0I exactly. Dense60/Dense80 candidate and CE metrics plus complete CE order reproduce R0I exactly. D80+E20 reproduces R0I union metrics under the unified builder.

## Policies frozen before evaluation

| Policy | Guaranteed original dense quota | Unique expansion supplements | Maximum CE pool |
|---|---:|---:|---:|
| dense60 | 60 | 0 | 60 |
| dense80 | 80 | 0 | 80 |
| d50e30 | 50 | 30 | 80 |
| d60e20 | 60 | 20 | 80 |
| d70e10 | 70 | 10 | 80 |
| d80e20 | 80 | 20 | 100 |

Dense copies always win deduplication by canonical chunk_id. The guaranteed prefix retains original dense order; unique supplements follow unchanged expansion first-seen order. Duplicates consume no supplement quota. All ceilings and prefix preservation are asserted at runtime. No per-query quota choice or extra policies.

Selection policy saved in preflight: Lexicographic priority: candidate macro Recall, candidate Hit, CE Hit20, CE Hit10, fewer no-gold queries, lower measured CE milliseconds/query, MRR. If the coverage winner improves no useful Top20 coverage and worsens Hit20 against dense60, report MIXED / INCONCLUSIVE instead of asserting extra cost is justified. No query-specific policy or added policy. Coverage-first priority winner: `d80e20`.

## Central comparison

| Policy | Candidate Hit | Candidate Recall | No gold | Hit10 | Hit20 | MRR | Mean candidates | Total ms/query |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense60 | 75.86% | 70.69% | 7 | 51.72% | 62.07% | 0.3578 | 60.00 | 111.43 |
| dense80 | 79.31% | 74.14% | 6 | 51.72% | 58.62% | 0.3539 | 80.00 | 149.08 |
| d50e30 | 75.86% | 72.41% | 7 | 51.72% | 58.62% | 0.3581 | 53.21 | 130.37 |
| d60e20 | 79.31% | 74.14% | 6 | 51.72% | 58.62% | 0.3584 | 62.83 | 145.91 |
| d70e10 | 75.86% | 70.69% | 7 | 51.72% | 58.62% | 0.3560 | 71.66 | 171.72 |
| d80e20 | 82.76% | 77.59% | 5 | 51.72% | 58.62% | 0.3543 | 82.48 | 180.86 |

Candidate Hit/Recall refer to the complete actual pool, before CE; Recall is macro average over accepted grade2 spans per query. Reranking changes ordering, never membership. Metrics cover29 evaluable DEV queries; the30th DEV query has no grade2 span and is reproduced but not scored.

## Counts and full reranking metrics

| Policy | Candidate count min / mean / max | Expansion-only unique added, total | Accepted queries |
|---|---:|---:|---:|
| dense60 | 60 / 60.00 / 60 | 0 | 22/29 |
| dense80 | 80 / 80.00 / 80 | 0 | 23/29 |
| d50e30 | 50 / 53.21 / 74 | 93 | 22/29 |
| d60e20 | 60 / 62.83 / 80 | 82 | 23/29 |
| d70e10 | 70 / 71.66 / 80 | 48 | 22/29 |
| d80e20 | 80 / 82.48 / 100 | 72 | 24/29 |

| System | Candidate Hit | Candidate Recall | No gold | MRR | Hit1 | Hit3 | Hit5 | Hit10 | Hit20 | Recall5 | Recall10 | Recall20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dense60 | 75.86% | 70.69% | 7 | 0.3578 | 27.59% | 37.93% | 41.38% | 51.72% | 62.07% | 41.38% | 50.00% | 58.62% |
| dense80 | 79.31% | 74.14% | 6 | 0.3539 | 27.59% | 37.93% | 41.38% | 51.72% | 58.62% | 41.38% | 50.00% | 56.90% |
| d50e30 | 75.86% | 72.41% | 7 | 0.3581 | 27.59% | 37.93% | 41.38% | 51.72% | 58.62% | 41.38% | 50.00% | 58.62% |
| d60e20 | 79.31% | 74.14% | 6 | 0.3584 | 27.59% | 37.93% | 41.38% | 51.72% | 58.62% | 41.38% | 50.00% | 56.90% |
| d70e10 | 75.86% | 70.69% | 7 | 0.3560 | 27.59% | 37.93% | 41.38% | 51.72% | 58.62% | 41.38% | 50.00% | 56.90% |
| d80e20 | 82.76% | 77.59% | 5 | 0.3543 | 27.59% | 37.93% | 41.38% | 51.72% | 58.62% | 41.38% | 50.00% | 56.90% |

Hit@pool and Recall@pool equal Candidate Hit and Candidate Recall above. Exact per-query span ranks, admitted spans, candidate counts and supplement counts are included in JSON.

## Existing expansion reproduction

Source: `{'source_path': 'D:\\SDC\\LibraryLLM\\rag\\reranker.py', 'source_sha256': 'e10dbe24ef1ce5f9083241d39b44246317db62ba5859f9321b6f220fe1079ced', 'evidence_source_sha256': 'c10f36c75fb414b9ce17b183f29ff78cc193d88bc379173040b473f939e261ca', 'per_branch_depth': 15, 'production_literal_cap': 40, 'only_controlled_override': 'MAX_MULTIQ_CANDIDATES = frozen provisional K; no other generation changes', 'merge': 'actual production AST: first-seen chunk dedupe, original query first, no sorting by dense score', 'hash_seed': '42', 'generation_note': 'existing family set iteration is process-hash-seed dependent; freeze seed42 and record all generated strings'}`. The actual pre-CE production AST and unchanged evidence.py generator are reused with Top15 per variant, original query first and first-seen canonical dedup. All generated strings, ordering, matched-query provenance and deduplicated candidate order reproduce R0I exactly with PYTHONHASHSEED=42. The R0I controlled cap80 is retained while uncapped first-seen candidates supply the supplements; observed uncapped maximum40, so no cap binds. Only the combination with original dense quotas changes. Production rag/reranker.py was never edited.

## Measured cost and shared-GPU headroom

| Policy | Dense retrieval s | Expansion retrieval s | CE scoring s | Total batch s | CE ms/query | Total ms/query | Logical / unique / actual pairs |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense60 | 0.311901 | 0.000000 | 2.892632 | 3.231390 | 99.746 | 111.427 | 1740 / 1740 / 1740 |
| dense80 | 0.337957 | 0.000000 | 3.949816 | 4.323461 | 136.201 | 149.085 | 2320 / 2320 / 2320 |
| d50e30 | 0.365337 | 0.793299 | 2.598609 | 3.780613 | 89.607 | 130.366 | 1543 / 1543 / 1543 |
| d60e20 | 0.361505 | 0.775600 | 3.064363 | 4.231448 | 105.668 | 145.912 | 1822 / 1822 / 1822 |
| d70e10 | 0.355603 | 0.816952 | 3.775623 | 4.979746 | 130.194 | 171.715 | 2078 / 2078 / 2078 |
| d80e20 | 0.342858 | 0.767444 | 4.097038 | 5.245025 | 141.277 | 180.863 | 2392 / 2392 / 2392 |

| Policy | Peak allocated MiB | Peak reserved MiB | Minimum global free GiB | Peak process RSS GiB |
|---|---:|---:|---:|---:|
| dense60 | 245.68 | 342.00 | 6.515 | 1.648 |
| dense80 | 245.68 | 342.00 | 6.515 | 1.655 |
| d50e30 | 245.68 | 342.00 | 6.515 | 1.657 |
| d60e20 | 245.68 | 342.00 | 6.515 | 1.661 |
| d70e10 | 245.68 | 342.00 | 6.515 | 1.663 |
| d80e20 | 245.68 | 342.00 | 6.515 | 1.666 |

No CE cache used: 11895 logical pairs were actually scored, 2399 distinct query/chunk pairs across policies, zero cache reuse. Each policy has fresh dense retrieval, expansion retrieval where applicable, and complete CE scoring. The16 warmup pairs and initial30-query reproduction are separate from policy timings. Total runtime includes construction, assertions and metric aggregation; expansion time includes unchanged generation/merge and frozen-order checks. Timings are one measured pass on a shared machine, not statistical latency estimates. All memory peaks include both resident models; minimum free GPU headroom remains above the1.5GiB guard.

## Critical accepted evidence

The target is the earliest original Top80 candidate overlapping an accepted span. Source BOTH means it is retained as a dense copy and also appears in the expansion retrieval; EXPANSION means it lies outside the guaranteed dense quota. Other accepted candidates per query are recorded separately in JSON. Ranks outside original Top80 are not inferred.

| Query | Policy | Target present | Source | Original dense rank | Pre-CE index | Post-CE rank |
|---|---|---|---|---:|---:|---:|
| v8_06 | dense60 | True | DENSE | 47 | 47 | 1 |
| v8_06 | dense80 | True | DENSE | 47 | 47 | 1 |
| v8_06 | d50e30 | True | BOTH | 47 | 47 | 1 |
| v8_06 | d60e20 | True | BOTH | 47 | 47 | 1 |
| v8_06 | d70e10 | True | BOTH | 47 | 47 | 1 |
| v8_06 | d80e20 | True | BOTH | 47 | 47 | 1 |
| pp_05 | dense60 | True | DENSE | 49 | 49 | 12 |
| pp_05 | dense80 | True | DENSE | 49 | 49 | 12 |
| pp_05 | d50e30 | True | DENSE | 49 | 49 | 12 |
| pp_05 | d60e20 | True | DENSE | 49 | 49 | 12 |
| pp_05 | d70e10 | True | DENSE | 49 | 49 | 12 |
| pp_05 | d80e20 | True | DENSE | 49 | 49 | 12 |
| v8_08 | dense60 | True | DENSE | 44 | 44 | 27 |
| v8_08 | dense80 | True | DENSE | 44 | 44 | 29 |
| v8_08 | d50e30 | True | DENSE | 44 | 44 | 27 |
| v8_08 | d60e20 | True | DENSE | 44 | 44 | 27 |
| v8_08 | d70e10 | True | DENSE | 44 | 44 | 29 |
| v8_08 | d80e20 | True | DENSE | 44 | 44 | 29 |
| v8_09 | dense60 | True | DENSE | 53 | 53 | 19 |
| v8_09 | dense80 | True | DENSE | 53 | 53 | 22 |
| v8_09 | d50e30 | False | None | 53 | None | None |
| v8_09 | d60e20 | True | DENSE | 53 | 53 | 22 |
| v8_09 | d70e10 | True | DENSE | 53 | 53 | 21 |
| v8_09 | d80e20 | True | DENSE | 53 | 53 | 25 |
| v8_10 | dense60 | True | DENSE | 27 | 27 | 23 |
| v8_10 | dense80 | True | DENSE | 27 | 27 | 27 |
| v8_10 | d50e30 | True | DENSE | 27 | 27 | 20 |
| v8_10 | d60e20 | True | DENSE | 27 | 27 | 23 |
| v8_10 | d70e10 | True | DENSE | 27 | 27 | 25 |
| v8_10 | d80e20 | True | DENSE | 27 | 27 | 27 |
| pp_02 | dense60 | True | DENSE | 29 | 29 | 33 |
| pp_02 | dense80 | True | DENSE | 29 | 29 | 38 |
| pp_02 | d50e30 | True | DENSE | 29 | 29 | 31 |
| pp_02 | d60e20 | True | DENSE | 29 | 29 | 33 |
| pp_02 | d70e10 | True | DENSE | 29 | 29 | 36 |
| pp_02 | d80e20 | True | DENSE | 29 | 29 | 38 |
| time_01 | dense60 | True | DENSE | 34 | 34 | 53 |
| time_01 | dense80 | True | DENSE | 34 | 34 | 60 |
| time_01 | d50e30 | True | BOTH | 34 | 34 | 48 |
| time_01 | d60e20 | True | BOTH | 34 | 34 | 53 |
| time_01 | d70e10 | True | BOTH | 34 | 34 | 56 |
| time_01 | d80e20 | True | BOTH | 34 | 34 | 60 |
| time_03 | dense60 | False | None | 74 | None | None |
| time_03 | dense80 | True | DENSE | 74 | 74 | 54 |
| time_03 | d50e30 | False | None | 74 | None | None |
| time_03 | d60e20 | False | None | 74 | None | None |
| time_03 | d70e10 | False | None | 74 | None | None |
| time_03 | d80e20 | True | DENSE | 74 | 74 | 54 |
| time_05 | dense60 | True | DENSE | 16 | 16 | 14 |
| time_05 | dense80 | True | DENSE | 16 | 16 | 15 |
| time_05 | d50e30 | True | DENSE | 16 | 16 | 13 |
| time_05 | d60e20 | True | DENSE | 16 | 16 | 14 |
| time_05 | d70e10 | True | DENSE | 16 | 16 | 14 |
| time_05 | d80e20 | True | DENSE | 16 | 16 | 15 |
| war_05 | dense60 | True | DENSE | 37 | 37 | 4 |
| war_05 | dense80 | True | DENSE | 37 | 37 | 5 |
| war_05 | d50e30 | True | DENSE | 37 | 37 | 4 |
| war_05 | d60e20 | True | DENSE | 37 | 37 | 4 |
| war_05 | d70e10 | True | DENSE | 37 | 37 | 4 |
| war_05 | d80e20 | True | DENSE | 37 | 37 | 5 |

v8_06 original rank47 and pp_05 original rank49 are asserted present in every policy. Their exact post-CE ranks are shown above; preserving membership does not imply unchanged CE rank when supplements outrank them.

## D60 + E20 analysis

D60+E20 preserves every original rank1–60 candidate. Candidate Recall changes 70.69%→74.14%; accepted-query coverage 22→23. CE Hit20 changes 62.07%→58.62%, Hit10 51.72%→51.72%. It adds82 unique supplement occurrences across29queries. Measured total latency changes 111.43→145.91ms/query; CE alone 99.75→105.67ms/query.

New covered queries versus Dense60: `['v8_01']`. New accepted-span admissions: `1`. Query Hit20 gains: `[]`; losses: `['v8_09']`.

## Expansion-only accepted evidence

Classification compares each supplement against its guaranteed dense quota. NEW_QUERY_COVERAGE means that quota admitted no accepted span; ADDITIONAL_ACCEPTED_SPAN adds a previously uncovered span; NEITHER adds another candidate for already covered spans. Accepted supplements outside Top20 increase admission without creating a useful Top20 hit.

| Policy | Query | Chunk | Original dense rank | CE rank | Contribution |
|---|---|---|---:|---:|---|
| d50e30 | v8_01 | OL45326637W__tokens_220__40c31a4f7a23b8db | None | 41 | NEW_QUERY_COVERAGE |
| d60e20 | v8_01 | OL45326637W__tokens_220__40c31a4f7a23b8db | None | 45 | NEW_QUERY_COVERAGE |
| d80e20 | v8_01 | OL45326637W__tokens_220__40c31a4f7a23b8db | None | 52 | NEW_QUERY_COVERAGE |

Exact source query variants and span indices for every accepted expansion-only candidate are in JSON.

## Expansion distractor demotions

For attribution, remove only appended supplements from a policy and rerank its guaranteed dense quota with exactly the same saved logits. This isolates membership effects without another scored policy or a changed CE. Report every accepted dense candidate crossing Top5/10/20, and distinguish candidate-level movement from the first accepted passage for the query. A distractor here lacks frozen accepted-span overlap; known unlabelled answer evidence is flagged separately.

Recorded accepted-candidate boundary demotions: 2; EXPANSION_DISTRACTOR_DEMOTION instances: 2.

- **d60e20 / v8_09 / EXPANSION_DISTRACTOR_DEMOTION**: accepted `OL45326637W__tokens_220__4d0447747b4e43f9`, CE score-8.290019989, rank19→22, crosses[20]; query first accepted rank19→22.
  - Appended `OL45326637W__tokens_220__77768aa05cfd785f`, CE score-6.634597301, rank11, variant(s) `['ambition animate animation being blame build compelled conscience construct creating creature curiosity discovery experiment']`, label limitation:False.
  - Appended `OL45326637W__tokens_220__8c70516c3481f2ee`, CE score-7.867939949, rank18, variant(s) `['ambition animate animation being blame build compelled conscience construct creating creature curiosity discovery experiment']`, label limitation:False.
  - Appended `OL45326637W__tokens_220__f2598dc4692cfc77`, CE score-8.038547516, rank19, variant(s) `['What causes or motivates victor regret creating creature remorse conscience guilt form being ambition compelled curiosity discovery', 'ambition animate animation being blame build compelled conscience construct creating creature curiosity discovery experiment']`, label limitation:False.
- **d70e10 / v8_09 / EXPANSION_DISTRACTOR_DEMOTION**: accepted `OL45326637W__tokens_220__4d0447747b4e43f9`, CE score-8.290019989, rank20→21, crosses[20]; query first accepted rank20→21.
  - Appended `OL45326637W__tokens_220__f2598dc4692cfc77`, CE score-8.038547516, rank18, variant(s) `['What causes or motivates victor regret creating creature remorse conscience guilt form being ambition compelled curiosity discovery', 'ambition animate animation being blame build compelled conscience construct creating creature curiosity discovery experiment']`, label limitation:False.

## Known CE-domain failures and label limitations

| Query | Policy | Accepted candidate present | CE first accepted rank | Classification |
|---|---|---|---:|---|
| v8_08 | dense60 | True | 27 | RERANKER_DOMAIN_FAILURE |
| v8_08 | dense80 | True | 29 | RERANKER_DOMAIN_FAILURE |
| v8_08 | d50e30 | True | 27 | RERANKER_DOMAIN_FAILURE |
| v8_08 | d60e20 | True | 27 | RERANKER_DOMAIN_FAILURE |
| v8_08 | d70e10 | True | 29 | RERANKER_DOMAIN_FAILURE |
| v8_08 | d80e20 | True | 29 | RERANKER_DOMAIN_FAILURE |
| pp_02 | dense60 | True | 33 | RERANKER_DOMAIN_FAILURE |
| pp_02 | dense80 | True | 38 | RERANKER_DOMAIN_FAILURE |
| pp_02 | d50e30 | True | 31 | RERANKER_DOMAIN_FAILURE |
| pp_02 | d60e20 | True | 33 | RERANKER_DOMAIN_FAILURE |
| pp_02 | d70e10 | True | 36 | RERANKER_DOMAIN_FAILURE |
| pp_02 | d80e20 | True | 38 | RERANKER_DOMAIN_FAILURE |
| time_01 | dense60 | True | 53 | RERANKER_DOMAIN_FAILURE |
| time_01 | dense80 | True | 60 | RERANKER_DOMAIN_FAILURE |
| time_01 | d50e30 | True | 48 | RERANKER_DOMAIN_FAILURE |
| time_01 | d60e20 | True | 53 | RERANKER_DOMAIN_FAILURE |
| time_01 | d70e10 | True | 56 | RERANKER_DOMAIN_FAILURE |
| time_01 | d80e20 | True | 60 | RERANKER_DOMAIN_FAILURE |

POSSIBLE_LABEL_COVERAGE_LIMITATION: 12 pool/query instances, 2 unique queries. Known pp_05 Wickham/Lydia and time_05 red-sun passages retain R0's engineering flag and receive no gold credit; exact passages and CE ranks are in JSON. Frozen DRAFT labels were not changed.

| Query | Policy | Known unlabelled answer passage CE rank | Source |
|---|---|---:|---|
| pp_05 | dense60 | 2 | DENSE |
| time_05 | dense60 | 4 | DENSE |
| pp_05 | dense80 | 2 | DENSE |
| time_05 | dense80 | 4 | DENSE |
| pp_05 | d50e30 | 2 | BOTH |
| time_05 | d50e30 | 4 | BOTH |
| pp_05 | d60e20 | 2 | BOTH |
| time_05 | d60e20 | 4 | BOTH |
| pp_05 | d70e10 | 2 | BOTH |
| time_05 | d70e10 | 4 | BOTH |
| pp_05 | d80e20 | 2 | BOTH |
| time_05 | d80e20 | 4 | BOTH |

## Verification, artifacts and stop

Tests: `{'result': '22 passed', 'path': 'D:\\SDC\\LibraryLLM\\datasets\\training\\reports\\rag_r0j_contract_tests.log', 'sha256': '4828419532c4a5d610bf63d6719fc83b46d6bf0abb61354bf6eefc4c5fecdba8'}`. Saved-parquet verification: `{'all_metrics_recomputed_from_saved_parquet': True, 'all_dense_quotas_and_ceilings_preserved': True, 'chunk_id_dedup_and_first_seen_supplements': True, 'raw_CE_sort_and_fingerprints_exact': True, 'original_passage_text_unchanged': True, 'R0I_dense60_dense80_and_union_reproduced': True, 'expansion_matches_R0I': True, 'all_encoded_query_ids_DEV_only': True, 'experimental_code_matches_preflight': True}`. Experiment source SHAs match preflight. Policy pools, raw-logit sorting, fingerprints, complete metrics and critical preservation were reconstructed from saved scores without loading models.

Score parquet: 11895 rows, SHA-256 `74dc0db0dac65fb9d2b845370de4bc240da5dc6229fadfc07f9cb014b6bb791a`.

**TEST evaluated: NO. Production changed: NO. Labels changed: NO. Historical artifacts changed: NO.**

Artifacts created:

- `scripts\r0j_common.py`
- `scripts\evaluate_rag_r0j_dense_quota_candidates.py`
- `scripts\report_rag_r0j_dense_quota_candidates.py`
- `tests\test_rag_r0j_dense_quota_candidates.py`
- `datasets\training\reports\rag_r0j_preflight.json`
- `datasets\training\reports\rag_r0j_dense_quota_candidates.json`
- `datasets\training\reports\rag_r0j_dense_quota_candidates.md`
- `datasets\training\evaluation\rag_r0j_candidate_scores.parquet`
- `datasets\training\reports\rag_r0j_expansion_distractors.json`
- `datasets\training\reports\rag_r0j_contract_tests.log`
- `datasets\training\reports\rag_r0j_evaluation.log`

**FINAL R0J DECISION: G. R0J MIXED / INCONCLUSIVE.**

Stopped after R0J. No production implementation, CE fine-tuning or composite-weight experiment was started.