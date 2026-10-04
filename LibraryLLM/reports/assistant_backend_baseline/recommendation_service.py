from collections import Counter
from datetime import datetime, timezone
import math
import requests


from backend.database.mongodb import (
    books_collection,
    issues_collection,
    reservations_collection,
    recommendation_feedbacks_collection
)

from backend.services.search_history_service import (
    get_user_search_history
)


# ============================================================
# CONFIGURATION
# ============================================================

# ----------------------------------------------------------
# V2 SCORING WEIGHTS (V2.2 + V2.3 + V2.4)
#
# TOTAL = 1.00
#
# Semantic relevance remains the strongest single signal.
# Borrowing/Reservation are behavioral signals.
# Availability is a usefulness signal.
# ----------------------------------------------------------

SEMANTIC_WEIGHT = 0.40
SUBJECT_WEIGHT = 0.15
AUTHOR_WEIGHT = 0.10
BORROWING_WEIGHT = 0.15
RESERVATION_WEIGHT = 0.10
RATING_WEIGHT = 0.05
POPULARITY_WEIGHT = 0.03
AVAILABILITY_WEIGHT = 0.02

CANDIDATE_COUNT = 50

SEARCH_API_URL = (
    "http://127.0.0.1:8003/search"
)

DECAY_RATE = 0.15

MAX_PROFILE_QUERIES = 10

# ----------------------------------------------------------
# V2.5 FEEDBACK WEIGHTS
#
# Behavioral strength per feedback type.
# Positive values boost; negative values suppress.
# ----------------------------------------------------------

FEEDBACK_WEIGHTS = {
    "VIEWED": 0.10,
    "CLICKED": 0.25,
    "RESERVED": 0.60,
    "ISSUED": 0.80,
    "RATED": 0.90,
    "DISMISSED": -0.60,
    "NOT_INTERESTED": -0.80
}

# Additive adjustment magnitude for feedback.
# Keeps feedback influential but does not override
# semantic relevance.
FEEDBACK_ADJUSTMENT = 0.10

# Maximum identical feedback events per work_id
# to prevent spam from overwhelming the profile.
MAX_FEEDBACK_PER_WORK = 5

# ----------------------------------------------------------
# V2.6 DIVERSITY THRESHOLDS
# ----------------------------------------------------------

MAX_BOOKS_PER_AUTHOR = 2

SUBJECT_SIMILARITY_THRESHOLD = 0.80

TITLE_SIMILARITY_THRESHOLD = 0.80


# ============================================================
# USER BEHAVIOR
# ============================================================

def get_user_behavior(user_id):

    search_history = get_user_search_history(
        user_id,
        limit=50
    )

    issues = list(
        issues_collection.find(
            {
                "user_id": user_id
            },
            {
                "_id": 0
            }
        ).sort(
            "issued_at",
            -1
        )
    )

    reservations = list(
        reservations_collection.find(
            {
                "user_id": user_id
            },
            {
                "_id": 0
            }
        ).sort(
            "reserved_at",
            -1
        )
    )

    # V2.5: Feedback history
    feedbacks = list(
        recommendation_feedbacks_collection.find(
            {
                "user_id": user_id
            },
            {
                "_id": 0
            }
        ).sort(
            "created_at",
            -1
        ).limit(200)
    )

    return {
        "search_history": search_history,
        "issues": issues,
        "reservations": reservations,
        "feedbacks": feedbacks
    }


# ============================================================
# BOOK LOOKUP
# ============================================================

def get_book_by_work_id(work_id):

    return books_collection.find_one(
        {
            "work_id": str(work_id)
        },
        {
            "_id": 0
        }
    )


# ============================================================
# METADATA EXTRACTION HELPER
# ============================================================

def extract_subjects_from_book(book):
    """Extract a list of subject strings from a book doc."""

    subjects = book.get("subjects")

    if not subjects:
        return []

    if isinstance(subjects, str):

        return [
            s.strip()
            for s in subjects.split("|")
            if s.strip()
        ]

    return list(subjects)


def extract_authors_from_book(book):
    """Extract a list of author strings from a book doc."""

    authors = book.get("authors")

    if not authors:
        return []

    if isinstance(authors, str):

        return [
            a.strip()
            for a in authors.split("|")
            if a.strip()
        ]

    return list(authors)


# ============================================================
# RECENCY HELPERS
# ============================================================

