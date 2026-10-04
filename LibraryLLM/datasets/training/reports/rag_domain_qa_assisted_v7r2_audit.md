# V7R2 source-referenced assisted-QA audit

**Current gate: B. V7R2 GENERATOR SEMANTICS STILL TOO LOW QUALITY — CHANGE GENERATOR APPROACH**

V7R0 and V7R1 remain frozen. V7R2 used the exact same 50 TRAIN passages in the same order.
All 50 presentation views and 331 source units passed round-trip, offset, and hash checks.
The generator returned source unit IDs, never authoritative evidence text. Code reconstructed evidence and mapped answer spans back to source.

## Pilot results

- Raw proposals: 50; invalid JSON: 1; zero-candidate passages: 0.
- Evidence/source integrity failures: 0; unit-reference failures: 0.
- Answer not exact in selected presentation unit: 23; ambiguous answer occurrences: 3.
- Deterministic passes: 4; semantic SUPPORTED/UNSUPPORTED/UNCERTAIN: 1/0/3.
- AUTO_CHECKED: 1; engineering audit plausible/obvious/ambiguous: 1/0/0; obvious-error rate: 0.0.
- TEST/evaluation leakage: 0/0; source hashes valid; production snapshot unchanged (64 files).
- Review packet rows: 0; human review not started; V8–V10 not started.

The source-reference interface solved exact evidence copying, but the model still often produced answer_text that was not an exact substring of its chosen unit, alongside question/reference and answer-type errors.
With fewer than 20 AUTO_CHECKED candidates, the run stops before a human review packet.
