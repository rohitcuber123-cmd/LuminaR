# 51_SCALABILITY_ANALYSIS.md: Theoretical Scalability & Dimension Projections

> **Audit Report:** Part 8 Research Evidence Audit  
> **Repository:** LuminaR (`d:\SDC\LibraryLLM`)  
> **Scope:** Theoretical Multi-Dimensional Scalability Analysis across Books, Tenants, and Vector Chunks  
> **Status:** Theoretical Architectural Projection (**NOT MEASURED unless explicitly noted**)  

---

## 1. Architectural Scaling Dimensions & Mathematical Foundations

LuminaR's architecture scales across three orthogonal axes:
1. **Bibliographic Catalogue Volumes ($N_{\text{books}}$):** $100 \rightarrow 1,000,000$ books.
2. **Institutional Tenancy Partitioning ($N_{\text{libraries}}$):** $1 \rightarrow 10,000$ libraries.
3. **Unstructured Document Chunks ($N_{\text{chunks}}$):** $10,000 \rightarrow 1,000,000+$ chunks.

### Mathematical Memory & Complexity Formulations

$$\text{Memory}_{\text{vector}} = d \times 4 \text{ bytes} = 384 \times 4 = 1,536 \text{ bytes/vector}$$
$$\text{Memory}_{\text{HNSW\_graph}} \approx 2 \times M \times 8 \text{ bytes} = 2 \times 32 \times 8 = 512 \text{ bytes/vector}$$
$$\text{Memory}_{\text{node\_total}} \approx 1,536 + 512 = 2,048 \text{ bytes} = 2.0 \text{ KiB/book}$$
$$\text{Search Complexity} = \mathcal{O}\left(\log(N_{\text{books}}) \cdot efSearch \cdot d\right)$$

---

## 2. Dimension A: Books Scalability ($100 \rightarrow 1\text{M}$)

> [!IMPORTANT]
> Projections in this section are **THEORETICAL CALCULATIONS** based on FAISS HNSW graph topology ($M=32, efConstruction=200, efSearch=128$) and MongoDB B-tree index schemas. They are **NOT EMPIRICALLY MEASURED** except where tagged `[MEASURED: 10K]`.

| Metric | 100 Books | 1,000 (1K) | 10,000 (10K) | 100,000 (100K) | 1,000,000 (1M) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Raw 384-D Vector Array** | 150.0 KiB | 1.46 MiB | 14.65 MiB | 146.48 MiB | 1.43 GiB |
| **FAISS HNSW RAM Index** | 200.0 KiB | 1.95 MiB | **17.20 MiB** `[MEASURED]` | 195.31 MiB | 1.91 GiB |
| **Search Traversal Latency (p50)** | $< 0.10 \text{ ms}$ | $0.18 \text{ ms}$ | **0.31 ms** `[MEASURED]` | $0.48 \text{ ms}$ | $0.68 \text{ ms}$ |
| **Cross-Encoder Rerank (50 cands)** | 45.96 ms | 45.96 ms | **45.96 ms** `[MEASURED]` | 45.96 ms | 45.96 ms |
| **MongoDB Books Storage** | ~150 KiB | ~1.50 MiB | ~15.0 MiB | ~150 MiB | ~1.50 GiB |
| **MongoDB B-Tree Index Footprint**| ~80 KiB | ~800 KiB | ~8.0 MiB | ~80 MiB | ~800 MiB |
| **Index Construction Duration** | $< 0.2 \text{ s}$ | ~1.8 s | ~22.5 s | ~4.8 min | ~55.0 min |

### Key Scalability Observations:
1. **Sub-Linear Search Latency:** Because HNSW graph traversal complexity scales logarithmically ($\mathcal{O}(\log N)$), expanding the catalogue by a factor of $100\times$ (from 10K to 1M books) only increases graph traversal time by $\approx 2.2\times$ (from 0.31 ms to 0.68 ms).
2. **Invariant Reranker Overhead:** The second-stage neural cross-encoder always processes exactly 50 candidates (`CROSSENCODER_RERANK_DEPTH = 50`). Its execution latency remains invariant (~50 ms) regardless of whether the library holds 1,000 books or 1,000,000 books.
3. **RAM Feasibility:** A 1,000,000-book catalogue fits entirely into **~2 GB of system RAM**, permitting deployment on standard budget cloud virtual machines without dedicated vector databases.

---

## 3. Dimension B: Tenant Libraries Scalability ($1 \rightarrow 10,000$)

> [!IMPORTANT]
> Projections in this section evaluate the multi-tenant architecture on a **single shared MongoDB instance** using composite indexing. **THEORETICAL ANALYSIS — NOT EMPIRICALLY MEASURED.**

