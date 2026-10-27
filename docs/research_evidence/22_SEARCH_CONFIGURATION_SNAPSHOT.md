# 22_SEARCH_CONFIGURATION_SNAPSHOT.md: Search Runtime Configuration Snapshot

## Executive Summary

This document records the exact runtime constants, environment variables, default thresholds, hyperparameters, and directory paths governing search, vector retrieval, and ranking in LuminaR. Every entry references its concrete source file and line number.

---

## 1. Search Engine Hyperparameters & Runtime Constants

| Constant Name | Value | Type | Source File & Line | Operational Effect |
| :--- | :--- | :--- | :--- | :--- |
| `EMBEDDING_MODEL` | `"all-MiniLM-L6-v2"` | `str` | `search/luminar_search.py:55` | Pretrained model loaded for dense query encoding |
| `RERANKER_MODEL` | `"cross-encoder/ms-marco-MiniLM-L-6-v2"` | `str` | `search/luminar_search.py:57` | Pretrained cross-encoder weights for reranking |
| `DIMENSION` / `EMBEDDING_DIM` | `384` | `int` | `search/index_manager.py:32` | Dimensionality ($d$) of vector embeddings and FAISS index |
| `SEMANTIC_MIN_VALID_CANDIDATES`| `50` | `int` | `search/luminar_search.py:61` | Minimum valid candidates required before reranking |
| `CROSSENCODER_RERANK_DEPTH` | `50` | `int` | `search/luminar_search.py:63` | Candidate pool size evaluated by cross-encoder |
| `SEARCH_MAX_RETURN_RESULTS` | `50` | `int` | `search/luminar_search.py:65` | Upper ceiling on results returned per request |
| `EF_SEARCH` | `128` | `int` | `search/luminar_search.py:67` | HNSW nearest-neighbor search exploration beam |
| `RERANK_BATCH_SIZE` | `16` | `int` | `search/luminar_search.py:69` | Forward-pass batch size for cross-encoder |
| `WARMUP_ITERATIONS` | `5` | `int` | `search/luminar_search.py:72` | Synthetic forward passes run on server boot |
| `HNSW_M` | `32` | `int` | `search/index_manager.py:54` | Number of bi-directional connection edges per node |
| `EF_CONSTRUCTION` | `200` | `int` | `search/index_manager.py:55` | Exploration depth during HNSW graph construction |
| `SEARCH_RANKED_POOL_SIZE` | `100` | `int` | `search/ranked_pages.py:8` | In-memory candidate pool retained for pagination |
| `POLL_SECONDS` | `2` | `int` | `search/index_manager.py:115`| Background thread sync queue poll frequency |
| `CORPUS_LIMIT` | `5_000_000` | `int` | `search/index_manager.py:115`| Hard upper capacity bound on indexed books |

---

## 2. Environment Variables & Overrides

| Environment Variable | Default Value | Used In | Operational Behavior |
| :--- | :--- | :--- | :--- |
| `LUMINAR_SEARCH_OVERFETCH_FACTOR`| `"2"` | `search/luminar_search.py:449` | Multiplier used in dynamic HNSW expansion loop |
| `LUMINAR_SEARCH_MAX_CANDIDATES` | `"1000"` | `search/luminar_search.py:450` | Hard limit on maximum candidate overfetch |
| `LEXICAL_SEARCH_ENABLED` | `"false"` | `search/luminar_search.py:470` | Feature toggle activating SQLite lexical sidecar |
| `LUMINAR_LEXICAL_PATH` | `datasets/ai/lexical/published` | `search/lexical_store.py:44` | Disk directory for lexical SQLite snapshots |
| `MONGO_URI` | `"mongodb://localhost:27017"` | `search/luminar_search.py:47` | Connection string for metadata database |
| `MONGO_DB_NAME` | `"luminar_library"` | `search/luminar_search.py:48` | MongoDB database name |

---

## 3. Lexical Sidecar & Typo Assistance Constants

