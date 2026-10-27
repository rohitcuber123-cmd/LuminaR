# 15 — RESEARCH PAPER TECHNICAL SUMMARY: MULTI-TENANT PRIVACY & DATA ISOLATION

*This document provides formal academic technical documentation of LuminaR's private library multi-tenancy and data isolation subsystem, structured for integration into an IEEE/ACM-format research paper.*

---

## Abstract

Modern digital libraries increasingly integrate neural retrieval and large language models (LLMs) to enhance document discovery and research workflows. However, deploying Retrieval-Augmented Generation (RAG) and dense semantic search across multiple autonomous institutions introduces severe privacy, security, and data leakage challenges. Conventional multi-tenant vector retrieval designs rely on post-retrieval metadata filtering over a shared monolithic vector index, exposing tenants to recall starvation, timing side-channels, and context contamination during reranking and generative inference. 

This paper presents the architectural design and implementation of LuminaR, an intelligent digital library platform featuring a privacy-preserving hybrid multi-tenancy architecture. Relational bibliographic data and physical circulation state machines are partitioned within shared MongoDB collections using programmatic repository scoping and compound unique indexes, while unstructured document assets and vector retrieval spaces are strictly partitioned into dedicated filesystem namespaces and isolated FAISS indexes per institutional tenant. For document-level RAG, we introduce an ephemeral runtime swapping pattern that dynamically binds an isolated vector index to the retriever under process-wide mutual exclusion, performs double authorization rechecks before and after generative inference, and scrubs all in-memory vector representations in a guaranteed cleanup routine. Experimental test audits confirm that cross-tenant document requests, foreign candidate retrieval, and citation spoofing are strictly rejected with zero observed cross-tenant data leakage.

---

## 1. Introduction & Problem Formulation

Digital libraries serving educational and research institutions operate under strict data sovereignty, privacy, and regulatory constraints (e.g., FERPA, GDPR). While public catalogue discovery benefits from shared bibliographic metadata, institutional holdings, private research pre-prints, circulation histories, and fee records must remain strictly isolated.

When integrating neural search and generative AI into such platforms, system designers encounter three core security dilemmas:

1. **The Shared Vector Space Dilemma (Recall Starvation)**: Dense retrieval relies on Approximate Nearest Neighbor (ANN) graphs (e.g., HNSW, FAISS). In a naive multi-tenant implementation, all tenants' embeddings reside in a single index. A query computes vector similarities globally, retrieving the top-$K$ candidates, followed by post-filtering by `tenant_id`. If another tenant's documents dominate the top-$K$ cluster, the querying tenant suffers from *recall starvation*, receiving null or degraded results even when relevant documents exist at ranks $K+1$.
2. **Context Contamination in Generative Inference**: When an LLM processes user queries augmented with retrieved document chunks, lingering in-memory chunk references from previous tenant requests risk context contamination or accidental disclosure through generative hallucination.
3. **Decoupling Identity from Authority**: Stateless authentication tokens (e.g., JWT) that embed tenant role claims become stale upon role revocation, leaving a vulnerability window until token expiry.

LuminaR addresses these challenges by introducing a hybrid multi-tenancy framework that decouples identity from authority, guarantees dedicated per-tenant vector spaces, and sandboxes generative inference at the process level.

---

## 2. Architectural Design

```
   ┌──────────────────────────────────────────────────────────────────┐
   │                     FASTAPI ROUTING GATEWAY                      │
   │  [JWT Validation] ──> [Dynamic DB Membership Check] ──> [404]   │
   └───────────────────────────────┬──────────────────────────────────┘
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
┌─────────────────────────────────┐         ┌─────────────────────────────────┐
│     STRUCTURED RELATIONAL       │         │    DENSE VECTOR & UNSTRUCTURED  │
│          DATA TIER              │         │           AI TIER               │
├─────────────────────────────────┤         ├─────────────────────────────────┤
│ • MongoDB (library_database)    │         │ • Dedicated Filesystem Sandbox  │
│ • Prefixed: institution_*       │         │   local-data/library-assets/{id}│
│ • TenantInventory Scope Wrapper │         │ • Dedicated FAISS Index Files   │
│ • Compound Unique Indexes       │         │   len(index) == len(tenant_docs)│
│ • Durable library_mutation Lock │         │ • Ephemeral RAG Runtime Swapping│
└─────────────────────────────────┘         └─────────────────────────────────┘
```

LuminaR establishes a structural division between structured transactional state and unstructured vector intelligence:

