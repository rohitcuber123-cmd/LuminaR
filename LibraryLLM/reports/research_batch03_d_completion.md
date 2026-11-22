# LuminaR Batch 03 / Prompt D — Tenant Search

**Disposition** PASS in the tested development scope. **Production** NOT_QUALIFIED.

## Baseline and scope

Current working-tree hashes were recorded for 1,718 paths. HEAD was `606f0dfce3970bea8e6fc2b62d243433d1a66b8a`. The October 31 Part 03 files were read as historical source observations. The baseline includes the Prompt A lifecycle, listener and authenticated-Mongo work, Prompt C Search guards, and Part 2Q recommendation and Assistant fixes. All were verified at preflight. The latest completed baseline was Prompt C with 3,173 backend passes, 20 skips, and 1,032 frontend passes.

The fixture runs used owned loopback Mongo instances and owned temporary artifacts. Public and private A/B libraries and authority fixtures used the current membership and invitation proof code. No resident service was restarted. The native pilot loaded locally cached all-MiniLM-L6-v2 and ms-marco-MiniLM-L-6-v2 on CPU with two Torch threads on an AMD Ryzen 7 260 (8 cores, 16 logical processors). It built a new five-work synthetic tenant generation in each isolated phase. Tenant HNSW used 384 dimensions, M=16, efConstruction=80 and efSearch=64. The global engine uses a different runtime efSearch and was outside these tests. No model download or existing-generation rebuild was performed.

## B03-01 — CONFIRMED DEFECT for filler words, EXPECTED DESIGN BOUNDS for conceptual recall and cap

The active tenant route calls `search/query_execution.py:_tenant_search`. Before the change, local fallback required every normalized topic token to be a substring of eligible title, author, subject or description text. One ordinary filler phrase hid an owned eligible match in NOT_BUILT, STALE, FAILED and RECOVERY_REQUIRED. All four fixture cases went from empty to the one canonical owned result. A foreign-library book with matching metadata was excluded.

Fallback now prefers the existing literal result set. If that set is empty, it can drop a small fixed set of English filler words while requiring every remaining content token. Hard predicates are applied before this step. Zero content tokens cannot activate relaxation. No synonym expansion, abbreviation dictionary, global filler or new ranking was introduced. Wrong content, wrong author and all-filler negative controls remained empty.

In the five-work pilot, both the unbuilt and READY conditions received the same six synthetic queries. The planner routed one positive query to structured metadata in both conditions and found its designated work. Four other positive queries each had one designated relevant work and exercised the fallback or native branch. The zero-relevance query was evaluated separately.

| Mode | Before, hit/recall at 3 over four branch-specific positive queries | After | Zero-relevance query before/after |
|---|---:|---:|---|
| Tenant-local fallback | 1/4 | 2/4 | 0/0 returned |
| MiniLM HNSW and CrossEncoder | 4/4 | 4/4 | 3/3 returned |

The filler-word query accounts for the improvement. The walking-difficulty paraphrase and `dbms` still missed in lexical fallback. This is the limit of the current bounded metadata approach. The native path returns candidates for unrelated queries because it has no relevance-abstention guarantee. These are authored synthetic judgments, with no independent reviewer or population inference.

## B03-02 — CONFIRMED DEFECT in optional reranking and cache-layer authority handling

The reranker call and score validation ran after the retrieval recovery boundary. RuntimeError, TimeoutError and nested score shape escaped, and a nonfinite score produced 503. All four now return the already validated, canonically hydrated tenant-native candidate set using the existing pre-rerank order. The public source remains `LIBRARY_LOCAL` and `TENANT_SEMANTIC`, with `ranking_degraded=true`. The reranker flag is false. No new ranking model, threshold, global route or publication write was added.

A cache-layer 403 also formerly triggered local fallback because every HTTPException in the native retrieval block was treated as recoverable. The boundary now distinguishes an unavailable native stage or the explicit corrupt-artifact contract from authorization failures. Injected cache, reranker and hydration 403s propagated. Real disposable missing-index and invalid-manifest cases returned only current local metadata under RECOVERY_REQUIRED and preserved the generation pointer. A source change during encoding discarded the native candidates and returned fresh local metadata. Revocation during encoding produced 404 before hydration or reranking.

A concurrent source change can cause this response to use local fallback while the status field still reflects the initial target observation. A subsequent target observation reported STALE. The request's `search_source` identifies the branch actually used.

## Freshness, roles and recommendation preservation

The native pilot observed READY before edits and STALE on the first status read after the title change. Author, subject and global-enrichment description edits changed the source fingerprint. Fresh local-only acquisition was searchable immediately in local fallback and withdrawal removed it. The original pointer remained fixed throughout. The timestamps describe fixture observations and do not establish event-driven freshness or an upper bound on detection lag. Linked-book enrichment used a synthetic global record in the disposable database.

