# 08_MODEL_RUNTIME_CONFIGURATION.md: Master Runtime Configuration & Hyperparameter Catalogue

## Executive Summary

This document catalogues every runtime configuration constant, threshold, weight matrix, hyperparameter, and environment variable governing AI/ML inference, retrieval, and ranking in LuminaR. Every entry references its concrete source file path and line number.

---

## 1. Generative LLM (`Qwen2.5-3B-Instruct`) Runtime Constants

**File Path:** `LibraryLLM/rag/llm.py` & `LibraryLLM/rag/qa.py`

| Configuration Key | Runtime Value | Type | Purpose & Impact | Source Reference |
| :--- | :--- | :--- | :--- | :--- |
| `DEFAULT_MODEL_NAME` | `"Qwen/Qwen2.5-3B-Instruct"` | `str` | Default Hugging Face repository identifier for local model load | `rag/llm.py:46` |
| `MAX_CONTEXT_CHARS` | `24000` | `int` | Hard character ceiling on prompt context (~6,000 BPE tokens) | `rag/llm.py:49`, `rag/qa.py:70` |
| `load_in_4bit` | `True` | `bool` | Enables bitsandbytes 4-bit weight quantization on CUDA | `rag/llm.py:152` |
| `bnb_4bit_quant_type` | `"nf4"` | `str` | NormalFloat4 non-linear quantization data type | `rag/llm.py:153` |
| `bnb_4bit_use_double_quant` | `True` | `bool` | Enables double quantization of quantization scale factors | `rag/llm.py:154` |
| `bnb_4bit_compute_dtype` | `torch.float16` | `torch.dtype` | FP16 compute dtype for linear matrix multiplications | `rag/llm.py:155` |
| `local_files_only` | `True` | `bool` | Prevents outbound internet calls; enforces local air-gapped cache | `rag/llm.py:130, 165` |
| `do_sample` | `False` | `bool` | Enforces greedy deterministic decoding | `rag/llm.py:352` |
| `temperature` (default) | `0.2` | `float` | Signature parameter (bypassed in greedy mode) | `rag/llm.py:270` |
| `temperature` (intent) | `0.1` | `float` | Signature parameter for intent extraction | `rag/llm.py:456` |
| `top_p` | `0.9` | `float` | Signature parameter (bypassed in greedy mode) | `rag/llm.py:271` |
| `max_new_tokens` (validator)| `160` | `int` | Token cap for evidence validation JSON schema | `rag/llm.py:512` |
| `max_new_tokens` (intent) | `400` | `int` | Token cap for intent classification JSON schema | `rag/llm.py:458` |
| `max_new_tokens` (concise) | `300` | `int` | Generation budget for concise QA responses | `rag/qa.py:182` |
| `max_new_tokens` (default) | `320` | `int` | Standard generation budget for QA responses | `rag/qa.py:185` |
| `max_new_tokens` (detailed)| `1000` | `int` | Generation budget for deep in-depth answers | `rag/qa.py:188` |
| `max_new_tokens` (compr.) | `1500` | `int` | Generation budget for multi-section study guides | `rag/qa.py:191` |
| `ASSISTANT_QWEN_TIMEOUT` | `60.0` | `float` | Max allowable seconds before timing out assistant generation | `assistant/orchestrator.py:42` |

---

## 2. Dense Embedding Model (`all-MiniLM-L6-v2`) Runtime Constants

**File Paths:** `LibraryLLM/search/luminar_search.py`, `LibraryLLM/search/index_manager.py`, `LibraryLLM/rag/retriever.py`

| Configuration Key | Runtime Value | Type | Purpose & Impact | Source Reference |
| :--- | :--- | :--- | :--- | :--- |
| `EMBEDDING_MODEL` | `"all-MiniLM-L6-v2"` | `str` | Model identifier loaded via `SentenceTransformer` | `search/luminar_search.py:55` |
| `EMBEDDING_DIM` | `384` | `int` | Vector dimensionality of embeddings | `search/index_manager.py:29` |
| `max_seq_length` | `256` | `int` | WordPiece token truncation ceiling | `search/index_manager.py:35` |
| `batch_size` (books build) | `64` | `int` | Batch size during bulk book corpus indexing | `search/index_manager.py:145` |
| `batch_size` (docs build) | `32` | `int` | Batch size during private document chunk indexing | `rag/services/document_service.py:112` |
| `batch_size` (query) | `1` | `int` | Batch size for real-time user query encoding | `search/luminar_search.py:488` |
| `HNSW_M` | `32` | `int` | Number of bi-directional links per node in FAISS HNSW graph | `search/index_manager.py:72` |
| `EF_CONSTRUCTION` | `200` | `int` | Depth of nearest neighbor exploration during index build | `search/index_manager.py:73` |
| `EF_SEARCH` | `128` | `int` | Depth of exploration during query traversal in HNSW graph | `search/luminar_search.py:67` |
| `MAX_CACHED_BOOKS` | `5` | `int` | Number of book indexes held in RAM in retriever cache | `rag/retriever.py:80` |

