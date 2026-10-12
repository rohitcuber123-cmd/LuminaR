# Full convergence result A–AO

| Field | Requested result | Outcome |
| --- | --- | --- |
| A | FINAL | PARTIAL: automated/source convergence complete; real-browser/visual/responsive gates not verified. |
| B | ROUTES AUDITED | 78 before / 79 after; full_route_inventory.md |
| C | FRONTEND COMPONENTS AUDITED | 82 before / 85 after page/component modules; 128 total TS modules |
| D | BACKEND FEATURE PATHS AUDITED | 190 HTTP declarations / 192 Python modules |
| E | DUPLICATES FOUND | 9 overlapping implementation clusters; decisions in frontend_duplicate_removal.md |
| F | DUPLICATES MERGED | All 9 clusters use canonical shared composition/helpers |
| G | DUPLICATES REMOVED | 8 obsolete files; dead direct Borrow handlers/duplicate markup/filter state removed in retained files |
| H | DUPLICATES RETAINED / WHY | Typed route/API adapters, distinct source/authority contracts, supplemental graph/Assistant cards, historic read-only data, pure compatibility/research utilities; explicitly classified |
| I | LOST FEATURES | Local saved/AI/more-actions, description/metadata/detail design; global server category filtering and View All mode/context |
| J | RESTORED | Common detail/cards/catalogue/chips/paging/personal actions and explicit return context |
| K | CONTEXT-SPECIFIC | Tenant stock/lending/reservations/fees/status; global HNSW/KG/assets/events; private account tools; local-only AI unsupported |
| L | BOOK DETAIL | Shared BookDetailView; canonical tenant facts/actions injected; visual/browser pending |
| M | READING LIST | One personal service/store; linked dedup; local-only namespaced save with revocation masking and owner deletion |
| N | SELECT FOR AI | One OL identity/store/counter in both linked contexts; local-only limitation explicit |
| O | CATALOG / BROWSE | Shared CatalogueSurface/grid/filter/search/paging; distinct authoritative adapters |
| P | CATEGORY / SUBJECT | Actual global facets and tenant counted subjects; filters before paging; scoped URL |
| Q | SEARCH | Shared display; global semantic pool50/page10; local lexical isolation; runtime Search health STALE |
| R | HOME | Accepted composition retained; shared cards/actions/View All; automated parity passes |
| S | RECOMMENDATIONS | Unchanged ranking; bounded tenant ownership intersection; no global filler |
| T | CONTEXT GRAPH | navigation_context_graph.md; explicit URL beats stale state; global resets remain explicit |
| U | PERSONAL PAGE CONTEXT | patron_library return metadata preserved across Saved/Profile/invitations/library discovery/Know More/Graph/events/reader/Assistant links |
| V | STORE / CACHE | One selected store and saved store; account/token guards; distinct membership/authority/private caches retained |
| W | BACKEND DUPLICATE REVIEW | Global/tenant/personal/read-only classified; canonical Part 2B/C only physical writers; old writes 410 |
| X | CSS | product.css and mature tokens/composition; old LibraryCatalogue.css removed after caller audit |
| Y | DEAD CODE | 8 files removed; unreachable mutations and unused state removed; retained compatibility documented |
| Z | GLOBAL VALIDATION | Automated suites and HTTP catalogue passed; 5M count preserved; authenticated browser Search not verified |
| AA | TEST LIBRARY VALIDATION | 150 ACTIVE records + 150 holdings exact baseline match; scoped API/feature fixture suites pass; production browser flow pending |
| AB | MOBILE / RESPONSIVE | NOT_VERIFIED at all six required viewports; source responsive controls implemented |
| AC | ACCESSIBILITY | JSDOM axe/keyboard semantics pass; rendered contrast/focus/touch/browser not verified |
| AD | PERFORMANCE / N+1 | Bounded batch availability/metadata; 1-second filtered-count budget; unknown totals truthful; no full load benchmark claim |
| AE | BACKEND TESTS | 1597 unique passed, 10 existing skipped, 0 failures; raw XML/log evidence retained |
| AF | FRONTEND TESTS | 637 passed, 0 failed; includes matrix-generated tests |
| AG | BROWSER WALKTHROUGH | NOT_VERIFIED: approved IAB tabs stuck on connection-error/internal pages; no fabricated evidence |
| AH | REGRESSION | Frozen authority/auth/institution/workspace/Assistant/Search/KG/RAG/document/knowledge/events/notifications wall passed; Router research excluded |
| AI | BUILD / LINT | Build PASS; lint exit 0 / 14 retained warnings / 0 new warning signatures |
| AJ | EXACT FILES CHANGED | Full absolute paths below and full_product_change_manifest.md/json; baseline comparison preserves preexisting dirty work |
| AK | EXACT FILES DELETED | 8 absolute paths below |
| AL | REPORTS CREATED | All 21 required reports present; extra inventories, XML/logs, preservation/runtime/manifest evidence retained |
| AM | REMAINING ISSUES | Browser/visual gates; Search STALE baseline; local-only AI unsupported; unknown filtered totals; retained lint/bundle warnings |
| AN | IMPROVEMENT REVIEW | Severity/disposition/evidence in full_product_convergence_improvement_review.md |
| AO | NEXT PHASE | Complete current browser/visual acceptance first. No new tenancy/index/model phase started. |


