# Staff and member frontend closure

Production implementation: frontend/src/pages/LibraryAnnouncements.tsx and .css; lib/libraryAnnouncements.ts; App.tsx routes; existing LibraryShells navigation; EventsPage/ManageEventsPage cross-links; existing NotificationCenter and lib/notifications action type. No second bell, counter, unread store, design theme or protected transport edit.

ADMIN manages drafts and publication. LIBRARIAN reads PUBLISHED content within Staff workspace without gaining management rights. Member routes use existing WorkspaceRoute. Server action resolution selects staff/member path from current membership. Page content is keyed by library/session/role/detail; aborts and response-tenant/status validation prevent stale library/session content. Focus refresh preserves row interactions; successful mutations/filter/page changes invalidate the old list before authoritative reload. Errors clear stale content and expose existing retry/reload UI.

Final frontend 988 passed / 0 failed / 0 skipped. Build PASS; lint PASS, 16 existing warnings, 0 new. Raw final5 logs contain complete executed evidence. New feature tests29, including stale saved-preview and focus refresh. Existing Analytics adjacency test preserved and passes.

Actual Chromium communication checks 23; six member widths1440/1366/1024/768/390/375, mobile Staff draft, keyboard Escape/focus, focused axe with no violations. Inspected390px member and Staff-dialog screenshots plus desktop edit. No document overflow at measured widths. 2 expected404 browser responses during revoked membership; no unexpected HTTP/page JavaScript errors. No blanket accessibility certification.

The existing aggregated bell remains account-wide with source-library labels and one unread badge. Existing45s polling/focus refresh and read-one/read-all semantics remain; priority is text-labeled. Event navigation is through canonical existing routes. No frontend fetch loads institution recipient arrays.
