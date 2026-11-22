# LuminaR Module 15 GPU V3 — Evaluation Methodology and Experimental Protocols

## 1. Environment Isolation and Non-Interference Controls

All live API, GPU, database, security, and browser verification runs were executed under strict isolation:
1. **Ephemeral MongoDB**: Every Python verification suite launched an isolated `mongod` instance via `isolation.py` (`C:\Program Files\MongoDB\Server\8.3\bin\mongod.exe`) bound to temporary storage and ephemeral localhost ports, leaving the running service on port `27017` (`luminar_library`) untouched.
2. **Hardware & Native Runtime**: Executed natively on `Windows-10-10.0.26300-SP0` using Python `3.11.9`, PyTorch `2.11.0+cu128`, CUDA runtime `12.8`, Transformers `5.15.1`, bitsandbytes `0.50.2` (driver `610.88`) on an `NVIDIA GeForce RTX 5060 Laptop GPU` (`8546484224` bytes / `7.9595` GiB VRAM reported, compute capability `12.0`, 26 SMs).
3. **Mock Suppression Verification**: Inspected process environment, `.env`, and `scripts/start_local.py` (`os.environ['LUMINAR_MOCK_LLM'] = '0'`) and asserted at runtime that effective `LUMINAR_MOCK_LLM == '0'` (`effective_mock_mode == False`) and that Assistant `QwenGateway` and `rag/qa.py` shared the identical in-process quantized model object and inference lock.

## 2. Priority 1 & Priority 2 — Root-Cause Trace, GPU Identity, Native Inference, and 142-Case Routing Evaluation

- **Root-Cause Reproduction**: Replayed 13 deterministic prompts (covering `"Show my reading list"`, 4 reading-list paraphrases, loans, history, fees, and named-title reading-list removal) before and after code changes (`pre_fix_repro_trace.json`, `post_fix_repro_trace.json`), capturing parsed structured intent, tool selection, clarify state, and database mutation status.
- **Model Identity & Native Probes (`15_model_identity.json`, `15_gpu_native_inference.json`)**: Verified loading of `Qwen/Qwen2.5-3B-Instruct` revision `aa8e72537993ba99e69dfaafa59ed015b17504d1` under 4-bit NF4 double quantization (`float16` compute) on `cuda:0`, logged RAM/CUDA memory deltas and init duration, and executed 5 bounded deterministic CUDA generation probes.
- **Routing Regression Suite (`15_routing_cases.jsonl`, `15_routing_confusion_matrix.json`)**: Constructed 142 independently labeled cases spanning `USER_READING_LIST` (16), `ADD_TO_READING_LIST` (10), `REMOVE_FROM_READING_LIST` (10), `CLEAR_READING_LIST` (4), `USER_LOANS` (14), `USER_HISTORY` (8), `USER_FEES` (8), `USER_RESERVATIONS` (8), `SEARCH_BOOKS` (10), `CHECK_AVAILABILITY` (8), `BOOK_DETAILS` (6), `COMPARE_BOOKS` (6), `RECOMMEND_BOOKS` / `RECOMMEND_FROM_BOOK` / `RECOMMEND_FROM_SELECTION` (6), `MORE_LIKE_THIS` (4), `DOCUMENT_QUESTION` (4), `GENERAL_LIBRARY_HELP` (4), `CLARIFICATION` (8), and `UNKNOWN` (8), including active-search and multi-book selection distractors. Recorded both raw `QwenGateway.parse` intent and end-to-end authenticated HTTP `/assistant/chat` intent, precision, recall, reading-list-to-account misroutes, and unexpected state mutations.
- **Clarification & Unavailable Callback (`15_clarification_results.json`, `15_unavailable_callback_results.json`)**: Tested 4 multi-turn clarification/continuation scenarios and verified fail-closed `HTTP_503` surfacing when the `/rag/ask` callback was unavailable on both `DOCUMENT_QUESTION` and `BOOK_CONTENT_QUESTION`.

## 3. Priority 3 — 32-Case Native Document RAG & Grounding Benchmark

