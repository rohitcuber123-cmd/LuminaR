# R0I — G3 candidate pool integration

**FINAL R0I DECISION: D. CURRENT EXPANSION/CAPPING DESTROYS USEFUL G3 CANDIDATES — FIX CANDIDATE CONSTRUCTION BEFORE INTEGRATION.**

Experimental/descriptive; frozen DEV labels remain DRAFT. No training, model/dataset downloads, Qwen, learned score mixing, or production changes. TEST evaluated: NO.

## Controls and fingerprints

Frozen before/after verification: `{'verified_file_count': 390, 'historical_files_changed': 0, 'cross_encoder_cache_changes': 0, 'production_files_changed': 0}`; production 64-file snapshot unchanged. G1/G2/G3/R0 and CE cache unchanged. SHA ledger in `rag_r0i_preflight.json`.

G3 `{'path': 'D:\\SDC\\LibraryLLM\\datasets\\training\\models\\minilm_g3_gooaq_50k_full', 'weights_sha256': '93e147de5e7a18998bff9a6cd9478ff6322553288403482bf6514792a0c940cd', 'max_length': 256, 'dimension': 384}`; existing R0 CE `{'model_id': 'cross-encoder/ms-marco-MiniLM-L-6-v2', 'path': 'C:\\Users\\balak\\.cache\\huggingface\\hub\\models--cross-encoder--ms-marco-MiniLM-L-6-v2\\snapshots\\233902d25c440f23af6f7d6e94d2946bac0bee0a', 'revision': '233902d25c440f23af6f7d6e94d2946bac0bee0a', 'model_weights_sha256': '821d1aa69520101d6e0737f78a042ae25b19e5cb9160701909d10434f4aeb0ae', 'files_sha256': {'config.json': '380e02c93f431831be65d99a4e7e5f67c133985bf2e77d9d4eba46847190bacc', 'model.safetensors': '821d1aa69520101d6e0737f78a042ae25b19e5cb9160701909d10434f4aeb0ae', 'special_tokens_map.json': '3c3507f36dff57bce437223db3b3081d1e2b52ec3e56ee55438193ecb2c94dd6', 'tokenizer.json': 'd241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66', 'tokenizer_config.json': 'a5c2e5a7b1a29a0702cd28c08a399b5ecc110c263009d17f7e3b415f25905fd8', 'vocab.txt': '07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3'}, 'max_sequence_length': 512, 'device': 'cuda:0', 'dtype': 'torch.float32', 'legacy_config_name_or_path': 'cross-encoder/ms-marco-MiniLM-L-12-v2', 'num_hidden_layers': 6, 'loaded_default_activation': 'Identity', 'scoring_activation': 'Identity (raw logits)', 'same_object_for_both_pools': True, 'model_inputs': ['original DEV question', 'exact frozen candidate passage text'], 'default_cache_resolved_weights_path': 'C:\\Users\\balak\\.cache\\huggingface\\hub\\models--cross-encoder--ms-marco-MiniLM-L-6-v2\\snapshots\\233902d25c440f23af6f7d6e94d2946bac0bee0a\\model.safetensors', 'matches_existing_default_local_cache': True}`. Current raw-phase environment `{'python_executable': 'D:\\SDC\\LibraryLLM\\.venv\\Scripts\\python.exe', 'GPU': 'NVIDIA GeForce RTX 5060 Laptop GPU', 'total_VRAM_bytes': 8546484224, 'free_VRAM_bytes': 7385120768, 'RAM_total_bytes': 16438054912, 'RAM_available_bytes': 2968350720, 'CUDA': '12.8', 'torch': '2.11.0+cu128', 'other_GPU_usage': '456, C:\\Program Files\\Python311\\python.exe, [N/A]'}`. G3 window256/dimension384, normalized embeddings; per-book IndexFlatIP; CE512/float32, batch16, explicit Identity logits, score-descending sort with chunk-ID tie break.

