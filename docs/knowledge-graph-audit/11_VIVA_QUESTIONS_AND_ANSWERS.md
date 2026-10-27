# 11 — COMPREHENSIVE VIVA & TECHNICAL REVIEW QUESTIONS (60+ QUESTIONS)

This document contains 65 rigorous, code-verified technical questions and answers designed specifically for university project reviews, viva voce examinations, and defense sessions.

Every question provides:
1. **Spoken Viva Answer (20–45 seconds):** Concise, authoritative response.
2. **Deep Technical Explanation:** Mathematical and architectural breakdown.
3. **Exact Code Reference:** File path and line numbers.
4. **Likely Follow-Up Question:** Anticipated examiner probe.
5. **Necessary Qualification:** Boundaries preventing unsupported claims.

---

## CATEGORY 1: FUNDAMENTAL CONCEPTS & SYSTEM TAXONOMY (Q01 – Q10)

### Q01: What is a Knowledge Graph, and how is it defined in LuminaR?
- **Spoken Viva Answer:** A knowledge graph represents entities and their semantic relationships as a structured network of nodes and edges. In LuminaR, we implement a typed bipartite metadata graph on SQLite linking books to authors, subjects, and description topics, along with a syntactic copula concept network extracted from PDF documents for study tools.
- **Deep Technical Explanation:** In Subsystem A, the graph is a heterogeneous bipartite network $G = (V_B \cup V_F, E)$, where $V_B$ represents book entities, $V_F$ represents typed feature entities, and $E \subseteq V_B \times V_F$ represents formal predicates (`AUTHORED_BY`, `HAS_SUBJECT`, `HAS_TOPIC`). In Subsystem B, it is a syntactic concept graph $G = (V_C, E_R)$ where $E_R$ represents copulas (`DEFINED_AS`, `CONTAINS`, `USED_FOR`).
- **Exact Code Reference:** [`knowledge_graph/relations.py:L2-L4`](file:///d:/SDC/LibraryLLM/knowledge_graph/relations.py#L2-L4) and [`knowledge_graph/core.py:L108-L116`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L108-L116).
- **Likely Follow-Up:** Is your graph an RDF triple store or an open-world knowledge base?
- **Qualification:** It is not an open-world RDF store like Wikidata; it operates on a closed schema over verified catalogue metadata and document text.

### Q02: Is this a true knowledge graph or simply a concept co-occurrence network?
- **Spoken Viva Answer:** It is a typed bipartite entity network, not an unweighted co-occurrence graph. Edges represent typed relationships weighted by logarithmic feature rarity, and book recommendations are generated through deterministic 2-hop traversals with exact, additive mathematical reason paths.
- **Deep Technical Explanation:** In simple co-occurrence graphs, edges represent raw frequency of adjacent words. In LuminaR, edges connect typed entities (`Book` to `Author`, `Subject`, `Topic`). Edges are weighted using an inverse-degree formulation: $W_k \cdot (1 + \ln((N+1)/(\text{deg}+1)))$, and vector cosine normalization guarantees that every shared bridge contributes an exact percentage to the recommendation score.
- **Exact Code Reference:** [`scripts/build_catalogue_graph.py:L67-L70`](file:///d:/SDC/LibraryLLM/scripts/build_catalogue_graph.py#L67-L70).
- **Likely Follow-Up:** Why did you not use direct book-to-book edges?
- **Qualification:** Direct book-to-book edges would obscure the explainable reason bridges and require $O(B^2)$ storage.

### Q03: What are the three distinct graph implementations in LuminaR?
- **Spoken Viva Answer:** LuminaR has three separate graph subsystems: first, the Global Catalogue Graph on SQLite for book recommendations and Graph Lab; second, the Document Concept Map in RAG study tools for PDF mind maps; and third, the Tenant Intelligence Graph stored as JSON artifacts for private institutional libraries.
- **Deep Technical Explanation:** Subsystem A (`knowledge_graph/core.py`) operates globally on `catalogue.sqlite`. Subsystem B (`rag/services/document_knowledge.py`) operates in-memory on PDF chunks. Subsystem C (`backend/services/library_intelligence_artifacts.py`) operates on disk JSON files scoped per institutional tenant with SHA-256 validation.
- **Exact Code Reference:** [`01_KNOWLEDGE_GRAPH_OVERVIEW.md`](file:///d:/SDC/docs/knowledge-graph-audit/01_KNOWLEDGE_GRAPH_OVERVIEW.md).
- **Likely Follow-Up:** Which graph is displayed in the main navigation under "Graph Lab"?
- **Qualification:** Graph Lab displays Subsystem A (the Global Catalogue Bipartite Graph).

### Q04: Why did you not use Neo4j for graph storage?
- **Spoken Viva Answer:** Neo4j introduces significant overhead: JVM memory footprints, network roundtrips, Cypher parsing, and operational complexity. Because our catalogue graph executes deterministic 2-hop bipartite queries, SQLite with read-only URI mode and B-tree indexes executes in under 10 milliseconds with zero infrastructure overhead.
- **Deep Technical Explanation:** Neo4j excels at arbitrary-depth variable-length path traversal ($k > 4$). In LuminaR, the discovery path is strictly fixed to 2 hops: $\text{Book} \to \text{Feature} \to \text{Book}$. In relational terms, this is an indexed self-join over `edges` on `(kind, term)`, which SQLite handles with zero network latency using `PRAGMA query_only=ON`.
- **Exact Code Reference:** [`knowledge_graph/core.py:L31-L37`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L31-L37).
- **Likely Follow-Up:** At what catalogue scale would Neo4j become necessary?
- **Qualification:** If LuminaR evolved into deep multi-hop citation traversals ($k \ge 5$) or required live concurrent graph mutations.

### Q05: Does LuminaR use an LLM to generate graph relationships?
- **Spoken Viva Answer:** No. Graph generation in LuminaR is 100% deterministic and rule-based. It does not invoke Qwen, GPT-4, or any other LLM. Telemetry explicitly logs zero LLM calls (`qwen_calls: 0`), preventing hallucinations, API costs, and non-deterministic behavior.
- **Deep Technical Explanation:** LLMs are prone to relation hallucination and high inference costs. Subsystem A extracts entities from MongoDB metadata; Subsystem B extracts syntactic copulas using compiled regular expressions (`DEFINITION = re.compile(...)`); Subsystem C compiles verified tenant books.
- **Exact Code Reference:** [`rag/services/document_knowledge.py:L445`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L445).
- **Likely Follow-Up:** Would an LLM improve relation extraction accuracy?
- **Qualification:** LLMs can extract nuanced relations but lack deterministic reproducibility and create high GPU latency.

### Q06: Is GraphRAG implemented in LuminaR?
- **Spoken Viva Answer:** No. GraphRAG is not implemented. The knowledge graphs do not participate in vector retrieval, chunk reranking, or LLM context prompt synthesis for document Q&A. The graph coexists alongside RAG purely as an interactive visualization and explainable discovery tool.
- **Deep Technical Explanation:** GraphRAG requires graph entity extraction, community summarization (e.g., via Leiden clustering), and subgraph retrieval injected into prompt generation. In LuminaR, `rag/services/retrieval.py` performs hybrid vector/BM25 retrieval over text chunks only.
- **Exact Code Reference:** [`08_RAG_INTEGRATION_AND_SECURITY.md`](file:///d:/SDC/docs/knowledge-graph-audit/08_RAG_INTEGRATION_AND_SECURITY.md).
- **Likely Follow-Up:** How can a knowledge graph coexist with RAG without being GraphRAG?
- **Qualification:** They share document provenance but operate as decoupled feature modules.

### Q07: How do you prevent the graph from becoming an unreadable "hairball"?
- **Spoken Viva Answer:** We apply aggressive multi-stage pruning: candidates are restricted to the top 10 to 50 books; each book displays only its strongest 3 reason paths; and description topics are degree-bounded between 3 and 0.1% of the catalogue size.
- **Deep Technical Explanation:** Graph clutter is prevented via: (1) degree bounding in SQL ($3 \le \text{degree} \le 0.001 \times N$), (2) top-$K$ candidate truncation, (3) `exploration()` bridge capping (`max_reasons=3`), and (4) SVG column constraints.
- **Exact Code Reference:** [`knowledge_graph/core.py:L108-L116`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L108-L116).
- **Likely Follow-Up:** Does limiting reasons to 3 discard important connections?
- **Qualification:** The similarity score calculates all shared features; only the visual exploration renders the top 3 bridges.

### Q08: How are node IDs constructed to ensure determinism?
- **Spoken Viva Answer:** Node IDs are generated deterministically using SHA-256 hashes of canonicalized entity strings. A feature node ID is always its entity type concatenated with the SHA-256 hash of its NFKC-normalized term, guaranteeing identical IDs across rebuilds.
- **Deep Technical Explanation:** `feature_id(kind, term) = kind + ':' + sha256(canonical(term))`. For document concepts: `concept_` + `sha256(text)[:16]`. For tenant books: `book:` + `library_book_id`.
- **Exact Code Reference:** [`knowledge_graph/core.py:L24`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L24).
- **Likely Follow-Up:** What happens if two different terms hash to the same ID?
- **Qualification:** SHA-256 collision probability is cryptographically negligible ($< 10^{-60}$).

### Q09: Are relationships in the graph factually verified or statistical?
- **Spoken Viva Answer:** In Subsystem A, relationships represent catalogue metadata assertions (e.g., this book is classified under this subject), not external factual ground truth. Shared author names are string matches, not entity-resolved human identities.
- **Deep Technical Explanation:** The system explicitly documents: *"Connections come from catalogue author names and subject labels. Shared names have not been resolved into verified author identities."* Two authors named "John Smith" will map to the same node unless disambiguated in the source data.
- **Exact Code Reference:** [`frontend/src/pages/KnowledgeGraphPage.tsx:L95`](file:///d:/SDC/LibraryLLM/frontend/src/pages/KnowledgeGraphPage.tsx#L95) and [`scripts/build_catalogue_graph.py:L68`](file:///d:/SDC/LibraryLLM/scripts/build_catalogue_graph.py#L68).
- **Likely Follow-Up:** How could entity resolution be added?
- **Qualification:** By integrating authority files such as VIAF, ORCID, or Wikidata QIDs.

### Q10: What graph visualization library is used on the frontend?
- **Spoken Viva Answer:** None. We built a custom SVG rendering engine in React. It renders nodes as styled SVG rectangles and edges as smooth cubic Bezier curves across three deterministic columns, avoiding the bundle size and layout instability of D3 or Cytoscape.
- **Deep Technical Explanation:** Native SVG `<svg viewBox="0 0 900 height">` with cubic Bezier `<path d="M ax ay C ... bx by" />`. Width and height scale with zoom parameters ($0.7 \le \text{zoom} \le 1.8$).
- **Exact Code Reference:** [`frontend/src/components/MetadataGraphCanvas.tsx:L8-L11`](file:///d:/SDC/LibraryLLM/frontend/src/components/MetadataGraphCanvas.tsx#L8-L11).
- **Likely Follow-Up:** Can users drag nodes around?
- **Qualification:** No, coordinates are mathematically positioned in columns to maintain reason-path legibility.

---

## CATEGORY 2: ARCHITECTURE, PERSISTENCE & MULTI-TENANCY (Q11 – Q20)

### Q11: How is the catalogue graph database initialized and updated?
- **Spoken Viva Answer:** It is built offline by streaming public book metadata from MongoDB into a temporary SQLite database, indexing tables, calculating inverse-degree feature weights and vector norms, and atomically replacing the production SQLite file via `os.replace`.
- **Deep Technical Explanation:** `scripts/build_catalogue_graph.py` writes to `catalogue.building.sqlite` with `PRAGMA synchronous=OFF` and `PRAGMA journal_mode=OFF`. Once indexing and VACUUM finish, an atomic rename moves it to `catalogue.sqlite`.
- **Exact Code Reference:** [`scripts/build_catalogue_graph.py:L20-L72`](file:///d:/SDC/LibraryLLM/scripts/build_catalogue_graph.py#L20-L72).
- **Likely Follow-Up:** Why is an atomic rename necessary?
- **Qualification:** It ensures readers querying the API never encounter a partially-built or locked database.

### Q12: How does the backend detect if a book's metadata changed since the graph was built?
- **Spoken Viva Answer:** It performs a fail-closed consistency check comparing the snapshot's author and subject sets against the live MongoDB record. If the metadata diverges, it raises HTTP 409 Conflict.
- **Deep Technical Explanation:** `features_current(snapshot, live)` checks: (1) `set(terms(snapshot['authors'])) == set(terms(live['authors']))`, (2) subjects equality, and (3) description SHA-256 hash match.
- **Exact Code Reference:** [`backend/routes/knowledge_graph.py:L43-L54`](file:///d:/SDC/LibraryLLM/backend/routes/knowledge_graph.py#L43-L54).
- **Likely Follow-Up:** Why not automatically update the SQLite row on the fly?
- **Qualification:** Updating one book alters feature degrees and global norms, which would corrupt cosine scores across other books.

### Q13: How does the system handle isolated books with no authors or subjects?
- **Spoken Viva Answer:** Isolated books are indexed in SQLite but return an empty recommendation list with a clear reason message: "No author or subject links for this book."
- **Deep Technical Explanation:** In `CatalogueGraph.more_like_this()`, if `features` query returns empty, it immediately returns `{'recommendations': [], 'candidate_count': 0, 'reason': 'No author or subject links for this book.'}`.
- **Exact Code Reference:** [`knowledge_graph/core.py:L68`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L68).
- **Likely Follow-Up:** Can an isolated book still be recommended to others?
- **Qualification:** No, because recommendations require at least one shared bridge feature.

### Q14: How are active loans and reservations handled in recommendations?
- **Spoken Viva Answer:** Active loans and reservations are dynamically queried from MongoDB and excluded from candidate recommendations so readers are never recommended books they currently possess or have on hold.
- **Deep Technical Explanation:** `exclusions(user)` queries `issues_collection` for `status: ISSUED` and `reservations_collection` for `ACTIVE` or `READY_FOR_PICKUP`. Excluded work IDs are filtered out in SQL: `if book['work_id'] in excluded_ids: continue`.
- **Exact Code Reference:** [`backend/routes/knowledge_graph.py:L37-L41`](file:///d:/SDC/LibraryLLM/backend/routes/knowledge_graph.py#L37-L41).
- **Likely Follow-Up:** What if a user is not signed in?
- **Qualification:** The endpoint is guarded by `user = Depends(identity)`; authentication is mandatory.

### Q15: How does multi-tenancy work in the Tenant Intelligence Graph (Subsystem C)?
- **Spoken Viva Answer:** Each tenant library has a completely separate directory namespace containing immutable graph artifacts validated by SHA-256 manifests. Background workers operate under distributed leases, and queries enforce tenant membership.
- **Deep Technical Explanation:** Artifacts live at `local-data/library-intelligence/{library_id}/kg/{generation_id}/`. Manifest files list exact SHA-256 checksums. Access is checked via `require_library_staff(library_id, actor)`.
- **Exact Code Reference:** [`backend/services/library_intelligence_artifacts.py:L20-L38`](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_artifacts.py#L20-L38).
- **Likely Follow-Up:** Can a user in Library A access Library B's graph by altering the URL?
- **Qualification:** No, the API verifies database membership and raises 403 Forbidden.

### Q16: How is the in-memory cache managed for tenant graphs?
- **Spoken Viva Answer:** We use an LRU `ArtifactCache` limited to at most 3 tenant graphs and 256 megabytes of resident RAM.
- **Deep Technical Explanation:** `ArtifactCache` uses an `OrderedDict` guarded by a re-entrant lock (`RLock`). Memory usage is calculated via recursive object sizing (`sys.getsizeof`). If capacity is exceeded, oldest entries are evicted.
- **Exact Code Reference:** [`backend/services/library_intelligence_artifacts.py:L132-L165`](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_artifacts.py#L132-L165).
- **Likely Follow-Up:** What happens if a tenant graph is evicted and requested again?
- **Qualification:** It is loaded back from verified disk JSON artifacts.

### Q17: What prevents path traversal vulnerabilities in tenant graph loading?
- **Spoken Viva Answer:** All paths are asserted against their canonical `.resolve()` path. Any path attempting directory traversal triggers an HTTP 404 or 409 exception.
- **Deep Technical Explanation:** `if path.resolve() != path: raise HTTPException(404, 'Artifact namespace is invalid.')`.
- **Exact Code Reference:** [`backend/services/library_intelligence_artifacts.py:L23`](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_artifacts.py#L23).
- **Likely Follow-Up:** Does this prevent symlink attacks?
- **Qualification:** Yes, because `.resolve()` resolves symlinks before equality checking.

### Q18: What SQLite PRAGMAs are used to optimize graph performance?
- **Spoken Viva Answer:** In read-only serving mode, we enforce `PRAGMA query_only=ON`. During offline builds, we use `PRAGMA journal_mode=OFF`, `synchronous=OFF`, `temp_store=FILE`, and a negative cache size of -131072 (128 megabytes).
- **Deep Technical Explanation:** `PRAGMA cache_size = -131072` allocates 128 MB of memory to SQLite's page cache. `PRAGMA query_only = ON` prevents any accidental modification by API threads.
- **Exact Code Reference:** [`knowledge_graph/core.py:L35`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L35) and [`scripts/build_catalogue_graph.py:L24`](file:///d:/SDC/LibraryLLM/scripts/build_catalogue_graph.py#L24).
- **Likely Follow-Up:** Does `PRAGMA synchronous=OFF` risk database corruption?
- **Qualification:** Only during building; the finished file is atomically renamed and opened strictly read-only.

### Q19: How are deleted source documents handled in the graph?
- **Spoken Viva Answer:** The API cross-checks the snapshot against live MongoDB active records. If a book was deleted, it is filtered out of recommendations or returns a 404 if requested as a seed.
- **Deep Technical Explanation:** `live = current_books(books_collection, [...])`. Any recommendation not present in `live` is dropped: `[r for r in recommendations if r['work_id'] in live]`.
- **Exact Code Reference:** [`backend/routes/knowledge_graph.py:L56-L58`](file:///d:/SDC/LibraryLLM/backend/routes/knowledge_graph.py#L56-L58).
- **Likely Follow-Up:** How often should the SQLite database be rebuilt?
- **Qualification:** Periodically (e.g., nightly cron) to clean deleted nodes and incorporate new books.

### Q20: How are book titles searched in the Knowledge Graph?
- **Spoken Viva Answer:** We perform bounded prefix range scans over the indexed `title_key` column in SQLite, supporting instant typeahead search without full table scans.
- **Deep Technical Explanation:** `SELECT * FROM books WHERE title_key >= ? AND title_key < ? ORDER BY title_key, work_id LIMIT ?` using `(prefix, prefix + '\U0010ffff')`.
- **Exact Code Reference:** [`knowledge_graph/core.py:L57-L58`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L57-L58).
- **Likely Follow-Up:** Can users search by work ID directly?
- **Qualification:** Yes, if the query matches `^OL[A-Za-z0-9_-]+$`, it performs an $O(1)$ work ID lookup.

---

## CATEGORY 3: MATHEMATICAL FORMULATIONS & SCORING (Q21 – Q35)

### Q21: What is the exact mathematical formula for feature weighting?
- **Spoken Viva Answer:** The weight of a feature is its relation multiplier times one plus the natural logarithm of total books plus one divided by feature degree plus one.
- **Deep Technical Explanation:**
  $$\text{weight}(k, t) = W_k \cdot \left(1 + \ln\left(\frac{N + 1}{\text{degree}(k, t) + 1}\right)\right)$$
  Where $W_{\text{author}} = 2.0$, $W_{\text{subject}} = 1.0$, $W_{\text{topic}} = 0.5$, and $N$ is catalogue size.
- **Exact Code Reference:** [`scripts/build_catalogue_graph.py:L55`](file:///d:/SDC/LibraryLLM/scripts/build_catalogue_graph.py#L55).
- **Likely Follow-Up:** Why is $+1$ added to the numerator and denominator?
- **Qualification:** Laplace smoothing prevents division by zero and ensures weights remain positive.

### Q22: Why is the author relation weight (2.0) higher than subject (1.0)?
- **Spoken Viva Answer:** An author is a stronger indicator of literary style, voice, and topic continuity than a broad subject classification, so author bridges are weighted twice as heavily as subject bridges.
- **Deep Technical Explanation:** In recommender systems, shared authorship is a high-precision, low-entropy signal compared to broad topical subjects (e.g., "History"). The $2.0\times$ multiplier reflects this empirical domain prior.
- **Exact Code Reference:** [`knowledge_graph/relations.py:L2`](file:///d:/SDC/LibraryLLM/knowledge_graph/relations.py#L2).
- **Likely Follow-Up:** Were these weights learned via machine learning?
- **Qualification:** No, they are versioned, conservative domain-expert policies (`RELATION_WEIGHTS`).

### Q23: What is the mathematical formulation of the cosine similarity score?
- **Spoken Viva Answer:** It is the dot product of shared feature weights squared divided by the square root of the product of the seed book norm and the candidate book norm.
- **Deep Technical Explanation:**
  $$\text{score}(s, c) = \frac{\sum_{f \in \text{Features}(s) \cap \text{Features}(c)} \text{weight}(f)^2}{\sqrt{\text{Norm}(s) \cdot \text{Norm}(c)}}$$
  Where $\text{Norm}(b) = \sum_{f \in \text{Features}(b)} \text{weight}(f)^2$.
- **Exact Code Reference:** [`knowledge_graph/core.py:L70-L73`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L70-L73).
- **Likely Follow-Up:** Does the score always fall between 0 and 1?
- **Qualification:** Yes, by the Cauchy-Schwarz inequality, normalized cosine similarity is strictly bounded in $[0, 1]$.

### Q24: How is each reason path's contribution calculated?
- **Spoken Viva Answer:** The contribution of a reason path is the squared weight of its shared bridge feature divided by the square root of the seed norm times the candidate norm.
- **Deep Technical Explanation:**
  $$\text{contribution}(p) = \frac{\text{weight}(f)^2}{\sqrt{\text{Norm}(s) \cdot \text{Norm}(c)}}$$
- **Exact Code Reference:** [`knowledge_graph/core.py:L103`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L103).
- **Likely Follow-Up:** Do the path contributions sum to the total book score?
- **Qualification:** Yes, the sum of all path contributions equals the candidate's total score exactly.

### Q25: How do you handle books that share multiple authors and subjects?
- **Spoken Viva Answer:** Each shared feature adds its squared weight into the numerator sum, increasing the cosine similarity score additively while normalizing against total metadata volume.
- **Deep Technical Explanation:** Multiple shared features increase the numerator dot product $\sum w_f^2$. Books sharing multiple rare features receive significantly higher scores than books sharing a single generic subject.
- **Exact Code Reference:** [`knowledge_graph/core.py:L70`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L70).
- **Likely Follow-Up:** Can a book with 50 subjects game the system to rank higher?
- **Qualification:** No, because its denominator norm $\sqrt{\text{Norm}(c)}$ will be massive, penalizing excessive subjects.

### Q26: What is the time complexity of the 2-hop traversal query?
- **Spoken Viva Answer:** It is proportional to the number of seed features times the average degree of those features, taking roughly 4 to 12 milliseconds in SQLite.
- **Deep Technical Explanation:** $O(|F_s| \cdot \overline{\text{deg}}(f))$. Because the database maintains an index on `edges(kind, term, book_id)`, SQLite traverses directly to candidate books without evaluating unrelated catalogue items.
- **Exact Code Reference:** [`06_GRAPH_ALGORITHMS_AND_DATA_STRUCTURES.md`](file:///d:/SDC/docs/knowledge-graph-audit/06_GRAPH_ALGORITHMS_AND_DATA_STRUCTURES.md).
- **Likely Follow-Up:** How does this compare to evaluating a full cosine similarity matrix?
- **Qualification:** A full matrix requires $O(B^2)$ comparisons (billions of operations), whereas our indexed join evaluates only connected candidates.

### Q27: How does description topic weighting work in V2?
- **Spoken Viva Answer:** Description topics are assigned a base multiplier of 0.5, giving them one-quarter the squared weight contribution of a subject feature at equal degree.
- **Deep Technical Explanation:** $W_{\text{topic}} = 0.5 \implies W_{\text{topic}}^2 = 0.25$, whereas $W_{\text{subject}}^2 = 1.0$. This conservative weight ensures that text-mined topics assist discovery without overwhelming verified human-catalogued metadata.
- **Exact Code Reference:** [`scripts/build_kg_topics.py:L91`](file:///d:/SDC/LibraryLLM/scripts/build_kg_topics.py#L91).
- **Likely Follow-Up:** Why are topics restricted to 5 per book?
- **Qualification:** To prevent long descriptions from inflating book norms and diluting subject precision.

### Q28: What is the formula for the Subject Pairwise Diversity metric?
- **Spoken Viva Answer:** It is the average Jaccard distance across all pairs of books in the recommendation list based on their subject sets.
- **Deep Technical Explanation:**
  $$\text{Div} = \frac{1}{\binom{K}{2}} \sum_{i < j} \left(1 - \frac{|S_i \cap S_j|}{|S_i \cup S_j|}\right)$$
- **Exact Code Reference:** [`knowledge_graph/metrics.py:L8`](file:///d:/SDC/LibraryLLM/knowledge_graph/metrics.py#L8).
- **Likely Follow-Up:** What does a diversity score of 1.0 mean?
- **Qualification:** It indicates that no two recommended books share any common subjects.

### Q29: What is the Overlap@K metric in the recommender comparison?
- **Spoken Viva Answer:** It measures the percentage of common books returned in the top-K results of both the knowledge graph and baseline recommender.
- **Deep Technical Explanation:**
  $$\text{Overlap}@K = \frac{|A \cap B|}{\min(|A|, |B|)}$$
- **Exact Code Reference:** [`knowledge_graph/metrics.py:L17`](file:///d:/SDC/LibraryLLM/knowledge_graph/metrics.py#L17).
- **Likely Follow-Up:** Does higher overlap indicate higher quality?
- **Qualification:** No, overlap merely measures agreement; high diversity and low overlap show that the graph surfaces new relevant candidates.

### Q30: What is the formula for Maximal Marginal Relevance in Subsystem B?
- **Spoken Viva Answer:** MMR balances candidate relevance against maximum embedding similarity to already selected concepts using a penalty factor of 2.2.
- **Deep Technical Explanation:**
  $$\text{MMR}(c_i) = \text{Score}(c_i) - 2.2 \cdot \max_{c_j \in \text{Selected}} (\mathbf{v}_i \cdot \mathbf{v}_j)$$
- **Exact Code Reference:** [`rag/services/document_knowledge.py:L386`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L386).
- **Likely Follow-Up:** What embedding model produces vectors $\mathbf{v}_i$?
- **Qualification:** `all-MiniLM-L6-v2` producing normalized 384-dimensional dense vectors.

---

## CATEGORY 4: NLP & CONCEPT EXTRACTION (Q31 – Q45)

### Q31: How are description topics extracted from book summaries?
- **Spoken Viva Answer:** We extract adjacent bigrams and trigrams using Unicode tokenization, filter them against scikit-learn English stopwords, and rank candidates using degree-bounded TF-IDF scoring.
- **Deep Technical Explanation:** Adjacent bigrams and trigrams between 3 and 40 characters are scanned. Candidates must have in-corpus degree between 3 and $0.1\%$ of catalogue size. Top 5 non-overlapping phrases are selected.
- **Exact Code Reference:** [`knowledge_graph/topics.py:L20-L52`](file:///d:/SDC/LibraryLLM/knowledge_graph/topics.py#L20-L52).
- **Likely Follow-Up:** Does it extract single-word topics?
- **Qualification:** No, single words are too generic; extraction is strictly limited to bigrams and trigrams ($size \in \{2, 3\}$).

### Q32: What stop words are filtered out during topic mining?
- **Spoken Viva Answer:** All 318 words from scikit-learn's English stopword list, plus 24 bibliographic domain words such as "book", "story", "guide", "novel", "edition", "reader", and "isbn".
- **Deep Technical Explanation:**
  ```python
  STOP = frozenset(ENGLISH_STOP_WORDS) | {'book', 'books', 'story', 'guide', 'novel', 'edition', 'author', 'reader', 'volume', 'isbn', ...}
  ```
- **Exact Code Reference:** [`knowledge_graph/topics.py:L10-L12`](file:///d:/SDC/LibraryLLM/knowledge_graph/topics.py#L10-L12).
- **Likely Follow-Up:** Why filter words like "novel" or "edition"?
- **Qualification:** Because nearly all catalogue blurbs contain them, creating meaningless bridge connections.

### Q33: How does the system prevent overlapping topic phrases?
- **Spoken Viva Answer:** During ranking, it applies substring deduplication: if phrase A is a substring of an already selected phrase B, phrase A is discarded.
- **Deep Technical Explanation:** `if any(phrase in other or other in phrase for other in chosen): continue`.
- **Exact Code Reference:** [`knowledge_graph/topics.py:L47-L48`](file:///d:/SDC/LibraryLLM/knowledge_graph/topics.py#L47-L48).
- **Likely Follow-Up:** Give an example.
- **Qualification:** If "modern machine learning" is chosen, "machine learning" is skipped to prevent duplicate bridges.

### Q34: How are concepts extracted from uploaded PDF documents in Subsystem B?
- **Spoken Viva Answer:** Through a multi-source extraction pipeline matching copula definitions (`is defined as`, `refers to`), structural headings, bullet items, and multi-word recurring phrases.
- **Deep Technical Explanation:** Sentences matching regex `DEFINITION` are parsed into `subject`, `copula`, and `answer`. Structural headings in section contexts are scored. Candidates are weighted using 8 structural signals.
- **Exact Code Reference:** [`rag/services/document_knowledge.py:L225-L338`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L225-L338).
- **Likely Follow-Up:** What is the minimum score required to be accepted?
- **Qualification:** Candidates must achieve an evidence score of at least 4.1 (`score >= 4.1`).

### Q35: How are singular and plural concept forms deduplicated?
- **Spoken Viva Answer:** Using morphological stem normalization in `phrase_key`, which strips trailing 's' from words longer than 4 characters that do not end in 'ss'.
- **Deep Technical Explanation:**
  ```python
  def phrase_key(label):
      words = legacy.normalize(label.replace('-', ' ')).split()
      return ' '.join(w[:-1] if len(w) > 4 and w.endswith('s') and not w.endswith('ss') else w for w in words)
  ```
- **Exact Code Reference:** [`rag/services/document_knowledge.py:L31-L33`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L31-L33).
- **Likely Follow-Up:** Give an example.
- **Qualification:** "Neural networks" becomes "neural network", merging them into a single concept.

### Q36: How does the system filter low-value document sections?
- **Spoken Viva Answer:** Regular expressions match boilerplate sections like acknowledgments, preface, table of contents, references, and bibliography, excluding their sentences from concept extraction.
- **Deep Technical Explanation:** `LOW_SECTIONS = re.compile(r'^(?:acknowledg(?:e)?ments?|preface|table of contents|contents|references|bibliography|index)\b', re.I)`.
- **Exact Code Reference:** [`rag/services/document_knowledge.py:L17`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L17).
- **Likely Follow-Up:** What if a definition appears in the preface?
- **Qualification:** It is intentionally ignored to prioritize primary instructional body text.

### Q37: How does Subsystem B ensure extracted concepts have educational explanatory support?
- **Spoken Viva Answer:** Each candidate concept must link to a complete sentence satisfying strict quality rules, including sentence capitalization, verbal content, and minimum length.
- **Deep Technical Explanation:** `quality_text(text)` asserts: (1) length between 30 and 650 characters, (2) word count between 6 and 90, (3) ends with terminal punctuation, (4) contains a verb (`VERBAL.search(text)`), and (5) $\ge 52\%$ alphabetic characters.
- **Exact Code Reference:** [`rag/services/document_knowledge.py:L69-L79`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L69-L79).
- **Likely Follow-Up:** Why enforce verbal content?
- **Qualification:** It eliminates section titles, tables of numbers, and equation fragments from being selected as concept explanations.

### Q38: How does the system handle acronyms in concept extraction?
- **Spoken Viva Answer:** The explanation scorer matches parenthesized acronyms against sentence tokens to link abbreviations to their full definitions.
- **Deep Technical Explanation:** `acronym = re.search(r'\(([A-Z][A-Z0-9/-]{1,12})\)', label)`. If the acronym token appears in the sentence, the explanation score increases by $+3$.
- **Exact Code Reference:** [`rag/services/document_knowledge.py:L84-L87`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L84-L87).
- **Likely Follow-Up:** Does it resolve standalone acronyms without definitions?
- **Qualification:** No, unsupported acronyms without text evidence are penalized as fragments.

### Q39: What syntactic copulas are mapped to relationship predicates?
- **Spoken Viva Answer:** "is defined as", "refers to", and "means" map to `DEFINED_AS`; "consists of" maps to `CONTAINS`; "is used for" maps to `USED_FOR`; and "has step" maps to `HAS_STEP`.
- **Deep Technical Explanation:** Look up dictionary in `document_knowledge.py:L426-L430`. Statements with "is" or "are" that lack definition evidence map to `DESCRIBED_AS`.
- **Exact Code Reference:** [`rag/services/document_knowledge.py:L426-L434`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L426-L434).
- **Likely Follow-Up:** What confidence score is assigned to `DEFINED_AS` edges?
- **Qualification:** Definitional relations receive confidence 0.95; descriptive relations receive 0.78.

### Q40: How are process steps extracted for graph edges?
- **Spoken Viva Answer:** Bulleted list items following procedural action verbs like "send", "transmit", "wait", "check", or "store" are tagged with the `HAS_STEP` relationship.
- **Deep Technical Explanation:** Regex matching in `document_knowledge.py:L294-L295` detects actor and modal verb actions in list items.
- **Exact Code Reference:** [`rag/services/document_knowledge.py:L294-L295`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L294-L295).
- **Likely Follow-Up:** Where do these process edges appear?
- **Qualification:** In the Mind Map visualization and Flashcard study aids.

---

## CATEGORY 5: FRONTEND VISUALIZATION & USER INTERACTION (Q41 – Q55)

### Q41: How does the SVG canvas calculate node positions?
- **Spoken Viva Answer:** It calculates positions deterministically: the seed book is fixed at x=135; metadata features are centered at x=450; and recommended books are placed on the right at x=765.
- **Deep Technical Explanation:**
  - Seed: $(135, \text{height} / 2)$
  - Features: $(450, 45 + i \cdot \frac{\text{height} - 90}{\max(1, |F| - 1)})$
  - Recommended Books: $(765, 45 + j \cdot \frac{\text{height} - 90}{\max(1, |B| - 1)})$
- **Exact Code Reference:** [`frontend/src/components/MetadataGraphCanvas.tsx:L6`](file:///d:/SDC/LibraryLLM/frontend/src/components/MetadataGraphCanvas.tsx#L6).
- **Likely Follow-Up:** How is the canvas height determined?
- **Qualification:** $\text{height} = \max(460, |F| \cdot 45 + 70, |B| \cdot 55 + 70)$ to prevent vertical node overlap.

### Q42: How are edge curves rendered between columns?
- **Spoken Viva Answer:** Edges are rendered using SVG cubic Bezier curve paths, setting the control point X coordinates to the horizontal midpoint between the two nodes.
- **Deep Technical Explanation:** `d="M ax ay C ((ax+bx)/2) ay, ((ax+bx)/2) by, bx by"`. This generates an S-shaped horizontal curve that exits and enters node rectangles horizontally.
- **Exact Code Reference:** [`frontend/src/components/MetadataGraphCanvas.tsx:L9`](file:///d:/SDC/LibraryLLM/frontend/src/components/MetadataGraphCanvas.tsx#L9).
- **Likely Follow-Up:** Why not straight lines?
- **Qualification:** Straight lines cross through intermediate node rectangles, making the graph illegible.

### Q43: What happens when a user clicks on a node in the graph?
- **Spoken Viva Answer:** The canvas highlights all active reason paths connected to that node, dims unrelated edges to 25% opacity, and updates the side panel with entity details and connected neighbors.
- **Deep Technical Explanation:** `onSelect(node)` sets `selected` state. Edges satisfying `edge.source === selected.id || edge.target === selected.id` receive `strokeWidth = 3` and entity stroke color; non-focus edges receive `opacity = 0.25`.
- **Exact Code Reference:** [`frontend/src/components/MetadataGraphCanvas.tsx:L9-L10`](file:///d:/SDC/LibraryLLM/frontend/src/components/MetadataGraphCanvas.tsx#L9-L10) and [`KnowledgeGraphPage.tsx:L95`](file:///d:/SDC/LibraryLLM/frontend/src/pages/KnowledgeGraphPage.tsx#L95).
- **Likely Follow-Up:** Can a user pivot the graph to explore a recommended book?
- **Qualification:** Yes, clicking "Use as starting book" makes that book the new seed and fetches its 2-hop graph.

### Q44: What accessibility features are implemented in the graph canvas?
- **Spoken Viva Answer:** Full keyboard navigation (`Enter` and `Space` keys to select nodes), ARIA labels on all nodes, SVG `<title>` tooltips, and screen-reader polite live regions (`aria-live="polite"`).
- **Deep Technical Explanation:** Node elements render `<g role="button" tabIndex={0} aria-label="...">` with `onKeyDown` handlers. Screen-reader announcements report when graph recommendations finish loading.
- **Exact Code Reference:** [`frontend/src/components/MetadataGraphCanvas.tsx:L10`](file:///d:/SDC/LibraryLLM/frontend/src/components/MetadataGraphCanvas.tsx#L10) and [`KnowledgeGraphPage.tsx:L87`](file:///d:/SDC/LibraryLLM/frontend/src/pages/KnowledgeGraphPage.tsx#L87).
- **Likely Follow-Up:** How does a screen reader interpret the visual connections?
- **Qualification:** In `BookConnectionGraph.tsx`, a hidden SVG `<desc>` tag spells out the textual reason path.

### Q45: How does the zoom functionality work without a library?
- **Spoken Viva Answer:** Zooming scales the SVG's pixel dimensions (`width = 900 * zoom`, `height = height * zoom`) while maintaining the fixed `viewBox`, creating clean vector scaling bounded between 0.7x and 1.8x.
- **Deep Technical Explanation:** State `zoom` adjusts by $\pm 0.15$ on `ZoomIn`/`ZoomOut` button clicks. Clamped via `Math.max(0.7, zoom - 0.15)` and `Math.min(1.8, zoom + 0.15)`.
- **Exact Code Reference:** [`frontend/src/pages/KnowledgeGraphPage.tsx:L92`](file:///d:/SDC/LibraryLLM/frontend/src/pages/KnowledgeGraphPage.tsx#L92).
- **Likely Follow-Up:** Does zooming blur the text?
- **Qualification:** No, SVG is resolution-independent vector graphics.

---

## CATEGORY 6: SECURITY, EVALUATION, LIMITATIONS & VIVA DEFENSE (Q46 – Q65)

### Q46: How do you prevent unauthorized users from accessing private library graphs?
- **Spoken Viva Answer:** Every request validates JWT identity and checks institutional membership via `require_library_staff`. Non-members receive HTTP 403 Forbidden.
- **Deep Technical Explanation:** `catalogue.read_context(library_id, actor)` extracts the authenticated user's active membership and role in that institution, preventing cross-tenant access.
- **Exact Code Reference:** [`backend/services/library_intelligence_service.py:L146`](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_service.py#L146).
- **Likely Follow-Up:** What if a user knows the generation ID of another tenant's graph?
- **Qualification:** Generation lookups are scoped strictly by `library_id` in MongoDB; guessing IDs yields 404 Not Found.

### Q47: Can confidential document text leak into the public catalogue graph?
- **Spoken Viva Answer:** No. The public graph streams only public fields from MongoDB `books_collection`. Private documents uploaded by users are stored in distinct collections and never enter SQLite.
- **Deep Technical Explanation:** The build script projects only: `work_id`, `title`, `authors`, `subjects`. Unit test `test_full_graph_has_typed_deduplicated_edges_and_no_private_fields` confirms private notes are never stored.
- **Exact Code Reference:** [`tests/test_knowledge_graph.py:L29`](file:///d:/SDC/LibraryLLM/tests/test_knowledge_graph.py#L29).
- **Likely Follow-Up:** Does the graph expose which reader borrowed a book?
- **Qualification:** No, circulation history is only used server-side to exclude loans from the caller's own recommendations.

### Q48: What are the main limitations of the current implementation?
- **Spoken Viva Answer:** The three primary limitations are: lack of author entity disambiguation (names are strings, not human identities); rule-based relation extraction missing complex paraphrases; and absence of GraphRAG retrieval integration.
- **Deep Technical Explanation:**
  1. Author names are not resolved against VIAF/ORCID.
  2. Subsystem B relies on regex copulas rather than neural relation extraction.
  3. Graph structure does not augment vector context in RAG prompt generation.
- **Exact Code Reference:** [`15_LIMITATIONS_AND_FUTURE_IMPROVEMENTS.md`](file:///d:/SDC/docs/knowledge-graph-audit/15_LIMITATIONS_AND_FUTURE_IMPROVEMENTS.md).
- **Likely Follow-Up:** How would you resolve author ambiguities?
- **Qualification:** By mapping author strings to unique authority records (Wikidata QIDs or Library of Congress Name Authority).

### Q49: What is the difference between Subsystem A and Subsystem C?
- **Spoken Viva Answer:** Subsystem A is the global public catalogue graph stored in SQLite for all readers, while Subsystem C is a private, tenant-isolated graph stored as JSON disk artifacts for specific institutional library workspaces.
- **Deep Technical Explanation:** Subsystem A operates over public global books in `catalogue.sqlite`. Subsystem C operates over tenant inventory in `local-data/library-intelligence/{library_id}/` and includes classification nodes (Dewey Decimal).
- **Exact Code Reference:** [`01_KNOWLEDGE_GRAPH_OVERVIEW.md`](file:///d:/SDC/docs/knowledge-graph-audit/01_KNOWLEDGE_GRAPH_OVERVIEW.md).
- **Likely Follow-Up:** Do they share the same frontend component?
- **Qualification:** Yes, both utilize `MetadataGraphCanvas.tsx` for consistent visual rendering.

### Q50: How do you validate that the SQLite database is healthy before opening it?
- **Spoken Viva Answer:** During build, the script executes `PRAGMA integrity_check`, verifies foreign key constraints, and validates book counts before vacuuming into the final release file.
- **Deep Technical Explanation:** `assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'`. At runtime, `CatalogueGraph` opens the file with read-only URI mode and timeout guards.
- **Exact Code Reference:** [`scripts/build_kg_topics.py:L96`](file:///d:/SDC/LibraryLLM/scripts/build_kg_topics.py#L96).
- **Likely Follow-Up:** What happens if the database file is missing?
- **Qualification:** The API catches `FileNotFoundError` and returns HTTP 503 ("Catalogue graph is not ready").

### Q51: How does the system handle multi-author books?
- **Spoken Viva Answer:** Author strings separated by pipe delimiters are split into individual authors, canonicalized, and inserted as separate edge rows in the database.
- **Deep Technical Explanation:** `terms('Cormen | Leiserson | Rivest')` produces three distinct edge rows in `edges`. Each author forms an independent bridge path.
- **Exact Code Reference:** [`knowledge_graph/core.py:L17-L22`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L17-L22).
- **Likely Follow-Up:** What if the source metadata uses commas instead of pipes?
- **Qualification:** Normalization splits only pipe delimiters; commas are preserved so "Smith, Jane" is not split into two entities.

### Q52: What is the maximum number of recommendations returned?
- **Spoken Viva Answer:** Bounded between 1 and 50, defaulting to 10. The API strictly rejects any request outside this range with a 422 Unprocessable Entity error.
- **Deep Technical Explanation:** Pydantic validation: `limit: int = Field(default=10, ge=1, le=50)`. In `core.py`: `if not 1 <= limit <= 50: raise ValueError(...)`.
- **Exact Code Reference:** [`backend/routes/knowledge_graph.py:L30`](file:///d:/SDC/LibraryLLM/backend/routes/knowledge_graph.py#L30).
- **Likely Follow-Up:** Why cap recommendations at 50?
- **Qualification:** To maintain low serialization payloads and sub-10ms response times.

### Q53: Does the Knowledge Graph support multiple languages?
- **Spoken Viva Answer:** Unicode NFKC normalization and case-folding support international character sets, but topic stopword filtering and copula rules are currently optimized for English.
- **Deep Technical Explanation:** Unicode characters are fully supported in node labels and text hashes. However, `ENGLISH_STOP_WORDS` and regex patterns (`is defined as`) assume English grammar.
- **Exact Code Reference:** [`knowledge_graph/relations.py:L8`](file:///d:/SDC/LibraryLLM/knowledge_graph/relations.py#L8).
- **Likely Follow-Up:** How would you extend it to multilingual texts?
- **Qualification:** By incorporating language-specific stopword lexicons and multilingual dependency parsers (e.g., Stanza or UDPipe).

### Q54: What did you personally implement versus relying on external libraries?
- **Spoken Viva Answer:** I designed and implemented the entire graph architecture: the SQLite relational schema, the 2-hop cosine traversal SQL algorithm, the additive reason path mathematical formulation, the custom React SVG visualization canvas, and the API security guards. External libraries were restricted to standard utilities: SQLite for storage, scikit-learn for English stopwords, and FastAPI for routing.
- **Deep Technical Explanation:** No graph database (Neo4j) or graph visualization framework (D3, Cytoscape) was used. Every line of traversal logic, path contribution arithmetic, and SVG Bezier rendering is custom-crafted in the repository.
- **Exact Code Reference:** [`10_WORKED_EXAMPLE.md`](file:///d:/SDC/docs/knowledge-graph-audit/10_WORKED_EXAMPLE.md).
- **Likely Follow-Up:** Why avoid external visualization libraries?
- **Qualification:** To achieve microsecond rendering speeds, zero layout flicker, deterministic 3-column readability, and minimal bundle size.

### Q55: How does the system handle book descriptions with excessive length?
- **Spoken Viva Answer:** Description tokenization is hard-capped at 512 tokens, and descriptions shorter than 20 tokens are discarded as insufficient for topic mining.
- **Deep Technical Explanation:** `TOPIC_POLICY = {'min_description_tokens': 20, 'max_description_tokens': 512}`.
- **Exact Code Reference:** [`knowledge_graph/relations.py:L6-L7`](file:///d:/SDC/LibraryLLM/knowledge_graph/relations.py#L6-L7).
- **Likely Follow-Up:** Why discard descriptions under 20 tokens?
- **Qualification:** Short snippets lack sufficient topical context and generate noisy n-grams.

### Q56: What happens if an API client sends unexpected JSON fields in the request body?
- **Spoken Viva Answer:** The request is rejected immediately with HTTP 422 because Pydantic models are configured with strict extra forbidden settings (`extra='forbid'`).
- **Deep Technical Explanation:** `model_config = ConfigDict(extra='forbid')` prevents request parameter pollution or unexpected injection payloads.
- **Exact Code Reference:** [`backend/routes/knowledge_graph.py:L28`](file:///d:/SDC/LibraryLLM/backend/routes/knowledge_graph.py#L28).
- **Likely Follow-Up:** Does this prevent prototype pollution?
- **Qualification:** Yes, only explicitly declared schema fields are permitted.

### Q57: How does the system ensure fast page loads on mobile screens?
- **Spoken Viva Answer:** The SVG canvas is wrapped in an overflow-x auto container with touch-scrolling support, and the exploration layout is capped at 10 books.
- **Deep Technical Explanation:** The responsive layout wraps the canvas in `<div className="overflow-auto p-3">`, enabling horizontal pan scrolling on viewports under 900px.
- **Exact Code Reference:** [`frontend/src/pages/KnowledgeGraphPage.tsx:L93`](file:///d:/SDC/LibraryLLM/frontend/src/pages/KnowledgeGraphPage.tsx#L93).
- **Likely Follow-Up:** Does the layout switch to vertical on mobile?
- **Qualification:** In `BookConnectionGraph.tsx`, a vertical two-book bridge layout is used specifically for book detail pages.

### Q58: Can the graph recommend books across different genres?
- **Spoken Viva Answer:** Yes. Because books can be linked through authors or multidisciplinary topics, the graph can surface serendipitous connections between books in different primary subject classifications.
- **Deep Technical Explanation:** A computer science book and a philosophy book sharing the topic "logic" or "artificial intelligence" will be connected through that bridge node.
- **Exact Code Reference:** [`knowledge_graph/core.py:L84-L86`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L84-L86).
- **Likely Follow-Up:** How is this measured?
- **Qualification:** Via the Subject Pairwise Distance diversity metric in `knowledge_graph/metrics.py`.

### Q59: What is the memory footprint of the SQLite database in production?
- **Spoken Viva Answer:** The SQLite database is memory-mapped on demand by the OS page cache; with `PRAGMA cache_size = -131072`, it uses at most 128 MB of RAM.
- **Deep Technical Explanation:** In Python, opening SQLite with `mode=ro` does not load the entire database into process heap; pages are read on demand using OS virtual memory mapping.
- **Exact Code Reference:** [`knowledge_graph/core.py:L33`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L33).
- **Likely Follow-Up:** What if multiple threads access it simultaneously?
- **Qualification:** SQLite in read-only mode supports completely concurrent, lock-free reader threads.

### Q60: How would you evaluate the graph's recommendation quality against human ground truth?
- **Spoken Viva Answer:** By taking 50 seed books across 5 academic domains, collecting top-10 recommendations from the graph and vector recommender, and conducting a double-blind evaluation with domain experts measuring Precision@10, Mean Reciprocal Rank, and Reason Plausibility.
- **Deep Technical Explanation:** Experts score recommendations on a 3-point scale (Irrelevant, Weakly Related, Highly Relevant). Reason plausibility verifies whether the shared bridge accurately explains the connection.
- **Exact Code Reference:** [`09_PERFORMANCE_TESTING_AND_EVALUATION.md`](file:///d:/SDC/docs/knowledge-graph-audit/09_PERFORMANCE_TESTING_AND_EVALUATION.md).
- **Likely Follow-Up:** Why double-blind?
- **Qualification:** To eliminate evaluator bias toward vector embeddings or graph representations.

### Q61: What is the purpose of the comparison endpoint (`/experimental/kg/compare`)?
- **Spoken Viva Answer:** It runs the graph recommender and the existing vector recommender simultaneously on the same seed book, returning overlap metrics and subject diversity scores for live comparative evaluation.
- **Deep Technical Explanation:** It queries `http://127.0.0.1:8004/recommendations/from-book` and computes `compare(existing, kg)` from `knowledge_graph/metrics.py`.
- **Exact Code Reference:** [`backend/routes/knowledge_graph.py:L106-L117`](file:///d:/SDC/LibraryLLM/backend/routes/knowledge_graph.py#L106-L117).
- **Likely Follow-Up:** What if the existing recommender service is down?
- **Qualification:** The endpoint catches request exceptions and returns HTTP 503 with a clean failure notice.

### Q62: Why are reason paths capped at 3 per book in the visual graph?
- **Spoken Viva Answer:** Showing more than 3 reason paths per book clutters the visual canvas with overlapping curves. All shared features contribute to the score, but only the top 3 are rendered for visual clarity.
- **Deep Technical Explanation:** `exploration(..., max_reasons=3)`. The full list of reason paths and provenance is still accessible via the `<details>` dropdown in the UI.
- **Exact Code Reference:** [`knowledge_graph/core.py:L108`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L108).
- **Likely Follow-Up:** Can a user inspect the discarded paths?
- **Qualification:** Yes, clicking "All reason paths and catalogue evidence" expands the full list.

### Q63: How are SVG node rectangles sized to fit entity labels?
- **Spoken Viva Answer:** Node rectangles have a fixed width of 230 pixels and height of 34 pixels; labels exceeding 32 characters are cleanly truncated with an ellipsis.
- **Deep Technical Explanation:** `<text>{node.label.length > 32 ? node.label.slice(0, 31) + '…' : node.label}</text>`. The full untruncated text is available in the SVG `<title>` element.
- **Exact Code Reference:** [`frontend/src/components/MetadataGraphCanvas.tsx:L10`](file:///d:/SDC/LibraryLLM/frontend/src/components/MetadataGraphCanvas.tsx#L10).
- **Likely Follow-Up:** Does truncation affect node matching?
- **Qualification:** No, node IDs and backend queries retain full string fidelity.

### Q64: What is the purpose of the `BookConnectionGraph` component?
- **Spoken Viva Answer:** It is a compact vertical bridge component rendered directly on individual book detail pages, illustrating exactly why a related book is recommended.
- **Deep Technical Explanation:** Seed book is rendered at the top, related book at the bottom, and shared feature pills stacked vertically in the center, connected by vertical Bezier arcs.
- **Exact Code Reference:** [`frontend/src/components/BookConnectionGraph.tsx:L9-L52`](file:///d:/SDC/LibraryLLM/frontend/src/components/BookConnectionGraph.tsx#L9-L52).
- **Likely Follow-Up:** How does the user navigate from this widget to the full graph?
- **Qualification:** It includes an interactive link: "Explore this book in Graph Lab →".

### Q65: If you had another month to work on this feature, what is the single most important improvement you would implement?
- **Spoken Viva Answer:** I would implement true GraphRAG by incorporating graph community summaries into LuminaR's vector retrieval pipeline, allowing the LLM to synthesize holistic answers across clusters of related books.
- **Deep Technical Explanation:** Run Leiden community detection over the bipartite graph, generate hierarchical cluster summaries with LLMs, and index both chunks and community summaries in the vector store to support global sense-making questions.
- **Exact Code Reference:** [`15_LIMITATIONS_AND_FUTURE_IMPROVEMENTS.md`](file:///d:/SDC/docs/knowledge-graph-audit/15_LIMITATIONS_AND_FUTURE_IMPROVEMENTS.md).
- **Likely Follow-Up:** How would this impact query latency?
- **Qualification:** It would increase indexing time, but retrieval latency would remain comparable to standard hybrid RAG.
