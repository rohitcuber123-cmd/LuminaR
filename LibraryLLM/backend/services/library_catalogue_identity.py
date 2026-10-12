"""Pure identity compatibility rules shared by API and read-only migration planning."""
from backend.schemas.library_catalogue import normalize_values


def normalized_title(title):
    return ' '.join(title.casefold().split())


def compatible(left, right):
    if normalized_title(left.get('title', '')) != normalized_title(right.get('title', '')):
        return False
    for field in ('edition', 'publication_year', 'publisher'):
        if left.get(field) and right.get(field) and str(left[field]).casefold() != str(right[field]).casefold():
            return False
    left_authors = {value.casefold() for value in normalize_values(left.get('authors'))}
    right_authors = {value.casefold() for value in normalize_values(right.get('authors'))}
    return not (left_authors and right_authors and left_authors.isdisjoint(right_authors))
