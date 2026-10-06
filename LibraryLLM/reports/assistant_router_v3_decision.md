# Semantic Router V3: FAIL

The CPU worker removes Qwen serialization from accepted requests, but the measured frozen-test precision and hybrid accuracy determine whether it is deployable. The default remains `existing_qwen`; this phase does not promote V3.

**A. Final outcome: FAIL.** Accepted precision gate: False; hybrid/critical gates: False; CPU concurrency gate: True.

**B. Larger model rejected.** A larger autoregressive router would still share GPU resources and inference admission with RAG. No larger model was benchmarked, installed or downloaded.

**C. Architecture.** Existing explicit UI action router → bounded identity/context builder → frozen CPU MiniLM → tiny independent heads → calibrated agreement/OOD/authority gate → existing deterministic tools, or one compact Qwen fallback. See `assistant_router_v3_architecture.md`.

**D. Encoder.** Cached `sentence-transformers/all-MiniLM-L6-v2`, frozen 384-dimensional normalized embeddings, CPU, maximum 256 tokens, two threads in an isolated process. Search/RAG CUDA encoders and settings are untouched.

**E. Classifiers.** {"intent_family": "mlp64", "intent_subtypes": "mlp64", "reference": "mlp64", "position": "mlp64", "fields": "mlp64", "criterion": "linear"}. Independent family and subtype heads must agree; reference source and position are separate. Supported catalogue fields and criterion presence have separate heads.

**F. Size.** 135,273 classifier parameters; 656,104 bytes excluding the manifest. The encoder is the already cached MiniLM, not an additional generative model.

**G. Data.** 3224 new compositional examples generated; 2635 retained after normalized deduplication. No private/user chat log training. Hand-authored intent definitions and synthetic references, topics and purposes; no Qwen data authoring.

**H. Split.** TRAIN 2112; DEV 523. Templates split before augmentation. Frozen 116/121 sets are TEST only. Synthetic repeated structures are a limitation, not evidence of real-world traffic distribution.

**I. Leakage.** Exact normalized TEST overlap after rejection: 0; embedding flags at cosine ≥0.97: 0. Both corpora and all old reports verified unchanged. Manual review checked 32 examples. See leakage and integrity reports.

**J. Alternatives on DEV.** Flat subtype accuracy 90.25%; family-constrained hierarchy 89.10%. Centroid/linear/MLP results for every head are in training.json. Runtime retains independent agreement rather than hiding family errors by masking.

**K. Family.** Existing: 99/111 (89.19%); held-out: 97/121 (80.17%).

**L. Subtype.** Existing: 85/111 (76.58%); held-out: 85/121 (70.25%).

**M. Reference source / position.** Existing: 110/116 (94.83%); held-out: 117/121 (96.69%).

Position binding equivalence: 62/88 and 70/91. Ordinal-word semantic gold is not separately labelled in the frozen corpus, so this is authoritative binding accuracy, not a claimed ordinal-language accuracy.

**N. Catalogue field.** Existing: 103/116 (88.79%); held-out: 106/121 (87.60%).

**O. Criterion presence.** Existing: 95/116 (81.90%); held-out: 110/121 (90.91%).

**P. Calibration.** DEV-only temperature scaling minimizes NLL; per-class confidence and ≥0.05 margin thresholds require empirical precision ≥97% with minimum eight accepted DEV examples. A DEV-selected centroid similarity floor rejects OOD. Small synthetic support is not a statistical guarantee.

**Q. Thresholds.** All head/class thresholds, supports and temperatures are preserved in calibration.json. Unsupported/unreliable classes use 1.01 and are never accepted. Mutation target is ≥99%, and every mutation still falls back and requires existing confirmation. No global arbitrary 0.8 cutoff.

**R. Coverage.** Existing 27/116 (23.28%); held-out 30/121 (24.79%). Target ≥70% missed; coverage was not forced.

**S. Accepted precision.** Existing 25/27 (92.59%); held-out 26/30 (86.67%). Target ≥97%.

**T. Fallback.** Existing 76.72%; held-out 75.21%. Target ≤30% missed. Per-category and reason counts are recorded in the case reports.

**U. Qwen calls per 100.** Restored semantic baseline approximately 100 routing calls; V3 existing 76.72, held-out 75.21. Accepted structured routes have zero Qwen calls. Fallback uses at most one routing call and no V2 retry; RAG/help retain their existing response generation separately.

**V. Existing hybrid strict.** 81/116 (69.83%), target ≥90%.

