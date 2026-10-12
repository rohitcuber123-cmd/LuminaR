# Frontend duplicate decisions

| Overlap | Canonical | Migrated | Decision | Retained reason |
| --- | --- | --- | --- | --- |
| Global / local Book Detail | BookDetailView + route data adapters | Cover, typography, description, saved, AI, facts, actions, skeleton, back | MERGED | Local canonical mutations injected |
| Inline ForYou/Popular/Arrivals / LibraryBookCard | BookCard + DiscoveryBookFrame | One card family, personal actions, tenant facts | MERGED | Section retrieval and accepted Home composition retained |
| Catalog / plain Library Browse | CatalogueSurface + CatalogueGrid | Search, chips, filters, grid, states, paging | MERGED | Global metadata and tenant books remain distinct data |
| Global Search / local search result layouts | CatalogueSurface + BookCard | Same result family and personal controls | MERGED | Semantic and tenant lexical engines intentionally distinct |
| Hardcoded global category / local subject forms | CategoryChips + real facets | Actual global facets / counted local subjects | MERGED | No irrelevant global chip injection |
| Global/Search/local paging markup | ProductPagination | Keyboard buttons, busy states, truthful totals, URL offsets | MERGED | Search page 10 / browse page 20 |
| Inline discovery personal action handlers | BookPersonalActions + one store/service | Saved, AI, server acknowledgement, session guards | MERGED | Supplemental graph/Assistant cards keep intent-specific composition |
| Repeated cover rendering and seed adaptation | BookCoverArt over existing BookCover | Safe cover fallback and consistent linked seed | MERGED | Auth decorative / compact graph covers use common renderer |
| Parallel library book/detail/filter CSS | product.css + existing tokens | Shared detail/card/chip/filter/action/state/paging rules | MERGED | Distinct workspace/event/document/diagram styles retained |


| Removed file | Replacement | Caller reason |
| --- | --- | --- |
| frontend/src/pages/CorePages.tsx | Canonical page modules | Unused older combined page implementations |
| frontend/src/pages/LibrarianPlaceholder.tsx | ManagementRedirect / StaffLibraryShell | Unused old dashboard placeholder |
| frontend/src/components/LibraryWorkspaceRoute.tsx | WorkspaceRoute | Unused parallel guard |
| frontend/src/pages/BookDetailPage.tsx.backup | BookDetailView | Stale unreferenced backup |
| frontend/src/pages/CatalogPage.tsx.backup | GlobalCatalogue | Stale unreferenced backup |
| frontend/src/data/categories.ts | Actual global/local facets | Unused hardcoded data |
| frontend/src/hooks/useBookActionState.ts | CatalogueBookActions / protected reader | Unused after dead legacy direct Borrow handlers removed |
| frontend/src/pages/LibraryCatalogue.css | product.css | Live context/actions/cover selectors moved; duplicate layout rules removed |


Units: 9 overlapping implementation clusters merged; 8 obsolete files removed. Dead direct Borrow handlers, duplicate local markup and unused store filter fields were also removed inside retained files. Caller AST/search inventory preceded removal; raw string counts were not treated as proof.

Retained typed route/API adapters compose one visual/transport implementation. api/core aliases the common request transport; institutionApi is a thin scoped typed wrapper. Distinct stores represent auth, memberships, platform assignments, selected context, saved state, global events/notifications and private document tools. Supplemental RelatedBookCard/Assistant layouts serve graph/intent facts and share canonical selection; they are not independent catalogue products. AuthLayout BOOKS are decorative.

LegacyProfilePage remains labelled read-only history. The unused readNow pure-test/compatibility helper has no production caller and its old writer remains 410. Workspaces, global events, private knowledge and protected reader are distinct valid features.
