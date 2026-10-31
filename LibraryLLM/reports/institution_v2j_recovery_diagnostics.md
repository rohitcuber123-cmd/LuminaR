# Recovery evidence and decision table

| Condition | Outcome evidence | Published/last-good evidence | Safe retry / intervention |
|---|---|---|---|
| QUEUED | Known unclaimed state; no liveness proof | Pointer inspected separately | No new retry; inspect current worker/queue. |
| RUNNING/VALIDATING/PUBLISHING with valid lease | Nonterminal durable claim; process/progress unknown | Existing pointer may be retained | Do not retry/cancel from this surface. |
| Expired executing lease | Derived recovery condition while stored state stays unchanged | Check active/previous pointer and checksums explicitly | Existing explicit operator reconciliation required; never force lease expiry. |
| FAILED | Known handled failure category, safe generic summary | Last-good reference and integrity tier independent of latest attempt | Only existing manual API may recheck known retry eligibility and fresh ADMIN; CLI implements no retry. |
| RECOVERY_REQUIRED / acknowledgement uncertainty | Unknown publication outcome | Match manifest/pointer/job/dataset references; opt-in file checksums | Manual reconciliation; no blind retry/clear. |
| Missing final/temp candidate | Could be never created, renamed or missing | Presence only; no fabricated corruption diagnosis for a never-created queued artifact | Inspect job stage/outcome and other references. |
| Invalid/foreign manifest, missing expected file, checksum mismatch | Inconsistent artifact evidence | Existing pointer preserved; integrity not verified | Manual investigation, no artifact repair/promotion. |
| Pointer changes during read | Concurrent observation, not a consistent snapshot | Cannot bless old observation as current | Repeat read-only inspection. |

The current helper never calls `service.recover`, `reconcile`, `target_status`, `source_records` or artifact native validators that import write-on-import state. Existing explicit recovery semantics remain the 2I matrix: validate exact matching published-by-job/generation and reconcile SUCCEEDED versus FAILED; fence both matching owners before releasing only an eligible tagged barrier. Untagged locks and corrupt pointers without a safely recoverable job require independent operator action. No invented repair command is supplied.

Published checksum integrity is not an authoritative READY signal. Catalogue freshness, full dataset records, native FAISS equivalence and graph structure are not checked here. The tool can establish anchored file-integrity evidence within budget and show retained references; runtime usability remains NOT_DETERMINED. Last-good files/pointers are not switched or destroyed by diagnosis.
