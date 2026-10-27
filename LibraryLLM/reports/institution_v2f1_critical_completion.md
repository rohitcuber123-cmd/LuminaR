Current consolidated closure: [institution_v2f1_consolidated_completion.md](institution_v2f1_consolidated_completion.md). The evidence below records the earlier sub-phase.

<!-- current-staff-catalogue-correction -->
# Current Part 2F.1 closure — PASS

The latest Staff catalogue/title correction is complete. **Staff Catalog opens the selected-library browsing surface at `/staff/libraries/{libraryId}/catalogue`; Inventory remains separate.** [Current completion, gates 231–254 and required QA fields](institution_v2f1_staff_catalogue_completion.md). The previous routing decision below is superseded; its other accepted evidence remains historical.

---

# Earlier critical closure — historical evidence

**FINAL PASS. All 45 additional acceptance gates (186–230) pass.**

Staff Catalog now opens the canonical current-library inventory. Add Book uses Physical / Online / Physical + Online; format is derived from actual holdings and permitted READY assets. Online creates no fake holding. Existing-book attachment and Online → Add Physical Stock preserve identity/accession and use canonical operations.

The cover repair restores the original palette foreground and decorative geometry from `c449f54`, following the user reference. Title/author backplates and the first repair’s adaptive colour/duplicate text layers are removed. All generated surfaces use one renderer. The assistant launcher moves away from essential card controls while retaining its existing dialog and backend behavior. Library document Q&A uses its authorized library/asset endpoint, with the existing answer renderer and immediate denial cleanup.

Backend: **1944 unique passed**, 10 existing security skips. Frontend: **805 passed**; final launcher and inventory follow-ups pass 93 and 26 tests. Build passes; lint has 0 errors and 14 existing warnings. Live Chromium checks cover 120 surface/viewport cases (including 14 named details at six sizes), 1,225 rendered cover checks including repeated instances, 36 card/viewport cases, 18 native format-dialog cases, canonical format filters and scoped PDF reading/Q&A.

TEST remains 150 ACTIVE records and 150 holdings with the original hashes unchanged. Global catalogue remains 5,000,000 estimated records; all 196 protected artifacts and 156 protected source checks pass. No tenant catalogue HNSW/KG build, global ranking change, router change or production authority grant occurred. Temporary Reading List QA state was restored. The separate format review library retains all three original examples plus the stock-upgrade example; TEST retains the explicitly requested safe attachment.

## Required final fields

| Field | Result |
|---|---|
| STAFF_CATALOG_FINAL_URL | /staff/libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae/inventory |
| STAFF_CATALOG_DATA_SOURCE | tenant-local |
| STAFF_CATALOG_GLOBAL_BOOKS_VISIBLE | NO |
| STAFF_LIBRARY_QUERY_PARAM_HACK_REMOVED | YES |
| ADD_BOOK_FORMAT_CONTROL | THREE_WAY |
| FORMAT_OPTIONS | Physical, Online, Physical + Online |
| PHYSICAL_FORM_BROWSER_PASS | YES |
| ONLINE_FORM_BROWSER_PASS | YES |
| PHYSICAL_ONLINE_FORM_BROWSER_PASS | YES |
| ONLINE_CREATES_FAKE_HOLDING | NO |
| EXISTING_PHYSICAL_ADD_ONLINE | YES |
| EXISTING_BOOK_ID_PRESERVED | YES |
| EXISTING_ACCESSION_PRESERVED | YES |
| INVENTORY_FORMAT_COLUMN | YES |
| INVENTORY_FORMAT_FILTER | YES |
| PATRON_ONLINE_READ_ACTION | YES |
| PATRON_ONLINE_REQUEST_ACTION_PRESENT | NO |
| PATRON_BOTH_HAS_REQUEST | YES |
| PATRON_BOTH_HAS_READ | YES |
| BOOK_COVER_BACKPLATE_ROOT_CAUSE | Opaque book-cover-text-scrim background around title/author. The first repair also introduced adaptive foreground/duplicate text; the user reference overrides that repair. Both are removed. |
| OLD_COVER_CSS_RECOVERED | YES |
| TITLE_BACKPLATE_REMOVED | YES |
| AUTHOR_BACKPLATE_REMOVED | YES |
| SPLIT_COLOR_TEXT_BEHAVIOR_RESTORED | YES — original uniform palette foreground, geometry and opacity; no adaptive colour changes |
| LONG_TITLE_NO_BOX | YES |
| SHORT_TITLE_NO_BOX | YES |
| UNICODE_TITLE_NO_BOX | YES |
| GLOBAL_CATALOG_COVER_PASS | YES |
| TEST_CATALOG_COVER_PASS | YES |
| RECOMMENDATION_COVER_PASS | YES |
| MOBILE_COVER_PASS | YES |
| SHARED_BOOK_COVER_RENDERER | YES |

