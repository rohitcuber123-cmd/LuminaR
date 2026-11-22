# LuminaR Module 15 GPU V3 — Figure and Table Generation Specification

All values referenced below are sourced exclusively from `reports/module15_gpu_v3/20261110T094131Z/*.json` (do not blend V1 or V2 metrics).

## Figure 1 — Reading List Repair Before-vs-After and Routing Confusion Matrix
- **Data Sources**: `pre_fix_repro_trace.json`, `post_fix_repro_trace.json`, `15_routing_confusion_matrix.json`.
- **Panel A (Focused Trace Comparison)**: 13 reproduction prompts showing pre-fix misroutes (`"Show my reading list"` -> `USER_LOANS` and `"Remove Synthetic Astronomy from my reading list"` -> `CLARIFICATION`) transitioning to 13/13 exact matches post-fix.
- **Panel B (Normalized Confusion Matrix on 142 HTTP Cases)**: Plot row-normalized counts from `http_response_evaluation.confusion_matrix` highlighting `USER_READING_LIST` (16/16 = 100% P/R, 0 misroutes into `USER_LOANS` or other account tools), `USER_LOANS` (13/14 = 92.86%), `SEARCH_BOOKS` (10/10 recall), vs. off-diagonal drift in `BOOK_DETAILS -> BOOK_CONTENT_QUESTION` (4/6) and fail-closed `CLARIFICATION` guards on selection/recommendation references.

## Figure 2 — RAG End-to-End Retrieval, Citation Support, and Answer Groundedness Profile
- **Data Sources**: `15_rag_retrieval_metrics.json`, `15_citation_support.json`, `15_answer_groundedness.json`.
- **Chart Type**: Paired metric breakdown across the 32 benchmark items:
  - Retrieval Recall@k = `1.0` (21/21 gold-page queries), wrong-document citations = `0`.
  - Per-page citation precision (`0.381` mean across 18 answerable queries; `79` same-document non-gold pages cited) vs. citation recall (`1.0`).
  - Answer groundedness: `13/18` (`0.7222`) strict fact match on answerable questions vs. `10/11` (`0.9091`) correct abstention on unanswerable/ambiguous cases, explicitly annotating `RAG-20` (textual abstention retaining 7 citations) and `RAG-22` (contradictory `FAST_ACCEPT` leak).
- **Latency Distribution Box/Violin Plot**: `15_rag_retrieval_metrics.json` latencies (mean `20,000.74 ms`, p50 `17,671.35 ms`, p95 `32,446.57 ms`, max `49,028.0 ms`).

## Figure 3 — Security & Prompt Injection Matrix
- **Data Sources**: `15_tenant_authorization.json` (16 cases), `15_prompt_injection.json` (7 cases).
- **Table/Heatmap**:
  - Tenant & Role Authorization: `13/13` negative/cross-tenant/role-escalation checks enforced (`401`/`403`/`404`/`409`) with `0` canary leaks; note `2/3` positive canary string checks returned `200` abstentions (`14/16` strict pass count).
  - Prompt Injection: 6/7 (`INJ-02`..`INJ-07`) defended (`SUCCESSFUL_DEFENSE`) vs. 1/7 (`INJ-01`) same-document instruction override (`OBSERVED_VIOLATION` emitting `OVERRIDE-999`).

## Figure 4 — Single-Copy 4-Bit CUDA Concurrency, VRAM Ceiling, and Lock Recovery
- **Data Sources**: `15_model_identity.json`, `15_gpu_contention.json`, `15_timeout_recovery.json`.
- **Dual-Axis Timeline & Memory Bar**:
  - Model footprint `2,010,079,744` B (`1.872 GiB`), post-load CUDA allocated `2,257,888,256` B (`2.103 GiB`), 2-way peak `2,528,740,352` B (`2.355 GiB`), 4-way peak `2,505,083,904` B (`2.333 GiB`) on `7.9595 GiB` GPU, `model_reload_count = 0`.
  - Latency comparison: Warm Assistant (`2,966.06 ms` mean, `3,504.84 ms` p95), Warm RAG (`14,640.99 ms` mean, `16,825.7 ms` p95), 4-way lock fail-fast `QWEN_UNAVAILABLE` rejection (`22.44 ms`), `0.15s` lock timeout (`166.22 ms`), followed by slot release (`11,336.26 ms`) and post-timeout Assistant (`2,430.84 ms`) + RAG (`13,955.45 ms`) recovery.

## Figure 5 — Real Chromium Browser UI Verification Evidence
- **Data Sources**: `15_browser_acceptance.json`, `screenshots/assistant_reading_list_and_flows.png`, `screenshots/document_rag_answer.png`, `screenshots/study_tools_quiz_ui.png`.
- **Composite UI Panel**: Annotated 3-frame strip demonstrating live Assistant clarification/continuation (`Dracula`), grounded PDF RAG answer + page citation badge (`Aurora-M4` on `12.0 volt DC`, `p.1`), and Knowledge Tools generated quiz (`7` MCQ + Fill-in-the-Blanks items).

