# LuminaR Semantic Router V4 — final evaluation

## A. Final result: FAIL

V4 is evaluated and remains an experimental artifact. Both frozen precision gates failed, as did coverage, hybrid accuracy, critical context and required live cases. Production remains `existing_qwen`. No promotion, additional model, post-test fine-tuning or threshold reduction occurred.

| Gate | Observed | Result |
| --- | --- | --- |
| Accepted precision >=97%, both | 88.46% / 75.00% | FAIL |
| Accepted coverage >=70%, both | 44.83% / 39.67% | FAIL |
| Hybrid >=90% / >=85% | 72.41% / 56.20% | FAIL |
| Critical context >=95% | 60.34% | FAIL |
| Fallback <=30%, both | 55.17% / 60.33% | FAIL |
| Live sports / second / account / Search | 5/6; 5/5; 3/4; 1/2 | FAIL |
| Page / previous comparison / selection change | 1/3; 0/2; 1/1 | FAIL |
| 20 classifier routes p95 <1 second | 784.97 ms default; 686.27 ms experimental batching | PASS |
| Classifier independent of GPU lock; runtime CUDA delta zero | Zero lock acquisitions; zero bytes | PASS |
| Fuzzy-title and unrelated Search false positives zero | 0 / 0 on both frozen sets | PASS |
| Concurrent users resolve their own complete context | No observed crossover; 0/20 successful book responses | FAIL |
| Preserve other algorithms and V3 evidence | Hash audit confirms authorized shared changes only | PASS |
| Production build | PASS | PASS |

## B. V3 baseline

| Metric | 116 | 121 |
| --- | --- | --- |
| Accepted correct / accepted | 25/27 | 26/30 |
| Accepted precision | 92.59% | 86.67% |
| Coverage | 23.28% | 24.79% |
| Hybrid strict | 81/116 (69.83%) | 60/121 (49.59%) |

V3 combined critical context: 58.10%; fallback approximately 75%. V3 sources, artifacts, calibration, datasets and saved evaluations were hashed before work; see `assistant_router_v4_baseline.json` and the final integrity report.

## C. Training distribution gap

The evidence supports template bias, but does not establish causation. V3 repeated politeness wrappers and had one focused book in 80.04% of cases. V4 covers 14 authority states equally and several tray sizes, but **85.71% still contain one focused book**. That explicit distribution requirement was not fully achieved. Frozen language is shorter and contains more varied lexical combinations. V4 still underrepresents short elliptical turns and no-focus/full-pair states.

| Corpus | Mean words | Unique messages | Skeletons | Vocabulary | Distinct bigram ratio |
| --- | --- | --- | --- | --- | --- |
| v3 | 9.47 | 2635 | 840 | 496 | 0.101 |
| v4 | 10.34 | 1083 | 462 | 717 | 0.235 |
| frozen_116 | 6.59 | 115 | 114 | 267 | 0.784 |
| frozen_121 | 8.26 | 121 | 121 | 343 | 0.828 |

These are diagnostic comparisons, not frozen targets used for optimization. Full intent/reference/position/context and syntax-proxy distributions are in `assistant_router_v4_dataset_gap.json`. Frozen sets do not independently label every ordinal word; context/binding diagnostics are identified accordingly.

## D. V4 dataset size

15,162 total cases; 1,083 unique messages across 208 semantic seed families. TRAIN contains 9,590 cases, within the requested 8,000–20,000 training target. Counts include context permutations, not 15,162 independently authored utterances.

## E. Data sources

Manually authored seeds, existing local Qwen2.5-3B offline paraphrases, deterministic context/field/criterion permutations, and generic character transpositions (8% of TRAIN). Labels originate from seeds. No private conversations, production logs, or frozen evaluation utterances entered training. Final origin counts: 7,392 manual-seed cases; 7,770 approved Qwen-origin cases after expansion.

## F. Manual quality review

364 generated strings passed initial format collection; automatic filtering retained 305. Rejections: format/entity 4, placeholder drift 21, duplicate 1, too distant 31, too close 2. Similarity band: 0.55–0.965. A stratified 202-item review found 45 wrong meanings/label drifts (22.28%), eight awkward strings and zero remaining duplicates. All 305 were manually compared by the coding agent with their seeds; 227 were retained after conservative item/family rejection, and three ambiguous seeds were repaired before training. This was agent review, **not independent human annotation**. The large initial error rate prompted the semantic accept-list; similarity filtering alone was inadequate.

