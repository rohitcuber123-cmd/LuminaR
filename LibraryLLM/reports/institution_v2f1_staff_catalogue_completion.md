Current consolidated closure: [institution_v2f1_consolidated_completion.md](institution_v2f1_consolidated_completion.md). The evidence below records the earlier sub-phase.

# Institution Part 2F.1 — clickable titles and Staff catalogue correction

**FINAL PASS. All 24 additional gates (231–254) pass.**

Staff Catalog now opens `/staff/libraries/{libraryId}/catalogue`, reusing the accepted Browse Books cards, covers, filters and paging for the selected library. Inventory remains the separate management table. TEST shows 150 canonical local books. Staff cards/details preserve Staff mode and do not offer Patron Request/Waitlist actions. An explicit Browse Global Catalogue action retains global 5M discovery.

Inventory title links open the exact LibraryBookRecord via `library_book_id`. Shared Staff detail displays format, physical facts, current call number, stock/requestable counts and authorized online-resource state/visibility. Existing edit, stock and online-upload forms are reused. Live Chromium verified safe PDF reading, Linked Book navigation, online upload in the disposable review library, library switching and Inventory Back with filters/page 2. Keyboard focus, Enter activation and online-dialog focus trap/Escape/restore pass. All 18 catalogue/inventory/detail viewport cases pass.

Backend: **1958 unique tests pass**, with 10 existing security skips; final 14-case Staff catalogue rerun passes. Frontend: full **831-case** run passes, followed by the final **28-case** affected suite (833 distinct cases across runs). Build passes. Lint: 0 errors, 0 new warnings, 14 existing warnings.

TEST retains the same 150 ACTIVE record and 150 holding hashes. Global catalogue remains 5,000,000 estimated records; all 196 protected artifact and 156 protected source checks pass. Accepted cover palette, geometry and renderer files are unchanged. No Git commit was made.

## Required final fields

| Field | Result |
|---|---|
| STAFF_INVENTORY_TITLE_CLICKABLE | YES |
| STAFF_TITLE_DESTINATION | /staff/libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae/books/{library_book_id} |
| STAFF_TITLE_USES_LIBRARY_BOOK_ID | YES |
| STAFF_TITLE_PRESERVES_STAFF_CONTEXT | YES |
| STAFF_BOOK_DETAIL_FORMAT_VISIBLE | YES |
| STAFF_BOOK_DETAIL_ONLINE_ASSET_VISIBLE | YES |
| STAFF_BOOK_DETAIL_READ_ONLINE_WORKS | YES |
| DIGITAL_ASSET_LINKED_BOOK_CLICKABLE | YES |
| INVENTORY_BACK_STATE_PRESERVED | YES |
| STAFF_CATALOG_FINAL_ROUTE | /staff/libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae/catalogue |
| STAFF_CATALOG_IS_INVENTORY | NO |
| STAFF_CATALOG_IS_GLOBAL | NO |
| STAFF_CATALOG_SELECTED_LIBRARY | e6d1e5b4-c48f-4b47-b96a-656a676fb8ae / TEST |
| STAFF_CATALOG_VISIBLE_BOOK_COUNT | 150 |
| STAFF_CATALOG_REUSES_BROWSE_SURFACE | YES |
| STAFF_CATALOG_PATRON_REQUEST_ACTIONS_VISIBLE | NO |
| STAFF_CATALOG_BOOK_DETAIL_PRESERVES_STAFF_CONTEXT | YES |
| STAFF_INVENTORY_REMAINS_SEPARATE | YES |
| EXPLICIT_GLOBAL_CATALOG_ACTION_EXISTS | YES |

## Acceptance evidence

| Gate | Requirement | Result | Evidence |
|---|---|---|---|
| 231 | Staff Inventory book titles are clickable. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 232 | Staff title navigation uses canonical library_book_id. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 233 | Clicking Staff title preserves Staff context. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 234 | Staff title does not route ADMIN/LIBRARIAN into Patron mode. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 235 | Staff Book Detail displays Physical / Online / Physical + Online state. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 236 | Attached Online copies are visible from Staff Book Detail. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 237 | Staff can open/read an authorized Online copy from the book detail. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 238 | Staff can manage/add Online copy from the same book workflow. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 239 | Digital Asset Linked Book title links back to the correct Staff book. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 240 | Patron/global title links preserve their respective contexts. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 241 | Book-title links are keyboard/focus accessible. | PASS | [institution_v2f1_staff_catalogue_responsive.json](institution_v2f1_staff_catalogue_responsive.json) |
| 242 | Returning to Inventory preserves relevant search/filter/page state where practical. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 243 | Staff Catalog no longer routes to Inventory. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 244 | Staff Catalog no longer routes to global 5M catalogue. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 245 | Staff Catalog has its own Staff-scoped library catalogue route. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 246 | Staff Catalog uses the selected library's canonical records. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 247 | Staff Catalog visually reuses the accepted Browse Books/Catalogue experience. | PASS | [institution_v2f1_staff_catalogue_responsive.json](institution_v2f1_staff_catalogue_responsive.json) |
| 248 | Inventory remains a separate management destination. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 249 | Staff catalogue cards do not expose Patron Request/Waitlist actions. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 250 | Staff catalogue book navigation preserves Staff context. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 251 | Physical / Online / Physical + Online state is visible in Staff catalogue where appropriate. | PASS | [institution_v2f1_staff_catalogue_responsive.json](institution_v2f1_staff_catalogue_responsive.json) |
| 252 | Switching Staff library changes the browsed catalogue. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 253 | Explicit Browse Global Catalogue still provides access to the 5M dataset. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |
| 254 | Global and Patron catalogue routing remain unchanged. | PASS | [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json) |

