# Assistant mutation safety

Reading-list add/remove previously called Core immediately. They now reuse the existing pending action, Confirm and Cancel routes.
There is no second confirmation subsystem. Book Detail and ordinary reading-list buttons continue using their unchanged direct Core routes.
Buttons inside the assistant propose changes and require confirmation.

Pending state belongs to a server-derived `sub:sid` conversation owner. The response exposes a random action ID, canonical `work_id`,
canonical batch `work_ids`, confirmation flag and five-minute expiry. Titles are display-only. PendingAction is frozen and batch IDs
are tuples; selections or request action_work_ids at confirmation cannot replace stored targets.

Every normal new assistant turn invalidates the previous proposal. Confirm/Cancel require both the matching pending ID and owning
conversation. Wrong account/session returns private 404; a wrong conversation cannot execute. Expiry clears pending state. Cancel
invalidates all pending fields and writes nothing. Confirmation enters the deterministic branch before routing; zero Qwen calls.

Confirm revalidates the authenticated session via existing dependencies, all stored catalogue IDs before any batch write, and current
reading-list membership. Add-already-present / remove-now-absent are successful no-op responses. Core's unchanged unique user/work
index, upsert and delete-one retain idempotence under races. An action is consumed before Core calls; timeouts are never automatically
replayed. Batch execution is not transactional: a failure after an earlier successful item may leave a partial result, reported as an error.
Recheck the list before explicitly asking again.

Saved-list editing remains available independently of the existing circulation-write feature flag. Borrow, return and reserve retain
their original flag and confirmation gates. Clear still requires its dedicated explicit assistant UI action. No Core endpoint or normal
frontend reading-list behavior was changed.

Live validation used two disposable, verified test identities and real HTTP/Core catalogue/list endpoints. All 12 scenarios passed;
all eight natural mutation prompts produced pending actions. No write before confirmation, Cancel retained the book, Confirm wrote
the stored target once, replay failed, selection B did not retarget A, wrong user/session returned 404, no-op revalidation succeeded,
and unrelated turns invalidated pending actions. Every confirmation/cancellation used zero Qwen calls. Test identities/list records
were removed in finally. Numeric live evidence: `assistant_production_live.json`.

TTL, concurrent double-confirm, failed catalogue validation, no automatic retry, immutable batch targets and authorization were also
checked with write spies. Existing borrow/return/reserve, explicit Clear and assistant security suites pass.

Limits: in-memory, bounded, single-process conversation storage; restart loses proposals. Multi-instance deployment needs shared state
or sticky sessions. The inherited TTL is 30 minutes per conversation and five minutes per pending action. No additional guarantees
are claimed for natural-language reference resolution beyond the logged production smokes.