The role and tenancy tests covered owner and ADMIN build authority, librarian staff reads, patron and private-code context, wrong UUID, forged and foreign identifiers, artifact traversal, outsider, revoked and platform-only denials. The mid-encoding revocation test exercised the second authority check. Overlapping recommendation and stale Assistant conversation cases exercise library switching independently of the request's fixed tenant UUID. No LLM was used to authorize any operation. The Part 2Q recommendation path retains GLOBAL_INTERSECTION_AND_LOCAL_DISCOVERY and canonical intersection. Assistant local borrowing and For You regression coverage was rerun.

## Resource observations

The five-work pilot has one query run per mode and phase. It includes file, database and model work, with separate encoder, reranker and hydration timings in the raw records. Model weights were already cached on disk. Each phase loaded fresh model instances, and subsequent queries within each phase reused its model and index cache. These were not isolated load tests. No latency improvement or p95 is claimed.

| Five-work timing, descriptive median | Before ms | After ms |
|---|---:|---:|
| Full native query | 170.053 | 218.457 |
| Encoder, native invocations | 17.814 | 19.398 |
| CrossEncoder, native invocations | 58.545 | 65.891 |
| Hydration, native queries | 24.383 | 34.971 |
| Full fallback query | 79.242 | 107.472 |
| Hydration, fallback queries | 26.829 | 41.981 |

The single-query fallback runs at 1/5/20/100/1,000 eligible staff-visible records hydrated exactly that many candidates. The size trial cloned synthetic metadata and exercised staff catalogue hydration. It does not model the distribution or holdings of a real collection. At 1,001 eligible records it still hydrated 1,000. One candidate was outside the cap, with no claim about which record is omitted in general. The 1,000-row runs took about 1.65 s before and 2.35 s after in different run conditions. This comparison is confounded by host load and single repeats. Raw stage timings are retained. The Search candidate bound is separate from existing source/status fingerprint and catalogue count operations.

## Regression and preservation

| Check | Actual result |
|---|---|
| Full backend, 38 groups | 3,191 passed / 0 failed / 20 skipped |
| Full frontend | 1,032 passed / 0 failed / 0 skipped |
| Production build | PASS |
| Lint | PASS, 16 warnings |
| Protected contracts | 75 passed / 0 failed / 0 skipped |
| Targeted tenant tests | 152 passed / 0 failed / 0 skipped |
| Tenant session and concurrent authority | 20 passed / 0 failed / 0 skipped |
| Part 2Q borrowing, Assistant and recommendation | 67 passed / 0 failed / 0 skipped |

All seven accepted fixture runners recorded stopping the owned Mongo process and removing the temporary root.

- `search/query_execution.py` from `c787704a57fec0129c115c2a1e31c48277419c5ec09a11d632095e113e1e1ceb` to `7f503b8193b114b28dbcd9a2c532e91459473695c7b473b38199b7127c9529eb`.
- `tests/institution_v2g/test_search_runtime.py` from `3da53861ff6d6e7eb6f04e665a599a71a4920802df54a30aebb5046fd6699568` to `9a334c7e387c7b5e23d70ca3587b16eab7e374447f7264e4dc05c55d794411ef`.

Only the tenant branch of `search/query_execution.py` and tenant tests changed. The Prompt C global branch remains intact. Global ranking, HNSW/KG, prior tenant generations, protected RAG, recommendations, Assistant and Batch 00 sources were preserved. No automatic builds, production cutover, telemetry activation, deployment or commit.

## Evidence

- [Current working-tree preflight](research_batch03_d_preflight.json)
- [Before repair, targeted failures](research_batch03_d_before.xml)
- [After repair, targeted tenant tests](research_batch03_d_targeted.xml)
- [Tenant session and concurrent authority](research_batch03_d_authority.xml)
- [Part 2Q recommendation and Assistant regression](research_batch03_d_q4.xml)
- [Real-model synthetic pilot before](research_batch03_d_native_before.json)
- [Real-model synthetic pilot after](research_batch03_d_native_after.json)
- [Full backend](institution_v2q_research_batch03_d_backend.json)
- [Full frontend, build and lint](institution_v2q_research_batch03_d_front_frontend.json)
- [Exact changes and hashes](research_batch03_d_preservation.json)

The first native pilot invocation stopped during setup because a synthetic linked-book submission lacked a required subject. The accepted baseline rerun supplied the required field on creation, cleared the fixture fields to exercise enrichment, and used the frozen preflight Search source with its hash verified. Both native pilot phases completed on owned fixtures.
