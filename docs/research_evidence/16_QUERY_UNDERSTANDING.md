# 16_QUERY_UNDERSTANDING.md: Query Processing & Understanding Audit

## Executive Summary

This document audits the exact query processing, normalization, and intent analysis pipeline active within LuminaR. Every documented mechanism is verified against concrete source code lines in `LibraryLLM/search/luminar_search.py`, `LibraryLLM/search/typo_assistance.py`, `LibraryLLM/search/lexical_store.py`, and `LibraryLLM/assistant/orchestrator.py`.

LuminaR does **not** employ a heavy conversational query rewriter or generative query expansion model in its core search path. The search engine relies on lightweight deterministic normalization, optional bounded typo/fuzzy matching, and dense bi-encoder sentence embedding.

---

## 1. Concrete Pipeline Audit: What LuminaR Actually Implements

| Mechanism | Implemented in Core Search? | Exact Code Reference | Implementation Details & Behavioral Characteristics |
| :--- | :---: | :--- | :--- |
| **Lowercasing** | **YES** | `search/luminar_search.py:83` | `.lower()` applied during lexical normalization. |
| **Punctuation Stripping** | **YES** | `search/luminar_search.py:83` | `re.sub(r"[^a-z0-9 ]+", " ", text)` removes all non-alphanumeric symbols. |
| **Unicode NFKC Normalization** | **YES** | `search/typo_assistance.py:12` | `unicodedata.normalize("NFKC", str(value)).casefold().strip()` |
| **Stopword Removal** | **NO** | N/A | Stopwords (e.g. *the, in, for, of, by*) are **retained** in search queries to allow the SentenceTransformer attention heads to preserve syntactic context. |
| **Stemming / Lemmatization** | **NO** | N/A | Neither Porter/Snowball stemmers nor WordNet lemmatizers are active in the core search path. |
| **Spell Correction / Typo Probing**| **YES** (Optional Flag) | `search/typo_assistance.py:17-34`, `search/lexical_store.py:71-92` | Single-edit whole-query candidate generator (`edit_prefixes`) + `SequenceMatcher` fuzzy similarity ratio ($\ge 0.86$) against indexed titles/authors. |
| **Fuzzy Matching** | **YES** (Optional Flag) | `search/lexical_store.py:21-22` | Bounded fuzzy match over SQLite lexical store (`FUZZY_THRESHOLD = 0.86`, `FUZZY_MARGIN = 0.05`). |
| **Synonym Expansion** | **NO** | N/A | No WordNet, thesaurus, or generative synonym expansion model is active. |
| **Acronym Expansion** | **NO** | N/A | Acronyms (e.g., *"AI"*, *"ML"*, *"NLP"*) are not rewritten or expanded. |
| **Generative Query Rewriting** | **NO** | N/A | User queries are passed directly to `all-MiniLM-L6-v2.encode()` without LLM rewrites. |
| **Author Name Detection** | **YES** (Strict) | `search/luminar_search.py:85-101` | Conservative author detection: `_author_match_ids` flags candidate books only if the query matches an entire author field exactly (length $\ge 2$ words). |
| **Title Detection** | **YES** (Optional Flag) | `search/lexical_integration.py:41` | Checks if query matches normalized title in SQLite lexical index. |
| **Category / Subject Detection** | **NO** | N/A | Categories are not automatically extracted from query strings in `search/luminar_search.py`; they must be passed explicitly via `category` parameter. |
| **Availability Intent Detection** | **NO** (In Search Engine)<br>**YES** (In Assistant) | `assistant/orchestrator.py:112` | Search engine does not parse natural language phrases like *"available here"*; availability filtering requires the explicit API flag `available_at_library=True`. |
| **Multi-Turn Context Tracking** | **NO** (In Search Engine)<br>**YES** (In Assistant) | `search/luminar_search.py:415` | Core search is strictly stateless. Contextual conversation history is managed exclusively in `assistant/orchestrator.py`. |

---

## 2. Walkthrough: Conceptual Evaluation Against Query Examples

To evaluate the operational behavior of LuminaR's query pipeline, we trace six canonical user queries through the active codebase:

