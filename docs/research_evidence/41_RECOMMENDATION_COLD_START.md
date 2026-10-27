# Recommendation & Discovery Cold-Start Behavior

## 1. Executive Summary

Cold start in LuminaR is handled through a combination of **heuristic fallbacks, deterministic recency sorting, and tenant catalog intersection**. Because LuminaR does not rely on a trained matrix-factorization collaborative filtering model, cold start does not cause runtime mathematical singularities or retraining blockers. However, the system exhibits distinct, explicit failure and fallback modes depending on whether the cold entity is a **new user**, a **new book**, or a **new participating library**.

---

## 2. Cold-Start Taxonomy in LuminaR

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           LUMINAR COLD-START MODES                              │
├─────────────────────────┬──────────────────────────┬────────────────────────────┤
│        NEW USER         │         NEW BOOK         │        NEW LIBRARY         │
├─────────────────────────┼──────────────────────────┼────────────────────────────┤
│ • Zero search queries   │ • Global Catalog Book    │ • Zero inventory holdings  │
│ • Zero loan history     │   - Vector index miss    │ • State = GLOBAL_FALLBACK  │
│ • Zero reservation logs │   - KG snapshot miss/404 │ • Recommendations = []     │
│ • Zero feedback events  │ • Tenant Library Book    │ • Home rails = []          │
│ ─────────────────────── │   - Top of New Arrivals  │ ────────────────────────── │
│ Global Service: []      │   - Backfill candidate   │ Transitions to Local once  │
│ Tenant Layer: Arrivals  │   - Popularity = 0       │ first book is accessioned  │
└─────────────────────────┴──────────────────────────┴────────────────────────────┘
```

---

## 3. New User Cold Start

### 3.1 Trace in Global Recommendation Microservice (`:8004`)
When a newly registered patron (`user_id`) calls `GET /recommendations`:
1. `build_user_profile(user_id)` executes:
   - `search_history = []` $\to$ `queries = []`, `search_interests = []`
   - `issues = []` $\to$ `borrowed_subjects = Counter()`, `borrowed_authors = Counter()`
   - `reservations = []` $\to$ `reserved_subjects = Counter()`, `reserved_authors = Counter()`
   - `feedbacks = []` $\to$ `feedback = []`, `feedback_work_scores = {}`
   - Exclusions: `active_issue_work_ids = set()`, `active_reservation_work_ids = set()`
2. `generate_semantic_candidates()` check:
   ```python
   if not queries:
       print("[Recommendation] No queries available, skipping semantic search")
       return []
   ```
3. **Outcome**: The global recommendation microservice returns an empty list (`[]`) with `count: 0`.

### 3.2 Tenant Library Discovery Fallback (`:8002`)
The user interface does not leave the reader with a blank screen. Instead, patron home and discovery routes invoke [`backend/services/library_catalogue_experience.py`](file:///d:/SDC/LibraryLLM/backend/services/library_catalogue_experience.py#L219-L236):
1. When `recommendations(library_id, actor, work_ids=(), limit=10)` receives empty global candidate `work_ids`:
   - `candidates = []` $\to$ `matches = []`.
   - The deterministic recent-acquisition fallback triggers immediately:
     ```python
     fallback = list(collection('library_books').aggregate([
         *usable(library_id),
         {'$match': {'library_book_id': {'$nin': []}}},
         *arrival_sort(),
         {'$limit': limit}
     ]))
     ```
   - **Result**: The new user receives the $10$ most recently accessioned physical books from their library, tagged with ranking `'GLOBAL_INTERSECTION_AND_LOCAL_DISCOVERY'`.
2. On the **Patron Home Dashboard** (`GET /api/v1/libraries/{library_id}/catalogue/home`):
   - The new user is served three curated rails:
     - **Featured Rail**: Ordered by accession sequence (`accession_sequence: 1`).
     - **New Arrivals Rail**: Ordered deterministically by `arrival_sort()` (`added_at: -1`).
     - **Popular Rail**: Scored by community activity across the preceding 90 days (`loans * 8 + requests * 2 + reservations * 1`).
   - The new user's personal shelf summary displays zeroes (`pending_requests: 0`, `active_loans: 0`, `waiting_reservations: 0`).

### 3.3 Bypass via Seed Book Recommendation
If a new user navigates to any book's detail page and clicks "More Like This" (`POST /recommendations/from-book` or `GET /kg/books/{work_id}/more-like-this`):
- **User cold start is completely bypassed**.
- The recommendation engine uses the seed book's `semantic_text` ($3000$ characters) as the semantic query, generating candidates regardless of whether the user has prior interactions.

---

## 4. New Book Cold Start

LuminaR exhibits two distinct behaviors depending on whether the book is a **global catalog entry** or a **tenant library physical holding**.

### 4.1 Global Catalog Book (New to MongoDB `books_collection`)

#### A. Vector Search Engine (`search/` on port `:8003`)
- Candidate generation relies on the pre-built HNSW vector index (`active_index.json`).
- If a new book document is inserted into MongoDB `books_collection` but the background sync worker or manual index rebuild has not processed it:
  - The book has no embedding vector in the HNSW graph.
  - **The book cannot be retrieved as a semantic candidate** for user profiles or seed queries.

#### B. Knowledge Graph (`knowledge_graph/` on port `:8002`)
- The knowledge graph is persisted as a frozen SQLite snapshot (`catalogue.sqlite`, 5.87 GB).
- **If the new book is queried as a seed**:
  - `graph.book(work_id)` raises `KeyError`.
  - Backend route [`guarded()`](file:///d:/SDC/LibraryLLM/backend/routes/knowledge_graph.py#L35) translates this into `HTTP 404: "This book is not in the catalogue graph."`.
- **If a book exists in the graph, but its MongoDB metadata has changed**:
  - [`features_current()`](file:///d:/SDC/LibraryLLM/backend/routes/knowledge_graph.py#L43-L47) compares normalized author and subject sets and SHA256 description hashes.
  - Returns `HTTP 409 Conflict: "This book’s metadata changed. Rebuild the graph before comparing it."`.
- **If a book has no authors or subjects in the graph**:
  - Returns `candidate_count: 0, reason: "No author or subject links for this book."`.

### 4.2 Tenant Library Holding (New Copy Added to `library_books`)
When a librarian imports a dataset or accessions a new book:
1. **Immediate Discovery Visibility**:
   - The book is assigned `created_at = now()` and optionally `acquisition_date`.
   - In [`arrival_sort()`](file:///d:/SDC/LibraryLLM/backend/services/library_catalogue_experience.py#L146-L149), `added_at` is set from `acquisition_date` falling back to `created_at`.
   - The book immediately surfaces at the **very first position of the New Arrivals rail** (`new_arrivals[0]`).
2. **Cold Popularity**:
   - Because it has zero historical loans, borrow requests, or reservations in the 90-day window, its `popularity.score = 0`.
   - It will not appear in the Popular rail until patrons interact with it.
3. **Local Recommendation Inclusion**:
   - If a global recommendation query produces fewer than $k$ matches held by the library, the new book is eligible for selection during the fallback pass (`*arrival_sort()`).

---

## 5. New Library Cold Start

When a newly registered library tenant is provisioned in the multi-library system:

### 5.1 Empty Catalog State (`GLOBAL_FALLBACK`)
In [`source_locked()`](file:///d:/SDC/LibraryLLM/backend/services/library_catalogue_experience.py#L59-L70):
1. `total = collection('library_books').count_documents({'library_id': library_id, 'status': 'ACTIVE', ...})`.
2. If `total == 0`:
   - `catalogue_source` is set to `'GLOBAL_FALLBACK'`.
   - Capabilities are restricted:
     - `physical_actions: false`
     - `reservations: false`
     - `local_search: false`
     - `global_discovery: true`
   - Notice displayed to patron: `"Global Catalogue · Not currently held by this library."`

### 5.2 Recommendation & Home Route Behavior
1. In `recommendations(library_id, actor)`:
   ```python
   if descriptor['catalogue_source'] == 'GLOBAL_FALLBACK':
       return {'source': descriptor, 'results': [], 'ranking': 'GLOBAL_FALLBACK'}
   ```
   **Returns an empty list immediately**. No global candidate intersection is attempted.
2. In `home(library_id, actor)`:
   ```python
   if descriptor['catalogue_source'] == 'GLOBAL_FALLBACK':
       return payload  # featured=[], new_arrivals=[], popular=[], subjects=[]
   ```
   All discovery rails return empty arrays.

### 5.3 Transition to Active Tenant State (`LIBRARY_LOCAL`)
As soon as the librarian uploads a catalog CSV or adds a single physical copy:
- `local_book_count >= 1`.
- `catalogue_source` switches to `'LIBRARY_LOCAL'`.
- All rails, local searches, and recommendation intersection pipelines activate automatically without requiring system restart or cache invalidation.

---

## 6. Cold-Start Summary Matrix

| Entity | Trigger Condition | Exact System Response | Fallback Mechanism |
|---|---|---|---|
| **New User** (Global) | Zero queries, loans, holds | `generate_semantic_candidates` returns `[]` | None in microservice |
| **New User** (Tenant) | Calling library recommendations | Global intersection matches $0$ books | `arrival_sort()` deterministic recent acquisitions |
| **New User** (Dashboard) | Visiting `/catalogue/home` | Summary shows zeroes | Displays Featured, New Arrivals, and Community Popular rails |
| **New Book** (Vector) | Not yet in HNSW index | Omitted from candidate generation | None until index sync job runs |
| **New Book** (Graph) | Not in `catalogue.sqlite` | Raises `HTTP 404` | Must rebuild SQLite snapshot |
| **New Book** (Tenant) | Zero circulation records | Scored `popularity = 0` | Displayed at top of New Arrivals rail |
| **New Library** | Zero active physical books | `catalogue_source: GLOBAL_FALLBACK` | Notice: "Global Catalogue · Not currently held" |
