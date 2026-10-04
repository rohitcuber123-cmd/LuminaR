# Frozen V4 → V5 source replay

This is regression evidence, not a new probe.

Old HIGH: 27; transitions: `{'DOWNGRADED_MEDIUM': 20, 'STILL_HIGH': 7}`

| Family | Old | Blocked upstream | Validator rejects | Still auto-validates |
|---|---:|---:|---:|---:|
| STATEMENT_FRAGMENT | 14 | 14 | 0 | 0 |
| CLEAN_REFERENCE | 7 | 0 | 0 | 7 |
| ACTION_CONTEXT | 1 | 1 | 0 | 0 |
| STATEMENT_TOPIC | 4 | 4 | 0 | 0 |
| DISCOURSE_DEPENDENCY | 1 | 1 | 0 | 0 |

Known failed V4 propositions still auto-validating: **0**.
