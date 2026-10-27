# 13_DATASET_INVENTORY.md: LuminaR Dataset Inventory & Provenance Catalogue

## Executive Summary

This inventory catalogues every dataset, database dump, vector index, evaluation benchmark, and experimental corpus present within the LuminaR repository (`d:\SDC\LibraryLLM\datasets`). Every entry documents physical file paths, byte sizes, schemas, record counts, licenses (where explicitly stated; never fabricated), and research suitability.

---

## 1. Master Dataset Inventory Table

| Name | Physical Path | Format | Size | Record Count | Public / Private | Explicit License | Research Suitability | Reproducibility |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **OpenLibrary Books Master** | `datasets/master/books_master.parquet` | Apache Parquet | 3.19 GB | ~5,000,000 works | Public Open Data | CC0 1.0 Universal / Public Domain (OpenLibrary) | **High**: Large-scale book retrieval & cataloging | High via OpenLibrary monthly dump scripts |
| **OpenLibrary Works Table** | `datasets/cleaned/works.parquet` | Apache Parquet | 2.55 GB | ~5,000,000 rows | Public Open Data | CC0 1.0 Universal | **High**: Work title, subjects, description analysis | High via extraction scripts |
| **OpenLibrary Editions Table** | `datasets/cleaned/editions.parquet` | Apache Parquet | 3.41 GB | Multi-million | Public Open Data | CC0 1.0 Universal | **High**: ISBN, publisher, publication year | High |
| **OpenLibrary Authors Table** | `datasets/cleaned/authors.parquet` | Apache Parquet | 345 MB | ~1,200,000 rows | Public Open Data | CC0 1.0 Universal | **High**: Author entity normalization | High |
| **OpenLibrary Relational Maps** | `datasets/cleaned/edition_work.parquet`, `edition_author.parquet`, `covers.parquet` | Apache Parquet | ~1.4 GB total | Multi-million | Public Open Data | CC0 1.0 Universal | **High**: Graph construction & relational linking | High |
| **Master SQLite Database** | `datasets/library.db` | SQLite 3 | 2.23 GB | ~5,000,000 books | Local Mirror | Derived from CC0 OpenLibrary | **High**: Low-latency relational queries | High |
| **DuckDB Metadata Store** | `datasets/ai/metadata/book_metadata.duckdb` | DuckDB Columnar | 2.60 GB | ~5,000,000 records | Local Mirror | Derived from CC0 OpenLibrary | **High**: Columnar aggregation & analytical search | High |
| **DuckDB ISBN Lookup Map** | `datasets/ai/mappings/isbn_lookup.duckdb` | DuckDB Columnar | 613 MB | Multi-million ISBNs | Local Map | Derived from CC0 OpenLibrary | **High**: O(1) ISBN-10/13 to Work ID resolution | High |
| **Global 5M HNSW Vector Index** | `datasets/ai/faiss/hnsw/hnsw.index` | FAISS Binary (`IndexHNSWFlat`) | 9.04 GB | **5,000,000 vectors** | Local Artifact | Internal artifact (MiniLM embeddings of CC0 corpus) | **Critical**: Production dense retrieval evaluation | High via `search/index_manager.py` (2,058s build) |
| **HNSW Work ID Map** | `datasets/ai/faiss/hnsw/index_work_ids.npy` | NumPy binary array | 67.8 MB | 5,000,000 strings | Local Artifact | Internal index mapping | **Critical**: Maps vector index offset $\to$ `work_id` | Deterministic from index build |
| **Labeled Search Eval Dataset**| `datasets/ai/evaluation/labeled_evaluation_dataset.json` | JSON | 933 KB | ~250–500 queries | Internal Benchmark | Internal Project Benchmark (No public license) | **High**: Standardized NDCG, MRR, Recall@K testing | Versioned in repository |
| **Raw Teacher Search Judgments**| `datasets/ai/evaluation/raw_teacher_judgments.json` | JSON | 893 KB | Query-passage pairs | Internal Benchmark | Internal Project Benchmark (No public license) | **High**: Cross-encoder relevance training & distillation | Versioned in repository |
| **RAG Baseline Chunk Corpus** | Production RAG runtime | JSON / SQLite | ~15 MB | **3,959 chunks** | Private / Domain Books | All rights reserved (Library domain books) | **High for audit**: 100% truncated by 256-token model | Audited in `reports/rag_embedding_truncation_audit.md` |
| **RAG 220-Token Chunk Variant**| `datasets/rag_experiments/chunking_v1/tokens_220/` | Parquet / JSON | ~25 MB | **16,895 passages** | Experimental Corpus | Internal experimental derivation | **High**: Evaluates window-aligned passage chunking | High via `scripts/build_rag_chunk_variants.py` |
| **Generic Pilot Training Pairs**| `datasets/training/processed/` | JSONL | Variable | 2,000 NQ + 1,000 SQuAD | Public Research Data | Apache 2.0 (NQ / SQuAD) | **Moderate**: Pilot exploration for bi-encoder fine-tuning | Streamed from Hugging Face Datasets |
| **Private Document PDFs** | `rag/private_documents/` | PDF / EPUB | Variable | User-dependent | Strictly Private | User / Institution owned | **Low (Confidential)**: Not suitable for public release | Not reproducible (Ad-hoc user uploads) |

