# V7R0 vs V7R1 controlled comparison

The original V7R0 prompt omitted the required category enum; it is a misconfigured control, not a semantic-quality measurement.
Both runs used exactly the same 50 TRAIN passages in the same order.

Failure counts overlap. Downstream question and semantic metrics are censored when a proposal fails an earlier deterministic check.

| Metric | V7R0 original | V7R1 corrected |
|---|---:|---:|
| passages | 50 | 50 |
| raw proposals | 93 | 36 |
| zero candidate passages | 0 | 14 |
| invalid json | 1 | 0 |
| invalid category | 91 | 0 |
| invalid difficulty | 1 | 0 |
| evidence exact failures | 80 | 31 |
| evidence ambiguous occurrences | 0 | 0 |
| answer exact failures | 45 | 12 |
| question reference failures | 0 | 1 |
| deterministic passes | 0 | 0 |
| semantic unsupported | 0 | 0 |
| semantic uncertain | 0 | 0 |
| AUTO CHECKED | 0 | 0 |