**File Paths:** `LibraryLLM/search/lexical_store.py`, `LibraryLLM/search/lexical_integration.py`, `LibraryLLM/search/typo_assistance.py`

| Configuration Key | Runtime Value | Type | Purpose & Impact | Source Reference |
| :--- | :--- | :--- | :--- | :--- |
| `SCHEMA_VERSION` | `2` | `int` | SQLite lexical database schema version | `search/lexical_store.py:13` |
| `NORMALIZATION_VERSION` | `'nfkc-casefold-space-v1'` | `str` | Text normalization algorithm identifier | `search/lexical_store.py:14` |
| `MAX_CANDIDATES` | `100` | `int` | Upper candidate bound for lexical lookup | `search/lexical_store.py:15` |
| `DEFAULT_CANDIDATES` | `50` | `int` | Default candidates requested from lexical store | `search/lexical_store.py:16` |
| `MAX_WORK_IDS_PER_VALUE` | `50` | `int` | Max books associated with single title/author | `search/lexical_store.py:17` |
| `MAX_CANDIDATE_SEEKS` | `512` | `int` | Maximum B-tree seeks allowed per fuzzy query | `search/lexical_store.py:18` |
| `MAX_QUERY_LENGTH` | `256` | `int` | Max character length accepted for lexical search | `search/lexical_store.py:19` |
| `MIN_FUZZY_LENGTH` | `5` | `int` | Minimum word length required before attempting fuzzy typo probes | `search/lexical_store.py:20` |
| `FUZZY_THRESHOLD` | `0.86` | `float` | Minimum `SequenceMatcher` similarity ratio | `search/lexical_store.py:21`, `search/typo_assistance.py:25` |
| `FUZZY_MARGIN` | `0.05` | `float` | Minimum lead between top match and second match | `search/lexical_store.py:22`, `search/typo_assistance.py:25` |
| `MAX_EDIT_PREFIXES` | `256` | `int` | Maximum single-edit permutations probed | `search/lexical_store.py:23` |
| `SIGNAL_LIMITS` | `{'exact_title': 10, 'exact_author': 10, 'fuzzy_title': 5, 'fuzzy_author': 5}` | `dict` | Max candidates injected per signal type | `search/lexical_integration.py:6-11` |
| `FUZZY_SCORE_BOOST` | `{'fuzzy_title': 0.02, 'fuzzy_author': 0.01}` | `dict` | Score additive adjustments for fuzzy signals | `search/lexical_integration.py:12` |

---

## 4. Key Performance Indicators & Status

To maintain scientific integrity, performance metrics are catalogued strictly as measured in repository benchmarks or marked **NOT MEASURED**:

| Metric | Status | Repository Evidence / Measured Value |
| :--- | :---: | :--- |
| **Model Load Latency (MiniLM)** | **MEASURED** | Recorded at startup: ~45–120 ms (CUDA) / ~180–350 ms (CPU) |
| **Model Load Latency (Reranker)**| **MEASURED** | Recorded at startup: ~65–140 ms (CUDA) / ~220–410 ms (CPU) |
| **HNSW Build Latency (5M vectors)**| **MEASURED** | Exactly **2,058.11 seconds** (~34.3 minutes) in `hnsw_metadata.json` |
| **Vector Dimension** | **CONFIRMED** | Exactly 384 dimensions ($d = 384$) |
| **P95 End-to-End Query Latency** | **NOT MEASURED** | Benchmarking across variable concurrency (1, 10, 50 clients) required |
| **HNSW Recall@50 vs Exact Flat** | **NOT MEASURED** | Formal comparative recall benchmark on 5M corpus required |
| **Post-Filtering Recall Degradation**| **NOT MEASURED** | Exact drop in Recall@10 across varying library inventory fractions ($\rho$) required |
| **NDCG@10 Hybrid vs Dense Only** | **NOT MEASURED** | Requires evaluation against `labeled_evaluation_dataset.json` |
