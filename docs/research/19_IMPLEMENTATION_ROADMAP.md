# Prioritized implementation and publication roadmap

This audit implements documentation only. The following application work is **PROPOSED**. Complexity estimates are relative, not schedules or measured effort.

## P0 — required before a current-system paper submission

1. Freeze paper scope and claim inventory; snapshot source/models/data/artifact provenance. Produce independent catalogue relevance and QA/source-span test sets. Owners: research/data work; dependencies: rights and representative query sampling; complexity medium. Benefit: defensible primary evidence.
2. Resolve global/unselected full-text authorization policy (`rag/api.py`, `book_access`, `retriever`), availability source mismatch (`ranked_pages`, `luminar_search`, `availability_service`) and book-index atomic publication (`embed`, `book_runtime`). Dependencies: explicit source entitlement contracts; complexity medium/high. Benefit: credible resource-specific system behavior.
3. Address or explicitly quantify oversized chunk truncation (`book_ingest`, `document_service`, `experimental_chunker`, `embed`). Freeze compatible separate experimental indexes before rollout; complexity medium. Benefit: represent source evidence without silent encoder loss.
4. Establish failure-safe circulation and identity/inventory constraints (`issue`, `reservation`, `fine`, `book_service`, migration/index scripts). Dependencies: Mongo deployment capabilities; complexity medium/high. Benefit: reliable workflows under failures/concurrency.
5. Run E1/E2/E3/E6/E7/E10 with controlled baselines and raw manifests; report CI, tails, refusals and failures. Complexity medium/high. Benefit: measured novelty/usefulness rather than feature lists.

## P1 — strongly recommended

Evaluate optional lexical pipeline/sidecar consistency and existing cross-encoder/expansion/evidence gates; add BM25 baseline and RRF experiment; token-budget prompt instrumentation; claim-level source mapping; process-stable assistant context or explicit sticky/single-worker deployment; session-bound frontend stale-response fencing for all data; scoped permissions groundwork and index observability. Improve package/model/data version pins and portable paths. Each needs an explicit hypothesis or reliability acceptance test.

## P2 — optional

Multilingual evaluation/model variants, OCR for scanned documents, richer copy/item records, learned recommendations with valid temporal labels, event personalization/delivery channels, accessibility/user study, and distributed catalogue discovery. Do not expand scope before primary retrieval/QA evidence is complete.

## Future architecture — Private Library IDs

Overall current status remains **EARLY IMPLEMENTATION / ARCHITECTURAL START — NOT PRODUCTION READY**. Inventory groundwork can be reused. See 23 for staged acceptance gates.

| Phase | Scope / code areas | Dependencies | Complexity | Research benefit |
|---|---|---|---|---|
| 1 Data model | New Library/Membership/Dataset; extend inventory into Holdings; migrate legacy LIB001 and shared works | Ownership/private metadata decision; audit actual indexes | High | Establish independent evaluation corpus units |
| 2 Scoped CRUD | backend dependencies/routes/services books/inventory/issues/reservations; LibraryContext; authorized active L | Phase1 and access policy | High | Reliable candidate and historical scope |
| 3 Dataset upload | Extend StaffForms/API with separate catalogue upload, staged parser/jobs/status/version/checksum | Phase2 + validation/idempotency design | High | Dynamic independent data-to-index study |
| 4 Index partitioning | IndexRegistry + scoped IndexManager/SyncQueue/cache/mappings/manifests; small FlatIP/large HNSW | Phase3 source publication model | High | Compare index cost under selectivity/churn |
| 5 Scoped semantic search | search API/current_books/lexical/ranking/paging/recommendation; final scope assertions | Phase4 + authorized context | High | Isolation/recall/latency experiments |
| 6 RAG isolation | rag API/access/retriever/book_assets/private-shared sources; assistant state/tools/citations | Phase5 and source ACLs | High | Isolation-aware generation evaluation |
| 7 Library UI | App/Header/store, select/join/switch, dataset/index status; stale response fencing | Backend contracts Phases2–6 | Medium/high | User workflow/membership experiments |
| 8 Library operations | Scoped events/seen/notices, analytics, queues/circulation/policies/history | Phase2 authorization and scoped entity migration | High | End-to-end ownership demonstration |
| 9 Evaluation | E8/E9 adversarial isolation and tenant scale; update/recovery/compatibility | Prior acceptance gates | High | Empirical future multi-library contribution |

No phase is “done” because a library field exists. Gate each by direct API scope tests plus runtime mapping/source assertions in a temporary environment. Preserve the current user/record history and publish old catalogue behavior as an explicitly named legacy public context during migration, not an implicit fallback for unknown libraries.

## Paper narrative choices

| Story | Fit today | Decision |
|---|---|---|
| A Semantic Library Search | Strong implemented mechanics, proxy historical evidence | Viable narrow focus after independent IR/ANN experiments |
| B Intelligent Digital Library with RAG | Strong integration and evidence heuristics | Recommended primary story if QA/gates evaluated |
| C Unified Library and Document Retrieval | Shared QA interface, distinct stores/indexes | Describe workflow integration; do not claim one unified cross-corpus ranking |
| D Hybrid Intelligent Library Platform | Optional lexical path plus recommendations/assistant | Use only with exact runtime flags and ablations; avoid a feature-list paper |
| E Multi-Library Semantic Retrieval | Current isolated pipeline absent | Future work/extensibility; primary paper only after 21–23 implementation/E8/E9 |
