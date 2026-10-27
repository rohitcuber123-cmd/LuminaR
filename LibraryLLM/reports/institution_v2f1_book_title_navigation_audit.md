# Part 2F.1 book-title navigation audit

Titles with canonical identities use real links. No routing by title, accession, ISBN or first membership.

| File | Surface | Classification | Destination | Result |
|---|---|---|---|---|
| frontend/src/pages/LibraryInventory.tsx | Staff Inventory table | STAFF_WORKSPACE | /staff/libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae/books/{library_book_id} | Fixed; real title Link; safe Inventory return state. |
| frontend/src/components/BookCard.tsx | Patron Browse / Catalogue | PATRON_WORKSPACE | /libraries/{explicit_library_id}/books/{library_book_id} | Verified; canonical shared card. |
| frontend/src/components/GlobalCatalogue.tsx | Global catalogue / Search | GLOBAL_INTENTIONAL | /book/{global_work_id} | Verified; shared card and global work identity. |
| frontend/src/pages/ReadingListPage.tsx | Saved global/local books | PERSONAL_WITH_RETURN_CONTEXT | exact global or library book; explicit Staff membership chooses Staff detail | Verified through shared BookCard/bookPath. No first-membership selection. |
| frontend/src/pages/LibraryReservationsFees.tsx | Reservation book rows | STAFF_WORKSPACE / PATRON_WORKSPACE | exact library book route in row workspace | Fixed; real title Link. |
| frontend/src/pages/LibraryCirculation.tsx | Circulation request/loan rows | STAFF_WORKSPACE / PATRON_WORKSPACE | exact library book route in row workspace | Fixed; real title Link. |
| frontend/src/pages/LibraryAnalyticsPage.tsx | Popular books table | STAFF_WORKSPACE | /staff/libraries/{analytics.library_id}/books/{library_book_id} | Fixed; uses response-scoped library and canonical row ID. |
| frontend/src/pages/LibraryAssets.tsx | Digital Asset linked-book label | STAFF_WORKSPACE / PATRON_WORKSPACE | exact library book detail | Fixed in facts/list and detail link; verified in browser. |
| frontend/src/pages/LibraryReservationsFees.tsx | Fee references and accrued estimates | STAFF_WORKSPACE / PATRON_WORKSPACE | exact library book where API supplies ID | Fee records link; estimates lacking canonical ID remain text, with no guessed destination. |
| frontend/src/pages/LibraryInventory.tsx | Uncommitted import preview rows | GLOBAL_INTENTIONAL | no canonical detail before creation | Intentional plain text: preview row has no created library_book_id. |
