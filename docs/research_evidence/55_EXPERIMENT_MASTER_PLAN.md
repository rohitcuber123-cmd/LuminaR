# 55_EXPERIMENT_MASTER_PLAN.md: Comprehensive Experiment Master Plan (A – K)

> **Audit Report:** Part 9 Research Experiment Design  
> **Repository:** LuminaR (`d:\SDC\LibraryLLM`)  
> **Scope:** Definitive Master Plan for Experiments A through K across Search, HNSW, RAG, Hallucination, Isolation, Recommendations, and Artifacts  
> **Status:** Ground-Truth Pre-Execution Protocol  

---

## 1. Executive Master Protocol

This document establishes the execution protocol for all 11 scientific experiments (Experiments A through K) designed for the LuminaR research paper. Every experiment specifies:
- Objective & Research Question mapping
- Implemented system configurations & comparison baselines
- Test datasets & query categories
- Step-by-step non-destructive execution protocol
- Evaluation metrics & validation thresholds

---

## 2. Experiment A: Multi-Modality Catalogue Search Benchmark

### 2.1 Objective & RQ Mapping
Evaluates **RQ1**. Quantifies the retrieval quality and latency across five search paradigms over the OpenLibrary book catalogue.

### 2.2 Compared Baselines & Configurations
1. **Keyword / Regex Search (B1):** MongoDB `$regex` pattern matching over `title`, `authors`, `subjects` (`backend/services/book_service.py`).
2. **Lexical Fuzzy Search (B2):** SQLite immutable token store with NFKC normalization and Levenshtein distance (`search/lexical_store.py`).
3. **Exact Dense Search (B3):** Exhaustive inner product linear scan (`faiss.IndexFlatIP`) using `all-MiniLM-L6-v2` embeddings.
4. **Approximate Dense HNSW (B4):** Graph-based retrieval (`faiss.IndexHNSWFlat`, $M=32, efConstruction=200, efSearch=128$).
5. **Two-Stage Re-ranked Dense (B5):** HNSW candidate retrieval ($k=50$) + `ms-marco-MiniLM-L-6-v2` Cross-Encoder re-ranking (`search/luminar_search.py`).
6. **Hybrid Multi-Modality Search (B6):** Merged lexical fuzzy + HNSW dense candidates + Cross-Encoder re-ranking (`search/lexical_integration.py`).

### 2.3 Query Taxonomy (10 Categories, $N=100$ Queries)
- **Exact Title (10 queries):** Direct titles (e.g. *"Fundamentals of Deep Learning"*).
- **Author Queries (10 queries):** Exact author names (e.g. *"Nikhil Buduma"*, *"Jane Austen"*).
- **Subject / Topic (10 queries):** Standard classification categories (e.g. *"Artificial Intelligence"*, *"Computer Neural Networks"*).
- **Synonym Queries (10 queries):** Domain synonyms (e.g. *"ML handbook"* for machine learning).
- **Beginner / Pedagogical (10 queries):** Learning requests (e.g. *"deep learning for absolute beginners"*).
- **Conceptual Queries (10 queries):** Abstract themes (e.g. *"books about human habits and willpower"*).
- **Descriptive Queries (10 queries):** Plot or content summaries (e.g. *"novel about a dystopian society where books are burned"*).
- **Typographical Errors (10 queries):** 1–2 character noise (e.g. *"fundementals of depe lerning"*).
- **Ambiguous Queries (10 queries):** Polysemous terms (e.g. *"networks"*, *"python"*).
- **Library-Scoped Queries (10 queries):** Filtered to active tenant holdings with `available_at_library=True`.

### 2.4 Metrics
- Precision@5, Recall@5, MRR, nDCG@5, HitRate@5.
- Mean Latency (ms), Median Latency / p50 (ms), 95th Percentile Latency / p95 (ms).

---

## 3. Experiment B: HNSW Approximate Vector Search vs. Exact Scan

### 3.1 Objective & RQ Mapping
Evaluates **RQ2**. Maps the empirical Pareto frontier between graph search approximation error and throughput acceleration across corpus orders of magnitude.