G3 reproduction `{'all_DEV_queries': 30, 'evaluable': 29, 'exact_Top50_ID_match': True, 'protected_TEST_encoded': False}`. All 30 DEV Top50 ID lists reproduced exactly; 29 evaluable queries scored. K50 CE ranks/metrics reproduce R0 exactly; max floating-score difference 0. No TEST encoded. Six K values and selection rule saved before evaluation; 16 DEV-only CE warmup pairs, then actual fresh retrieval/scoring for every K without cross-K score reuse.

## Frozen R0 context

| Metric | A dense | A+CE Top50 | G3 dense | G3+CE Top50 |
|---|---:|---:|---:|---:|
| MRR | 0.1653 | 0.3163 | 0.1360 | 0.3572 |
| Hit@5 | 24.14% | 34.48% | 20.69% | 41.38% |
| Hit@10 | 34.48% | 48.28% | 37.93% | 51.72% |
| Hit@20 | 48.28% | 51.72% | 44.83% | 58.62% |
| Hit@50 | 65.52% | 65.52% | 72.41% | 72.41% |
| Recall@50 | 62.07% | 62.07% | 68.97% | 68.97% |

## Raw original-query predefined K sweep

Candidate Hit/Recall use the complete TopK pool. Reranking metrics use CE order inside that same pool. Candidate membership/coverage is invariant through CE; no expansion, evidence, lexical, union or mixed scoring in this phase.

| System | Candidate Hit | Candidate Recall | No gold | MRR | Hit1 | Hit3 | Hit5 | Hit10 | Hit20 | Recall5 | Recall10 | Recall20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| G3 raw K20 | 44.83% | 44.83% | 16 | 0.3107 | 24.14% | 37.93% | 41.38% | 44.83% | 44.83% | 41.38% | 44.83% | 44.83% |
| G3 raw K30 | 51.72% | 50.00% | 14 | 0.3095 | 24.14% | 34.48% | 37.93% | 44.83% | 48.28% | 37.93% | 44.83% | 46.55% |
| G3 raw K40 | 62.07% | 60.34% | 11 | 0.3191 | 24.14% | 34.48% | 37.93% | 48.28% | 51.72% | 37.93% | 46.55% | 51.72% |
| G3 raw K50 | 72.41% | 68.97% | 8 | 0.3572 | 27.59% | 37.93% | 41.38% | 51.72% | 58.62% | 41.38% | 50.00% | 58.62% |
| G3 raw K60 | 75.86% | 70.69% | 7 | 0.3578 | 27.59% | 37.93% | 41.38% | 51.72% | 62.07% | 41.38% | 50.00% | 58.62% |
| G3 raw K80 | 79.31% | 74.14% | 6 | 0.3539 | 27.59% | 37.93% | 41.38% | 51.72% | 58.62% | 41.38% | 50.00% | 56.90% |

## Incremental candidate bands

| Band | Extra covered queries | Extra accepted spans | Recall gain | CE Hit20 change | Latency ms/query change |
|---|---:|---:|---:|---:|---:|
| 20→30 | 2 | 2 | +5.17% | +3.45% | +16.684 |
| 30→40 | 3 | 4 | +10.34% | +3.45% | +19.082 |
| 40→50 | 3 | 3 | +8.62% | +6.90% | +19.894 |
| 50→60 | 1 | 1 | +1.72% | +3.45% | +16.126 |
| 60→80 | 1 | 1 | +3.45% | -3.45% | +37.012 |

Newly covered queries by band:

