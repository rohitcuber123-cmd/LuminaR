# Assistant latency baseline

Real CUDA/service measurements, 2026-10-01. Original Part 2 routing and generation behavior; numeric instrumentation only. Each case uses a fresh conversation. One resident Qwen process, no reload, mutations disabled. Startup excluded.

| Operation | Intent calls | Response calls | RAG calls | Intent generation ms | Tool wall ms | Response generation ms | Client total ms | Input / output tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| search | 1 | 1 | 0 | 13798.1 | 1958.0 | 34847.7 | 50991.5 | 2951 / 388 |
| available_now | 1 | 0 | 0 | 16365.4 | 0.2 | 0.0 | 16674.5 | 1255 / 121 |
| recommend_default | 1 | 1 | 0 | 13694.5 | 666.7 | 13008.4 | 27702.4 | 2948 / 206 |
| recommend_one | 1 | 1 | 0 | 23318.4 | 1708.9 | 12486.3 | 37862.3 | 3055 / 211 |
| recommend_multiple | 1 | 1 | 0 | 36815.2 | 3075.0 | 12801.9 | 53039.4 | 3829 / 243 |
| compare | 1 | 1 | 0 | 34172.0 | 50.0 | 2750.0 | 37292.8 | 3282 / 150 |
| availability | 1 | 1 | 0 | 24431.8 | 28.4 | 1795.5 | 26562.1 | 1760 / 131 |
| fees | 1 | 1 | 0 | 13800.7 | 13.6 | 2951.3 | 17074.7 | 2169 / 126 |
| loans | 1 | 1 | 0 | 13348.6 | 40.5 | 2437.9 | 16121.6 | 1567 / 120 |
| reservations | 1 | 1 | 0 | 13840.2 | 11.7 | 16733.4 | 30891.4 | 2298 / 236 |
| general | 1 | 1 | 0 | 14491.7 | 0.0 | 11381.7 | 26187.9 | 1559 / 199 |
| book_rag | 1 | 0 | 0 | 26174.4 | 20484.3 | 0.0 | 46966.5 | 1268 / 125 |
| document_rag | 1 | 0 | 3 | 14243.0 | 25179.5 | 0.0 | 39738.9 | 4098 / 288 |

Request validation, entity resolution, search, recommendation, Core metadata, availability, account, RAG and serialization observations are retained per case in chatbot_latency_baseline.json and the raw JSONL. Intent parsing is an inclusive stage (prompt/decoder setup, generation, JSON validation). Service timings sum concurrent HTTP calls; use tool_execution for elapsed wall time, not their sum.

The original model route returned clarification for Available now and the book-content query. These are failed routing cases, not successful baseline results. Document RAG ran successfully. An additional paired book-RAG run uses an existing reader with a currently borrowed, indexed book; it creates no loan.

Model calls consume almost all structured-operation latency. Search: 48,645.9 ms model generation versus 1,958.0 ms tool wall time. Default recommendation: 26,702.9 ms generation versus 666.7 ms tool wall time.

Runtime: {"attention_backend": "luminar_sdpa", "torch": "2.11.0+cu128", "transformers": "5.15.1", "cuda": "12.8", "device": "cuda:0", "gpu": "NVIDIA GeForce RTX 5060 Laptop GPU", "flash_available": false, "sdpa_flash_enabled": true, "sdpa_mem_efficient_enabled": true, "model_resident_id": 2937416829648, "pid": 18824}

Settings: constrained intent cap 650; prose cap 300; greedy do_sample=False, use_cache=True, torch.inference_mode; one beam. Completed baseline intents emitted 102–146 tokens including EOS, never approaching the cap. No evidence of substantial unused continuation after valid JSON.