## G. Template diversity

V4 has 462 delexicalized skeletons and 5.21 unique messages per seed family, versus V3’s 840 skeletons and 11.71 messages per template family. V4 vocabulary and bigram diversity increased, while context replication inflates case count (32.82 cases/skeleton). Thus a larger corpus did not establish greater semantic breadth. Skeleton normalization is a heuristic lower-bound diagnostic, never a production language rule. Shared message-embedding clusters use cached base MiniLM, unique messages, 64 clusters and seed 947; the post-evaluation audit changes no model or predictions.

| Group | Occupied /64 | Entropy bits | Effective clusters | Largest cluster |
| --- | --- | --- | --- | --- |
| v3 | 61 | 5.685 | 51.4 | 4.17% |
| v4 | 57 | 5.518 | 45.8 | 4.89% |
| frozen_116 | 31 | 4.459 | 22.0 | 13.91% |
| frozen_121 | 32 | 4.540 | 23.3 | 11.57% |

## H. TRAIN / DEV / INTERNAL split

Seed families were assigned before generation: four of eight seeds per type to TRAIN (104 families), two to DEV (52), two to INTERNAL (52). All paraphrases/context variants remain within their family split. Final sizes: 9,590 / 3,724 / 1,848. Normalized messages also remain disjoint. Family separation reduces leakage but does not remove shared writing style or semantic-type/template bias.

## I. Leakage audit

Exact frozen-text overlap: 0; family split overlap: 0; near-duplicate flags at 0.97: 0. Maximum embedding similarity: 0.8906; p95: 0.7579. Frozen text was inspected only for distribution/leak auditing; no frozen labels entered losses, calibration or candidate selection. Both sealed evaluations ran once, after the candidate/runtime seal. The exclusive started marker prevents a second invocation.

## J. Encoder input

```text
[MSG] which one is available?
[STATE] active=SELECTION focus=1 changed=False awaiting=False document=False book_access=False
[SEL] 1|Public book title ; 2|Other public title
[CMP] none
[REC] none
[PAGE] none
[RECENT] none
```

The encoder sees public titles, ordinal positions and structural authority. Titles are bounded to 64 characters; each pool to four books; input to 256 tokens. Current message precedes current state/selection and older context. Work IDs, document IDs and private/account facts are excluded/redacted. IDs stay in parent-side binding. No descriptions or authors are serialized. Twenty-four existing numerical context features join the 384-dimensional normalized embedding.

## K. Frozen vs fine-tuned encoder

| Variant | DEV coverage | DEV precision | INTERNAL coverage | INTERNAL precision |
| --- | --- | --- | --- | --- |
| A_message | 9.02% | 100.00% | 4.55% | 100.00% |
| B_message_numeric | 21.08% | 98.73% | 13.96% | 93.02% |
| C_serialized | 9.88% | 99.46% | 7.41% | 100.00% |
| D_serialized_numeric | 12.46% | 99.14% | 10.17% | 98.94% |
| Fine-tuned critical / independent | 22.31% | 98.92% | 15.04% | 96.76% |

Old V3 heads on V4 INTERNAL: coverage 11.96%, raw subtype accuracy 84.47%; no comparable accepted-semantic precision was recorded for that legacy audit. A=message only; B=message+numeric; C=serialized context; D=serialized+numeric. Context serialization improves conservative internal coverage over A, but does not deliver the required generalization. Frozen V4 ablations used calibrated balanced linear heads. Only the sealed fine-tuned candidate was run against frozen116/121.

## L. Independent vs joined action

| Loss | Policy | DEV coverage | DEV precision | INTERNAL coverage | INTERNAL precision |
| --- | --- | --- | --- | --- | --- |
| equal | joint | 25.73% | 99.48% | 17.59% | 96.00% |
| equal | independent | 23.09% | 99.07% | 14.56% | 96.65% |
| critical | joint | 25.54% | 99.68% | 19.05% | 93.18% |
| critical | independent | 22.31% | 98.92% | 15.04% | 96.76% |

Seven multitask heads share the encoder. The joint action head has 31 semantic actions, including FIELD:attribute subclasses; the independent policy combines family/subtype consistency with relevant field/reference/position/criterion heads. The final precision-first comparison selected critical/independent. Both variants failed the INTERNAL 97% precision gate. Loss-masked irrelevant heads were removed from admission checks before sealing; no class thresholds were lowered. Trial-local `selected_policy` fields describe earlier DEV-only choices; the final operating point and artifact manifest are authoritative.

