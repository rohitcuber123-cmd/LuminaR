# V7R1 assisted-QA controlled rerun audit

**Gate: B. ASSISTED AUTHORING QUALITY STILL TOO LOW — REVISE GENERATION STRATEGY**

Original V7 is a frozen, misconfigured control. Its six hashes remain unchanged; the exact same 50 TRAIN passages were reused in order.
The local Qwen2.5-3B-Instruct ran greedily on CUDA in FP16, max 430 generator and 210 judge tokens; no judge inference was reached.
The fixed prompt explicitly listed nine categories and three difficulties and required exact evidence and answer substrings.

## Results

- 50 passages; 36 proposals; 14 zero-candidate passages.
- 0 invalid JSON/category/difficulty; 0 deterministic passes; 0 AUTO_CHECKED.
- 31 quotes had zero exact target-passage matches; 0 were duplicate exact matches.
- 19 of the zero-match quotes matched only after diagnostic whitespace/NFKC normalization; 12 did not. No normalization was used for acceptance.
- 12 answers were not exact substrings of their proposed evidence.
- Source hashes valid; TEST leakage 0; evaluation-span leakage 0.
- Engineering source audit: 0 AUTO_CHECKED rows to inspect; plausible 0, obvious error 0, ambiguous 0; obvious-error rate not applicable.
- Review packet rows 0; human review not started; V8–V10 not started.

The matcher had no false duplicate-quote failures. The original reason name was misleading: all 80 were absent exact strings.
The corrected category contract worked (91 → 0 invalid), but the model still usually rewrote line-wrapped source text rather than copying it exactly.
Revising the extraction strategy is required before another generation run. The <20 AUTO_CHECKED gate stops this run.
