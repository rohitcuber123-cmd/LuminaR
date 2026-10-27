# 56_METRICS_AND_FORMULAS.md: Exact Mathematical Metrics & Evaluation Formulations

> **Audit Report:** Part 9 Research Experiment Design  
> **Repository:** LuminaR (`d:\SDC\LibraryLLM`)  
> **Scope:** Formal Mathematical Definitions, Bounds, and Algorithms for All Information Retrieval, Vector Indexing, RAG, Privacy, and System Metrics  
> **Status:** Ground-Truth Specification  

---

## 1. Information Retrieval & Ranking Metrics

### 1.1 Precision@k
Precision at rank $k$ measures the proportion of retrieved documents in the top-$k$ positions that are relevant to the query:

$$\text{Precision@}k(q) = \frac{1}{k} \sum_{i=1}^k \mathbb{I}\left(\text{rel}(q, d_i) > 0\right)$$

$$\text{Precision@}k = \frac{1}{|Q|} \sum_{q \in Q} \text{Precision@}k(q)$$

- **Bounds:** $[0.0, 1.0]$.
- **Variables:** $d_i$ is the document ranked at position $i$; $\text{rel}(q, d_i) \in \{0, 1\}$ is binary relevance (or binarized from graded relevance: $\text{rel} \ge 1$); $|Q|$ is the total number of evaluation queries.

---

### 1.2 Recall@k
Recall at rank $k$ measures the fraction of all relevant documents in the corpus that appear within the top-$k$ retrieved positions:

$$\text{Recall@}k(q) = \frac{\sum_{i=1}^k \mathbb{I}\left(\text{rel}(q, d_i) > 0\right)}{R_q}$$

$$\text{Recall@}k = \frac{1}{|Q|} \sum_{q \in Q} \text{Recall@}k(q)$$

- **Bounds:** $[0.0, 1.0]$.
- **Variables:** $R_q$ is the total number of relevant documents known to exist in the corpus for query $q$. If $R_q = 0$, the query is omitted from the macro-average.

---

### 1.3 Mean Reciprocal Rank (MRR)
MRR evaluates how early the first relevant item appears in the ranked candidate list:

$$\text{RR}(q) = \begin{cases} \frac{1}{\text{rank}_q^*} & \text{if a relevant document is found in top-}k \\ 0 & \text{otherwise} \end{cases}$$

$$\text{MRR} = \frac{1}{|Q|} \sum_{q \in Q} \text{RR}(q)$$

- **Bounds:** $[0.0, 1.0]$.
- **Variables:** $\text{rank}_q^*$ is the 1-indexed position of the highest-ranked relevant document for query $q$.

---

### 1.4 Normalized Discounted Cumulative Gain (nDCG@k)
nDCG evaluates the quality of ranking using graded relevance labels ($\text{rel}_i \in \{0, 1, 2\}$ where $0 = \text{irrelevant}$, $1 = \text{somewhat relevant}$, $2 = \text{highly relevant}$), penalizing relevant documents appearing lower in the list via a logarithmic discount:

$$\text{DCG@}k(q) = \sum_{i=1}^k \frac{2^{\text{rel}(q, d_i)} - 1}{\log_2(i + 1)}$$

$$\text{IDCG@}k(q) = \sum_{i=1}^{\min(k, |R_q|)} \frac{2^{\text{rel}^*(q, i)} - 1}{\log_2(i + 1)}$$

$$\text{nDCG@}k(q) = \begin{cases} \frac{\text{DCG@}k(q)}{\text{IDCG@}k(q)} & \text{if } \text{IDCG@}k(q) > 0 \\ 0 & \text{if } \text{IDCG@}k(q) = 0 \end{cases}$$

$$\text{nDCG@}k = \frac{1}{|Q|} \sum_{q \in Q} \text{nDCG@}k(q)$$

