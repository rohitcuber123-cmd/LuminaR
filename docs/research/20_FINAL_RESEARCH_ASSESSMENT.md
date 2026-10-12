# Final research assessment

## Outcome

LuminaR has substantive implemented retrieval, QA, circulation and staff functionality. Its publication weakness is independent evidence and a sharply defended contribution. The repository is much richer than a CRUD prototype; it is not yet defensible as a completed private-library retrieval platform.

The current paper should center **semantic catalogue discovery with evidence-aware resource-specific RAG**, using independent relevance/source-span QA experiments and honest system limitations. A separate index-maintenance study could support it. The institution architecture belongs in extensibility/future work until authorized membership→upload→index→query→RAG isolation works and is evaluated.

## Verified / incomplete / absent

Verified code paths include MiniLM/HNSW catalogue ANN, cross-encoder reranking, immutable base/delta publication, selected-book FlatIP QA, session-owned PDF ingestion/QA, local Qwen/evidence checks, contextual assistant tools, heuristic recommendations, metadata relationships, auth/OTP/staff setup, borrow/return/reservation/renewal/fine records, inventory CSV/XLSX preview/confirm, real staff dashboards, events/unseen state and in-app notices.

Incomplete or conditional paths include optional lexical integration/sync (default off), assistant circulation mutations (default off and confirmed), full financial payment, independent correctness/grounding evidence, cross-store circulation completion, consistent physical availability in search, global full-text entitlement and atomic book-index publication. Experimental training/router/chunk variants do not change the base-model/default router story.

Not implemented in the traced active path: OCR, DOCX/TXT web upload, BM25/RRF catalogue hybrid, authenticated library registration/membership/active scope, institution-owned independent catalogue indexing, per-library HNSW registry, institution RAG/event/analytics isolation or scheduled event publishing. Existing library_id inventory/issue/UI fields constitute **EARLY IMPLEMENTATION / ARCHITECTURAL START — NOT PRODUCTION READY**.

## Readiness rubric

| Dimension | Max | Assigned | Reason |
|---|---:|---:|---|
| Implementation completeness | 25 | 20 | Broad real flows/tests; policy/consistency defects and deployment limits |
| Novelty | 15 | 5 | Integration/heuristics potentially interesting; no clear independent advance yet |
| Evaluation design/artifacts | 20 | 7 | Numerous tools and historical runs; proxy labels and limited independent current study |
| Reproducibility | 10 | 4 | Scripts/lock/assets exist; package ranges, hard-coded paths and incomplete run provenance |
| Architecture clarity | 10 | 6 | Traced separation/versioning; legacy duplication and mixed inventory authority |
| Data quality/rights/labels | 10 | 3 | Metadata and sources exist; truncation, teacher-percentile labels, source licenses require audit |
| Baseline comparison | 5 | 1 | Historical model/latency controls; complete fair current independent baselines missing |
| Experimental claim evidence | 5 | 1 | Scoped diagnostics, not enough headline independent evidence |
| **Total** | **100** | **47** | Editorial audit judgment, not a measured system score |

No points are added for unimplemented institution retrieval. Future architecture potential is qualitatively high for a systems study; assigning a second numeric score without workload/implementation would be artificial.

## Highest-value work

First independent query/QA gold, source representation/token-aware chunk experiments and entitlement/availability/consistency fixes. Then ablate already implemented evidence/expansion/reranking/lexical behavior. Finally implement authorized institutions and compare scoped indexes at controlled library selectivity/scale. Merely adding features or a libraryId field will not solve the research evidence deficit.

The strongest current research candidates are evidence-aware grounding/abstention, maintainable versioned semantic indexes, and resource-bound discovery/QA integration. The principal missing experiments are exact vs lexical/dense/rerank quality; HNSW vs exact neighbor fidelity and cost; RAG vs LLM plus evidence/chunk ablations; selected-resource/user isolation; mutation/crash recovery. Future tenant leakage/index architecture tests are a separate study.

## Audit limitations and reproducibility

414 Python source files were read structurally into the symbol/hash inventory; key runtime modules and frontend/service chains were manually traced. This does not mean every experiment/snapshot was executed or every line independently proved correct. No new tests, services, database access or index loads/builds were performed. Selected historical artifact JSONs were inspected; counts/latencies remain attributed to those artifacts. Secrets were not reproduced; live process environment and database schema are unverified. Application source was not modified.

The document set contains 00–23 plus `SOURCE_EVIDENCE_INDEX.md`. The most useful reviewer files are 09, 12, 17, 20, 21 and 22. Source pointers/labels must be updated if application code changes after this revision.

Documentation validation completed: all 24 required filenames present; 520 local Markdown links and 198 explicit source-path occurrences resolve; all 414 indexed source SHA-256 values still match; 68 reviewer answers and 31 explicit private-library answers are present. Git status contains only the 25 new research Markdown files. This checks document structure/references and source integrity, not application behavior or experimental claims.

## Request coverage map

| User request areas | Documents |
|---|---|
| Objectives, scope, repository reconnaissance (1–5) | 00,01,02,08,09, SOURCE_EVIDENCE_INDEX |
| Semantic search/HNSW/private mapping/ingestion architecture (6–16) | 03,08,21,22,23 |
| Book/PDF QA, chunking, models, operations, staff/events/analytics/auth (17–26) | 02,04,05,06,07,08 |
| Current/future private scope, datasets/lifecycle/registry/scalability/flows (27–35) | 03,07,21,22,23 |
| Feature matrix/cheat sheet/contributions/novelty/gaps/improvements (36–41) | 02,09,10,11 |
| Experiments/metrics/baselines/ablations/reproducibility/security/scale (42–49) | 11,12,13,21,22 |
| Architecture/figures/tables/claims/questions/hypotheses/titles/abstract/introduction/related work/methodology/pseudocode/stack/demo (50–64) | 03–08,14,15,16,17 |
| Reviewer defense/debt/tests/readiness/roadmap/story (65–70) | 01,11,12,18,19,20,23 |
| Output/quality/final assessment (71–73) | All 00–23; final chat |
| Explicit 31 private-library questions/API/directory/consistency/versioning/duplication/inventory/paper positioning (74–82) | 21 (numbered answers),22,23,14,17 |

## Test coverage inspection

Python `pytest.ini` selects tests/ and excludes reports/data/vendor directories. Existing tests cover semantic synchronization/mapping/corrupt snapshot/recovery and optional lexical variants; selected book entitlement/reference switching; private document/cache lifecycle; assistant routing/context; evidence/query types and RAG evaluation contracts; experimental chunk/training data metrics; knowledge graph; staff auth; events; notices and renewals. Frontend tests include assistant, routing/read-now, staff-auth, search-depth, document-cache, graph, event, admin-notice and renewal contracts.

Many fixtures mock service/model/DB components. These establish intended contracts; they do not measure human relevance or prove actual process/generation/concurrency performance. Package.json's default test command runs a subset (read-now/routing/assistant), not every frontend test file. Existing tests were inspected, not run here. Dedicated exhaustive borrow/return/reservation/fine failure/concurrency and future library ownership/isolation suites are needed; some access/renewal/notice tests exercise circulation indirectly. Tenant tests must include all negative routes, raw candidate/mapping/source/library assertions, corrupted-index fallback, active switching, event/analytics ownership and dataset replacement.
