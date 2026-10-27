# Resume V2C-B only after this stop report

Do not start V2C-C or Part2I. V2C-B is not accepted.

1. Read current_blocker.md, stop_condition_observed.json and the failing reproducer.
2. Repair authorized() error boundaries: a missing/unissued choice is not evidence
   that current membership was revoked. Confirm authorization loss freshly before
   invalidation; an operation404 must not clear or touch accepted contexts.
3. Keep the reproducer's unchanged-context assertion. Also verify a valid pending
   choice still works after a forged request and concurrent/stale operations remain
   denied without state corruption. Run the corrected patron-to-librarian role test.
4. Freeze implementation, restart Search on the existing authoritative MongoDB,
   and rerun all required backend/frontend/browser gates. Recheck final per-item
   subject/exclusion removals against the running server, not only component tests.
5. Use new explicitly disposable QA fixtures; prior488/489 accounts are disabled and
   the V2CB Clause QA library is archived. Preserve existing evidence. Capture a fresh
   comparable after benchmark. Complete remaining acceptance without masking the
   existing STALE/degraded Global health or rebuilding HNSW/KG.

No repair was applied after the user-mandated stop in this run.
