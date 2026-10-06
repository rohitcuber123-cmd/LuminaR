# Events & Announcements V1

**PASS — Core 8002 owns the module. Existing Mongo database and frontend; no new service or ML dependency.**

## A. Schema

`events`: unique UUID `event_id`, title (3–140), category enum, summary (≤300), description (≤5000), optional timezone-aware UTC start/end,
optional location (≤200), ordered unique `related_work_ids` (≤12), strict boolean featured, lifecycle status, canonical numeric created/updated staff IDs,
created/updated timestamps, immutable first `published_at`, optional cancelled/archived timestamps, internal revision for optimistic concurrency.
Client audit/status/identity fields are forbidden. End requires start and cannot precede it. Contents are plain text.

`event_user_state`: one unique numeric user ID, ≤500 exact seen event IDs, revision, initialized/updated times,
last seen publication/UUID metadata. No per-user event or inbox copy.

## B. Lifecycle

Create → DRAFT. Explicit publish → PUBLISHED. PUBLISHED → CANCELLED or ARCHIVED; CANCELLED → ARCHIVED.
Only DRAFT may be hard-deleted through the product. Repeating a successful transition is idempotent.
First publication is immutable; editing creates no new publication signal. ARCHIVED is read-only and staff-visible.
Cancelled previously-published details remain accessible with a clear Cancelled message; cancelled/archived events leave ordinary lists.
CAS prevents concurrent edits/publish from silently overwriting changes; conflicts ask the user to refresh.

## C. Categories

NEW_ARRIVALS, BOOK_SALE, WORKSHOP, AUTHOR_EVENT, READING_CLUB, COMMUNITY_EVENT, LIBRARY_PROGRAM,
LIBRARY_NOTICE, CLOSURE, EXHIBITION, OTHER. Book Sale is informational: no payment, price or checkout fields.

## D. Authorization

All Events routes require existing authenticated, active, verified accounts. Server revalidates canonical current account role.
GENERAL_USER reads published content and changes only its own seen state. ADMIN/LIBRARIAN can manage all library events, including each other's.
Draft/archive public detail returns private 404. Staff management/write routes return 403 to readers.
Payload user IDs and spoofed staff/audit fields cannot choose account ownership. No auth/session semantics were changed.

## E. API routes

| Scope | Method / route |
|---|---|
| Authenticated browse | GET `/events?view=upcoming|past&category=&query=&featured=&page=&page_size=` |
| Authenticated detail | GET `/events/{event_id}` |
| Authenticated unseen | GET `/events/unseen` |
| Own signed snapshot | POST `/events/mark-seen` with `cursor` |
| Staff list | GET `/staff/events?status=&category=&query=&sort=updated|created|start&page=&page_size=` |
| Staff create | POST `/staff/events` (201, always DRAFT) |
| Staff detail/edit | GET / PATCH `/staff/events/{event_id}` |
| Staff transition | POST `/staff/events/{event_id}/publish`, `/cancel`, `/archive` |
| Staff draft-only delete | DELETE `/staff/events/{event_id}` |

Page defaults 12, maximum 50. Query maximum 120; substring title/summary matching is escaped and case-insensitive.
Upcoming includes ongoing events through their end, future start-only events, and undated announcements. Past uses end when available, otherwise start.
Upcoming featured items sort first, then nearest start; undated items sort after dated items within their featured group, then publication/UUID deterministically.
Undated announcements remain Upcoming until cancellation/archive. Boundaries use exact UTC request time; browser display uses local timezone.

## F. Mongo indexes

Existing index keys audited before adding. No duplicate key-equivalent indexes are added; conflicting non-unique identity index fails startup for review.

| Collection | Key | Unique |
|---|---|---|
| events | event_id ASC | yes |
| events | status ASC, start_at ASC | no |
| events | status ASC, published_at DESC, event_id ASC | no |
| events | category ASC, status ASC, start_at ASC | no |
| event_user_state | user_id ASC | yes |

Mongo's existing `_id` indexes remain. No text index or new database; lightweight event substring search stays separate from book Search.

## G. Related books

Only canonical IDs are stored. Every response hydrates current public book metadata with one batched `$in` query, preserving selected order.
Unknown/missing IDs fail validation atomically; disappearing links on existing public events are omitted and reported as missing.
Editor warns that saving will remove missing links. Staff identities use one batched lookup.
The editor uses existing Search with history saving/availability restriction disabled for the picker, and its existing capabilities batch.
Search scoring, recommendation and KG remain untouched. Related cards deep-link to `/book/{work_id}`.
The real Mongo test proves twelve event rows require one book lookup and one staff lookup, rather than one query per row.