---

## 2. In-Depth Dataset Profiles

### 2.1 OpenLibrary Master Catalogue (`books_master.parquet` & `library.db`)
* **Source:** Open Data dumps published by the Internet Archive Open Library project.
* **Format:** Apache Parquet (snappy compression) + SQLite 3 table.
* **Fields:**
  * `work_id` (string, e.g. `"OL1000000W"`)
  * `title` (string)
  * `authors` (list of strings)
  * `subjects` / `genres` (list of strings)
  * `description` (string, variable length)
  * `first_publish_year` (integer)
  * `ratings_average` (float 1.0–5.0)
  * `ratings_count` (integer)
  * `reading_log_count` (integer)
  * `cover_id` (integer)
* **Explicit License:** Public Domain / CC0 1.0 Universal.
* **Research Suitability:** Excellent for zero-shot IR benchmarks, large-scale lexical search experiments, and recommendation profiling.

---

### 2.2 Global Dense Vector HNSW Index (`hnsw.index`)
* **Metadata Record:** `datasets/ai/faiss/hnsw/hnsw_metadata.json`
* **Size:** 9,040,711,138 bytes (~9.04 GB).
* **Vector Count:** Exactly **5,000,000 vectors** ($d = 384$).
* **Metric:** Inner Product (`METRIC_INNER_PRODUCT`) on L2-normalized float32 vectors.
* **HNSW Hyperparameters:**
  * $M = 32$ (edges per node)
  * $efConstruction = 200$
  * $efSearch = 64$ (default, overridden to 128 at runtime in `search/luminar_search.py:67`)
* **Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2`.
* **Build Time:** 2,058.11 seconds (~34.3 minutes) on host hardware.
* **Research Suitability:** High. Serves as the frozen ground-truth vector baseline for all LuminaR hybrid search and R0 retrieval experiments.

---

### 2.3 RAG Benchmark & Chunking Experiment Corpora
* **Corpus 1: Production Baseline (`3,959 chunks`)**
  * Average length: 648.9 tokens (median 659.0 tokens).
  * 100% of chunks exceed the 256-token effective window of `all-MiniLM-L6-v2`.
  * Documented in [reports/rag_embedding_truncation_audit.md](file:///d:/SDC/LibraryLLM/reports/rag_embedding_truncation_audit.md).
* **Corpus 2: Experimental 220-Token Variant (`16,895 passages`)**
  * Derived by re-chunking domain books with strict 220-token ceiling (leaving 36 tokens for special tokens and query prepending).
  * 0% truncation under `all-MiniLM-L6-v2`.
  * Documented in [datasets/training/README.md](file:///d:/SDC/LibraryLLM/datasets/training/README.md).

---

### 2.4 Labeled IR Evaluation Benchmarks (`labeled_evaluation_dataset.json`)
* **Size:** 933,578 bytes.
* **Schema:**
  ```json
  [
    {
      "query_id": "Q001",
      "query": "principles of classical mechanics lagrangian",
      "relevant_work_ids": ["OL12345W", "OL67890W"],
      "relevance_grades": {"OL12345W": 3, "OL67890W": 2},
      "intent": "academic_subject"
    }
  ]
  ```
* **Teacher Source:** Cross-encoder soft labels generated by `cross-encoder/ms-marco-MiniLM-L-6-v2` (`raw_teacher_judgments.json`).
* **Research Suitability:** Provides reproducible ground-truth labels for evaluating lexical vs dense vs hybrid search ranking quality (NDCG@10, MAP, MRR).
