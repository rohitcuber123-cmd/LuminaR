# LuminaR Search V11 — implementation handoff and closure

**Decision: ADVANCED_SMART_FROZEN_STABLE_SEARCH_RETAINED.**

V11 integrates a usable development preview into the actual backend and catalogue
frontend. It is not a production release. Advanced interpretation remains below
the complex-query usability gates; no fresh acceptance population was consumed.
C4 and its existing EXACT path remain the default. No V12 or further major parser
research phase is scheduled. The project can proceed to polishing other features.

## What is active and what is frozen

Production preview is blocked in code, even if the preview flag and allowlist are
set. `search/smart_preview.py::preview_allowed` requires deployment mode
`development` or `test`, an explicit flag, an authenticated login session and an
operator allowlist. All switches default to production/off/no allowlist/no store.
`search/preview_api.py::configured_store` also refuses an in-memory production
store. No environment settings were activated in this execution.

The preview is available for explicit development review at
`/search?search_preview=1` or an existing library catalogue URL with that parameter.
The server must separately allow the account and configure a state store. A URL,
client boolean, library identifier or staff flag cannot grant access. Default
pages continue rendering their existing catalogue implementation.

The frozen V10 compiler and its v4 grammar dependency are pinned under
`scratch/search_architecture_v10/` and
`scratch/search_v2c_c5er/candidate_search_v4/`. They are an archived compiler
dependency, not a second retrieval engine. SMART imports them lazily; EXACT and
the default C4 path do not invoke the experimental compiler. Historical files
were not edited. `.gitattributes` preserves their byte hashes when versioned.

## Where the implementation lives

| Feature | Repository-relative implementation |
|---|---|
| Server gate, source normalization, capability precedence | `search/smart_preview.py::preview_allowed`, `compile_query` |
| Original/accepted source mapping and typed operands | `search/smart_preview.py::source_contract`; archived V10 QueryIntent/proof contracts |
| Native retrieval adapter, negative formats, bounded refill | `search/smart_preview.py::PreparedRuntime` |
| Accepted query, issued operations and source preservation | `search/preview_service.py::PreviewService` |
| Memory development double and injectable Mongo CAS | `search/preview_state.py::MemoryStateStore`, `MongoStateStore` |
| 500-character API and state-bound operations | `search/preview_api.py::PreviewRequest`, `install` |
| Registration in the actual Search API | `search/interaction_api.py::install`, called by `search/api.py` |
| Shared global/local execution | `search/query_execution.py::GlobalQuerySearch.search`, `_tenant_search`; optional `runtime` defaults to C4 |
| Capability registry | `search/smart_preview_capabilities.json` — `V11-native-capabilities-v3` |
| Feature discovery and frontend contracts | `frontend/src/lib/searchPreview.ts::useSearchPreviewGate` |
| Search bar, cards, decisions and refinements | `frontend/src/components/SearchPreview.tsx` |
| Global and tenant integration | `frontend/src/components/GlobalCatalogue.tsx`, `frontend/src/pages/LibraryCatalogue.tsx` |
| Search-specific styling | `frontend/src/styles/search-preview.css` |

The single new preview POST endpoint is `/query/preview` on the Search API
(`/search-api/query/preview` through the frontend proxy). It handles initial
searches and server-issued completion, Apply/Keep, add/remove filter and sort
operations. `/query/features` reports server permission and the frozen release
decision. This separate contract avoids changing C4 session semantics or widening
an old DTO while leaving its accepted-source handling incompatible.

## Supported behavior and security boundaries

SMART preserves ordinary topics and advisory text, combines explicit native
filters, and blocks unresolved or unsupported mandatory conditions. Explicit
registered category selections become filters; descriptive phrases such as
“fiction writing” remain topics. Supported equivalent field syntax is normalized
with original/accepted spans retained. Canonical spelling corrections require
Apply or Keep. Arbitrary narrative corrections are not qualified.

GLOBAL supports current rating predicates, author/title lookup, native sort and
online entitlement filtering. It does not support publication-year, language or
circulation filters. GLOBAL ONLINE means the actor's current readable borrowing
entitlement, not every ebook in the world. Institutional search supports native
year/language/format/availability fields where authoritative hydrated data exists.
Negative and ONLY-format predicates require known Boolean capability flags;
unknown flags are not treated as known absence.

Mandatory page count, commercial price, publisher and edition filters remain
unsupported. Unsupported capability takes precedence over a missing value, while
the missing state is retained. Missing supported author/rating/format/sort values
can be completed through issued source-bound choices. Strict title-only substring
and byte-exact quoted matching remain unsupported. EXACT retains normalized native
title/identifier semantics and never uses advanced interpretation.