### 3.2 Evaluation Scales
Evaluate across seven dataset sizes:
1. **1,000 vectors (1K)**
2. **5,000 vectors (5K)**
3. **10,000 vectors (10K)** `[Baseline fixture verified]`
4. **25,000 vectors (25K)**
5. **50,000 vectors (50K)**
6. **100,000 vectors (100K)**
7. **1,000,000 vectors (1M+)** `[Theoretical projection / subset validation]`

### 3.3 Metric Protocol
- **ANN 1-Recall@10:** Overlap between top-10 neighbors returned by HNSW vs exact `IndexFlatIP`:
  $$\text{ANN Recall@10} = \frac{|\text{Top10}_{\text{HNSW}} \cap \text{Top10}_{\text{Flat}}|}{10}$$
- **Mean & p95 Search Latency (ms)**: Measured over 100 random evaluation vectors.
- **Index Build Duration (seconds)**: Time required to insert and link all vectors.
- **Index File Size (MB)** and **Peak Memory Allocation (MB)**.

---

## 4. Experiment C: Semantic Query Understanding & Robustness

### 4.1 Objective & RQ Mapping
Evaluates **RQ3**. Measures the degradation penalty ($\Delta \text{MRR}$) when user queries suffer from natural typographical, lexical, or conceptual noise.

### 4.2 Test Groups & Perturbation Protocol ($N=120$ Queries)
1. **Group 1: Pristine Control ($N=20$):** Canonical reference queries from `labeled_evaluation_dataset.json`.
2. **Group 2: Typographical Perturbation ($N=20$):** Injected single/double letter transpositions, deletions, or keyboard mis-hits (e.g., *"artifishal inteligence"*).
3. **Group 3: Synonym Substitution ($N=20$):** Replaced non-stopwords with WordNet domain synonyms (e.g., *"tome on coding"* for *"book on programming"*).
4. **Group 4: Paraphrasing ($N=20$):** Natural language restatements (e.g., *"how can I pick up Python syntax"*).
5. **Group 5: Acronym Expansion / Contraction ($N=20$):** Replaced full phrases with acronyms or vice-versa (e.g., *"NLP"*, *"CNN"*, *"DBMS"*).
6. **Group 6: Vague & Exploratory ($N=20$):** High-level requests lacking keywords (e.g., *"stuff about how the mind works"*).

### 4.3 Evaluation & Failure Categorization
For each failed query (HitRate@5 = 0), classify root cause:
- `CATEGORY_A`: Incomplete vector vocabulary representation (Bi-encoder failure).
- `CATEGORY_B`: Misleading re-ranking cross-attention penalty.
- `CATEGORY_C`: Lexical tokenizer segmentation failure.

---

## 5. Experiment D: Grounded RAG vs. Parametric Zero-Shot LLM

### 5.1 Objective & RQ Mapping
Evaluates **RQ4**. Directly assesses the factual efficacy of supplying retrieved book context versus relying on internal LLM parametric weights.

### 5.2 Test Conditions
- **Condition 1 (Parametric Zero-Shot):** `Qwen/Qwen2.5-3B-Instruct` prompted with question only:
  ```text
  You are LuminaR. Answer the user's question directly.
  QUESTION: {question}
  ANSWER:
  ```
- **Condition 2 (LuminaR Grounded RAG):** `Qwen/Qwen2.5-3B-Instruct` executed through `rag/qa.py` with top-$k$ retrieved chunks formatted into `[Source X]` context blocks.

### 5.3 Test Set
- 50 book domain questions (historical facts, character relationships, technical algorithms, and specific author claims across indexed texts).

### 5.4 Evaluation Criteria
- **Factual Correctness (1–5 Likert)**: Evaluated against reference ground-truth book text.
- **Groundedness Score (0–1)**: Proportion of generated sentences supported by the text.
- **Unsupported Claim Count**: Number of ungrounded or fabricated factual assertions.
- **Generation Latency (seconds)**.

---

## 6. Experiment E: Hallucination Mitigation & Negative Abstention

### 6.1 Objective & RQ Mapping
Evaluates **RQ5**. Quantifies the system's ability to resist generating false information when questions cannot be answered from the provided documents.

