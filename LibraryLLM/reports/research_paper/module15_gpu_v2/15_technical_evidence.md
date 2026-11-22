# 15 — LLM integration and AI orchestration

Snapshot `20261105T045721Z_606f0df_15_gpu_v2`, captured 2026-11-05 04:57:21 UTC; branch `codex/search-v11-finalization`, HEAD `606f0dfce3970bea8e6fc2b62d243433d1a66b8a`. [Snapshot](15_snapshot.json) · [checks](15_test_results.json) · [ledger](15_feature_status.csv). Historical CPU snapshot `20261031T140041Z_606f0df_15`; prior GPU evidence `reports/module15_gpu_verification/`; V2 evidence `reports/module15_gpu_v2/`. Repository paths identify external evidence; this package includes its own summaries. V2 outcome **FAIL**: one observed Reading List misroute; substantial coverage untested. Production Mongo authentication and index integrity **NOT QUALIFIED**.

## Model and engine inventory

| Component | Mechanism | Evidence | Limitations |
|---|---|---|---|
| Global Search | MiniLM embeddings, CrossEncoder reranking, FAISS HNSW | `search/luminar_search.py:LuminaRSearchEngine` | V2 used a controlled fixture; global index and accuracy unqualified. |
| Tenant Search | Injected encoder, optional reranker, tenant HNSW | `backend/services/library_intelligence_artifacts.py:build_search`, `search/library_intelligence.py` | No tenant security or retrieval evaluation in V2. |
| Document/book RAG | MiniLM embeddings, FAISS retrieval, cross-encoder reranking, Qwen generation and validation | `rag/services/document_service.py`, `rag/services/library_asset_pipeline.py`, `rag/qa.py` | Personal and institutional documents have separate scopes; no live RAG benchmark. |
| Assistant | Structured routing and tools over resident Qwen | `assistant/api.py:install_assistant`, `assistant/orchestrator.py:chat`, `assistant/qwen.py:QwenGateway` | V2 isolated assembly, not normal deployed topology. |
| Knowledge tools | Template-based quizzes and separate CPU MiniLM encoder | `rag/services/knowledge_quiz.py`, `knowledge_encoder.py` | Individual workflows and UI untested; not all artifacts use Qwen. |
| Knowledge Graph and recommendation | Metadata graph edges and recommendation scoring | `knowledge_graph/core.py`, `recommendation/recommendation_service.py` | Not evidence of an LLM-generated graph or Qwen scorer. |

## Qwen execution and quantization

The source `rag/llm.py:LuminaRLLM` specifies local-only Qwen/Qwen2.5-3B-Instruct. The prior direct probe loaded revision `aa8e72537993ba99e69dfaafa59ed015b17504d1` on `cuda:0`; the loaded model reported 4-bit NF4, double quantization and float16 compute. Its first parameter was bfloat16, distinct from quantized linear weights and compute dtype. Tokenizer commit metadata was absent. A direct factual response was correct for one question. Mock mode and full prompt debugging were disabled for the probe. V2 loaded the same reported model revision. See `reports/module15_gpu_verification/gpu_model_load.json`, `native_probe.json` and `reports/module15_gpu_v2/lab/live_results.json`. This establishes neither general accuracy nor deployed identity.

## Assistant routing and orchestration

The source default is `existing_qwen`; V3/V4/V5 require explicit configuration and are marked experimental (`assistant/api.py`, `assistant/ROUTER_FREEZE.md`). A task-owned Mongo instance and synthetic users supported real login and authenticated HTTP requests through the existing Assistant handler. The V2 assembly used a controlled global Search provider; one search request returned one synthetic catalogue item. Missing authentication returned 401; ambiguous availability produced a reference clarification. Exact per-tool traces were not captured. See `reports/module15_gpu_v2/assistant_live_api.json`, `test_environment.json`, `assistant_clarification.json`.

### Observed Reading List routing failure

The authenticated request “Show my reading list” was classified `USER_LOANS` instead of the Reading List operation. This is a failure for the observed case, not a population error rate. Its root cause is unknown. The relevant Assistant path includes `assistant/qwen.py:QwenGateway.parse` and `assistant/orchestrator.py:chat`; available evidence does not isolate either as the cause. `reports/module15_gpu_v2/assistant_routing.json`.

## Shared inference resource architecture

Source installs the Assistant gateway with `engine.llm` and `engine.inference_lock`; V2 observed identical gateway/engine model and lock objects within its assembly. The source defines a bounded gateway slot, one-worker executor and lock, and the institutional asset pipeline uses the inference lock for processing; the CPU study encoder has a separate lock. Actual Assistant/RAG contention, throughput, timeout behavior and recovery were not measured. Object identity does not establish scheduling performance. See `reports/module15_gpu_v2/shared_inference_runtime.json`, `assistant/qwen.py:QwenGateway.generate`, `rag/services/library_asset_pipeline.py:process_job`.

## Global and tenant Search relationships

Global and tenant Search provide catalogue retrieval rather than automatically invoking Qwen. The V2 controlled fixture demonstrates only the isolated request path, not production global index readiness, tenant retrieval, or absence of Qwen calls in production autocomplete. No production HNSW or KG rebuild was reported.

## Document RAG, grounding and citations

Source paths retrieve and rerank evidence, generate responses, validate support and assemble citations. `rag/document_grounding.py:select_definition_evidence` scopes definition candidates; `rag/qa.py:ask` contains NOT_SUPPORTED source suppression. Historical CPU work ran five synthetic helper checks without a model or service. Prior GPU regression populations ran 110 and 54 controlled tests separately. The reviewed current contract accepts `rag/qa.py` bytes and projects to the frozen hash through enumerated transformations. None measures live answer support, citation precision, abstention accuracy or complete ingestion. The V2 document request did not reach its deliberately unavailable callback; unavailable handling remains untested.

## Failure and fallback boundaries

| Trigger | Mechanism or observation | Limitation |
|---|---|---|
| Missing authentication | V2 HTTP 401 | One isolated endpoint case. |
| Ambiguous request | V2 clarification | Continuation, invalid choice and expiry untested. |
| Unsupported action | V2 returned clarification | State not independently verified. |
| Gateway timeout | Source returns unavailable while work may continue | No live timeout or recovery measurement. |
| Insufficient evidence | Source defines NOT_SUPPORTED and source suppression | Refusal and false-abstention rates unknown. |
| Document unavailable | Callback configured unavailable | Request did not reach it. |

## Authorization and prompt injection

Source-visible document checks include authorization, active generation and source scope (`rag/services/library_asset_pipeline.py`). V2 did not evaluate private tenant isolation, revoked access, cross-library substitution or malicious retrieved passages. Prompt wording treating records as data is not evidence of resistance. Production MongoDB authentication is not qualified.

## Reproducibility and limitations

Historical and current snapshots share HEAD but differ in working-tree source hashes; see `15_snapshot.json` and `reports/module15_gpu_v2/cross_machine_matrix.json`. Current `rag/qa.py` has mixed line endings, matches HEAD after Git normalization and satisfies the reviewed projection. The historical hash difference is only partially explained; line endings alone are not established as its cause. Full index integrity, production topology, live grounding, GPU contention and Chromium acceptance remain unmeasured. No CPU/GPU speedup can be calculated from different workloads.