## Acceptance evidence

| Gate | Requirement | Result | Evidence |
|---|---|---|---|
| 186 | TEST Staff Catalog does not render the global 5M catalogue. | PASS | [institution_v2f1_staff_catalog_browser.json](institution_v2f1_staff_catalog_browser.json) |
| 187 | Staff Catalog does not rely on staff_library query parameter pseudo- tenancy. | PASS | [institution_v2f1_staff_catalog_browser.json](institution_v2f1_staff_catalog_browser.json) |
| 188 | Staff Catalog resolves to canonical TEST Staff collection/inventory. | PASS | [institution_v2f1_staff_catalog_browser.json](institution_v2f1_staff_catalog_browser.json) |
| 189 | Explicit global Catalog remains global. | PASS | [institution_v2f1_staff_catalog_browser.json](institution_v2f1_staff_catalog_browser.json) |
| 190 | Patron Catalog remains tenant scoped. | PASS | [institution_v2f1_staff_catalog_browser.json](institution_v2f1_staff_catalog_browser.json) |
| 191 | Add Book presents exactly three mutually exclusive primary format choices: Physical, Online, Physical + Online. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 192 | Physical selection displays physical inventory fields. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 193 | Online selection displays online upload fields. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 194 | Online selection does not require fake quantity. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 195 | Online selection does not create fake physical holding. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 196 | Physical + Online displays both input sections. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 197 | Format displayed to users is derived from canonical resource state. | PASS | [institution_v2f1_critical_backend.xml](institution_v2f1_critical_backend.xml) |
| 198 | READY attached asset contributes Online capability. | PASS | [institution_v2f1_critical_backend.xml](institution_v2f1_critical_backend.xml) |
| 199 | PROCESSING asset does not falsely advertise Online availability. | PASS | [institution_v2f1_critical_backend.xml](institution_v2f1_critical_backend.xml) |
| 200 | FAILED asset does not falsely advertise Online availability. | PASS | [institution_v2f1_critical_backend.xml](institution_v2f1_critical_backend.xml) |
| 201 | Existing physical book exposes Add Online Copy. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 202 | Adding Online Copy does not create a second LibraryBookRecord. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 203 | Existing library_book_id remains unchanged. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 204 | Existing accession remains unchanged. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 205 | Existing physical holding remains unchanged. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 206 | Successful attachment changes derived state to Physical + Online. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 207 | Inventory shows Format column/badge. | PASS | [institution_v2f1_format_filter_browser.json](institution_v2f1_format_filter_browser.json) |
| 208 | Inventory format filtering works. | PASS | [institution_v2f1_format_filter_browser.json](institution_v2f1_format_filter_browser.json) |
| 209 | Online-only Patron Book Detail shows Read Online. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 210 | Online-only Patron Book Detail does not show Request Book. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 211 | Physical-only Patron Book Detail shows physical request behavior. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 212 | Physical + Online exposes both actions independently. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 213 | Real-browser Add Physical passes. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 214 | Real-browser Add Online passes. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 215 | Real-browser Add Physical + Online passes. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 216 | Real-browser existing Physical → Physical + Online passes. | PASS | [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json) |
| 217 | Generated book titles no longer display an unintended rectangular background/backplate. | PASS | [institution_v2f1_cover_visual_validation.json](institution_v2f1_cover_visual_validation.json) |
| 218 | Generated author text no longer displays an unintended rectangular background/backplate. | PASS | [institution_v2f1_cover_visual_validation.json](institution_v2f1_cover_visual_validation.json) |
| 219 | Global Catalog covers use the restored older LuminaR title treatment. | PASS | [institution_v2f1_cover_visual_validation.json](institution_v2f1_cover_visual_validation.json) |
| 220 | TEST catalogue covers use the same restored treatment. | PASS | [institution_v2f1_cover_visual_validation.json](institution_v2f1_cover_visual_validation.json) |
| 221 | Recommendation covers use the same restored treatment. | PASS | [institution_v2f1_cover_visual_validation.json](institution_v2f1_cover_visual_validation.json) |
| 222 | Long titles wrap without requiring an opaque text box. | PASS | [institution_v2f1_cover_visual_validation.json](institution_v2f1_cover_visual_validation.json) |
| 223 | Short titles do not produce oversized text rectangles. | PASS | [institution_v2f1_cover_visual_validation.json](institution_v2f1_cover_visual_validation.json) |
| 224 | Unicode titles render without a title backplate. | PASS | [institution_v2f1_cover_visual_validation.json](institution_v2f1_cover_visual_validation.json) |
| 225 | Multiple-author covers remain readable without author backplates. | PASS | [institution_v2f1_cover_visual_validation.json](institution_v2f1_cover_visual_validation.json) |
| 226 | Cover decorative geometry remains behind text. | PASS | [institution_v2f1_cover_visual_validation.json](institution_v2f1_cover_visual_validation.json) |
| 227 | Split-color covers preserve integrated region-aware typography. | PASS | [institution_v2f1_cover_visual_validation.json](institution_v2f1_cover_visual_validation.json) |
| 228 | No mobile-specific CSS reintroduces title boxes. | PASS | [institution_v2f1_cover_visual_validation.json](institution_v2f1_cover_visual_validation.json) |
| 229 | One shared BookCover renderer remains authoritative. | PASS | [institution_v2f1_cover_visual_validation.json](institution_v2f1_cover_visual_validation.json) |
| 230 | Real-browser screenshots confirm the older LuminaR cover language has been restored rather than redesigned. | PASS | [institution_v2f1_cover_visual_validation.json](institution_v2f1_cover_visual_validation.json) |

