# Catalogue / Browse convergence

GlobalCatalogue and LibraryCatalogue route adapters compose CatalogueSurface, CatalogueGrid, CatalogueSearch, CatalogueFilters, CategoryChips, ProductPagination and BookCard. The separate local plain form/grid/detail CSS is removed after caller migration.

Global categories come from actual API facets. Category/author constraints query the database before pagination, using literal escaped pipe-token subjects and escaped author terms. Unfiltered 5M count is estimated. Filtered exact count has maxTimeMS=1000; timeout returns count=null, the UI says matching titles and Next uses limit+1 probing. A false current-page filter or invented filtered total is not retained.

Local subjects/counts come from the selected library only. Subject/author/status/search are URL state and reset offset on change. Circulation status is local-only. Local no-result views offer explicit Search all LuminaR. View All selects actual arrivals/popular/recommendation data. Local For You intersects the existing candidate set with ownership, filters the bounded scoped set before paging and never uses unrelated global filler. Accepted empty-library GLOBAL_FALLBACK remains explicit, non-owned and without physical actions.

Global server-filter/paging tests, 68 catalogue/Home/context checks, source transition and backend ownership tests pass. Browser layout/overflow comparison remains pending.
