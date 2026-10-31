# Supervised maintenance design — inactive

| Candidate policy | Correctness/cost/operational tradeoff |
|---|---|
| Manual only (current) | Exact Admin intent and existing durable infrastructure; no surprise load, but stale generations can persist unnoticed. |
| Admin-approved pending rebuild | Recommend next: explicitly review authoritative stale signal, exact source/target generation, cost/budget and authority before creating the existing manual job. Needs stale-intent versioning and clear approval invalidation; avoids silently scheduling work. |
| Scheduled window | Predictable contention period but requires approved timezone/window/missed-run semantics, budget reservation, authority rechecks and recovery suppression. Not implemented. |
| Debounced automatic | Quiet-period batching lowers repeated work; races with continuous changes, approval lifecycle, costs and expired ownership need proof. Not implemented. |
| Threshold based | Can protect small updates or large imports differently, but mutation count alone does not estimate embedding/cache/KG work or guarantee relevance/freshness. Not implemented. |
| Hybrid supervised | Admin approves a bounded target/source/budget intent with a later window; more flexible but more complex persistence/restart/permission semantics. Separate phase. |

For 100 indexed books → import 500 → 20 metadata edits → import 100, never create a job per mutation. Recommend a single target-scoped reviewable pending intention after a quiet period for presentation, with a maximum-wait alert during continuous mutation, explicit Admin approval and fresh admission before request. Search and KG remain independent; a changed source after approval invalidates or explicitly refreshes the approved intent. No intent persistence or timer was added here.

Required future facts: authoritative current vs published fingerprints/revisions, which fields changed, last relevant mutation time, count/volume and estimated missing embeddings/graph work, exact approval identity/scope/expiry, active/queued jobs, resource reservation and recovery flags. Existing dataset sequence is NOT a mutation revision. All mutation paths including imports/replay/global enrichment must participate before using revision-driven triggers. Large tenants/frequent mutations need aging and budgets; small tenants may finish before progress is observed. Any recovery-required outcome suppresses automatic creation until explicit reconciliation.

Before automation: complete mutation contract, freshness/race/restart proof, calibrated resource/admission and tenant fairness, operator liveness/recovery/retention observability, idempotent approvals/triggers/audits, security revocation tests, last-good crash consistency and workload/query-contention evidence. No automatic/scheduled policy is activated by this design.