- 20→30: `v8_10` (Frankenstein), dense accepted rank 27, CE rank after Top30 12.
- 20→30: `pp_02` (Pride and Prejudice), dense accepted rank 29, CE rank after Top30 23.
- 30→40: `time_01` (The Time Machine), dense accepted rank 34, CE rank after Top40 40.
- 30→40: `time_02` (The Time Machine), dense accepted rank 31, CE rank after Top40 33.
- 30→40: `war_05` (The War of the Worlds), dense accepted rank 37, CE rank after Top40 4.
- 40→50: `v8_06` (Dracula), dense accepted rank 47, CE rank after Top50 1.
- 40→50: `v8_08` (Dracula), dense accepted rank 44, CE rank after Top50 27.
- 40→50: `pp_05` (Pride and Prejudice), dense accepted rank 49, CE rank after Top50 12.
- 50→60: `v8_09` (Frankenstein), dense accepted rank 53, CE rank after Top60 19.
- 60→80: `time_03` (The Time Machine), dense accepted rank 74, CE rank after Top80 54.

| Newly admitted span band | Query | Span index | Dense rank | CE rank |
|---|---|---:|---:|---:|
| 20→30 | v8_10 | 1 | 27 | 12 |
| 20→30 | pp_02 | 0 | 29 | 23 |
| 30→40 | v8_10 | 0 | 37 | 6 |
| 30→40 | time_01 | 0 | 34 | 40 |
| 30→40 | time_02 | 0 | 31 | 33 |
| 30→40 | war_05 | 0 | 37 | 4 |
| 40→50 | v8_06 | 0 | 47 | 1 |
| 40→50 | v8_08 | 0 | 44 | 27 |
| 40→50 | pp_05 | 0 | 49 | 12 |
| 50→60 | v8_09 | 0 | 53 | 19 |
| 60→80 | time_03 | 0 | 74 | 54 |

## Critical recovery and domain-failure tracking

| Query | K | Accepted candidate present | Dense accepted rank | CE accepted rank |
|---|---:|---|---:|---:|
| v8_06 | 20 | False | None | None |
| v8_06 | 30 | False | None | None |
| v8_06 | 40 | False | None | None |
| v8_06 | 50 | True | 47 | 1 |
| v8_06 | 60 | True | 47 | 1 |
| v8_06 | 80 | True | 47 | 1 |
| pp_05 | 20 | False | None | None |
| pp_05 | 30 | False | None | None |
| pp_05 | 40 | False | None | None |
| pp_05 | 50 | True | 49 | 12 |
| pp_05 | 60 | True | 49 | 12 |
| pp_05 | 80 | True | 49 | 12 |
| v8_08 | 20 | False | None | None |
| v8_08 | 30 | False | None | None |
| v8_08 | 40 | False | None | None |
| v8_08 | 50 | True | 44 | 27 |
| v8_08 | 60 | True | 44 | 27 |
| v8_08 | 80 | True | 44 | 29 |
| pp_02 | 20 | False | None | None |
| pp_02 | 30 | True | 29 | 23 |
| pp_02 | 40 | True | 29 | 27 |
| pp_02 | 50 | True | 29 | 31 |
| pp_02 | 60 | True | 29 | 33 |
| pp_02 | 80 | True | 29 | 38 |
| time_01 | 20 | False | None | None |
| time_01 | 30 | False | None | None |
| time_01 | 40 | True | 34 | 40 |
| time_01 | 50 | True | 34 | 48 |
| time_01 | 60 | True | 34 | 53 |
| time_01 | 80 | True | 34 | 60 |

Candidate-absent failures and poor CE ranking are distinct. Carry-forward R0 domain failures: v8_08, pp_02, time_01; increasing K can admit evidence but cannot guarantee understanding.

## Measured latency and shared-GPU memory

