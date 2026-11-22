# 15 — Paper-ready facts

Snapshot `20261105T045721Z_606f0df_15_gpu_v2`, captured 2026-11-05 04:57:21 UTC; branch `codex/search-v11-finalization`, HEAD `606f0dfce3970bea8e6fc2b62d243433d1a66b8a`. [Snapshot](15_snapshot.json) · [checks](15_test_results.json) · [ledger](15_feature_status.csv). Historical CPU snapshot `20261031T140041Z_606f0df_15`; prior GPU evidence `reports/module15_gpu_verification/`; V2 evidence `reports/module15_gpu_v2/`. Repository paths identify external evidence; this package includes its own summaries. V2 outcome **FAIL**: one observed Reading List misroute; substantial coverage untested. Production Mongo authentication and index integrity **NOT QUALIFIED**.

## Source-confirmed architecture

- Source configures Qwen2.5-3B-Instruct and installs Assistant with the resident engine and inference lock (`rag/llm.py`, `assistant/api.py`).
- Study quizzes use templates and a separate CPU MiniLM encoder where applicable; not all artifacts use Qwen (`rag/services/knowledge_quiz.py`, `knowledge_encoder.py`).

## Runtime-observed CUDA findings

- Local Qwen generated a factual response on CUDA; the loaded configuration reported 4-bit NF4, double quantization and float16 compute (`reports/module15_gpu_verification/native_probe.json`, `qwen_inference.json`).
- Model revision was reported; tokenizer commit metadata was absent (`reports/module15_gpu_verification/native_probe.json`).

## Native isolated HTTP findings

- Synthetic login and authenticated requests reached the existing Assistant handler; controlled Search returned a fixture item and missing authentication returned 401 (`reports/module15_gpu_v2/assistant_live_api.json`).
- Gateway and engine model/lock objects were identical in that assembly (`reports/module15_gpu_v2/shared_inference_runtime.json`).

## Observed failures

- One Reading List request was classified USER_LOANS; cause and frequency are unknown (`reports/module15_gpu_v2/assistant_routing.json`).

## Not established

- Live grounding, citations, tenant isolation, injection resistance, contention, timeout recovery and browser acceptance were not evaluated (`reports/module15_gpu_v2/final_qa.json`). Production Mongo authentication and index integrity remain NOT QUALIFIED. The current byte contract passes, but the historical mismatch is only partially explained (`reports/module15_gpu_v2/grounding_contract_crosscheck.json`).
