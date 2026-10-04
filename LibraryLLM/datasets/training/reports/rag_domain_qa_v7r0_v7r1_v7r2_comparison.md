# V7R0/V7R1/V7R2 controlled QA comparison

All runs used the same 50 TRAIN passages. V7R0 was a misconfigured control; counts of failure reasons can overlap.
Downstream checks are censored by earlier deterministic failures. A dash means the interface did not have that check.

| Metric | V7R0 | V7R1 | V7R2 |
|---|---:|---:|---:|
| passages | 50 | 50 | 50 |
| raw proposals | 93 | 36 | 50 |
| zero candidate passages | 0 | 14 | 0 |
| invalid json | 1 | 0 | 1 |
| invalid category | 91 | 0 | 0 |
| invalid difficulty | 1 | 0 | 0 |
| answer completeness failures | 0 | 0 | 11 |
| question failures | 0 | 5 | 20 |
| deterministic passes | 0 | 0 | 4 |
| semantic SUPPORTED | 0 | 0 | 1 |
| semantic UNSUPPORTED | 0 | 0 | 0 |
| semantic UNCERTAIN | 0 | 0 | 3 |
| AUTO CHECKED | 0 | 0 | 1 |
| evidence failures | 80 | 31 | 0 |
| unit reference failures | — | — | 0 |
| answer presentation match failures | — | — | 23 |
| answer ambiguity | — | — | 3 |