Gate 227 follows the latest user reference: integrated typography uses the original uniform palette foreground, without adaptive colour changes. Earlier “after initial” screenshots are historical and superseded. Final captures use `institution_v2f1_sample_*`, `institution_v2f1_cards_*` and current surface captures.

## Files changed

- `backend/routes/library_inventory.py`
- `backend/schemas/library_catalogue.py`
- `backend/services/library_book_formats.py`
- `backend/services/library_catalogue_service.py`
- `backend/services/library_catalogue_experience.py`
- `backend/services/library_lending_service.py`
- `backend/services/library_v2c_plan.py`
- `frontend/src/components/AIChatWidget.tsx`
- `frontend/src/components/BookCover.tsx`
- `frontend/src/components/BookCard.tsx`
- `frontend/src/components/BookDetailView.tsx`
- `frontend/src/components/DiscoveryBookFrame.tsx`
- `frontend/src/components/Header.tsx`
- `frontend/src/components/LibraryStockEditor.tsx`
- `frontend/src/hooks/useProductContext.ts`
- `frontend/src/lib/productContext.ts`
- `frontend/src/lib/bookPresentation.ts`
- `frontend/src/lib/libraryCatalogue.ts`
- `frontend/src/lib/libraryInventory.ts`
- `frontend/src/pages/CatalogPage.tsx`
- `frontend/src/pages/LibraryInventory.tsx`
- `frontend/src/pages/LibraryAssets.tsx`
- `frontend/src/pages/LibraryAssets.css`
- `frontend/src/styles/product.css`
- `frontend/package.json`
- `frontend/tests/institution-critical-closure.test.tsx`
- `frontend/tests/institution-inventory.test.tsx`
- `frontend/tests/institution-lending.test.tsx`
- `frontend/tests/platform-completion.test.tsx`
- `frontend/tests/institution-assets.test.tsx`
- `tests/institution_v2f/test_book_formats.py`
- `scripts/institution_v2f1_browser.py`
- `scripts/institution_v2f1_visual_browser.py`
- `scripts/institution_v2f1_final_browser.py`
- `scripts/institution_v2f1_preservation.py`
- `scripts/institution_v2f1_reports.py`