| Metric | 1 Library | 10 Libraries | 100 Libraries | 1,000 (1K) | 10,000 (10K) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Active Tenant Collections** | 29 collections | 29 collections | 29 collections | 29 collections | 29 collections |
| **Tenancy Partitions** | 1 `library_id` | 10 `library_id` | 100 `library_id` | 1,000 `library_id` | 10,000 `library_id` |
| **Locks Collection Rows** | 1 row | $\le 10$ rows | $\le 100$ rows | $\le 1,000$ rows | $\le 10,000$ rows |
| **Membership Index Size** | ~16 KiB | ~160 KiB | ~1.6 MiB | ~16 MiB | ~160 MiB |
| **Lending Journal Overhead** | ~50 KiB | ~500 KiB | ~5.0 MiB | ~50 MiB | ~500 MiB |
| **Tenant Lock Contention Risk** | Zero (1 tenant) | Zero (Isolated) | Zero (Isolated) | Negligible | Low (Isolated) |
| **Cross-Tenant Leakage Probability**| Zero (Scoped) | Zero (Scoped) | Zero (Scoped) | Zero (Scoped) | Zero (Scoped) |

### Key Scalability Observations:
1. **Zero Cross-Tenant Contention:** Because `library_mutation(library_id)` uses `_id: library_id` in `institution_locks`, a write transaction in Library A **never blocks reads or writes in Library B**. Lock contention is strictly confined within each individual tenant.
2. **Index Cardinality Optimization:** All composite indexes prefix `library_id` as the leading key (e.g., `{ "library_id": 1, "accession_number": 1 }`). MongoDB's wiredTiger B-tree engine efficiently prunes non-matching tenant trees, ensuring $O(\log M)$ index lookup times where $M$ is the size of the tenant's individual holdings, not the platform total.
3. **Bottleneck at 10,000 Libraries:** At 10,000 active libraries with concurrent users, the single-node standalone MongoDB instance experiences connection pool saturation. Scaling past 1,000 libraries requires sharding the database cluster using `library_id` as the **shard key**.

---

## 4. Dimension C: Document Chunks Scalability ($10\text{K} \rightarrow 1\text{M}+$)

> [!IMPORTANT]
> Projections in this section evaluate the RAG and Knowledge Artifact chunking architecture. **THEORETICAL ANALYSIS — NOT EMPIRICALLY MEASURED.**

| Metric | 10,000 Chunks | 100,000 Chunks | 1,000,000 (1M) Chunks | 5,000,000 (5M) Chunks |
| :--- | :---: | :---: | :---: | :---: |
| **Typical Corpus Equivalent** | ~50 Books / Documents | ~500 Books | ~5,000 Books | ~25,000 Books |
| **Raw Text Storage (UTF-8)** | ~15.0 MiB | ~150.0 MiB | ~1.46 GiB | ~7.32 GiB |
| **Vector Embedding Storage (384-D)** | ~14.6 MiB | ~146.5 MiB | ~1.43 GiB | ~7.15 GiB |
| **Flat Vector Search (IndexFlatIP)**| **~1.2 ms** | ~11.5 ms | ~114.0 ms | ~570.0 ms |
| **HNSW Vector Search ($M=32$)** | **~0.3 ms** | ~0.5 ms | ~0.7 ms | ~0.9 ms |
| **Cosine Cloze Semantic Grading** | ~0.8 ms | ~0.8 ms | ~0.8 ms | ~0.8 ms |
| **Ingestion Embedding GPU Time** | ~45 s | ~7.5 min | ~1.25 hours | ~6.25 hours |
| **Ingestion Embedding CPU Time** | ~6.5 min | ~65.0 min | ~10.8 hours | ~54.0 hours |

### Key Scalability Observations:
1. **Flat Index Degeneration:** Private document sessions use FAISS `IndexFlatIP` (`rag/services/private_documents.py:107`), which performs exhaustive inner product scans. While lightning fast for single documents ($< 500$ chunks, $< 0.1 \text{ ms}$), exhaustive search scales linearly $\mathcal{O}(N)$. At 1,000,000 chunks, flat search latency degrades to **~114 ms**, requiring transition to HNSW or IVF indexes.
2. **Embedding Throughput Barrier:** Generating 384-dimensional embeddings for 1,000,000 chunks on CPU requires $\sim 10.8 \text{ hours}$ of continuous computation. Large-scale document chunk ingestion requires GPU acceleration (`batch_size=64`, ~1.25 hours).
3. **Artifact Generation Immunity:** Cloze semantic answer grading (`rag/services/cloze_grading.py`) only embeds the student's single-sentence submission and compares cosine similarity against the canonical answer embedding ($1 \times 384$). Its performance (**~0.8 ms**) is completely decoupled from total repository chunk volume.

---

## 5. Architectural Scalability Limits Summary

```text
========================================================================================
DIMENSION           CURRENT THRESHOLD      NEXT BOTTLENECK            REQUIRED MITIGATION
========================================================================================
Books               5,000,000 vectors      RAM capacity (10 GB)       FAISS IndexIVFFlat / DiskANN
Libraries           100 tenants            Mongo Connection Pool      Sharded Mongo Cluster (shard on library_id)
Document Chunks     10,000 per session     IndexFlatIP scan latency   HNSW per tenant asset collection
LLM Generation      1 request concurrent   GPU VRAM / CUDA Lock       vLLM Continuous Batching / Multi-GPU
========================================================================================
```