## M. Chosen architecture and training

Cached all-MiniLM-L6-v2, fine-tuned shared encoder, seven linear heads, two-thread CPU worker, bounded queue (64), one encoder per worker, default batch size one. Six-epoch maximum, DEV-loss early stopping (patience two), encoder LR 2e-5, head LR 0.002, AdamW decay 0.01, batch 32, gradient clipping 1.0, action-balanced sampling and relevant-head loss masks. Chosen epoch was the lowest DEV loss (epoch five). Loss weights: family 0.3, subtype 1, reference 1, position 1.2, field 0.8, criterion 0.6, action 1.2. Two loss variants were trained on each of two V4 corpus versions (four complete fine-tuning trials); the first corpus lacked some DEV field/criterion slots and was archived/repaired before frozen execution. Aborted plumbing/precompute attempts are preserved too.

DEV temperature scaling, per-class confidence/margin thresholds, centroid OOD floor and structural consistency control admission. Empirical class precision target is 97%, minimum 12 DEV cases per class, margin 0.05; disabled classes have thresholds above one. OOD floor: 0.223966. This is not a statistical population guarantee. Mutation requests retain Qwen plus confirmation. Free-form criteria and explicit entities retain extraction fallback. Qwen uses the existing resident model; maximum one routing call per rejected frozen request.

## N. Model size

Base MiniLM encoder approximately 22.7 million parameters, 384-dimensional output; seven heads contain 35,992 parameters over 408 inputs. Final artifact totals 91,844,728 bytes (87.59 MiB). Safe encoder serialization plus tensor-only head loading; every artifact file is hash-verified. Manifest seal: `7a7d002fbe6e5abb0ecb8d895cd6062aaa4a683aa597280daf2b68450ed0a72e`. Dataset/seed hashes, framework versions, loss weights, thresholds and encoder hashes are in the manifest.

## O. CPU and host RAM

Worker startup 11.08 seconds, startup RSS 777 MiB; live startup RSS 768 MiB. Peak observed benchmark RSS 888 MiB. Some no-batch samples reported 429 MiB after Windows working-set trimming; this is not the model’s full memory budget. Two threads used approximately 189–197% CPU under load. Host RAM 15,677 MiB; live service/commit snapshots include Mongo, Core, Search, Recommendation, RAG and Vite. Search had substantial pre-existing commit usage (~14.2 GiB); RAG ~8.4 GiB process commit. Windows commit includes nonresident/address-space effects and cannot be summed as physical RSS. Search subprocess regression ran serially, and normal services were reused for live load. No V4 Windows paging/commit failure was observed. Final restored-service snapshot is in `assistant_router_v4_restored_smoke.json`; its available physical RAM was ~1.6 GiB, so resource headroom remains limited.

## P. GPU usage

Training used CUDA offline. Runtime router worker reported `device=cpu`, `cuda_initialized=false`, allocated CUDA bytes zero. Both concurrency configurations changed CUDA allocation by zero bytes and never acquired the Qwen GPU lock. Existing RAG/Qwen CUDA allocation (~2.27 GB) is separate. A real held Qwen inference lock did not block 20 CPU classifier routes (p95 736.20 ms).

## Q. Intent accuracy

| Frozen set | Hybrid correct / applicable | Hybrid accuracy |
| --- | --- | --- |
| 116 | 94/116 | 81.03% |
| 121 | 81/121 | 66.94% |

Raw V4 pre-admission component accuracy: 116: 81/111 (72.97%); 121: 94/121 (77.69%).

## R. Reference accuracy

| Frozen set | Hybrid correct / applicable | Hybrid accuracy |
| --- | --- | --- |
| 116 | 85/88 | 96.59% |
| 121 | 73/91 | 80.22% |

Raw V4 pre-admission component accuracy: 116: 111/116 (95.69%); 121: 115/121 (95.04%).

## S. Position accuracy

| Frozen set | Hybrid correct / applicable | Hybrid accuracy |
| --- | --- | --- |
| 116 | 77/88 | 87.50% |
| 121 | 74/91 | 81.32% |

