# Persistent in-app notifications

A. Storage: Mongo notifications, one document per canonical recipient user_id. See notification_schema.json; no email ownership.

B. Indexes: unique notification_id/dedupe_key; owner+created_at+ID; owner+read_at; sender+created_at; source+created_at+ID. Supporting issues(status,due_date) and activity owner/work/global chronology indexes. Exact installed inventory: admin_notification_indexes.json.

C. Types: ADMIN_MESSAGE, DUE_SOON, DUE_TODAY, OVERDUE. No speculative reservation/renewal types.

D. Admin flow: Operations row Notify User or Notifications tab New notification opens a recipient picker, bounded plain-text title/message and Send. Backend validates every account, resolves email to canonical ID, then persists. Success means STORED; no external/push transport guarantee. Sent audit displays recipient current email, Admin sender, timestamp and stored status.

E. Multiple selected accounts: supported, up to50 unique canonical recipients; deduplicates ID/email selections. One request UUID provides retry idempotency per sender/recipient. All validation precedes writes; transport/DB failure after some writes may be partial, retry converges by dedupe keys.

F. Broadcast: optional and skipped. No broadcast endpoint/button.

G. Header bell: all authenticated roles see their own badge and notification center. Persistent bounded20-item pages, newest first, empty/error/retry states, Escape/close focus restoration. Mobile panel and scrolling reserve space for the existing assistant launcher.

H. Toast: non-blocking role=status,8-second auto-dismiss or close; one toast per observed ID per active session, consolidated for multiple arrivals. Closing leaves the durable inbox entry. Initial login backlog is silent. No browser popup/alert for a notification.

I. Polling: visible-session refresh every45seconds, focus/visibility/login/read/bell refresh; at most one in-flight poll with pending follow-up, AbortController and account/token scope guard. An offline tab learns new notices after reconnect/focus. This is bounded polling, not server push/WebSockets.

J. Read state: own ID AND user_id query for PATCH /notifications/{id}/read; private404 for another owner/missing ID. Existing read_at remains stable. POST /notifications/read-all uses an invocation cutoff so later concurrent notices stay unread. GET /notifications/unread-count is indexed. All state persists through refresh/logout/login/Core restart.

K. Due rules: exactly two UTC calendar days before due = DUE_SOON; due UTC calendar day = DUE_TODAY; past UTC calendar day = OVERDUE. One-day-before has no new kind. Returned loans excluded.

L. Dates: existing Mongo datetimes are naive UTC on read. New API dates normalize to explicit UTC offsets; browser displays local time. Reminder day rules reuse UTC calendar-day semantics of current fine calculations without changing fine amounts or the existing Profile timestamp styling.

M. Dedupe: TYPE:loan_id:normalized_due_timestamp, unique DB key and atomic setOnInsert. One initial overdue per due version; no daily replay. Admin message uses sender/request UUID/recipient. Repeated and four parallel scans produce one stored reminder.

N. Worker: Core FastAPI lifespan thread, immediate scan then configurable60-minute interruptible wait; minimum5minutes. Streaming relevant ISSUED due-range query, batch500; exact source state rechecked before insert. Clean stop; safe counts/duration/failure-code logs and retry on next interval. Configuration and results: notification_due_worker.json.

O. Catch-up: only current meaningful state. A long-overdue loan gets one OVERDUE, without retroactive soon/today alerts or a backlog of overdue intervals. Changes to future due dates prevent a new old-version overdue notice. Existing historical notice remains visible.

P. Reservations: optional alerts deferred; no invented pickup expiry or false ready transition. Existing circulation behavior remains.

Q. Retention: no TTL/premature deletion or delete API. Indefinite V1 retention pending an explicit archival policy.

R. Security: JWT plus current DB role/account validation. Non-Admin cannot directory-search, drill down, send, audit, or assisted-return via new APIs. Readers/Librarians only their own inbox. No stored credential/hash/JWT fields exposed; plain React text prevents payload execution. Role matrix/tests: notification_security.json. Separate token/user storage-event reconciliation was debounced to fix the genuine multi-tab account-switch integration race discovered during live validation.

S. Validation:48 isolated real-Mongo feature tests,76 existing auth tests,385 passing broader backend regressions with one known untouched BookRAG failure;170 distinct frontend cases passing across target suites. Disposable Admin/Alice/Bob live flow verified attribution, changed email, owner isolation, read state, refresh/relogin, multi-send, three due states and zero repeat duplicates. Responsive operations/composer/inbox/toast checked at requested1440x900,1366x768,768x1024,375x812 (native viewport rounding recorded). Test records removed with original account/circulation/inventory hashes and book count matching. See live/browser/performance reports.

T. Limits: Core must run for scheduling; no separate durable scheduler. Small live activity dataset, no million-event capacity benchmark. Multi-recipient writes are retry-safe but not a cross-document transaction. A concurrent return can race between final source check and notice insert. Toast seen-ID memory is retained for the active session. Already stored notices stay after return/due change. No existing renewal API. Broadcast/reservation alerts and email/SMS/mobile/cloud push remain out of scope. Search/recommendation/KG/BookRAG/DocumentRAG/private-cache source hashes and frozen KG artifact match baseline.
