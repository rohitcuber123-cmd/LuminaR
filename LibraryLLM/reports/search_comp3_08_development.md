# Development regression results

| Population | Typed | Execution | False execution | Missed valid |
|---|---:|---:|---:|---:|
| C5C644 (exposed) | 644/644 | 644/644 | 0/394 | 0/250 |
| c5e90 (exposed) | 90/90 | 90/90 | 0/60 | 0/30 |
| c5er150 (exposed) | 150/150 | 150/150 | 0/100 | 0/50 |
| smarteng150 (exposed) | 150/150 | 150/150 | 0/100 | 0/50 |
| Fresh independent | 92/150 | 107/150 | 25/100 | 18/50 |

All four development cohorts are exposed. None is credited as fresh evidence. Final pytest: 1515 tests, 0 failures, 0 errors. Changed C5C predictions: [search_comp3_c5c_changed_predictions.json](D:/SDC/LibraryLLM/reports/search_comp3_c5c_changed_predictions.json); each other cohort has a complete changed_predictions list in its final results. No gold was changed.

Typed and execution accuracy do not imply full semantic accuracy. C5C strict scored dimensions are 201/644; 443 contexts have at least one strict mismatch, including semantic strings, affected-field reporting and intent. No executed C5C positive has a scored hard-operand mismatch. Full failure artifacts are preserved, including the initial unsuccessful regression attempts.

**Fresh acceptance finding:** Fresh qualification failed all five parser gates despite all exposed typed/execution decisions passing. The benchmark populations differ in semantics and cannot be treated as a longitudinal improvement/regression estimate. Do not mistake development results for generalization.