---

## 3. Cross-Encoder Reranker (`ms-marco-MiniLM-L-6-v2`) Runtime Constants

**File Paths:** `LibraryLLM/search/luminar_search.py` & `LibraryLLM/rag/reranker.py`

| Configuration Key | Runtime Value | Type | Purpose & Impact | Source Reference |
| :--- | :--- | :--- | :--- | :--- |
| `RERANKER_MODEL` | `"cross-encoder/ms-marco-MiniLM-L-6-v2"` | `str` | Pretrained cross-encoder weights identifier | `search/luminar_search.py:57` |
| `CROSSENCODER_RERANK_DEPTH` | `50` | `int` | Number of first-stage search candidates passed to cross-encoder | `search/luminar_search.py:63` |
| `RERANK_BATCH_SIZE` | `16` | `int` | Query-passage pair evaluation batch size | `search/luminar_search.py:69` |
| `SEARCH_MAX_RETURN_RESULTS` | `50` | `int` | Final hard limit on search results returned to client | `search/luminar_search.py:65` |
| `MAX_MULTIQ_CANDIDATES` | `40` | `int` | Ceiling on total candidates gathered across multi-query expansions | `rag/reranker.py:213` |
| `TOP_K_CHUNKS` (QA) | `5` | `int` | Number of top reranked chunks injected into RAG LLM context | `rag/qa.py:112` |

---

## 4. Recommendation Engine 8-Factor Weight Constants

**File Path:** `LibraryLLM/recommendation/recommendation_service.py:33-88`

| Factor | Weight Variable | Mathematical Weight | Signal Category |
| :--- | :--- | :--- | :--- |
| **Semantic Relevance** | `SEMANTIC_WEIGHT` | **0.40** (40%) | Dense vector match with user interaction history |
| **Subject Match** | `SUBJECT_WEIGHT` | **0.15** (15%) | Exact category/genre overlap |
| **Author Affinity** | `AUTHOR_WEIGHT` | **0.10** (10%) | Author preference derived from past borrows |
| **Borrowing Behavior** | `BORROWING_WEIGHT` | **0.15** (15%) | Books similar to previously issued titles |
| **Reservation Behavior** | `RESERVATION_WEIGHT` | **0.10** (10%) | Books similar to active/past reservations |
| **User Rating** | `RATING_WEIGHT` | **0.05** (5%) | Normalized 1–5 star global ratings |
| **Circulation Popularity** | `POPULARITY_WEIGHT` | **0.03** (3%) | Total aggregate borrow count across library |
| **Physical Availability** | `AVAILABILITY_WEIGHT` | **0.02** (2%) | Binary boost if `available_copies > 0` |
| **Total Linear Sum** | | **1.00** (100%) | Normalized compound score |

### Interaction & Diversity Tuning Constants
* `CANDIDATE_COUNT = 50`: Initial candidate pool pulled from search service.
* `DECAY_RATE = 0.15`: Exponential time decay rate applied per 30-day epoch.
* `MAX_PROFILE_QUERIES = 10`: Cap on past search queries used to construct recommendation profile.
* `MAX_BOOKS_PER_AUTHOR = 2`: Diversity cap preventing a single author from dominating recommendations.
* `SUBJECT_SIMILARITY_THRESHOLD = 0.80`: Suppresses near-duplicate subjects.
* `TITLE_SIMILARITY_THRESHOLD = 0.80`: Suppresses duplicate title editions.

---

## 5. Environment Variables Reference

| Variable Name | Default Value | Used In | Effect |
| :--- | :--- | :--- | :--- |
| `LUMINAR_MODEL_DIR` | None (`~/.cache/huggingface`) | `rag/llm.py` | Local disk directory override for model weights |
| `ASSISTANT_QWEN_TIMEOUT`| `"60.0"` | `assistant/orchestrator.py` | Timeout in seconds for conversational replies |
| `MONGO_URI` | `"mongodb://localhost:27017"` | `recommendation/`, `search/` | Connection URI for metadata MongoDB |
| `MONGO_DB_NAME` | `"luminar_library"` | `recommendation/`, `search/` | Target MongoDB database name |
| `LUMINAR_SEARCH_MAX_CANDIDATES`| `"1000"` | `search/luminar_search.py` | Candidate ceiling for dense vector search |
| `LOAN_RENEWAL_DAYS` | `"14"` | `backend/services/loan_service.py`| Base loan renewal extension duration |
| `LOAN_MAX_RENEWALS` | `"2"` | `backend/services/loan_service.py`| Maximum renewals permitted per checkout |
