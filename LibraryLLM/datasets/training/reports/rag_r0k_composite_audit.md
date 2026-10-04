# R0K — Current composite reranker on fixed G3 Dense60

**FINAL R0K DECISION: B. RAW CROSS-ENCODER IS BETTER THAN CURRENT COMPOSITE.**

Raw CE wins the frozen primary ordering priority: Hit20 is62.07% versus58.62%; Hit10 ties at51.72%; MRR is0.3578 versus0.3300. Composite improves Hit5 (41.38%→48.28%) but adds no Top20 query recovery and demotes time_05 out of Top20. Membership and candidate coverage remain identical. This conclusion is descriptive on29 DRAFT DEV queries; no production change follows automatically.

Experimental/descriptive engineering audit on frozen DRAFT DEV labels. No production changes, expansion, candidate search, weight tuning, training, downloads or TEST evaluation.

## Frozen controls and fingerprints

Freeze verification: `{'verified_file_count': 418, 'historical_files_changed': 0, 'cross_encoder_cache_changes': 0, 'production_files_changed': 0}`. G1/G2/G3/R0/R0I/R0J, tokens_220, evaluation labels, source map and model/cache files unchanged; all 64 production snapshot files unchanged. Full before-SHA ledger in rag_r0k_preflight.json.

G3: `D:\SDC\LibraryLLM\datasets\training\models\minilm_g3_gooaq_50k_full`, weights SHA-256 `93e147de5e7a18998bff9a6cd9478ff6322553288403482bf6514792a0c940cd`; normalized384-dimensional embeddings, window256, unchanged per-book IndexFlatIP indexes.

CE: `cross-encoder/ms-marco-MiniLM-L-6-v2`, snapshot `233902d25c440f23af6f7d6e94d2946bac0bee0a`, weights SHA-256 `821d1aa69520101d6e0737f78a042ae25b19e5cb9160701909d10434f4aeb0ae`. Exact local R0/R0I/R0J checkpoint, float32, max512, batch16. Actual6-layer architecture; legacy config name says L-12. Loaded default activation and explicit experimental activation are both Identity; no softmax or sigmoid.

Environment: `{'python_executable': 'D:\\SDC\\LibraryLLM\\.venv\\Scripts\\python.exe', 'GPU': 'NVIDIA GeForce RTX 5060 Laptop GPU', 'total_VRAM_bytes': 8546484224, 'free_VRAM_bytes': 7385120768, 'RAM_total_bytes': 16438054912, 'RAM_available_bytes': 3435778048, 'CUDA': '12.8', 'torch': '2.11.0+cu128', 'other_GPU_usage': '16372, C:\\Program Files\\Python311\\python.exe, [N/A]'}`. CE package fingerprints and versions: `{'source_sha256': {'D:\\SDC\\LibraryLLM\\.venv\\Lib\\site-packages\\sentence_transformers\\base\\model.py': '8537ce4c45dd79436030dbbc62a81763700592ce8176e1dfec4b9a53cfe2743e', 'D:\\SDC\\LibraryLLM\\.venv\\Lib\\site-packages\\torch\\utils\\_contextlib.py': 'c4b52075af6b23784336b88d1c608c1ba22bcece245f03d20e8ff12b8bb774c9'}, 'versions': {'sentence-transformers': '5.6.0', 'transformers': '5.15.1', 'torch': '2.11.0+cu128'}, 'CE_scoring_adapter_source_sha256': {'D:\\SDC\\LibraryLLM\\scripts\\r0i_common.py': '0d4ff6d4b634446dbd73b999215a7bf09942ac49febc62fb289589bfee23cec2'}, 'unwrapped_predict_implementation_finalization_sha256': {'D:\\SDC\\LibraryLLM\\.venv\\Lib\\site-packages\\sentence_transformers\\cross_encoder\\model.py': 'cbed9620536de1e5eea677bd54e768b0138e7eeb2b755c26e07f9462dc07cd9a'}, 'additional_source_hash_provenance': 'Unwrapped CrossEncoder.predict source identified with inspect.unwrap and hashed at final artifact verification; supplementary to the preflight project/forward/decorator hashes.'}`.

