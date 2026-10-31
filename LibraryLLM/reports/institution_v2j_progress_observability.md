# Heartbeat versus progress

Existing heartbeat updates heartbeat_at/lease_expires_at every ten seconds while a valid job lease remains. Existing progress updates stage/state/counters but does not persist a last-progress timestamp. Existing audit events record request/outcome, not a durable intermediate progress history. None is sufficient to reconstruct progress recency.

The output therefore distinguishes recent/stale/missing/future job heartbeat from `progress.recency=UNKNOWN` and `last_progress_at=NOT_AVAILABLE`. Missing last_updated is not replaced with heartbeat time. Stage text/counters are real durable observations; a long embedding/native index call may make no counter update while renewal continues. A terminal counter is not acknowledgement of validated pointer publication.

No new timestamp field, stage history, worker heartbeat document or UI badge was added. Proving stalled progress would require a separately approved telemetry contract with fencing/backward compatibility and race tests. This phase reports the uncertainty rather than claiming stopped or healthy progress.
