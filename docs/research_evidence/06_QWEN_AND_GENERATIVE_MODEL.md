# 06_QWEN_AND_GENERATIVE_MODEL.md: Comprehensive Deep Dive into Generative Model Architecture

## Executive Summary

The sole generative large language model implemented and running within LuminaR is **Qwen2.5-3B-Instruct**. This report documents the exact model configuration, weight quantization, inference framework, sampling parameters, schema-constrained decoding mechanisms, memory handling, and an exhaustive code trace of every repository feature that invokes it.

---

## 1. Technical Identity & Specifications

| Parameter | Exact Value | Source Code / File Reference |
| :--- | :--- | :--- |
| **Model Family** | Qwen 2.5 (Decoder-only Transformer) | Hugging Face Hub |
| **Exact Model Identifier** | `Qwen/Qwen2.5-3B-Instruct` | `LibraryLLM/rag/llm.py:46` (`DEFAULT_MODEL_NAME = "Qwen/Qwen2.5-3B-Instruct"`) |
| **Model Provider** | Alibaba Cloud / Qwen Team | Open-weights release (September 2024) |
| **Actual Parameter Count** | **3,085,938,688** (~3.09 Billion) | Standard Hugging Face configuration |
| **Inference Framework** | Hugging Face `transformers` + `bitsandbytes` + PyTorch | `LibraryLLM/rag/llm.py:28-40` |
| **Local Model Path** | Resolved via Hugging Face cache directory (`~/.cache/huggingface/hub/models--Qwen--Qwen2.5-3B-Instruct`) or local mirror path specified via env `LUMINAR_MODEL_DIR` | `LibraryLLM/rag/llm.py:126` (`local_files_only=True`) |
| **Air-Gap Verification** | `local_files_only=True` is explicitly passed to both `AutoTokenizer.from_pretrained` and `AutoModelForCausalLM.from_pretrained` | `LibraryLLM/rag/llm.py:130, 165` |

---

## 2. Quantization, Hardware & Memory Management

### 2.1 Quantization Configuration
LuminaR implements 4-bit NormalFloat4 (NF4) quantization when running on CUDA, powered by `bitsandbytes`:

```python
# Extracted from LibraryLLM/rag/llm.py:151-164
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.float16,
)
```

* **Quantization Type:** NormalFloat4 (`nf4`), an information-theoretically optimal non-linear data type for normally distributed neural weights.
* **Double Quantization:** `bnb_4bit_use_double_quant=True` (quantizes the quantization constants, saving an additional ~0.37 bits per parameter).
* **Compute Dtype:** `torch.float16` for dequantized matrix multiplications during the forward attention pass.
* **CPU Fallback:** If `torch.cuda.is_available()` evaluates to `False`, the model loads in unquantized 32-bit floating point (`torch.float32`) with `device_map={"": "cpu"}`. `bitsandbytes` 4-bit quantization is not supported on CPU.

### 2.2 Memory Footprint & Allocation
* **Static Weights in VRAM (4-bit NF4):** ~2.1 GB VRAM.
* **Key-Value (KV) Cache:** Dynamically allocated per generation step. For a 2,048 token sequence, the KV cache consumes approximately ~320 MB VRAM.
* **Peak Inference VRAM:** ~2.8 GB to ~3.5 GB VRAM on a single NVIDIA GPU.
* **CPU Fallback Memory:** ~7.8 GB to ~8.5 GB system RAM when loaded in FP32 on CPU.
* **Memory Management Strategy:**
  * Singleton instance persists in memory across requests (`_llm_instance`).
  * Explicit `torch.cuda.empty_cache()` is called during shutdown or exception recovery routines.
  * No model offloading to disk/CPU swap during standard operation.

---

## 3. Decoding & Generation Hyperparameters

LuminaR employs a strict **deterministic greedy decoding strategy** to eliminate factual hallucinations and ensure consistent JSON schema compliance.