`institution_v2f1_lending_regression.xml` records a superseded combined-fixture attempt. The authoritative isolated V2B/V2C reruns and complete current regression groups pass. Debug/initial screenshots and this older XML are retained as history, rather than used as final acceptance evidence. The navigation audit and accepted Part 2F report link to this closure.

## Reports

- [institution_v2f1_QA_cleanup.json](institution_v2f1_QA_cleanup.json)
- [institution_v2f1_assistant_followup.log](institution_v2f1_assistant_followup.log)
- [institution_v2f1_book_card_layout_validation.json](institution_v2f1_book_card_layout_validation.json)
- [institution_v2f1_book_format_architecture.md](institution_v2f1_book_format_architecture.md)
- [institution_v2f1_build.log](institution_v2f1_build.log)
- [institution_v2f1_catalogue_regression.xml](institution_v2f1_catalogue_regression.xml)
- [institution_v2f1_changed_files.json](institution_v2f1_changed_files.json)
- [institution_v2f1_cover_root_cause.md](institution_v2f1_cover_root_cause.md)
- [institution_v2f1_cover_samples.json](institution_v2f1_cover_samples.json)
- [institution_v2f1_cover_visual_validation.json](institution_v2f1_cover_visual_validation.json)
- [institution_v2f1_critical_backend.xml](institution_v2f1_critical_backend.xml)
- [institution_v2f1_critical_baseline.json](institution_v2f1_critical_baseline.json)
- [institution_v2f1_critical_completion.json](institution_v2f1_critical_completion.json)
- [institution_v2f1_critical_completion.md](institution_v2f1_critical_completion.md)
- [institution_v2f1_critical_preservation.json](institution_v2f1_critical_preservation.json)
- [institution_v2f1_critical_regression.json](institution_v2f1_critical_regression.json)
- [institution_v2f1_format_accessibility.json](institution_v2f1_format_accessibility.json)
- [institution_v2f1_format_filter_browser.json](institution_v2f1_format_filter_browser.json)
- [institution_v2f1_formats_backend.xml](institution_v2f1_formats_backend.xml)
- [institution_v2f1_formats_browser.json](institution_v2f1_formats_browser.json)
- [institution_v2f1_inventory_followup.log](institution_v2f1_inventory_followup.log)
- [institution_v2f1_lending_regression.xml](institution_v2f1_lending_regression.xml)
- [institution_v2f1_lint.log](institution_v2f1_lint.log)
- [institution_v2f1_online_stock_browser.json](institution_v2f1_online_stock_browser.json)
- [institution_v2f1_review_fixtures.json](institution_v2f1_review_fixtures.json)
- [institution_v2f1_runtime.json](institution_v2f1_runtime.json)
- [institution_v2f1_safe_document_browser.json](institution_v2f1_safe_document_browser.json)
- [institution_v2f1_staff_catalog_browser.json](institution_v2f1_staff_catalog_browser.json)
- [institution_v2f1_v2b.xml](institution_v2f1_v2b.xml)
- [institution_v2f1_v2c.xml](institution_v2f1_v2c.xml)

## Limits and recommendation

- Library uploads currently support PDF; unsupported TXT/DOCX formats are not advertised.
- Global catalogue preservation uses estimated count; protected binary artifacts compare size/mtime, while protected source files and TEST books/holdings use hashes.
- Browser validation uses Chromium at the six requested sizes.
- Ten pre-existing security test skips and fourteen existing lint warnings remain; no failing tests or lint errors.
- Original palette colours/brand and author opacity are intentionally restored per the latest user reference. No claim of newly adjusted cover contrast colours.

**Accept Part 2F.1 closure. STOP before Part 2G and all catalogue index/KG/build/publishing work.**