def parse_search_timestamp(value):
    """Safely parse a search history timestamp to a
    timezone-aware UTC datetime."""

    if value is None:

        return None

    # Already a datetime object

    if isinstance(value, datetime):

        if value.tzinfo is None:

            return value.replace(
                tzinfo=timezone.utc
            )

        return value

    # String — try ISO format

    if isinstance(value, str):

        try:

            parsed = datetime.fromisoformat(
                value
            )

            if parsed.tzinfo is None:

                parsed = parsed.replace(
                    tzinfo=timezone.utc
                )

            return parsed

        except (ValueError, TypeError):

            return None

    return None


def calculate_recency_weight(created_at):
    """Calculate exponential recency decay.

    weight = exp(-DECAY_RATE * age_days)

    Recent searches → weight near 1.0
    Older searches  → weight decays toward 0.0
    """

    timestamp = parse_search_timestamp(
        created_at
    )

    if timestamp is None:

        return 0.0

    now = datetime.now(
        timezone.utc
    )

    age = now - timestamp

    age_days = max(
        age.total_seconds() / 86400.0,
        0.0
    )

    weight = math.exp(
        -DECAY_RATE * age_days
    )

    return min(
        max(weight, 0.0),
        1.0
    )


def build_recency_aware_queries(
    search_interests
):
    """Build a combined semantic query string from
    recency-weighted search interests.

    Selects the top MAX_PROFILE_QUERIES interests
    sorted by recency weight, then joins their
    query strings.
    """

    if not search_interests:

        return []

    # Sort by recency weight descending

    sorted_interests = sorted(
        search_interests,
        key=lambda item: item[
            "recency_weight"
        ],
        reverse=True
    )

    # Keep the strongest recent queries

    top_interests = sorted_interests[
        :MAX_PROFILE_QUERIES
    ]

    # Filter out nearly-zero weight queries

    return [
        interest["query"]
        for interest in top_interests
        if interest["recency_weight"] > 0.01
    ]


# ============================================================
# USER PROFILE
# ============================================================