## Files changed

- `backend/routes/library_catalogue_experience.py`
- `backend/services/library_catalogue_experience.py`
- `frontend/package.json`
- `frontend/src/App.tsx`
- `frontend/src/components/BookCard.tsx`
- `frontend/src/components/BookDetailView.tsx`
- `frontend/src/components/LibraryBookTitleLink.tsx`
- `frontend/src/components/LibraryShells.tsx`
- `frontend/src/components/StaffBookManagement.tsx`
- `frontend/src/components/WorkspaceRoute.tsx`
- `frontend/src/hooks/useLibraryCatalogue.ts`
- `frontend/src/lib/bookPresentation.ts`
- `frontend/src/lib/libraryCatalogue.ts`
- `frontend/src/lib/libraryReservationsFees.ts`
- `frontend/src/lib/libraryWorkspace.ts`
- `frontend/src/lib/productContext.ts`
- `frontend/src/pages/LibraryAnalyticsPage.tsx`
- `frontend/src/pages/LibraryAssets.tsx`
- `frontend/src/pages/LibraryCatalogue.tsx`
- `frontend/src/pages/LibraryCirculation.tsx`
- `frontend/src/pages/LibraryInventory.tsx`
- `frontend/src/pages/LibraryReservationsFees.tsx`
- `frontend/src/styles/product.css`
- `frontend/tests/institution-critical-closure.test.tsx`
- `frontend/tests/staff-catalogue-titles.test.tsx`
- `scripts/institution_v2f1_staff_catalogue_browser.py`
- `scripts/institution_v2f1_staff_catalogue_reports.py`
- `tests/library_catalogue_experience/test_staff_catalogue.py`

Regenerated full-suite XML/logs and viewport screenshots are evidence outputs, listed separately by their report prefix. No credentials are included. The original `institution_v2f1_staff_catalogue_backend.xml` and frontend log captured early fixture/assertion failures; authoritative final results are the full regression catalogue XML and `*_backend_final.xml` / `*_frontend_final.log`.

## Reports

- [institution_v2f1_staff_catalogue_architecture.md](institution_v2f1_staff_catalogue_architecture.md)
- [institution_v2f1_staff_catalogue_backend.log](institution_v2f1_staff_catalogue_backend.log)
- [institution_v2f1_staff_catalogue_backend.xml](institution_v2f1_staff_catalogue_backend.xml)
- [institution_v2f1_staff_catalogue_backend_final.log](institution_v2f1_staff_catalogue_backend_final.log)
- [institution_v2f1_staff_catalogue_backend_final.xml](institution_v2f1_staff_catalogue_backend_final.xml)
- [institution_v2f1_staff_catalogue_browser.json](institution_v2f1_staff_catalogue_browser.json)
- [institution_v2f1_staff_catalogue_build.log](institution_v2f1_staff_catalogue_build.log)
- [institution_v2f1_staff_catalogue_changed_files.json](institution_v2f1_staff_catalogue_changed_files.json)
- [institution_v2f1_staff_catalogue_completion.json](institution_v2f1_staff_catalogue_completion.json)
- [institution_v2f1_staff_catalogue_completion.md](institution_v2f1_staff_catalogue_completion.md)
- [institution_v2f1_staff_catalogue_frontend.log](institution_v2f1_staff_catalogue_frontend.log)
- [institution_v2f1_staff_catalogue_frontend_final.log](institution_v2f1_staff_catalogue_frontend_final.log)
- [institution_v2f1_staff_catalogue_lint.log](institution_v2f1_staff_catalogue_lint.log)
- [institution_v2f1_staff_catalogue_preservation.json](institution_v2f1_staff_catalogue_preservation.json)
- [institution_v2f1_staff_catalogue_regression.json](institution_v2f1_staff_catalogue_regression.json)
- [institution_v2f1_staff_catalogue_responsive.json](institution_v2f1_staff_catalogue_responsive.json)
- [institution_v2f1_staff_catalogue_routes.json](institution_v2f1_staff_catalogue_routes.json)
- [institution_v2f1_book_title_navigation_audit.md](institution_v2f1_book_title_navigation_audit.md)

## Limits and stop

- Library uploads support PDF only, as in the accepted phase.
- Global 5M preservation uses estimated_document_count; binary artifacts compare size/mtime, and TEST/source checks use hashes.
- Browser validation uses Chromium at the six requested viewports.
- Ten existing security skips and fourteen existing lint warnings remain; no failing tests or lint errors.
- The safe review library retains the newly created Staff-only QA attachment for manual review; TEST data is unchanged.
- Earlier critical report screenshots/routing decisions remain historical; this correction supersedes the Staff Catalog → Inventory decision.

**Accept the current Part 2F.1 correction. STOP before Part 2G and all further domain/index/build work.**