**W. Held-out hybrid strict.** 60/121 (49.59%), target ≥85%.

**X. Critical context.** 104/179 (58.10%), target ≥95%. Per-set critical results: {'passed': 61, 'total': 88, 'percent': 69.32} and {'passed': 43, 'total': 91, 'percent': 47.25}.

**Y. Safety.** Contextual fuzzy-title calls: 0; unrelated contextual Search calls: 0. Explicit entity fallback requires calibrated EXPLICIT source and literal grounding. Mutation confirmation bypass: zero in contract/regression checks; no live circulation mutations were performed.

**Z. Sports chain.** 6/6 live passes. See the live table below for intent, references, fallback, Qwen calls and latency.

**AA. Second pair.** 5/5 live passes. See the live table below for intent, references, fallback, Qwen calls and latency.

**AB. Accounts.** 1/4 live passes. See the live table below for intent, references, fallback, Qwen calls and latency.

**AC. CPU concurrency.** Worker inference plus IPC and policy; tools/HTTP excluded. No batching and optional five-millisecond micro-batching are measured separately in the table below. Batch size one remains default.

**AD. Mixed traffic.** {"total_seconds": 7.067448800007696, "accepted": 15, "accepted_latency": {"requests": 15, "median_ms": 190.49369999265764, "p90_ms": 299.72490000363905, "p95_ms": 315.6437600016943, "max_ms": 332.75609998963773, "throughput_per_sec": null, "errors": 0}, "fallback_errors": 4, "qwen_calls": 1, "cuda_delta_bytes": 0}. The existing Qwen gateway uses bounded busy rejection, not an unbounded queue. Actual mixed-request failures are retained.

**AE. Throughput.** Optional micro-batch 20-user classification / one-user Qwen routing: 744.3×. This compares routing only, not complete product capacity. Busy failures do not count as successful GPU throughput. GPU baseline is safely limited to 1/2/5 simultaneous attempts.

**AF. Resources.** {"classifier_worker": {"pid": 35044, "device": "cpu", "startup_ms": 20185.91080000624, "rss_mb": 778.35546875, "dimension": 384, "encoder_instances": 1, "cpu_threads": 2}, "rag_process_rss_mb": 1277.34375, "cuda_before_worker": {"allocated_bytes": 2267456512, "reserved_bytes": 2503999488}, "cuda_after_bench": {"allocated_bytes": 2267456512, "reserved_bytes": 2503999488}, "gpu_name": "NVIDIA GeForce RTX 5060 Laptop GPU", "host_ram_total_bytes": 16438054912, "worker_load_gpu_delta_bytes": 0, "cuda20_delta_bytes": 0, "queue_capacity": 64, "batch_size_default": 1, "batching_experiment": {"batch_size": 8, "delay_ms": 5}, "current_resident_qwen": {"attention_backend": "luminar_sdpa", "torch": "2.11.0+cu128", "transformers": "5.15.1", "cuda": "12.8", "device": "cuda:0", "gpu": "NVIDIA GeForce RTX 5060 Laptop GPU", "flash_available": false, "sdpa_flash_enabled": true, "sdpa_mem_efficient_enabled": true, "model_resident_id": 2230803160208, "pid": 33912, "model_footprint_bytes": 2010079744, "cuda_free_bytes": 5023727616, "cuda_total_bytes": 8546484224, "cuda_allocated_bytes": 2257888256, "cuda_reserved_bytes": 2327838720}, "cpu_worker_cuda_before_after": {"cuda_before": {"allocated_bytes": 2257888256, "reserved_bytes": 2327838720}, "cuda_after": {"allocated_bytes": 2257888256, "reserved_bytes": 2327838720}, "audit": {"pid": 35044, "device": "cpu", "startup_ms": 20185.91080000624, "rss_mb": 778.35546875, "dimension": 384, "encoder_instances": 1, "cpu_threads": 2}}, "live_rag_http": {"document": {"rag_status": 200, "rag_duration_ms": 15405.012500006706, "requests": 20, "qwen_calls": 0, "accepted": 20, "http_p95_ms": 8036.580764986866, "classifier_gateway_p95_ms": 4811.197994990653, "encoder_p95_ms": 30.394560001877853, "worker_queue_p95_ms": 16.240690008271486}, "book": {"rag_status": 200, "rag_duration_ms": 20916.723700007424, "requests": 20, "qwen_calls": 0, "accepted": 20, "http_p95_ms": 8388.823314991168, "classifier_gateway_p95_ms": 3331.994530001976, "encoder_p95_ms": 27.787474998331167, "worker_queue_p95_ms": 31.625390007684473}}, "http_integration_limit": "Fast independent CPU inference does not eliminate event-loop/client/auth/tool overhead in the shared RAG HTTP handler. HTTP coexistence tails exceed the classifier-only target; no RAG/Search algorithm changes made."}. CPU/RAM/queue details appear below and in resources.json. Startup CUDA allocation/reservation is compared before and after the CPU worker; unchanged inference tensors do not establish exact desktop VRAM across unrelated processes.