def build_user_profile(user_id):

    behavior = get_user_behavior(
        user_id
    )

    search_history = behavior[
        "search_history"
    ]

    issues = behavior[
        "issues"
    ]

    reservations = behavior[
        "reservations"
    ]

    feedbacks = behavior[
        "feedbacks"
    ]

    profile = {
        "queries": [],
        "work_ids": [],
        "subjects": Counter(),
        "authors": Counter(),

        # V2.2 — Borrowing History
        "borrowed_subjects": Counter(),
        "borrowed_authors": Counter(),

        # V2.3 — Reservation History
        "reserved_subjects": Counter(),
        "reserved_authors": Counter(),

        # V2.5 — Feedback
        "feedback": [],
        "feedback_subjects": Counter(),
        "feedback_authors": Counter(),
        "feedback_work_scores": {},

        # Exclusions: only currently-active interactions
        "active_issue_work_ids": set(),
        "active_reservation_work_ids": set()
    }

    # ========================================================
    # SEARCH HISTORY — with recency weights (V2.1)
    # ========================================================

    search_interests = []

    for search in search_history:

        query = search.get(
            "query"
        )

        if query:

            profile["queries"].append(
                query
            )

            recency_weight = (
                calculate_recency_weight(
                    search.get(
                        "created_at"
                    )
                )
            )

            search_interests.append(
                {
                    "query": query,
                    "recency_weight": round(
                        recency_weight,
                        4
                    )
                }
            )

    profile["search_interests"] = (
        search_interests
    )

    # ========================================================
    # ISSUED BOOKS (V2.2 — Borrowing History)
    #
    # All issues contribute to preferences.
    # Only ISSUED (currently active) excluded from results.
    # RETURNED issues are historical preference signals.
    # ========================================================

    for issue in issues:

        work_id = issue.get(
            "work_id"
        )

        if not work_id:
            continue

        work_id = str(work_id)

        # Track for general metadata extraction
        if work_id not in profile["work_ids"]:
            profile["work_ids"].append(
                work_id
            )

        # Track active issues for exclusion
        status = issue.get(
            "status",
            ""
        )

        if status == "ISSUED":
            profile[
                "active_issue_work_ids"
            ].add(work_id)

        # Extract borrowing preferences
        # from ALL issues (including returned)
        book = get_book_by_work_id(
            work_id
        )

        if book is not None:

            for subj in extract_subjects_from_book(
                book
            ):
                profile[
                    "borrowed_subjects"
                ][subj] += 1

            for auth in extract_authors_from_book(
                book
            ):
                profile[
                    "borrowed_authors"
                ][auth] += 1

    # ========================================================
    # RESERVED BOOKS (V2.3 — Reservation History)
    #
    # ACTIVE / READY_FOR_PICKUP → strong signal + excluded
    # FULFILLED → moderate/strong signal
    # CANCELLED → weak signal (ignored for preferences)
    # ========================================================

    for reservation in reservations:

        work_id = reservation.get(
            "work_id"
        )

        if not work_id:
            continue

        work_id = str(work_id)

        # Track for general metadata extraction
        if work_id not in profile["work_ids"]:
            profile["work_ids"].append(
                work_id
            )

        status = reservation.get(
            "status",
            ""
        )

        # Active reservations are excluded from results
        if status in (
            "ACTIVE",
            "READY_FOR_PICKUP"
        ):
            profile[
                "active_reservation_work_ids"
            ].add(work_id)

        # Skip cancelled reservations for preference
        if status == "CANCELLED":
            continue

        # Extract reservation preferences
        # from ACTIVE + READY_FOR_PICKUP + FULFILLED
        book = get_book_by_work_id(
            work_id
        )

        if book is not None:

            for subj in extract_subjects_from_book(
                book
            ):
                profile[
                    "reserved_subjects"
                ][subj] += 1

            for auth in extract_authors_from_book(
                book
            ):
                profile[
                    "reserved_authors"
                ][auth] += 1

    # ========================================================
    # EXTRACT GENERAL USER INTEREST METADATA
    #
    # This populates the original profile["subjects"]
    # and profile["authors"] from all interacted books.
    # ========================================================

    for work_id in profile[
        "work_ids"
    ]:

        book = get_book_by_work_id(
            work_id
        )

        if book is None:
            continue

        for auth in extract_authors_from_book(
            book
        ):
            profile["authors"][
                str(auth)
            ] += 1

        for subj in extract_subjects_from_book(
            book
        ):
            profile["subjects"][
                str(subj)
            ] += 1

    # ========================================================
    # FEEDBACK HISTORY (V2.5 — User Feedback Loop)
    #
    # Aggregate feedback events into preference signals.
    # Cap repeated identical events to prevent spam.
    # Apply recency decay to each feedback event.
    # ========================================================

    # Count events per (work_id, feedback_type)
    # to enforce MAX_FEEDBACK_PER_WORK cap.
    feedback_counts = Counter()

    for fb in feedbacks:

        work_id = fb.get("work_id")
        fb_type = fb.get("feedback_type", "")

        if not work_id or not fb_type:
            continue

        work_id = str(work_id)

        # Skip unsupported feedback types
        if fb_type not in FEEDBACK_WEIGHTS:
            continue

        # Cap repeated identical events
        count_key = (
            work_id,
            fb_type
        )

        feedback_counts[count_key] += 1

        if feedback_counts[
            count_key
        ] > MAX_FEEDBACK_PER_WORK:
            continue

        strength = FEEDBACK_WEIGHTS[
            fb_type
        ]

        recency = calculate_recency_weight(
            fb.get("created_at")
        )

        effective = strength * recency

        profile["feedback"].append(
            {
                "work_id": work_id,
                "feedback_type": fb_type,
                "feedback_strength": round(
                    strength,
                    4
                ),
                "recency_weight": round(
                    recency,
                    4
                ),
                "effective_weight": round(
                    effective,
                    4
                )
            }
        )

        # Aggregate per-work net score
        if work_id not in profile[
            "feedback_work_scores"
        ]:
            profile[
                "feedback_work_scores"
            ][work_id] = 0.0

        profile[
            "feedback_work_scores"
        ][work_id] += effective

        # Extract subject/author signals
        # from feedback (for preference transfer)
        book = get_book_by_work_id(
            work_id
        )

        if book is not None:

            # Scale subject/author counts
            # by sign of feedback
            sign = 1 if effective > 0 else -1

            for subj in extract_subjects_from_book(
                book
            ):
                profile[
                    "feedback_subjects"
                ][subj] += sign

            for auth in extract_authors_from_book(
                book
            ):
                profile[
                    "feedback_authors"
                ][auth] += sign

    return profile


# ============================================================
# SEMANTIC CANDIDATE GENERATION
# ============================================================