## Major feature parity

| Feature | Global | Library | Shared? | Parity? | Notes |
| --- | --- | --- | --- | --- | --- |
| Home | YES | YES | YES | YES | Existing accepted shared composition; audit every rail action. |
| LUMINAR logo | YES | YES | YES | YES | Explicit patron URL, including return context on personal pages; global / remains global. |
| Catalog / Browse Books | YES | YES | YES | YES | Retain mature global composition with tenant data adapter. |
| Header / catalogue Search | PARTIAL | YES | YES | NO | Global semantic search and scoped local lexical search remain intentionally distinct. Runtime index STALE/baseline_verified=false with 5M vectors and no pending updates; no rebuild. Authenticated browser search pending. |
| Book Detail | YES | YES | YES | YES | One BookDetailView; new authoritative tenant facts and commands. |
| Book cards | YES | YES | YES | YES | One BookCard with grid/rail variants; wrappers only adapt data. |
| Categories / subject chips | YES | YES | YES | YES | Shared CategoryChips; actual local subjects/counts and global subjects stay scoped. |
| Pagination | YES | YES | YES | YES | One accessible control; URL state and data-specific cursor/offset. |
| New Arrivals | YES | YES | YES | YES | Arrival cards retain personal actions and canonical owned physical actions. |
| Popular | YES | YES | YES | YES | Shared cards; tenant truth never filled from unrelated global popularity. |
| For You / recommendations | YES | YES | YES | YES | Algorithm unchanged; expose shared personal actions and scoped owned books. |
| Reading List / bookmark / saved books | YES | YES | YES | YES | Bookmark is navigation to the same personal list, not a second saved concept. |
| Saved linked local book | YES | YES | YES | YES | Same user/work identity prevents duplicate saved entries. |
| Saved local-only book | NO | YES | NO | YES | Extend existing personal service with a namespaced local target; validate active patron membership. |
| Select for AI linked work | YES | YES | YES | YES | Use actual global_work_id; never use local record UUID as an OpenLibrary work. |
| Select for AI local-only | NO | NO | NO | YES | Intentionally unsupported: Assistant accepts OL work IDs and global metadata. Local-only UUID is not fabricated as an OL identity. Detail explains limitation; personal saving works. |
| Selected-book counter | YES | YES | YES | YES | Shared store and canonical work identity synchronize count everywhere. |
| Ask LuminaR | YES | YES | YES | YES | Keep existing router, selected-context binding, confirmations and scoped commands. |
| Know More / Book RAG | YES | YES | NO | YES | Preserve explicit return context; library physical loans do not create new digital entitlement. |
| Graph Lab | YES | YES | NO | YES | Global graph; preserve return context on linked-book navigation; no tenant KG. |
| Borrow Request | NO | YES | NO | YES | Only library-owned circulating requestable stock; global direct Borrow stays retired. |
| Return Request | NO | YES | NO | YES | Active loan until staff confirms physical receipt. |
| Renewal | NO | YES | NO | YES | Accepted canonical renewal semantics remain intact. |
| Reservations / waitlist | NO | YES | NO | YES | No obsolete global writer is reopened. |
| Fees | NO | YES | NO | YES | Existing audited fees and staff settlement, no new payment processing. |
| Loan / activity history | YES | YES | NO | YES | Personal legacy history explicitly separate from tenant activity. |
| Notifications bell | YES | YES | YES | YES | Accepted global notifications only; tenancy is excluded. |
| Events | YES | YES | YES | YES | Global feature; platform management guard; tenancy excluded. |
| Profile / account | YES | YES | YES | YES | Keep explicit return context on personal links. |
| My Libraries | YES | YES | YES | YES | Group by actual memberships; never choose first of several. |
| Mobile navigation / layout | PARTIAL | PARTIAL | YES | NO | Same responsive compositions; verify six viewports. Real-browser six-viewport/focus/contrast/history/reload validation NOT_VERIFIED. |
| Accessibility / keyboard / focus | PARTIAL | PARTIAL | YES | NO | Use real buttons, pressed states, labels, headings, visible focus and keyboard-accessible actions. Real-browser six-viewport/focus/contrast/history/reload validation NOT_VERIFIED. |
| Staff Workspace | YES | YES | NO | YES | Library ADMIN/LIBRARIAN only; no global role authority. |
| Platform Console | YES | YES | NO | YES | Explicit PlatformRoleAssignment; membership required for library internals. |
| Document RAG / Knowledge Tools / private cache | YES | YES | YES | YES | Accepted privacy/entitlement and existing models untouched. |
| Read Now / digital entitlement | YES | YES | NO | YES | Legacy active issue required; no direct Borrow after retirement. |

