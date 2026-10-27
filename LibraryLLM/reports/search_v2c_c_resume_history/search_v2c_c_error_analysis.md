# V2C-C mandatory stop

An active private patron with an accepted Search context and pending clarification requests `/query/suggestions?staff=true` in the same library. HTTP403 is correct. Both patron documents are then deleted, while GENERAL_USER membership remains ACTIVE.

The existing helper `search/scope_authorization.py` freshly checks only the requested STAFF workspace. On403 it calls library-wide invalidation. `search/session_store.py` filters by user/library but omits workspace, so permitted PATRON state is deleted as collateral. This differs from the repaired forged-choice404 bug: here authorization genuinely denies one workspace, but cleanup reaches another permitted workspace.

Full real authoritative Mongo before/after: `search_v2c_c_preflight_security.json`. Independently reproduced against isolated Mongo by `tests/institution_v2g/test_query_v2c_c_stop_condition.py`; its unchanged-state assertion fails. No private content was returned by this request.

User prompt section35 explicitly requires STOP if session corruption reappears. No corrective production patch was applied. No further benchmark tuning, held-out evaluation, full regression, browser acceptance or performance run is claimed. The8003 running service remains the prior accepted code; draft C runtime integration was removed.

Proposed next repair: distinguish requested-workspace denial from actual whole-library access loss. Preserve still-authorized workspace contexts and pending choices. Clear only inaccessible workspace state on role/permission changes, and preserve full affected-library cleanup for actual revocation. Verify both directions of patron/staff denial, role changes, cross-workspace forged choices, revocation and concurrency before resuming C.
