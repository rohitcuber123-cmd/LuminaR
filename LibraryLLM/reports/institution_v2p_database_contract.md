# Announcement persistence contract

`institution_announcements` is the only new domain collection. Existing `events`, `notifications`, memberships and invitation collections are reused. There is no duplicate unread store or bell.

| Field | Type | Authority / purpose |
|---|---|---|
| announcement_id | canonical UUID string | Server identity, globally unique |
| library_id | canonical UUID string | Route + current membership; immutable |
| created_by_user_id | integer | Current server identity; immutable |
| updated_by_user_id / published_by_user_id / withdrawn_by_user_id | integer / nullable | Server actor history; staff-only serialization |
| request_id | UUID string | Draft-create retry identity scoped to library and creator |
| title / body | plain text ≤140 / ≤5000 | Validated input; no HTML or rich-text execution |
| category | GENERAL / EVENT / LIBRARY_UPDATE / IMPORTANT_NOTICE | Presentation only |
| priority | NORMAL / IMPORTANT | Presentation only; never changes authority |
| status | DRAFT / PUBLISHED / WITHDRAWN | Server state machine |
| revision | integer | Optimistic concurrency for edit/publish/withdraw |
| linked_event_id | optional UUID | Existing event in the same library; publish requires published/cancelled historical event |
| audience | ALL_ACTIVE_MEMBERS | Server constant; no submitted recipients |
| created_at / updated_at / published_at / withdrawn_at | UTC timestamps | Server clock only; publication remains original |
| delivery.recipients | bounded integer array ≤20,000 | Publication-time eligible membership snapshot; never serialized to public/staff UI |
| delivery.state | NOT_PUBLISHED / PENDING / COMPLETE / FAILED / CANCELLED | Separate from publication status |
| delivery.total / cursor / delivered / suppressed | integers | Durable bounded progress; no inferred success |
| delivery.attempts / last_error_code / next_attempt_at | bounded attempts / safe code / UTC | Restart-safe backoff; no exception strings |

Required indexes implemented by `library_announcement_service.ensure_indexes`: unique announcement_id; unique (library_id, created_by_user_id, request_id); (library_id,status,published_at desc,announcement_id); (delivery.state,delivery.next_attempt_at,published_at). Shared notification query index: (user_id,scope,library_id,read_at,created_at desc). Existing global unique dedupe_key index is retained.

Indexes are created at normal application startup, matching existing architecture. An empty new announcement collection/index set appeared in the default database during the task window. Its initiating process was not conclusively attributed. It was verified against the absent baseline and exact new schema, then removed while empty. Later, concurrent application activity created a real announcement in the existing TEST library under existing creator4; that populated namespace and its indexes are retained. The final regression runner also establishes an owned fallback database/session scope before legacy imports. The shared notification compound index may have initialized during startup; no pre-task global-notification-index snapshot exists, so equality is not claimed for that set. See preservation_adjustment.json and concurrent_activity.json. No authentication cutover or deployment was performed.

The observed notification count increased50→54: one valid existing-system overdue reminder and three copies of the concurrent TEST-library announcement. All were retained. Excluding these new IDs, the original50-document digest matches the immutable baseline. One old pending borrow request expired through the existing committed actor0 journal; substituting its exact original creation receipt in memory reproduces the baseline hash, without a database reversal. Original audit/operation rows, events, loans, reservations and all original institution index definitions remain preserved. Raw database equality is deliberately not claimed while valid live activity continues.

Member and staff listing limit is 1–50, default20; offset0–10,000. Member queries always include library_id/status PUBLISHED; staff queries always include library_id. Audience resolution and delivery eligibility are batched over canonical user IDs and accepted invitation proofs. Recipient arrays are not loaded into browser memory. Publishing above the membership cap rejects before the atomic publication write; larger distribution requires a separately reviewed paginated-snapshot design.
