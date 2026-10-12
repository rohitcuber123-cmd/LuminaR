import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from backend.database.mongodb import books_collection


# ============================================================
# CONFIG
# ============================================================

TARGET_FILE = Path(__file__).parent / "target_books.json"
OUTPUT_FOUND = Path(__file__).parent / "rag_candidates.json"
OUTPUT_MISSING = Path(__file__).parent / "rag_missing.json"
OUTPUT_REVIEW = Path(__file__).parent / "rag_review.json"

# Matching thresholds
STRONG_MATCH = 0.90
REVIEW_MATCH = 0.75


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(value):
    """Normalize text for comparison."""

    if value is None:
        return ""

    value = str(value)

    # Unicode normalization
    value = unicodedata.normalize("NFKD", value)

    # Remove accents
    value = "".join(
        c for c in value
        if not unicodedata.combining(c)
    )

    # Lowercase
    value = value.lower()

    # Normalize punctuation
    value = value.replace("&", " and ")

    # Remove punctuation
    value = re.sub(r"[^a-z0-9\s]", " ", value)

    # Normalize whitespace
    value = re.sub(r"\s+", " ", value).strip()

    return value


def normalize_author(value):
    """Normalize author names."""

    value = normalize_text(value)

    # Handle "last, first"
    if "," in str(value):
        parts = [p.strip() for p in str(value).split(",", 1)]

        if len(parts) == 2:
            value = f"{parts[1]} {parts[0]}"

    return value


