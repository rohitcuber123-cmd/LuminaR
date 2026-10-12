# Recommended next tenancy phase

Recommend Events + Notifications tenancy next, subject to explicit approval. This is based on the repository's remaining global dependencies, not an assumed roadmap.

- backend/routes/events.py: staff() authorizes global ADMIN/LIBRARIAN and routes live at /staff/events. No library UUID reaches the service.
- backend/services/event_service.py: event records/indexes and event_seen state are global event_id/user_id based. Publication visibility and seen receipts have no canonical institution audience.
- backend/routes/notifications.py: admin() checks global ADMIN; /admin operations and recipients are global-account scoped.
- backend/services/notification_service.py: list_own() queries only user_id; insert_notice() and dedupe keys omit library_id; scan_due() consumes legacy integer issues; notify_reservation_available() uses legacy reservation/work identities and pickup wording.
- backend/services/notification_worker.py calls that legacy notification service. It cannot safely deliver canonical queue-converted or loan-fee events with tenant audience rules.

Part 2C already creates durable reservation/fee audit intents. The most useful next bridge is a separate durable tenant notification outbox keyed by library UUID, canonical source UUID and event identity, with current audience validation. Preserve library labels in a member's combined inbox and prevent a global staff role from sending tenant notices without membership. Make queue alerts describe borrow approval and the Part 2B hold deadline.

Start with tenant ownership/audience models, proven legacy migration/quarantine, per-library cutover and notification deduplication. Then integrate canonical circulation/queue/fee events. Email/push channels follow only after tenant in-app delivery is correct. Admin analytics remains global and should be scoped later against canonical data; digital asset/RAG tenancy, Search overlays and Recommendation awareness require separate authorized phases.

No Events, Notifications, analytics, retrieval or recommendation implementation was changed in Part 2C. Stop here and wait for explicit user approval for the next phase.
