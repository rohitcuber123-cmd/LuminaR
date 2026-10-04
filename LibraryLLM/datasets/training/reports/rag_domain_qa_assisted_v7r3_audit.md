# V7R3 engineering source audit

Current gate: A. V7R3 IMPLEMENTATION CONTRACT FAILED — FIX PIPELINE

All AUTO_CHECKED candidates were audited against their authoritative source.

AUTO_CHECKED: 3
Plausible: 1
Obvious semantic errors: 2
Ambiguous: 0
Review packet gate: FAIL

No human review has occurred.

- AQA7R3-012-1: PLAUSIBLE_FOR_HUMAN_REVIEW (None) — The selected evidence explicitly identifies the guns brought from Woolwich and Chatham to cover Kingston.
- AQA7R3-032-2: OBVIOUS_SEMANTIC_ERROR (BAD_CATEGORY) — The question asks for direct speaker identification, but Stage A labeled the fact EVENT.
- AQA7R3-034-2: OBVIOUS_SEMANTIC_ERROR (ANSWER_SELECTION_ERROR) — The answer span includes 'ago' before 'in London'; a WHERE question requires the location, not the trailing time word. OTHER_EXPLICIT let this wrong type escape deterministic checks.
