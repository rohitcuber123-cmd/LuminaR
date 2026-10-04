# V7 assisted QA pilot audit

Experimental only; no human review or training approval.

Decision: **ASSISTED AUTHORING PILOT STILL TOO LOW QUALITY**

- TRAIN passages: 50
- Raw proposals: 93
- AUTO_CHECKED: 0
- Rejected records: 94
- Format failures: 1
- TEST/evaluation span leakage: 0/0

## Rejection reasons

- INVALID_CATEGORY: 91
- EVIDENCE_NOT_UNIQUE_EXACT_IN_POSITIVE: 80
- ANSWER_NOT_EXACT_IN_EVIDENCE: 45
- INVALID_GENERATOR_JSON: 1
- INVALID_DIFFICULTY: 1

The generator used free-form category labels because the initial prompt omitted the required enum.
It also often paraphrased the evidence rather than copying an exact source substring.
The prompt has been corrected in code, but this fixed pilot was not rerun or relabeled.
The <20 AUTO_CHECKED stop gate applies; no review packet, V8, V9, or V10 was produced.
