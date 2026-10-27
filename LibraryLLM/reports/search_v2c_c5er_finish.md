# V2C-C.5E-R — Final Semantic Parser Recovery and Fresh Independent Validation Report

## Executive Summary

- **Outcome**: `PARTIAL`
- **C5F Readiness**: `BLOCKED` (`C5F_READY=False`)
- **Candidate Selected**: `search-v2c-c5er-disabled-candidate-4` (Candidate V4)
- **Candidate Activation**: `DISABLED` (Current production parser and C4 policy remain untouched)

## Key Results by Evaluation Cohort

| Evaluation Cohort | Population Size | Typed Accuracy | Execution Accuracy | False Executions | Missed Executions |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A. C5C Development** | 644 | 644/644 (100.00%) | 644/644 (100.00%) | 0/394 (0.00%) | 0/250 (0.00%) |
| **B. Exposed Historical C5E** | 90 | 90/90 (100.00%) | 90/90 (100.00%) | 0/60 (0.00%) | 0/30 (0.00%) |
| **C. Fresh Independent Acceptance** | 150 | 57/150 (38.00%) | 97/150 (64.67%) | 8/100 (8.00%) | 45/50 (90.00%) |

## Regression and Native Validation

- **Development Regressions**: 1,418 / 1,418 test assertions passed (`regression_v4/test_generalized_ledger.py` etc.).
- **Evaluation Adapter V2**: 16 / 16 unit tests passed (`test_evaluation_adapter_v2.py`).
- **Offline Native Components**: 40 / 40 checks passed (`PASS_WITH_LIMITED_QUALIFICATION`).
- **Private Library Independence**: Verified; searches own unlinked books with empty global fixture.
- **Structural Isolation**: `PASS` (0 collisions detected against heldout and baseline).
- **Protected File Verification**: 2040 / 2040 files verified unchanged with SHA256 hashes.

## Remaining Blockers for C5F

1. **False-Execution Gate**: Observed 8/100 (8.00%) false executions in fresh independent ambiguous cases (cases: `C5ER_A01_*`, `C5ER_A02_*` across tenant scopes). Pre-registered safety threshold requires 0 false executions.
2. **Missed-Execution Rate**: Observed 45/50 (90.00%) missed executions on fresh independent executable queries.
3. **Typed Accuracy**: 57/150 (38.00%) on fresh independent acceptance cohort.

## Preservation Guarantees

- Production parser: **UNCHANGED**
- Active C4 policy: **UNCHANGED**
- Production Mongo database: **ZERO MUTATIONS**
- Sealed heldout examples: **0 EVALUATIONS / UNACCESSED**
- HNSW / KG indexes: **ZERO REBUILDS**
- Historical C5A-C5E evidence: **100% PRESERVED & VERIFIED**
