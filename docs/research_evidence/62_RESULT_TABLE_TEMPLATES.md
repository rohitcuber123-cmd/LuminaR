# 62. Empirical Result Table Templates and Benchmark Log

## 1. Protocol Notice and Data Integrity Mandate

> [!IMPORTANT]
> **Strict Empirical Rule**: In strict compliance with academic integrity guidelines, **ALL empirical cells in this document are initialized as `NOT MEASURED` or left blank**. 
> No fabricated, synthetic, estimated, or speculative numbers are included. 
> These templates serve as the pre-registered reporting schemas to be populated directly from empirical benchmark execution runs.

---

## 2. Table 1: Search Architecture Benchmarks (Experiment A)

Evaluates the retrieval effectiveness and latency of baseline and hybrid retrieval configurations across the 10 stratified query categories on the LuminaR catalog collection ($N = 100$ queries).

### 2.1 Overall System Comparison (All Query Categories Aggregated)

| System ID | Retrieval Configuration | Precision@5 | Recall@5 | MRR | nDCG@5 | HitRate@5 | Mean Latency (ms) | Median Latency (ms) | p95 Latency (ms) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **B1** | BM25 Lexical Baseline | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **B3** | Dense Brute-Force (`IndexFlatIP`) | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **B4** | Dense HNSW (`IndexHNSWFlat`) | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **B5** | SQLite Lexical Store (Exact/Fuzzy) | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **B6** | **Full LuminaR Hybrid + Reranker** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |

### 2.2 nDCG@5 Performance Broken Down by Query Category

| System ID | Exact Title | Author | Subject | Synonym | Beginner | Conceptual | Descriptive | Typo | Ambiguous | Scoped | Macro Mean |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **B1: BM25** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **B3: Dense Flat** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **B4: Dense HNSW** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **B5: SQLite Lexical** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **B6: Hybrid + Rerank** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |

---

## 3. Table 2: Vector Index Scaling & Efficiency (Experiment B)

Quantifies the trade-off between exact dense search (`IndexFlatIP`) and approximate nearest neighbor search (`IndexHNSWFlat`, $M=32, efConstruction=200, efSearch=128$) across 6 scaling tiers.

| Corpus Scale ($N$) | Metric | Exact FlatIP (B3) | HNSW Graph (B4) | Relative Speedup ($\times$) | Recall Retention ($\%$) |
| :---: | :--- | :---: | :---: | :---: | :---: |
| **1,000** | ANN Recall@10 | 1.000 (Definitional) | NOT MEASURED | — | NOT MEASURED |
| | Mean Latency (ms) | NOT MEASURED | NOT MEASURED | NOT MEASURED | — |
| | p95 Latency (ms) | NOT MEASURED | NOT MEASURED | — | — |
| | Build Time (s) | NOT MEASURED | NOT MEASURED | — | — |
| | Resident Memory (MB)| NOT MEASURED | NOT MEASURED | — | — |
| | Serialized Size (MB)| NOT MEASURED | NOT MEASURED | — | — |
| **5,000** | ANN Recall@10 | 1.000 | NOT MEASURED | — | NOT MEASURED |
| | Mean Latency (ms) | NOT MEASURED | NOT MEASURED | NOT MEASURED | — |
| | p95 Latency (ms) | NOT MEASURED | NOT MEASURED | — | — |
| | Build Time (s) | NOT MEASURED | NOT MEASURED | — | — |
| | Resident Memory (MB)| NOT MEASURED | NOT MEASURED | — | — |
| | Serialized Size (MB)| NOT MEASURED | NOT MEASURED | — | — |
| **10,000** | ANN Recall@10 | 1.000 | NOT MEASURED | — | NOT MEASURED |
| | Mean Latency (ms) | NOT MEASURED | NOT MEASURED | NOT MEASURED | — |
| | p95 Latency (ms) | NOT MEASURED | NOT MEASURED | — | — |
| | Build Time (s) | NOT MEASURED | NOT MEASURED | — | — |
| | Resident Memory (MB)| NOT MEASURED | NOT MEASURED | — | — |
| | Serialized Size (MB)| NOT MEASURED | NOT MEASURED | — | — |
| **25,000** | ANN Recall@10 | 1.000 | NOT MEASURED | — | NOT MEASURED |
| | Mean Latency (ms) | NOT MEASURED | NOT MEASURED | NOT MEASURED | — |
| | p95 Latency (ms) | NOT MEASURED | NOT MEASURED | — | — |
| | Build Time (s) | NOT MEASURED | NOT MEASURED | — | — |
| | Resident Memory (MB)| NOT MEASURED | NOT MEASURED | — | — |
| | Serialized Size (MB)| NOT MEASURED | NOT MEASURED | — | — |
| **50,000** | ANN Recall@10 | 1.000 | NOT MEASURED | — | NOT MEASURED |
| | Mean Latency (ms) | NOT MEASURED | NOT MEASURED | NOT MEASURED | — |
| | p95 Latency (ms) | NOT MEASURED | NOT MEASURED | — | — |
| | Build Time (s) | NOT MEASURED | NOT MEASURED | — | — |
| | Resident Memory (MB)| NOT MEASURED | NOT MEASURED | — | — |
| | Serialized Size (MB)| NOT MEASURED | NOT MEASURED | — | — |
| **100,000+** | ANN Recall@10 | 1.000 | NOT MEASURED | — | NOT MEASURED |
| | Mean Latency (ms) | NOT MEASURED | NOT MEASURED | NOT MEASURED | — |
| | p95 Latency (ms) | NOT MEASURED | NOT MEASURED | — | — |
| | Build Time (s) | NOT MEASURED | NOT MEASURED | — | — |
| | Resident Memory (MB)| NOT MEASURED | NOT MEASURED | — | — |
| | Serialized Size (MB)| NOT MEASURED | NOT MEASURED | — | — |

