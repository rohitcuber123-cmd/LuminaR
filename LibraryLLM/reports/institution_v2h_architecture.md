# Institution Part 2H architecture

The canonical Staff route is `/staff/libraries/:libraryId/intelligence`, nested in the existing Staff shell and membership route guard. One page contains independent Semantic Search Index and Knowledge Graph cards. No global or Platform build controls exist.

React → relative Core API → existing Part 2G durable job → Search service worker → private immutable generation → validation → atomic publication → fenced Mongo active pointer. The browser never invokes a script, subprocess or shell.

`LibraryIntelligencePage` is keyed by canonical route UUID and authentication token. Requests use the accepted tenant serialization helper, AbortController, sequence checks and an unmounted-session guard. A status response must match the requested UUID. Active QUEUED/RUNNING/VALIDATING/PUBLISHING jobs poll every three seconds; terminal states stop polling. Focus and explicit Refresh fetch authoritative status. React does not calculate staleness or own job state.

Exact fresh ADMIN membership requests builds. Librarians view status only. General Users and Platform-only users cannot enter this tenant operation. The public build API rejects empty catalogues and blocks starting over unresolved outcomes; worker snapshot rechecks prevent an emptied catalogue publishing meaningless artifacts. Internal legacy Part 2G empty-artifact serialization remains tested without creating a public empty build operation.

The status contract adds current eligible count, build permission, latest attempt, published generation verification, successful generation number and duration. Published pointer validity is separate from latest attempt state. A failed rebuild retains the previous pointer. Catalogue reader/ranking code remains frozen: reads follow the existing Part 2G safe local fallback during non-READY states. No unsupported promise of continuous semantic serving is made.

Existing mutation barriers, partial unique effective-active job index, heartbeat leases and publication/job fencing remain authoritative. Concurrency can briefly return the established retryable 503 barrier response; a retry resolves to the same effective job. Recovery UI requires existing explicit operator reconciliation and never blindly repeats an unknown publication.

Build audits reuse the canonical tenant audit collection and hydrated actor display. Deterministic per-job/outcome event UUIDs make audit writes idempotent. SEARCH_INDEX_BUILD_* and KG_BUILD_* events also appear in Operational Activity. No duplicate audit system is introduced.

Shared Staff cards, badges, buttons, native progress and the existing focus-trapping Modal are reused. Search parameters are read-only advanced details. Catalogue metadata artifacts remain separate from uploaded document content and RAG.