Authorization uses the existing `interaction_api.authorized` and native
`catalogue.read_context` policy. Authority precedes facets/state access and is
checked again before committing the response. Actor, login session, library,
workspace, mode, feature/parser version, source/IR digests, accepted-plan version
and expiry bind state. The server issues operation IDs and source spans; no
client-proposed QueryPlan is accepted. A single CAS row replacement consumes old
operation IDs and publishes accepted source/plan together. Provider failure does
not consume a pending operation. Live Mongo durability is **not verified**.

Native execution derives global entitlements for positive and negative formats,
checks hydrated predicates and serialization, pushes authoritative local fields
before collection limits, and uses stable keyset refill up to 5,000 local rows.
The global ranked window remains 50, using the existing provider's metadata
filter/refill logic. Filters and sorting precede user pagination. Totals are
explicitly incomplete; the UI says “ranked search window.” Full recall is not
claimed. Unlinked institutional records never fall through to global discovery.
Linked metadata can still depend on global availability.

Existing MiniLM/vector/reranker interfaces, generation checks, book serialization,
cards, covers, detail/borrow actions, recommendations, More Like This and protected
RAG/document endpoints are reused. No models, weights, indexes, knowledge graph,
Qwen/RAG configuration, lending rules or adjacent pages were rebuilt.

## Validation and evidence

The authoritative final results and all requested QA fields are in
`reports/search_arch11_final_report.json`. The evidence index there references:

- `reports/search_arch11_broad_release_tests.xml`: reviewed archived regressions
  plus application/native/API tests; seven historical deselections remain explicit.
- `reports/search_arch11_application_qa_release.json`: exposed development replay
  through the actual ASGI endpoint, with mock authority and read-only collections.
- `reports/search_arch11_frontend_full.log`: complete existing frontend suite,
  including adjacent-feature tests; focused preview checks are separately retained.
- `reports/search_arch11_browser_qaverified.json`: actual Chromium routing/UI with
  intercepted fixture service data, desktop/mobile screenshots and focused axe.
- `reports/search_arch11_contract_review.json`: independent source-only normative
  review; no candidate predictions or fresh acceptance were inspected.
- `reports/search_arch11_source_manifest.json`: changed/new source hashes and
  preservation verification. V10 source/report hashes remain unchanged.

Tests use actual HTTP route/native execution code but mocked authorization/data.
Memory one-use and injected Mongo conditional-replace tests are not persisted
security, expiry/crash-recovery or staging qualification. A local root reachability
probe failed; current service/index health is not qualified. Native `/health` can
open SQLite in write mode, so it was not used under this execution's no-live-write
boundary. No real JWT credentials or independent book relevance judgments were
available for safe write-free integration. Relevance and full live API performance
are NOT QUALIFIED; the historical MiniLM 12-vector probe is not relabeled as a
production relevance test or warm embedding benchmark.

Useful maintenance commands (use a new tag for new report filenames):

```powershell
.\.venv\Scripts\python.exe scripts/search_arch11_regress.py maintenance20261029
.\.venv\Scripts\python.exe -m pytest tests/test_search_arch11_integration.py -q
cd frontend
npm test
npm run build
npm run lint
```

The exposed application replay can be reproduced with
`scripts/search_arch11_application_qa.py <unique-tag>`. It remains development
evidence. Do not generate a new independent population while known gates fail.

## Rollback and known limitations

Keep `LUMINAR_SMART_SEARCH_PREVIEW` unset/`0` and deployment mode production; leave
the preview state backend unconfigured. Remove `search_preview=1` from the page
URL or select “Use standard search.” C4 remains active without a database migration.
Three native rollback cases compare outputs to immutable commit
`822b667e092ba251537f0f3647348b7aa6ca641c`; frontend rollback is also browser-tested.
Do not delete source/evidence archives as a rollback procedure.

Advanced multi-field prose, reference/correction language and long requests still
miss valid execution frequently in exposed V8/V9 material. Raw hard-field masks
also disagree with the reviewed topical-category and derived-format policies;
raw scores are retained rather than cosmetically rescored. These limits prevent
independent acceptance and activation. The explicitly framed missing-format defect
found during V11 completion testing was blocked and repaired with source-owned
completion; that repair is development evidence, not proof of general language
coverage.

Any future operational staging review would need separate authorization for real
JWT/current membership, persisted CAS, authorized relevance judgments and live
service measurements. A possible operational target for that review is warm API
p95 ≤2 seconds at four simultaneous searches, with cold startup measured separately
and <1% unexpected provider failures. The 30-second UI cancellation and native provider limits do not establish a staged end-to-end deadline or durable reconnect recovery. This is a proposal, not an adopted SLO or a
threshold used to pass the mock timings.

**Final next action:** retain the frozen advanced preview and stable default search;
move to polishing LuminaR's other features. Search work is now maintenance, not
another major parser/model development cycle.