| System | Logical pairs | Unique pairs | Actual scored | Retrieval s | CE s | Total batch s | CE ms/query | Peak allocated bytes | Peak reserved bytes | Minimum free bytes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| G3 raw K20 | 580 | 580 | 580 | 0.365603 | 0.991395 | 1.361855 | 34.186021 | 257613824 | 358612992 | 6995050496 |
| G3 raw K30 | 870 | 870 | 870 | 0.339280 | 1.501541 | 1.848339 | 51.777262 | 257613824 | 358612992 | 6995050496 |
| G3 raw K40 | 1160 | 1160 | 1160 | 0.360410 | 2.033790 | 2.403180 | 70.130703 | 257613824 | 358612992 | 6995050496 |
| G3 raw K50 | 1450 | 1450 | 1450 | 0.419213 | 2.551928 | 2.979640 | 87.997510 | 257613824 | 358612992 | 6995050496 |
| G3 raw K60 | 1740 | 1740 | 1740 | 0.368347 | 3.070443 | 3.645214 | 105.877331 | 257613824 | 358612992 | 6995050496 |
| G3 raw K80 | 2320 | 2320 | 2320 | 0.370451 | 4.141692 | 4.523864 | 142.816955 | 257613824 | 358612992 | 6995050496 |
| original | 2320 | 2320 | 2320 | 0.354336 | 3.966925 | 4.335400 | 136.790514 | 257613824 | 358612992 | 6995050496 |
| existing-expansion | 635 | 635 | 635 | 0.808834 | 1.080399 | 1.894472 | 37.255124 | 257613824 | 358612992 | 6995050496 |
| dense-preserving-union | 2392 | 2392 | 2392 | 1.178607 | 4.270652 | 5.461937 | 147.263862 | 257613824 | 358612992 | 6995050496 |

**Provisional raw candidate K: 80.** Frozen selection rule: Maximize candidate Recall@K, then candidate Hit@K, then CE Hit@20 and Hit@10; among tied quality choose lowest measured retrieval+CE milliseconds/query, then higher MRR, then smaller K. No query-specific K tuning. All timings are actual one-pass measurements on this shared machine; small differences can contain runtime noise. Peak memory includes both resident frozen models. No unrelated GPU workloads were terminated.

## Existing expansion construction and dense-preserving control

Existing policy: `{'source_path': 'D:\\SDC\\LibraryLLM\\rag\\reranker.py', 'source_sha256': 'e10dbe24ef1ce5f9083241d39b44246317db62ba5859f9321b6f220fe1079ced', 'evidence_source_sha256': 'c10f36c75fb414b9ce17b183f29ff78cc193d88bc379173040b473f939e261ca', 'per_branch_depth': 15, 'production_literal_cap': 40, 'only_controlled_override': 'MAX_MULTIQ_CANDIDATES = frozen provisional K; no other generation changes', 'merge': 'actual production AST: first-seen chunk dedupe, original query first, no sorting by dense score', 'hash_seed': '42', 'generation_note': 'existing family set iteration is process-hash-seed dependent; freeze seed42 and record all generated strings'}`. Execute the actual pre-CE AST from production RAGReranker.search; no production instance or composite score is run. Only its final cap is exposed as the same provisional K budget. The unchanged function uses 15 per branch and first-seen dedupe; at most three variants gives ≤45 candidates before dedupe, so the K ceiling can remain underfilled. Actual query strings/counts and literal-cap40 counts are saved in JSON. Original source text is never rewritten.

Union control: retain every original dense Top80 candidate, append at most20 unique existing expansion candidates in first-seen order; temporary pool ceiling 100. No original candidate is sacrificed. All three systems were separately retrieved and CE-scored to measure actual runtime.

K80 maximizes candidate coverage/Recall under the rule saved before the sweep (23 covered,74.14% recall). K60 is the practical quality/latency tradeoff: CE Hit20 is62.07% versus58.62% at80, and CE time105.88 versus142.82ms/query. The sole newly covered K60→80 query is time_03, whose accepted CE rank is54; v8_09 falls from CE19 atK60 to beyond20 atK80. The K80 recommendation is coverage-first and provisional, not an unqualified claim that80 gives better useful ranks than60.

| System | Candidate Hit | Candidate Recall | No gold | MRR | Hit1 | Hit3 | Hit5 | Hit10 | Hit20 | Recall5 | Recall10 | Recall20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| original | 79.31% | 74.14% | 6 | 0.3539 | 27.59% | 37.93% | 41.38% | 51.72% | 58.62% | 41.38% | 50.00% | 56.90% |
| existing-expansion | 58.62% | 55.17% | 12 | 0.3582 | 27.59% | 41.38% | 48.28% | 48.28% | 55.17% | 46.55% | 46.55% | 53.45% |
| dense-preserving-union | 82.76% | 77.59% | 5 | 0.3543 | 27.59% | 37.93% | 41.38% | 51.72% | 58.62% | 41.38% | 50.00% | 56.90% |

