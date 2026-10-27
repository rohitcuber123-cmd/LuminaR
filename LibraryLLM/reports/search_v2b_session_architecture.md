# Session-aware Search

The browser stores only a random UUID, active flag and expiry in sessionStorage. The server binds the UUID to authenticated user, JWT login session, GLOBAL or exact library, and staff/patron workspace. Client IDs cannot grant access. Fresh library authorization precedes context resolution and profile access. Foreign context reuse returns 404.

Mongo search_sessions_v2b shares bounded state between the semantic service and existing core fallback. It stores current/previous deterministic plans and the last input, not a transcript or permanent interest history. A 30-minute idle and 60-minute hard lifetime is enforced on every request; Mongo TTL is cleanup only. At most 32 contexts per user, versioned compare-and-swap updates and request fingerprints bound storage and replay. Expiry is tested with a controlled clock, not a claimed real-hour browser wait.

Refinements edit fields and delegate new queries to accepted V2A parsing. Independent topics reset constraints; explicit “instead” replaces the topic while retaining filters. Smart, Genre / Subject, Title / Author and Exact remain available. KG expansion is recomputed from the current plan, never inherited as permanent session knowledge.

Clear search context deletes only the authenticated current scope. Logout preclears the account's search contexts before the existing document logout can revoke the token; backend auth logout also invalidates contexts. Login/account switch resets browser identifiers. Revoked membership invalidates the user's affected library contexts and derived profile; no stale search UI is displayed.

Expiry responses always include the explicit UTC offset. A final repeated-request browser check exposed PyMongo's naive-UTC read being serialized without an offset, which JavaScript interpreted as local time. This was corrected and covered with real Mongo replay/restore assertions; the targeted 12-case V2B suite passed again.
