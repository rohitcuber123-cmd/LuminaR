# Publication, delivery and recovery

The publication CAS changes DRAFT to PUBLISHED, increments revision and writes the server timestamp, immutable content, recipient snapshot and initial cursor atomically in one Mongo document. No separate enqueue can be lost between domain publication and outbox creation. This is single-document atomicity, not a multi-document transaction.

The existing tenant notification worker calls the announcement adapter as part of its existing bounded materialize loop. Each adapter call scans at most10 pending publications and processes at most500 recipients overall, at most100 for one tenant slice. Existing lending delivery retains its own original limit. No new worker/thread, scheduler, queue service, WebSocket or automatic intelligence action.

For each snapshot recipient still eligible, the adapter calls notification_service.insert_notice. The dedupe key includes library_id, announcement_id, recipient_id and ANNOUNCEMENT_PUBLISHED. The original globally unique dedupe index prevents duplicates across repeated publish, concurrent workers, failed acknowledgments and process restarts. Content copies are generic; body/title stay behind the current-membership announcement endpoint.

After a slice, cursor/delivered/suppressed counters persist. If notice insertion succeeds but cursor persistence fails, replay invokes the same keys and advances once. Eligibility is checked again under the membership gate; revoked recipients are counted as suppressed. New members after publication may read existing PUBLISHED content, but the snapshot is never expanded or retroactively delivered.

Failure metadata is limited to DELIVERY_FAILED, attempts and next-attempt time. Backoff starts30s, doubles to a maximum3600s; after10 unsuccessful attempts state becomes FAILED and automatic retries stop. ADMIN manual retry resets an exhausted budget and processes one bounded slice of the original snapshot. No destructive automatic recovery or recipient reassignment.

WITHDRAWN cancels pending fan-out atomically with the domain transition. Existing generic notifications remain account-owned read receipts but resolve to an unavailable tombstone; no withdrawn body is exposed. Publication-time recipient resolution is capped at20,000 active membership records; exceeding the cap rejects before publication. Staff can inspect total/cursor/delivered/suppressed/state/error separately from publication.

An unknown-outcome create/edit/publish/withdraw exception retains the existing durable tenant lock, consistent with Institution V1. Operator reconciliation requires stopped writers and explicit existing lock recovery; this feature does not clear such locks automatically. Delivery errors are caught within the idempotent slice so routine delivery retry does not require an unsafe lock takeover.