## Exact current production formula

```python
CROSSENCODER_WEIGHT * item['normalized_rerank_score'] + EVIDENCE_WEIGHT * item['evidence_score'] + FAISS_WEIGHT * item['faiss_norm']
```

Weights read from current rag/evidence.py: CE=0.3, evidence=0.55, dense=0.15. Formula fingerprint SHA-256: `dcdbb3736acd1d41a05cec28d3429a1b378f326aaa8f671242b27db4a13174fd`; executed scoring AST SHA-256: `a22efecab506ec7bf5dcb5149003cdfabbd2d8af723cbdc5e33654ab61ddf81b`.

Executed unchanged post-CE statements from rag/reranker.py lines311–432; no production candidate-generation code, model construction or final Top5 truncation is invoked. All60 candidates remain available for ordering/evaluation.

| Participating project source | SHA-256 |
|---|---|
| D:\SDC\LibraryLLM\rag\reranker.py | e10dbe24ef1ce5f9083241d39b44246317db62ba5859f9321b6f220fe1079ced |
| D:\SDC\LibraryLLM\rag\evidence.py | c10f36c75fb414b9ce17b183f29ff78cc193d88bc379173040b473f939e261ca |
| D:\SDC\LibraryLLM\rag\retriever.py | 4fa6208b8fad104d2926f6ca9ac9da8fe6966ec59ceee5b1b169a9fe72dd2281 |

CE scoring uses the frozen R0I adapter and exact loaded CE. Preflight hashes cover the adapter, inherited forward source and predict decorator; the unwrapped CrossEncoder predict implementation is additionally fingerprinted during final artifact verification, with that provenance recorded explicitly. Checkpoint tokenizer/config files retain their R0 hashes in JSON.

## Normalization, evidence context and ties

Normalization: `{'CE': 'per-query pool min-max (score-min)/(max-min)', 'dense': 'same per-query min-max; input score key, fallback faiss_score, fallback0', 'empty': '[]', 'zero_range': '0.5 for every candidate if span ==0 exactly', 'normalization_clipping': 'none; finite actual inputs are in[0,1] after min-max', 'evidence': 'calculate_evidence_score directly; internally clamped max(0,min(1,score)), no pool normalization', 'final_score_clipping': 'none'}`.

Composite tie rule: Python stable candidates.sort(key=final_score, reverse=True); exact ties retain incoming dense order. Raw CE uses descending raw logits with chunk-ID ascending for exact ties. The candidate prefix starts in original dense order.

Evidence context: `{'retrieval_queries': '[original question] only; no generator or expanded retrieval called', 'intent_data': None, 'intent_note': 'Unchanged RAGReranker.search default; equivalent to historical audit intent_data={}; no external semantic intent model invoked.', 'metadata': 'Exact frozen tokens_220 corpus metadata, with score=G3 inner product and dense input rank', 'all_chunks_dict': 'All16895 exact frozen tokens_220 texts keyed by unchanged canonical chunk_id', 'concept_matching': 'Existing evidence-internal concept matching remains; no separate lexical retrieval/score added.', 'default_evidence_formula': 'clamp(0.20*term_overlap +0.20*phrase_overlap +0.10*concept_density +0.30*alignment_score +0.15*multi_q_coverage +0.05*speaker_score)', 'default_branch_note': 'intent_data=None leaves semantic_intent=None, so existing final evidence combination takes fallback even when regex intent is causal/temporal. multi_q_coverage=0 for a single retrieval query. No branch repaired.', 'metadata_index_note': 'Existing neighbor/temporal helpers parse numeric chunk-ID suffixes; frozen tokens_220 hash IDs are not remapped to numeric IDs.'}`. The actual imported calculate_evidence_score and normalize_scores_minmax functions execute unchanged. Their complete source and the executed production statement block are preserved in JSON.

