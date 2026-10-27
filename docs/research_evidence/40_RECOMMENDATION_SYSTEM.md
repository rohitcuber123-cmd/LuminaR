# Book Recommendation System Architecture & Scoring

## 1. Executive Summary

LuminaR implements a **multi-stage, content-based hybrid recommendation system with behavioral feedback adjustments**, operating across two distinct layers:
1. **Global Recommendation Service** (`recommendation/` running on port `8004`): Produces personalized top-$k$ candidates from the global 5,000,000-book catalog using semantic vector search (port `8003`), user search recency decay, borrowing history, reservation history, explicit feedback interactions, and diversity constraints.
2. **Tenant Library Scoping Layer** (`backend/services/library_catalogue_experience.py` on port `8002`): Restricts global candidate work IDs to physical books currently held by a patron's active library, falling back deterministically to recent local acquisitions if global candidates are absent or exhausted.

**Critical Architectural Fact**: LuminaR does **NOT** use Collaborative Filtering (CF). There is no matrix factorization (SVD/ALS), no user-user similarity matrix, and no neural collaborative filtering. It is a **heuristic hybrid content-and-behavior recommender**.

---

## 2. End-to-End Recommendation Pipeline Trace

```
Patron Request (GET /recommendations or POST /recommendations/from-book)
  │
  ▼
[Input Signal Harvesting] ─── User search history, active/returned loans, active/fulfilled reservations, feedback events
  │
  ▼
[User Profile Construction] ── Exponential recency decay (λ=0.15), subject/author frequency Counters, active exclusions
  │
  ▼
[Candidate Generation] ────── Combined recency-weighted search query sent to Search API (:8003/search, top_k=50)
  │                            (or Seed Book semantic_text[:3000] in Seed Mode)
  │
  ▼
[Hard Filtering] ──────────── Exclude currently ISSUED loans & ACTIVE/READY_FOR_PICKUP reservations
  │
  ▼
[Composite 8-Factor Scoring] ─ Semantic(0.40) + Subject(0.15) + Author(0.10) + Borrowing(0.15)
  │                            + Reservation(0.10) + Rating(0.05) + Popularity(0.03) + Availability(0.02)
  │
  ▼
[Feedback Adjustment] ────── Additive adjustment: + 0.10 × Feedback_Score (clamped [-1.0, 1.0])
  │
  ▼
[Sorting & Diversity Reranking] Greedy deduplication: Max 2 books/author, Jaccard subject < 0.80, title token < 0.80
  │
  ▼
[Tenant Library Intersect] ── Match against collection('library_books') for tenant libraryId
  │                            Fallback to local acquisitions (*arrival_sort()) if matches < limit
  ▼
Final Hydrated Recommendations
```

---

## 3. Input Signals & Profile Representation