| System | Candidate count min / mean / max |
|---|---:|
| original | 80 / 80.00 / 80 |
| existing-expansion | 16 / 21.90 / 40 |
| dense-preserving-union | 80 / 82.48 / 100 |

| Critical target | System | Original dense rank | Candidate present | CE target rank |
|---|---|---:|---|---:|
| v8_06 | original | 47 | True | 1 |
| v8_06 | existing-expansion | 47 | True | 1 |
| v8_06 | dense-preserving-union | 47 | True | 1 |
| pp_05 | original | 49 | True | 12 |
| pp_05 | existing-expansion | 49 | False | None |
| pp_05 | dense-preserving-union | 49 | True | 12 |
| v8_08 | original | 44 | True | 29 |
| v8_08 | existing-expansion | 44 | False | None |
| v8_08 | dense-preserving-union | 44 | True | 29 |
| pp_02 | original | 29 | True | 38 |
| pp_02 | existing-expansion | 29 | False | None |
| pp_02 | dense-preserving-union | 29 | True | 38 |
| time_01 | original | 34 | True | 60 |
| time_01 | existing-expansion | 34 | True | 21 |
| time_01 | dense-preserving-union | 34 | True | 60 |

Original queries losing all accepted candidates under expansion: `['v8_08', 'v8_09', 'pp_02', 'pp_05', 'time_03', 'time_05', 'war_05']`. Lost original dense candidate rows 1764; reason counts `{'NOT_IN_ANY_QUERY_VARIANT_TOP15': 1764}`. Every lost ID, original dense rank, gold-overlap flag and determinable cause is in `rag_r0i_expansion_candidate_loss.json`.

- v8_08 (Dracula): accepted-overlapping `OL85892W__tokens_220__b0608a6d61982aa3`, original dense rank 44, loss reason NOT_IN_ANY_QUERY_VARIANT_TOP15.
- v8_09 (Frankenstein): accepted-overlapping `OL45326637W__tokens_220__4d0447747b4e43f9`, original dense rank 53, loss reason NOT_IN_ANY_QUERY_VARIANT_TOP15.
- v8_10 (Frankenstein): accepted-overlapping `OL45326637W__tokens_220__d692ecab271e2f41`, original dense rank 27, loss reason NOT_IN_ANY_QUERY_VARIANT_TOP15.
- v8_10 (Frankenstein): accepted-overlapping `OL45326637W__tokens_220__ab105de57c1622ef`, original dense rank 68, loss reason NOT_IN_ANY_QUERY_VARIANT_TOP15.
- pp_02 (Pride and Prejudice): accepted-overlapping `OL66524W__tokens_220__8b96df463e1033b2`, original dense rank 29, loss reason NOT_IN_ANY_QUERY_VARIANT_TOP15.
- pp_05 (Pride and Prejudice): accepted-overlapping `OL66524W__tokens_220__a636a19f5f30a36b`, original dense rank 49, loss reason NOT_IN_ANY_QUERY_VARIANT_TOP15.
- time_03 (The Time Machine): accepted-overlapping `OL27039837W__tokens_220__66ff965e46a058c0`, original dense rank 74, loss reason NOT_IN_ANY_QUERY_VARIANT_TOP15.
- time_05 (The Time Machine): accepted-overlapping `OL27039837W__tokens_220__f1a3b6c23f488f74`, original dense rank 16, loss reason NOT_IN_ANY_QUERY_VARIANT_TOP15.
- war_05 (The War of the Worlds): accepted-overlapping `OL33027136W__tokens_220__dac07da0ace467c2`, original dense rank 37, loss reason NOT_IN_ANY_QUERY_VARIANT_TOP15.
- war_05 (The War of the Worlds): accepted-overlapping `OL33027136W__tokens_220__6a6c883adc4a72ef`, original dense rank 50, loss reason NOT_IN_ANY_QUERY_VARIANT_TOP15.