**AG. RAG coexistence.** {"document": {"rag_status": 200, "rag_duration_ms": 15405.012500006706, "requests": 20, "qwen_calls": 0, "accepted": 20, "http_p95_ms": 8036.580764986866, "classifier_gateway_p95_ms": 4811.197994990653, "encoder_p95_ms": 30.394560001877853, "worker_queue_p95_ms": 16.240690008271486}, "book": {"rag_status": 200, "rag_duration_ms": 20916.723700007424, "requests": 20, "qwen_calls": 0, "accepted": 20, "http_p95_ms": 8388.823314991168, "classifier_gateway_p95_ms": 3331.994530001976, "encoder_p95_ms": 27.787474998331167, "worker_queue_p95_ms": 31.625390007684473}}. Both RAG requests returned SUPPORTED; the disposable document was removed and a second user received 404. Encoder p95 stayed near 30 ms, but classifier gateway/HTTP p95 reached several seconds. This shared-handler latency misses the integration goal despite lock independence. No RAG quality changes were made.

**AH. Backend checks.** 805 distinct passing tests including 42 V3 contracts and 20 Search/pagination checks; 10 opt-in security integration checks skipped. The original full suite passed 781 before four extra query/auth/shadow/literal-ID contracts were added; the affected 235 tests and final 42 V3 tests pass. Full XML evidence retained. An isolated Search subprocess first hit Windows commit/paging pressure during overlapping checks and passed on its serial rerun. The older API freeze test now protects the unchanged authenticated handler/RAG callback AST.

**AI. Frontend.** 132 tests pass: 85 assistant plus 47 Search pagination, Part 3, KG and admin/notification UI tests. Frontend source is unchanged. One stale Part 3 assertion was corrected to the existing dedicated `action_work_ids` target while retaining the visible tray, without changing runtime behavior.

**AJ. Build/lint.** Production build passes with its existing large-chunk warning. Lint passes with zero errors and 19 existing warnings.

**AK. Exact source files changed/added.** `assistant/api.py`, `assistant/profiling.py`, `assistant/router_v3.py`, `scripts/router_v3_data.py`, `scripts/train_router_v3.py`, `scripts/evaluate_router_v3.py`, `scripts/check_router_v3_live.py`, `scripts/summarize_router_v3.py`, `tests/test_assistant_router_v3.py`, `tests/test_document_rag_latency.py`, `frontend/tests/part3-contract.test.tsx`. Artifacts: `assistant/models/router_v3/calibration.json`, `assistant/models/router_v3/criterion.pt`, `assistant/models/router_v3/fields.pt`, `assistant/models/router_v3/intent_family.pt`, `assistant/models/router_v3/intent_subtypes.pt`, `assistant/models/router_v3/labels.json`, `assistant/models/router_v3/manifest.json`, `assistant/models/router_v3/position.pt`, `assistant/models/router_v3/reference.pt`. Dataset: `training/assistant_router_v3/dataset.jsonl`. SHA256 source/artifact manifest is preserved separately; generated V3 reports/logs are additional evidence.

**AL. Training command used.** `.venv\Scripts\python.exe scripts/train_router_v3.py`. Reproduce into a new namespace: `.venv\Scripts\python.exe scripts/train_router_v3.py --output assistant/models/router_v3_reproduction --report-prefix assistant_router_v3_reproduction`. Existing manifests are never overwritten and no model is auto-activated.

**AM. Start commands.** From `D:\SDC\LibraryLLM`: set `$env:ASSISTANT_ROUTER_MODE="existing_qwen"`; clear `$env:ASSISTANT_ROUTER_V2_VARIANT`; set `$env:ASSISTANT_ROUTER_V2_RETRY="0"`; run `.venv\Scripts\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005 --workers 1`. For explicit experiment only change mode to `router_v3` or `router_v3_shadow`. Existing dependencies: `backend.main:app` on 8002, `search.api:app` on 8003 and `recommendation.api:app` on 8004 using the same uvicorn command. Frontend: `npm run dev -- --host 127.0.0.1 --port 5173` from `frontend`.