Raw V4 pre-admission component accuracy: 116: 77/88 (87.50%); 121: 86/91 (94.51%). Position is canonical book-binding equivalence, not independently annotated ordinal labels; explicit named entities are excluded.

## T. Field accuracy

| Frozen set | Relevant field head correct | Hybrid exact requested fields |
| --- | --- | --- |
| 116 | 7/8 | 7/8 |
| 121 | 2/6 | 2/6 |

Only explicitly requested field cases are meaningful for this loss-masked head. The legacy all-case `selective.components.fields` counters include irrelevant targets and should not be interpreted as field accuracy. Fine-tuned INTERNAL relevant-field accuracy is 100.00%.

## U. Criterion-presence accuracy

| Frozen set | Raw relevant preference-head correct | Hybrid explicit criterion required |
| --- | --- | --- |
| 116 | 22/22 | 4/10 (40.00%) |
| 121 | 19/19 | 5/14 (35.71%) |

Hybrid explicit-criterion accuracy includes existing interpretation fallback. Criterion detection does not extract free text; criterion-positive requests retain Qwen extraction. All-case raw criterion counters include masked/nonpreference cases and are descriptive only.

## V. Accepted precision

116: 46/52 = 88.46%; 121: 36/48 = 75.00%. Both fail 97%. False accepts were not hidden by compatibility scoring. INTERNAL had 269/278 = 96.76%, already below the gate before frozen testing.

## W. Accepted coverage

116: 52/116 = 44.83%; 121: 48/121 = 39.67%. Both fail 70%. Higher coverage than V3 came with lower precision. Risk/coverage curves are descriptive cached-prediction summaries; no post-test operating point was selected.

## X. Qwen fallback rate

116: 64/116 = 55.17%; 121: 73/121 = 60.33%. Confidence gating, invalid/ambiguous references, explicit entity extraction and complex/free-form interpretation retain fallback. Both fail <=30%.

## Y. Qwen calls per 100 requests

116: 55.17; 121: 60.33. Maximum one routing call, zero routing prose calls and zero retries on these runs. Accepted classifier routes use zero Qwen calls. These metrics are routing calls, not total generative RAG work.

## Z. Hybrid frozen 116

84/116 = **72.41%**, versus V3 69.83%; required 90%. This is strict output semantics including intent, authoritative references, fields/goal/criterion and clarification where applicable.

## AA. Hybrid frozen 121

68/121 = **56.20%**, versus V3 49.59%; required 85%. Compatibility-only accuracy is 69/121, but strict 68/121 is the decision metric.

## AB. Critical contextual accuracy

116: 61/88 = 69.32%; 121: 47/91 = 51.65%; combined 108/179 = 60.34%. Required 95%. Held-out previous-comparison strict accuracy was 1/16; selection change 1/3; page 3/5. Frozen generalization remains poor.

## AC. Safety false positives

Both frozen sets: contextual fuzzy-title false positives zero, unrelated contextual Search fallbacks zero, schema/semantic-invalid outputs zero. Mutations retain existing confirmation and authorization. No account credentials or private content were saved in live evidence. Zero crossover was observed in 20 concurrent users, but the functional isolation gate failed because none returned the requested complete book response; absence of output cannot prove useful context resolution.

## AD. Live conversational chains

| Chain | Correct | Required cases | Routing Qwen calls |
| --- | --- | --- | --- |
| original_sports | 5 | 6 | 2 |
| second_pair | 5 | 5 | 3 |
| accounts | 3 | 4 | 1 |
| search | 1 | 2 | 1 |
| complex | 1 | 1 | 1 |

Real public catalogue pairs: Economics of Football / The Economics of the National Football League, then Atomic Habits / Frankenstein. Sports failed “anything similar to that one” with an accepted incorrect intent (`RECOMMEND_AVAILABLE_SIMILAR` instead of `MORE_LIKE_THIS`). The second five-turn chain passed, partly through fallback. The live observer validates intent, references, requested fields and clarification; it did not independently judge every free-form criterion interpretation. Frozen semantic grading is stricter. Reported confidence below is the raw subtype head, not a probability that the entire answer is correct. Client elapsed time includes observer profile lookup; server trace timings are separately retained in JSON.

