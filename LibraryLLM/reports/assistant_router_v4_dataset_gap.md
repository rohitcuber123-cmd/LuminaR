# V4 distribution audit

Template overfitting supported by repeated politeness wrappers, synthetic focus bias, and large DEV/frozen performance gap; not a causal proof.

| Corpus | Cases | Unique messages | Skeletons | Mean words | Vocabulary | Bigram ratio |
| --- | --- | --- | --- | --- | --- | --- |
| v3 | 2635 | 2635 | 840 | 9.47 | 496 | 0.101 |
| v4 | 15162 | 1083 | 462 | 10.34 | 717 | 0.235 |
| frozen_116 | 116 | 115 | 114 | 6.59 | 267 | 0.784 |
| frozen_121 | 121 | 121 | 121 | 8.26 | 343 | 0.828 |

Authority-state and tray-size diversity improved, but single-focus remains overrepresented. Short/elliptical language and no-focus/full-pair focus states remain underrepresented; V4 did not fully resolve the V3 context-distribution defect.

Single-focus fraction: V3 80.04%, V4 85.71%. Authority-state and tray-size variation did not remove this bias. Data is 14 context expansions per utterance; lexical diversity must be assessed on unique messages. Detailed syntax, intent, reference, position and context distributions plus descriptive shared embedding clusters are in the JSON. Frozen comparisons are audit-only and never labels used for training or threshold fitting. No model was changed after frozen evaluation.


| Group | Occupied /64 | Entropy bits | Effective clusters | Largest cluster |
| --- | --- | --- | --- | --- |
| v3 | 61 | 5.685 | 51.4 | 4.17% |
| v4 | 57 | 5.518 | 45.8 | 4.89% |
| frozen_116 | 31 | 4.459 | 22.0 | 13.91% |
| frozen_121 | 32 | 4.540 | 23.3 | 11.57% |
