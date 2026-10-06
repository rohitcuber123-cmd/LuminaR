# LuminaR Router V5 — final decision

**FAIL. Do not promote V5, V4 or V3. `existing_qwen` is restored. Stop after this V5 evaluation.** No V6, classifier training, fine-tuning, larger Qwen or NLI download was started.

The small semantic registry is inspectable and CPU routing is fast. Its selective precision did not generalize and the shortlisted fallback is not reliable enough. Literal-span extraction still mistakes contextual phrases for book names. The full stack also experienced substantial host memory pressure.

## A–AI results

| Item | Final result |
|---|---|
| A. Status | **FAIL**: precision, coverage, hybrid, critical-context, fallback and fuzzy-title gates missed. |
| B. V4 lessons | CPU isolation, bounded queue, cancellation ownership, zero router CUDA, no admitted-route Qwen routing lock and shared HTTP transport preserved. V3/V4 evidence unchanged. |
| C. Binding | Structured arguments → reliable literal entities → selection → active previous comparison/recommendations → page → recent results/focus → extraction/clarification. Selection changes clear stale focus; explicit empty results do not revive it. |
| D. Registry | Definitions, five exemplars, negatives, existing intent mapping, source/argument requirements and confirmation flags. Separate positional/field/criterion banks. |
| E. Contracts | 29 action contracts. |
| F. Exemplars | Five per action, 145 total; auxiliary banks also five per label. No classification corpus/head fitting. |
| G. Retrieval | C: 0.70 max exemplar + 0.20 top-three exemplar mean + 0.10 definition cosine; per-action DEV-only score/margin gates. |
| H. CrossEncoder | Disabled in candidate. Full verifier improved raw DEV top-one matching but 20-way p95 was 1494.89 ms batched; compact form 1020.36 ms, both above hard gate. |
| I. Worker RSS | 857.62 MiB after initialization; selected benchmark 20-way RSS 857.61 MiB. Below 1.3 GiB. |
| J. DEV ablations | A/B/C/D and compact-D same 244-case DEV; details below. E hybrid 133/244 = 54.51%. |
| K. Sealed precision | 31/33 = **93.94%**, below 97%. |
| L. Sealed coverage | 33/168 = **19.64%**, below 60% target. |
| M. Sealed hybrid | 99/168 = **58.93%**, below 90%. |
| N. Critical context | 39/92 = **42.39%**, below 95%. |
| O. Old 116/121 | Strict hybrid 45/116 = 38.79%; 45/121 = 37.19%. These are exposed regression sets. |
| P. Account live | 3/4. Current loans/fees/reservations pass; recently-borrowed history fails. |
| Q. Comparison live | 2/4. General contrasts pass; preference ambiguity and rating comparison fail strict checks. |
| R. Previous context | 0/3; all three natural follow-ups fail. |
| S. Page | 1/3; availability passes, author/related queries fail. |
| T. Discovery | 2/3; vampires Search fails, joint recommendation and related-book request pass. |
| U. Fuzzy titles | **5** bad contextual entity spans in sealed parse; **9** actual unwanted contextual title-resolution calls in old regression (3/6). Zero gate fails. |
| V. Unrelated Search | New sealed parse: zero fresh Search action mistakes. Old product fixtures: **9** unrelated Search calls through bad title resolution (3/6). Zero gate fails. |
| W. Fallback | 135/168 = **80.36%**, above 40% target. |
| X. Shortlisted Qwen | Sealed fallback 68/135 = 50.37%. Paired DEV product replay: 21/40 shortlisted vs 10/40 full existing-Qwen; insufficient despite improvement in that sample. |
| Y. Qwen/100 | 80.36 actual routing generations per 100 sealed requests. At most one routing generation, no retry. Generative RAG/prose remains separate. |
| Z. Concurrency | CPU scorer p95 1/5/10/20: 35.64/77.66/144.29/209.18 ms with selected 5 ms batching. Routing throughput only. |
| AA. Mixed load | 15 admitted, 5 fallback, 4 busy, 15/20 semantically correct; end-to-end p95 1207.50 ms. Two real accounts, twenty conversations. |
| AB. CPU/RAM/GPU | Two worker CPU threads (~201% two-core usage in benchmark), router CUDA 0. Full-stack host available RAM fell to 228 MiB; commit reached 87.81% and paging peaked at 55539 pages/s. Memory-pressure gate fails. |
| AC. HTTP transport | Preserved single installation/lifespan AsyncClient, 40 max/20 keepalive, request bearer isolation. Regression passes. |
| AD. Tests | 898 backend passes, 10 skips; 137 frontend passes. 43 new V5 unit/executor checks. No test failures after fixture-separated runs. |
| AE. Build/lint | Build passes. Lint zero errors, 19 existing warnings. |
| AF. Exact files | Three existing source edits: `assistant/api.py`, `assistant/profiling.py`, `assistant/semantic.py`; new sources/data/artifacts listed below and every report/log/hash in `assistant_router_v5_file_manifest.json`. Empty private-document SQLite registry changed during synthetic upload/delete. |
| AG. Commands | Normal local start and experiment commands below. Current five services are running with default gateway restored. |
| AH. Production | Keep `existing_qwen`; preserve this rejected experiment as evidence. Do not deploy V5 or automatically start another model/router experiment. |
| AI. Limits | Small per-contract DEV support; manual author overlaps contract author; modest previous/changed/recommendation/short strata; field/position scoring weak; literal-span entity proof inadequate; legacy reading-list confirmation gap; two physical test accounts; host paging. |