This audit uses the existing search default intent_data=None, equivalent to earlier retrieval audits using{}. It does not invoke QA-level semantic intent extraction. Evidence-internal concept, phrase, actor/event and speaker heuristics remain as written; no separate lexical retrieval or lexical score is introduced. No query expansion strings are generated; retrieval_queries contains the original question only.

## Reproduction and fixed membership

Reproduction: `{'all_DEV_queries': 30, 'evaluable_DEV_queries': 29, 'exact_Top50_prefix_all_DEV': True, 'exact_R0J_Top60_evaluable': True, 'raw_CE_R0J_all_metrics_and_ranks_exact': True, 'raw_CE_R0J_maximum_score_absolute_difference': 0.0, 'CE_default_activation_is_Identity': True}`. All30 DEV queries reproduce the frozen Top50 prefix; all29 evaluable Dense60 pools reproduce R0J exactly. The30th DEV query has no grade2 accepted passage and is reproduced without scoring. Raw CE matches every R0J Dense60 metric, rank, and score (maximum absolute score difference0).

A/B/C contain exactly the same 60 chunk IDs per evaluable query: 1740 query/chunk pairs. Raw CE logits are scored once and reused exactly by composite. All accepted-overlap flags are added after scoring; gold spans never enter the production scoring function. Candidate Hit, Candidate Recall and no-gold are invariant.

## Metrics

| Metric | Dense60 | Raw CE | Current Composite |
|---|---:|---:|---:|
| MRR | 0.1367 | 0.3578 | 0.3300 |
| Hit@1 | 3.45% | 27.59% | 24.14% |
| Hit@3 | 17.24% | 37.93% | 34.48% |
| Hit@5 | 20.69% | 41.38% | 48.28% |
| Hit@10 | 37.93% | 51.72% | 51.72% |
| Hit@20 | 44.83% | 62.07% | 58.62% |
| Recall@5 | 20.69% | 41.38% | 48.28% |
| Recall@10 | 37.93% | 50.00% | 50.00% |
| Recall@20 | 44.83% | 58.62% | 56.90% |
| Candidate Hit | 75.86% | 75.86% | 75.86% |
| Candidate Recall | 70.69% | 70.69% | 70.69% |
| No-gold candidate count | 7 | 7 | 7 |

Frozen decision priority: Compare current-composite versus raw-ce lexicographically by Hit20, Hit10, Hit5, MRR. Exact equality is neutral; descriptive DRAFT DEV results, no weight optimization. Raw CE has higher Hit20; Hit10 ties; composite improves Hit5 but loses MRR and Hit1/3. This is an aggregate descriptive conclusion, not a claim that every query benefits from raw CE.

## Every-query accepted-rank movement

Raw CE→Composite counts: `{'UNCHANGED': 16, 'IMPROVED': 4, 'REGRESSED': 9}`. UNCHANGED includes the7 queries with no accepted candidate, whose ranks remain absent.