| Chain | Turn | Result | CPU accepted | Subtype confidence | Qwen calls | Client ms | Resolved public IDs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| original_sports | what differences do these books indicate | PASS | True | 0.9976 | 0 | 2236.7 | OL25644705W, OL20667625W |
| original_sports | which one would be better | PASS | True | 0.9886 | 0 | 169.1 | OL25644705W, OL20667625W |
| original_sports | for someone mainly interested in soccer economics | PASS | False | 0.9953 | 1 | 5727.6 | OL25644705W, OL20667625W |
| original_sports | is the first one available | PASS | True | 0.9775 | 0 | 137.1 | OL25644705W |
| original_sports | and the other? | PASS | False | 0.3090 | 1 | 2860.9 | OL20667625W |
| original_sports | anything similar to that one | FAIL | True | 0.9937 | 0 | 4713.6 | OL17442789W, OL7018729W, OL6912983W, OL18796962W, OL8493074W, OL6576899W, OL5598769W, OL10353169W, OL33390536W, OL11321519W |
| second_pair | how do they stack up? | PASS | True | 0.8964 | 0 | 191.2 | OL17930368W, OL2000134W |
| second_pair | which has more subjects? | PASS | True | 0.9801 | 0 | 194.3 | OL17930368W, OL2000134W |
| second_pair | what about availability? | PASS | False | 0.7339 | 1 | 2759.9 | OL17930368W, OL2000134W |
| second_pair | tell me more about the second | PASS | False | 0.4523 | 1 | 3631.7 | OL2000134W |
| second_pair | find something connected to it | PASS | False | 0.9828 | 1 | 5179.5 | OL2000134W |
| accounts | what books do I still have out? | FAIL | False | 0.9896 | 1 | 3677.9 | none |
| accounts | do I owe the library anything? | PASS | True | 0.9985 | 0 | 128.7 | none |
| accounts | have I got any reservations? | PASS | True | 0.8004 | 0 | 80.4 | none |
| accounts | what have I borrowed recently? | PASS | True | 0.9973 | 0 | 133.8 | none |
| search | I need a beginner-friendly book about machine learning | PASS | True | 0.9885 | 0 | 2380.1 | OL19542893W, OL20794000W, OL21654311W, OL19543070W, OL27389964W, OL20560218W, OL25591389W, OL19543610W, OL26198197W, OL25227435W |
| search | something on saving and household budgeting | FAIL | False | 0.7211 | 1 | 4471.9 | none |
| complex | I want whichever of these would give me more useful background for studying the economics of professional sports, but I'm less interested in management or player salaries. | PASS | False | 0.8928 | 1 | 4455.4 | OL25644705W, OL20667625W |

## AE. Live accounts

3/4. “what books do I still have out?” failed through Qwen fallback. Fees, reservations and recent-history phrases passed with zero Qwen routing calls. Account data was read under each request’s authorization and was not persisted in reports.

## AF. Live Search

1/2. Beginner-friendly machine-learning request passed classifier-only. Saving/household-budgeting request failed through fallback. Existing Search query/ranking/pagination algorithms were unchanged. Final Search health still reports pre-existing degraded index state; HTTP remains 200.

## AG. Page / previous comparison / selection change

Page 1/3: authors passed; availability and similar-books failed. Changing A+B to C+D passed the rating comparison (1/1). Clearing the tray after a valid comparison failed both previous-comparison follow-ups (0/2). Noise cases 1/2. Original test setup used invalid `COMPARE_SELECTED` with a null message; those two 422 setup calls and their dependent follow-ups were corrected using the real `COMPARE` contract and rechecked. Failed original attempts are retained separately. This observer repair changed neither model nor frozen evaluation. Concurrent own-pair query returned zero successful book responses across 20 requests, despite zero observed crossover.

## AH. CPU concurrency

| Concurrent | Default median ms | Default p95 ms | Default req/s | Batch median ms | Batch p95 ms | Batch req/s |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 37.98 | 44.83 | 25.77 | 50.68 | 66.18 | 19.02 |
| 5 | 193.36 | 207.91 | 25.94 | 161.84 | 170.25 | 31.50 |
| 10 | 383.59 | 404.88 | 25.85 | 231.76 | 468.67 | 36.22 |
| 20 | 749.30 | 784.97 | 26.33 | 465.50 | 686.27 | 35.84 |

80 requests per level per configuration, zero errors/Qwen/GPU-lock calls. Experimental micro-batching: max eight, 5 ms delay; measured sequentially with one encoder at a time. Both pass p95 <1 second at 20, both miss preferred <=500 ms. Default remains no batching. Queue and encoder timing plus CPU/RSS are in the concurrency JSON. These rates are classification throughput, not product capacity. No 744x capacity claim is made.