### 6.2 Tripartite Question Taxonomy ($N=110$ Questions)
1. **Answer-Present ($N=40$):** Direct factual questions whose answers exist explicitly in the indexed context.
2. **Partially-Answerable ($N=30$):** Questions where only part of the inquiry is covered in the context, requiring the model to address what is present while explicitly refusing what is missing.
3. **Answer-Absent ($N=40$):** Plausible-sounding questions whose answers are completely absent from the indexed text (e.g., *"What was Dr. Smith's opinion on quantum entanglement in Chapter 3?"* when Dr. Smith is never mentioned).

### 6.3 Metric Protocol
- **Abstention Accuracy (%):** Percentage of answer-absent questions resulting in an explicit refusal verdict (`NOT_SUPPORTED` / *"The provided text does not contain information..."*).
- **Hallucination Rate (%):** Percentage of answer-absent questions where the model invents a fabricated answer.
- **Partial Refusal Precision (%):** Accuracy on partially-answerable questions.

---

## 7. Experiment F: Systematic RAG Failure Mode Taxonomy

### 7.1 Objective
Diagnoses the complete breakdown of end-to-end question answering by categorizing all non-perfect queries into a standardized 7-stage failure taxonomy.

### 7.2 Failure Categories
1. **Failure 1: Query Interpretation:** Misunderstood query intent or inverted question polarity (`rag/query_types.py`).
2. **Failure 2: Retrieval Recall:** Relevant source chunks not retrieved within initial top-$k$ vector candidates (`rag/retriever.py`).
3. **Failure 3: Chunking Boundary:** Critical evidence bisected across page or chunk boundaries (`rag/services/document_service.py`).
4. **Failure 4: Re-ranking Demotion:** Relevant chunks retrieved but ranked below the context cutoff window (`rag/reranker.py`).
5. **Failure 5: Context Construction Noise:** Prompt budget filled with distractor chunks, diluting model attention (`rag/qa.py`).
6. **Failure 6: Generative Hallucination / Distortion:** Model misinterprets supplied context or hallucinates external claims (`rag/llm.py`).
7. **Failure 7: Multi-Tenant / Session Scope Leakage:** Document belonging to foreign tenant or revoked session accessed (`rag/services/private_documents.py`).

---

## 8. Experiment G: Text Chunk Sizing & Boundary Semantics

### 8.1 Objective & RQ Mapping
Evaluates **RQ6**. Analyzes the trade-off between chunk size and semantic granularity.

### 8.2 Compared Configurations
Using the existing evaluation framework in `datasets/rag_experiments/chunking_v1`:
1. **Configuration 1 (`tokens_180`):** 180-token tight boundary chunking.
2. **Configuration 2 (`tokens_220`):** 220-token standard sliding chunking.
3. **Configuration 3 (`tokens_240`):** 240-token expanded window chunking.
4. **Configuration 4 (`current_baseline`):** Production 3,000-character sliding window with 400-character overlap (`CHUNK_SIZE = 3000, CHUNK_OVERLAP = 400`).

### 8.3 Metrics
- Retrieval Precision@5 & Recall@5 against target evidence passages.
- Downstream RAG Factual Correctness & Groundedness Score.
- Ingestion Throughput (pages processed per second).

---

## 9. Experiment H: Retrieval Depth Sensitivity ($k \in \{1, 3, 5, 10, 20\}$)

### 9.1 Objective & RQ Mapping
Evaluates **RQ7**. Identifies the Pareto optimal candidate depth $k$ for prompt context construction.

### 9.2 Protocol
Execute 50 multi-faceted evaluation questions across five context depths:
- $k = 1$ (Minimal context, lowest prefill latency)
- $k = 3$ (Default `concise` depth)
- $k = 5$ (Default `normal` depth)
- $k = 10$ (`detailed` depth)
- $k = 20$ (`comprehensive` maximum budget)

### 9.3 Metrics
- Answer Completeness (1–5 scale).
- Groundedness Score (0–1).
- Context Noise Ratio: $\frac{\text{Irrelevant Chunks in Context}}{\text{Total Context Chunks}}$.
- Prompt Prefill & Generation Latency (seconds).

