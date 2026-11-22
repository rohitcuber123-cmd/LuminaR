# 15 — Evaluation plan

Snapshot `20261105T045721Z_606f0df_15_gpu_v2`, captured 2026-11-05 04:57:21 UTC; branch `codex/search-v11-finalization`, HEAD `606f0dfce3970bea8e6fc2b62d243433d1a66b8a`. [Snapshot](15_snapshot.json) · [checks](15_test_results.json) · [ledger](15_feature_status.csv). Historical CPU snapshot `20261031T140041Z_606f0df_15`; prior GPU evidence `reports/module15_gpu_verification/`; V2 evidence `reports/module15_gpu_v2/`. Repository paths identify external evidence; this package includes its own summaries. V2 outcome **FAIL**: one observed Reading List misroute; substantial coverage untested. Production Mongo authentication and index integrity **NOT QUALIFIED**.

Ledger vocabulary: RUNTIME_VERIFIED means the bounded stated observation only; IMPLEMENTED_NOT_VERIFIED means source evidence only; OBSERVED_FAILURE is a failed case; NOT_MEASURED indicates absent evaluation.

| Outcome | OBSERVED versus PROPOSED | Protocol and control |
|---|---|---|
| Definition helper | OBSERVED | Five historical synthetic pure-function checks; no model or service. |
| Qwen and gateway | OBSERVED | Prior CUDA generation and direct intent/clarification probes; no authenticated tools. |
| Assistant HTTP | OBSERVED | Synthetic authenticated V2 assembly, fixture Search, 401, clarification and Reading List misroute. |
| Routing and safety | PROPOSED | At least 100 independently labeled balanced queries including Reading List/loans paraphrases, ambiguous references and unauthorized actions; report confusion matrix and counts. |
| Answer support | PROPOSED | At least 30 independent document-question pairs with gold spans and document/tenant-family splits; score retrieval, support, citations and abstention separately. |
| Authorization and injection | PROPOSED | Disposable users, revoked and cross-tenant cases; synthetic canaries and attacks verified as retrieved; count unauthorized actions and disclosure. |
| Failure recovery | PROPOSED | Actual unavailable callback, malformed intent, overload, timeout, empty retrieval and stale generation; record residual work and lock recovery. |
| Latency and resources | PROPOSED | Bounded concurrency; capture warm/cold condition, sample size, tokens, queue wait, p50/p95 and CPU/GPU peaks. |
| Knowledge and browser | PROPOSED | Exercise each supported study workflow and real Chromium rendering, login, switching and errors. |
| Reproducibility | PROPOSED | Pin model/tokenizer hashes, dependencies, prompts, source, hardware and cache state. |

These are proposed sample sizes, not executed results. Preserve independent labels and avoid general hallucination-rate or CPU/GPU speedup claims. Never transfer private documents to hosted baselines without authorization.
