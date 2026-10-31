# Evidence-based worker liveness

Existing source: `search/library_intelligence.py:TenantIntelligence.__init__/start/loop/close/run_one` and `library_intelligence_store.claim/heartbeat`. One configured local worker, 2s idle wait, 90s lease and 10s renewal. Job worker_id is recorded at claim; it is not a PID. No durable independent idle heartbeat, startup record, shutdown record or worker restart log exists.

| Classification | Evidence and limit |
|---|---|
| UNKNOWN | No executing observation, missing/future heartbeat, or only recent job renewal/lease. An idle live worker and an absent worker cannot be distinguished. |
| STALE_HEARTBEAT | An observed executing-state job has an old heartbeat or expired/missing lease. This is stale job renewal evidence, not proof that the process died. |
| DEGRADED | Unresolved recovery or competing executing-state observations in the configured serial architecture. It describes operational inconsistency, not process death. |
| HEALTHY | Deliberately never emitted: current data cannot prove live healthy execution. |

Recent means within 30 seconds (three existing renewal intervals), explicitly a diagnostic window, not a new lease rule/SLO. Valid lease alone never produces HEALTHY. Heartbeats ahead of observation time are CLOCK_SKEW, not recent healthy evidence. Observation end time is used after reads so a normal concurrent heartbeat is not mistaken for a future event.

Canonical `tenant-{UUID}` worker IDs are exposed only as stable hashed correlation references. Different recorded owners can be inspected, but restart time/process identity remains NOT_AVAILABLE. Legacy/arbitrary owner strings are not echoed. Real process CPU/RAM and startup/shutdown/restart require a separately approved independent telemetry mechanism; no worker or job field is changed in this phase.
