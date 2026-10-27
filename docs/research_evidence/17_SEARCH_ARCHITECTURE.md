# 17_SEARCH_ARCHITECTURE.md: Master Search Architecture & Retrieval Modalities

## Executive Summary

This document audits all search modalities within LuminaR, detailing which retrieval paradigms are active in the production runtime, which exist as experimental/optional sidecars, and which are completely absent despite common literature assumptions.

---

## 1. Inventory of Search Modalities

| Search Modality | Implemented? | Runtime Status | Implementation Location | Underlying Technology |
| :--- | :---: | :---: | :--- | :--- |
| **Dense Semantic Vector Search** | **YES** | **ACTIVE / PRIMARY** | `search/luminar_search.py:421-469` | `all-MiniLM-L6-v2` (384-D) + `faiss.IndexHNSWFlat` |
| **Cross-Encoder Reranking** | **YES** | **ACTIVE / PRIMARY** | `search/luminar_search.py:536-543` | `cross-encoder/ms-marco-MiniLM-L-6-v2` (Top 50) |
| **Exact Field Match** | **YES** | **ACTIVE** | `search/luminar_search.py:85`, `search/lexical_integration.py:15` | Structured string comparison on `work_id`, `isbn`, author, title |
| **Substring Match** | **YES** | **ACTIVE** | `backend/services/library_catalogue_experience.py:49` | MongoDB `$regex` on casefolded `search_text` |
| **Regex Search** | **YES** | **ACTIVE** | `backend/services/library_catalogue_experience.py:46-56` | MongoDB regex aggregation pipelines |
| **Fuzzy / Typo Search** | **YES** | **OPTIONAL SIDECAR** | `search/lexical_store.py:20`, `search/typo_assistance.py:25` | Single-edit prefix generation + Python `difflib.SequenceMatcher` ($\ge 0.86$) |
| **Hybrid Search (Dense + Lexical)** | **YES** | **OPTIONAL SIDECAR** | `search/luminar_search.py:470-482` | Dense HNSW + SQLite lexical candidate merge (`LEXICAL_SEARCH_ENABLED=true`) |
| **BM25 / Okapi Inverted Index** | **NO** | **NOT IMPLEMENTED** | N/A | Neither Lucene, Elasticsearch, Whoosh, nor BM25 ranking exists in the runtime |
| **MongoDB Full-Text (`$text`)** | **NO** (In core search) | **NOT ACTIVE** | N/A | Core search routes directly to FAISS HNSW; catalogue routes use `$regex` |

---

## 2. Active Search Runtime Architecture

```mermaid
flowchart TD
    ClientQuery[Client HTTP Search Request<br>GET /search?q=query&limit=10] --> Endpoint[search/api.py:search]

    Endpoint --> Engine[search/luminar_search.py:LuminaRSearchEngine]

    subgraph Primary Dense Path
        Engine --> EmbedQuery["1. Vectorization<br>MiniLM-L6-v2.encode([q])<br>Output: 384-D Vector"]
        EmbedQuery --> L2Norm["2. L2 Normalization<br>faiss.normalize_L2(vec)"]
        L2Norm --> HNSWLookup["3. FAISS HNSW Search<br>Snapshot.candidates(query_vector, fetch_k)<br>Pool: Top 50–100 Candidates"]
        HNSWLookup --> MongoHydrate["4. Metadata Fetch<br>books_collection.find(work_ids)<br>Filter valid books"]
    end

    subgraph Optional Lexical Sidecar (LEXICAL_SEARCH_ENABLED=true)
        Engine -.-> LexicalStore["SQLite Lexical Store<br>datasets/ai/lexical/published/"]
        LexicalStore -.-> ExactFuzzyMatch["Exact / Fuzzy Lookup<br>SequenceMatcher >= 0.86"]
        ExactFuzzyMatch -.-> MergeCandidates["merge_lexical_candidates()<br>Inject Lexical Signals"]
    end

    MongoHydrate --> MergeCandidates
    MergeCandidates --> PairConstruction["5. Cross-Encoder Pair Assembly<br>[query, Title + Authors + Subjects]"]
    PairConstruction --> CrossEncoder["6. Cross-Encoder Forward Pass<br>ms-marco-MiniLM-L-6-v2.predict()<br>batch_size=16"]
    CrossEncoder --> Sorting["7. Rank Sort<br>Rerank Score desc, HNSW Score desc"]
    Sorting --> AuthorBoost{"Exact Author Match?<br>_author_match_ids()"}
    AuthorBoost -->|Yes| ElevateAuthor["Elevate Author Matches to Tier 1"]
    AuthorBoost -->|No| PhysicalFilter
    ElevateAuthor --> PhysicalFilter{"available_at_library=true?"}
    PhysicalFilter -->|Yes| FilterInventory["Filter by library_inventory<br>available_physical_copies > 0"]
    PhysicalFilter -->|No| SliceResults["Slice [:final_k] (Default 10)"]
    FilterInventory --> SliceResults
    SliceResults --> ReturnJSON[Return Final Ranked JSON Payload]
```

---

## 3. Detailed Modality Examination

### 3.1 The Dense Vector Paradigm (Active Primary)
* Every search query is converted into a 384-dimensional unit vector by `sentence-transformers/all-MiniLM-L6-v2`.
* Nearest-neighbor traversal is performed against an in-memory FAISS HNSW graph indexing 5,000,000 OpenLibrary titles.
* Inner-product distance on normalized vectors computes cosine similarity $\cos(\theta)$.

### 3.2 The Cross-Encoder Reranking Paradigm (Active Primary)
* Unlike bi-encoders that encode query and document independently, the cross-encoder concatenates both into a single sequence:
  $$\mathbf{x} = \text{[CLS] } \text{Query} \text{ [SEP] Title: } T \text{ Authors: } A \text{ Subjects: } S \text{ [SEP]}$$
* Full multi-layer cross-attention between every query word and every book metadata word produces a nuanced scalar relevance score.
* Evaluates `CROSSENCODER_RERANK_DEPTH = 50` candidates per request.

### 3.3 The Lexical Paradigm (SQLite Prefix Range + Fuzzy Probes)
* When enabled via `LEXICAL_SEARCH_ENABLED=true`, LuminaR does **not** query a Lucene BM25 index.
* Instead, it queries an immutable SQLite database (`datasets/ai/lexical/published/`) using B-tree range queries:
  ```sql
  SELECT normalized_value, work_id FROM lexical_values 
  WHERE value_type=? AND normalized_value>=? AND normalized_value<? 
  ORDER BY normalized_value, work_id LIMIT 50;
  ```
* For typos, it runs single-character insertion/deletion/transposition candidate generators (`edit_prefixes`) bounded to 256 seeks and scores them via Python `difflib.SequenceMatcher`.

### 3.4 Catalogue Experience Paradigm (MongoDB Regex)
* Within institutional tenant views (`/libraries/{id}/catalogue/books`), queries are filtered against `institution_library_books` using MongoDB regular expressions:
  ```python
  query['search_text'] = {'$regex': re.escape(search.strip().casefold())}
  ```
* This provides instant substring matching across local titles and authors without involving the AI models.