## DEV comparison

Raw top-one accuracy is action-label matching, not accepted-route correctness. Admission additionally checks complete goal/identity/field/criterion/confirmation semantics. Thresholds use only DEV with at least four admitted support cases and 99% empirical precision; small support is not a statistical confidence guarantee.

| Method | Raw top-one action | Admitted | Admitted precision | Coverage |
|---|---|---|---|---|
| A | 104/244 (42.62%) | 24 | 100.00% | 9.84% |
| B | 146/244 (59.84%) | 41 | 100.00% | 16.80% |
| C | 162/244 (66.39%) | 50 | 100.00% | 20.49% |
| D | 175/244 (71.72%) | 28 | 100.00% | 11.48% |
| D_compact | 158/244 (64.75%) | 19 | 100.00% | 7.79% |

E uses the chosen C thresholds unchanged: 50/50 admitted correctly, 20.49% coverage, 133/244 strict hybrid correctness, 79.51% fallback. Full-Qwen paired controls were stratified, at most two per contract, capped at forty. Prompt input averages were 560.95 versus 900.43 tokens. Original raw parser-only control scores are retained but are not a fair product comparison because existing Qwen leaves some IDs/goal tags to the executor. The paired product replay uses the same cached decisions with complete in-memory API fixtures and strict comparison goals. No additional model calls or threshold changes were made for that replay.

Position DEV binding accuracy: definition-only 63/94; safe structural defaults 74/94; tiny exemplar/definition scorer 62/94. Structural defaults cannot resolve general ordinals/OTHER. The selected path uses calibrated positional scoring, structural defaults where safe and fallback otherwise; it still fails natural-language conversational position quality.

## Frozen evaluation provenance

The registry meanings were frozen before pack authoring; 168 cases were sealed before the separate 244-case DEV pack existed; thresholds were fixed before the candidate seal. The sealed evaluation ran once, then the old sets ran without adjustment. Candidate/runtime/cache hashes remain unchanged.

Sealed SHA-256: `8ec272c8db4d4b065f3af89347096bf67f09cf30b2d2ef422bb7f9a1f34fcdf4`.

Sources: 153 manually authored cases plus 15 reviewed offline existing-Qwen cases; rejected malformed/ambiguous/invented-title generations are retained. There are 160 no-focus and eight focused cases. Contexts: no context 59, page 45, selection 30, document four, authorized book four, current results eight, previous five, selection change five, recommendation three, four-book selection two, previous-focus one, one-book selection one and explicit empty result one. Seventeen turns have fewer than six words. These last conversational strata are modest and some transformations share a message. This is hash-sealed evidence, not perfectly independent human research.

New sealed scoring is parse-level and checks exact action, goal, IDs, supported fields, criterion presence/span, confirmation flag and continuation/filter arguments. It does not prove tool execution correctness. Old regression and live checks exercise the unchanged executor. Five new sealed entity failures would request inappropriate title resolution; nine old fixture cases actually do so and invoke unrelated Search. Underspecified refinement labels are retained as strict failures rather than changed after sealing.

## CPU and live concurrency

| Concurrency | Unbatched scorer p95 ms | 5 ms micro-batch p95 ms |
|---|---|---|
| 1 | 25.12 | 35.64 |
| 5 | 130.64 | 77.66 |
| 10 | 212.70 | 144.29 |
| 20 | 425.51 | 209.18 |

The held QwenGateway mutex test admitted 20/20 requests correctly, with zero routing lock acquisitions or generation and p95 199.27 ms. It uses an injected model that forbids generation, so no duplicate GPU stack is loaded. Real GPU coexistence is measured separately below.

Live isolated comparison probes: 20/20 correct, no cross-user book references, 20 admitted. Full-response p95 was 1654.65 ms; scorer p95 was approximately 117.68 ms. These repeat a DEV-admitted sentence to measure admission/load, and are not twenty independent natural-language successes or twenty physical user accounts. Core/auth/metadata transport plus host pressure make end-to-end time larger than pure scoring. Mixed load repeats some admitted probes and reports real semantic correctness, fallback and busy counts; it is not overall product capacity.