- **Dataset (`15_rag_gold_dataset.jsonl`)**: 32 queries over synthetic multi-page technical/scientific PDFs with gold support pages, expected answer facts, and explicit abstention expectations across categories: `factual`, `definition`, `multi_paragraph`, `two_passages`, `missing_answer`, `contradictory_passages`, `ambiguous_reference`, `unrelated_question`, `cross_doc_confusion`, `nonexistent_page`, `page_location`, and `long_context_deep`.
- **Metrics (`15_rag_retrieval_metrics.json`, `15_citation_support.json`, `15_answer_groundedness.json`)**: Evaluated end-to-end retrieval Recall@k, full gold-page hit rate, latency distribution (mean, p50, p95, max), wrong-document citation count (`incorrect_doc_citations`), per-page citation precision & recall, strict answer fact-match rate on answerable items, false abstention rate, and correct abstention rate on unanswerable items.

## 4. Priorities 4 & 5 — Multi-Tenant Authorization & Prompt-Injection Evaluation

- **Authorization Matrix (`15_tenant_authorization.json`)**: 16 synthetic HTTP cases with embedded canary strings testing private personal document isolation across patrons, institutional asset visibility (`PUBLIC_PATRON` vs. `STAFF_ONLY`), cross-tenant library isolation, role-escalation blocks (`MEMBER` vs. `LIBRARIAN`), unauthenticated requests (`HTTP 401`), and deleted-document access (`HTTP 404`), counting observed canary leaks.
- **Prompt Injection (`15_prompt_injection.json`)**: 7 adversarial injection payloads placed inside document text and query context (`INJ-01`..`INJ-07`), measuring whether injected instructions overrode system grounding, leaked secrets/canaries, or forced fabricated claims (`SUCCESSFUL_DEFENSE` vs. `OBSERVED_VIOLATION`).

## 5. Priorities 6 & 7 — GPU Contention, Timeout Recovery, and Knowledge Tools

- **Contention & Timeout Recovery (`15_gpu_contention.json`, `15_timeout_recovery.json`)**: Measured warm single-request latencies (5 Assistant, 5 RAG), 2-way and 4-way concurrent requests sharing the single inference lock (verifying fail-fast `QWEN_UNAVAILABLE` slot rejection without spawning duplicate 3B model copies), mixed 3-way ingest+assistant+rag load, and explicit `0.15s` lock-acquisition timeout recovery followed by healthy Assistant and `/rag/ask` completions.
- **Knowledge Tools (`15_knowledge_tools.json`)**: 12 API checks across summary, key concepts, flashcards, mind map, quiz (`mcq`, `fill_blank`, `matching`, mixed), deterministic `cloze_grading` (`qwen_calls=0`), sparse-PDF graceful `question_count=0` handling, and cross-user artifact isolation (`HTTP 404`).

## 6. Priority 8 — Real Chromium E2E Acceptance (`15_browser_acceptance.json`)

Executed 9 headless Chromium Playwright flows against Vite (`http://127.0.0.1:5173`), Core backend (`8002`), Search/Rec fixtures (`8003`/`8004`), and real CUDA RAG/Assistant/Knowledge service (`8005`), asserting zero uncaught page errors and capturing UI screenshots (`screenshots/`): unauthenticated guard, login, search page, Assistant multi-turn search/reading-list/loans/clarify-continue (`Dracula`), institution switch & staff block, private PDF upload + RAG grounded answer + citation, unavailable model `503` recovery, Knowledge Tools quiz generation, and logout guard.

## 7. Priorities 9 & 10 — CPU Contract/Unit Regressions & Source Hash Audit

Executed offline pytest populations (V1/V2 baseline, V2o2 contract mutations, Assistant & Routing suite, Grounding & RAG contracts, Authorization & Institutional Docs, Loan Renewal, Loans & Search integration, Q4 Recommendation Concurrency) and 4 Vitest/Node frontend suites (`15_regression_results.json`), followed by byte-level post-change SHA-256 verification against the pre-change baseline (`15_source_hashes_post_change.json`).