| Query | Dense first accepted | Raw CE first accepted | Composite first accepted | Delta | Classification |
|---|---:|---:|---:|---:|---|
| v8_01 | None | None | None | None | UNCHANGED |
| v8_02 | 4 | 6 | 3 | -3 | IMPROVED |
| v8_03 | 9 | 3 | 4 | 1 | REGRESSED |
| v8_04 | None | None | None | None | UNCHANGED |
| v8_06 | 47 | 1 | 1 | 0 | UNCHANGED |
| v8_07 | None | None | None | None | UNCHANGED |
| v8_08 | 44 | 27 | 38 | 11 | REGRESSED |
| v8_09 | 53 | 19 | 15 | -4 | IMPROVED |
| v8_10 | 27 | 6 | 8 | 2 | REGRESSED |
| pp_01 | 7 | 1 | 1 | 0 | UNCHANGED |
| pp_02 | 29 | 33 | 32 | -1 | IMPROVED |
| pp_03 | 7 | 7 | 5 | -2 | IMPROVED |
| pp_04 | None | None | None | None | UNCHANGED |
| pp_05 | 49 | 12 | 18 | 6 | REGRESSED |
| alice_01 | 7 | 1 | 1 | 0 | UNCHANGED |
| alice_02 | 17 | 2 | 5 | 3 | REGRESSED |
| alice_03 | 3 | 2 | 2 | 0 | UNCHANGED |
| alice_04 | 2 | 1 | 1 | 0 | UNCHANGED |
| alice_05 | 1 | 1 | 1 | 0 | UNCHANGED |
| time_01 | 34 | 53 | 53 | 0 | UNCHANGED |
| time_02 | 31 | 41 | 42 | 1 | REGRESSED |
| time_03 | None | None | None | None | UNCHANGED |
| time_04 | 7 | 1 | 2 | 1 | REGRESSED |
| time_05 | 16 | 14 | 25 | 11 | REGRESSED |
| war_01 | None | None | None | None | UNCHANGED |
| war_02 | 3 | 1 | 1 | 0 | UNCHANGED |
| war_03 | None | None | None | None | UNCHANGED |
| war_04 | 2 | 1 | 1 | 0 | UNCHANGED |
| war_05 | 37 | 4 | 5 | 1 | REGRESSED |

## Threshold recoveries and demotions

| Threshold | Recovered queries | Demoted queries |
|---|---|---|
| Top1 | [] | ['time_04'] |
| Top3 | ['v8_02'] | ['v8_03', 'alice_02'] |
| Top5 | ['v8_02', 'pp_03'] | [] |
| Top10 | [] | [] |
| Top20 | [] | ['time_05'] |

## Critical queries and component breakdown

Target is the earliest original dense candidate overlapping an accepted span; query-first accepted ranks are listed separately because a different accepted candidate can lead after reranking.

| Query | Target dense rank | Target raw CE rank | Target composite rank | Query raw first | Query composite first |
|---|---:|---:|---:|---:|---:|---:|
| v8_06 | 47 | 1 | 1 | 1 | 1 |
| pp_05 | 49 | 12 | 18 | 12 | 18 |
| v8_08 | 44 | 27 | 38 | 27 | 38 |
| v8_09 | 53 | 19 | 15 | 19 | 15 |
| v8_10 | 27 | 23 | 8 | 6 | 8 |
| pp_02 | 29 | 33 | 32 | 33 | 32 |
| time_01 | 34 | 53 | 53 | 53 | 53 |
| time_03 | 74 | None | None | None | None |
| time_05 | 16 | 14 | 25 | 14 | 25 |
| war_05 | 37 | 4 | 5 | 4 | 5 |

| Query | Raw CE score | Evidence score | Dense norm | CE weighted | Evidence weighted | Dense weighted | Final composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| v8_06 | 3.743077040 | 0.410000000 | 0.071677071 | 0.300000000 | 0.225500000 | 0.010751561 | 0.536251561 |
| pp_05 | -0.372051477 | 0.266666667 | 0.100846051 | 0.170794946 | 0.146666667 | 0.015126908 | 0.332588520 |
| v8_08 | -8.432656288 | 0.425000000 | 0.070921361 | 0.062146393 | 0.233750000 | 0.010638204 | 0.306534597 |
| v8_09 | -8.290019989 | 0.400000000 | 0.047757416 | 0.091758505 | 0.220000000 | 0.007163612 | 0.318922118 |
| v8_10 | -7.952352524 | 0.417500000 | 0.222611471 | 0.069156302 | 0.229625000 | 0.033391721 | 0.332173023 |
| pp_02 | -0.043057289 | 0.340000000 | 0.118362764 | 0.135366885 | 0.187000000 | 0.017754415 | 0.340121300 |
| time_01 | -10.992580414 | 0.425000000 | 0.265257093 | 0.010353236 | 0.233750000 | 0.039788564 | 0.283891800 |
| time_03 | None | None | None | None | None | None | None |
| time_05 | -7.076780319 | 0.128571429 | 0.342427739 | 0.133556094 | 0.070714286 | 0.051364161 | 0.255634540 |
| war_05 | 0.159573108 | 0.325000000 | 0.167845294 | 0.223723434 | 0.178750000 | 0.025176794 | 0.427650228 |

