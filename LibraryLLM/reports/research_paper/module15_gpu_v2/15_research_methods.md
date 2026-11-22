# 15 — AI research methods

Snapshot `20261105T045721Z_606f0df_15_gpu_v2`, captured 2026-11-05 04:57:21 UTC; branch `codex/search-v11-finalization`, HEAD `606f0dfce3970bea8e6fc2b62d243433d1a66b8a`. [Snapshot](15_snapshot.json) · [checks](15_test_results.json) · [ledger](15_feature_status.csv). Historical CPU snapshot `20261031T140041Z_606f0df_15`; prior GPU evidence `reports/module15_gpu_verification/`; V2 evidence `reports/module15_gpu_v2/`. Repository paths identify external evidence; this package includes its own summaries. V2 outcome **FAIL**: one observed Reading List misroute; substantial coverage untested. Production Mongo authentication and index integrity **NOT QUALIFIED**.

## Implemented and observed methods

The original CPU stage combined source inspection with five isolated synthetic definition-helper checks, without running a model, GPU, database or service. The first GPU stage inspected loaded quantization, generated one factual answer and probed the accepted gateway; controlled regression populations of 110 and 54 tests were recorded separately. V2 used a task-owned local Mongo process, synthetic users, application login and actual HTTP Assistant requests in an assembled service. Global Search was a fixture; the document callback was unavailable and not reached. The object identity check covered gateway/engine sharing, not contention. No production data was needed.

The source contract was assessed by exact-byte checks and an enumerated projection to the frozen hash. The historical mismatch remains partially explained. No live grounded-answer accuracy, tenant authorization or prompt-injection experiment was conducted. Report the Reading List misroute without estimating population accuracy from one case.

## PROPOSED research methods

Use independently labeled paired intent queries with document, tenant and template-family splits. Annotate gold source spans independently of outputs; score retrieval and evidence selection separately from answer support, citation precision/recall and abstention. Use synthetic cross-scope canaries, verify attack retrieval, and record actual tool actions. Bound concurrency and record queue time, response time, sample size, token count, hardware, memory and eventual recovery. Preserve source hashes, model and tokenizer artifacts, dependencies, cache and authorization context; secure licenses and consent. These are proposed methods, not measurements already made.
