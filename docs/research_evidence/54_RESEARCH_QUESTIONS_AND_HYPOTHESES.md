# 54_RESEARCH_QUESTIONS_AND_HYPOTHESES.md: Research Questions & Scientific Hypotheses

> **Audit Report:** Part 9 Research Experiment Design  
> **Repository:** LuminaR (`d:\SDC\LibraryLLM`)  
> **Scope:** Formal Research Questions, Hypotheses, Variables, Baselines, and Implementation Readiness  
> **Status:** Ground-Truth Experiment Specification (Pre-Execution Protocol)  

---

## 1. Research Overview & Problem Formulation

LuminaR addresses the critical challenge of unifying **large-scale library catalogue information retrieval (5,000,000 books)**, **multi-tenant institutional isolation**, and **low-latency grounded generative study assistance** on accessible commodity hardware. 

To evaluate the system defensibly for scientific publication, we formulate ten formal research questions spanning information retrieval, vector indexing, query robustness, retrieval-augmented generation (RAG), hallucination mitigation, multi-tenancy privacy, recommendation systems, and deterministic knowledge synthesis.

---

## 2. Research Questions (RQ1 – RQ10)

### RQ1: Multi-Stage Hybrid Retrieval vs. Single-Modality Baselines
- **Research Question:** Does a two-stage hybrid retrieval architecture combining Bi-Encoder dense retrieval (`all-MiniLM-L6-v2`), SQLite-backed lexical fuzzy matching, and Cross-Encoder re-ranking (`ms-marco-MiniLM-L-6-v2`) achieve statistically superior retrieval effectiveness (nDCG@5, MRR) across natural language book queries compared to pure lexical or unranked dense retrieval?
- **Hypothesis ($H_1$):** Hybrid retrieval with cross-attention re-ranking achieves an nDCG@5 $\ge 0.85$, outperforming pure keyword search ($p < 0.01$) by resolving vocabulary mismatch in conceptual queries, while outperforming unranked dense retrieval by correcting top-rank false positive semantic drift.
- **Independent Variable:** Retrieval Pipeline Architecture (Regex Keyword, Pure Lexical Fuzzy, Unranked Dense HNSW, Dense + Cross-Encoder, Hybrid Merged + Cross-Encoder).
- **Dependent Variables:** nDCG@5, MRR, Precision@5, HitRate@5, End-to-End Latency (ms).
- **Baseline:** MongoDB Text/Regex Search, Unranked FAISS HNSW.
- **Dataset:** `datasets/ai/evaluation/labeled_evaluation_dataset.json` (30 test queries with graded relevance from cross-encoder teacher).
- **Metric:** nDCG@5, MRR, Mean & p95 Latency.
- **Implementation Readiness:** **READY (Implemented)** in `search/luminar_search.py` and `search/lexical_integration.py`.

---

### RQ2: HNSW Approximate Vector Search Efficiency & Recall Trade-off
- **Research Question:** What is the empirical trade-off between Approximate Nearest Neighbor (ANN) Recall@10 and search latency when scaling FAISS `IndexHNSWFlat` ($M=32, efSearch=128$) against exact brute-force inner product scan (`IndexFlatIP`) across catalogue scales from 1,000 to 1,000,000 books?
- **Hypothesis ($H_2$):** HNSW maintains an ANN Recall@10 $\ge 0.95$ relative to brute-force search while reducing query latency by over $20\times$ at 100K+ catalogue scale, with memory overhead scaling linearly at $\sim 2.0\text{ KB}$ per book.
- **Independent Variable:** Indexing Algorithm (`IndexFlatIP` vs `IndexHNSWFlat`) and Corpus Scale ($N \in \{1\text{K}, 5\text{K}, 10\text{K}, 25\text{K}, 50\text{K}, 100\text{K}, 1\text{M}\}$).
- **Dependent Variables:** ANN Recall@10 (1-Recall overlap), Mean Search Latency (ms), p95 Latency (ms), Index File Size (MB), Build Time (s).
- **Baseline:** Exact Brute-Force Inner Product Scan (`faiss.IndexFlatIP`).
- **Dataset:** Stratified subset of OpenLibrary catalogue embeddings (`datasets/ai/embeddings`).
- **Metric:** 1-Recall@10, Mean & p95 Latency, Index Size.
- **Implementation Readiness:** **READY (Implemented)** in `search/index_manager.py` and `benchmarks/embedding_model_comparison`.

