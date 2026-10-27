# Part 2F.1 — Staff catalogue correction and clickable titles

The latest user correction supersedes the earlier decision to send Staff Catalog to Inventory. The current canonical browsing route is `/staff/libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae/catalogue`; management stays at `/staff/libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae/inventory`. Both navigation entries remain.

Staff Catalogue reuses `LibraryCataloguePage`, `CatalogueSurface`, `CatalogueGrid`, `BookCard`, `DiscoveryBookFrame`, `BookCoverArt` and `BookCover`. The detail route reuses `LibraryCatalogueDetail` and `BookDetailView`, with the existing BookEditor, LibraryStockEditor and AddSoftCopyModal. No second cover system or catalogue design was added.

The existing source/books/genres/detail catalogue APIs accept `staff=true` to select a representation. That flag invokes `require_library_staff`; it is never authority. ACTIVE ADMIN/LIBRARIAN LibraryMembership in the URL's exact library is mandatory, revalidated inside the canonical lock. Platform role and legacy User.role do not supply membership. Missing/revoked membership returns the existing non-disclosing 404; an active Patron requesting Staff representation receives 403. Default Patron browsing remains Patron-only. No new mutation service exists.

Staff reads use canonical LibraryBookRecords, holdings and authorized READY assets (including STAFF_ONLY). Processing/failed unstocked records remain visible for management; they never acquire a false online capability. An empty Staff library returns LOCAL/0 and never automatically loads global filler. Source counts and pages remain bounded server reads. Global browsing is an explicit `/catalog` action.

`libraryBookPath` centralizes exact library/book identities. Staff Inventory titles carry only a same-library Inventory return path; search, record/state/format filters and zero-based page are URL state. Creation/import commands are excluded from return links. Foreign and malformed history return state is rejected. Personal card links consult the matching explicit membership, without first-membership selection. Reservations, circulation, analytics and asset-linked titles reuse `LibraryBookTitleLink` and its visible keyboard focus style.

Staff detail displays canonical format, accession, ISBN/global reference, shelf, current holding call number, status, stock/requestable counts and resource status/visibility. Staff book resources reuse the existing protected asset APIs; only READY authorized assets offer Read Online. Asset detail already enforces file/RAG/Knowledge permissions. The browser uploaded a hand-authored QA PDF to the disposable review library only, retaining book identity and holding hash. TEST records/holdings were not changed.

Original cover palette/geometry files are unchanged from the accepted HEAD. No text backplates, adaptive foreground colors, new catalogue HNSW/KG builds, Router changes or new phase were introduced.
