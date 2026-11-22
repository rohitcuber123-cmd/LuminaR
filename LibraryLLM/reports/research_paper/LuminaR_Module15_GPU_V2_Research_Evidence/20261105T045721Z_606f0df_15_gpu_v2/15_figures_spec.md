# 15 — Figure recipes

Snapshot `20261105T045721Z_606f0df_15_gpu_v2`, captured 2026-11-05 04:57:21 UTC; branch `codex/search-v11-finalization`, HEAD `606f0dfce3970bea8e6fc2b62d243433d1a66b8a`. [Snapshot](15_snapshot.json) · [checks](15_test_results.json) · [ledger](15_feature_status.csv). Historical CPU snapshot `20261031T140041Z_606f0df_15`; prior GPU evidence `reports/module15_gpu_verification/`; V2 evidence `reports/module15_gpu_v2/`. Repository paths identify external evidence; this package includes its own summaries. V2 outcome **FAIL**: one observed Reading List misroute; substantial coverage untested. Production Mongo authentication and index integrity **NOT QUALIFIED**.

Figure recipes show source-defined flow. Named observations are limited to V2; these are not measured production deployment maps.

## Figure A — AI subsystem architecture (source-defined)
```mermaid
flowchart TD
 U[Authenticated user] --> A[Assistant router and tools]
 A --> S[Global or tenant catalogue Search]
 A --> R[Authorized book or document RAG]
 R --> E[MiniLM retrieval and reranking]
 E --> Q[Qwen generation and evidence validation]
 Q --> V[Response and citations]
 R --> K[Study templates and knowledge tools]
 K --> C[Separate CPU MiniLM encoder]
```

## Figure B — Tested integration boundary
```mermaid
flowchart LR
 U[Observed synthetic login] --> A[Observed Assistant HTTP handler]
 A --> Q[Observed resident CUDA Qwen]
 A --> S[Observed controlled Search fixture]
 A -.-> D[Document callback unavailable: not reached]
 D -.-> R[Source-defined RAG: unverified]
```
Legend: observed nodes identify V2 cases; dashed paths are source-defined or unverified. The document callback was not successfully exercised.

## Figure C — Shared inference model
```mermaid
flowchart LR
 A[Assistant gateway: observed] --> L[Shared inference lock: identity observed]
 R[Document RAG: source-defined] --> L
 I[Institution document processing: source-defined] --> L
 L --> Q[Resident Qwen: observed]
 C[CPU study encoder: source-defined] --> K[Separate encoder lock]
```
No contention, throughput or resource-allocation comparison is inferred.

## Figure D — Assistant routing
```mermaid
flowchart TD
 U[Authenticated request] --> G[Qwen structured intent]
 G --> T[Authorized tool orchestration]
 G --> C[Clarification when ambiguous]
 G --> F[Observed failure: Reading List classified USER_LOANS]
 F --> X[Expected Reading List route not selected]
```

## Figure E — RAG validation (source-defined; live evaluation NOT VERIFIED)
```mermaid
flowchart LR
 D[Authorized document] --> P[Prepare and chunk]
 P --> E[Embed and retrieve]
 E --> R[Rerank and select evidence]
 R --> Q[Qwen answer]
 Q --> V[Evidence validation]
 V --> S[Supported response and citations]
 V --> N[NOT_SUPPORTED and source suppression]
```