def generate_semantic_candidates(
    queries,
    authorization,
    candidate_count=CANDIDATE_COUNT
):

    if not queries:
        print("[Recommendation] No queries available, skipping semantic search")
        return []

    if not authorization:
        print("[Recommendation] No authorization, skipping semantic search")
        return []

    # ========================================================
    # BUILD COMBINED QUERY
    # ========================================================

    recent_queries = queries[:10]

    combined_query = " ".join(
        recent_queries
    ).strip()

    # Skip if query is empty after joining
    if not combined_query:
        print("[Recommendation] Combined query is empty, skipping semantic search")
        return []

    print(f"[Recommendation] Semantic search with query: '{combined_query[:100]}...'")

    # ========================================================
    # CALL SEARCH API
    # ========================================================

    try:

        print(f"[Recommendation] Calling search API with top_k={candidate_count}")
        response = requests.post(
            SEARCH_API_URL,
            json={
                "query": combined_query,
                "top_k": candidate_count,
                "save_history": False
            },
            headers={
                "Authorization": authorization
            },
            timeout=30
        )

    except requests.RequestException as e:

        print(
            "[Recommendation] Search API connection error:",
            str(e)
        )

        return []

    # ========================================================
    # CHECK STATUS
    # ========================================================

    if response.status_code != 200:

        print(
            "[Recommendation] Search API returned error:",
            response.status_code,
            response.text[:200]
        )

        return []

    # ========================================================
    # PARSE RESPONSE
    # ========================================================

    result = response.json()
    result_count = len(result.get("results", []))
    print(f"[Recommendation] Search API returned {result_count} candidates")

    # ========================================================
    # BUILD CANDIDATES
    # ========================================================

    candidates = []

    for item in result.get(
        "results",
        []
    ):

        work_id = item.get(
            "work_id"
        )

        if not work_id:
            continue

        # ----------------------------------------------------
        # Use hnsw_score as normalized semantic similarity.
        # Do NOT use rerank_score (it can exceed 1.0).
        # ----------------------------------------------------

        score = item.get(
            "hnsw_score",
            0
        )

        try:

            score = float(
                score
            )

        except (
            TypeError,
            ValueError
        ):

            score = 0.0

        candidates.append(
            {
                "work_id": str(
                    work_id
                ),

                "semantic_score": score,

                "title": item.get(
                    "title"
                ),

                "authors": item.get(
                    "authors"
                ),

                "subjects": item.get(
                    "subjects"
                ),

                "average_rating": item.get(
                    "rating"
                ),

                "rating_count": item.get(
                    "rating_count",
                    0
                ),

                "reading_log_count": item.get(
                    "read_logs",
                    0
                )
            }
        )

    return candidates


# ============================================================
# SUBJECT SIMILARITY
# ============================================================

def calculate_subject_score(
    book,
    user_subjects
):

    subjects = book.get(
        "subjects"
    )

    if not subjects:

        return 0.0

    # --------------------------------------------------------
    # Book subjects
    # --------------------------------------------------------

    if isinstance(
        subjects,
        str
    ):

        book_subjects = {
            subject.strip().lower()
            for subject in subjects.split("|")
            if subject.strip()
        }

    else:

        book_subjects = {
            str(subject).strip().lower()
            for subject in subjects
        }

    if not book_subjects:

        return 0.0

    # --------------------------------------------------------
    # User subjects
    # --------------------------------------------------------

    user_subject_set = {
        str(subject).strip().lower()
        for subject in user_subjects
    }

    if not user_subject_set:

        return 0.0

    # --------------------------------------------------------
    # Overlap
    # --------------------------------------------------------

    overlap = (
        book_subjects
        &
        user_subject_set
    )

    return len(
        overlap
    ) / len(
        book_subjects
    )


# ============================================================
# AUTHOR SIMILARITY
# ============================================================

def calculate_author_score(
    book,
    user_authors
):

    authors = book.get(
        "authors"
    )

    if not authors:

        return 0.0

    # --------------------------------------------------------
    # Book authors
    # --------------------------------------------------------

    if isinstance(
        authors,
        str
    ):

        book_authors = {
            author.strip().lower()
            for author in authors.split("|")
            if author.strip()
        }

    else:

        book_authors = {
            str(author).strip().lower()
            for author in authors
        }

    if not book_authors:

        return 0.0

    # --------------------------------------------------------
    # User authors
    # --------------------------------------------------------

    user_author_set = {
        str(author).strip().lower()
        for author in user_authors
    }

    if not user_author_set:

        return 0.0

    # --------------------------------------------------------
    # Overlap
    # --------------------------------------------------------

    overlap = (
        book_authors
        &
        user_author_set
    )

    return len(
        overlap
    ) / len(
        book_authors
    )


# ============================================================
# RATING SCORE
# ============================================================

def calculate_rating_score(
    book
):

    rating = book.get(
        "average_rating",
        0
    )

    try:

        rating = float(
            rating
        )

    except (
        TypeError,
        ValueError
    ):

        return 0.0

    return min(
        max(
            rating / 5.0,
            0.0
        ),
        1.0
    )


# ============================================================
# POPULARITY SCORE
# ============================================================

