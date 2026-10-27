# 05_MODEL_CARDS.md: Model Cards for All Active LuminaR Models

This document presents structured, comprehensive Model Cards (following the framework established by Mitchell et al., 2019) for every active model in LuminaR. Every operational parameter reflects actual repository implementation in `d:\SDC\LibraryLLM`.

---

# Model Card 1: Qwen2.5-3B-Instruct (Generative LLM)

## 1. Model Details
* **Model Name:** Qwen2.5-3B-Instruct
* **Hugging Face Hub ID:** `Qwen/Qwen2.5-3B-Instruct`
* **Model Developer:** Alibaba Cloud / Qwen Team
* **Release Date:** September 2024
* **Model Type:** Causal Autoregressive Language Model (Decoder-only Transformer)
* **Architecture Specifics:**
  * Layers: 36 decoder transformer blocks
  * Hidden Dimension: 2,048
  * Attention Heads: 16 query heads, 2 key/value heads (Grouped-Query Attention / GQA)
  * Vocabulary Size: 151,646 tokens (BPE)
  * RoPE: Rotary Position Embedding with YaRN context extension up to 131,072 tokens
  * Activation Function: SwiGLU
* **Total Parameters:** ~3.09 Billion (3,085,938,688)
* **License:** Qwen Open Model License Agreement (Apache 2.0 compatible for research and commercial use under threshold)

## 2. Intended Use in LuminaR
* **Primary Intended Uses:**
  1. **Domain Book RAG QA:** Synthesize factual, grounded answers to user questions citing retrieved book paragraphs.
  2. **Private Document QA:** Grounded Q&A against user-uploaded PDFs, EPUBs, and Word documents.
  3. **Conversational Assistant:** Multi-turn conversational interaction, clarifying query intent, and structuring library recommendations.
  4. **Constrained Intent Extraction:** Parsing complex natural language requests into structured JSON function-calling payloads via `lm-format-enforcer`.
  5. **Evidence Validation:** Automated self-consistency verification comparing synthesized answers against retrieved reference chunks using JSON schema.
* **Out-of-Scope / Prohibited Uses:**
  * Autonomous ungrounded factual generation without retrieved context (hallucination risk).
  * Direct execution of arbitrary code or system shell commands.
  * Medical, legal, or high-stakes safety-critical advisory.

## 3. Runtime Configuration & Hardware Placement
* **Deployment Topology:** 100% Local Inference (Air-gapped; `local_files_only=True`).
* **Inference Framework:** Hugging Face `transformers` (`AutoModelForCausalLM`, `AutoTokenizer`) + `bitsandbytes` + `torch`.
* **Quantization Format:** 4-bit NormalFloat4 (`BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16)`).
* **Hardware Device:** NVIDIA CUDA GPU (Device 0) when available; CPU fallback (FP32).
* **Memory Footprint:**
  * Weights VRAM Footprint: ~2.1 GB VRAM (in 4-bit NF4).
  * Peak Inference VRAM: ~3.2 GB to 4.5 GB VRAM depending on generation length and KV cache.
  * CPU RAM Footprint (Fallback): ~7.5 GB to 8.2 GB system RAM (in FP32).
* **Process Model & Concurrency:** Process Singleton instantiated in `LibraryLLM/rag/llm.py` via `_llm_instance`. Protected by re-entrant mutex `inference_lock = threading.RLock()`. Inference requests are strictly serialized.

## 4. Hyperparameters & Generation Settings
* **Sampling Mode:** Deterministic Greedy Decoding (`do_sample=False`).
* **Nominal Temperature:** `0.2` (passed in signature, bypassed by greedy decoding).
* **Nominal Top-P:** `0.9` (passed in signature, bypassed by greedy decoding).
* **Max Generation Tokens (`max_new_tokens`):**
  * Fast intent classification: `400`
  * Evidence validation check: `160`
  * Concise QA answer: `300`
  * Default QA answer: `320`
  * Detailed QA answer: `1,000`
  * Comprehensive QA answer: `1,500`
