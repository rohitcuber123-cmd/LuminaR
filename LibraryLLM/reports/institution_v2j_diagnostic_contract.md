# Read-only diagnostic contract

Schema `tenant-intelligence-diagnostics-v1`. Required canonical library UUID; optional explicit job UUID, state filters, keyset cursor and limits. Output separates observed facts, derived conditions and unavailable information. It never determines authoritative catalogue freshness or runtime READY.

| Output | Meaning |
|---|---|
| jobs / selected_job | Scoped durable job whitelist; enums, IDs, actual counters, times, lease evidence and safe failure categories. No raw error strings, fences or paths. |
| tenant_active_jobs | Up to two current effective-active target jobs for the requested tenant, independent of history filtering. |
| worker | Database-wide resident-worker job observations; process_alive/startup/shutdown/restart remain UNKNOWN/NOT_AVAILABLE. Canonical recorded worker IDs are one-way correlation references, not PIDs or proof of liveness. |
| queue | Explicitly authorized database queue context: exact count at query time, up to three oldest observations, age, executing-state count and selected job position range. Other tenant UUIDs here are intentional operator context, never ordinary Staff output. |
| targets | Separate stored state, active/previous references, bounded latest observed attempt, checksum evidence and manual-investigation flag. created_at ties are flagged; latest observed is not guaranteed complete history. |
| artifacts | Bounded namespace references, presence, manifests, associations, known-file sizes and verification level/coverage. Missing candidate may mean never created, renamed or lost; no guessed failure outcome. |
| resources | Actual local-volume disk observation if available; worker CPU/RAM/GPU NOT_AVAILABLE without a trustworthy PID mapping. |
| actions_available | Always empty. |

No durable health states are added. Zero work counters do not imply failure; full counters do not imply publication. Heartbeat, progress, state transition and publication acknowledgement are distinct. queued_at uses created_at with its basis stated. There is no existing last_updated or last_progress timestamp: output is NOT_AVAILABLE/UNKNOWN rather than an invented time.

Mongo reads are best effort on standalone Mongo, not a transactional snapshot. Observation start/end times are returned; pointers are read again and a change makes verification inconclusive. Job/counter/count observations can also change during the window. Repeat inspection rather than acting from a stale diagnostic. No read snapshot becomes authoritative over membership, jobs or generation state.

Default job page 20, max 50, one library and known state filters. Cursor is library/filter-bound, based on insertion ObjectId descending (not FIFO created_at); foreign/malformed cursors are rejected. Exact job lookup uses job_id_1. Default history uses the existing _id index and can examine extra foreign rows in sparse histories; one-second Mongo operation limits and a 1–30 second invocation budget fail closed. A future dedicated history index requires independent review; the command creates none.

Artifact enumeration default 20 entries per Search/KG directory, max 50, plus bounded prioritized references (max limit+2 candidates per target). Each manifest is at most 64 KiB; fixed expected filenames only. No global recursion. Default checksums OFF. Explicit verification uses a shared default 16 MiB, max 256 MiB byte budget and the same deadline. Reads never exceed the originally statted file length; growth/mtime/identity changes become inconclusive and partially read bytes count against the budget. OS calls on failing storage are not forcibly preemptible; deadlines are checked between bounded operations/chunks.

## Executed diagnostic costs

| Historical jobs | Median ms | p95 ms | Docs examined, profiled read | Catalogue queries | Output bytes max |
|---:|---:|---:|---:|---:|---:|
| 0 | 13.789 | 17.359 | 0 | 0 | 5,089 |
| 1 | 13.880 | 20.317 | 2 | 0 | 9,297 |
| 100 | 32.633 | 40.792 | 41 | 0 | 49,751 |
| 1,000 | 30.780 | 40.817 | 41 | 0 | 49,751 |
| 10,000 | 32.718 | 37.297 | 41 | 0 | 49,751 |

Real auth-enabled isolated Mongo, default 20-row page and bounded metadata/no catalogue access. Service timings exclude connect/auth setup; fresh process CLI wall time includes it. CPU, tracemalloc, cold process and four-invocation concurrency details are in the performance JSON. No production SLO is asserted.
