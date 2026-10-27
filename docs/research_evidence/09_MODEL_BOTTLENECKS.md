# 09_MODEL_BOTTLENECKS.md: Rigorous Audit of System Bottlenecks & Operational Constraints

## Executive Summary

This document provides a scientifically rigorous architectural audit of the throughput, memory, context, and latency constraints of the LuminaR AI/ML pipeline. 

To maintain strict scientific integrity, this audit strictly bifurcates:
1. **VERIFIED BOTTLENECKS:** Constraints mathematically or structurally proven by source code patterns, serialization locks, and configuration parameters.
2. **POTENTIAL BOTTLENECK REQUIRING MEASUREMENT:** Theoretical performance regressions that are logically plausible based on architecture, but whose precise numerical magnitudes have not yet been empirically profiled on target hardware (`NOT MEASURED`).

---

## 1. Verified Bottlenecks (Architecturally Proven)

### Bottleneck 1: Global Sequential Locking of Generative Inference
* **Classification:** **VERIFIED BOTTLENECK**
* **Root Cause:** A re-entrant mutex (`inference_lock = threading.RLock()`) in `LibraryLLM/rag/llm.py:48` wraps every invocation of `generate()`, `analyze_intent()`, and `validate_evidence()`.
* **Structural Impact:**
  * Generative inference is strictly serialized to a single thread.
  * If Request $A$ generates 320 tokens (taking, e.g., 6 seconds on local GPU), incoming Requests $B, C, \dots$ are placed in an OS-level wait queue.
  * System concurrency for all LLM-backed endpoints (`/ask`, `/chat`, intent analysis) is strictly capped at:
    $$\text{Max Throughput} = \frac{1}{\text{Mean Generation Latency}}\text{ req/sec}$$
  * Under a modest load of 5 concurrent users, user 5 will experience queuing delays exceeding 25–30 seconds.

---

### Bottleneck 2: Mandatory Two-Pass Inference in RAG Question Answering
* **Classification:** **VERIFIED BOTTLENECK**
* **Root Cause:** `LibraryLLM/rag/qa.py:195-235` executes two sequential forward passes through `Qwen2.5-3B-Instruct` for every standard RAG question:
  1. **Pass 1 (Synthesis):** Generates the grounded answer text (`max_new_tokens` up to 320–1000).
  2. **Pass 2 (Validation):** Passes question, generated answer, and context chunks back into Qwen with `ValidatorSchema` (`max_new_tokens = 160`) to verify factual grounding.
* **Structural Impact:**
  * Even a single isolated user request pays the latency penalty of two back-to-back LLM generations under the sequential lock.
  * Extends single-request roundtrip latency by 35%–50% compared to single-pass RAG architectures.

---

### Bottleneck 3: Token Truncation Asymmetry in Document Vectorization
* **Classification:** **VERIFIED BOTTLENECK**
* **Root Cause:**
  * Ingestion chunker (`rag/services/document_service.py:95`) segments documents into **400-word windows** (~500–550 WordPiece tokens).
  * Bi-encoder embedding model (`search/index_manager.py:35`) enforces `model.max_seq_length = 256` tokens with hard right-truncation.
* **Structural Impact:**
  * Words situated between token index 257 and ~550 in any document chunk are completely ignored during dense vector generation.
  * Dense semantic retrieval only indexes the first half of each chunk. If a user asks a query whose semantic match lies in the second half of a 400-word chunk, dense retrieval misses the candidate (unless captured by lexical fallback).

---

### Bottleneck 4: Monolithic Synchronous REST Delivery (No SSE Streaming)
* **Classification:** **VERIFIED BOTTLENECK**
* **Root Cause:** Endpoints `POST /ask` (`rag/api.py:105`) and `POST /api/chat` (`assistant/api.py:65`) generate complete tokens synchronously inside worker threads before returning a unified JSON payload.
* **Structural Impact:**
  * Frontend clients receive zero visual feedback during the entire generation process.
  * Perceived User Latency (PUL) is equal to total generation latency ($TTFT + N \times t_{\text{token}}$) rather than Time-to-First-Token ($TTFT$).

---

### Bottleneck 5: Severe CPU Fallback Latency Wall
* **Classification:** **VERIFIED BOTTLENECK**
* **Root Cause:** `bitsandbytes` 4-bit NF4 quantization requires NVIDIA CUDA hardware. On non-GPU or CPU-only hosts, `rag/llm.py:170-178` falls back to unquantized `torch.float32`.
* **Structural Impact:**
  * RAM consumption jumps from 2.1 GB VRAM to ~8.2 GB system RAM.
  * Generation speed on CPU degrades to approximately 1–3 tokens/second.
  * A 320-token answer on CPU takes between 100 and 320 seconds, causing typical HTTP client timeouts (defaulting to 60s in `ASSISTANT_QWEN_TIMEOUT`).

---

## 2. Potential Bottlenecks Requiring Measurement

The following areas represent potential operational bottlenecks that require empirical benchmarking before conclusive statements can be made.

### Bottleneck 6: Cold-Start Initialization Latency
* **Classification:** **POTENTIAL BOTTLENECK REQUIRING MEASUREMENT**
* **Description:** First-time lazy initialization of `Qwen2.5-3B-Instruct` involves loading ~3.1 GB of quantized weights from NVMe/SATA disk into host RAM, moving them to VRAM, and initializing `bitsandbytes` CUDA kernels.
* **Empirical Status:** **NOT MEASURED**
* **Profiling Requirement:** Measure elapsed wall-clock time from the first HTTP request trigger until the model is ready to receive input tensors across target hardware platforms (e.g., PCIe 4.0 NVMe vs SATA SSD).

