# LuminaR Batch 02 / Prompt C — Global Semantic Search

**Result** PASS. **Production qualification** NOT_QUALIFIED.

## Checkpoint

The starting tree was the current working tree at `606f0dfce3970bea8e6fc2b62d243433d1a66b8a`, including uncommitted Batch 00 and Part 2Q work. The preflight stores Git status and 1,718 raw file fingerprints. All five Batch 00 source/test hashes matched its completion report before edits. The starting accepted totals were 3,162 backend passed, 20 skipped, 1,032 frontend passed, successful build and lint with 16 warnings, and 75 protected-contract tests passed.

The October 31 Part 02 research evidence was reconciled with current code. The full earlier Prompt C instruction text was unavailable in the local attachments. The latest continuation supplied the task scope and constraints. Historical observations remain separate from these results.

## C1 — Structured lexical-provider failures

`search/query_execution.py:GlobalQuerySearch.search` directly called the optional provider from exact title, title/author exact and fuzzy, and explicit author branches. A provider read exception escaped into the HTTP handler and became a generic 500, even though canonical metadata was available. Before the change, all four injected SQLite-error cases returned 500. The existing semantic optional merge and default empty-provider behavior already had separate fallback logic.

The structured branches now fall back to their existing bounded canonical metadata lookup on lexical I/O or SQLite failures. A failed title/author sequence discards any partial sidecar IDs and tentative spelling corrections. The original exact/title/author predicates, canonical hydration, bounds, and result sorting are retained. An HTTP authorization denial still propagates. The author expansion probe now handles only a Mongo execution timeout locally. Other canonical-provider exceptions propagate to the existing HTTP error boundary. The change makes no promise that canonical metadata is available or that fuzzy matches can be recovered from an unavailable sidecar.

**Measured after.** All four cases returned 200 with only the matching fixture work. The tests included a nonmatching candidate and asserted that semantic search was never called. The separate HTTP 403 control reached neither canonical retrieval nor semantic fallback before or after. These are production-handler tests with controlled provider faults and catalogue rows. No resident endpoint failure or performance improvement was measured.

## C2 — Global endpoint scope and unsupported MACHINE constraints

`search/api.py:search` previously dispatched a caller-supplied MACHINE library ID to `search/ranked_pages.py:RankedSearchPages.search`. That code hydrates a legacy inventory view. Its pool and availability path do not establish canonical tenant membership. The HUMAN global route silently ignored arbitrary library IDs. MACHINE also silently dropped HUMAN-only fields such as explicit minimum rating and format.

The global HTTP boundary now rejects scoped MACHINE requests and non-placeholder HUMAN library IDs with a generic 422 before retrieval or history. Tenant callers use the existing membership-checked library catalogue endpoint. Existing Global HUMAN clients that send the historical `LIB001` placeholder are kept compatible. That placeholder does not represent authoritative physical stock in the global HUMAN contract. MACHINE retains the global ranked-page API with supported category and author filters and rejects meaningful nondefault HUMAN-only controls.

**Measured before and after.** Five controlled requests moved from HTTP 200 and dispatch to HTTP 422 with zero calls to either search handler. The inputs were a MACHINE tenant UUID, MACHINE LIB001 with physical availability, HUMAN tenant UUID, MACHINE explicit rating minimum of zero, and MACHINE online format. The compatibility controls passed before and after for unscoped MACHINE with category/author and the existing HUMAN placeholder request. The test shows unsafe dispatch and ignored constraints on the old route, rather than a measured live disclosure. Direct offline engine and ranked-page library options were left intact.

## Strict constraints, fallback and Assistant

- HUMAN strict rating boundaries, missing values, explicit exclusions, and unsupported or contradictory capability requests were covered by the deterministic and contract suites. Beginner wording reaches the existing rerank query as a preference. No corpus reading-level or length guarantee is implied. The ranking implementation and model paths are unchanged.
- Existing tenant tests cover missing, building, failed and stale indexes, canonical visibility changes, foreign IDs, private-library outsiders, and revocation. The fallback reads through the tenant-authorized catalogue context and emits `LIBRARY_LOCAL`. The HTTP repair closes a different legacy global endpoint path. No tenant fallback code was edited.
- Before editing Search, eight Part 2Q Assistant cases verified verbatim topical query forwarding. The Search adapter uses the default unscoped HUMAN endpoint and disables history. Recommendation's internal MACHINE call is unscoped. These checks establish the integration contract. Native topical relevance and live Qwen behavior were outside this run.

## Results

| Check | Actual result |
|---|---|
| Full backend, 38 groups | 3,173 passed / 0 failed / 20 skipped |
| Full frontend | 1,032 passed / 0 failed / 0 skipped |
| Production build | PASS |
| Lint | PASS, 16 warnings |
| Protected contracts | 75 passed / 0 failed / 0 skipped |
| Targeted Search | 85 passed / 0 failed / 0 skipped |
| Strict/soft constraints | 114 passed / 0 failed / 0 skipped |
| Tenant Search and isolation | 52 passed / 0 failed / 0 skipped |

## Exact changes

- `search/api.py` from `64fb09aec0c6ddc8cc4540a96f29fd93d70ffdf5817546b885c3d3a0415fd99f` to `13358ddf7e227935a20765ddfbf899678b462bf2d940e6d23fd0d9eb2ab9ea32`.
- `search/query_execution.py` from `b4d8a74569dafbae12e3d68561533129265e5b66285d4a7cc2a0c130cc248111` to `c787704a57fec0129c115c2a1e31c48277419c5ec09a11d632095e113e1e1ceb`.
- `tests/test_lexical_api_fallback.py` from `2cb13be4170d61358795d8b613258452bf428668c4d22f8216004f67170ecd43` to `d2895662e486aa0fd44eb2c9985f1bd2b036a772d14094278795f0f953da397c`.

No model changes, global ranking changes, HNSW/KG rebuilds, protected RAG edits, resident restarts, production auth activation, telemetry enablement, deployment or commit. Post-run preservation compares source hashes including Batch 00, global pointers, protected RAG, and read-only artifact and database observations against the recorded checkpoint.

## Evidence files

- [Starting working-tree hashes](research_batch02_c_preflight.json)
- [Before repair, original failure results](research_batch02_c_before.xml)
- [After repair, targeted results](research_batch02_c_targeted.xml)
- [Constraint results](research_batch02_c_constraints.xml)
- [Tenant Search and isolation results](research_batch02_c_tenant.xml)
- [Assistant preflight](research_batch02_c_assistant_before.log)
- [Full backend group results](institution_v2q_research_batch02_c_backend.json)
- [Full frontend, build and lint](institution_v2q_research_batch02_c_front_frontend.json)
- [Source hashes and preservation](research_batch02_c_preservation.json)
- [Disposable regression cleanup](research_batch02_c_backend_isolation.json)