### 2.1 The Dynamic Per-Request Authorization Boundary
Let $\mathcal{U}$ be the set of platform users, $\mathcal{L}$ be the set of registered libraries, and $\mathcal{M} \subset \mathcal{U} \times \mathcal{L} \times \mathcal{R} \times \mathcal{S}$ be the set of active institutional memberships, where $\mathcal{R} \in \{\text{ADMIN}, \text{LIBRARIAN}, \text{GENERAL\_USER}\}$ and $\mathcal{S} \in \{\text{ACTIVE}, \text{SUSPENDED}, \text{REMOVED}\}$.

Authentication produces a signed JWT embedding solely the account identity $u \in \mathcal{U}$ and a unique session identifier $s \in \mathcal{S}_{\text{id}}$. On every incoming request targeting library $\ell \in \mathcal{L}$, the dependency layer executes:
$$f_{\text{auth}}(u, s, \ell) = \begin{cases} 
\text{Allow}(u, \ell, r), & \text{if } s \notin \text{Revoked} \land (u, \ell, r, \text{ACTIVE}) \in \mathcal{M} \\
\text{Reject}(404), & \text{otherwise}
\end{cases}$$
By returning HTTP 404 rather than HTTP 403 when $(u, \ell) \notin \mathcal{M}$, the system enforces *Information Concealment*, preventing unauthorized callers from confirming the existence of protected institutions.

### 2.2 Relational Tier: Logical Scoping via `TenantInventory`
Within MongoDB, collections are prefixed with `institution_*`. All read, write, count, and update queries targeting inventory records pass through a repository wrapper:
$$\mathcal{Q}_{\text{scoped}}(q, \ell) = q \cup \{\text{library\_id}: \ell\}$$
If an incoming query filter contains a mismatched library identifier ($\exists \ell' \in q \mid \ell' \neq \ell$), the wrapper raises a structural error (`ValueError`), preventing cross-tenant predicate injection. Compound unique indexes enforce uniqueness within the tenant namespace:
$$\text{Unique}(\text{library\_id}, \text{accession\_number}), \quad \text{Unique}(\text{library\_id}, \text{barcode})$$

---

## 3. Dedicated Semantic Vector Index Isolation

### 3.1 Mathematical Formulation of Search Isolation
Let $\mathcal{D}_\ell = \{d_1, d_2, \dots, d_{N_\ell}\}$ represent the bibliographic corpus of library $\ell$. The text of each book $d_i$ is mapped to a normalized dense embedding using a bi-encoder $E(\cdot)$:
$$\mathbf{v}_i = \frac{E(d_i)}{\|E(d_i)\|_2} \in \mathbb{R}^{384}$$
Rather than inserting $\mathbf{v}_i$ into a global index $\mathcal{I}_{\text{global}}$, LuminaR compiles a dedicated index $\mathcal{I}_\ell$ serialized to disk at:
$$\text{Path}(\mathcal{I}_\ell) = \text{local-data/library-intelligence/}\ell\text{/search/}\text{gen\_id/index.faiss}$$
Given a user query $q$, the query vector $\mathbf{q} = \frac{E(q)}{\|E(q)\|_2}$ is evaluated strictly over $\mathcal{I}_\ell$:
$$\mathcal{C}_\ell = \operatorname*{arg\,top\,K}_{i \in \{1, \dots, N_\ell\}} (\mathbf{q} \cdot \mathbf{v}_i)$$
Because $|\mathcal{I}_\ell| = N_\ell$, $100\%$ of candidate representations in $\mathcal{C}_\ell$ originate from library $\ell$. CrossEncoder reranking scores $S_{\text{CE}}(q, d_i)$ are subsequently computed exclusively over pairs $(q, d_i)$ where $d_i \in \mathcal{C}_\ell$.

### 3.2 Fingerprint Drift & Stale Fallback
To prevent stale vector retrieval after catalog modifications, the system computes a cryptographic dataset fingerprint:
$$\Phi(\mathcal{D}_\ell) = \text{SHA-256}\left(\operatorname{Sort}(\{\operatorname{Normalize}(d) \mid d \in \mathcal{D}_\ell\})\right)$$
If $\Phi(\mathcal{D}_\ell) \neq \Phi_{\text{manifest}}$, the semantic retrieval pipeline falls back gracefully to real-time database lexical search (`LOCAL_FALLBACK`), guaranteeing that withdrawn or modified records are never returned from stale vector indexes.

---

## 4. Ephemeral RAG Runtime Swapping

For unstructured PDF and document question-answering, LuminaR enforces sandbox isolation on the in-memory retriever runtime:

