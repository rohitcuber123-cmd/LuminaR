# V8 Final Evaluation Report

**Generated:** 2026-09-13T07:35:08.795790

**GPU:** NVIDIA GeForce RTX 5060 Laptop GPU


## Baseline (18 queries)

- Intent Accuracy: **100.00%** (18/18)
- Total Latency: **32624.2ms** mean
- Validation Latency: **8737.7ms** mean
- Fast Filter Latency: **2.64ms** mean

## Adversarial (42 cases)

- Accuracy: **88.10%** (37/42)
- False Positives: **2**
- False Negatives: **3**
- Unsupported Premise Rejection: **94.59%**
- FF False Positives: **1** | FF False Negatives: **0**
- LLM False Positives: **1** | LLM False Negatives: **3**

## V7 Historical Comparison

| Metric | Historical V7 | Current Reproduction | Difference | Match? |
|--------|--------------|---------------------|------------|--------|
| intent_accuracy_canonical | 100.0 | 100.0 | +0.0000 | YES |
| adversarial_accuracy | 83.33 | 88.1 | +4.7700 | **NO** |
| unsupported_premise_rejection | 89.19 | 94.59 | +5.4000 | **NO** |
| validation_latency_mean_ms | 46724.59 | 8737.71 | -37986.8800 | **NO** |
| fast_filter_latency_mean_ms | 1.36 | 2.64 | +1.2800 | **NO** |
| total_latency_mean_ms | 70653.34 | 32624.18 | -38029.1600 | **NO** |
| ff_false_positives | 1 | 1 | +0.0000 | YES |
| ff_false_negatives | 1 | 0 | -1.0000 | **NO** |
| llm_validator_false_negatives | 19 | 3 | -16.0000 | **NO** |
| llm_validator_false_positives | 3 | 1 | -2.0000 | **NO** |

## Discrepancies

> [!WARNING]
> The following metrics differ from the historical V7 report:
>
> - **adversarial_accuracy**: V7=83.33, Now=88.1 (diff=+4.7700)
> - **unsupported_premise_rejection**: V7=89.19, Now=94.59 (diff=+5.4000)
> - **validation_latency_mean_ms**: V7=46724.59, Now=8737.71 (diff=-37986.8800)
> - **fast_filter_latency_mean_ms**: V7=1.36, Now=2.64 (diff=+1.2800)
> - **total_latency_mean_ms**: V7=70653.34, Now=32624.18 (diff=-38029.1600)
> - **ff_false_negatives**: V7=1, Now=0 (diff=-1.0000)
> - **llm_validator_false_negatives**: V7=19, Now=3 (diff=-16.0000)
> - **llm_validator_false_positives**: V7=3, Now=1 (diff=-2.0000)
>
> Likely causes: LLM non-determinism (temperature=0.1), GPU state, token sampling order.

---
*Raw data: [intent_aware_rag_v8_final_evaluation.json](file:///d:/SDC/LibraryLLM/reports/intent_aware_rag_v8_final_evaluation.json)*