v8_06 hard check: accepted target dense47, raw CE1, composite1. Its CE/evidence/dense weighted contributions are0.300000000/0.225500000/0.010751561. The strong raw-CE recovery remains at rank1; no demotion attribution is needed.

## Known CE-domain failures

| Query | Raw CE first accepted | Composite first accepted | Movement |
|---|---:|---:|---|
| v8_08 | 27 | 38 | REGRESSED |
| pp_02 | 33 | 32 | IMPROVED |
| time_01 | 53 | 53 | UNCHANGED |

These cases have admitted accepted evidence and therefore reflect ordering failures, distinct from absent-candidate failures such as time_03. Improvements in individual cases do not establish general heuristic superiority.

## Label-coverage limitations

Known engineering-only POSSIBLE_LABEL_COVERAGE_LIMITATION passages receive no automatic gold credit. Frozen DRAFT labels remain unchanged.

| Query | Chunk | Raw CE rank | Composite rank | Evidence |
|---|---|---:|---:|---:|
| pp_05 | OL66524W__tokens_220__d4ff028b2f8aa974 | 2 | 5 | 0.266666667 |
| time_05 | OL27039837W__tokens_220__2928e5046c948f13 | 4 | 7 | 0.128571429 |

Full answer-evidence text and all components are in JSON. These are2 unique passages/queries, observed under raw CE and composite; they are excluded from accepted-span metrics.

## Effective component contributions

| Component | Mean absolute weighted term | Median | p10 | p90 | Dominance frequency |
|---|---:|---:|---:|---:|---:|
| CE | 0.094955881 | 0.078291097 | 0.004594822 | 0.214521952 | 27.28% |
| evidence | 0.144169264 | 0.137500000 | 0.000000000 | 0.302500000 | 60.56% |
| dense | 0.038893244 | 0.028776353 | 0.003434146 | 0.089933446 | 12.16% |

Dominance method/counts: `{'denominator_candidate_pairs': 1740, 'exact_tie_count': 2, 'component_unique_winner_count': {'CE': 474, 'evidence': 1053, 'dense': 211}, 'component_including_ties_count': {'CE': 476, 'evidence': 1055, 'dense': 213}, 'component_fractional_dominance_frequency': {'CE': 0.2727969348659004, 'evidence': 0.6055555555555555, 'dense': 0.12164750957854407}, 'note': 'Numerically largest absolute weighted term per candidate. Large offsets do not necessarily determine pairwise ordering; margins in harm/benefit cases provide that attribution.'}`. No weight changes or alternative formulas were evaluated.

## Ordering disagreement

Global distribution: `{'candidate_pairs': 1740, 'mean_absolute_rank_change': 5.964367816091954, 'median_absolute_rank_change': 4.0, 'rank_changes': {'5': {'count': 823, 'fraction': 0.4729885057471264}, '10': {'count': 371, 'fraction': 0.2132183908045977}, '20': {'count': 68, 'fraction': 0.03908045977011494}}, 'pairwise_order_inversions': 7062, 'pairwise_comparison_count': 51330}`.