### Example 1: `"books for beginners in AI"`
* **Normalization:** Converted to `"books for beginners in ai"`.
* **Stopwords:** `"for"` and `"in"` are **not removed**.
* **Processing:** The full 5-word sentence is forwarded to `all-MiniLM-L6-v2.encode(["books for beginners in ai"])`.
* **Retrieval Behavior:** MiniLM's self-attention captures the semantic relationship between *"beginners"* (introductory) and *"AI"* (artificial intelligence). The 384-D vector retrieves candidate books via FAISS HNSW.
* **Reranking:** Cross-encoder scores candidate titles and subjects against the full phrase.
* **Failure Risk:** Books titled *"Artificial Intelligence: A Modern Approach"* may rank highly even though they are comprehensive graduate-level textbooks rather than beginner primers.

---

### Example 2: `"something easy to start machine learning"`
* **Normalization:** Stripped to `"something easy to start machine learning"`.
* **Processing:** Treated as conversational natural language; forwarded directly to dense embedding.
* **Retrieval Behavior:** Dense vector search maps the phrase into the proximity of introductory machine learning books.
* **Absence of Intent Extraction:** Search does not translate *"easy to start"* into a structured difficulty filter.

---

### Example 3: `"intro neural networks"`
* **Normalization:** `"intro neural networks"`.
* **Processing:** Short 3-word query.
* **Retrieval Behavior:** MiniLM easily encodes *"intro"* as a semantic synonym for introduction. Cross-encoder scores query against `Title: ... Subjects: ...`.

---

### Example 4: `"books by Andrew Ng"`
* **Author Matching Rule (`search/luminar_search.py:85-101`):**
  ```python
  def _author_match_ids(self, query, metadata):
      q = self._norm_text(query) # "books by andrew ng"
      for wid, book in metadata.items():
          if any(self._norm_text(a) == q for a in (book.get("authors") or [])):
              ids.add(wid)
  ```
* **Critical Finding:** Because `_norm_text(query)` equals `"books by andrew ng"`, and the book's author field is `"Andrew Ng"`, the exact equality test `q == a` **FAILS**.
* **Impact:** In the core search engine, `author_ids` evaluates to an empty set! Structured author boosting is not applied. The engine relies solely on dense vector matching of the phrase `"books by Andrew Ng"`.
* *(Note: If routed through `assistant/orchestrator.py`, the assistant extracts the entity `"Andrew Ng"` and passes it as a structured author parameter).*

---

### Example 5: `"networking books available here"`
* **Normalization:** `"networking books available here"`.
* **Availability Processing:** The search engine **does not recognize** the natural language tokens `"available here"` as an instruction to filter by physical inventory.
* **Impact:** The words `"available here"` are embedded directly into the 384-D query vector as literal semantic text. This can dilute retrieval quality because the vector now looks for books whose descriptions contain the word *"available"*.
* **To Filter Availability:** The client must explicitly submit HTTP parameters: `?library_id=XYZ&available_at_library=true`.

---

### Example 6: `"artifical inteligence"` [Typographical Error]
* **Scenario A: Standard Production Mode (`LEXICAL_SEARCH_ENABLED=false`):**
  * The misspelled query is passed directly to the MiniLM WordPiece tokenizer.
  * Tokenizer breaks `"artifical"` into subwords: `['art', '##ific', '##al']`.
  * The resulting dense embedding vector is distorted relative to the canonical vector for `"artificial intelligence"`, resulting in lower cosine similarity and potential retrieval degradation.
* **Scenario B: Lexical Sidecar Active (`LEXICAL_SEARCH_ENABLED=true`):**
  * `search/typo_assistance.py:conservative_similarity` computes:
    $$\text{Ratio} = \text{SequenceMatcher}(\text{"artifical inteligence"}, \text{"artificial intelligence"}).\text{ratio}() = 0.954$$
  * Since $0.954 \ge 0.86$ (`FUZZY_THRESHOLD`), the engine identifies the match and injects a candidate with `fuzzy_title` signal boosted by $+0.02$.
