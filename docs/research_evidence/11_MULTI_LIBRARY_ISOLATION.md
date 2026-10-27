# 11_MULTI_LIBRARY_ISOLATION.md: Backend Tenant Isolation Audit & Security Analysis

## Executive Summary

This document audits backend tenant isolation across all thirteen functional subsystems of LuminaR. 

The central finding of this audit is that **LuminaR operates an architectural dichotomy**:
1. **Institutional V2 Subsystem:** Enforces strict cryptographic and role-based tenant isolation in backend dependencies (`backend/institution_dependencies.py`). Changing `library_id` in a request URL yields an immediate HTTP 404 or 403.
2. **Global V1 Subsystem:** Legacy endpoints (`/search`, `/recommendations`, `/rag/ask`, `/kg`, `/books`, `/events`) operate on a single shared OpenLibrary database and a shared 5-million-vector FAISS HNSW index, with **no mandatory library tenancy** or only optional post-retrieval filtering.

---

## 1. Subsystem Isolation Matrix

| Subsystem | Library Scoped? | Where Enforced? | Frontend Enforced? | Backend Enforced? | Possible Leakage Risk / Security Assessment |
| :--- | :---: | :--- | :---: | :---: | :--- |
| **Catalogue Browsing** | **YES** (Tenant route)<br>**NO** (Global route) | `backend/services/library_catalogue_experience.py:31` | Yes | **YES** (`require_library_membership`) | **Zero risk on `/libraries/{id}/catalogue`**: returns 404 if user lacks active membership. **High risk if using `/books`**: exposes global OpenLibrary data. |
| **Normal Search (Lexical / BM25)** | **PARTIAL** | `search/api.py:250`, `search/ranked_pages.py:31` | Yes | **PARTIAL** (Optional filter) | **LEAKAGE RISK:** `GET /search?library_id=XYZ&available_at_library=true` does NOT verify caller membership in library `XYZ`. An unauthenticated outsider can probe inventory stock of private libraries. |
| **Semantic Search (Dense Vector)** | **NO** | `search/luminar_search.py:770` | No | **NO** | **NO ISOLATION:** FAISS index is 100% global (5M vectors). Dense candidates are retrieved globally; library filtering is applied as an in-memory post-filter on candidate ranks. |
| **Recommendations** | **YES** (Tenant route)<br>**NO** (Global route) | `backend/services/library_catalogue_experience.py:221` | Yes | **YES** (`require_library_membership`) | **Zero risk on tenant endpoint**: intersects candidates with `institution_library_books`. Legacy `/recommendations` endpoint is completely unpartitioned. |
| **RAG (Question Answering)** | **YES** (Asset route)<br>**NO** (Global route) | `rag/services/library_asset_routes.py:41` | Yes | **YES** (`authorize_asset`) | **Zero risk on `/libraries/{id}/assets/{asset_id}/ask`**: strictly verifies tenant ownership. Global `/rag/ask` has no concept of library tenancy. |
| **Knowledge Graph** | **NO** | `backend/routes/knowledge_graph.py` | No | **NO** | **NO ISOLATION:** Operates strictly on global OpenLibrary `work_id`. Topic clusters and book relationships cannot be partitioned by library. |
| **Events Management** | **YES** (Tenant route)<br>**NO** (Global route) | `backend/services/library_event_service.py` | Yes | **YES** (`require_library_membership`, `require_library_staff`) | **Zero risk on tenant route**: events stored in `institution_events`. Legacy `/events` route exposes platform-wide events. |
| **Borrow / Checkouts** | **YES** | `backend/services/library_lending_service.py` | Yes | **YES** (`require_library_patron`, `library_mutation`) | **Zero risk on tenant route**: verifies active membership, available copies in `institution_copies`, and writes to `institution_loans`. |
| **Return** | **YES** | `backend/services/library_lending_service.py` | Yes | **YES** (`require_library_staff`) | **Zero risk**: only authorized staff of that specific `library_id` can process loan returns. |
| **Reserve / Hold** | **YES** | `backend/services/library_v2c_reservations.py` | Yes | **YES** (`require_library_patron`) | **Zero risk**: verifies waitlist status and records to `institution_reservations` with strict `library_id` scoping. |
| **Circulation History** | **YES** | `backend/routes/library_lending.py:57` | Yes | **YES** (`user_id` + `library_id`) | **Zero risk**: queries `institution_loans` filtered by composite key `{'library_id': library_id, 'user_id': user_id}`. |
| **Admin & Staff Controls** | **YES** | `backend/institution_dependencies.py:64` | Yes | **YES** (`require_library_owner`, `require_library_staff`) | **Zero risk**: access code rotation, staff invitation, and membership changes require validated tenant staff role. |
| **Analytics Dashboard** | **YES** | `backend/routes/library_analytics.py:15` | Yes | **YES** (`require_library_staff`) | **Zero risk**: strictly returns aggregated statistics for the specified `library_id`; outsiders receive HTTP 404. |

