# Institution communications API

All operations use the existing authenticated core API and `/libraries/{library_id}` convention. All path identities are UUID-validated. No global or platform announcement-management endpoint exists.

| Method / suffix | Authority | Contract |
|---|---|---|
| GET /announcements | Current eligible member | PUBLISHED only; limit/offset bounded |
| GET /announcements/{announcement_id} | Current eligible member | Same library, PUBLISHED; missing/draft/withdrawn404 |
| GET /staff/announcements | Current ADMIN | Optional status DRAFT/PUBLISHED/WITHDRAWN, bounded list |
| GET /staff/announcements/{announcement_id} | Current ADMIN | Draft/history + delivery summary, no recipient IDs |
| POST /announcements | Current ADMIN |201; content + request_id; creator/ownership/history derived |
| PATCH /announcements/{announcement_id} | Current ADMIN | Full draft content + revision; conflict409 |
| POST /announcements/{announcement_id}/publish | Current ADMIN | revision; single-document durable publication; retry preserves snapshot/time |
| POST /announcements/{announcement_id}/withdraw | Current ADMIN | revision; published history retained; idempotent already-withdrawn |
| POST /announcements/{announcement_id}/delivery/retry | Current ADMIN | At most100 recipients; rest remains pending; may reset exhausted retry budget |

Content fields: title,body,category,priority,linked_event_id. Extra fields forbidden, including library_id, created_by_user_id, recipients, status, publication timestamps and arbitrary audience. Validation422, forbidden role403, concealed foreign/nonmember resource404, stale lifecycle409, existing tenant lock/recovery503. No resource existence detail crosses tenant authorization.

Publication returns `status=PUBLISHED` and a separate `delivery` state. It does not claim all notifications are delivered. Worker or bounded manual retry completes materialization. Plain-text drafts reject HTML delimiters/control characters; frontend renders text without raw HTML, auto-linking or embedded images.

Existing `/notifications`, `/notifications/unread-count`, `/notifications/{id}/read`, `/notifications/read-all`, `/{id}/action` are reused. Recipient identity always comes from the authenticated account. Aggregated inbox/read-all remain account-wide and explicitly labeled by source library, preserving established semantics. New announcement notices are hidden from list/count/detail/mark-read after current membership loss; existing generic lending-history semantics remain unchanged. Withdrawn notices retain generic copy/read state with disabled navigation; protected withdrawn content is unavailable to members.