## Exact changed

- `D:/SDC/LibraryLLM/assistant/orchestrator.py`
- `D:/SDC/LibraryLLM/backend/routes/books.py`
- `D:/SDC/LibraryLLM/backend/routes/reading_list.py`
- `D:/SDC/LibraryLLM/backend/services/availability_service.py`
- `D:/SDC/LibraryLLM/backend/services/book_service.py`
- `D:/SDC/LibraryLLM/backend/services/library_catalogue_experience.py`
- `D:/SDC/LibraryLLM/backend/services/reading_list_service.py`
- `D:/SDC/LibraryLLM/frontend/package.json`
- `D:/SDC/LibraryLLM/frontend/src/App.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/AIChatWidget.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/AccountMenu.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/BookCapabilities.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/BookConnectionGraph.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/BookDiscoveryMenu.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/DiscoveryBookFrame.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/Footer.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/ForYou.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/Header.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/HomeCatalogueContext.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/LibraryCatalogueBook.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/MoreLikeThisSection.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/NewArrivals.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/PopularBooks.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/RelatedBookCard.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/assistant/AssistantTurn.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/events/EventUI.tsx`
- `D:/SDC/LibraryLLM/frontend/src/lib/api.ts`
- `D:/SDC/LibraryLLM/frontend/src/lib/libraryCatalogue.ts`
- `D:/SDC/LibraryLLM/frontend/src/pages/AccountPages.tsx`
- `D:/SDC/LibraryLLM/frontend/src/pages/BookDetailPage.tsx`
- `D:/SDC/LibraryLLM/frontend/src/pages/BookReaderPage.tsx`
- `D:/SDC/LibraryLLM/frontend/src/pages/CatalogPage.tsx`
- `D:/SDC/LibraryLLM/frontend/src/pages/EventDetailPage.tsx`
- `D:/SDC/LibraryLLM/frontend/src/pages/KnowledgeGraphPage.tsx`
- `D:/SDC/LibraryLLM/frontend/src/pages/LLMPage.tsx`
- `D:/SDC/LibraryLLM/frontend/src/pages/LibraryCatalogue.tsx`
- `D:/SDC/LibraryLLM/frontend/src/pages/ProfilePage.tsx`
- `D:/SDC/LibraryLLM/frontend/src/pages/ReadingListPage.tsx`
- `D:/SDC/LibraryLLM/frontend/src/pages/SearchPage.tsx`
- `D:/SDC/LibraryLLM/frontend/src/store/useAssistantStore.ts`
- `D:/SDC/LibraryLLM/frontend/src/store/useLibraryStore.ts`
- `D:/SDC/LibraryLLM/frontend/tests/kg-product.test.tsx`
- `D:/SDC/LibraryLLM/frontend/tests/library-catalogue.test.tsx`
- `D:/SDC/LibraryLLM/frontend/tests/search-depth.test.tsx`
- `D:/SDC/LibraryLLM/scripts/full_product_inventory.py`
- `D:/SDC/LibraryLLM/search/api.py`
- `D:/SDC/LibraryLLM/search/ranked_pages.py`
- `D:/SDC/LibraryLLM/tests/test_search_depth.py`

## Exact added