## H. Events page

Existing header Events placeholder now opens `/events`, with Upcoming/Past, category and search in URL state, backend pagination,
responsive cards, featured label, dates/location, related-book count, skeletons, distinct empty states, errors and retry.
Staff see Create/Manage links; readers do not. Requests abort or ignore stale responses on filter/account changes.

## I. Event Detail

`/events/:eventId`: title, category, summary, plain text description, local dates/location, publication date, related catalogue cards.
New Arrivals has a New this week book section. Clear cancellation message. Staff get Edit; missing/private details offer a usable error state.

## J. Staff management

`/staff/events` reuses site theme and existing Modal, with status/category/search, pagination, actor/date information,
Edit, Publish, Cancel, Archive and draft-only Delete. Archived history remains in staff list and read-only staff API detail.

## K. Create/edit/publish flow

`/staff/events/new` and `/staff/events/:eventId/edit`: bounded fields, local date inputs converted to UTC, optional location/dates,
featured checkbox, existing Search book picker, ordered selection with cover/title/author/work ID/removal and twelve-book limit.
Save Draft never publishes. Publish Now saves safely first, then requires explicit confirmation; dismissing keeps that draft.
Editing published content preserves first publication and offers Save changes. Buttons lock during requests; all lifecycle impacts have confirmations.

## L. Unseen design

One account record; window = latest 500 published events from 14 days. Cancellation/archive removes an event from unseen eligibility.
First account access initializes the exact current snapshot as baseline, suppressing historical login backlog.
Signed ten-minute receipts contain exact unseen IDs plus authenticated user/session; mark-seen validates and merges with CAS.
Equal-millisecond publications and concurrent receipts cannot hide a later event or lose another acknowledged ID.
No follower enumeration, notification inbox fan-out or count query per event; no timers/workers on the backend.

## M. Header badge

One existing navigation item; count is scoped to auth token, hidden at zero, capped visually at 9+, accessible actual count.
Desktop, tablet and existing mobile menu validated without horizontal overflow.

## N. Toast

One app-level Events monitor polls every 60 seconds while visible, plus focus, login and same-client publication refresh.
It reuses existing Toast framework with seven-second event toast and View Event link. Observed-ID set is bounded at 1000,
first poll seeds without toasts, repeated IDs do not repeat. Rapid multiple publications are coalesced to the latest small toast.
Token scope hides earlier account's event toasts immediately; abort/request guards reject late responses.
A store revision check refreshes an older poll instead of restoring a badge from before page acknowledgement.
Existing NotificationCenter's independent inbox timer/policy remains unchanged; there was no shared scheduler to reuse.

## O. Mark-seen

A successful Events page snapshot posts its signed receipt. Reading remains usable if marking fails and badge stays pending for retry.
The receipt is frozen before reading/hydrating the page, rather than using wall-clock `now`;
publications arriving during page reads or after receipt issuance remain unseen.
Opening a filtered page acknowledges that page load's recent global unseen snapshot, consistent with opening Events.

## P. Account isolation

Server identity and session binding enforce own seen state. Account A marking cannot advance B; extra user IDs and other-session receipts reject.
Frontend uses token scope on badge/toast plus abort and ownership guards; role-protected management routes remain server-authoritative.
Live checks and frontend late-response/account-switch tests pass. No real user identities or secrets are recorded in JSON evidence.

## Q. Live validation

Actual Core HTTP, Mongo, normal Vite and browser UI with four disposable identities; real catalogue books were read but never changed.
Ten API workflows plus UI creation/three Search selections/publish/detail/book link, login backlog, reader polling toast,
badge/mark-seen, mobile/tablet/desktop and management route protection. See `events_live_validation.json` and screenshots.
All marked synthetic events/accounts/seen rows were removed after validation, including published fixtures via explicit test cleanup,
without changing the product's published-delete restriction. Normal user 127.0.0.1 session was preserved by testing localhost origin.

## R. Performance

Actual localhost wall times, five samples/action, small event catalogue and existing Mongo book catalogue.