Profile construction is implemented in [`recommendation/recommendation_service.py`](file:///d:/SDC/LibraryLLM/recommendation/recommendation_service.py#L340-L689) via `build_user_profile(user_id)`:

### 3.1 Search History & Recency Decay
- Queries are harvested from `search_history_collection` (limit 50).
- An exponential decay weight is computed per query based on elapsed time:
  $$\text{weight} = \exp(-\lambda \cdot \Delta t_{\text{days}})$$
  where $\lambda = \text{DECAY\_RATE} = 0.15$.
  - Recent searches ($\Delta t \approx 0$) receive weights near $1.0$.
  - A search from 7 days ago receives weight $\exp(-0.15 \times 7) \approx 0.35$.
  - Queries with weight $< 0.01$ are dropped.
- The top 10 queries sorted by recency weight are concatenated into a combined search string `combined_query`.

### 3.2 Borrowing History (`issues_collection`)
- Active loans (`status == 'ISSUED'`) are added to `active_issue_work_ids` for **hard exclusion**.
- All loans (including historical `RETURNED` issues) contribute to:
  - `borrowed_subjects`: Frequency Counter of subjects across borrowed books.
  - `borrowed_authors`: Frequency Counter of authors across borrowed books.

### 3.3 Reservation History (`reservations_collection`)
- Active reservations (`status in ['ACTIVE', 'READY_FOR_PICKUP']`) are added to `active_reservation_work_ids` for **hard exclusion**.
- Fulfilled and active reservations contribute to:
  - `reserved_subjects`: Frequency Counter of subjects.
  - `reserved_authors`: Frequency Counter of authors.
- `CANCELLED` reservations are explicitly ignored.

### 3.4 Behavioral Feedback Interaction (`recommendation_feedbacks_collection`)
- Captures client telemetry events with pre-defined weights:

| Feedback Type | Weight $w_{\text{fb}}$ | Meaning |
|---|---|---|
| `VIEWED` | $+0.10$ | Impression on recommendation rail |
| `CLICKED` | $+0.25$ | Opened book details card |
| `RESERVED` | $+0.60$ | Placed hold from recommendation |
| `ISSUED` | $+0.80$ | Checked out physical copy |
| `RATED` | $+0.90$ | Submitted star rating |
| `DISMISSED` | $-0.60$ | Clicked dismiss button on card |
| `NOT_INTERESTED` | $-0.80$ | Explicit negative preference |

- **Spam Control**: Maximum 5 identical feedback events per `work_id` (`MAX_FEEDBACK_PER_WORK = 5`).
- **Decay**: Effective weight $= w_{\text{fb}} \cdot \exp(-0.15 \cdot \Delta t_{\text{days}})$.
- Aggregates:
  - `feedback_work_scores`: Dictionary mapping `work_id` $\to$ net accumulated feedback score.
  - `feedback_subjects`: Positive feedback adds $+1$; negative feedback subtracts $-1$.
  - `feedback_authors`: Positive feedback adds $+1$; negative feedback subtracts $-1$.

---

## 4. Candidate Generation

Implemented in [`generate_semantic_candidates()`](file:///d:/SDC/LibraryLLM/recommendation/recommendation_service.py#L695-L865):

1. **Personalized Profile Mode**:
   - Up to 10 recency-weighted queries are concatenated: `combined_query = " ".join(recent_queries)`.
   - Dispatches HTTP POST to Search API:
     ```json
     POST http://127.0.0.1:8003/search
     {
       "query": combined_query,
       "top_k": 50,
       "save_history": false
     }
     ```
   - Candidates are extracted from vector search results. The raw `hnsw_score` is used as `semantic_score`. (Rerank score is explicitly ignored because BGE-Reranker-v2 logits are unbounded).

2. **Single Seed Book Mode** (`/recommendations/from-book`):
   - Used when a user requests books similar to a specific book (`seed_work_id`).
   - Profile queries are overridden by `semantic_text(seed)[:3000]`.
   - Behavioral counters (borrowed, reserved, feedback) are reset to empty.
   - Seed book is added to hard exclusions.

---

## 5. Scoring Formulas and Exact Weights

The hybrid score combines 8 base components plus an additive feedback adjustment in [`calculate_recommendation_score()`](file:///d:/SDC/LibraryLLM/recommendation/recommendation_service.py#L1666-L1900):

### 5.1 The 8 Base Components & Weights

$$\text{BaseScore} = \sum_{i=1}^{8} W_i \cdot S_i$$

| Component | Weight $W_i$ | Scoring Function $S_i$ | Formula / Definition |
|---|---|---|---|
| **Semantic Similarity** | **0.40** | `semantic_score` | Clamped `hnsw_score` $\in [0.0, 1.0]$ from vector retrieval |
| **Subject Overlap** | **0.15** | `subject_score` | $\frac{\| \text{Subjects}_{\text{book}} \cap \text{Subjects}_{\text{user}} \|}{\| \text{Subjects}_{\text{book}} \|}$ |
| **Author Overlap** | **0.10** | `author_score` | $\frac{\| \text{Authors}_{\text{book}} \cap \text{Authors}_{\text{user}} \|}{\| \text{Authors}_{\text{book}} \|}$ |
| **Borrowing Overlap** | **0.15** | `borrowing_score` | $\min(0.7 \cdot \text{SubjOverlap}_{\text{borrowed}} + 0.3 \cdot \text{AuthOverlap}_{\text{borrowed}}, 1.0)$ |
| **Reservation Overlap** | **0.10** | `reservation_score` | $\min(0.7 \cdot \text{SubjOverlap}_{\text{reserved}} + 0.3 \cdot \text{AuthOverlap}_{\text{reserved}}, 1.0)$ |
| **Average Rating** | **0.05** | `rating_score` | $\min(\max(\frac{\text{average\_rating}}{5.0}, 0.0), 1.0)$ |
| **Popularity** | **0.03** | `popularity_score` | $\min\left(\frac{\ln(1 + \text{read\_logs} + \text{ratings})}{10.0}, 1.0\right)$ (log-normalized) |
| **Availability** | **0.02** | `availability_score` | $\frac{\text{available\_copies}}{\text{total\_copies}}$ if in catalog, else $0.0$ |
| **Total Base Weights** | **1.00** | | Convex combination of 8 signals |

### 5.2 Feedback Adjustment

$$\text{FeedbackScore} = \text{DirectContribution} + \text{SubjectTransfer} + \text{AuthorTransfer}$$

- **Direct Match**: Clamped net feedback score for candidate book $\times 0.6$.
- **Subject Transfer**: $(\text{PosOverlap} \times 0.3) - (\text{NegOverlap} \times 0.15)$.
- **Author Transfer**: $\text{PosAuthorOverlap} \times 0.1$.
- Clamped to $[-1.0, 1.0]$.

$$\text{FinalScore} = \text{clamp}_{[0.0, 1.0]}\left( \text{BaseScore} + 0.10 \times \text{FeedbackScore} \right)$$

---

## 6. Hard Filtering & Exclusions

Implemented in [`RankedRecommendationPages.page()`](file:///d:/SDC/LibraryLLM/recommendation/ranked_pages.py#L16-L45):
- **Currently Issued Books**: Any book with `user_id == current_user` and `status == 'ISSUED'` is excluded.
- **Active Holds/Reservations**: Any book with `status in ['ACTIVE', 'READY_FOR_PICKUP']` is excluded.
- **Seed Book**: When in seed mode, `seed_work_id` is excluded.
- **Historical Loans & Fulfilled Reservations**: Explicitly **NOT** excluded; they remain eligible for recommendation if returned/completed.

---

## 7. Diversity Re-ranking (V2.6)

Implemented in [`apply_diversity_reranking()`](file:///d:/SDC/LibraryLLM/recommendation/recommendation_service.py#L1548-L1660) via a greedy filtering pass over candidates sorted by `FinalScore`:

1. **Author Concentration Cap**:
   - `MAX_BOOKS_PER_AUTHOR = 2`.
   - Once 2 books by an author have been selected into the final list, subsequent candidates by that author are deferred.
2. **Subject Similarity Threshold**:
   - `SUBJECT_SIMILARITY_THRESHOLD = 0.80`.
   - Computes Jaccard similarity between candidate subject set and already selected books:
     $$J(A, B) = \frac{\| A \cap B \|}{\| A \cup B \|}$$
   - If $J \ge 0.80$ against any selected book, candidate is deferred.
3. **Title Lexical Overlap Threshold**:
   - `TITLE_SIMILARITY_THRESHOLD = 0.80`.
   - Computes Jaccard similarity across lowercased whitespace title tokens.
   - If $J \ge 0.80$, candidate is deferred to prevent near-duplicate editions.
4. **Deferred Backfill**:
   - If the candidate pool under-fills the requested `limit` after filtering, deferred books backfill remaining slots in score order.

---

## 8. Multi-Library Tenant Scoping

LuminaR enforces strict tenant boundaries on physical holdings while allowing global discovery:

In [`backend/services/library_catalogue_experience.py:recommendations()`](file:///d:/SDC/LibraryLLM/backend/services/library_catalogue_experience.py#L219-L236):
1. **Candidate Intersect**:
   - Accepts global candidate `work_ids` (up to 200) from the recommendation service.
   - Queries `collection('library_books')` scoped to `library_id` with `status == 'ACTIVE'`:
     ```python
     collection('library_books').aggregate([
         *usable(library_id),
         {'$match': {'global_work_id': {'$in': candidates}}},
         {'$set': {'recommendation_rank': {'$indexOfArray': [candidates, '$global_work_id']}}},
         {'$sort': {'recommendation_rank': 1, 'library_book_id': 1}},
         {'$limit': limit}
     ])
     ```
2. **Deterministic Local Discovery Fallback**:
   - If `len(matches) < limit`, the remaining slots are filled from recent local acquisitions (`*arrival_sort()`):
     ```python
     collection('library_books').aggregate([
         *usable(library_id),
         {'$match': {'library_book_id': {'$nin': [r['library_book_id'] for r in matches]}}},
         *arrival_sort(),
         {'$limit': limit - len(matches)}
     ])
     ```
   - Ranking strategy is labelled `'GLOBAL_INTERSECTION_AND_LOCAL_DISCOVERY'`.
3. **Global Fallback State**:
   - If the library has 0 books or is uninitialized (`GLOBAL_FALLBACK`), recommendations return empty with `ranking: 'GLOBAL_FALLBACK'`.

---

## 9. Recommendation Feature Evaluation Summary

| Method / Feature | Implemented? | Location / Verification |
|---|---|---|
| **Popularity** | **YES** | Log-normalized in 8-factor score ($W=0.03$); 90-day event sum in local library |
| **Borrow History** | **YES** | Overlap with borrowed subjects/authors ($W=0.15$) |
| **Search History** | **YES** | Top 10 recency-weighted queries combined into vector search |
| **Category / Subject** | **YES** | Overlap with profile subjects ($W=0.15$) |
| **Author Matching** | **YES** | Overlap with profile authors ($W=0.10$) |
| **Embedding Similarity** | **YES** | BGE-small-en-v1.5 HNSW cosine similarity ($W=0.40$) |
| **Content-Based Filtering** | **YES** | Primary basis of all candidate scoring |
| **Collaborative Filtering** | **NO** | No matrix factorization, no user-user vectors, no ALS |
| **New Arrivals** | **YES** | Deterministic local fallback in `arrival_sort()` |
| **Hybrid Scoring** | **YES** | Linear convex combination + feedback adjustment |
| **Rules / Heuristics** | **YES** | Diversity re-ranking, author cap (2), active loan exclusion |