* **Repetition Mitigation:**
  * Constrained decoding: Native schema enforcement (`lm-format-enforcer`).
  * Free-form text: Custom logits processor `AnswerRepetitionControl(input_length)` applying hard 3-gram repeat prevention restricted to generated tokens (ignoring prompt context).
* **Input Context Cap:** `MAX_CONTEXT_CHARS = 24000` characters (~5,500 to 6,500 tokens).

## 5. Performance Characteristics & Known Limitations
* **Observed Latency (Local RTX GPU):**
  * Time-to-First-Token (TTFT): ~250–500 ms (depending on prompt token count).
  * Generation Speed: ~35–55 tokens/second in 4-bit NF4.
* **Limitations:**
  * Small parameter scale (3.09B) occasionally struggles with multi-hop logical deductions across more than 4 disconnected document chunks.
  * Strict greedy decoding reduces creative variety in conversational small-talk in exchange for deterministic factual fidelity.

---

# Model Card 2: all-MiniLM-L6-v2 (Dense Bi-Encoder Embedding)

## 1. Model Details
* **Model Name:** all-MiniLM-L6-v2
* **Hugging Face Hub ID:** `sentence-transformers/all-MiniLM-L6-v2`
* **Model Developer:** Sentence-Transformers (Microsoft MiniLM backbone fine-tuned by Nils Reimers et al.)
* **Release Date:** August 2021
* **Model Type:** Bi-Encoder Sentence / Passage Embedding Model (BERT-style Transformer Encoder)
* **Architecture Specifics:**
  * Backbone: MiniLM-L6-H384-uncased
  * Layers: 6 Transformer encoder layers
  * Hidden Dimension: 384
  * Attention Heads: 12
  * Parameter Count: ~22.7 Million (22,713,216)
  * Pretrained Vocabulary: 30,522 WordPiece tokens
* **License:** Apache 2.0

## 2. Intended Use in LuminaR
* **Primary Intended Uses:**
  1. **Global Book Semantic Indexing:** Mapping full book chunks into 384-D vector space stored in FAISS HNSW indexes.
  2. **Private Document Chunk Indexing:** Mapping uploaded PDF/EPUB/DOCX text paragraphs into private vector collections.
  3. **Query Encoding:** Encoding live user search queries and RAG questions into the identical 384-D vector space.
  4. **Cloze QA Similarity Grading:** Semantic grading of user answers against expected answers in self-assessment quizzes via cosine similarity.
* **Out-of-Scope / Prohibited Uses:**
  * Cross-lingual semantic matching (model is trained primarily on English corpora).
  * Long-document single-shot representation (capped at 256 tokens).

## 3. Technical Parameters & Metric Space
* **Embedding Dimension:** 384 dimensions ($d = 384$).
* **Pooling Strategy:** Token-level Mean Pooling weighted by attention mask (`output_value = 'sentence_embedding'`).
* **Normalization:** Strict **L2 Unit Normalization** ($\|\mathbf{v}\|_2 = 1.0$) applied to every vector via `faiss.normalize_L2(vectors)`.
* **Metric Space:** Cosine Similarity, computed as Inner Product on L2-normalized vectors ($\langle \mathbf{u}, \mathbf{v} \rangle \equiv \cos(\theta)$).
* **Max Sequence Length:** 256 tokens (truncated beyond 256).
* **Precision:** Float32 (single precision).

## 4. Hardware & Operational Lifecycle
* **Deployment Topology:** 100% Local Inference (`local_files_only=True`).
* **Hardware Device:** `cuda` if available; otherwise `cpu`.
* **Batch Sizes:**
  * Index build (books): 64
  * Document ingestion: 32
  * Live query: 1
* **Memory Footprint:** ~90 MB RAM/VRAM.
* **Caching Infrastructure:** SQLite disk cache (`embedding_cache.sqlite3`) keyed by `sha256(normalized_text)`. Repeated queries incur 0 ms model forward-pass time.

