# Controlled QA comparison through V7R3

All runs used the same 50 TRAIN passages. V7R0 was a misconfigured control; counts of failure reasons can overlap.
Downstream checks are censored by earlier deterministic failures. A dash means the interface did not have that check.

| Metric | V7R0 | V7R1 | V7R2 | V7R3 |
|---|---:|---:|---:|---:|
| passages | 50 | 50 | 50 | 50 |
| raw proposals | 93 | 36 | 50 | 79 |
| zero candidate passages | 0 | 14 | 0 | 0 |
| invalid json | 1 | 0 | 1 | 0 |
| invalid category | 91 | 0 | 0 | 0 |
| invalid difficulty | 1 | 0 | 0 | 0 |
| answer completeness failures | 0 | 0 | 11 | 21 |
| question failures | 0 | 5 | 20 | 23 |
| deterministic passes | 0 | 0 | 4 | 19 |
| semantic SUPPORTED | 0 | 0 | 1 | 3 |
| semantic UNSUPPORTED | 0 | 0 | 0 | 1 |
| semantic UNCERTAIN | 0 | 0 | 3 | 15 |
| AUTO CHECKED | 0 | 0 | 1 | 3 |
| evidence failures | 80 | 31 | 0 | 0 |
| unit reference failures | — | — | 0 | 15 |
| answer presentation match failures | — | — | 23 | 0 |
| answer ambiguity | — | — | 3 | 0 |
| answer span failures | — | — | — | 27 |
| judge invalid json | — | — | — | 2 |
