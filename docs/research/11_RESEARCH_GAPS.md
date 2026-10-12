# Research gaps, weaknesses and technical debt

## P0: before submission

| Gap | Evidence / consequence | Required resolution |
|---|---|---|
| Independent current retrieval labels | `create_relevance_labels.py:34–68` assigns top 20% grade2, next 30% grade1 from teacher ranks regardless of absolute relevance | New independently judged query pool including irrelevant/ambiguous queries; frozen test set |
| Embedding truncation | Active 3000-character book/PDF chunks vs MiniLM 256-token window; historical artifact reports 3958/3959 truncated | Token-aware variants, re-embedding, source coverage and QA experiments |
| Unselected RAG entitlement gap | `book_access.authorize_selection` allows no selection; global retrieval uses all book assets | Explicit global full-text policy and authorized candidate scope; direct API tests |
| Availability inconsistency | `ranked_pages.py` filters stock using global book counts, while borrow prefers library_inventory | Reproduce mismatched counts; align authoritative availability before availability claims |
| Partial circulation commits | Stock decrement precedes issue insert; return CAS precedes fine/activity/stock | Fault recovery/idempotent side effects or supported DB transaction; failure fixtures |
| Scientific causal comparisons incomplete | Historical latency/teacher diagnostic artifacts do not establish current independent advantage | Freeze source/model/data/hardware, rerun controlled baselines, paired confidence intervals |
| Book-index publication generation | `embed.index_registered_book` replaces graph and metadata separately | Manifest-backed immutable bundle publication or explicit maintenance lock/recovery |
| Paper novelty unclear | All major model/index algorithms are established | One primary RQ and evaluated differentiating mechanism; restrained contribution statements |

## P1: important engineering/research improvements

Candidate union limits and heuristic evidence weights need ablation; aliasing `document_id/work_id` changes expansion behavior and needs contract consistency; context character budget does not measure prompt tokens; selected-book local chat does not send transcript; assistant conversations are process-local; librarian dashboards combine selected inventory with global circulation; numeric book IDs use max+1; reservations/fines have check-then-write identity windows; reading-list copied facts can age; direct imported popularity is not local engagement; query-history profile bias can repeatedly reinforce itself. Each weakness is a targeted experiment/fix, not a blanket declaration that the entire feature fails.

Lexical integration and its mutation worker are separate opt-in flags, both default false. Evaluate available snapshot/current generation and deployment settings before saying “hybrid production search”. Sidecar absent/corrupt fallback retains dense search, which is reasonable for public discovery; future private-library fallback must remain in the authorized scope.

Model paths default to cached aliases; Python packages are loosely specified; launchers and DuckDB/SQLite helpers use host-specific paths. Training scripts and candidate directories can be mistaken for active models. Add exact model revisions, source hashes, pinned environment, corpus checksums, seeds/thread counts, rights and generation manifests. The existing 5M manifest marks the legacy baseline unverified; do not treat its count as a revalidated current database.

## Future architecture gaps

Library registration/unique identity, membership/invitations, librarian assignment, scoped private catalogue data, versioned datasets, durable indexing jobs, scoped vector mapping/registry, source-isolated RAG, owned admin changes, event/notification provenance, scoped analytics, user switching and lifecycle deletion remain **PROPOSED**. `library_id` inventory work does not close these gaps. Details and dependencies: 21–23.

## Improvements ranked by value and effort

| Improvement | Research value | Effort | Risk | Dependency / expected benefit |
|---|---|---|---|---|
| Independent labels + test protocol | Very high | Medium | Low | Enables all comparative claims |
| Token-aware source chunking | High | Medium | Medium | Reindex compatible models; increase represented source coverage, measure benefit |
| Grounding/refusal calibration | High | Medium/high | Medium | Gold supported/unsupported corpus; exposes false refusal tradeoff |
| Evaluate existing reranker/lexical path | High | Low/medium | Low | Already implemented; determine contribution rather than recommending it as new |
| BM25+dense fusion + rerank | High | Medium | Medium | New baseline/index; useful exact/semantic tradeoff hypothesis |
| Metadata-aware/context/library filters | High | High | High | Authorized candidate scope and ownership model |
| Verified claim-level citations | High | Medium/high | Medium | Source-span links/entailment evaluation |
| Adaptive/token/section chunking | High | Medium | Medium | Stable offsets; compare fixed token baseline first |
| Query expansion ablation | Medium/high | Low | Low | Existing rule expansion; avoid invented facts/query drift |
| Learned recommender study | Medium | High | Medium | Real consented temporal interaction data; current heuristic baseline exists |
| Private-library partition/registry | High future systems value | High | High | Complete scoped CRUD/membership first; operational isolation plus scale study |
| Multilingual retrieval | Medium/high | High | Medium | New models/data/indices; MiniLM English default does not prove multilingual performance |
| OCR | Product-dependent | Medium | Medium | Scanned-document demand; document privacy/accuracy evaluation |

No application fixes were made. These are action proposals prioritized for research defensibility.