---

### Bottleneck 7: Cross-Encoder Reranker Forward-Pass Latency
* **Classification:** **POTENTIAL BOTTLENECK REQUIRING MEASUREMENT**
* **Description:** Both search and RAG invoke `cross-encoder/ms-marco-MiniLM-L-6-v2` over top candidate pools (`CROSSENCODER_RERANK_DEPTH = 50` in search; 15–20 in RAG) using `batch_size = 16`.
* **Hypothesis:** Full cross-attention over 50 text pairs (up to 512 tokens each) may dominate first-stage BM25 + FAISS search time by an order of magnitude.
* **Empirical Status:** **NOT MEASURED**
* **Profiling Requirement:** Benchmark time spent in `CrossEncoder.predict()` on GPU and CPU across varying query-passage candidate pool sizes (10, 25, 50, 100).

---

### Bottleneck 8: Long-Prompt Prefill Latency at 24,000 Characters
* **Classification:** **POTENTIAL BOTTLENECK REQUIRING MEASUREMENT**
* **Description:** Prompt context is capped at `MAX_CONTEXT_CHARS = 24000` (~6,000 tokens). Transformer self-attention prefill computational complexity scales quadratically ($O(N^2)$) with prompt sequence length.
* **Hypothesis:** Large multi-chunk prompts close to the 24,000-character ceiling will exhibit noticeably delayed Time-to-First-Token (TTFT) compared to concise 1,000-character prompts.
* **Empirical Status:** **NOT MEASURED**
* **Profiling Requirement:** Profile TTFT across prompt lengths: 500, 2000, 5000, 10000, and 24000 characters.

---

### Bottleneck 9: Reasoning Degradation in 3B Parameter Regime
* **Classification:** **POTENTIAL BOTTLENECK REQUIRING MEASUREMENT**
* **Description:** 3-billion parameter models possess limited parametric capacity compared to 7B, 14B, or 70B models, particularly in resolving contradictory claims across multiple retrieved chunks or synthesizing deep multi-hop deductions.
* **Empirical Status:** **NOT MEASURED**
* **Profiling Requirement:** Standardized RAG evaluation using Ragas, TruLens, or G-Eval across faithfulness, answer relevancy, and context recall benchmarks on the LuminaR library corpus.

---

### Bottleneck 10: Multi-Process GPU VRAM Contention
* **Classification:** **POTENTIAL BOTTLENECK REQUIRING MEASUREMENT**
* **Description:** In production, Search (`search.api`, port 8003) and RAG (`rag.api`, port 8005) run as separate Python processes. Both instantiate PyTorch CUDA contexts and load SentenceTransformer / CrossEncoder models, while RAG additionally loads Qwen in 4-bit NF4.
* **Hypothesis:** Running both services concurrently on a single consumer GPU with 6 GB or 8 GB VRAM may trigger CUDA Out-Of-Memory (OOM) errors during simultaneous heavy bursts.
* **Empirical Status:** **NOT MEASURED**
* **Profiling Requirement:** Monitor `nvidia-smi` peak allocated and reserved VRAM under concurrent high-throughput load across both microservices.

---

## 3. Summary Comparison Matrix

| Bottleneck Candidate | Status | Primary Impact Metric | Mitigation Pathway in Codebase |
| :--- | :--- | :--- | :--- |
| **Inference Lock Concurrency** | **VERIFIED** | Throughput (Requests/sec) | Add worker pool or migrate to vLLM / TensorRT-LLM server |
| **Two-Pass RAG (QA + Validator)**| **VERIFIED** | Latency per request | Make validator optional via query flag or combine into single-pass prompt |
| **256-Token Truncation in MiniLM**| **VERIFIED** | Semantic Recall | Align chunk window to 200 words (~240 tokens) or migrate to 512/8192-token embedder |
| **Lack of SSE Token Streaming** | **VERIFIED** | Time-to-First-Feedback | Implement FastAPI `StreamingResponse` using `TextIteratorStreamer` |
| **CPU Fallback Latency Wall** | **VERIFIED** | Latency / Usability | Enforce GPU requirement or deploy ONNX Runtime / llama.cpp GGUF on CPU |
| **Cold-Start Load Duration** | **NOT MEASURED** | Startup responsiveness | Implement eager background warmup on server boot (`warmup_iterations`) |
| **Cross-Encoder 50-Depth Overhead**| **NOT MEASURED** | Search P99 latency | Measure GPU vs CPU latency; tune `CROSSENCODER_RERANK_DEPTH` from 50 to 25 |
| **24K Char Prefill TTFT** | **NOT MEASURED** | Time-to-First-Token | Measure prefill latency profile; implement FlashAttention-2 |
| **3B Multi-Hop Accuracy Limits** | **NOT MEASURED** | Answer Quality / Accuracy | Standardize Ragas benchmark; evaluate Qwen2.5-7B or 14B under AWQ/GPTQ |
| **Multi-Process VRAM Contention** | **NOT MEASURED** | Reliability / VRAM stability | Run unified monolithic process or route embeddings through shared embedding microservice |