The fixed per-variant Top15 request loses seven previously covered queries before the final cap: v8_08, v8_09, pp_02, pp_05, time_03, time_05 and war_05. At the frozen budget80 the existing expansion pools contain only16–40 candidates. No candidate is lost by a cap in this audit; all1,764 missing original dense IDs were never returned by any variant's Top15. v8_06 is preserved and remains CE rank1; pp_05's accepted target is omitted. Original/expansion/union accepted-evidence coverage is23/29,17/29,24/29; macro candidate recall74.14%,55.17%,77.59%. Expansion's slightly higher MRR does not outweigh lost accepted evidence. Dense-preserving union retains the complete original80 quota and restores it, while adding one covered query. These are frozen DRAFT-span metrics, not a claim that every nonaccepted passage is irrelevant.


## Label coverage diagnostics

Engineering-only POSSIBLE_LABEL_COVERAGE_LIMITATION instances: 17; unique queries `['pp_05', 'time_05']`. Carried-forward source-inspected Wickham/Lydia and red-sun passages directly support answers but fail frozen accepted-span overlap. No label or metric was changed, and these are not counted as gold. Exact passage text and observed CE rank for each pool are in JSON.

## Integrity and stop

Tests: `{'result': '20 passed', 'log_sha256': 'a8ebf3477966d462ff0e71964de753c3049c12dd9fe79adb4d738e99b5df8528', 'path': 'D:\\SDC\\LibraryLLM\\datasets\\training\\reports\\rag_r0i_contract_tests.log'}`. Final artifact checks: `{'score_rows_and_metrics_recomputed_from_saved_parquet': True, 'all_K_nested_and_original_order_preserved': True, 'raw_CE_sort_only': True, 'union_preserves_every_original_dense_candidate': True, 'same_G3_and_CE_fingerprint_all_systems': True, 'TEST_never_encoded': True, 'raw_phase_files_unchanged': True}`.

Final candidate-score parquet: 13467 rows, SHA-256 `2c486c3c7788e90d5fca635641699f7b01bddbe7bde41972df9d747b0a05cdcb`. Raw sweep report and raw scores remain unchanged after expansion. All historical/R0/model/label/source-map and 64 production files have zero changes. TEST evaluated: NO.

Artifacts added:

- `datasets/training/reports/rag_r0i_contract_tests.log`
- `datasets/training/reports/rag_r0i_expansion.log`
- `datasets/training/reports/rag_r0i_expansion_candidate_loss.json`
- `datasets/training/reports/rag_r0i_preflight.json`
- `datasets/training/reports/rag_r0i_raw_k.log`
- `datasets\training\evaluation\rag_r0i_candidate_pool_scores.parquet`
- `datasets\training\evaluation\rag_r0i_raw_k_scores.parquet`
- `datasets\training\reports\rag_r0i_candidate_pool.json`
- `datasets\training\reports\rag_r0i_candidate_pool.md`
- `datasets\training\reports\rag_r0i_raw_k.json`
- `scripts/evaluate_rag_r0i_candidate_pool.py`
- `scripts/evaluate_rag_r0i_expansion.py`
- `scripts/r0i_common.py`
- `scripts/report_rag_r0i_candidate_pool.py`
- `tests/test_rag_r0i_candidate_pool.py`

**FINAL R0I DECISION: D. CURRENT EXPANSION/CAPPING DESTROYS USEFUL G3 CANDIDATES — FIX CANDIDATE CONSTRUCTION BEFORE INTEGRATION.**

Stop after R0I. The provisional raw K is an engineering recommendation, not a production change. Candidate construction must preserve useful original dense evidence before integration; no composite-reranker experiment or CE fine-tuning was started.