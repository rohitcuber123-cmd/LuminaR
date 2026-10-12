# Staff, dataset upload, analytics, events and notifications

## Staff permissions and UI

`App.tsx` routes `/admin` to `StaffDashboard admin`, `/librarian` to `StaffDashboard`, and staff event routes to protected pages. `backend/dependencies.require_roles` verifies roles server-side; JWT decode refreshes current Mongo identity. Book add/update allow ADMIN/LIBRARIAN; book and inventory deletion are ADMIN; staff directory/creation/change is ADMIN. Staff setup uses emailed OTP and password establishment. Real dashboard, management and forms exist; unused Placeholder files do not negate them.

The library input in `StaffDashboard.tsx:81–84,366–378` defaults to `VITE_LIBRARY_ID || LIB001`; editing it selects inventory queries/imports. It is not library registration or verified librarian assignment. Any appropriately ranked staff identity can supply another library ID to current inventory operations. Future ownership enforcement belongs in backend dependency/service boundaries.

## Dataset workflow: what it actually imports

`StaffForms.DatasetImport` → `api/core.previewImport` → POST `/inventory/import/preview?library_id=L` with file → `create_preview` → rows/status stored in Mongo preview → UI review → `/inventory/import/confirm` with preview_id/library_id → `confirm_inventory_import` → matching physical holdings inserted → counts/result UI.

Supported files are CSV and XLSX (`read_csv_file/read_xlsx_file/read_uploaded_file`). Required columns include ISBN, total_copies, available_copies; optional descriptive/shelf fields aid presentation/matching. ISBN normalizes and resolves to existing catalogue works using DuckDB ISBN lookup. Rows are MATCHED/EXISTS/NOT_FOUND/AMBIGUOUS/INVALID; only MATCHED are imported, and duplicate matched work rows consolidate counts. Preview matching is bounded by its stored library_id; confirmation verifies that pair, but not uploader or institution membership.

This is **inventory import of known global works**, not an independent catalogue ingestion-and-embedding service. `confirm_inventory_import:510–770` inserts library_inventory documents and marks the preview CONFIRMED, collecting row failures. It does not create new bibliographic works or call MiniLM/HNSW. A partial failure can coexist with CONFIRMED; replace with explicit partial/retry semantics in future jobs. No library-dataset version/checksum/index publication model is traced. Existing semantic-sync tests explicitly verify inventory confirmation does not sync the catalogue graph.

## Analytics lineage

| Display/data | Where measured | Meaning / limitation |
|---|---|---|
| Total users | `/admin/summary`, `users.count_documents({})` | All accounts, not active-in-window |
| Total books | `books.estimated_document_count()` | Estimated global catalogue count |
| Librarians | Users role LIBRARIAN and active !=false | Role count, no assigned libraries |
| Active loans | Issues status ISSUED | Global active transactions |
| Reservations | ACTIVE or READY_FOR_PICKUP | Global waiting/pickup records |
| Outstanding fines | `$match UNPAID` then `$group sum amount` | Persisted unpaid INR total |
| Available inventory | StaffDashboard filters selected inventory available_copies>0 | Titles with a free copy, not free-copy sum |
| Overdue books | Dashboard filters fetched issue due dates/status | Browser-derived global overdue records |
| Popular books | Imported reading_log_count/rating sort | Not directly measured LuminaR click popularity |
| Categories | Cached book_categories sorted count | Offline/precomputed global distribution |
| Search queries | search_history collection | Authenticated saved first-page queries |
| Assistant/RAG timings | telemetry/profiling and response timing | Instrumentation, not a complete product usage dashboard |

Evidence: `routes/notifications.py:68–78 summary`, `StaffDashboard.tsx:215–261`, `book_service.py:51–124`, `search/api.py:282–307`. Librarian loans/reservations/fines/all activity queries remain global even when inventory ID changes. No end-to-end semantic-usage/chatbot-usage/upload/event-engagement analytics dashboard was verified. Mock-looking data in old snapshots must not substitute for these actual sources.

## Events lifecycle and publishing

`EventEditorPage/ManageEventsPage` → `/staff/events` → `event_service.create/edit/transition/delete_draft`. `schemas/events.py` forbids unknown input fields and defines NEW_ARRIVALS, BOOK_SALE, WORKSHOP, AUTHOR_EVENT, READING_CLUB, COMMUNITY_EVENT, LIBRARY_PROGRAM, LIBRARY_NOTICE, CLOSURE, EXHIBITION, OTHER. Dates must be timezone aware and have a valid range; related work IDs are unique and validated against books. State is DRAFT → PUBLISHED → CANCELLED/ARCHIVED; only drafts delete. Publish checks shared publish requirements; optimistic revision protects edit/transition conflicts. Audit creator/updater/time fields are server-generated. First published time is not reset by repeat publish.

Reader `/events` returns published upcoming/past records; staff listings filter status/category/query/date sorts. Related book hydration is application-side. Future start dates describe event time; they do **not** schedule automatic publication. There is no separate audience/group/library targeting field. No explicit unpublish-to-draft transition or automated event expiration job is traced; past/upcoming categorization derives dates.

`EventMonitor`, event pages and `useEventStore` support unseen indicators. `event_user_state` holds a bounded 14-day/500-event seen window; first access establishes a baseline. Signed 10-minute seen receipts bind event IDs to account/session; mark_seen CAS merges observed IDs. This differs from one notification document per event/user. No push/email event-delivery guarantee or view/click engagement analytics is implemented by these receipts.

## Account notifications

`NotificationCenter` calls `/notifications`, unread-count, mark-read and read-all. ADMIN can search users, send targeted notices and view sent notices. `notification_service.insert_notice` uses deduplication keys; periodic `DueWorker` scans DUE_SOON/DUE_TODAY/OVERDUE and reservation pickup. `loan_notification_service` reconciles stale reminders after due-date changes. Mongo per-user records supply unread state; this is polling/in-app delivery. Brevo is an OTP email integration, not proof every event/loan notice is emailed.

## Proposed private-library changes

Scope librarians by membership role and resource library before upload/create/update/delete, event publishing, assisted loan work, directory and analytics. Add library_id to events and per-library event seen state; explicit platform-global event scope must be ADMIN-controlled. Notifications include library provenance/authorized recipient membership. Aggregate with a leading library `$match`; platform totals require separate ADMIN permission. Preserve uploaded dataset versions and indexing progress in a new Dataset service; do not rename current inventory import and call that work complete.
