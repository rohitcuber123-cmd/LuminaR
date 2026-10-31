# Standalone V8 local learned-extractor experiment

The cached Qwen2.5-3B-Instruct model **loaded successfully** on attempt3 using installed Accelerate per-shard BF16 dispatch. Two real DEVELOPMENT outputs were captured; both failed schema/source validation. The comparison remains **incomplete and unqualified**. Retain the frozen7r1 deterministic proof architecture for continued disabled development. Production readiness is **BLOCKED**.

## Scope and evidence

The user clarified that this addendum is standalone and that a separate prompt will follow. No unseen baseV8 semantic requirements were assumed. Frozen7r1 is the deterministic control, carried forward without semantic edits. Candidate `search-smarteng-disabled-proof-8-local` is disabled. Pinned Qwen revision `aa8e72537993ba99e69dfaafa59ed015b17504d1`, nine cached files, runtime versions, prompt, ontology, schema, proof, source, scorer and population were frozen before capture in `search_proof8a3_comparison_freeze.json` and `search_proof8a3_configuration.json`. No downloads or training occurred.

## Measured attempts and resource gate

| Attempt | Result | Tree RAM peak | Model outputs |
|---|---|---:|---:|
| 1 | RAM_BUDGET_EXCEEDED | 4,392,308,736 bytes | 0 |
| 2 | RAM_BUDGET_EXCEEDED | 6,186,856,448 bytes | 0 |
| 3 | QUERY_HARD_TIMEOUT after successful load | 4,819,132,416 bytes | 2 |

Attempt1 used a4GiB RAM cap; attempt2 used5.75GiB with sequential Transformers loading. The installed loader retained mmap handles for both shards. Attempt3 used installed Accelerate1.14.0 meta initialization and per-shard GPU dispatch of the same unmodified BF16 weights within the5.75GiB cap. No quantization or weight conversion was required. bitsandbytes was installed and inventoried; other quantization backends listed in the inventory were absent.

Attempt3 loaded in 27.595s worker time (28.932s parent-to-loaded). CPU tree RAM peak was 4,819,132,416 bytes. CUDA allocated peak was 6,507,345,920, reserved peak 6,746,537,984; global GPU peak usage was 6,876,561,408 bytes. Its minimum free VRAM was 1,407,188,992 bytes, above the1GiB reserve. Minimum available RAM across all attempts was 3,020,754,944 bytes, above the2GiB reserve. Guards permit transient overshoot; they are sampled controls, not OS quotas. Two earlier attempts were terminated for crossing their caps and preserved.

The third query started but had no output. CPU telemetry contains a 491.652s gap, also visible in GPU telemetry; the parent stopped the worker for query hard timeout upon resuming. The gap's cause is unconfirmed. It must not be interpreted as continuous model computation or a representative latency result. All owned worker processes were cleaned up. No other application was terminated.

The final retry audit measured **6,181,048,320 bytes available RAM** and **8,282,701,824 bytes available VRAM**. The frozen RAM gate requires 7,784,628,224 bytes (5.75GiB cap +2GiB reserve +0.5GiB margin). Current gate: **BLOCKED_CURRENT_HEADROOM**. Even the observed loader peak plus reserve/margin requires 7,503,486,976 bytes. No further worker was launched. Top process memory and Python/application role hints are preserved in `search_proof8_resume_resource_gate.json`; no large RAG process was identified from those hints, and live RAG concurrency was not exercised.

## Semantic comparison and denominator limits

| Pipeline | Typed on intended cohort | Execution | False execution | Missed valid |
|---|---:|---:|---:|---:|
| Frozen deterministic control | 16/16 | 18/18 | 0/8 | 0/10 |
| Restricted-language fallback | 0/16 | 8/18 | 0/8 | 10/10 |
| Learned proof workflow, including16 missing-output clarifications | 0/16 | 8/18 | 0/8 | 10/10 |

The last row is guarded workflow behavior, **not18 learned predictions**. Only queries01/02 have real model outputs. On this common observed subset, deterministic scored2/2 typed and2/2 execution; learned proof scored0/2 and0/2, missed2/2 valid executions, and has **no observed blocked-query denominator** for false execution. Both outputs were JSON objects (2/2) but schema/source-valid0/2, so neither reached proof compilation or authorized execution. Schema validation is the first gate of the same deterministic proof pipeline; it is never bypassed to manufacture a proof result. No model search, database query, scope choice or tool call occurred.

The model confused canonical domains with role names, used invalid role/polarity enums, stringified numeric operands, lost strict year comparison, and emitted incorrect character offsets. Predicted exact source substrings were 0/5 valid. Agreed mandatory units omitted or changed: 4/4 across the two observed contexts. Raw per-dimension source-span/domain/operator/operand/modality/polarity/state scores are in `search_proof8_observed_only_analysis.json`; its observed-only denominators supersede all18 annotation counts for statements about raw model quality. Invalid offsets make IoU alignment diagnostic rather than authoritative semantic matching. Relationship and negative-query accuracy are unmeasured (0 applicable observed outputs). There is no complete invention oracle; zero accepted hard filters is not a claim of zero raw invention.

The18 queries were independently authored/reviewed before exposure and are now exposed DEVELOPMENT data. Two notice subtypes remain unscored for typed accuracy. This is not fresh acceptance, and no fresh acceptance was attempted. Native scalar control agreement is29/29 on this small selected population; this does not establish generalization or live database correctness.

## Operational measurements

Two completed generation durations were 38.844s and 11.811s. Their descriptive p50 is 25.327s and p95 is 38.844s (n=2). Warm excluding first is 11.811s (n=1); p95 at n=1 is merely that same observation, not tail-latency qualification. No serial-complete or two-caller-complete event exists. Serial/concurrent throughput and queue latency are **not measured**. The harness was configured for one model with two queued callers after the serial phase; that probe never ran.

Worker CPU time was 68.531s. Corrected peak sampled CPU use is 121.19% of one core; the initial sample is excluded because it divides startup CPU by an almost-zero interval. Global GPU peak sampled utilization was 99%; global mean 24.98% is gap-biased and does not establish model utilization or RAG contention. One of3 started queries was parent-aborted after the telemetry gap; neither of the2 completed outputs timed out. Sixteen planned outputs remain absent (1 started,15 unstarted). Attempts1/2 token-budget audit mistakenly counted BatchEncoding keys; attempt3 corrected it and measured943–965 input tokens, all below4096. Earlier evidence was preserved.

## Regression, preservation and next requirement

The reviewed regression ran1705 passing tests with6 disclosed legacy contract nodes deselected under the unchanged independently reviewed migration (`search_proof8_readiness_tests.xml`). The frozen semantic control was not changed. Historical evidence (5095 protected entries), all three source freezes and all nine cached model files were rehashed successfully. Tracked/staged diffs are empty. All new evidence is retained, including rejected outputs and interrupted runs. No production/parser/C4/EXACT/auth/library isolation mutation, Mongo write, index rebuild, deployment, remote inference or institutional data use occurred. Native database/JWT qualification remains limited by the no-writes constraint. The model's previously audited research license does not establish commercial deployment permission.

The experiment established a successful guarded loading path and captured actual failures. It did **not** complete the18-query learned comparison or operational qualification. Next work requires sufficient current RAM for the guarded full capture, schema/ontology extraction repair under a newly frozen development configuration, complete serial/two-caller measurements, and the separate baseV8 semantic requirements. After selection, freeze the normative contract/scorer/criteria before genuinely fresh independent acceptance. Neither pipeline is production-qualified by these results. See `search_proof8_final_qa.json` for all22 requested QA fields.