## AI. Mixed 20-user load

Observed eligibility probes targeted 14 classifier-eligible and six fallback messages; the measured concurrent run accepted 15. HTTP completion successes 16/20; busy rejections 4; failures 4; wall time 6.666 s; completion throughput 3.000 requests/s. Classifier median/p95: 228.09/428.01 ms (20 measurements); client HTTP p95 2452.62 ms. This is HTTP error/completion throughput, **not 16 semantically correct answers**. Existing Qwen admission remains bounded. Per-request classifier latency and busy status are retained.

## AJ. HTTP contention root cause and fix

Creating 20 per-request `httpx.AsyncClient` instances took 7,804.59 ms synchronously (~388.36 ms median each), blocking the RAG event loop before useful tool work. A single lifespan client is now reused (40 max connections, 20 keep-alive; 40 s timeout/connect 3 s). Every request creates its own tool wrapper and passes its own bearer header; no shared user/auth defaults. Client shutdown closes it. Pool configuration and transport setup changed; tool/auth/callback contracts and algorithms did not. Exact trace-joined server timing excludes client-side profile-file lookup. See `assistant_router_v4_http_contention.md`.

## AK. RAG coexistence

| RAG | HTTP | Verdict | CPU requests | CPU Qwen calls | Server p95 ms | Classifier/gateway p95 ms |
| --- | --- | --- | --- | --- | --- | --- |
| document | 200 | SUPPORTED | 20 | 0 | 741.70 | 665.82 |
| book | 200 | SUPPORTED | 20 | 0 | 841.51 | 739.13 |

40/40 concurrent fees requests were accepted with zero Qwen routing calls. Document and authorized book RAG returned supported answers while classification continued. V3 coexistence server p95 was roughly eight seconds; V4 measured 742/842 ms after the client fix. Document owner upload returned 200; another user’s access returned 404; the disposable synthetic document was deleted. No permanent catalogue/circulation mutation was performed. RAG took ~18.75/21.63 seconds for its own generative responses; CPU throughput does not remove generative admission limits.

## AL. Regression tests

833 unique backend tests passed; 10 opt-in integration tests skipped. This equals 805 existing baseline/regression passes plus 28 V4 tests; later V4 runs replace duplicated tests and resolve the initial missing-corpus skip. Frontend: 85 assistant tests plus 47 Search-depth/KG/notification tests = 132 passes. Coverage includes assistant, security/session/ownership, staff/admin/notifications, circulation, Search pagination, recommendation/KG, Know More, book access and document RAG security. V4 tests cover serialization/current-message priority/redaction, loss masks, seed splitting/overlap, frozen guard, accepted/rejected Qwen counts, GPU-lock independence, concurrent owner state and mutation confirmation. Group counts/XML/logs are indexed in the regression JSON. Skipped checks are not claimed as passed.

## AM. Build and lint

Production frontend build passed (TypeScript + Vite). Lint completed with zero errors and 19 existing warnings. No frontend source or ranking/algorithm implementation changed in V4.

## AN. Exact changed files

Modified existing files:

- `assistant/api.py`
- `assistant/profiling.py`
- `assistant/qwen.py`
- `tests/test_document_rag_latency.py`

`api.py` adds opt-in modes and the reusable HTTP transport; `profiling.py` records V4 numeric timings; `qwen.py` updates only the busy response text; the document latency test normalizes the authorized HTTP-client wrapper change while retaining the remaining handler contract assertion.

New source/test files:

- `assistant/router_v4.py`
- `tests/test_assistant_router_v4.py`
- `scripts/router_v4_data.py`
- `scripts/generate_router_v4.py`
- `scripts/prepare_router_v4.py`
- `scripts/train_router_v4.py`
- `scripts/select_router_v4.py`
- `scripts/seal_router_v4.py`
- `scripts/evaluate_router_v4.py`
- `scripts/check_router_v4_live.py`
- `scripts/audit_router_v4_completion.py`
- `scripts/summarize_router_v4.py`