---

## 4. Table 3: Query Understanding & Degradation Robustness (Experiment C)

Measures retrieval robustness under linguistic distortions and challenging phrasing patterns.

| Test Perturbation Group | Number of Queries | Pure Lexical (B5) HitRate@5 | Pure Dense (B4) HitRate@5 | Hybrid Reranked (B6) HitRate@5 | Top Dominant Failure Category |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Exact Control Queries** | 20 | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Synonym Substitutions** | 20 | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Syntactic Paraphrasing** | 20 | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Typographical Errors (1-2 edits)** | 20 | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Severe Typos (3+ edits / phonetic)**| 20 | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Acronyms & Abbreviations** | 20 | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Ambiguous / Polysemous Phrasing**| 20 | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Verbose Problem Descriptions** | 20 | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |

---

## 5. Table 4: End-to-End RAG vs. Parametric LLM-Only (Experiment D)

Compares `Qwen2.5-3B-Instruct` operating purely on parametric weights against the full LuminaR RAG pipeline.

| Metric | LLM-Only Baseline (B7) | LuminaR RAG Pipeline (B8) | Relative Difference ($\Delta$) | Statistically Significant ($p < 0.05$)? |
| :--- | :---: | :---: | :---: | :---: |
| **Factual Correctness (1-5 Likert)** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Binary Correctness ($\ge 4$) Rate** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Contextual Groundedness Score** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Answer Relevance (0-3 scale)** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Completeness (Nugget Recall)** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Unsupported Claim Rate ($\%$)** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Citation Precision ($\%$)** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Mean End-to-End Latency (ms)** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Median End-to-End Latency (ms)** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **p95 Latency (ms)** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |

---

## 6. Table 5: Hallucination, Groundedness, and Abstention (Experiment E)

Evaluates defensive behavior across the Tri-Partite Question Suite ($N = 90$ questions).

| Question Partition | System Configuration | Hallucination Rate ($\%$) | Unsupported Claim Rate ($\%$) | Abstention Accuracy ($\%$) | Groundedness Score |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Partition A: Answer-Present** ($N=30$) | LLM-Only (B7) | NOT MEASURED | NOT MEASURED | N/A (Should Answer) | NOT MEASURED |
| | LuminaR RAG (B8) | NOT MEASURED | NOT MEASURED | N/A (Should Answer) | NOT MEASURED |
| **Partition B: Partially Answerable** ($N=30$) | LLM-Only (B7) | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| | LuminaR RAG (B8) | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Partition C: Answer-Absent** ($N=30$) | LLM-Only (B7) | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| | LuminaR RAG (B8) | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |

---

## 7. Table 6: RAG Error Breakdown Distribution (Experiment F)

Categorizes all observed failures into the 7-stage taxonomy.

| Pipeline Failure Stage | Error Code | Incident Count | Proportion of Failures ($\%$) | Primary Contributing Cause |
| :--- | :---: | :---: | :---: | :--- |
| **Stage 1: Query Interpretation** | E1 | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Stage 2: Retrieval Recall** | E2 | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Stage 3: Chunking Boundary** | E3 | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Stage 4: Re-ranking Demotion** | E4 | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Stage 5: Context Noise & Distraction** | E5 | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Stage 6: Generative Hallucination** | E6 | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Stage 7: Tenant Scope Leakage** | E7 | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Total Analyzed Incidents** | — | NOT MEASURED | 100.0% | — |

---

## 8. Table 7: Chunk Size & Segmentation Sensitivity (Experiment G)

Benchmarks retrieval and generation effectiveness across 5 chunking configurations.

