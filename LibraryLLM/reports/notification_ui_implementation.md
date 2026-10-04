# Admin notification UI and Select all users

Completed 2026-10-03.

The notification history now uses dashboard spacing, a styled success/error banner, readable wrapping for emails/messages and subtle inbox delivery badges. Mobile history uses stacked labelled rows. The composer has a recipient summary, search, removable compact selections, Select all users, Clear and a footer that keeps Send/Cancel visible while the content scrolls.

Select all users loads the entire eligible directory in 50-record pages, independent of the current search. Eligible means active and email-verified, matching existing delivery rules. It replaces the selection with all eligible accounts and never sends automatically. Selected IDs can be removed individually, and Clear removes the selection. The directory remains ADMIN-only and returns public account fields, count and bounded offset pagination.

Sending uses the existing protected notification endpoint with at most 50 explicit immutable user IDs per request. One request UUID and frozen recipient/message snapshot are retained across batches and retries. After a failed batch, Retry remaining resumes from the last confirmed batch. An uncertain failed response is retried with the same UUID, so existing per-recipient server dedupe prevents duplicates. Fields and selection lock after sending starts; close to compose another message. A ref guards immediate double submission. Progress reports confirmed recipients; there is no automatic send to newly registered users after selection. Multi-batch sending is not an all-or-nothing transaction.

Validation:

- Backend notification/Admin suite: 50 passed, including full directory pagination beyond 50, eligibility/private fields/authorization, bounded request validation and same-UUID bulk retries.
- Frontend notification and renewal suites: 23 passed, including selection beyond visible/search results, 73-account batching, individual removal, Clear, failed directory page preserving the previous selection and partial send retry/double-submit protection.
- Production build passed; lint has zero errors and 19 existing warnings. No new dependency.
- Normal browser login, Select all (12 eligible accounts while fixtures existed), Clear and send to two disposable readers verified. Both test deliveries appeared in styled history. No message was sent to a real account.
- Desktop1440/tablet767/mobile375 observed widths had no horizontal overflow. Composer footer remained visible at every size; mobile history layout was checked.
- Disposable accounts/messages cleaned; original users, notifications, activity, issues, reservations and fines hashes match. Temporary Vite/browser tab closed and viewport reset. Main frontend5173 remains running; Core8002 restarted with the new directory API and reminder worker enabled.

Changed source/test/config files:

- [.gitignore](D:/SDC/LibraryLLM/.gitignore): ignore private disposable fixture credentials.
- [notifications.py](D:/SDC/LibraryLLM/backend/routes/notifications.py): bounded directory offset/count response.
- [notification_service.py](D:/SDC/LibraryLLM/backend/services/notification_service.py): directory pagination/count, stable ordering.
- [AdminOperations.tsx](D:/SDC/LibraryLLM/frontend/src/pages/AdminOperations.tsx): picker, bounded bulk send/retry and history styling hooks.
- [StaffUI.tsx](D:/SDC/LibraryLLM/frontend/src/components/StaffUI.tsx): optional modal class for scoped composer layout.
- [Staff.css](D:/SDC/LibraryLLM/frontend/src/pages/Staff.css): scoped desktop/mobile history, picker and composer styles.
- [admin-notifications.test.tsx](D:/SDC/LibraryLLM/frontend/tests/admin-notifications.test.tsx): bulk selection/retry tests.
- [test_notifications.py](D:/SDC/LibraryLLM/tests/notification_ops/test_notifications.py): directory/bulk delivery tests.

Evidence: notification_ui_browser.json, notification_ui_backend_tests.log, notification_ui_frontend_tests.log, notification_ui_build.log, notification_ui_lint.log, notification_ui_select_all.png, notification_ui_composer_tablet.png, notification_ui_composer_mobile.png, notification_ui_history.png and notification_ui_history_mobile.png.

No Search, Recommendation, KG, Know More, RAG, loan renewal or due-reminder policy was changed.