- **Bounds:** $[0.0, 1.0]$.
- **Variables:** $\text{rel}^*(q, i)$ is the relevance grade of the $i$-th item in the ideally sorted candidate list for query $q$.

---

### 1.5 Hit Rate@k (Success@k)
Hit Rate measures the percentage of evaluation queries for which at least one relevant document is successfully retrieved within the top-$k$ positions:

$$\text{Hit@}k(q) = \begin{cases} 1 & \text{if } \sum_{i=1}^k \mathbb{I}\left(\text{rel}(q, d_i) > 0\right) \ge 1 \\ 0 & \text{otherwise} \end{cases}$$

$$\text{HitRate@}k = \frac{1}{|Q|} \sum_{q \in Q} \text{Hit@}k(q)$$

- **Bounds:** $[0.0, 1.0]$ or $[0\%, 100\%]$.

---

## 2. Approximate Vector Search Metrics

### 2.1 Approximate Nearest Neighbor Recall (ANN 1-Recall@k)
Measures the fidelity of approximate graph search (`IndexHNSWFlat`) relative to exact exhaustive inner-product search (`IndexFlatIP`):

$$\text{ANN Recall@}k(q) = \frac{\left| \mathcal{R}_{\text{HNSW}}(q, k) \cap \mathcal{R}_{\text{Exact}}(q, k) \right|}{k}$$

$$\text{ANN Recall@}k = \frac{1}{|Q|} \sum_{q \in Q} \text{ANN Recall@}k(q)$$

- **Bounds:** $[0.0, 1.0]$.
- **Variables:** $\mathcal{R}_{\text{HNSW}}(q, k)$ is the set of $k$ nearest vector IDs returned by FAISS HNSW; $\mathcal{R}_{\text{Exact}}(q, k)$ is the true set of $k$ nearest vector IDs returned by exhaustive scan.

---

## 3. System Latency & Throughput Formulations

Given an ordered collection of measured execution latencies $\mathcal{L} = \{L_1, L_2, \dots, L_N\}$ sorted such that $L_{(1)} \le L_{(2)} \le \dots \le L_{(N)}$:

### 3.1 Mean Latency ($\bar{L}$)
$$\bar{L} = \frac{1}{N} \sum_{i=1}^N L_i$$

### 3.2 Median Latency (p50)
$$L_{\text{p50}} = \begin{cases} L_{\left(\frac{N+1}{2}\right)} & \text{if } N \text{ is odd} \\ \frac{1}{2} \left( L_{\left(\frac{N}{2}\right)} + L_{\left(\frac{N}{2} + 1\right)} \right) & \text{if } N \text{ is even} \end{cases}$$

### 3.3 95th Percentile Latency (p95)
Using nearest-rank or linear interpolation:
$$L_{\text{p95}} = L_{(\lceil 0.95 \cdot N \rceil)}$$

- **Unit:** Milliseconds (ms) or Seconds (s).

---

## 4. RAG Quality, Groundedness & Hallucination Metrics

Let an answer $A$ generated for query $q$ be segmented into $S(A) = \{s_1, s_2, \dots, s_{|S|}\}$ distinct factual atomic propositions (sentences).

### 4.1 Groundedness Score
The proportion of generated sentences whose factual claims are strictly entailed by the retrieved context chunks $\mathcal{C}$:

$$\text{Groundedness}(A, \mathcal{C}) = \frac{1}{|S(A)|} \sum_{s \in S(A)} \mathbb{I}\left(s \text{ is entailed by } \mathcal{C}\right)$$

- **Bounds:** $[0.0, 1.0]$. A score of $1.0$ indicates zero ungrounded claims.

---

### 4.2 Unsupported Claim Rate (UCR)
The complement of Groundedness, measuring the density of ungrounded or extracontextual assertions:

$$\text{UCR}(A, \mathcal{C}) = 1.0 - \text{Groundedness}(A, \mathcal{C}) = \frac{1}{|S(A)|} \sum_{s \in S(A)} \mathbb{I}\left(s \text{ is NOT entailed by } \mathcal{C}\right)$$