---

### RQ3: Semantic Query Understanding & Robustness to Query Degradation
- **Research Question:** How resilient is LuminaR's semantic retrieval pipeline against varied natural language query degradations (misspellings/typos, domain acronyms, paraphrasing, and vague intent) compared to lexical token matching?
- **Hypothesis ($H_3$):** Bi-Encoder dense embedding combined with cross-encoder re-ranking retains $> 80\%$ of its pristine MRR when subjected to typographical noise and semantic paraphrasing, whereas lexical keyword search degrades by $> 50\%$.
- **Independent Variable:** Query Degradation Category (Pristine, 1–2 Character Typos, Synonym Substitution, Acronym Expansion/Abbreviation, Vague Conceptual Descriptions).
- **Dependent Variables:** MRR, HitRate@5, Degradation Penalty ($\Delta \text{MRR} = \text{MRR}_{\text{degraded}} / \text{MRR}_{\text{pristine}}$).
- **Baseline:** Pristine query execution and SQLite lexical search (`search/lexical_store.py`).
- **Dataset:** Curated query perturbation benchmark generated from `labeled_evaluation_dataset.json`.
- **Metric:** MRR, Precision@5, HitRate@5.
- **Implementation Readiness:** **READY (Implemented)** in `search/typo_assistance.py` and `search/luminar_search.py`.

---

### RQ4: Grounded RAG vs. Parametric LLM Generation
- **Research Question:** To what extent does RAG with locally resident `Qwen2.5-3B-Instruct` improve factual claim precision and eliminate bibliographic hallucinations compared to zero-context parametric generation on domain-specific book inquiries?
- **Hypothesis ($H_4$):** Grounded RAG achieves a Factual Correctness score $\ge 90\%$ and an Unsupported Claim Rate $< 5\%$, whereas parametric zero-shot Qwen generation exhibits an Unsupported Claim Rate $> 40\%$ on long-tail book queries.
- **Independent Variable:** Generation Mode (Zero-Shot Parametric LLM vs. LuminaR Grounded RAG with top-$k$ retrieved chunks).
- **Dependent Variables:** Factual Correctness (1–5 scale), Groundedness Score (0–1), Unsupported Claim Rate (%), Generation Latency (s).
- **Baseline:** Unaugmented `Qwen/Qwen2.5-3B-Instruct` prompted without retrieved context.
- **Dataset:** 50 book domain questions (across technical, historical, and fiction texts in `rag/books`).
- **Metric:** Groundedness, Factual Accuracy, Unsupported Claim Rate.
- **Implementation Readiness:** **READY (Implemented)** in `rag/qa.py` and `rag/llm.py`.

---

### RQ5: Hallucination Mitigation & Negative Abstention Accuracy
- **Research Question:** How accurately does LuminaR's dual hallucination prevention mechanism (system prompt grounding constraints + `lm-format-enforcer` validator schema) detect and abstain from answering unanswerable, out-of-domain, or partially answerable questions?
- **Hypothesis ($H_5$):** LuminaR achieves an Abstention Accuracy $\ge 95\%$ on answer-absent questions with a Hallucination Rate $< 2\%$, reliably producing refusal verdicts (`NOT_SUPPORTED`) rather than fabricating evidence.
- **Independent Variable:** Question Answerability Class (Answer-Present, Partially-Answerable, Answer-Absent / Out-of-Domain).
- **Dependent Variables:** Abstention Accuracy (%), Hallucination Rate (%), Groundedness (%).
- **Baseline:** Standard unconstrained RAG without JSON schema validation or explicit refusal prompting.
- **Dataset:** Tripartite test suite: 40 Answer-Present, 30 Partially-Answerable, and 40 Answer-Absent questions.
- **Metric:** Abstention Accuracy, Hallucination Rate, Precision of Refusal.
- **Implementation Readiness:** **READY (Implemented)** in `rag/qa.py:258-265` and `rag/llm.py:36-39`.