Document upload 200; cross-user ask 404; document answer 200; Book RAG answer 200. Twenty admitted account queries alongside each RAG request had server p95 356.32 ms / 616.40 ms. The synthetic document was deleted, and the restored registry/directory counts are both zero. Private data, tokens, emails and private chunks are not persisted in V5 evidence.

The cached [CrossEncoder L6 publisher model card](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2) specifies Apache-2.0 and MS MARCO relevance training, not entailment verification. No NLI model was downloaded. An unmeasured NLI model is not recommended automatically: measured full-stack paging and already-failed semantic/latency evidence do not establish that another model would meet this task's gates.

## Confirmation and restoration

Borrow, return and reserve were tested with write spies and mutations enabled: no execution before confirmation. The existing security/confirmation suite passes. Reading-list add/remove are different: the unchanged legacy executor writes immediately and ignores the V5 confirmation flag. Cached-decision replay demonstrates that gap in memory; no real reading-list mutation is requested by the live matrix. This prevents claiming universal mutation safety from a parser flag. Clear still requires its existing explicit UI action.

All five service readiness endpoints return 200 (Recommendation uses `/`, not `/health`). The restored typed comparison passes and both smoke profiles have no V5 telemetry. The restored natural page-availability query clarifies instead of answering; that existing-Qwen limitation is recorded and not repaired in this stopped experiment. A transient stale Windows LISTEN row initially blocked restart after the old process had stopped; the helper now waits for socket release and refuses duplicate services.

## Exact new source, evaluation and artifact files

Existing source edits are only the three listed under AF. All other baseline sources/models/datasets/reports remain byte-identical. The sole runtime-data difference is the cleaned private-document registry. The machine-readable file manifest includes all new report/log/evidence hashes as well as these files:

- `assistant/models/router_v5/calibration.json`
- `assistant/models/router_v5/contracts.json`
- `assistant/models/router_v5/manifest.json`
- `assistant/router_v5/__init__.py`
- `assistant/router_v5/binding.py`
- `assistant/router_v5/contracts.py`
- `assistant/router_v5/gateway.py`
- `assistant/router_v5/matcher.py`
- `assistant/router_v5/worker.py`
- `evaluation/assistant_router_v5/dev.json`
- `evaluation/assistant_router_v5/generation_review.json`
- `evaluation/assistant_router_v5/independent_qwen_raw.jsonl`
- `evaluation/assistant_router_v5/sealed.json`
- `evaluation/assistant_router_v5/sealed_manual.json`
- `scripts/author_router_v5_dev.py`
- `scripts/benchmark_router_v5_dev.py`
- `scripts/calibrate_router_v5.py`
- `scripts/check_router_v5_live.py`
- `scripts/check_router_v5_lock.py`
- `scripts/compare_router_v5_positions.py`
- `scripts/evaluate_router_v5.py`
- `scripts/evaluate_router_v5_dev.py`
- `scripts/finalize_router_v5_candidate.py`
- `scripts/freeze_router_v5.py`
- `scripts/prepare_router_v5.py`
- `scripts/replay_router_v5_controls.py`
- `scripts/report_router_v5.py`
- `scripts/router_v5_data.py`
- `scripts/router_v5_evidence.py`
- `scripts/serve_router_v5.ps1`
- `scripts/summarize_router_v5_regression.py`
- `scripts/verify_router_v5_restored.py`
- `tests/test_assistant_router_v5.py`

## Start/reproduction commands

Services are already running. From a stopped normal stack, use `D:\SDC\LibraryLLM` as working directory:

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
.venv\Scripts\python.exe -m uvicorn search.api:app --host 127.0.0.1 --port 8003
.venv\Scripts\python.exe -m uvicorn recommendation.api:app --host 127.0.0.1 --port 8004
$env:ASSISTANT_ROUTER_MODE='existing_qwen'
.venv\Scripts\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005
```

Run `npm run dev -- --host 127.0.0.1 --port 5173` from the frontend directory. Hidden, duplicate-checked service helpers are `scripts/serve_router_v5.ps1 -Mode dependencies`, `-Mode experimental-rag` and `-Mode restore-rag`. The experimental mode is preserved for review, not recommended for production. The sealed runner command was `.venv\Scripts\python.exe scripts/evaluate_router_v5.py --sealed-once`; its exclusive marker prevents a second evaluation. Do not clear that marker to retune or rerun this pack.

**Stop condition reached: V5 evaluated and rejected, default restored, no automatic follow-on experiment.**