| Chunking Configuration | Character Size / Overlap | Token Estimate | Retrieval nDCG@5 | RAG Correctness (1-5) | Groundedness Score | Avg Context Tokens | Total End-to-End Latency (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Config 1: Micro Chunks** | $500\text{ chars} / 100$ | $\approx 100\text{ tok}$ | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Config 2: Short Chunks** | $1000\text{ chars} / 200$ | $\approx 220\text{ tok}$ | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Config 3: Medium Chunks** | $1500\text{ chars} / 300$ | $\approx 330\text{ tok}$ | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Config 4: Long Chunks** | $2000\text{ chars} / 400$ | $\approx 450\text{ tok}$ | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Config 5: Production Window** | $3000\text{ chars} / 400$ | $\approx 680\text{ tok}$ | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |

---

## 9. Table 8: Top-$k$ Context Window Budget Sensitivity (Experiment H)

Analyzes the impact of the retrieved context budget $k \in \{1, 3, 5, 10, 20\}$ on accuracy, distraction, and prompt size.

| Top-$k$ Budget | Retrieval Recall@$k$ | Context Size (Tokens) | RAG Correctness (1-5) | Groundedness Score | Hallucination Rate ($\%$) | LLM Prompt Eval Latency (ms) | Total Response Latency (ms) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$k = 1$** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **$k = 3$** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **$k = 5$ (Default)**| NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **$k = 10$** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **$k = 20$** | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |

---

## 10. Table 9: Multi-Library Isolation and Security Audit (Experiment I)

Audits Cross-Library Leakage Rates ($\text{CLLR}$) across 6 operational interfaces in overlapping catalog configurations.

| Operational Interface | Total Invocations ($N$) | Foreign Candidates Surfaced | Cross-Library Leakage Rate ($\%$) | Security Pass / Fail |
| :--- | :---: | :---: | :---: | :---: |
| **Catalog Browse & Filter** | 500 | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **HNSW Semantic Search** | 500 | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **RAG Generative Answers** | 500 | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Recommendation Engine** | 500 | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Knowledge Graph Nodes** | 500 | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Direct Document Fetch API** | 500 | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Aggregate Security Audit** | **3,000** | NOT MEASURED | NOT MEASURED | NOT MEASURED |

---

## 11. Table 10: Recommendation Algorithm Benchmarks (Experiment J)

Evaluates recommendation algorithms on catalog utility, ranking accuracy, inventory health, and diversity.

| Recommendation Algorithm | System ID | nDCG@10 | HitRate@10 | Catalog Coverage ($\%$) | Gini Diversity Index | Unfulfilled Hold Rate ($\%$) | Mean Latency (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Random Baseline** | B11 | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Global Popularity Baseline** | B12 | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Single-Factor Category Match** | B13 | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Pure Collaborative Filter** | B14 | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Full 8-Factor LuminaR Engine**| B15 | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |

---

## 12. Table 11: Educational Knowledge Artifact Quality (Experiment K)

Compares deterministic extraction against generative LLM prompting for study tool generation.

| Generated Artifact Type | Generator Architecture | Factual Correctness ($\%$) | Source Faithfulness ($\%$) | Distractor / Edge Quality | Parsing / Render Failures ($\%$) | Generation Latency (ms) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Concept Flashcards** | Deterministic CPU (B16) | NOT MEASURED | NOT MEASURED | N/A | NOT MEASURED | NOT MEASURED |
| | Generative Qwen (B17) | NOT MEASURED | NOT MEASURED | N/A | NOT MEASURED | NOT MEASURED |
| **Multiple-Choice Quizzes** | Deterministic CPU (B16) | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| | Generative Qwen (B17) | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Cloze Deletion Tests** | Deterministic CPU (B16) | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| | Generative Qwen (B17) | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **Concept Mind Maps** | Deterministic Graph (B16)| NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| | Generative Qwen (B17) | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |

---

## 13. Table 12: Search Ablation Study Results

Populates empirical values for the ablation variants defined in [58_ABLATION_PLAN.md](file:///d:/SDC/docs/research_evidence/58_ABLATION_PLAN.md).

| Ablation ID | Description | nDCG@5 | MRR | Precision@5 | Recall@5 | Mean Latency (ms) | p95 Latency (ms) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **ABL-SRCH-00** | Full LuminaR Pipeline | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **ABL-SRCH-01** | w/o Cross-Encoder Reranker | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **ABL-SRCH-02** | w/o Lexical-Fuzzy Store | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **ABL-SRCH-03** | w/o Dense Semantic Search | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **ABL-SRCH-04** | w/o HNSW (Exact FlatIP) | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **ABL-SRCH-05** | w/o Dynamic Pool ($k_1=10$) | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **ABL-SRCH-06** | w/o Levenshtein Matching | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |

---

## 14. Table 13: RAG Ablation Study Results

Populates empirical values for the generative RAG defense ablations.

| Ablation ID | Description | Groundedness Score | Hallucination Rate ($\%$) | Abstention Accuracy ($\%$) | JSON Format Failures ($\%$) | Generation Latency (ms) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **ABL-RAG-00** | Full LuminaR RAG | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **ABL-RAG-01** | w/o Schema Enforcer | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **ABL-RAG-02** | w/o Refusal Prompting | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **ABL-RAG-03** | w/o Context (LLM-Only) | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **ABL-RAG-04** | w/o Intent Classification | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
| **ABL-RAG-05** | w/o NF4 Quant (FP16 Base)| NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED | NOT MEASURED |