**AN. Production recommendation.** Keep `existing_qwen` active. Do not promote this classifier artifact. CPU discriminative routing is still the suitable concurrency direction, but this synthetic dataset/calibration does not meet correctness gates. No larger router or automatic fine-tuning is recommended or performed.

**AO. Limitations.** Synthetic template/context distribution differs from natural TEST language; many training contexts have a single focus, while real trays may have none. Position generalization and some classes fail despite optimistic DEV calibration. Low empirical support causes LOANS/HISTORY and other classes to abstain. Criterion continuation, complex filters, pagination and content remain Qwen fallback. Source/head classification cannot extract novel entities or free-form criteria. Book-RAG/pending flags are supported inputs but current compact context does not supply all of them; authenticated HTTP remains authoritative. Performance samples are synthetic and routing-only; the approximately 744× figure uses one successful single-request GPU baseline and is not a stable production-capacity estimate. Shared HTTP handler tails remain slow during RAG. Live pass criteria check public intent, authoritative references, fields and explicit clarification; live free-text criterion meaning was not separately persisted/reviewed. Frozen strict evaluation includes semantic goals and a manual criterion review. Default batching remains off. Search health remains its pre-existing stale-index state. A Qwen timeout caused a temporary busy episode, and an observer/report-file transport error was recovered without model or threshold changes; original affected evidence is archived.


## Frozen case results by category

| Set | Category | Requests | Accepted | Accepted correct | Fallback | Hybrid correct |
|---|---|---:|---:|---:|---:|---:|
| 116 | factual_comparison | 12 | 3 | 3 | 9 | 7 |
| 116 | preference | 12 | 0 | 0 | 12 | 12 |
| 116 | preference_criterion | 10 | 0 | 0 | 10 | 5 |
| 116 | availability | 10 | 1 | 0 | 9 | 5 |
| 116 | field_comparison | 5 | 0 | 0 | 5 | 5 |
| 116 | subject_comparison | 3 | 0 | 0 | 3 | 3 |
| 116 | ordinal_details | 10 | 2 | 2 | 8 | 7 |
| 116 | ordinal_availability | 6 | 4 | 3 | 2 | 5 |
| 116 | graph | 8 | 5 | 5 | 3 | 6 |
| 116 | recommendation | 5 | 1 | 1 | 4 | 4 |
| 116 | search | 8 | 3 | 3 | 5 | 5 |
| 116 | account | 13 | 6 | 6 | 7 | 10 |
| 116 | reference_ambiguity | 5 | 0 | 0 | 5 | 5 |
| 116 | previous_comparison | 3 | 0 | 0 | 3 | 0 |
| 116 | selection_change | 3 | 2 | 2 | 1 | 2 |
| 116 | explicit_entity | 2 | 0 | 0 | 2 | 0 |
| 116 | page | 1 | 0 | 0 | 1 | 0 |
| 121 | factual_comparison | 18 | 3 | 3 | 15 | 12 |
| 121 | preference | 5 | 0 | 0 | 5 | 5 |
| 121 | preference_criterion | 14 | 1 | 0 | 13 | 5 |
| 121 | availability | 10 | 3 | 1 | 7 | 6 |
| 121 | recommendation | 10 | 1 | 1 | 9 | 6 |
| 121 | graph | 5 | 1 | 1 | 4 | 1 |
| 121 | ordinal_details | 5 | 2 | 1 | 3 | 4 |
| 121 | account | 15 | 8 | 8 | 7 | 8 |
| 121 | search | 10 | 7 | 7 | 3 | 9 |
| 121 | previous_comparison | 16 | 2 | 2 | 14 | 2 |
| 121 | explicit_entity | 5 | 0 | 0 | 5 | 0 |
| 121 | page | 5 | 2 | 2 | 3 | 2 |
| 121 | selection_change | 3 | 0 | 0 | 3 | 0 |


## CPU concurrency

