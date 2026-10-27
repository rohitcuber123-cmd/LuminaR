# 04 — DOCUMENT PROCESSING & CONCEPT EXTRACTION

## 1. Supported Document & Data Sources

LuminaR extracts and constructs graph entities from three distinct types of inputs:

1. **Global Catalogue Metadata (Subsystem A):**
   - **Source:** MongoDB `books_collection`.
   - **Fields Used:** `work_id`, `title`, `authors`, `subjects`, `description`, `active`, `searchable`.
   - **Scope:** Full catalogue or bounded batches streamed offline to SQLite.

2. **Uploaded PDF Document Chunks (Subsystem B):**
   - **Source:** Text chunks produced by LuminaR's PDF ingestion pipeline (`pypdf` / PyMuPDF text extractors).
   - **Fields Used:** `chunk_id`, `text`, `pageStart`, `pageEnd`, `chapter`, `section`, `heading`.
   - **Sampling Bounds:** Maximum 1,200 chunks (`legacy.MAX_CHUNKS`), maximum 2,200 structural units (`MAX_UNITS`), maximum 6,000 sentences (`legacy.MAX_SENTENCES`). Maximum text per chunk: 12,000 characters.

3. **Tenant Institutional Inventory (Subsystem C):**
   - **Source:** MongoDB `institution_library_books` collections.
   - **Fields Used:** `library_book_id`, `title`, `authors`, `subjects`, `classification` (Dewey Decimal / LC), `global_work_id`.

---

## 2. Text Preprocessing & Cleaning Pipeline

### 2.1 Unicode Normalization & Cleaning
Across all subsystems, raw strings pass through strict Unicode normalization:
```python
# knowledge_graph/core.py:L15
def canonical(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())
```
- **NFKC Normalization:** Converts full-width characters (e.g., `Ｃomputer` $\to$ `Computer`) and decomposes ligatures (`ﬁ` $\to$ `fi`).
- **Case-Folding:** Case-insensitive comparison (`casefold()` handles German `ß` $\to$ `ss` and Greek accents correctly, unlike simple `lower()`).
- **Whitespace Collapsing:** Replaces multi-spaces, tabs, and newlines with a single space and trims edges.

In Subsystem B ([`rag/services/document_knowledge.py:L24-L28`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L24-L28)), additional cleaning strips zero-width spaces (`\u200b`), byte order marks (`\ufeff`), soft hyphens (`\u00ad`), and joins hyphenated line wraps:
```python
text = re.sub(r'([A-Za-z])-\s*\n\s*([a-z])', r'\1\2', text)
```

---

## 3. Concept Extraction: Subsystem A (Corpus Topics)