def calculate_popularity_score(
    book
):

    reading_count = book.get(
        "reading_log_count",
        0
    )

    rating_count = book.get(
        "rating_count",
        0
    )

    try:

        reading_count = float(
            reading_count
        )

    except (
        TypeError,
        ValueError
    ):

        reading_count = 0

    try:

        rating_count = float(
            rating_count
        )

    except (
        TypeError,
        ValueError
    ):

        rating_count = 0

    popularity = (
        reading_count
        +
        rating_count
    )

    # --------------------------------------------------------
    # Log normalization
    #
    # Prevents extremely popular books from
    # dominating the recommendation system.
    # --------------------------------------------------------

    return min(
        math.log1p(
            popularity
        ) / 10.0,
        1.0
    )


# ============================================================
# BORROWING SCORE (V2.2)
# ============================================================

def calculate_borrowing_score(
    book,
    borrowed_subjects,
    borrowed_authors
):
    """Score based on overlap between candidate book and
    subjects/authors from the user's borrowing history.

    Borrowing is a strong behavioral signal.
    """

    subject_overlap = 0.0
    author_overlap = 0.0

    # Subject overlap from borrowed books
    if borrowed_subjects:

        book_subjects = set(
            s.strip().lower()
            for s in (
                extract_subjects_from_book(book)
            )
        )

        user_borrowed_set = set(
            str(s).strip().lower()
            for s in borrowed_subjects
        )

        if book_subjects:

            overlap = (
                book_subjects
                &
                user_borrowed_set
            )

            subject_overlap = len(
                overlap
            ) / len(
                book_subjects
            )

    # Author overlap from borrowed books
    if borrowed_authors:

        book_authors = set(
            a.strip().lower()
            for a in (
                extract_authors_from_book(book)
            )
        )

        user_borrowed_authors = set(
            str(a).strip().lower()
            for a in borrowed_authors
        )

        if book_authors:

            overlap = (
                book_authors
                &
                user_borrowed_authors
            )

            author_overlap = len(
                overlap
            ) / len(
                book_authors
            )

    # Combine: subjects weighted more than authors
    return min(
        0.7 * subject_overlap
        + 0.3 * author_overlap,
        1.0
    )


# ============================================================
# RESERVATION SCORE (V2.3)
# ============================================================

def calculate_reservation_score(
    book,
    reserved_subjects,
    reserved_authors
):
    """Score based on overlap between candidate book and
    subjects/authors from the user's reservation history.

    Reservation is a strong interest signal.
    """

    subject_overlap = 0.0
    author_overlap = 0.0

    # Subject overlap from reserved books
    if reserved_subjects:

        book_subjects = set(
            s.strip().lower()
            for s in (
                extract_subjects_from_book(book)
            )
        )

        user_reserved_set = set(
            str(s).strip().lower()
            for s in reserved_subjects
        )

        if book_subjects:

            overlap = (
                book_subjects
                &
                user_reserved_set
            )

            subject_overlap = len(
                overlap
            ) / len(
                book_subjects
            )

    # Author overlap from reserved books
    if reserved_authors:

        book_authors = set(
            a.strip().lower()
            for a in (
                extract_authors_from_book(book)
            )
        )

        user_reserved_authors = set(
            str(a).strip().lower()
            for a in reserved_authors
        )

        if book_authors:

            overlap = (
                book_authors
                &
                user_reserved_authors
            )

            author_overlap = len(
                overlap
            ) / len(
                book_authors
            )

    # Combine: subjects weighted more than authors
    return min(
        0.7 * subject_overlap
        + 0.3 * author_overlap,
        1.0
    )


# ============================================================
# AVAILABILITY SCORE (V2.4)
# ============================================================

def calculate_availability_score(
    book
):
    """Score based on current availability.

    availability_score = available_copies / total_copies

    Books not in the library get 0.0.
    A book with total_copies=3, available_copies=0 gets 0.0
    but remains library_available=true.
    """

    if not book.get(
        "library_available",
        False
    ):
        return 0.0

    total = book.get(
        "total_copies",
        0
    )

    if total <= 0:
        return 0.0

    available = book.get(
        "available_copies",
        0
    )

    try:

        total = float(total)
        available = float(available)

    except (TypeError, ValueError):

        return 0.0

    return min(
        max(
            available / total,
            0.0
        ),
        1.0
    )


# ============================================================
# FEEDBACK SCORE (V2.5)
# ============================================================

