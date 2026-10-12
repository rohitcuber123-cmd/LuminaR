# Full feature parity matrix

Initial source inspection is recorded separately from final validation. YES is a capability classification; runtime verification is recorded in test_coverage and regression/browser reports. Intentional unsupported capabilities are explicit.

| Feature | Global | Library | Shared? | Parity? | Duplicate? | Action / canonical | Notes |
|---|---|---|---|---|---|---|---|
| Home | YES | YES | YES | YES | NO | KEEP / Home + HomeCatalogueContext + shared cards | Existing accepted shared composition; audit every rail action. |
| LUMINAR logo | YES | YES | YES | YES | NO | MERGE / useProductContext / productHomePath | Explicit patron URL, including return context on personal pages; global / remains global. |
| Header navigation | YES | YES | YES | YES | NO | MERGE / Header + useProductContext | Same header family; data-specific destinations; account context should be explicit. |
| Patron library switcher | YES | YES | NO | YES | NO | KEEP / PatronLibraryShell / verified memberships | Only active GENERAL_USER memberships enter Patron mode; staff identities stay separate. |
| Catalog / Browse Books | YES | YES | YES | YES | NO | MERGE / GlobalCatalogue / LibraryCataloguePage + CatalogueSurface | Retain mature global composition with tenant data adapter. |
| Header / catalogue Search | PARTIAL | YES | YES | NO | NO | MERGE / CatalogueSurface + BookCard / distinct semantic and local data adapters | Global semantic search and scoped local lexical search remain intentionally distinct. Runtime index STALE/baseline_verified=false with 5M vectors and no pending updates; no rebuild. Authenticated browser search pending. |
| Search results | YES | YES | YES | YES | NO | MERGE / BookCard | Use the same BookCard and catalogue results family. |
| Book Detail | YES | YES | YES | YES | NO | MERGE / BookDetailView / BookDetailSkeleton | One BookDetailView; new authoritative tenant facts and commands. |
| Book cards | YES | YES | YES | YES | NO | MERGE / BookCard / DiscoveryBookFrame | One BookCard with grid/rail variants; wrappers only adapt data. |
| Book covers | YES | YES | YES | YES | NO | MERGE / BookCoverArt / BookCover | One cover renderer with safe remote URL and deterministic fallback. |
| Categories / subject chips | YES | YES | YES | YES | NO | MERGE / CategoryChips + actual facets | Shared CategoryChips; actual local subjects/counts and global subjects stay scoped. |
| Genre filtering | YES | YES | YES | YES | NO | REPLACE / CategoryChips + scoped URL | Global category filter must query all matching records, not only current page. |
| Author filtering | YES | YES | YES | YES | NO | MERGE / CatalogueFilters + backend query | Reusable filter field; backend-specific operations. |
| Circulation status filter | NO | YES | NO | YES | NO | KEEP / existing implementation with explicit context | Library-only holding status; no false global stock ownership. |
| Pagination | YES | YES | YES | YES | NO | MERGE / ProductPagination + URL state | One accessible control; URL state and data-specific cursor/offset. |
| New Arrivals | YES | YES | YES | YES | NO | MERGE / NewArrivals + BookCard | Arrival cards retain personal actions and canonical owned physical actions. |
| Popular | YES | YES | YES | YES | NO | MERGE / PopularBooks + BookCard / tenant signals | Shared cards; tenant truth never filled from unrelated global popularity. |
| For You / recommendations | YES | YES | YES | YES | NO | KEEP / ForYou + BookCard / unchanged ranker and tenant intersection | Algorithm unchanged; expose shared personal actions and scoped owned books. |
| View All | YES | YES | YES | YES | NO | REPLACE / homeCataloguePath + actual sort/view data | View All should render the requested arrival/popular/recommendation dataset. |
| Related books / More actions | YES | YES | YES | YES | NO | PORT / BookDiscoveryMenu / MoreLikeThisSection / return context | Global KG relationships reused for linked works; explicit global discoveries with return context. |
| Reading List / bookmark / saved books | YES | YES | YES | YES | NO | PORT / reading_list_service / useLibraryStore / ReadingListPage / BookPersonalActions | Bookmark is navigation to the same personal list, not a second saved concept. |
| Saved linked local book | YES | YES | YES | YES | NO | PORT / unique user_id + global work_id | Same user/work identity prevents duplicate saved entries. |
| Saved local-only book | NO | YES | NO | YES | NO | PORT / namespaced local target / same personal service | Extend existing personal service with a namespaced local target; validate active patron membership. |
| Select for AI linked work | YES | YES | YES | YES | NO | PORT / BookSelectButton / useAssistantStore | Use actual global_work_id; never use local record UUID as an OpenLibrary work. |
| Select for AI local-only | NO | NO | NO | YES | NO | KEEP / existing implementation with explicit context | Intentionally unsupported: Assistant accepts OL work IDs and global metadata. Local-only UUID is not fabricated as an OL identity. Detail explains limitation; personal saving works. |
| Selected-book counter | YES | YES | YES | YES | NO | PORT / AIChatWidget / one selected store | Shared store and canonical work identity synchronize count everywhere. |
| Ask LuminaR | YES | YES | YES | YES | NO | KEEP / existing_qwen / accepted Assistant / URL-bound lending context | Keep existing router, selected-context binding, confirmations and scoped commands. |
| Assistant page context | YES | YES | YES | YES | NO | PORT / useAssistantPageContext / linked global IDs | Bind global work IDs from tenant display metadata; local-only IDs omitted explicitly. |
| Know More / Book RAG | YES | YES | NO | YES | NO | KEEP / existing implementation with explicit context | Preserve explicit return context; library physical loans do not create new digital entitlement. |
| Graph Lab | YES | YES | NO | YES | NO | KEEP / existing implementation with explicit context | Global graph; preserve return context on linked-book navigation; no tenant KG. |
| My Library | NO | YES | NO | YES | NO | KEEP / existing implementation with explicit context | GENERAL_USER membership; canonical tenant loans and request states. |
| Borrow Request | NO | YES | NO | YES | NO | KEEP / existing implementation with explicit context | Only library-owned circulating requestable stock; global direct Borrow stays retired. |
| Cancel Borrow Request | NO | YES | NO | YES | NO | KEEP / existing implementation with explicit context | Idempotent cancellation; library-scoped identity. |
| Return Request | NO | YES | NO | YES | NO | KEEP / existing implementation with explicit context | Active loan until staff confirms physical receipt. |
| Renewal | NO | YES | NO | YES | NO | KEEP / existing implementation with explicit context | Accepted canonical renewal semantics remain intact. |
| Reservations / waitlist | NO | YES | NO | YES | NO | KEEP / existing implementation with explicit context | No obsolete global writer is reopened. |
| Fees | NO | YES | NO | YES | NO | KEEP / existing implementation with explicit context | Existing audited fees and staff settlement, no new payment processing. |
| Loan / activity history | YES | YES | NO | YES | NO | KEEP / existing implementation with explicit context | Personal legacy history explicitly separate from tenant activity. |
| Notifications bell | YES | YES | YES | YES | NO | KEEP / existing implementation with explicit context | Accepted global notifications only; tenancy is excluded. |
| Events | YES | YES | YES | YES | NO | KEEP / existing implementation with explicit context | Global feature; platform management guard; tenancy excluded. |
| Profile / account | YES | YES | YES | YES | NO | MERGE / AccountProfilePage / withPatronContext | Keep explicit return context on personal links. |
| My Libraries | YES | YES | YES | YES | NO | KEEP / existing implementation with explicit context | Group by actual memberships; never choose first of several. |
| Login redirect | YES | YES | YES | YES | NO | KEEP / existing implementation with explicit context | Normal authenticated route resolution; retain safe explicit target URL. |
| Logout / session isolation | YES | YES | YES | YES | NO | KEEP / session resets / scoped toasts | Personal and library state scoped to the current account/token. |
| Deep links | YES | YES | YES | YES | NO | KEEP / existing implementation with explicit context | URL context beats remembered selection. |
| Browser reload | PARTIAL | PARTIAL | YES | NO | NO | MERGE / existing implementation with explicit context | Canonical query filters and explicit return context survive reload. Real-browser six-viewport/focus/contrast/history/reload validation NOT_VERIFIED. |
| Browser Back / Forward | PARTIAL | PARTIAL | YES | NO | NO | MERGE / existing implementation with explicit context | Share URL-based filter state; no stale uncontrolled author/subject values. Real-browser six-viewport/focus/contrast/history/reload validation NOT_VERIFIED. |
| 404 / error / retry states | YES | YES | YES | YES | NO | MERGE / StatePanel / wildcard / retry | Use shared StatePanel and explicit 404 fallback. |
| Loading state | YES | YES | YES | YES | NO | MERGE / shared skeletons / keyed response guards | Reuse detail/grid skeletons; never expose stale tenant result while changing contexts. |
| Empty states | YES | YES | YES | YES | NO | MERGE / StatePanel / explicit Search all LuminaR | One state family; explicit Search all LuminaR, no silent result merging. |
| Mobile navigation / layout | PARTIAL | PARTIAL | YES | NO | NO | KEEP / existing implementation with explicit context | Same responsive compositions; verify six viewports. Real-browser six-viewport/focus/contrast/history/reload validation NOT_VERIFIED. |
| Accessibility / keyboard / focus | PARTIAL | PARTIAL | YES | NO | NO | MERGE / existing implementation with explicit context | Use real buttons, pressed states, labels, headings, visible focus and keyboard-accessible actions. Real-browser six-viewport/focus/contrast/history/reload validation NOT_VERIFIED. |
| API transport | YES | YES | YES | YES | NO | KEEP / existing implementation with explicit context | Thin service-specific wrappers are intentional; no duplicate auth/retry transport. |
| Auth / selected context / caches | YES | YES | YES | YES | NO | KEEP / distinct account-scoped stores / dead filter fields removed | Different concepts, no duplicate authoritative memberships or selection stores. |
| Inventory / import / copies | NO | YES | NO | YES | NO | KEEP / existing implementation with explicit context | Staff-only inventory; global catalogue is not tenant stock. |
| Staff Workspace | YES | YES | NO | YES | NO | KEEP / existing implementation with explicit context | Library ADMIN/LIBRARIAN only; no global role authority. |
| Platform Console | YES | YES | NO | YES | NO | KEEP / existing implementation with explicit context | Explicit PlatformRoleAssignment; membership required for library internals. |
| Legacy management URLs / writers | YES | YES | NO | YES | NO | COMPATIBILITY_ONLY / existing implementation with explicit context | Read-only old history and retirement paths stay; obsolete unused dashboard placeholder removed. |
| CSS / design system | YES | YES | YES | YES | NO | MERGE / product.css / mature composition / existing tokens | One product book family; remove only selectors with audited retired callers. |
| Document RAG / Knowledge Tools / private cache | YES | YES | YES | YES | NO | KEEP / existing implementation with explicit context | Accepted privacy/entitlement and existing models untouched. |
| Read Now / digital entitlement | YES | YES | NO | YES | NO | KEEP / BookCapabilities / protected BookReaderPage / no direct Borrow | Legacy active issue required; no direct Borrow after retirement. |
| More actions on book cards | YES | YES | YES | YES | NO | PORT / BookDiscoveryMenu | Shared related discovery navigation for a valid global work. |
| Format filtering | NO | NO | NO | YES | NO | REMOVE / Unsupported schema capability; misleading note/dead fields removed | No authoritative format fields in either source; unsupported both contexts. No fake filter or patron-facing implementation note. |
| Catalogue / HNSW / KG preservation | YES | YES | NO | YES | NO | KEEP / existing implementation with explicit context | Baseline and after evidence; no index/model build or global catalogue writes. |
