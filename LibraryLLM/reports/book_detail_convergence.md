# Book detail convergence

Global BookDetailPage and LibraryCatalogueDetail are data adapters to BookDetailView/BookDetailSkeleton. The mature global two-column cover, typography and action composition is reused, with common cover and personal controls. There is one book detail design family.

Linked local metadata hydrates descriptions, cover seed, ratings and reading counts in bounded batches. Accession, shelf, circulation status, requestable count, pending request, reservation and loan state come only from tenant records/holdings. Global stock and shelf never leak into library facts. CatalogueBookActions preserves Part 2B/C Request Book, cancellation, confirmed waitlist and idempotency. Global non-owned works have no direct Borrow or tenant request. Digital access stays a separate protected entitlement.

Saved and AI selection use one canonical identity/store. Local-only details offer saving and explain the unsupported AI contract. Related discovery is optional and binds an actual global work. Back navigation stays in explicit context. Tests cover both detail contexts, description/accession, personal controls, axe semantics and absence of global stock leakage. Real-browser visual comparison at six viewports remains NOT_VERIFIED.