---

# Model Card 3: ms-marco-MiniLM-L-6-v2 (Cross-Encoder Reranker)

## 1. Model Details
* **Model Name:** cross-encoder/ms-marco-MiniLM-L-6-v2
* **Hugging Face Hub ID:** `cross-encoder/ms-marco-MiniLM-L-6-v2`
* **Model Developer:** Sentence-Transformers Team
* **Release Date:** 2021
* **Model Type:** Cross-Encoder Transformer Reranker
* **Architecture Specifics:**
  * Backbone: MiniLM-L6-H384
  * Layers: 6 Transformer layers with full cross-attention across concatenated Query-Passage pairs
  * Parameter Count: ~22.7 Million (22,713,216)
  * Classification Head: Linear projection to scalar logit score
* **Training Objective:** Fine-tuned on MS MARCO Passage Ranking dataset with binary cross-entropy loss.
* **License:** Apache 2.0

## 2. Intended Use in LuminaR
* **Primary Intended Uses:**
  1. **Hybrid Search Reranking:** Taking the top 50 candidates retrieved by BM25 + FAISS HNSW and computing all-to-all cross-attention scores.
  2. **RAG Candidate Filtering:** Taking top 15–20 retrieved document chunks and scoring them against the user query before context assembly.
* **Out-of-Scope Uses:**
  * First-stage retrieval over massive collections (computationally prohibitive at $O(N)$).

## 3. Technical Parameters & Metric Space
* **Input Structure:** Concatenated string `(query, passage)` separated by `[SEP]`.
* **Input Token Limit:** 512 tokens maximum for the combined pair.
* **Output:** Unbounded real scalar logit $s \in (-\infty, \infty)$. Higher values denote stronger passage relevance.
* **Batch Size:** `batch_size = 16`.
* **Hardware Device:** `cuda` if available; otherwise `cpu`.
* **Memory Footprint:** ~95 MB RAM/VRAM.

---

# Model Card 4: Tesseract OCR Engine (Document OCR Fallback)

## 1. Model Details
* **Model Name:** Tesseract Open Source OCR Engine
* **Engine Type:** Multi-stage image analysis with LSTM neural network text line recognizer
* **Developer:** HP Labs (originally) / Google / Tesseract Community
* **Version:** 5.x
* **License:** Apache 2.0

## 2. Intended Use in LuminaR
* **Role:** Secondary fallback extraction for PDF pages that contain rasterized image scans lacking digital text layers.
* **Trigger Condition:** Executed only when PyMuPDF `page.get_text()` returns fewer than 50 text characters.
* **Invocation Mode:** Python wrapper calling local CLI binary `tesseract.exe` or PyMuPDF OCR extension.
* **Hardware Device:** CPU-only.

---

# Non-Deep-Learning Inference Engines Reference Card

| Component | Architecture | Mathematical Formulation | Stored / Learned Parameters |
| :--- | :--- | :--- | :--- |
| **Recommendation Engine** | 8-Factor Linear Scoring + Exponential Decay | $S = \sum_{i=1}^8 w_i f_i \cdot \exp(-\Delta t / 30) \cdot \prod (1 - d_{\text{cat}})$ | None (Hand-tuned heuristic coefficients) |
| **Knowledge Graph Linker** | Sparse TF-IDF + Cosine Similarity | $\text{sim}(d_1, d_2) = \frac{\mathbf{v}_{1} \cdot \mathbf{v}_{2}}{\|\mathbf{v}_{1}\| \|\mathbf{v}_{2}\|}$ | Corpus vocabulary dictionary & inverse document frequencies |
| **Mind Map & Flashcards** | Deterministic Syntax & TextRank | Regex pattern matching + graph centrality matrix | None (Rule-based grammar heuristics) |
| **Cloze Question Blanking** | Part-of-Speech / Salience Blanking | Inverse frequency noun selection with word masking | None (Token frequency statistics) |
