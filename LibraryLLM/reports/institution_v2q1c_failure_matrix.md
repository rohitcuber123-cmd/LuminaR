# Part 2Q.1 continuation failure matrix

Evidence and cause are separated in the accompanying JSON.

| Case | Recorded behavior | Proven cause / missing evidence | Repair status |
|---|---|---|---|
| F01 | That position is not in the current book list. | Same conversation and ten recent IDs were supplied; actual parsed scope still unknown. | CONDITIONAL_ON_TRACE |
| F02 | Scope choice not captured in prior runs | Controlled RECENT_RESULTS/NONE binds SECOND; empty SELECTED_BOOKS/PAGE gives the observed error. This is not the actual model decision. | UNKNOWN |
| F03 | Page 15; SUPPORTED; four null source pages | All four matched public chunks have null pages; context headers include page only when metadata exists; the number appears in generation, not citation formatting. | APPLIED_AND_TARGETED_TESTED |
| F04 | Abstaining answers with SUPPORTED evidence verdicts | verdict is assigned before answer generation. Both cases used LLM evidence validation, not FAST_ACCEPT. | NO_GENERIC_REWRITE_JUSTIFIED |
| F05 | Computing/business networks/mathematics mix | Seed has no global ID; code routes this branch to subject-based local Search. The actual native/fallback provider was not recorded. | NOT_BEFORE_JUDGMENT |
| F06 | Not executed live in earlier work | Missing evidence, not a proven implementation defect. | EVALUATION_REQUIRED |
| F07 | 160 inventory rows unjudged, not 160 executions | No independent labels exist in the recorded artifacts. | REPORTING_ONLY |
| F08 | Live private-asset matrix previously missing | Public RAG030 abstention is not private authorization evidence. | EVALUATION_REQUIRED |
| F09 | HTTP 200; HNSW 613.67ms; 101 candidates; generation 30 | Existing machine endpoint returns a cache miss, native-stage timing, candidate/rerank counts and generation. | NO_REPAIR_NEEDED |
| F10 | Public subset executed; private/revocation/mobile coverage incomplete | Earlier browser evidence explicitly marked PARTIAL. | EVALUATION_REQUIRED |
