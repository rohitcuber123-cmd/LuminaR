# Queue and head-of-line visibility

The actual worker chooses earliest created_at QUEUED/effective_active and has no tie-breaker. It completes run_one serially. Partial unique (library_id,target) suppresses duplicate effective builds for the same target, not one build per library. Existing tenant barriers can block the oldest queued library; long builds can delay later tenants.

The authenticated operator sees database queue counts grouped over indexed known active states, up to three oldest observations, age of the oldest and up to five bounded executing/recovery observations. These are durable states, not confirmed executing processes. Global queue context intentionally carries each job's own library UUID, separately from the requested tenant's job/artifact pages. No catalogue or library-name hydration is required.

For one explicit selected queued job, an indexed aggregate counts strictly earlier timestamps and equal timestamps. Position is `[earlier+1, earlier+ties]`, with FIFO/no-tie-breaker basis. It is approximate point-in-time evidence, not a deterministic ordering promise or ETA. General history uses insertion-ID order and is labelled separately.

Head-of-line diagnosis is POTENTIAL_TENANT_BARRIER_BLOCK if a current oldest tenant barrier is observed, POTENTIAL_WAIT_BEHIND_EXECUTION_STATE if durable executing observations exist, otherwise UNKNOWN or NO_QUEUED_JOBS. A short legitimate barrier can disappear immediately; this never proves an abandoned lock. Queue age is shown numerically but no prolonged-wait threshold/SLO is invented. Persistent observations require manual investigation, not forced release, reordering, fairness scheduling or preemption.
