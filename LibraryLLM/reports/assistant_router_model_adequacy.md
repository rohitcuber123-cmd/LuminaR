# Router model adequacy — FAIL

The strongest tested Qwen2.5-3B-Instruct architecture achieved **76/116 (65.52%)** on the unchanged existing corpus and **68/121 (56.20%)** on sealed held-out language. The adequacy floors were 85% and 80%; both failed. Stop further routing/prompt tuning for this phase. No regex rescue, model download, replacement, or larger-model benchmark was performed.

The current 3B router appears to be limiting reliability under the tested formulations. Structurally valid JSON frequently chose the wrong intent, goal, position, or failed to retain a criterion. This evidence does not prove that every possible 3B formulation fails or that an untested larger model would pass. Conditional required fields raised criterion success from 0/10 in E to 9/10 in E2, but overall accuracy remained 73/116 and safety worsened. F did not improve aggregate accuracy over D. Its held-out retries recovered 0/22 strict cases.

Safety also failed: the selected candidate made two unwanted title-resolution calls and two unrelated Search fallbacks on held-out contextual requests. One focused retry replaced a rejected invented title with the literal pseudo-title “latter book”; another treated “a copy of the book on this page” as a named title. Existing literal grounding rejected nonliteral spans but did not establish that every literal span was a genuine title. No held-out phrases were added to production rules. The candidate was not promoted.

Measured hardware (normal RAG process, same existing model):

| Observation | Value |
|---|---:|
| GPU | NVIDIA GeForce RTX 5060 Laptop GPU |
| Total CUDA VRAM | 7.96 GiB |
| Model parameter/buffer footprint | 1.87 GiB |
| CUDA allocated | 2.10 GiB |
| CUDA reserved | 2.17 GiB |
| CUDA free at startup | 4.68 GiB |
| NVIDIA-SMI observed resident use | 2799 MiB |
| NVIDIA-SMI observed free | 5101 MiB |

CUDA counters, parameter footprint, and NVIDIA-SMI use different accounting and were sampled at different points. These are observations, not guaranteed peak headroom. RAG and routing share the existing model and inference lock. A separate larger router would need to coexist with the resident RAG model, its KV cache, retrieval models and workspace within the measured budget; fit has not been established. Replacing the shared model would change frozen RAG behavior and is outside this phase.

Only Qwen2.5-3B-Instruct is cached as a generative model. Other cached models are embeddings/rerankers. A future, separately authorized proposal can select one candidate, measure loading/inference peak VRAM and coexistence, then use new sealed language and the same fixed acceptance gates. No candidate is installed or recommended as already proven.

The default compact baseline is restored: original live chain **6/6**, explicit Compare **zero Qwen calls**. The failed V2 candidate's original live chain remains **4/6** in its own report; restoration is not counted as V2 acceptance.