---

## 10. Experiment I: Multi-Library Privacy & Tenant Isolation

### 10.1 Objective & RQ Mapping
Evaluates **RQ8**. Empirically verifies zero cross-library information leakage under multi-tenant deployment.

### 10.2 Test Environment
Provision two synthetic tenant institutions in MongoDB:
- **Tenant Alpha (`LIB_ALPHA`):** Holds books $B_1 \dots B_{50}$, private asset $A_{\alpha}$, events $E_{\alpha}$.
- **Tenant Beta (`LIB_BETA`):** Holds books $B_{25} \dots B_{75}$ (overlapping titles), private asset $A_{\beta}$, events $E_{\beta}$.

### 10.3 Adversarial Vectors ($N=200$ Automated Probes)
1. **Direct ID Forgery:** Patron Alpha submits API requests targeting `LIB_BETA` book IDs and loans.
2. **Cross-Tenant Catalogue Search:** Patron Alpha queries `/catalogue/books` with Beta-exclusive access codes.
3. **Cross-Tenant RAG QA:** Patron Alpha submits document QA queries targeting Asset $A_{\beta}$.
4. **Circulation Elevation:** Patron Alpha requests borrow on a book owned strictly by Beta.
5. **Private Document Session Sniffing:** User Alpha queries `/rag/ask` with User Beta's `document_id`.

### 10.4 Metric
$$\text{Cross-Library Leakage Rate} = \frac{\text{Unauthorized Cross-Tenant Responses (HTTP 200)}}{\text{Total Adversarial Probes}} \times 100\%$$
- **Target Invariant:** Exactly **$0.0\%$** (all probes must yield HTTP 404 concealment or HTTP 403).

---

## 11. Experiment J: Behavioral Recommendation Algorithm Evaluation

### 11.1 Objective & RQ Mapping
Evaluates **RQ9**. Compares the 8-factor hybrid recommendation engine against static baselines.

### 11.2 Compared Algorithms
1. **Random Baseline:** Random sampling from active tenant catalogue.
2. **Global Popularity Baseline:** Ranked by lifetime borrowing log count (`reading_log_count`).
3. **Content / Subject-Only Baseline:** Unweighted subject overlap matching.
4. **Current LuminaR Engine:** 8-factor hybrid model with exponential decay ($e^{-\lambda \Delta t}$) and holding availability constraints (`recommendation/recommendation_service.py`).

### 11.3 Metrics
- **Catalog Coverage (%):** Percentage of unique catalogue books recommended across all patron profiles.
- **Subject Affinity Score:** Cosine similarity between recommended book subjects and user borrowing profile.
- **Physical Availability Rate (%):** Percentage of recommended books with `requestable >= 1` in the active tenant inventory.
- **Latency (ms)** per recommendation request.

---

## 12. Experiment K: Deterministic Knowledge Artifact Synthesis Quality

### 12.1 Objective & RQ Mapping
Evaluates **RQ10**. Benchmarks the structural correctness, pedagogical validity, and latency of deterministic study intelligence synthesis.

### 12.2 Artifact Types Evaluated ($N=20$ Academic Chapters)
1. **Extractive Key Concepts & Summaries:** Evaluated for sentence boundary integrity and factual grounding.
2. **Flashcards:** Evaluated for Front (prompt) / Back (answer) separation and answer conciseness.
3. **Hierarchical Mind Maps:** Evaluated for valid SVG structure, node tree hierarchy, and absence of circular loops.
4. **MCQ Quizzes:** Evaluated for valid correct answer indexing and realistic distractor plausibility.
5. **Fill-in-the-Blank Cloze Quizzes:** Evaluated for sentence blank masking and MiniLM cosine tolerance grading (`rag/services/cloze_grading.py`).

### 12.3 Metrics
- Schema Validity Rate (%): Valid parseable JSON conforming to schema without repair.
- Source Support Rate (%): Percentage of generated facts/answers verifiable directly in source chapter text.
- MCQ Distractor Validity Rate (%): Distractors are plausible non-trivial domain concepts, not gibberish.
- Generation Latency (ms): Total time from parsed text to delivered artifact.