def calculate_feedback_score(
    book,
    profile
):
    """Calculate a feedback-derived score for a candidate.

    Combines:
    1. Direct work_id match (has the user interacted
       with this exact book?)
    2. Subject/author preference transfer from feedback
       history (similar topics get a boost or penalty).

    Returns a value in [-1.0, +1.0].
    """

    work_id = str(
        book.get("work_id", "")
    )

    score = 0.0

    # -------------------------------------------------
    # Direct match: user gave feedback on this work_id
    # -------------------------------------------------

    feedback_work_scores = profile.get(
        "feedback_work_scores",
        {}
    )

    if work_id in feedback_work_scores:

        # Clamp the direct score contribution
        direct = feedback_work_scores[
            work_id
        ]

        score += min(
            max(direct, -1.0),
            1.0
        ) * 0.6

    # -------------------------------------------------
    # Subject transfer from feedback
    # -------------------------------------------------

    feedback_subjects = profile.get(
        "feedback_subjects",
        Counter()
    )

    if feedback_subjects:

        book_subjects = set(
            s.strip().lower()
            for s in extract_subjects_from_book(
                book
            )
        )

        fb_subject_set = set(
            str(s).strip().lower()
            for s in feedback_subjects
            if feedback_subjects[s] > 0
        )

        negative_set = set(
            str(s).strip().lower()
            for s in feedback_subjects
            if feedback_subjects[s] < 0
        )

        if book_subjects:

            pos_overlap = len(
                book_subjects & fb_subject_set
            ) / len(book_subjects)

            neg_overlap = len(
                book_subjects & negative_set
            ) / len(book_subjects)

            score += (
                pos_overlap * 0.3
                - neg_overlap * 0.15
            )

    # -------------------------------------------------
    # Author transfer from feedback
    # -------------------------------------------------

    feedback_authors = profile.get(
        "feedback_authors",
        Counter()
    )

    if feedback_authors:

        book_authors = set(
            a.strip().lower()
            for a in extract_authors_from_book(
                book
            )
        )

        fb_author_set = set(
            str(a).strip().lower()
            for a in feedback_authors
            if feedback_authors[a] > 0
        )

        if book_authors:

            overlap = len(
                book_authors & fb_author_set
            ) / len(book_authors)

            score += overlap * 0.1

    # Clamp to [-1.0, 1.0]
    return min(
        max(score, -1.0),
        1.0
    )


# ============================================================
# DIVERSITY HELPERS (V2.6)
# ============================================================

def calculate_jaccard_similarity(
    set_a,
    set_b
):
    """Jaccard similarity between two sets."""

    if not set_a or not set_b:
        return 0.0

    intersection = len(
        set_a & set_b
    )

    union = len(
        set_a | set_b
    )

    if union == 0:
        return 0.0

    return intersection / union


def get_subject_set(book):
    """Extract lowered subject set from a recommendation."""

    subjects = book.get("subjects", "")

    if not subjects:
        return set()

    if isinstance(subjects, str):

        return set(
            s.strip().lower()
            for s in subjects.split("|")
            if s.strip()
        )

    return set(
        str(s).strip().lower()
        for s in subjects
    )


def get_author_set(book):
    """Extract lowered author set from a recommendation."""

    authors = book.get("authors", "")

    if not authors:
        return set()

    if isinstance(authors, str):

        return set(
            a.strip().lower()
            for a in authors.split("|")
            if a.strip()
        )

    return set(
        str(a).strip().lower()
        for a in authors
    )


def get_title_tokens(book):
    """Simple lowered word-token set from a title."""

    title = book.get("title", "")

    if not title:
        return set()

    return set(
        title.lower().split()
    )


def apply_diversity_reranking(
    recommendations,
    limit
):
    """Greedy diversity re-ranking.

    Ensures the final list does not contain:
    - More than MAX_BOOKS_PER_AUTHOR books from one author
    - Multiple books with near-identical subjects
    - Multiple books with near-identical titles

    Skipped candidates are held back and used
    to fill remaining slots if needed.
    """

    selected = []
    deferred = []

    author_counts = Counter()

    for rec in recommendations:

        if len(selected) >= limit:
            break

        # -------------------------------------------------
        # Author limit check
        # -------------------------------------------------

        rec_authors = get_author_set(rec)
        author_blocked = False

        for author in rec_authors:

            if author_counts[
                author
            ] >= MAX_BOOKS_PER_AUTHOR:

                author_blocked = True
                break

        # -------------------------------------------------
        # Subject similarity check
        # -------------------------------------------------

        rec_subjects = get_subject_set(rec)
        subject_blocked = False

        for sel in selected:

            sel_subjects = get_subject_set(sel)

            sim = calculate_jaccard_similarity(
                rec_subjects,
                sel_subjects
            )

            if sim >= SUBJECT_SIMILARITY_THRESHOLD:

                subject_blocked = True
                break

        # -------------------------------------------------
        # Title similarity check
        # -------------------------------------------------

        rec_title_tokens = get_title_tokens(rec)
        title_blocked = False

        for sel in selected:

            sel_title_tokens = get_title_tokens(sel)

            sim = calculate_jaccard_similarity(
                rec_title_tokens,
                sel_title_tokens
            )

            if sim >= TITLE_SIMILARITY_THRESHOLD:

                title_blocked = True
                break

        # -------------------------------------------------
        # Decision
        # -------------------------------------------------

        if (
            author_blocked
            or subject_blocked
            or title_blocked
        ):
            deferred.append(rec)
            continue

        selected.append(rec)

        for author in rec_authors:
            author_counts[author] += 1

    # -------------------------------------------------
    # Fill remaining slots from deferred if needed
    # -------------------------------------------------

    for rec in deferred:

        if len(selected) >= limit:
            break

        selected.append(rec)

    return selected