New artifacts/data: `assistant/models/router_v4/`, `assistant/models/router_v4_candidates/`, `training/assistant_router_v4/`. New evidence is exclusively under `reports/assistant_router_v4*`, including the archived first V4 slot-coverage attempt. The complete recursive file inventory and hashes are in `assistant_router_v4_file_manifest.json`. Hash verification covers 3,245 baseline files: four authorized shared source/test files changed; no baseline file is missing; sealed runtime, artifact and manifest remain unchanged. The live upload/delete also changed `rag/private_documents/registry.sqlite` bytes; the registry contains zero rows after disposable-document removal. It was not restored from an old database snapshot. Original V3 source/data/evidence and Search/Recommendation/KG/RAG algorithms remain intact.

## AO. Exact training command

Commands used before the final seal, from `D:\SDC\LibraryLLM`:

```powershell
.venv\Scripts\python.exe scripts/train_router_v4.py --output assistant/models/router_v4 --seed 947 --device cuda
.venv\Scripts\python.exe scripts/select_router_v4.py --device cuda
.venv\Scripts\python.exe scripts/seal_router_v4.py
```

The corpus accept-list and seeds are versioned in the V4 training directory; framework versions/config/hashes are recorded. Reproduction must use a separate checkout/copy and fresh V4 report/candidate namespace. Do not run these commands against the completed experiment: the existing manifest guard refuses artifact replacement, while preparation/selection tools write their V4 evidence namespace. No reproduction training was run after the frozen evaluation. Numerical GPU nondeterminism can prevent byte-identical retraining.

## AP. Exact evaluation command

The one-time command used after sealing:

```powershell
.venv\Scripts\python.exe scripts/evaluate_router_v4.py --frozen-test --concurrency
```

`--frozen-test` requires matching manifest/runtime seal and an absent exclusive started marker. That marker now exists and blocks another frozen execution. For new development, `--concurrency` alone does not inspect frozen text; use a fresh evidence namespace/copy for future benchmarks. Live experiment used `scripts/check_router_v4_live.py`; only the invalid context observer setup was repaired separately. There was no repeated frozen probing.

## AQ. Start commands and restored state

Default RAG start (services are already running; do not start duplicates):

```powershell
$env:ASSISTANT_ROUTER_MODE = "existing_qwen"
$env:ASSISTANT_ROUTER_V2_VARIANT = ""
$env:ASSISTANT_ROUTER_V2_RETRY = "0"
$env:ASSISTANT_PROFILE_PATH = "D:\SDC\LibraryLLM\reports\assistant_router_v4_restored_profiles.jsonl"
.venv\Scripts\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005 --workers 1
```

Other existing services use `backend.main:app` on 8002, `search.api:app` on 8003, `recommendation.api:app` on 8004 and existing Vite on 5173. Experimental modes are supported through `ASSISTANT_ROUTER_MODE=router_v4` or `router_v4_shadow`; V3 modes remain supported too. **Neither V4 mode is enabled now.** Required offline gates failed, so conditional shadow validation was skipped. Restored typed comparison and natural first-book availability passed with no V4 telemetry; natural routing used existing Qwen. No router child remains. Health: Core/RAG healthy, Recommendation ready, frontend HTTP200, Search HTTP200/degraded (existing condition).

## AR. Production recommendation

Keep `existing_qwen`. Do not promote either V3 or V4. Retain the reviewed HTTP transport fix and numeric telemetry integration. V4 demonstrates that small CPU inference can coexist with generative RAG, but its false accepts and unresolved contextual cases are unacceptable. The frozen data remains sealed; no new model or automatic follow-on experiment has been started.

## AS. Known limitations

The experiment did not meet the complete language/data-distribution mission: most examples still have a single focus, only 1,083 unique messages underlie 15,162 cases, internal families share authored style, and manual review was performed by the agent rather than independent annotators. Critical previous-comparison, criterion and page semantics failed; explicit named entities still depend on existing Qwen extraction, which also failed some frozen cases. Higher acceptance is not safe capacity when precision is poor. Calibration uses correlated context variants and empirical thresholds without a population guarantee. Some all-case masked-head counters are not meaningful; relevant-only recomputations are reported above. Concurrent no-crossover checks returned no useful book responses. Mixed-load completion is not semantic accuracy. Optional integration tests were skipped; Search remains degraded and host RAM/commit headroom is limited. Timing reflects this Windows machine and its existing services; batching missed the preferred 500 ms p95 target. Shadow validation was correctly skipped. Frozen evaluations are complete once, the default is restored, and work stops here.
