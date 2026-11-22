# Shared notification lifecycle

One existing account-wide aggregated bell, existing notifications collection and read_at state. Existing types and generic tenant-history privacy contract remain. New type ANNOUNCEMENT_PUBLISHED uses scope LIBRARY, audience MEMBER and canonical source_id/source_type announcement.

The server reconstructs `/libraries/{library_id}/announcements/{announcement_id}` from typed source identities and a currently published record. An arbitrary persisted action_route is never a navigation authority. The client separately checks type, audience, UUID source identity and exact source-library path before navigation. Fresh action resolution occurs before following a bell item.

List/count/unread/read-one/read-all/detail filter the new private type by current eligible membership. Revocation, private outsider, invalid accepted-invitation proof, disabled account and inactive library cannot expose the private copy or inflate its unread count. Other users cannot mark/read a notice. No query accepts recipient identity. Repeated mark-read preserves its first timestamp; read-all uses the original timestamp cutoff. Account-wide read-all across eligible libraries is deliberate and consistent with the existing aggregated inbox.

Withdrawn/missing source produces a generic unavailable notice with no navigation; it can still be marked read. Unread means unread notification copy, not number of still-published announcements. No private body is stored in that copy.

Existing45s polling and focus/visibility refresh remain. Read mutations refresh immediately; another tab refreshes on focus or the existing polling interval. New-type IMPORTANT priority is presented in the shared bell without a second counter. No production telemetry or external delivery channel is activated.