| Query | Spearman correlation | Changed ≥5 | Changed ≥10 | Changed ≥20 | Pairwise inversion fraction | First accepted delta |
|---|---:|---:|---:|---:|---:|---:|
| v8_01 | 0.894137 | 33/60 (55.00%) | 12/60 (20.00%) | 3/60 (5.00%) | 13.79% | None |
| v8_02 | 0.953209 | 16/60 (26.67%) | 4/60 (6.67%) | 1/60 (1.67%) | 8.53% | -3 |
| v8_03 | 0.869241 | 32/60 (53.33%) | 17/60 (28.33%) | 2/60 (3.33%) | 15.31% | 1 |
| v8_04 | 0.903862 | 31/60 (51.67%) | 10/60 (16.67%) | 1/60 (1.67%) | 13.50% | None |
| v8_06 | 0.868463 | 30/60 (50.00%) | 15/60 (25.00%) | 2/60 (3.33%) | 15.25% | 0 |
| v8_07 | 0.886913 | 33/60 (55.00%) | 18/60 (30.00%) | 1/60 (1.67%) | 14.63% | None |
| v8_08 | 0.929147 | 29/60 (48.33%) | 11/60 (18.33%) | 0/60 (0.00%) | 11.47% | 11 |
| v8_09 | 0.891970 | 27/60 (45.00%) | 11/60 (18.33%) | 5/60 (8.33%) | 13.73% | -4 |
| v8_10 | 0.829619 | 33/60 (55.00%) | 20/60 (33.33%) | 3/60 (5.00%) | 17.63% | 2 |
| pp_01 | 0.790720 | 41/60 (68.33%) | 18/60 (30.00%) | 8/60 (13.33%) | 19.94% | 0 |
| pp_02 | 0.956766 | 19/60 (31.67%) | 4/60 (6.67%) | 0/60 (0.00%) | 8.19% | -1 |
| pp_03 | 0.878133 | 32/60 (53.33%) | 16/60 (26.67%) | 1/60 (1.67%) | 14.63% | -2 |
| pp_04 | 0.922367 | 22/60 (36.67%) | 12/60 (20.00%) | 0/60 (0.00%) | 11.19% | None |
| pp_05 | 0.931092 | 26/60 (43.33%) | 6/60 (10.00%) | 1/60 (1.67%) | 10.79% | 6 |
| alice_01 | 0.956543 | 19/60 (31.67%) | 4/60 (6.67%) | 0/60 (0.00%) | 8.81% | 0 |
| alice_02 | 0.850736 | 29/60 (48.33%) | 16/60 (26.67%) | 4/60 (6.67%) | 16.61% | 3 |
| alice_03 | 0.836844 | 26/60 (43.33%) | 16/60 (26.67%) | 7/60 (11.67%) | 15.42% | 0 |
| alice_04 | 0.755599 | 35/60 (58.33%) | 19/60 (31.67%) | 6/60 (10.00%) | 20.51% | 0 |
| alice_05 | 0.952820 | 17/60 (28.33%) | 7/60 (11.67%) | 0/60 (0.00%) | 8.59% | 0 |
| time_01 | 0.944762 | 16/60 (26.67%) | 7/60 (11.67%) | 0/60 (0.00%) | 9.55% | 0 |
| time_02 | 0.944651 | 27/60 (45.00%) | 6/60 (10.00%) | 0/60 (0.00%) | 10.06% | 1 |
| time_03 | 0.948764 | 21/60 (35.00%) | 6/60 (10.00%) | 0/60 (0.00%) | 9.38% | None |
| time_04 | 0.927591 | 25/60 (41.67%) | 11/60 (18.33%) | 0/60 (0.00%) | 11.47% | 1 |
| time_05 | 0.891470 | 31/60 (51.67%) | 13/60 (21.67%) | 1/60 (1.67%) | 14.69% | 11 |
| war_01 | 0.908197 | 31/60 (51.67%) | 15/60 (25.00%) | 0/60 (0.00%) | 12.54% | None |
| war_02 | 0.787830 | 43/60 (71.67%) | 19/60 (31.67%) | 4/60 (6.67%) | 19.72% | 0 |
| war_03 | 0.905863 | 19/60 (31.67%) | 10/60 (16.67%) | 3/60 (5.00%) | 11.86% | None |
| war_04 | 0.661684 | 42/60 (70.00%) | 31/60 (51.67%) | 13/60 (21.67%) | 24.24% | 0 |
| war_05 | 0.850458 | 38/60 (63.33%) | 17/60 (28.33%) | 2/60 (3.33%) | 16.95% | 1 |