```
[Request] ──> Acquire(inference_lock)
                  │
                  ├── clear_runtime() [Wipes doc_index, metadata, texts]
                  ├── Read runtime.faiss from local-data/library-assets/{id}/{asset_id}/
                  ├── Populate retriever: doc_ids = {asset_id}
                  ├── recheck_authority(pre-inference)
                  ├── Local LLM Inference: Qwen2.5-3B-Instruct
                  ├── recheck_authority(post-inference)
                  ├── Validate Citations: for chunk in sources: chunk in manifest
                  │
                  └── finally: clear_runtime() [Mandatory Memory Zeroing]
```

### 4.1 Security Properties of the RAG Pipeline
1. **Zero Lingering State**: The `clear_runtime()` subroutine nullifies `retriever.doc_index`, `retriever.doc_metadata`, and `retriever.doc_chunk_texts` both immediately before index loading and in an unconditional `finally:` block.
2. **Mitigation of TOCTOU Exploitation**: The `recheck(row, actor)` function is invoked prior to LLM forward-pass and immediately post-generation, preventing Time-of-Check to Time-of-Use race conditions if a user's membership is revoked while the model is decoding tokens.
3. **Citation Authenticity Invariant**: The pipeline verifies that:
   $$\forall s \in \text{Sources}(\text{Output}), \quad s \in \text{Manifest}(\text{Document})$$
   Any citation mismatch aborts the response with HTTP 409 Conflict.
4. **Defense Against Prompt Exfiltration**: Even in the presence of adversarial indirect prompt injection embedded within an uploaded PDF, the retriever runtime contains only chunks from that single document. The model lacks access to any foreign tenant vectors or external tool execution environments.

---

## 5. Implementation Verification & Empirical Testing

The security architecture was evaluated across an integration test suite comprising 8 test modules (`tests/institution_v1` through `tests/institution_v2h`). Key empirical findings include:

| Test Scenario | Test Implementation | Verified Behavior |
|---|---|---|
| **Cross-Tenant Asset Access** | `test_cross_tenant_asset_uuid_denied` | Client presenting valid asset UUID belonging to Library B via Library A route receives HTTP 404. |
| **Foreign Book Exclusion** | `test_dataset_generation_scope_and_no_foreign_books` | Index generation for Library A over co-existing libraries contains strictly $|d \in \text{Lib A}|$; zero foreign titles present. |
| **Identical File Namespace Isolation** | `test_identical_cross_library_checksum_namespace_is_separate` | Identical PDF (same SHA-256) uploaded to two libraries receives disjoint UUIDs, disjoint filesystem paths, and zero duplicate collision. |
| **Circulation Concurrency Races** | `test_return_confirm_race_and_renew_return_race` | 6 concurrent threads executing return and renewal operations reconcile holding availability with zero double-allocation. |
| **Platform Admin Denial** | `test_controls.py:test_intelligence_status_authority` | User holding global `PLATFORM_ADMIN` role without explicit tenant membership receives HTTP 404 on tenant endpoints. |

---

## 6. Resource Efficiency Considerations

A common objection to per-tenant vector indexing is memory overhead. We analyze the theoretical memory footprint for a dense 384-dimensional index:
- Precision: IEEE 754 single-precision float (4 bytes).
- Vector size: $384 \times 4 = 1,536 \text{ bytes}$.
- Memory for a collection of $10,000$ documents:
  $$M = 10,000 \times 1.536 \text{ KB} \approx 15.36 \text{ MB}$$
Because each tenant index requires merely ~15 MiB of RAM, an LRU cache capping resident memory at 2 active indexes (`max_entries = 2`) ensures that total application RAM consumption remains bounded by $\mathcal{O}(1)$ relative to total registered institutions.

---

## 7. Limitations & Future Work

While LuminaR achieves comprehensive logical and AI data isolation, current architectural limitations include:
1. **Single-Node Global Inference Lock**: RAG requests are serialized under `engine.inference_lock` during local LLM decoding. Multi-tenant throughput under high concurrent load requires horizontal model serving (e.g., continuous batching with tenant queue tagging).
2. **Transport & Volume Encryption**: Transport TLS termination and database encryption-at-rest rely on underlying deployment infrastructure (reverse proxies and encrypted block storage) rather than native application-level encryption.
3. **Identity Federation**: The system currently relies on local email/password registration; integration with institutional SAML 2.0 / Shibboleth identity providers is planned for enterprise production deployment.

---

## 8. Conclusion

LuminaR demonstrates that intelligent digital library systems can provide advanced semantic search, generative RAG, and automated knowledge tooling without sacrificing institutional multi-tenancy boundaries. By combining logical database scoping via `TenantInventory`, dedicated per-library FAISS indexes, and ephemeral runtime memory zeroing, the platform establishes a verified, defense-in-depth security model that eliminates cross-tenant data leakage by design.