```python
# Extracted from LibraryLLM/rag/llm.py:348-385
outputs = self.model.generate(
    **inputs,
    max_new_tokens=max_new_tokens,
    do_sample=False,              # STRICTLY GREEDY
    temperature=0.2,              # Retained in signature; ignored by PyTorch when do_sample=False
    top_p=0.9,                    # Ignored by PyTorch when do_sample=False
    pad_token_id=self.tokenizer.pad_token_id,
    eos_token_id=self.tokenizer.eos_token_id,
    logits_processor=logits_processors,
    prefix_allowed_tokens_fn=prefix_allowed_tokens_fn,
)
```

### Parameter Breakdown

| Hyperparameter | Value | Behavior & Code Rationale |
| :--- | :--- | :--- |
| `do_sample` | `False` | **Deterministic Greedy Decoding.** The model always selects $\arg\max_{w} P(w \mid w_{<t})$. |
| `temperature` | `0.2` (nominal) | Retained as default argument in `generate()`, but strictly non-operational because `do_sample=False`. Intent extraction passes `0.1`. |
| `top_p` | `0.9` (nominal) | Retained in parameter signatures; bypassed during greedy evaluation. |
| `top_k` | Not set / N/A | Not configured in `model.generate()`. |
| `max_new_tokens` | Dynamic (160–1500) | Varies by prompt mode:<br>• `160`: Evidence validation (`ValidatorSchema`)<br>• `400`: Intent classification (`IntentSchema`)<br>• `300`: Concise RAG answer<br>• `320`: Default standard RAG answer<br>• `1000`: Detailed RAG answer<br>• `1500`: Comprehensive study summary |
| `repetition_penalty` | Custom Logits Processor | Standard Hugging Face `repetition_penalty` is set to `1.0` (disabled) to avoid penalizing necessary citations. Instead, a custom `AnswerRepetitionControl(input_length)` logits processor bans repeated 3-grams solely within generated tokens. |
| `context_window` | Architectural: 32,768<br>Enforced: 24,000 chars | Architectural max is 32K tokens. Prompt context text is hard-truncated to `MAX_CONTEXT_CHARS = 24000` characters (~6,000 BPE tokens) in `rag/llm.py:49`. |
| `streaming` | Backend: Synchronous | The backend REST endpoints return monolithic JSON responses. Server-Sent Events (SSE) streaming is not active on backend endpoints. |
| `timeout` | 60.0 seconds | Configured in `assistant/orchestrator.py` via `float(os.getenv("ASSISTANT_QWEN_TIMEOUT", "60.0"))`. |
| `retry` | 0 (Fail-Fast) | Failed generations raise exceptions caught by route handlers, returning HTTP 503 or a fallback error string without automated re-try loops. |

---

## 4. Constrained Decoding (`lm-format-enforcer`)

LuminaR uses the `lm-format-enforcer` library to guarantee that structural JSON outputs conform 100% to Pydantic schemas without syntax errors or missing keys:

1. **Intent Extraction Schema (`IntentSchema`):**
   ```python
   class IntentSchema(BaseModel):
       intent: str = Field(description="One of: search, recommend, summarize, explain, general_chat")
       confidence: float = Field(ge=0.0, le=1.0)
       query: str = Field(default="")
       filters: dict = Field(default_factory=dict)
   ```
   * Enforced via: `build_transformers_prefix_allowed_tokens_fn(tokenizer, JsonSchemaParser(IntentSchema.model_json_schema()))`.
   * Mechanism: Dynamically masks out all vocabulary tokens that would violate the JSON grammar or schema regex at each autoregressive step.

2. **Evidence Validation Schema (`ValidatorSchema`):**
   ```python
   class ValidatorSchema(BaseModel):
       is_supported: bool
       confidence: float
       contradictions: list[str]
       supporting_passage_ids: list[int]
   ```
   * Enforced via: `build_transformers_prefix_allowed_tokens_fn(tokenizer, JsonSchemaParser(ValidatorSchema.model_json_schema()))`.

