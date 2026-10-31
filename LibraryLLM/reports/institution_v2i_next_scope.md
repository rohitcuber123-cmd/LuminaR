# Recommended next phase

Part 2J: an operator-only, read-only worker liveness and recovery diagnostic surface, designed against current jobs/leases/tagged barriers, with no automatic action. First obtain review of this Part 2I evidence and baseline failures. Specify idle liveness, heartbeat-vs-progress semantics, bounded same-tenant lifecycle/reconciliation views, safe operational access and audit. Use it to qualify resource/admission estimates before considering an Admin-approved pending rebuild workflow.

Automatic/scheduled maintenance, cancellation, retention deletion, incremental HNSW/KG, multiple workers and global controls remain separately gated future proposals. No later-phase implementation begins in this task.