| Batching | Concurrent | Requests | Median ms | P95 ms | Requests/sec | Errors | Accepted | CPU % | Worker RSS MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| no_batching | 1 | 80 | 22.9 | 30.1 | 40.0 | 0 | 80 | 190.7 | 854.5 |
| no_batching | 5 | 80 | 113.5 | 141.0 | 42.7 | 0 | 80 | 175.8 | 855.5 |
| no_batching | 10 | 80 | 223.6 | 259.6 | 44.1 | 0 | 80 | 197.5 | 855.5 |
| no_batching | 20 | 80 | 422.8 | 448.8 | 46.6 | 0 | 80 | 191.9 | 855.5 |
| micro_batching | 1 | 80 | 33.5 | 48.1 | 27.3 | 0 | 80 | 152.2 | 855.1 |
| micro_batching | 5 | 80 | 54.7 | 117.0 | 83.6 | 0 | 80 | 193.3 | 861.8 |
| micro_batching | 10 | 80 | 54.1 | 106.4 | 150.2 | 0 | 80 | 176.6 | 866.0 |
| micro_batching | 20 | 80 | 114.3 | 169.0 | 149.7 | 0 | 80 | 196.8 | 866.5 |


## Live chains

| Chain | Message | Intent | Resolved public books | CPU accepted | Qwen calls | ms | Pass |
|---|---|---|---|---|---:|---:|---|
| original_sports | what differences do these books indicate | COMPARE_BOOKS | OL25644705W, OL20667625W | True | 0 | 1925.2 | True |
| original_sports | which one would be better | COMPARE_BOOKS | OL25644705W, OL20667625W | False | 1 | 4845.2 | True |
| original_sports | for someone mainly interested in soccer economics | COMPARE_BOOKS | OL25644705W, OL20667625W | False | 1 | 6361.5 | True |
| original_sports | is the first one available | CHECK_AVAILABILITY | OL25644705W | False | 1 | 3770.7 | True |
| original_sports | and the other? | CHECK_AVAILABILITY | OL20667625W | False | 1 | 3840.2 | True |
| original_sports | anything similar to that one | MORE_LIKE_THIS | OL20667625W | False | 1 | 5181.6 | True |
| second_pair | how do they stack up? | COMPARE_BOOKS | OL17930368W, OL2000134W | False | 1 | 5566.6 | True |
| second_pair | which has more subjects? | COMPARE_BOOKS | OL17930368W, OL2000134W | False | 1 | 5111.5 | True |
| second_pair | what about availability? | CHECK_AVAILABILITY | OL17930368W, OL2000134W | False | 1 | 4022.2 | True |
| second_pair | tell me more about the second | BOOK_DETAILS | OL2000134W | False | 1 | 5132.7 | True |
| second_pair | find something connected to it | MORE_LIKE_THIS | OL2000134W | False | 1 | 6227.9 | True |
| accounts | what books do I still have out? | CLARIFICATION |  | False | 1 | 6452.4 | False |
| accounts | do I owe the library anything? | USER_FEES |  | True | 0 | 534.1 | True |
| accounts | have I got any reservations? | USER_LOANS |  | False | 1 | 6075.9 | False |
| accounts | what have I borrowed recently? | CLARIFICATION |  | False | 1 | 5833.0 | False |
| search | I need a beginner-friendly book about machine learning | SEARCH_BOOKS | OL19542893W, OL20794000W, OL21654311W, OL19543070W, OL27389964W, OL20560218W, OL25591389W, OL19543610W, OL26198197W, OL25227435W | True | 0 | 4140.5 | True |
| search | something on saving and household budgeting | CLARIFICATION |  | False | 1 | 6106.4 | False |
| complex | I want whichever of these would give me more useful background for studying the economics of professional sports, but I'm less interested in management or player salaries. | COMPARE_BOOKS | OL25644705W, OL20667625W | False | 1 | 5456.3 | True |


## Integrity and transport recovery


{
  "original_files_checked": 3137,
  "authorized_changes": [
    "assistant/api.py",
    "assistant/profiling.py",
    "tests/test_document_rag_latency.py",
    "rag/private_documents/registry.sqlite"
  ],
  "unexpected_changes": [],
  "frozen_corpora_unchanged": true,
  "public_intent_enum_unchanged": true,
  "old_reports_unchanged": true,
  "search_recommendation_kg_rag_admin_notifications_frontend_preserved": true,
  "private_document_registry": "Runtime SQLite journal/header changed during authorized disposable upload/purge; zero document rows remain. RAG code is unchanged."
}

The initial timeout/stale-observer records are preserved in `assistant_router_v3_initial_transport_failure`. Final case reports retain initial valid responses, remeasure only transport failures/unfinished cases, and use request-local telemetry. No frozen TEST results changed weights, training examples or DEV thresholds. Each new evaluation request has at most one Qwen routing call.