- **Bounds:** $[0.0, 1.0]$ or $[0\%, 100\%]$.

---

### 4.3 Hallucination Rate
The proportion of evaluation responses that contain at least one verifiable factual contradiction or completely fabricated assertion:

$$\text{Hallucination}(A, \mathcal{C}) = \begin{cases} 1 & \text{if } \exists s \in S(A) \text{ such that } s \text{ contradicts } \mathcal{C} \text{ or invents facts} \\ 0 & \text{otherwise} \end{cases}$$

$$\text{Hallucination Rate} = \frac{1}{|Q|} \sum_{q \in Q} \text{Hallucination}(A_q, \mathcal{C}_q)$$

- **Bounds:** $[0.0, 1.0]$ or $[0\%, 100\%]$.

---

### 4.4 Abstention Accuracy (Negative Constraint Precision)
Evaluated over the subset of **Answer-Absent** questions $Q_{\text{absent}}$ where the correct response is an explicit refusal to answer due to missing evidence:

$$\text{Correct Abstention}(A, q) = \begin{cases} 1 & \text{if } A \text{ outputs explicit refusal verdict (e.g. NOT\_SUPPORTED)} \\ 0 & \text{if } A \text{ attempts to answer or fabricates information} \end{cases}$$

$$\text{Abstention Accuracy} = \frac{1}{|Q_{\text{absent}}|} \sum_{q \in Q_{\text{absent}}} \text{Correct Abstention}(A_q, q)$$

- **Bounds:** $[0.0, 1.0]$ or $[0\%, 100\%]$.

---

## 5. Security & Privacy Isolation Metrics

### 5.1 Cross-Library Leakage Rate (CLLR)
Given a set of $M$ adversarial cross-tenant probes $\mathcal{P} = \{p_1, \dots, p_M\}$ where client actor $u \in \text{Library}_A$ attempts to access, query, borrow, or inspect records belonging exclusively to $\text{Library}_B$ ($A \ne B$):

$$\text{Leakage}(p) = \begin{cases} 1 & \text{if probe receives HTTP 200/201 with foreign tenant data} \\ 0 & \text{if probe receives HTTP 404/403 or is rejected} \end{cases}$$

$$\text{CLLR} = \left( \frac{1}{M} \sum_{p \in \mathcal{P}} \text{Leakage}(p) \right) \times 100\%$$

- **Target Invariant:** Exactly **$0.0\%$**. Any value $> 0.0\%$ constitutes a critical security vulnerability.

---

## 6. Recommendation Engine Metrics

Let $U$ be the set of active users, $\text{Rec}(u, K)$ be the set of $K$ recommended books for user $u$, and $\mathcal{B}_{\text{catalog}}$ be the complete tenant library book inventory.

### 6.1 Catalog Coverage
The percentage of unique inventory books recommended to at least one user across all recommendation lists:

$$\text{Catalog Coverage}(K) = \frac{\left| \bigcup_{u \in U} \text{Rec}(u, K) \right|}{|\mathcal{B}_{\text{catalog}}|} \times 100\%$$

- **Bounds:** $[0\%, 100\%]$. Higher coverage indicates reduced popularity bias and superior exploration.

---

### 6.2 Physical Availability Guarantee Rate
The proportion of recommended items that can actually be checked out immediately by the patron:

$$\text{Availability}(u, K) = \frac{1}{K} \sum_{b \in \text{Rec}(u, K)} \mathbb{I}\left(\text{requestable}(b, \text{library}_u) \ge 1\right)$$

$$\text{Physical Availability Rate} = \frac{1}{|U|} \sum_{u \in U} \text{Availability}(u, K) \times 100\%$$

- **Target Invariant:** **$100.0\%$** for tenant catalogue recommendations.