## Harm cases: first accepted rank worsens by at least5

All candidates crossing the target in opposite directions between raw CE and composite are recorded with exact text and component scores in JSON and rag_r0k_composite_harm_cases.json. Pairwise attribution uses the signs of actual weighted term margins; it is diagnostic, with no tuned weights or scored ablations.

- **v8_08 / MULTI_COMPONENT_DISTRACTOR**: first accepted rank27→38; 11 crossing candidates. Target `OL85892W__tokens_220__b0608a6d61982aa3`.
  - `OL85892W__tokens_220__8a7c805c2295c0be`: CE=-9.060168266, evidence=0.475000000, dense=0.453361869; weighted CE/evidence/dense=0.048028607/0.261250000/0.040239307, final=0.349517915; MULTI_COMPONENT_DISTRACTOR.
  - `OL85892W__tokens_220__4b94a7e5ac03df6d`: CE=-8.837579727, evidence=0.475000000, dense=0.443071038; weighted CE/evidence/dense=0.053036412/0.261250000/0.035199964, final=0.349486376; MULTI_COMPONENT_DISTRACTOR.
  - `OL85892W__tokens_220__a58040ca89718203`: CE=-8.501379013, evidence=0.475000000, dense=0.414726198; weighted CE/evidence/dense=0.060600267/0.261250000/0.021319709, final=0.343169975; MULTI_COMPONENT_DISTRACTOR.
- **pp_05 / MULTI_COMPONENT_DISTRACTOR**: first accepted rank12→18; 6 crossing candidates. Target `OL66524W__tokens_220__a636a19f5f30a36b`.
  - `OL66524W__tokens_220__afe3a410b9e8065c`: CE=-0.432785749, evidence=0.266666667, dense=0.674200058; weighted CE/evidence/dense=0.169459968/0.146666667/0.107187725, final=0.423314360; DENSE_SCORE_DISTRACTOR.
  - `OL66524W__tokens_220__1bd008b71b8ab8be`: CE=-0.737912178, evidence=0.375000000, dense=0.593201518; weighted CE/evidence/dense=0.162753097/0.206250000/0.045187916, final=0.414191013; MULTI_COMPONENT_DISTRACTOR.
  - `OL66524W__tokens_220__aff0bbbc3682de15`: CE=-0.553276002, evidence=0.316666667, dense=0.611139774; weighted CE/evidence/dense=0.166811517/0.174166667/0.058918638, final=0.399896822; MULTI_COMPONENT_DISTRACTOR.
- **time_05 / MULTI_COMPONENT_DISTRACTOR**: first accepted rank14→25; 11 crossing candidates. Target `OL27039837W__tokens_220__f1a3b6c23f488f74`.
  - `OL27039837W__tokens_220__9122c96ef699acfc`: CE=-7.651810169, evidence=0.307142857, dense=0.415210366; weighted CE/evidence/dense=0.115265196/0.168928571/0.083366972, final=0.367560740; MULTI_COMPONENT_DISTRACTOR.
  - `OL27039837W__tokens_220__bfa137dac0997c7d`: CE=-8.630975723, evidence=0.335714286, dense=0.387822926; weighted CE/evidence/dense=0.084119306/0.184642857/0.065182711, final=0.333944874; MULTI_COMPONENT_DISTRACTOR.
  - `OL27039837W__tokens_220__9dda2cf59f68f2e3`: CE=-10.287841797, evidence=0.332142857, dense=0.465635121; weighted CE/evidence/dense=0.031416707/0.182678571/0.116847170, final=0.330942448; MULTI_COMPONENT_DISTRACTOR.

## Benefit cases: first accepted rank improves by at least5

All candidates crossing the target in opposite directions between raw CE and composite are recorded with exact text and component scores in JSON and rag_r0k_composite_harm_cases.json. Pairwise attribution uses the signs of actual weighted term margins; it is diagnostic, with no tuned weights or scored ablations.