In the catalogue graph, topics are mined from book descriptions using adjacent source phrase extraction and TF-IDF degree bounding ([`knowledge_graph/topics.py`](file:///d:/SDC/LibraryLLM/knowledge_graph/topics.py)).

### 3.1 Mathematical Formulation
1. **Tokenization:** Regex matching Unicode word tokens between 3 and 40 characters:
   $$\text{WORD} = \backslash b[\wedge\backslash W\backslash d\_]\{3, 40\}\backslash b$$
2. **N-Gram Candidate Generation:** Adjacent bigrams and trigrams ($size \in \{2, 3\}$) are extracted. Candidates containing any stopword from `STOP` are immediately rejected:
   $$\text{STOP} = \text{scikit-learn ENGLISH\_STOP\_WORDS} \cup \{\text{book, guide, novel, edition, reader, isbn, ...}\}$$
3. **Corpus Degree Bounding:** To eliminate both rare typos and uninformative generic phrases, a candidate phrase $p$ must satisfy:
   $$\text{min\_degree} \le \text{degree}(p) \le \max\left(\text{min\_degree}, \lfloor N \cdot \text{maximum\_degree\_fraction} \rfloor\right)$$
   Where:
   - $\text{min\_degree} = 3$
   - $\text{maximum\_degree\_fraction} = 0.001$ ($0.1\%$ of the catalogue)
   - $N$ = total books in the catalogue
4. **TF-IDF Phrase Scoring:**
   $$\text{score}(p) = \left(1 + \ln(\text{tf}(p))\right) \cdot \left(1 + \ln\left(\frac{N + 1}{\text{degree}(p) + 1}\right)\right)$$
5. **Sub-Phrase Redundancy Pruning:**
   ```python
   # knowledge_graph/topics.py:L46-L51
   chosen = []
   for phrase in ranked:
       if any(phrase in other or other in phrase for other in chosen):
           continue
       chosen.append(phrase)
       if len(chosen) == TOPIC_POLICY['max_topics_per_book']: # Capped at 5
           break
   ```

---

## 4. Concept Extraction: Subsystem B (Document Concepts)

Subsystem B extracts pedagogical concepts and factual relationships directly from PDF sentences ([`rag/services/document_knowledge.py:L212-L344`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L212-L344)).

### 4.1 Candidate Extraction Sources
1. **Copula Definition Matcher:**
   $$\text{DEFINITION} = \wedge((?:[A-Za-z0-9-]+\backslash s+)\{0, 5\}[A-Za-z0-9-]+)\backslash s+(\text{copula})\backslash s+(.+?[.!?])\$$$
   Where copulas include: `is defined as`, `refers to`, `consists of`, `is used for`, `means`, `is`, `are`.
2. **Structural Headings:** Heading units extracted from document sections (`unit_kind == 'HEADING'`).
3. **List Items & Process Steps:** Bulleted lists (`BULLET = re.compile(r'^\s*(?:\d+[.)]|[ivx]+[.)]|[•\-])')`).
4. **Recurring Multi-Word Phrases:** 2-to-4 word phrases occurring at least 3 times across at least 2 distinct document pages.

### 4.2 Multi-Signal Concept Scoring Formula
For each candidate concept $c$, LuminaR computes an evidence score combining structural and statistical signals:

$$\text{Score}(c) = \sum \text{Signals} - \text{GenericityPenalty} - \text{FragmentPenalty}$$

Where the signals are:
- $\text{Definition Signal} = 4.5 \times \mathbb{I}(\text{defined})$
- $\text{Heading Signal} = 2.8 \times \mathbb{I}(\text{heading})$
- $\text{Frequency Signal} = \min(1.5, 0.6 \cdot \ln(1 + |\text{evidence}|))$
- $\text{Multi-Page Signal} = \min(1.2, 0.25 \cdot |\text{pages}|)$
- $\text{Specificity Signal} = \min\left(2.0, \frac{1}{|W|} \sum_{w \in W} \ln\left(1 + \frac{|\text{rows}|}{\text{df}(w)}\right)\right)$
- $\text{Relation Signal} = 0.8 \times \mathbb{I}(\text{has substantive relation})$
- $\text{Multi-Word Signal} = \min(1.0, 0.35 \cdot (|W| - 1))$

Penalties:
- $\text{Genericity Penalty} = (0.7 \text{ if defined else } 3.0 \text{ if single-word else } 0.25) + \max(0, 1.2 - \text{specificity}) + 2.0 \cdot \mathbb{I}(\text{generic context word})$
- $\text{Fragment Penalty} = 2.5 \times \mathbb{I}(\text{starts with 'step 1', 'part 2', etc.})$

**Threshold:** Any candidate with $\text{Score}(c) < 4.1$ is rejected (`metrics['genericity_rejections'] += 1`).

---

## 5. Concept Normalization & Deduplication

To prevent fragmented or duplicate nodes representing identical concepts, LuminaR applies three layers of deduplication:

### 5.1 Morphological Singularization (`phrase_key`)
```python
# rag/services/document_knowledge.py:L31-L33
def phrase_key(label):
    words = legacy.normalize(label.replace('-', ' ')).split()
    return ' '.join(w[:-1] if len(w) > 4 and w.endswith('s') and not w.endswith('ss') else w for w in words)
```
This merges singular and plural forms (e.g., `neural networks` $\to$ `neural network`).

### 5.2 Lexical Token-Subset Merging
If candidate $A$'s token set is a subset of candidate $B$'s token set ($A \subseteq B$ or $B \subseteq A$), and both are not independently verified definitions, the redundant candidate is merged.

### 5.3 Semantic Embedding Deduplication via MMR
The top 192 scored candidates are encoded using `all-MiniLM-L6-v2` into 384-dimensional normalized vectors $\mathbf{v}_i$. Maximal Marginal Relevance (MMR) selects candidates:
$$\text{MMR\_Score}(c_i) = \text{Score}(c_i) - 2.2 \cdot \max_{c_j \in \text{Selected}} (\mathbf{v}_i \cdot \mathbf{v}_j)$$

If two candidates share cosine similarity $\ge 0.90$ ($\mathbf{v}_i \cdot \mathbf{v}_j \ge 0.90$) and have identical explanation text (SequenceMatcher ratio $\ge 0.90$), the duplicate is suppressed.