- `D:/SDC/LibraryLLM/frontend/src/components/BookCard.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/BookCoverArt.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/BookDetailView.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/BookPersonalActions.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/CatalogueBookActions.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/CatalogueSurface.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/GlobalCatalogue.tsx`
- `D:/SDC/LibraryLLM/frontend/src/components/ProductPagination.tsx`
- `D:/SDC/LibraryLLM/frontend/src/hooks/useProductContext.ts`
- `D:/SDC/LibraryLLM/frontend/src/lib/bookPresentation.ts`
- `D:/SDC/LibraryLLM/frontend/src/lib/productContext.ts`
- `D:/SDC/LibraryLLM/frontend/src/styles/product.css`
- `D:/SDC/LibraryLLM/frontend/tests/full-product-convergence.test.tsx`
- `D:/SDC/LibraryLLM/scripts/finalize_full_product_evidence.py`
- `D:/SDC/LibraryLLM/scripts/full_product_correct_baseline.py`
- `D:/SDC/LibraryLLM/scripts/full_product_inventory.cjs`
- `D:/SDC/LibraryLLM/scripts/full_product_rewrite_surfaces.py`
- `D:/SDC/LibraryLLM/scripts/report_full_product_convergence.py`
- `D:/SDC/LibraryLLM/scripts/test_full_product_frontend.py`
- `D:/SDC/LibraryLLM/scripts/test_full_product_regressions.py`
- `D:/SDC/LibraryLLM/scripts/write_full_product_reports.py`
- `D:/SDC/LibraryLLM/tests/library_catalogue_experience/test_full_product_convergence.py`

## Exact deleted

- `D:/SDC/LibraryLLM/frontend/src/components/LibraryWorkspaceRoute.tsx`
- `D:/SDC/LibraryLLM/frontend/src/data/categories.ts`
- `D:/SDC/LibraryLLM/frontend/src/hooks/useBookActionState.ts`
- `D:/SDC/LibraryLLM/frontend/src/pages/BookDetailPage.tsx.backup`
- `D:/SDC/LibraryLLM/frontend/src/pages/CatalogPage.tsx.backup`
- `D:/SDC/LibraryLLM/frontend/src/pages/CorePages.tsx`
- `D:/SDC/LibraryLLM/frontend/src/pages/LibrarianPlaceholder.tsx`
- `D:/SDC/LibraryLLM/frontend/src/pages/LibraryCatalogue.css`

## Exact phase tools

- `D:/SDC/LibraryLLM/scripts/full_product_inventory.py`
- `D:/SDC/LibraryLLM/scripts/full_product_inventory.cjs`
- `D:/SDC/LibraryLLM/scripts/full_product_correct_baseline.py`
- `D:/SDC/LibraryLLM/scripts/report_full_product_convergence.py`
- `D:/SDC/LibraryLLM/scripts/full_product_rewrite_surfaces.py`
- `D:/SDC/LibraryLLM/scripts/test_full_product_regressions.py`
- `D:/SDC/LibraryLLM/scripts/test_full_product_frontend.py`
- `D:/SDC/LibraryLLM/scripts/finalize_full_product_evidence.py`
- `D:/SDC/LibraryLLM/scripts/write_full_product_reports.py`

## Required reports

- `D:/SDC/LibraryLLM/reports/full_product_convergence_baseline.json`
- `D:/SDC/LibraryLLM/reports/full_route_inventory.md`
- `D:/SDC/LibraryLLM/reports/full_frontend_component_inventory.md`
- `D:/SDC/LibraryLLM/reports/full_backend_feature_inventory.md`
- `D:/SDC/LibraryLLM/reports/full_state_store_inventory.md`
- `D:/SDC/LibraryLLM/reports/full_css_inventory.md`
- `D:/SDC/LibraryLLM/reports/full_feature_parity_matrix.md`
- `D:/SDC/LibraryLLM/reports/full_feature_parity_matrix.json`
- `D:/SDC/LibraryLLM/reports/book_detail_convergence.md`
- `D:/SDC/LibraryLLM/reports/catalogue_browse_convergence.md`
- `D:/SDC/LibraryLLM/reports/reading_list_convergence.md`
- `D:/SDC/LibraryLLM/reports/select_for_ai_convergence.md`
- `D:/SDC/LibraryLLM/reports/search_convergence.md`
- `D:/SDC/LibraryLLM/reports/navigation_context_graph.md`
- `D:/SDC/LibraryLLM/reports/frontend_duplicate_removal.md`
- `D:/SDC/LibraryLLM/reports/backend_duplicate_review.md`
- `D:/SDC/LibraryLLM/reports/full_product_browser_walkthrough.json`
- `D:/SDC/LibraryLLM/reports/full_product_visual_parity.md`
- `D:/SDC/LibraryLLM/reports/full_product_regression.json`
- `D:/SDC/LibraryLLM/reports/full_product_convergence_improvement_review.md`
- `D:/SDC/LibraryLLM/reports/full_product_convergence_next_scope.md`
