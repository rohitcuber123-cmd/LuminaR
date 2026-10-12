# Library Catalogue Experience V1

The selected patron library now owns the catalogue context. The existing global LuminaR catalogue remains separate and unchanged. The previous generic institution home and inventory-centric patron route are replaced by a real scoped home, rails, browse/search, arrivals, genres, Popular and details. Global marketing cover strips outside a library workspace remain outside this phase.

## Read path and source

`GET /libraries/{UUID}/catalogue/{source,home,books,genres,books/{UUID},global-books/{OL…W}}` authenticates current identity and checks a fresh scoped membership before any collection work. Patron content requires GENERAL_USER; the source summary also serves staff. ACTIVE meaningful metadata joined to a same-library holding determines the count. Zero stock is still a valid local owned record. Missing holdings and withdrawn metadata do not count. No has_dataset flag exists in production code.

The server owns source selection. React consumes the descriptor through one adapter; an empty filtered local result never causes fallback. Local cards use bounded tenant hydration. Empty libraries use the existing global catalogue endpoints and Search API, with global metadata normalized to non-owned discovery. The global-work detail resolver can return A's canonical local record while the same work in B returns global non-owned metadata.

## Canonical availability and actions

The existing pure Part 2B projection is shared by individual and bulk reads. Total stock minus pending holds, active loans, unavailable stock and unavailable copy conditions produces physical availability; reference/unavailable status and waiting-queue priority determine requestability. COPY mode keeps its verification/recovery checks. Noncanonical inventory snapshots are not lending truth: requestable count is null and commands are hidden. Canonical read maintenance remains inside the accepted durable lending gate.

Request, reserve, cancel request and cancel reservation call only accepted Part 2B/C commands, with stable idempotency keys across retry. The card needs matching active GENERAL_USER membership and canonical owned metadata. The backend remains authoritative. Global legacy quantity, LIB001 stock and source-provided forged action flags never create a physical button on global cards.

## Display and navigation

One DisplayBook model carries identity, metadata, source, owned state, optional shelf/accession/status/counts, personal request/reservation/loan states and actions. Local-only UUID records are normal. Safe cover URLs are optional; failures render a deterministic branded title/author cover. Home has actual library identity and counts, deterministic accession-ordered Featured rails, authoritative addition-ordered arrivals, current subjects/counts, recent activity Popular when present, and personal summary. Routes and header navigation stay scoped.

Abort and alive guards discard late work. The request key contains token, library ID, operation, filters and revision; the resolved source joins the returned cache identity. Data is hidden immediately when that identity changes. There is no persistent cross-library catalogue cache. Existing lending-state events refresh hydrated data.

## Performance and limits

Home selects at most 12 cards in each rail and hydrates a union of at most 36 books once. Browse uses 20 books per frontend page, 50 maximum on the API. Subjects are bounded separately. Holding joins and grouped allocation/queue queries replace per-card HTTP state calls. The database-call-count test covers 1 versus 10 cards. This is bounded round-trip evidence, not a production-scale scan benchmark. Counts, subjects and recent activity still aggregate matching tenant data. Existing global metadata enrichment is unchanged.

## Frozen integrations

The only lending-service change extracts the unchanged pure availability projection. Full 2B/2C regressions pass. Main mounts the new reader/indexes; App, Header and LibraryShells integrate it; the dead generic home export is removed. A supplementary KG test's obsolete global BORROW expectation is corrected to the accepted library-selection link; KG product code is untouched. All prior report hashes, protected global/AI source hashes, production collection counts and recorded artifact metadata pass preservation checks.

No tenant HNSW/KG worker, Build/Rebuild button, Events/Notifications tenancy, analytics, digital tenancy or private-vector routing is implemented.
