# 15 — Open questions and roadmap

Snapshot `20261105T045721Z_606f0df_15_gpu_v2`, captured 2026-11-05 04:57:21 UTC; branch `codex/search-v11-finalization`, HEAD `606f0dfce3970bea8e6fc2b62d243433d1a66b8a`. [Snapshot](15_snapshot.json) · [checks](15_test_results.json) · [ledger](15_feature_status.csv). Historical CPU snapshot `20261031T140041Z_606f0df_15`; prior GPU evidence `reports/module15_gpu_verification/`; V2 evidence `reports/module15_gpu_v2/`. Repository paths identify external evidence; this package includes its own summaries. V2 outcome **FAIL**: one observed Reading List misroute; substantial coverage untested. Production Mongo authentication and index integrity **NOT QUALIFIED**.

| Unknown | Evidence required / pointer | Priority | Why it matters |
|---|---|---|---|
| Reading List routed as USER_LOANS: cause? | Trace paired requests; assistant_routing.json | High | Wrong account tool may mislead. |
| Phrase-specific or broader intent collision? | Independent Reading List/loans labels; assistant_live_api.json | High | One failure cannot estimate prevalence. |
| Supported citations in live RAG? | Synthetic gold spans; citation_support.json | High | Grounding accuracy unmeasured. |
| Unavailable document callback behavior? | Route into unavailable callback; assistant_live_api.json | High | Prior request never reached callback. |
| Private tenant access end-to-end? | Membership, outsider, revoked and cross-library matrix; tenant_authorization.json | High | Source checks do not prove isolation. |
| Can retrieved PDF instructions drive tools? | Retrieve synthetic attacks and audit canaries; prompt_injection.json | High | Prompt wording alone is not proof. |
| Does shared inference bottleneck GPU? | Bounded contention and tracing; concurrency.json | Medium | Lock identity does not measure throughput. |
| Does timed-out work retain slot and recover? | Controlled timeout and recovery trace; timeout_recovery.json | High | Background work may continue. |
| Do knowledge tools work end-to-end? | Execute supported study workflows; knowledge_tools.json | Medium | Templates do not verify output. |
| Can tokenizer revision be identified? | Artifact provenance; model_identity.json | Medium | Commit metadata absent. |
| Why did historical qa.py bytes differ? | Compare original bytes and reviewed projection; grounding_contract_crosscheck.json | Medium | Mixed line endings do not fully establish cause. |
| Can production Mongo authentication be qualified? | Operator-approved evidence; final_qa.json | High | Local development Mongo is not production qualification. |
| Does normal topology match the assembly? | Safe full-stack verification; test_environment.json | High | Fixture assembly omits normal services. |
| Does Chromium render and recover? | Browser on disposable full stack; browser_acceptance.json | Medium | No browser acceptance. |