# ============================================================
# FINAL RECOMMENDATION SCORE (V2)
# ============================================================

def calculate_recommendation_score(
    book,
    semantic_score,
    profile
):

    # --------------------------------------------------------
    # Semantic similarity
    # --------------------------------------------------------

    semantic_score = min(
        max(
            semantic_score,
            0.0
        ),
        1.0
    )

    # --------------------------------------------------------
    # Subject similarity (general profile)
    # --------------------------------------------------------

    subject_score = (
        calculate_subject_score(
            book,
            profile[
                "subjects"
            ].keys()
        )
    )

    # --------------------------------------------------------
    # Author similarity (general profile)
    # --------------------------------------------------------

    author_score = (
        calculate_author_score(
            book,
            profile[
                "authors"
            ].keys()
        )
    )

    # --------------------------------------------------------
    # Borrowing score (V2.2)
    # --------------------------------------------------------

    borrowing_score = (
        calculate_borrowing_score(
            book,
            profile.get(
                "borrowed_subjects",
                Counter()
            ).keys(),
            profile.get(
                "borrowed_authors",
                Counter()
            ).keys()
        )
    )

    # --------------------------------------------------------
    # Reservation score (V2.3)
    # --------------------------------------------------------

    reservation_score = (
        calculate_reservation_score(
            book,
            profile.get(
                "reserved_subjects",
                Counter()
            ).keys(),
            profile.get(
                "reserved_authors",
                Counter()
            ).keys()
        )
    )

    # --------------------------------------------------------
    # Rating
    # --------------------------------------------------------

    rating_score = (
        calculate_rating_score(
            book
        )
    )

    # --------------------------------------------------------
    # Popularity
    # --------------------------------------------------------

    popularity_score = (
        calculate_popularity_score(
            book
        )
    )

    # --------------------------------------------------------
    # Availability (V2.4)
    # --------------------------------------------------------

    availability_score = (
        calculate_availability_score(
            book
        )
    )

    # --------------------------------------------------------
    # Feedback (V2.5)
    # --------------------------------------------------------

    feedback_score = (
        calculate_feedback_score(
            book,
            profile
        )
    )

    # ========================================================
    # HYBRID SCORE (V2)
    #
    # The base 8-component score is computed first.
    # Feedback is then applied as a controlled additive
    # adjustment, clamped to [0.0, 1.0].
    # ========================================================

    base_score = (

        SEMANTIC_WEIGHT
        * semantic_score

        +

        SUBJECT_WEIGHT
        * subject_score

        +

        AUTHOR_WEIGHT
        * author_score

        +

        BORROWING_WEIGHT
        * borrowing_score

        +

        RESERVATION_WEIGHT
        * reservation_score

        +

        RATING_WEIGHT
        * rating_score

        +

        POPULARITY_WEIGHT
        * popularity_score

        +

        AVAILABILITY_WEIGHT
        * availability_score
    )

    # V2.5: Apply feedback adjustment
    final_score = (
        base_score
        + FEEDBACK_ADJUSTMENT
        * feedback_score
    )

    # Clamp to [0.0, 1.0]
    final_score = min(
        max(final_score, 0.0),
        1.0
    )

    return {
        "score": round(
            final_score,
            4
        ),

        "semantic_score": round(
            semantic_score,
            4
        ),

        "subject_score": round(
            subject_score,
            4
        ),

        "author_score": round(
            author_score,
            4
        ),

        "borrowing_score": round(
            borrowing_score,
            4
        ),

        "reservation_score": round(
            reservation_score,
            4
        ),

        "rating_score": round(
            rating_score,
            4
        ),

        "popularity_score": round(
            popularity_score,
            4
        ),

        "availability_score": round(
            availability_score,
            4
        ),

        "feedback_score": round(
            feedback_score,
            4
        )
    }


