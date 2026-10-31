# Durable job inspection

Actual fields: job_id/library_id/target, state, stage, progress_current/total, attempt, created_at, started_at, heartbeat_at, completed_at, lease_expires_at, effective_active, artifact_generation_id, requested_generation_id, worker_id and error_code. Fences, raw worker IDs/error messages and user/account data are not output. State/stage/failure values are whitelisted; malformed values become UNKNOWN/OTHER/BUILD_FAILED. Numeric counters must be bounded actual integers.

The command returns scoped history (20 default/50 maximum), an optional scoped selected job, and separately scoped effective-active jobs, so a FAILED history filter cannot hide a running/recovery attempt. Job_id lookup is bound to library UUID. A foreign job UUID produces SCOPED_JOB_NOT_FOUND. Insertion-ID keyset pagination avoids unbounded offset and does not pretend to be the worker's FIFO ordering.

Queued time is explicitly derived from created_at. Duration is a completed interval for known SUCCEEDED/FAILED jobs or an elapsed observation for other started jobs. Missing fields on old jobs stay readable and are NOT_AVAILABLE. There is no fabricated last updated/progress timestamp or percentage. State SUCCEEDED is an acknowledged durable fact; progress counters alone never imply success. Published target references remain separate from attempts and do not prove serving eligibility.

Only the bounded observed page/selected/current active jobs inform latest observed attempt. Timestamp ties are flagged rather than promising a unique latest identity. No complete history claim is made. No job is acquired, renewed, requeued, recovered, cancelled, edited or removed by inspection.