---

## 5. Exhaustive Feature Invocation Audit

| Feature | Invokes Qwen? | Exact Code Entry Point | Full Call Trace |
| :--- | :--- | :--- | :--- |
| **Domain Book RAG QA** | **YES** | `POST /ask` in `rag/api.py` | `rag/api.py:ask_question()` $\rightarrow$ `rag/qa.py:LuminaRAG.ask()` $\rightarrow$ `rag/qa.py:_build_grounded_prompt()` $\rightarrow$ `rag/llm.py:LuminaRLLM.generate()` |
| **Private Document QA** | **YES** | `POST /ask` with `document_id` in `rag/api.py` | `rag/api.py:ask_question()` $\rightarrow$ `rag/qa.py:LuminaRAG.ask(document_id=doc_id)` $\rightarrow$ `rag/qa.py:_build_grounded_prompt()` $\rightarrow$ `rag/llm.py:LuminaRLLM.generate()` |
| **Conversational Assistant** | **YES** | `POST /api/chat` in `assistant/api.py` | `assistant/api.py:chat()` $\rightarrow$ `assistant/orchestrator.py:AssistantOrchestrator.handle_message()` $\rightarrow$ `assistant/qwen.py:QwenGateway.generate()` $\rightarrow$ `rag/llm.py:LuminaRLLM.generate()` |
| **Intent Analysis (Tier 2)** | **YES** | Internal fallback in `assistant/orchestrator.py` | `assistant/orchestrator.py:_extract_intent()` $\rightarrow$ `rag/llm.py:LuminaRLLM.analyze_intent()` $\rightarrow$ `rag/llm.py:_analyze_intent_uncached()` (with `IntentSchema`) |
| **Evidence Validation** | **YES** | Post-processing in `rag/qa.py` | `rag/qa.py:LuminaRAG.ask()` $\rightarrow$ `rag/llm.py:LuminaRLLM.validate_evidence()` (with `ValidatorSchema`) |
| **Recommendation Explanation**| **YES** | Chatbot action in `assistant/orchestrator.py` | `assistant/orchestrator.py:_explain_recommendation()` $\rightarrow$ `assistant/qwen.py:QwenGateway.generate()` $\rightarrow$ `rag/llm.py:LuminaRLLM.generate()` |
| **Recommendation Engine** | **NO** | `POST /api/recommendations` | `recommendation/recommendation_service.py:get_recommendations()` (Heuristic 8-factor linear scoring only) |
| **Knowledge Artifacts** | **NO** | `POST /api/documents/{id}/artifacts` | `rag/services/document_knowledge.py:generate_artifacts()` (Deterministic regex, TextRank, and TF-IDF only) |
| **Semantic & Hybrid Search** | **NO** | `GET /search` in `search/api.py` | `search/luminar_search.py:search()` (FAISS HNSW + BM25 + Cross-Encoder reranker only) |
| **Query Rewriting / Expansion**| **NO** | `search/luminar_search.py` | Rule-based regex token normalization only; no generative query expansion |

---

## 6. Concurrency & Thread Safety

* **Synchronization Primitive:** `threading.RLock()` instantiated at module level: `inference_lock = threading.RLock()`.
* **Execution Scope:** Every call to `LuminaRLLM.generate()`, `LuminaRLLM.analyze_intent()`, and `LuminaRLLM.validate_evidence()` is wrapped in `with self.inference_lock:`.
* **Implications:**
  * Multiple incoming HTTP requests on FastAPI worker threads are strictly serialized before model execution.
  * Prevents CUDA out-of-memory crashes and corrupted KV cache buffers.
  * Imposes a throughput bottleneck: if request $A$ takes 4.5 seconds to generate 320 tokens, request $B$ is queued and must wait 4.5 seconds before starting.