# ============================================================
# GET RECOMMENDATIONS
# ============================================================
def get_recommendations(
    user_id,
    authorization,
    limit=10
):

    # ========================================================
    # BUILD USER PROFILE
    # ========================================================

    profile = build_user_profile(
        user_id
    )

    # ========================================================
    # GET SEMANTIC CANDIDATES
    #
    # V2.1: Use recency-weighted query selection.
    # Recent searches dominate the combined query.
    # This calls the existing 8003 search service.
    # ========================================================

    recency_queries = build_recency_aware_queries(
        profile.get(
            "search_interests",
            []
        )
    )

    # Fall back to raw queries if recency
    # processing produced nothing.

    effective_queries = (
        recency_queries
        if recency_queries
        else profile["queries"][:MAX_PROFILE_QUERIES]
    )

    semantic_candidates = (
        generate_semantic_candidates(
            effective_queries,
            authorization,
            CANDIDATE_COUNT
        )
    )

    # ========================================================
    # EXCLUSIONS (V2.2 / V2.3 refined)
    #
    # Only CURRENTLY active interactions are excluded:
    # - Books the user currently has ISSUED
    # - Books with ACTIVE / READY_FOR_PICKUP reservation
    #
    # Historical borrowing and fulfilled reservations
    # are NOT excluded — they contribute to preferences.
    #
    # Search results themselves are NOT excluded because
    # appearing in search results does not mean the user
    # actually interacted with the book.
    # ========================================================

    excluded_work_ids = (
        profile.get(
            "active_issue_work_ids",
            set()
        )
        |
        profile.get(
            "active_reservation_work_ids",
            set()
        )
    )

    # ========================================================
    # SCORE CANDIDATES
    # ========================================================

    recommendations = []

    for candidate in semantic_candidates:

        work_id = candidate[
            "work_id"
        ]

        # ----------------------------------------------------
        # Skip only currently active interactions
        # ----------------------------------------------------

        if work_id in excluded_work_ids:

            continue

        # ----------------------------------------------------
        # Build base book object from search metadata.
        # This ensures candidates are never discarded
        # simply because MongoDB lookup fails.
        # ----------------------------------------------------

        book = {
            "work_id": work_id,
            "book_id": None,
            "title": candidate.get("title"),
            "authors": candidate.get("authors"),
            "subjects": candidate.get("subjects"),
            "average_rating": candidate.get(
                "average_rating"
            ),
            "rating_count": candidate.get(
                "rating_count", 0
            ),
            "reading_log_count": candidate.get(
                "reading_log_count", 0
            ),
            "available_copies": 0,
            "total_copies": 0,
            "shelf_location": None,
            "library_available": False
        }

        # ----------------------------------------------------
        # Enrich with MongoDB when available
        # ----------------------------------------------------

        mongo_book = get_book_by_work_id(
            work_id
        )

        if mongo_book is not None:

            book.update(
                mongo_book
            )
            book["library_available"] = True

        # ----------------------------------------------------
        # Calculate hybrid score
        # ----------------------------------------------------

        scores = (
            calculate_recommendation_score(
                book,

                candidate[
                    "semantic_score"
                ],

                profile
            )
        )

        # ----------------------------------------------------
        # Build recommendation
        # ----------------------------------------------------

        recommendation = {

            "work_id": work_id,

            "book_id": book.get(
                "book_id"
            ),

            "title": book.get(
                "title"
            ),

            "authors": book.get(
                "authors"
            ),

            "subjects": book.get(
                "subjects"
            ),

            "average_rating": book.get(
                "average_rating",
                0
            ),

            "total_copies": book.get(
                "total_copies",
                0
            ),

            "available_copies": book.get(
                "available_copies",
                0
            ),

            "shelf_location": book.get(
                "shelf_location"
            ),

            "library_available": book.get(
                "library_available",
                False
            ),

            "score": scores[
                "score"
            ],

            "score_breakdown": scores
        }

        recommendations.append(
            recommendation
        )

    # ========================================================
    # SORT BY FINAL SCORE
    # ========================================================

    recommendations.sort(
        key=lambda item: item[
            "score"
        ],
        reverse=True
    )

    # ========================================================
    # V2.6: DIVERSITY RE-RANKING
    #
    # Applied AFTER scoring and sorting.
    # Ensures the final list is not dominated by
    # near-identical books, authors, or subjects.
    # ========================================================

    diverse_results = apply_diversity_reranking(
        recommendations,
        limit
    )

    # ========================================================
    # RETURN TOP N
    # ========================================================

    return diverse_results[
        :limit
    ]