| Action | Median ms | Maximum ms | Preferred ms |
|---|---:|---:|---:|
| create_event | 12.05 | 27.82 | 500 |
| publish_event | 11.16 | 16.36 | 500 |
| unseen_count | 9.58 | 10.33 | 100 |
| published_list | 14.08 | 15.04 | 250 |
| mark_seen | 12.77 | 13.82 | 500 |
| edit_event | 13.6 | 14.41 | 500 |
| event_detail | 8.48 | 10.38 | 250 |
| staff_management_list | 14.46 | 14.57 | 250 |
| category_search_filter | 15.62 | 16.32 | 250 |

All preferred maxima met. Read batching and bounds validated. These are local V1 measurements, not a large-events stress benchmark.

## S. Backend tests

963 passed, 10 existing skips, 0 failures.
Events-specific 48 tests use disposable real Mongo databases, including expiry/concurrent publication/concurrent seen merge/batch hydration.
Production assistant/KG, staff/auth/admin, notifications, circulation, Search, book/document security/cache regressions pass.
No frozen router corpora or research suites were rerun. Fresh normal RAG startup reports existing_qwen, zero experimental modules and zero child workers.

## T. Frontend tests

219 passed: 28 Events cases + 191 existing cases across all ten production files.
Events covers routing/badges/mobile menu, URL filters, empty/error/retry, current metadata links, mutation confirmations, picker bounds,
login/online toast deduplication, role-protected deep links and late account-response isolation.
Real browser covers responsive layout; JSDOM does not claim pixel-layout validation.

## U. Build/lint

Production build PASS; 0 lint errors, 19 existing warnings.
Existing bundle >500 KB notice retained. No dependencies added or updated.

## V. Exact files changed

Project root: `D:\SDC\LibraryLLM`. Baseline hashes: `events_baseline.json`; final preservation diff: `events_file_audit.json`.
Only four existing files changed; all Events module/helpers/tests below are new. Assistant, RAG, Search, Recommendation, KG,
Admin/Notifications sources and fixed router evidence are byte-for-byte unchanged.

- `backend/main.py`
- `frontend/src/App.tsx`
- `frontend/src/components/Header.tsx`
- `frontend/src/components/Toast.tsx`
- `backend/routes/events.py`
- `backend/schemas/events.py`
- `backend/services/event_service.py`
- `frontend/src/components/events/EventMonitor.tsx`
- `frontend/src/components/events/EventUI.tsx`
- `frontend/src/lib/events.ts`
- `frontend/src/pages/EventDetailPage.tsx`
- `frontend/src/pages/EventEditorPage.tsx`
- `frontend/src/pages/Events.css`
- `frontend/src/pages/EventsPage.tsx`
- `frontend/src/pages/ManageEventsPage.tsx`
- `frontend/src/store/useEventStore.ts`
- `frontend/tests/events.test.tsx`
- `scripts/check_events_live.py`
- `scripts/events_evidence.py`
- `scripts/report_events.py`
- `scripts/start_events_core.ps1`
- `scripts/start_events_existing_services.ps1`
- `scripts/start_events_stack.ps1`
- `scripts/test_events_regressions.py`
- `tests/events/test_events.py`

## W. Known limitations and commands

Unseen badges cover fourteen days / five hundred recent published events; `count_capped` discloses window saturation.
First-ever access treats existing publications as backlog. A re-login suppresses initial toasts while retaining the account's existing unseen badge.
Opening any Events filter acknowledges the global snapshot; individual detail opening does not mark all Events seen.
There is no email/SMS, scheduled publishing, RSVP, attendance, calendar sync, ticketing, event images or commerce.
Escaped substring filtering and computed upcoming sort may scan/sort matches; there is no claim of million-event pagination performance.
Polling can delay another user's toast by up to sixty seconds; offline/hidden tabs reconcile on focus. Multiple rapid events coalesce to one latest toast.
CAS conflicts require refresh; no automatic publish retries. Plain text only. Staff UI keeps archived summaries/history; detailed archive content remains in staff API.

From a stopped stack, use separate PowerShell terminals in `D:\SDC\LibraryLLM`:

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
.venv\Scripts\python.exe -m uvicorn search.api:app --host 127.0.0.1 --port 8003
.venv\Scripts\python.exe -m uvicorn recommendation.api:app --host 127.0.0.1 --port 8004
$env:ASSISTANT_ROUTER_MODE='existing_qwen'
.venv\Scripts\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005
```

In `D:\SDC\LibraryLLM\frontend`: `npm run dev -- --host 127.0.0.1 --port 5173`.
All five normal ports already have one healthy listener. No port 8006. Events V1 complete; stop here.