def title_similarity(a, b):
    a = normalize_text(a)
    b = normalize_text(b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    # Handle "the X" vs "X"
    a_no_the = re.sub(r"^the\s+", "", a)
    b_no_the = re.sub(r"^the\s+", "", b)

    if a_no_the == b_no_the:
        return 0.98

    return SequenceMatcher(None, a, b).ratio()


def author_similarity(a, b):
    a = normalize_author(a)
    b = normalize_author(b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    return SequenceMatcher(None, a, b).ratio()


# ============================================================
# AUTHOR EXTRACTION
# ============================================================

def extract_authors(book):
    """
    Try several possible author field structures used by
    Open Library / processed datasets.
    """

    authors = []

    value = (
        book.get("authors")
        or book.get("author")
        or book.get("author_name")
        or book.get("author_names")
    )

    if not value:
        return authors

    if isinstance(value, str):
        return [value]

    if isinstance(value, list):

        for item in value:

            if isinstance(item, str):
                authors.append(item)

            elif isinstance(item, dict):
                name = (
                    item.get("name")
                    or item.get("author")
                    or item.get("author_name")
                )

                if name:
                    authors.append(str(name))

    return authors


# ============================================================
# WORK ID EXTRACTION
# ============================================================

def extract_work_id(book):

    work_id = (
        book.get("work_id")
        or book.get("work")
        or book.get("key")
    )

    if isinstance(work_id, dict):
        work_id = (
            work_id.get("key")
            or work_id.get("work_id")
        )

    if not work_id:
        return None

    work_id = str(work_id)

    # Open Library work IDs sometimes appear as:
    # /works/OL123W
    if "/works/" in work_id:
        work_id = work_id.split("/works/")[-1]

    return work_id


# ============================================================
# ISBN EXTRACTION
# ============================================================

def extract_isbn(book):

    for field in [
        "isbn",
        "isbn10",
        "isbn13",
        "isbn_10",
        "isbn_13",
        "isbn_list",
    ]:

        value = book.get(field)

        if value:

            if isinstance(value, list):
                return value[0] if value else None

            return value

    return None


# ============================================================
# MONGODB SEARCH
# ============================================================

def get_candidate_documents(title):

    """
    Use MongoDB to find title candidates.

    This does NOT load the 5M collection into memory.
    """

    # First try exact title.
    candidates = list(
        books_collection.find(
            {
                "title": {
                    "$regex": f"^{re.escape(title)}$",
                    "$options": "i"
                }
            }
        ).limit(50)
    )

    if candidates:
        return candidates

    # Then try a contains search.
    candidates = list(
        books_collection.find(
            {
                "title": {
                    "$regex": re.escape(title),
                    "$options": "i"
                }
            }
        ).limit(100)
    )

    return candidates


# ============================================================
# MATCH ONE BOOK
# ============================================================

def find_book(target):

    target_title = target["title"]
    target_author = target.get("author", "")

    candidates = get_candidate_documents(target_title)

    results = []

    for book in candidates:

        catalog_title = book.get("title", "")

        authors = extract_authors(book)

        # If no author information exists, still allow title
        # matching, but don't give it maximum confidence.
        if authors:
            best_author_score = max(
                author_similarity(target_author, author)
                for author in authors
            )
        else:
            best_author_score = 0.0

        title_score = title_similarity(
            target_title,
            catalog_title
        )

        # Combined score.
        if authors:
            score = (
                title_score * 0.65
                + best_author_score * 0.35
            )
        else:
            score = title_score * 0.75

        # Determine match method.
        if title_score == 1.0 and best_author_score == 1.0:
            method = "title_author_exact"

        elif title_score >= 0.95 and best_author_score >= 0.90:
            method = "title_author_strong"

        elif title_score >= 0.90:
            method = "title_strong"

        else:
            method = "fuzzy"

        results.append(
            {
                "book": book,
                "title_score": round(title_score, 4),
                "author_score": round(best_author_score, 4),
                "score": round(score, 4),
                "method": method,
            }
        )

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results


# ============================================================
# FORMAT RESULT
# ============================================================

def format_result(target, result):

    book = result["book"]

    authors = extract_authors(book)

    return {
        "requested_title": target["title"],
        "requested_author": target.get("author", ""),

        "catalog_title": book.get("title"),

        "catalog_authors": authors,

        "work_id": extract_work_id(book),

        "book_id": book.get("book_id"),

        "isbn": extract_isbn(book),

        "match_method": result["method"],

        "confidence": result["score"],

        "title_score": result["title_score"],

        "author_score": result["author_score"],
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 60)
    print(" LuminaR RAG Book Availability Check")
    print("=" * 60)
    print()

    # --------------------------------------------------------
    # Load targets
    # --------------------------------------------------------

    if not TARGET_FILE.exists():

        print(
            f"ERROR: {TARGET_FILE} does not exist."
        )

        sys.exit(1)

    with open(
        TARGET_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        targets = json.load(f)

    print(
        f"Loaded {len(targets)} requested books."
    )

    print()

    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------

    found = []
    missing = []
    review = []

    for index, target in enumerate(
        targets,
        start=1
    ):

        title = target["title"]
        author = target.get("author", "")

        print(
            f"[{index}/{len(targets)}] "
            f"Searching: {title} — {author}"
        )

        matches = find_book(target)

        if not matches:

            print("    ✗ NOT FOUND")
            print()

            missing.append(target)

            continue

        best = matches[0]

        formatted = format_result(
            target,
            best
        )

        confidence = best["score"]

        # ----------------------------------------------------
        # Strong match
        # ----------------------------------------------------

        if (
            confidence >= STRONG_MATCH
            and formatted["work_id"]
        ):

            print("    ✓ FOUND")

            print(
                f"      Title: "
                f"{formatted['catalog_title']}"
            )

            print(
                f"      Author: "
                f"{', '.join(formatted['catalog_authors'])}"
            )

            print(
                f"      Work ID: "
                f"{formatted['work_id']}"
            )

            print(
                f"      Confidence: "
                f"{confidence:.2f}"
            )

            print()

            found.append(formatted)

        # ----------------------------------------------------
        # Needs review
        # ----------------------------------------------------

        elif confidence >= REVIEW_MATCH:

            print("    ? NEEDS REVIEW")

            print(
                f"      Candidate: "
                f"{formatted['catalog_title']}"
            )

            print(
                f"      Work ID: "
                f"{formatted['work_id']}"
            )

            print(
                f"      Confidence: "
                f"{confidence:.2f}"
            )

            print()

            # Include top candidates
            review_entry = {
                "requested_title": title,
                "requested_author": author,
                "candidates": [
                    format_result(
                        target,
                        candidate
                    )
                    for candidate in matches[:5]
                ],
            }

            review.append(review_entry)

        # ----------------------------------------------------
        # Missing
        # ----------------------------------------------------

        else:

            print("    ✗ NOT FOUND")

            print()

            missing.append(target)

    # --------------------------------------------------------
    # Save results
    # --------------------------------------------------------

    with open(
        OUTPUT_FOUND,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            found,
            f,
            indent=2,
            ensure_ascii=False
        )

    with open(
        OUTPUT_MISSING,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            missing,
            f,
            indent=2,
            ensure_ascii=False
        )

    with open(
        OUTPUT_REVIEW,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            review,
            f,
            indent=2,
            ensure_ascii=False
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print(" SUMMARY")
    print("=" * 60)

    print(
        f"Requested:    {len(targets)}"
    )

    print(
        f"Found:        {len(found)}"
    )

    print(
        f"Missing:      {len(missing)}"
    )

    print(
        f"Needs review: {len(review)}"
    )

    print()
    print(
        f"Found books:  {OUTPUT_FOUND}"
    )

    print(
        f"Missing:      {OUTPUT_MISSING}"
    )

    print(
        f"Review:       {OUTPUT_REVIEW}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()