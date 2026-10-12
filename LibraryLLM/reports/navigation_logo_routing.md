# Navigation logo repair — PASS

The exact brand link is Header.tsx, Header(), a React Router Link with class global-logo and accessible name LuminaR home. It previously used to="/" for every workspace. Header catalogue/search links also relied on activeLibrary, which could lag behind the current route.

libraryWorkspace.ts now extracts a canonical UUID only from the explicit /libraries/{uuid} path prefix. luminarHomePath returns that library Home for every Patron child. Header uses the same URL UUID for Browse Books, New Arrivals, My Library and search. Remembered IDs cannot override it, even before the route context request finishes. The helper grants no permissions: WorkspaceRoute still checks the server and LibraryMembership before mounting tenant content.

Global Home, Catalog, Search, account pages, Staff Workspace and Platform Console logo destinations remain /. Staff never uses the Patron logo destination. Graph Lab, Events, About and Know More retain existing global destinations. Direct / remains available for global discovery. All destinations are router-relative, independent of development port. Vite API proxy configuration is separate and unchanged.

TEST logo destination from Home, My Library, Reservations, Fees and catalogue children: /libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae. Required logo/header tests and real browser checks cover URL-first routing, switching, stale remembered state, Staff and Platform separation.
