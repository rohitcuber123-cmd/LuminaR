# V8 Step 1: V7 Reproduction Report

**Generated:** 2026-09-13T05:26:40.879455

**GPU:** NVIDIA GeForce RTX 5060 Laptop GPU


## Baseline (18 queries)

- Intent Accuracy: **100.00%** (18/18)
- Total Latency: **63778.7ms** mean
- Validation Latency: **34274.4ms** mean
- Fast Filter Latency: **2.35ms** mean

## Adversarial (42 cases)

- Accuracy: **73.81%** (31/42)
- False Positives: **7**
- False Negatives: **4**
- Unsupported Premise Rejection: **81.08%**
- FF False Positives: **1** | FF False Negatives: **0**
- LLM False Positives: **6** | LLM False Negatives: **4**

## V7 Historical Comparison

| Metric | Historical V7 | Current Reproduction | Difference | Match? |
|--------|--------------|---------------------|------------|--------|
| intent_accuracy_canonical | 100.0 | 100.0 | +0.0000 | YES |
| adversarial_accuracy | 83.33 | 73.81 | -9.5200 | **NO** |
| unsupported_premise_rejection | 89.19 | 81.08 | -8.1100 | **NO** |
| validation_latency_mean_ms | 46724.59 | 34274.43 | -12450.1600 | **NO** |
| fast_filter_latency_mean_ms | 1.36 | 2.35 | +0.9900 | **NO** |
| total_latency_mean_ms | 70653.34 | 63778.71 | -6874.6300 | **NO** |
| ff_false_positives | 1 | 1 | +0.0000 | YES |
| ff_false_negatives | 1 | 0 | -1.0000 | **NO** |
| llm_validator_false_negatives | 19 | 4 | -15.0000 | **NO** |
| llm_validator_false_positives | 3 | 6 | +3.0000 | **NO** |

## Discrepancies

> [!WARNING]
> The following metrics differ from the historical V7 report:
>
> - **adversarial_accuracy**: V7=83.33, Now=73.81 (diff=-9.5200)
> - **unsupported_premise_rejection**: V7=89.19, Now=81.08 (diff=-8.1100)
> - **validation_latency_mean_ms**: V7=46724.59, Now=34274.43 (diff=-12450.1600)
> - **fast_filter_latency_mean_ms**: V7=1.36, Now=2.35 (diff=+0.9900)
> - **total_latency_mean_ms**: V7=70653.34, Now=63778.71 (diff=-6874.6300)
> - **ff_false_negatives**: V7=1, Now=0 (diff=-1.0000)
> - **llm_validator_false_negatives**: V7=19, Now=4 (diff=-15.0000)
> - **llm_validator_false_positives**: V7=3, Now=6 (diff=+3.0000)
>
> Likely causes: LLM non-determinism (temperature=0.1), GPU state, token sampling order.

---
*Raw data: [intent_aware_rag_v8_v7_reproduction.json](file:///d:/SDC/LibraryLLM/reports/intent_aware_rag_v8_v7_reproduction.json)*