None.

Harm classifications: `{'MULTI_COMPONENT_DISTRACTOR': 3}`. Benefit classifications: `{}`.

## Actual latency, GPU and RAM

| Stage | Seconds per29-query batch | ms/query |
|---|---:|---:|
| Dense retrieval | 0.399122 | 13.763 |
| Raw CE scoring | 3.122593 | 107.676 |
| Raw CE sorting | 0.003133 | 0.108 |
| Evidence scoring | 3.913918 | 134.963 |
| Composite normalization/sort and audit wrapper, excluding evidence | 0.117192 | 4.041 |
| Dense60 + raw CE pipeline | 3.524848 | 121.546 |
| Dense60 + composite pipeline | 7.552825 | 260.442 |

Composite extra latency: 138.896ms/query. Evidence was measured, not assumed cheap. Actual measured shared retrieval and CE stages; add measured raw sorting or composite stage respectively. No separate CE rerun or extrapolated cost. The composite stage includes source verification and defensive candidate copies; non-evidence time is therefore normalization/sort plus audit overhead, not an isolated pure-formula microbenchmark. Initial30-query reproduction and16 CE warmup pairs are excluded from pipeline times. This is one actual shared-machine pass; timings contain runtime noise.

CE batch size16; actual scored unique pairs1740 (1740 logical per scored system, reused exactly between B/C). Peak allocated VRAM=245.68MiB; peak reserved=342.00MiB; minimum global free=6.515GiB; peak process RSS=1.756GiB. Both frozen models were resident. No unrelated workload was terminated.

## Integrity, artifacts and stop

Tests: `{'result': '22 passed', 'path': 'D:\\SDC\\LibraryLLM\\datasets\\training\\reports\\rag_r0k_contract_tests.log', 'sha256': 'd7b6e31cb0b7dc9c080f91a000e26f538a88c79c611c7c8b9d9236365d8b18ec'}`. Final saved-artifact verification: `{'all_metrics_recomputed_from_saved_scores': True, 'Dense60_and_raw_CE_exact_R0J_reproduction': True, 'all_system_candidate_memberships_identical': True, 'candidate_Hit_Recall_no_gold_invariant': True, 'normalization_and_weighted_terms_exact': True, 'production_stable_composite_sort_exact': True, 'formula_and_CE_source_hashes_unchanged': True, 'all_candidate_passages_match_frozen_corpus': True, 'all_encoded_queries_DEV_only': True, 'gold_overlap_added_only_after_scoring': True, 'experimental_code_matches_preflight': True}`.

Component parquet: 1740 rows; SHA-256 `d36346c1e914731c182159bc9eb0fb7fb280d05d6efb281eade081b2d5b26171`. Every system metric was reconstructed from saved ranks. Normalization, weighted terms, stable composite ties, source hashes and all memberships were verified without model inference.

**TEST evaluated: NO. Production changed: NO. Labels changed: NO. Historical artifacts changed: NO.**

Artifacts created:

- `scripts\r0k_common.py`
- `scripts\evaluate_rag_r0k_composite_audit.py`
- `scripts\report_rag_r0k_composite_audit.py`
- `tests\test_rag_r0k_composite_audit.py`
- `datasets\training\reports\rag_r0k_preflight.json`
- `datasets\training\reports\rag_r0k_composite_audit.json`
- `datasets\training\reports\rag_r0k_composite_audit.md`
- `datasets\training\evaluation\rag_r0k_composite_scores.parquet`
- `datasets\training\reports\rag_r0k_composite_harm_cases.json`
- `datasets\training\reports\rag_r0k_contract_tests.log`
- `datasets\training\reports\rag_r0k_evaluation.log`

**FINAL R0K DECISION: B. RAW CROSS-ENCODER IS BETTER THAN CURRENT COMPOSITE.**

Stopped after R0K. No production integration, weight tuning, CE fine-tuning or additional candidate-policy experiment was started.