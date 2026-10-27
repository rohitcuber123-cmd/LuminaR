# 08 — RAG INTEGRATION & MULTI-TENANT SECURITY AUDIT

## 1. RAG Integration Reality Check: Is GraphRAG Implemented?

A critical requirement of academic and technical code audits is preventing false claims of advanced capabilities. During university reviews, students are often tempted to claim: *"We implemented GraphRAG."*

**Code-Verified Finding: GraphRAG is NOT implemented in LuminaR.**

### 1.1 Architectural Comparison

| Architectural Dimension | Traditional RAG | GraphRAG (e.g., Microsoft GraphRAG) | LuminaR Verified Architecture |
|---|---|---|---|
| **Graph Construction** | None | LLM extracts entity-relationship triples from text chunks | Deterministic regex copulas & TF-IDF metadata |
| **Retrieval Mechanism** | Dense vector similarity & BM25 sparse keyword search | Graph traversal / community summary retrieval + vector search | Dense vector similarity & BM25 hybrid search |
| **Context Generation** | Retrieved text chunks concatenated into prompt | Graph subgraphs, communities, and entity triples concatenated into prompt | Retrieved text chunks only (`rag/services/retrieval.py`) |
| **LLM Participation** | Generates final answer from text chunks | Extracts triples + generates answers | Generates final answer from text chunks only |
| **Graph Purpose** | N/A | Core retrieval & reasoning component | Visual navigation, recommendation explainability, study aids |

---

### 1.2 Code Evidence from the Ingestion & Retrieval Pipelines

1. **Retrieval Pipeline Inspection:**
   In [`rag/services/retrieval.py`](file:///d:/SDC/LibraryLLM/rag/services/retrieval.py), retrieval executes purely through dense vector stores (FAISS/Chroma/Milvus) and BM25 token matching. The graph databases (`catalogue.sqlite` or `graph.json`) are **never imported or queried during chat question answering**.
2. **LLM Invocation Proof:**
   In [`rag/services/document_knowledge.py:L445`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L445), the metrics returned by the knowledge extraction engine explicitly state:
   ```python
   metrics.update({
       'qwen_calls': 0,
       'knowledge_model_ms': round((time.perf_counter() - started) * 1000, 2)
   })
   ```
   Zero LLM calls are made to construct nodes, edges, or concepts.
3. **Coexistence Without Dependency:**
   In LuminaR, the Knowledge Graph and RAG subsystems **coexist as parallel, complementary features**:
   - RAG answers targeted reader questions based on semantic chunk retrieval.
   - The Knowledge Graph visualizes high-level conceptual maps and bibliographical bridges, allowing readers to explore the library independently of asking a question.

---

## 2. Security Boundaries & Private Library Isolation

Graph subsystems in multi-tenant environments face severe security risks: cross-user data leakage, unauthorized traversal across private libraries, and leaking confidential document content.

### 2.1 Subsystem A: Reader Personalization & Loan Exclusions

In the global catalogue graph, recommendations are personalized and protected against privacy leaks:

```python
# backend/routes/knowledge_graph.py:L37-L41
def exclusions(user):
    uid = int(user['sub'])
    issued = issues_collection.find({'user_id': uid, 'status': 'ISSUED'}, {'_id': 0, 'work_id': 1})
    reserved = reservations_collection.find({'user_id': uid, 'status': {'$in': ['ACTIVE', 'READY_FOR_PICKUP']}}, {'_id': 0, 'work_id': 1})
    return {r['work_id'] for r in [*issued, *reserved] if r.get('work_id')}
```

1. **Authentication Guard:** Every endpoint requires a valid JWT bearer token (`identity = current_identity(user)`).
2. **Loan Exclusion Filter:** Books currently borrowed or reserved by the signed-in reader are automatically excluded from the recommendation candidates (`result['recommendations']`), ensuring users are not recommended books already on their shelf.
3. **No Private Field Exposure:** The SQLite build script projects only public catalogue fields (`title`, `authors`, `subjects`). Private librarian notes, borrower histories, and circulation records are strictly excluded during ingestion ([`tests/test_knowledge_graph.py:L29`](file:///d:/SDC/LibraryLLM/tests/test_knowledge_graph.py#L29)).

---

### 2.2 Subsystem C: Multi-Tenant Isolation & Path Traversal Guards

The tenant intelligence graph operates under strict cryptographic and filesystem multi-tenancy ([`backend/services/library_intelligence_artifacts.py`](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_artifacts.py)):

1. **Filesystem Canonicalization & Path Traversal Defense:**
   To prevent directory traversal attacks (e.g., `../../etc/passwd`), every path is verified against its canonical resolution:
   ```python
   # backend/services/library_intelligence_artifacts.py:L23
   if path.resolve() != path:
       raise HTTPException(404, 'Artifact namespace is invalid.')
   ```
2. **Cryptographic Integrity Validation:**
   Every tenant graph artifact (`graph.json`) is accompanied by an immutable `manifest.json`. Before serving, LuminaR verifies the SHA-256 digest of every file against the signed manifest:
   ```python
   # backend/services/library_intelligence_artifacts.py:L89
   if file.resolve() != file or file.stat().st_size > MAX_ARTIFACT_BYTES or store.checksum(file) != expected:
       raise ValueError()
   ```
3. **Database Ownership Verification:**
   Before a graph is returned to an institutional user, the system verifies that every book ID in the graph is strictly owned by that tenant:
   ```python
   # backend/services/library_intelligence_artifacts.py:L99-L100
   owned = {r['library_book_id'] for r in store.collection('library_books').find({'library_id': library_id, 'library_book_id': {'$in': list(ids)}}, {'library_book_id': 1})}
   if ids != owned:
       raise ValueError()
   ```
4. **Role-Based Scoping & Membership Verification:**
   In [`backend/services/library_intelligence_service.py:L146-L153`](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_service.py#L146-L153), requests are validated using `catalogue.read_context(library_id, actor, staff=staff)`. The graph is dynamically filtered so that only books visible under the user's specific membership permissions are included in the returned payload.