---

## 2. In-Depth Security Analysis: Manual Parameter Tampering

### Scenario: Attacker Manually Modifies `library_id` in API Requests

#### Attack Vector A: Attacker targets `/libraries/{victim_library_id}/catalogue/home`
1. Attacker obtains a valid JWT token as a registered user of Library A.
2. Attacker crafts an HTTP request substituting `library_id = "victim-uuid"` (a private corporate library).
3. **Backend Execution:**
   ```python
   # LibraryLLM/backend/institution_dependencies.py:18-44
   library, membership = resolve_library_membership(victim_library_id, current_user)
   if not membership:
       raise HTTPException(404, 'Library resource not found.')
   ```
4. **Result: SECURE.** Because the attacker's `user_id` does not possess an active record in `institution_memberships` for `victim-uuid`, the server returns HTTP 404 ("Library resource not found"), intentionally hiding even the existence of the private library's catalog.

#### Attack Vector B: Attacker targets `/search?query=patent&library_id={victim_library_id}&available_at_library=true`
1. Attacker calls the standalone Search API on port 8003.
2. Attacker provides a private library's UUID in the query string.
3. **Backend Execution:**
   ```python
   # LibraryLLM/search/api.py:274 & search/luminar_search.py:770
   if library_id and available_at_library:
       results = [r for r in results if r["library_available"] and r["available_physical_copies"] > 0]
   ```
4. Search API queries `library_inventory` in MongoDB to check if the book is stocked.
5. **Result: LEAKAGE VULNERABILITY.** The standalone Search API (`search/api.py`) does **NOT** import `institution_dependencies.py` and does **NOT** validate whether the caller is an authorized member of `victim_library_id`. An attacker can systematically enumerate ISBNs/work IDs to determine the physical inventory of a private library.

#### Attack Vector C: Attacker targets `/libraries/{victim_library_id}/assets/{asset_id}/ask`
1. Attacker submits a confidential document QA question to a private library's asset.
2. **Backend Execution:**
   ```python
   # LibraryLLM/rag/services/library_asset_pipeline.py:228
   row = self.repository.authorize_asset(library_id, asset_id, actor, ready=True)
   ```
   * `authorize_asset` executes `require_library_membership(library_id, actor)`.
   * Verifies `asset['library_id'] == library_id`.
   * For staff-only documents, verifies `membership['role'] in ('ADMIN', 'LIBRARIAN')`.
3. **Result: SECURE.** Access is blocked at the tenant membership gate.

---

## 3. Summary of Isolation Architecture

1. **Transactional Boundaries:** Institutional mutations in MongoDB are wrapped with file-based locking (`with library_mutation(library_id):`), preventing cross-tenant race conditions.
2. **Multi-Tenant Scoping:** Tenant queries always inject `{'library_id': library_id}` directly into MongoDB aggregation pipelines and find filters.
3. **Search Decoupling Gap:** The search and indexing service (`search/luminar_search.py`) remains historically global and treats `library_id` as an unauthenticated metadata filter rather than a secure tenant partition.
