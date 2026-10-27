# RAG Context Construction & Diversity Selection Evidence

> **Audit Context**: LuminaR Research Evidence Audit — Part 5  
> **Source Files Verified**:
> - `rag/qa.py` (Lines 36–72, 141–261, 693–710)
> - `rag/reranker.py` (Lines 33–38, 209–250, 424–460)
> - `rag/retriever.py` (Lines 140–280)
> - `rag/evidence.py` (Lines 8–16, 1500–1570)

---

## 1. Retrieval Parameters & Settings Matrix

| Parameter | Exact Value | Active Source Location | Operational Description |
| :--- | :--- | :--- | :--- |
| **`CANDIDATE_K`** | 10 to 20 (dynamic by depth) | `rag/qa.py:36-62` (`DEPTH_CONFIG`) | Number of raw nearest-neighbor vectors pulled from FAISS index per query. |
| **`MAX_MULTIQ_CANDIDATES`**| 40 | `rag/reranker.py:213` | Ceiling on total merged candidates when multi-query expansion runs. |
| **`FINAL_K` / `context_chunks`**| 4 to 15 (dynamic by depth) | `rag/qa.py:36-62` | Final count of passages selected for inclusion into the LLM context. |
| **`MAX_CONTEXT_CHARS`** | **24,000 characters** | `rag/qa.py:70` | Hard character ceiling; prevents prompt overflow into Qwen's 32k context window. |
| **Similarity Threshold** | **None (Rank-based)** | `rag/retriever.py` | FAISS returns top-k nearest neighbors unconditionally; no absolute cosine cut-off. |
| **Duplicate Removal** | Primary Key: `chunk_id` | `rag/reranker.py:237`, `rag/qa.py:858` | Suppresses duplicate occurrences of the same chunk across query expansions. |
| **Neighboring Chunks** | **NOT IMPLEMENTED** | `rag/qa.py`, `rag/retriever.py` | Does not fetch preceding or succeeding chunks ($c-1, c+1$) around retrieved matches. |
| **Cross-Encoder Reranking** | `ms-marco-MiniLM-L-6-v2` | `rag/reranker.py:25` | Reranks candidates using deep query-passage cross-attention logits. |
| **Hybrid Weighting** | 0.30 CE + 0.55 EV + 0.15 FAISS | `rag/evidence.py:8-10` | Fuses CrossEncoder, structural evidence signals, and FAISS vector similarity. |

---

## 2. Multi-Tier Scope Filtering

LuminaR isolates retrieval across tenants, documents, and books using strict metadata boundaries:

```
+-------------------------------------------------------------------------+
|                              RETRIEVAL SCOPE                            |
+-------------------------------------------------------------------------+
       |
       +---> Document Filter: `retriever.doc_index` & `doc_ids = {document_id}`
       |     Restricts search exclusively to the isolated session FAISS index.
       |
       +---> Book Filter: `work_id` index partition
       |     Restricts search to chunks belonging to the selected catalog work.
       |
       +---> Library Filter: Tenant isolation boundary
       |     Inherited from library asset authorization; cross-library reads blocked.
       |
       +---> User Filter: Session ownership in SQLite registry
             Enforces that users can only mount and query their own active uploads.
```

- **Document Isolation**: In `rag/services/private_documents.py:221-234` (`selected()`), when a private document is queried, the retriever's runtime state is dynamically scoped to that document's private FAISS index (`runtime.faiss`) and chunk dictionary (`doc_chunk_texts`). Global catalogue chunks are completely unsearchable during that call.
- **Book Isolation**: In `rag/retriever.py:175-210`, if `work_id` is specified, search candidates from other catalog books are rejected.

---

## 3. Diversity-Aware Passage Selection (`select_diverse_context`)

Rather than naively packing the top reranked chunks into the prompt (which frequently causes near-duplicate passages from the same page to crowd out complementary evidence), LuminaR implements a **lexical Maximal Marginal Relevance (MMR) algorithm** in `rag/qa.py:141-195`:

```python
def select_diverse_context(self, results, max_chunks):
    if not results:
        return []

    def get_terms(text):
        return set(re.findall(r"\b[a-zA-Z]{3,}\b", text.lower()))

    unselected = list(results)
    for item in unselected:
        item["terms"] = get_terms(item.get("text", ""))

    selected = []
    while len(selected) < max_chunks and unselected:
        best_idx = -1
        best_score = -float('inf')
        best_redundancy = 0.0

        for i, item in enumerate(unselected):
            redundancy = 0.0
            if selected:
                max_sim = 0.0
                for s in selected:
                    intersection = len(item["terms"] & s["terms"])
                    union = len(item["terms"] | s["terms"])
                    sim = intersection / union if union > 0 else 0
                    if sim > max_sim:
                        max_sim = sim
                redundancy = max_sim

            penalty = 0.3 * redundancy
            context_score = item.get("final_score", 0.0) - penalty

            if context_score > best_score:
                best_score = context_score
                best_idx = i
                best_redundancy = redundancy

        chosen = unselected.pop(best_idx)
        chosen["redundancy_penalty"] = 0.3 * best_redundancy
        chosen["final_context_score"] = chosen.get("final_score", 0.0) - chosen["redundancy_penalty"]
        selected.append(chosen)

    return selected
```

### Mathematical Formulation:
For each unselected candidate passage $c$, its marginal context score is evaluated iteratively against the set of already selected passages $S$:
$$\text{Redundancy}(c, S) = \max_{s \in S} \text{JaccardTerms}(c, s)$$
$$\text{Score}_{\text{context}}(c) = \text{Score}_{\text{final}}(c) - 0.30 \times \text{Redundancy}(c, S)$$

- **Impact**: If a candidate passage shares high lexical overlap ($\text{Jaccard} > 0.70$) with a previously accepted passage, it suffers a substantial penalty ($\sim 0.21$), allowing lower-ranked passages covering different aspects or chapters to be included in the context window.

---

## 4. Context Assembly & Formatting (`build_context`)

In `rag/qa.py:197-261`, selected passages are formatted with structured provenance headers:

```text
[Source 1]
Book: Computer Networks
Author: Andrew S. Tanenbaum
Chapter: The Data Link Layer
Page: 214
File: computer_networks.pdf

Sliding window protocols provide flow control by allowing the sender
to transmit multiple frames before receiving an acknowledgment...

[Source 2]
Book: Computer Networks
Author: Andrew S. Tanenbaum
Chapter: The Data Link Layer
Page: 218
File: computer_networks.pdf

In Go-Back-N ARQ, if a frame is damaged or lost, the receiver discards
all subsequent frames without acknowledging them...
```

### Guardrails:
1. **Empty Text Filter**: Chunks with whitespace-only text are omitted (`if not text: continue`).
2. **Book / Document Fields**: Formats `Book`, `Author`, `Chapter`, and `Page` when available; defaults to `File: {filename}` when book metadata is absent.
3. **Context Length Ceiling**:
   ```python
   if total_chars + len(source_text) > MAX_CONTEXT_CHARS:
       break
   ```
   Accumulates passages until reaching 24,000 characters (~5,000 to 6,000 tokens), reserving the remaining token budget for prompt instructions and generated output.
