# J contract alternatives

| Option | Decision |
|---|---|
| A: retain exact whole-page identity | Strong detection of every byte, including harmless UX. Current guard retained pending approval; incompatible with accepted O source. Reverting O is rejected. |
| B: behavioral security invariants | Expresses role/membership, canonical scope, no automatic commands, races and isolation. Alone does not detect every source-level infrastructure addition. |
| C: narrow reviewed fingerprints | Pins tenant GET/POST transport and active-state interpretation; retains original exact backend hashes. Alone does not prove UI session or confirmation behavior. |
| D: B + C, with reviewed AST boundary | Recommended smallest appropriate combined contract. Retain three backend SHA guards; pin test helpers, protect reviewed transport, reject unreviewed page capabilities, run existing behavior suites and actual browser checks. |

Before: original backend and entire frontend page bytes must match J; all operational security tests continue separately. After proposed approval: backend bytes still exact, unchanged native protocol guard retained, helper code pinned before import, exact canonical tenant transport preserved, page imports and command locations checked with TypeScript AST. Current role/membership authority, Admin build confirmation/deduplication, Librarian read-only, General User/Platform-only denial, cross-library/session race protection, no auto rebuild/shell/operator API/secret output remain behavioral requirements.

The three transport export lines are identical in the original accepted J/O checkpoint and current O helper, fingerprint `2ea2e6e79c2d4767438a0d40442fe493838c81df20b13b6725592ee6db4dc091`. Candidate tests accept O and reject six concrete unauthorized mutations. This is a narrower contract, deliberately allowing reviewed presentation evolution. It is not a JavaScript sandbox or a substitute for reviewing future transport/store changes.

No proposed helper is installed under tests/contracts and no frozen assertion changed. `institution_v2o1_j_approval.patch` contains the complete exact change. Applying it requires the explicit approval required by Part E. Until then the original failure remains a release gate.