---

### RQ6: Chunk Size & Boundary Semantics in Technical PDF Retrieval
- **Research Question:** How does text chunk granularity (sliding window characters vs. page-bounded tokens: 180, 220, 240 tokens vs. 3,000 characters) affect retrieval relevance and downstream RAG answer quality?
- **Hypothesis ($H_6$):** Page-bounded sliding chunks of 220–240 tokens provide optimal semantic coherence, maximizing retrieval Recall@5 without fragmenting sentences across page margins, compared to oversized 3,000-character windows.
- **Independent Variable:** Chunking Configuration (`tokens_180`, `tokens_220`, `tokens_240`, `char_3000_overlap_400`).
- **Dependent Variables:** Retrieval Recall@5, RAG Groundedness, Total Ingestion Time (s), Context Chunk Count.
- **Baseline:** Current production sliding window character chunker (`CHUNK_SIZE = 3000, CHUNK_OVERLAP = 400`).
- **Dataset:** Technical study guide corpus (`datasets/rag_experiments/chunking_v1`).
- **Metric:** Recall@5, Groundedness Score, Ingestion Throughput.
- **Implementation Readiness:** **READY (Implemented)** in `rag/services/document_service.py` and `datasets/rag_experiments/chunking_v1`.

---

### RQ7: Retrieval Depth ($k$) Sensitivity in Context Construction
- **Research Question:** What is the optimal number of retrieved context chunks ($k \in \{1, 3, 5, 10, 20\}$) that maximizes answer completeness while minimizing prompt processing latency and context noise?
- **Hypothesis ($H_7$):** Answer completeness plateaus at $k=5$, while $k > 5$ increases prompt prefill latency by $> 40\%$ and introduces irrelevant distractors that decrease groundedness precision.
- **Independent Variable:** Retrieved Context Chunks Count ($k \in \{1, 3, 5, 10, 20\}$).
- **Dependent Variables:** Answer Completeness (1–5), Groundedness Score (0–1), Prompt Token Count, Generation Latency (s).
- **Baseline:** Single-chunk retrieval ($k=1$).
- **Dataset:** 50 multi-faceted technical document questions.
- **Metric:** Completeness, Groundedness, Prefill Latency.
- **Implementation Readiness:** **READY (Implemented)** in `rag/qa.py:583-600` (`get_depth_config`).

---

### RQ8: Multi-Tenant Cryptographic & Logical Privacy Isolation
- **Research Question:** Does LuminaR's predicate-scoped repository model (`TenantInventory.scope`) and session-isolated SQLite document architecture guarantee a zero percent ($0.0\%$) Cross-Library Leakage Rate under concurrent adversarial query injection?
- **Hypothesis ($H_8$):** LuminaR achieves a Cross-Library Leakage Rate of exactly $0.0\%$, with 100% of foreign-tenant access attempts rejected via HTTP 404 concealment or parameter tampering aborts.
- **Independent Variable:** Client Access Vector (Direct URL enumeration, cross-library book borrow, forged query payload `library_id`, concurrent private document session querying).
- **Dependent Variables:** Cross-Library Leakage Rate (%), HTTP Status Code Distribution (404 vs 403 vs 200).
- **Baseline:** Unscoped global repository model without tenant predicates.
- **Dataset:** Dual synthetic institution sandbox (Library A and Library B with overlapping title catalogues).
- **Metric:** Cross-Library Leakage Rate (%).
- **Implementation Readiness:** **READY (Implemented)** in `backend/services/library_catalogue_repository.py` and `tests/test_book_access_control.py`.

---

