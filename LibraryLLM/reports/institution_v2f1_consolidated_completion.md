ORIGINAL_PART_2F_STATUS: PASS

PART_2F1_CLOSURE_STATUS: PASS

Final consolidated Part 2F.1 acceptance; stop before Part 2G.

The final sweep repaired the remaining PDF-only upload and duplicate document-chat gaps. PDF pages now render as bounded authenticated source-page images, avoiding a blank native iframe. TXT uses inert UTF-8 text; DOCX uses extracted paragraph text. Original bytes and checksums remain available for download; legacy .doc is explicitly unsupported.

Ask LuminaR opens the shared AIChatWidget and sends DOCUMENT_QUESTION through the existing Assistant API. Its canonical `library:<library_id>:asset:<asset_id>` context resolves to the existing authorized library asset pipeline in the resident existing_qwen process. Fresh membership/visibility checks precede private reads and the returned answer. The routing algorithms, model and generation pipeline are unchanged. No second normal document chatbot remains. Knowledge Tools reuses its existing asset-scoped workflow/cache.

Staff Catalog remains separate visual browsing; Inventory remains collection management. Inventory has bounded readable title/subject columns, canonical title links, and preserved return filters/page. Three radio choices create real holdings/assets, with displayed format derived only from canonical physical stock and READY resources. The original generated-cover palettes, geometric layers and typography remain intact, with no opaque text backplates.

Operational Activity/Audit use the shared padded, bounded Staff table and contained reference presentation. Authorized actor/member emails are hydrated in one bounded users.find($in) call; canonical audit IDs remain unchanged and historical unresolved accounts retain a safe fallback.

| Required QA field | Final result |
|---|---|
| STAFF_LOGO_FINAL_ROUTE | /staff/libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae |
| STAFF_CATALOG_FINAL_ROUTE | /staff/libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae/catalogue |
| STAFF_CATALOG_IS_GLOBAL | NO |
| STAFF_CATALOG_IS_INVENTORY | NO |
| STAFF_CATALOG_VISIBLE_LIBRARY | TEST / e6d1e5b4-c48f-4b47-b96a-656a676fb8ae |
| STAFF_INVENTORY_SEPARATE | YES |
| STAFF_BOOK_TITLE_CLICKABLE | YES |
| STAFF_BOOK_DETAIL_ROUTE | /staff/libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae/books/a8a04662-23be-45ea-bb20-0f0b86bcfa12 |
| THREE_WAY_FORMAT_CONTROL | YES |
| FORMAT_OPTIONS | Physical, Online, Physical + Online |
| PHYSICAL_BROWSER_PASS | YES |
| ONLINE_BROWSER_PASS | YES |
| PHYSICAL_ONLINE_BROWSER_PASS | YES |
| ONLINE_FAKE_HOLDING_CREATED | NO |
| EXISTING_PHYSICAL_ADD_ONLINE_PASS | YES |
| BOOK_ID_PRESERVED | YES |
| ACCESSION_PRESERVED | YES |
| PDF_ACTUAL_CONTENT_VISIBLE | YES |
| TXT_PREVIEW_PASS | YES |
| DOCX_PREVIEW_PASS | YES |
| ASK_LUMINAR_USES_EXISTING_WIDGET | YES |
| REAL_DOCUMENT_QA_PASS | YES |
| KNOWLEDGE_TOOLS_PASS | YES |
| TITLE_BACKPLATE_REMOVED | YES |
| AUTHOR_BACKPLATE_REMOVED | YES |
| SPLIT_COLOR_COVER_BEHAVIOR_PASS | YES |
| STAFF_CONTROLS_SHARED_STYLE | YES |
| OPERATIONAL_ACTIVITY_LAYOUT_PASS | YES |
| AUDIT_ACTOR_EMAIL_PASS | YES |
| AUDIT_MEMBER_EMAIL_PASS | YES |
| IDENTITY_LOOKUP_BATCHED | YES |
| GLOBAL_BOOK_COUNT | 5000000 |
| GLOBAL_HNSW_REBUILT | NO |
| GLOBAL_KG_REBUILT | NO |

Regression: 310 current affected backend tests passed (173 asset/extension, 69 catalogue, 68 Assistant); prior full 1,958-test backend closure retained. Frontend 835 passed (687 default + 148 extended). Build PASS; lint 0 errors / 14 existing warnings.

Chromium evidence: 18 consolidated flows; 36 Staff/document viewport cases; 42 additional Staff controls cases; 186 cover viewport cases. Viewports: 1440×900, 1366×768, 1024×768, 768×1024, 390×844, 375×812. No page overflow. Native download checksum, PDF open/close/error/retry, actual document-grounded shared Assistant response, scoped flashcards, text previews, operational identities and source-page screenshot all pass.

Preservation: TEST remains 150 ACTIVE records / 150 holdings; all TEST records, holdings and assets match the start-of-sweep hashes. Global catalogue remains approximately 5,000,000 (estimated_document_count). All 196 protected global binary artifacts retain size/mtime. Personal registry logical tables remain identical; SQLite physical timestamps are excluded using the accepted preservation method. Search/Recommendation/router/Qwen protected source hashes remain unchanged. Safe QA additions were confined to the disposable review library and one user-owned Reading List item.

Evidence: `institution_v2f1_consolidated_browser.json`, `..._controls.json`, `..._covers.json`, `..._regression.json`, `..._preservation.json`, `..._changed_files.json`, and current XML/logs. Exact source paths and hashes are in the changed-files manifest. Current PNGs use `institution_v2f1_consolidated_*`.

Limits: DOCX preview preserves readable text, not Word page layout/images; .doc is unsupported. PDF previews are bounded page images with original PDF download. Browser validation used Chromium. Global count is estimated; binary preservation uses metadata, while protected source files use SHA-256. Existing backend deprecation/lint/build-size warnings remain. Initial harness failures (oversized pytest ID, premature catalogue lookup/report write, cached-tool locator) were corrected; final logs/XML are authoritative. Earlier iframe-presence evidence was superseded by actual rendered-source proof.

No credentials are committed or placed in reports. No Git commit, next domain phase, global index build, router research, Part 2G, or tenant catalogue HNSW/KG work was performed. Ready for review.