### RQ9: Multi-Factor Hybrid Recommendation vs. Unranked Popularity
- **Research Question:** Does an 8-factor behavioral recommendation engine incorporating exponential temporal decay ($e^{-\lambda \Delta t}$) and physical holding availability produce higher novelty and subject affinity than static popularity baselines?
- **Hypothesis ($H_9$):** LuminaR's multi-factor recommendation engine improves Subject Alignment and Novelty by $> 30\%$ over global top-borrowed books, while maintaining 100% physically requestable recommendations for the active tenant.
- **Independent Variable:** Recommendation Algorithm (Random, Global Popularity, Content/Subject-Only, LuminaR 8-Factor Hybrid Engine).
- **Dependent Variables:** Subject Affinity Score, Catalog Coverage (%), Availability Validity Rate (%), Recommendation Latency (ms).
- **Baseline:** Global Top-Popularity (borrow count ranking).
- **Dataset:** Synthetic patron borrowing history and ratings across 1,000 tenant catalogue items.
- **Metric:** Subject Alignment, Novelty, Availability Guarantee.
- **Implementation Readiness:** **READY (Implemented)** in `recommendation/recommendation_service.py`.

---

### RQ10: Deterministic Knowledge Synthesis vs. Generative LLM Artifacts
- **Research Question:** Can deterministic algorithmic synthesis (sentence-boundary extraction, bipartite concept graphs, MiniLM semantic Cloze grading) generate study artifacts (mind maps, flashcards, quizzes) with higher structural validity and lower latency than unconstrained generative LLM prompting?
- **Hypothesis ($H_{10}$):** Deterministic synthesis achieves $100\%$ schema validity and zero hallucinations at $< 100\text{ ms}$ latency, eliminating LLM JSON decoding errors and reducing compute cost by $100\times$.
- **Independent Variable:** Artifact Generation Engine (Deterministic Algorithm in `document_knowledge.py` vs. Generative LLM Prompting with Qwen).
- **Dependent Variables:** Schema Validity Rate (%), Hallucinated Distractor Rate (%), Generation Latency (ms), Execution Failure Rate (%).
- **Baseline:** Zero-shot Qwen2.5-3B-Instruct prompted to output JSON flashcards and mind maps.
- **Dataset:** 20 academic PDF chapters.
- **Metric:** Structural Validity (%), Generation Latency, Hallucinated Edge/Term Rate (%).
- **Implementation Readiness:** **READY (Implemented)** in `rag/services/document_knowledge.py` and `rag/services/cloze_grading.py`.

---

## 3. Summary of Research Questions & Implementation Readiness

| RQ | Core Focus Area | Baseline System | Dataset | Metric | Code Readiness |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **RQ1** | Hybrid Retrieval vs Lexical | Mongo Regex / Pure Dense | 30 Teacher Graded Queries | nDCG@5, MRR | **READY** |
| **RQ2** | HNSW Efficiency & Scaling | Brute-force `IndexFlatIP` | Stratified 1K–100K Index | Recall@10, Latency | **READY** |
| **RQ3** | Query Degradation Robustness | Pristine / Pure Lexical | Perturbation Benchmark | MRR, HitRate@5 | **READY** |
| **RQ4** | RAG vs Zero-Shot LLM | Zero-Shot Qwen Parametric | 50 Book QA Questions | Groundedness, Correctness | **READY** |
| **RQ5** | Hallucinations & Abstention | Unconstrained RAG Prompt | 110 Present/Absent Questions | Abstention Accuracy | **READY** |
| **RQ6** | Document Chunk Granularity | 3000-char sliding window | Technical Study Guides | Recall@5, Groundedness | **READY** |
| **RQ7** | Top-$k$ Context Sensitivity | Single chunk ($k=1$) | Multi-faceted Technical QA | Completeness, Latency | **READY** |
| **RQ8** | Multi-Library Isolation | Unscoped Global Model | Overlapping Dual Tenancy | Leakage Rate ($0.0\%$) | **READY** |
| **RQ9** | Multi-Factor Recommendation | Global Borrow Popularity | Patron Borrow History | Subject Affinity, Novelty | **READY** |
| **RQ10**| Deterministic Study Tools | Generative LLM Prompting | 20 Academic PDF Chapters | Structural Validity, Latency | **READY** |
